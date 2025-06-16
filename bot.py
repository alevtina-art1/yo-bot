import logging
import os
import json
import tempfile
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from dotenv import load_dotenv
import openai

# Загрузка переменных окружения
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Проверка переменных окружения
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in environment variables.")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set in environment variables.")

openai.api_key = OPENAI_API_KEY

# Настройки
ADMIN_ID = 5576028179
TARIFFS = {
    "smell":     {"title": "Понюхай",          "price": 0,    "limit": 50},
    "basic":     {"title": "Просто хам",       "price": 99,   "limit": 50},
    "simple":    {"title": "Буду проще",       "price": 299,  "limit": 100},
    "etiquette": {"title": "Чхал на этикет",   "price": 499,  "limit": 300},
    "truth":     {"title": "Бесценная правда", "price": 699,  "limit": 600},
    "ebamurena": {"title": "Ебамурена",        "price": 1099, "limit": 2000},
}
TEMPLATES_PATH = "expired_templates.json"
USER_DATA_PATH = "user_data.json"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка шаблонов с обработкой ошибок
try:
    with open(TEMPLATES_PATH, "r", encoding="utf-8") as f:
        expired_templates = json.load(f)
        if not isinstance(expired_templates, list) or not expired_templates:
            raise ValueError("expired_templates.json must contain a non-empty list.")
except Exception as e:
    logger.error("Ошибка загрузки шаблонов: %s", e)
    expired_templates = ["Лимит сообщений исчерпан. Купи тариф или подожди."]

# Загрузка базы пользователей
def load_users():
    if not os.path.exists(USER_DATA_PATH):
        return {}
    try:
        with open(USER_DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Ошибка чтения user_data.json: %s", e)
        return {}

def save_users(data):
    try:
        with open(USER_DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error("Ошибка сохранения user_data.json: %s", e)

# Генерация ответа от ИИ
async def generate_reply(prompt: str) -> str:
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Отвечай как дерзкий уличный помощник."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.9
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error("Error in generate_reply: %s", e)
        return "Ошибка при генерации ответа. Попробуй позже."

# Озвучка
async def get_tts_filename(text: str, gender: str) -> str | None:
    voice = "ru-RU-VeraNeural" if gender == "female" else "ru-RU-DmitryNeural"
    try:
        audio_data = openai.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text
        )
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        with open(tmp.name, "wb") as f:
            f.write(audio_data.content)
        return tmp.name
    except Exception as e:
        logger.error("TTS error: %s", e)
        return None

# Обработчик ошибок приложения
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception while handling update %s: %s", update, context.error)

# Хендлеры
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Емааа! Дарова, короче.\n"
        "Я твой бро или подруга. Базарю резко, могу и послать. Кто ты, пацан или баба?"
    )
    kb = [[InlineKeyboardButton("👊 Пацаан", callback_data="gender_male"),
           InlineKeyboardButton("💁 Баба", callback_data="gender_female")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def gender_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    gender = update.callback_query.data.split('_')[1]
    context.user_data['gender'] = gender
    text = f"Окей, {'бро' if gender=='male' else 'подруга'}! Ты согласен, что тебя будут подстёбывать и посылать?"
    kb = [[InlineKeyboardButton("✅ Согласен", callback_data="consent_yes"),
           InlineKeyboardButton("❌ Я-лох", callback_data="consent_no")]]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def consent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    if update.callback_query.data.endswith('no'):
        return await update.callback_query.edit_message_text("Ну и иди тогда. /start если передумаешь.")
    user_id = str(update.callback_query.from_user.id)
    users = load_users()
    users[user_id] = {'tariff': 'smell', 'messages': 0, 'gender': context.user_data.get('gender', 'male')}
    save_users(users)
    text = "Чекай тарифы х*ифы ниже:"
    kb = [[InlineKeyboardButton("💰 Тарифы х*ифы", callback_data="show_tariffs")]]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def show_tariffs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    parts = [f"🔹 *{v['title']}* — {v['price']}₽ ({v['limit']} сообщений)" for v in TARIFFS.values()]
    text = '*Тарифы х*ифы:*
' + '\n'.join(parts)
    keyboard = [[InlineKeyboardButton(f"{v['title']} — {v['price']}₽", callback_data=f"pay_{k}")]
                for k, v in TARIFFS.items()]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def pay_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    tariff_key = update.callback_query.data.split('_', 1)[1]
    user_id = str(update.callback_query.from_user.id)
    users = load_users()
    if user_id in users:
        users[user_id]['tariff'] = tariff_key
        save_users(users)
    title = TARIFFS.get(tariff_key, {}).get('title', tariff_key)
    await update.callback_query.edit_message_text(
        f"Тариф *{title}* выбран. (Заглушка оплаты)\nПогнали!", parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    text = update.message.text
    users = load_users()
    if user_id not in users:
        return await update.message.reply_text("Сначала жми /start, чудо.")
    user = users[user_id]
    tariff = TARIFFS.get(user['tariff'], list(TARIFFS.values())[0])
    if user['messages'] >= tariff['limit']:
        return await update.message.reply_text(random.choice(expired_templates))
    reply = await generate_reply(text)
    users[user_id]['messages'] += 1
    save_users(users)
    await update.message.reply_text(reply)
    mp3_path = await get_tts_filename(reply, user.get('gender', 'male'))
    if mp3_path and os.path.exists(mp3_path):
        await update.message.reply_voice(voice=InputFile(mp3_path))
        try:
            os.remove(mp3_path)
        except Exception as e:
            logger.warning("Не удалось удалить временный файл: %s", e)

# Запуск бота
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_error_handler(error_handler)
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(gender_callback, pattern='^gender_'))
    app.add_handler(CallbackQueryHandler(consent_callback, pattern='^consent_'))
    app.add_handler(CallbackQueryHandler(show_tariffs, pattern='^show_tariffs$'))
    app.add_handler(CallbackQueryHandler(pay_callback, pattern='^pay_'))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Бот запущен и ждёт сообщений")
    try:
        app.run_polling()
    except Exception as e:
        logger.exception("Неожиданная ошибка при запуске бота: %s", e)
