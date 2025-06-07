import os
import logging
from datetime import datetime
import pytz
import requests
from geopy.geocoders import Nominatim
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram import ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv

load_dotenv()

# 🔐 Загружаем конфиденциальные данные
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OWM_KEY = os.getenv("OWM_API_KEY")

# ===🛠 ЛОГГЕР===
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ===📍 /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    button = KeyboardButton(text="🌍 Привет! Дай связь!", request_location=True)
    keyboard = ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Как ты? Друг! ⬇️", reply_markup=keyboard)

# ===📦 ОБРАБОТКА ЛОКАЦИИ===
async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user = update.effective_user
    location = message.location

    lat = location.latitude
    lon = location.longitude

    # Имя или username пользователя
    username = f"@{user.username}" if user.username else f"{user.full_name} (id:{user.id})"

    # Получаем адрес
    geolocator = Nominatim(user_agent="telegram-weather-bot")
    address = "не удалось определить"
    try:
        location_info = geolocator.reverse((lat, lon), language="ru", timeout=10)
        if location_info:
            address = location_info.address
    except Exception as e:
        logger.warning(f"Geo error: {e}")

    # Местное время
    try:
        tz = pytz.timezone("Europe/Chisinau")
        local_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        local_time = "Не удалось определить"

    base_message = (
        f"{username}, [{datetime.now().strftime('%d.%m.%Y %H:%M')}]\n"
        f"✅ Получено:\n"
        f"🌍 Широта: {lat:.5f}\n"
        f"🌍 Долгота: {lon:.5f}\n\n"
        f"📍 Местоположение: {address}\n\n"
        f"🕒 Местное время: {local_time} (Europe/Chisinau)\n\n"
    )

    # Прогноз погоды
    forecast_message = ""
    try:
        url = (
            f"https://api.openweathermap.org/data/2.5/forecast?"
            f"lat={lat}&lon={lon}&appid={OWM_KEY}&units=metric&lang=ru"
        )
        res = requests.get(url)
        data = res.json()

        if "list" in data:
            forecast = data["list"][:4]
            forecast_message = "☁️ Прогноз погоды:\n"
            for entry in forecast:
                dt_txt = entry["dt_txt"]
                temp = entry["main"]["temp"]
                description = entry["weather"][0]["description"]
                forecast_message += f"{dt_txt}: {temp}°C, {description}\n"
        else:
            forecast_message = "⚠️ Не удалось получить прогноз погоды."
    except Exception as e:
        logger.error(f"Weather error: {e}")
        forecast_message = "⚠️ Ошибка при получении погоды."

    await message.reply_text(base_message + forecast_message)
# Удаляем клавиатуру после ответа
await message.reply_text("Спасибо! 🛰", reply_markup=ReplyKeyboardRemove())

# ===🚀 MAIN ===
def main():
    if not BOT_TOKEN or not OWM_KEY:
        raise ValueError("Переменные окружения TELEGRAM_BOT_TOKEN и OWM_API_KEY не заданы!")

    port = int(os.environ.get("PORT", 10000))
    host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    webhook_url = f"https://{host}/{BOT_TOKEN}"

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))

    logger.info("Bot started")

    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        webhook_url=webhook_url
    )


if __name__ == "__main__":
    main()

