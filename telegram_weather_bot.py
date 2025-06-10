import os
import logging
import requests
from telegram import Update, InputMediaPhoto
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes
)
from geopy.geocoders import Nominatim

# === Настройка ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = os.getenv("OWNER_ID")  # Телеграм ID владельца бота
OPENWEATHER_TOKEN = os.getenv("OPENWEATHER_TOKEN")

logging.basicConfig(level=logging.INFO)

# === Получить адрес по координатам ===
def get_address(lat, lon):
    geolocator = Nominatim(user_agent="telegram-weather-bot")
    location = geolocator.reverse((lat, lon), language="ru")
    return location.address if location else "Адрес не найден"

# === Получить погоду ===
def get_weather(lat, lon):
    url = (
        f"https://api.openweathermap.org/data/2.5/weather?"
        f"lat={lat}&lon={lon}&appid={OPENWEATHER_TOKEN}&units=metric&lang=ru"
    )
    r = requests.get(url)
    data = r.json()

    if r.status_code != 200:
        return "Не удалось получить погоду."

    desc = data["weather"][0]["description"].capitalize()
    temp = data["main"]["temp"]
    feels = data["main"]["feels_like"]
    humidity = data["main"]["humidity"]
    wind = data["wind"]["speed"]

    return (
        f"🌡 Температура: {temp}°C\n"
        f"🤔 Ощущается как: {feels}°C\n"
        f"💨 Ветер: {wind} м/с\n"
        f"💧 Влажность: {humidity}%\n"
        f"☁️ {desc}"
    )

# === Команда /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Пришли мне смайлмк 📍")


# === Обработка геолокации ===
async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    location = update.message.location
    lat, lon = location.latitude, location.longitude

    address = get_address(lat, lon)
    weather = get_weather(lat, lon)

    map_url = f"https://static-maps.yandex.ru/1.x/?ll={lon},{lat}&size=450,300&z=14&l=map&pt={lon},{lat},pm2rdm"

    # Сообщение пользователю
    msg = (
        f"📍 Геолокация:\n"
        f"Широта: {lat}\nДолгота: {lon}\n\n"
        f"🏠 Адрес: {address}\n\n"
        f"{weather}"
    )
    await update.message.reply_photo(photo=map_url, caption=msg)

    # Сообщение владельцу
    if OWNER_ID:
        owner_text = (
            f"👤 @{user.username or user.first_name} прислал геолокацию:\n"
            f"🗺 {address}\n"
            f"📍 lat={lat}, lon={lon}\n\n"
            f"{weather}"
        )
        await context.bot.send_photo(chat_id=int(OWNER_ID), photo=map_url, caption=owner_text)


# === Обработка ошибок ===
async def error_handler(update, context):
    logging.error(f"Ошибка: {context.error}")


# === Главная функция ===
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_error_handler(error_handler)

    app.run_polling()


if __name__ == "__main__":
    main()



