import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
from dotenv import load_dotenv
from io import BytesIO

from templates_logic import get_reply_from_templates

load_dotenv()

# ——— Конфиг ———
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = 5576028179

TARIFFS = {
    "poniuhai": {"title": "Понюхай", "limit": 50, "price": 0},
    "basic": {"title": "Просто хам", "limit": 100, "price": 99},
    "simple": {"title": "Буду проще", "limit": 100, "price": 299},
    "etiquette": {"title": "Чхал на этикет", "limit": 300, "price": 499},
    "truth": {"title": "Бесценная правда", "limit": 600, "price": 699},
    "ebamurena": {"title": "Ебамурена", "limit": 2000, "price": 1099},
}

user_data = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
client = OpenAI(api_key=OPENAI_API_KEY)

# ——— OpenAI-ответ ———
async def ask_openai(prompt):
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ Ошибка ИИ: {str(e)}"

# ——— /start ———
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("👊 Я пацан", callback_data="gender_male"),
         InlineKeyboardButton("💅 Я баба", callback_data="gender_female")]
    ]
    await update.message.reply_text(
        "Емааа! Дарова, ща разберёмся кто ты.\nТы вообще кто по жизни?",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ——— пол ———
async def gender_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gender = update.callback_query.data.split("_")[1]
    user_id = update.effective_user.id
    user_data[user_id] = {"gender": gender, "tariff": "poniuhai", "used": 0}
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "Ты серьёзно согласен, что тебя тут будут подстёбывать, стебать и даже слать? 😂",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Согласен", callback_data="consent_yes"),
             InlineKeyboardButton("❌ Я слабак", callback_data="consent_no")]
        ])
    )

# ——— согласие ———
async def consent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.callback_query.data == "consent_no":
        await update.callback_query.edit_message_text("Ну и катись, /start если надумаешь.")
        return
    await update.callback_query.edit_message_text(
        "Респект, ты в деле. Ниже — тарифы х*ифы:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Тарифы х*ифы", callback_data="tariffs")],
            [InlineKeyboardButton("❓ За что плачу?", callback_data="why_pay")]
        ])
    )

# ——— тарифы ———
async def show_tariffs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "*Тарифы х*ифы:*\n\n"
    for key, t in TARIFFS.items():
        text += f"🔸 *{t['title']}* — {t['price']}₽ ({t['limit']} смс)\n"
    kb = [
        [InlineKeyboardButton(f"Купить {t['title']}", callback_data=f"buy_{k}")]
        for k, t in TARIFFS.items() if t["price"] > 0
    ]
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# ——— покупка ———
async def buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tariff = update.callback_query.data.split("_")[1]
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        f"Выбран тариф: *{TARIFFS[tariff]['title']}*. Пока оплата заглушка.\nСкоро прикрутим — не ной.",
        parse_mode="Markdown"
    )

# ——— почему платим ———
async def why_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "Ты платишь за:\n— Мощь ChatGPT без VPN\n— Озвучку и стиль\n— Ответы по картинке, фотке, голосом\n— Ну и за кайф, ага."
    )

# ——— сообщения ———
async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message.text

    if user_id not in user_data:
        await update.message.reply_text("Жми /start сначала.")
        return

    u = user_data[user_id]
    tariff = u["tariff"]
    u["used"] += 1

    if u["used"] > TARIFFS[tariff]["limit"]:
        template_reply = get_reply_from_templates(msg)
        await update.message.reply_text(template_reply)
        return

    reply = await ask_openai(msg)
    await update.message.reply_text(reply)

# ——— запуск ———
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(gender_callback, pattern="gender_"))
    app.add_handler(CallbackQueryHandler(consent_callback, pattern="consent_"))
    app.add_handler(CallbackQueryHandler(show_tariffs, pattern="tariffs"))
    app.add_handler(CallbackQueryHandler(buy_callback, pattern="buy_"))
    app.add_handler(CallbackQueryHandler(why_pay, pattern="why_pay"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.run_polling()

if __name__ == "__main__":
    main()
