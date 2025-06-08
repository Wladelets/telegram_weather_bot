import os
import logging
import pytz
from datetime import datetime
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import requests

# Загрузка переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWM_KEY = os.getenv("OWM_KEY")
OWNER_ID = int(os.getenv("OWNER_ID"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 10000))

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Кнопка для отправки геолокации
location_keyboard = KeyboardButton(text="📍 Отправить местоположение", request_location=True)
markup = ReplyKeyboardMarkup([[location_keyboard]], resize_keyboard=True)

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Нажми кнопку ниже, чтобы отправить мне своё местоположение:",
        reply_markup=markup,
    )

async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.location:
        lat = update.message.location.latitude
        lon = update.message.location.longitude

        # Получение погоды
        weather_url = (
            f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OWM_KEY}&units=metric&lang=ru"
        )
        weather_data = requests.get(weather_url).json()

        if weather_data.get("main"):
            temp = weather_data["main"]["temp"]
            feels = weather_data["main"]["feels_like"]
            weather_description = weather_data["weather"][0]["description"].capitalize()
            city = weather_data.get("name", "неизвестный город")

            # Обратное геокодирование (получить адрес)
            geo_url = (
                f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
            )
            geo_data = requests.get(geo_url).json()
            address = geo_data.get("display_name", "Адрес не найден")

            # Местное время
            tz = pytz.timezone("Europe/Chisinau")
            local_time = datetime.now(tz).strftime("%H:%M:%S")

            # Формирование ответа
            text = (
                f"🌍 Город: {city}\n"
                f"📍 Адрес: {address}\n"
                f"🌡 Температура: {temp}°C (ощущается как {feels}°C)\n"
                f"☁️ Погода: {weather_description}\n"
                f"🕒 Местное время: {local_time} (Europe/Chisinau)\n\n"
                f"🔢 Координаты: {lat}, {lon}"
            )

            # Отправить пользователю
            await update.message.reply_text(text)

            # Отправить владельцу бота
            await context.bot.send_message(chat_id=OWNER_ID, text=f"📬 Новый пользователь:\n\n{text}")
        else:
            await update.message.reply_text("Ошибка при получении данных о погоде.")

if __name__ == "__main__":
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(MessageHandler(filters.LOCATION, location_handler))

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL,
    )


