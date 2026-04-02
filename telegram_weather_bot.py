import os
import logging
import requests
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# === Загрузка .env ===
load_dotenv()

BOT_TOKEN = os.getenv("8045976543:AAH0ZIq-MLRiUYFCioNJlPEaFgUYSoe4RQw")
OWNER_ID = os.getenv("7749916934")
OPENWEATHER_TOKEN = os.getenv("a6115733a483924112f4edb9f3c83482")
WEBHOOK_HOST = os.getenv("https://telegram-weather-botq.onrender.com")   # Например: https://telegram-weather-botq.onrender.com
PORT = int(os.getenv("PORT", 10000))       # Render обычно использует 10000

if not BOT_TOKEN or not OPENWEATHER_TOKEN:
    raise ValueError("❌ BOT_TOKEN или OPENWEATHER_TOKEN не установлены!")

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}" if WEBHOOK_HOST else None

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# === Получить адрес ===
def get_address(lat: float, lon: float) -> str:
    try:
        geolocator = Nominatim(user_agent="telegram-weather-bot")
        location = geolocator.reverse((lat, lon), language="ru")
        return location.address if location else "Адрес не найден"
    except Exception as e:
        logging.error(f"Ошибка геокодера: {e}")
        return "Не удалось определить адрес"


# === Получить погоду (синхронно) ===
def get_weather(lat: float, lon: float) -> str:
    try:
        url = (
            f"https://api.openweathermap.org/data/2.5/weather?"
            f"lat={lat}&lon={lon}&appid={OPENWEATHER_TOKEN}&units=metric&lang=ru"
        )
        r = requests.get(url, timeout=10)
        data = r.json()

        if r.status_code != 200 or "main" not in data:
            return "Не удалось получить данные о погоде 😞"

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
    except Exception as e:
        logging.error(f"Ошибка погоды: {e}")
        return "Ошибка при получении погоды 😞"


# === Команды ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Пришли мне свою геолокацию 📍")


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.message.from_user
        location = update.message.location
        lat, lon = location.latitude, location.longitude

        address = get_address(lat, lon)
        weather = get_weather(lat, lon)

        map_url = f"https://static-maps.yandex.ru/1.x/?ll={lon},{lat}&size=450,300&z=14&l=map&pt={lon},{lat},pm2rdm"

        msg = (
            f"📍 Геолокация:\n"
            f"Широта: {lat}\nДолгота: {lon}\n\n"
            f"🏠 Адрес: {address}\n\n"
            f"{weather}"
        )

        await update.message.reply_photo(photo=map_url, caption=msg)

        # Отправка владельцу
        if OWNER_ID:
            try:
                owner_id = int(OWNER_ID)
                owner_msg = (
                    f"👤 @{user.username or user.first_name} прислал геолокацию:\n"
                    f"🗺 {address}\n"
                    f"📍 lat={lat}, lon={lon}\n\n"
                    f"{weather}"
                )
                await context.bot.send_photo(chat_id=owner_id, photo=map_url, caption=owner_msg)
            except ValueError:
                logging.error("OWNER_ID не является числом")

    except Exception as e:
        logging.error(f"Ошибка в handle_location: {e}")
        await update.message.reply_text("Произошла ошибка при обработке локации.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"Ошибка: {context.error}", exc_info=context.error)


# === Запуск ===
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.LOCATION, handle_location))
    application.add_error_handler(error_handler)

    if WEBHOOK_URL:
        logging.info(f"Запуск через webhook → {WEBHOOK_URL}")
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=WEBHOOK_PATH,
            webhook_url=WEBHOOK_URL,
            allowed_updates=["message"]
        )
    else:
        logging.info("Запуск через polling (для теста)")
        application.run_polling()


if __name__ == "__main__":
    main()
