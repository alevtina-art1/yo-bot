import logging
import os
import tempfile
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from openai import OpenAI
from dotenv import load_dotenv
from templates_logic import get_reply_from_templates

# ——— Конфиг ———
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = 5576028179

if not BOT_TOKEN:
    raise RuntimeError("Environment variable TELEGRAM_TOKEN is not set")
if not OPENAI_API_KEY:
    raise RuntimeError("Environment variable OPENAI_API_KEY is not set")

TARIFFS = {
    "poniuhai":  {"title": "Понюхай",          "limit": 50,   "price": 0},
    "basic":     {"title": "Просто хам",       "limit": 100,  "price": 99},
    "simple":    {"title": "Буду проще",       "limit": 100,  "price": 299},
    "etiquette": {"title": "Чхал на этикет",   "limit": 300,  "price": 499},
    "truth":     {"title": "Бесценная правда",  "limit": 600,  "price": 699},
    "ebamurena": {"title": "Ебамурена",        "limit": 2000, "price": 1099},
}

# Временное хранение пользователей
user_data: dict[int, dict] = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
client = OpenAI(api_key=OPENAI_API_KEY)

# ——— OpenAI-ответ ———
async def ask_openai(prompt: str) -> str:
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error("Error in OpenAI request: %s", e)
        return f"⚠️ Ошибка ИИ: {e}"

# ——— /start ———
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    kb = [
        [
            InlineKeyboardButton("👊 Я пацан", callback_data="gender_male"),
            InlineKeyboardButton("💅 Я баба",   callback_data="gender_female"),
        ]
    ]
    await update.message.reply_text(
        "Емааа! Дарова, ща разберёмся кто ты.\nТы вообще кто по жизни?",
        reply_markup=InlineKeyboardMarkup(kb),
    )

# ——— пол ———
async def gender_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    gender = update.callback_query.data.split("_")[1]
    user_id = update.effective_user.id
    user_data[user_id] = {"gender": gender, "tariff": "poniuhai", "used": 0}
    await update.callback_query.edit_message_text(
        "Ты серьёзно согласен, что тебя тут будут подстёбывать, стебать и даже слать? 😂",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Согласен", callback_data="consent_yes"),
                InlineKeyboardButton("❌ Я слабак", callback_data="consent_no"),
            ]
        ]),
    )

# ——— согласие ———
async def consent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    if update.callback_query.data == "consent_no":
        return await update.callback_query.edit_message_text("Ну и катись, /start если надумаешь.")
    await update.callback_query.edit_message_text(
        "Респект, ты в деле. Ниже — тарифы х*ифы:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Тарифы х*ифы", callback_data="tariffs")],
            [InlineKeyboardButton("❓ За что плачу?", callback_data="why_pay")],
        ]),
    )

# ——— тарифы ———
async def show_tariffs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    text = "*Тарифы х*ифы:*\n"
    for key, t in TARIFFS.items():
        text += f"🔸 *{t['title']}* — {t['price']}₽ ({t['limit']} смс)\n"
    kb = [
        [InlineKeyboardButton(f"Купить {t['title']}", callback_data=f"buy_{key}")]
        for key, t in TARIFFS.items() if t['price'] > 0
    ]
    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )

# ——— Покупка тарифа ———
async def buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    tariff = update.callback_query.data.split("_")[1]
    user_id = update.effective_user.id
    if user_id in user_data:
        user_data[user_id]['tariff'] = tariff
    title = TARIFFS.get(tariff, {}).get('title', tariff)
    await update.callback_query.edit_message_text(
        f"Выбран тариф: *{title}*. Пока оплата заглушка.\nСкоро прикрутим — не ной.",
        parse_mode="Markdown",
    )

# ——— почему платим ———
async def why_pay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    text = (
        "Ты платишь за:\n"
        "— Мощь ChatGPT без VPN\n"
        "— Озвучку и стиль\n"
        "— Ответы по картинке, фотке, голосом\n"
        "— Ну и за кайф, ага."
    )
    await update.callback_query.edit_message_text(text)

# ——— текстовые сообщения ———
async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    msg = update.message.text
    if user_id not in user_data:
        return await update.message.reply_text("Жми /start сначала.")
    u = user_data[user_id]
    u['used'] += 1
    limit = TARIFFS[u['tariff']]['limit']
    if u['used'] > limit:
        tpl = get_reply_from_templates(msg)
        return await update.message.reply_text(tpl)
    reply = await ask_openai(msg)
    await update.message.reply_text(reply)

# ——— голосовые сообщения ———
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id not in user_data:
        return await update.message.reply_text("Жми /start сначала.")
    u = user_data[user_id]
    u['used'] += 1
    limit = TARIFFS[u['tariff']]['limit']
    if u['used'] > limit:
        tpl = get_reply_from_templates("")
        return await update.message.reply_text(tpl)
    voice = update.message.voice
    if not voice:
        return
    file = await voice.get_file()
    tmp_path = tempfile.NamedTemporaryFile(delete=False, suffix=".ogg").name
    await file.download_to_drive(tmp_path)
    try:
        with open(tmp_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="json"
            )
        text = transcript.text
    except Exception as e:
        logger.error("Error in transcription: %s", e)
        await update.message.reply_text("⚠️ Не удалось распознать голосовое сообщение.")
        os.remove(tmp_path)
        return
    os.remove(tmp_path)
    reply = await ask_openai(text)
    await update.message.reply_text(reply)

# ——— запуск ———
def main() -> None:
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(gender_callback, pattern="^gender_"))
    app.add_handler(CallbackQueryHandler(consent_callback, pattern="^consent_"))
    app.add_handler(CallbackQueryHandler(show_tariffs, pattern="^tariffs$"))
    app.add_handler(CallbackQueryHandler(buy_callback, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(why_pay, pattern="^why_pay$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    logger.info("Бот запущен и ждёт сообщений")
    app.run_polling()

if __name__ == "__main__":
    main()
