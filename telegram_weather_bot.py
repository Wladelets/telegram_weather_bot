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
import asyncio

# === Загрузка переменных окружения ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# === Логгирование ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# === Обработка ошибок ===
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="\u274c Ошибка при обработке обновления:", exc_info=context.error)
    if isinstance(update, Update) and update.message:
        await update.message.reply_text("\u26a0\ufe0f Произошла ошибка. Мы уже работаем над этим.")


# === Обработка геолокации ===
async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    await message.reply_text("\u0421пасибо! 🛠", reply_markup=ReplyKeyboardRemove())

    user = update.effective_user
    location = message.location
    lat = location.latitude
    lon = location.longitude
    username = f"@{user.username}" if user.username else f"{user.full_name} (id:{user.id})"

    # Определение адреса
    address = "не удалось определить"
    try:
        geolocator = Nominatim(user_agent="telegram-weather-bot")
        location_info = geolocator.reverse((lat, lon), language="ru", timeout=10)
        if location_info:
            address = location_info.address
    except Exception as e:
        logger.warning(f"Geo error: {e}")

    # Определение локального времени
    try:
        tz = pytz.timezone("Europe/Kiev")
        local_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        local_time = "Не удалось определить"

    # Прогноз погоды
    forecast = ""
    try:
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
        res = requests.get(url)
        res.raise_for_status()
        data = res.json()

        if "list" in data:
            forecast += "\n☁️ Прогноз погоды:\n"
            for entry in data["list"][:4]:
                dt = entry["dt_txt"]
                temp = entry["main"]["temp"]
                desc = entry["weather"][0]["description"]
                forecast += f"{dt}: {temp}°C, {desc}\n"
        else:
            forecast += "\u26a0\ufe0f Не удалось получить погоду."
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error from OpenWeather: {e}")
        forecast += "\u26a0\ufe0f Ошибка HTTP при получении погоды."
    except ValueError as e:
        logger.error(f"JSON parse error: {e}")
        forecast += "\u26a0\ufe0f Ошибка подразборки JSON."
    except Exception as e:
        logger.error(f"Weather error: {e}")
        forecast += "\u26a0\ufe0f Ошибка при погоде."

    # Ответ пользователю
    reply_msg = (
        f"🌍 Координаты:\n"
        f"Широта: {lat:.5f}\n"
        f"Долгота: {lon:.5f}\n\n"
        f"📍 Адрес: {address}\n"
        f"🕒 Местное время: {local_time} (Europe/Kiev)\n"
        f"{forecast}"
    )
    await message.reply_text(reply_msg)

    # Уведомление админу
    admin_msg = (
        f"🧽 Локация от {username}\n"
        f"📍 Адрес: {address}\n"
        f"🌐 Координаты: {lat:.5f}, {lon:.5f}\n"
        f"🕒 Время: {local_time}\n"
        f"{forecast}"
    )
    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg)


# === Команда /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Пришли свою геолокацию 📍")


# === Запуск бота с Webhook ===
async def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.LOCATION, handle_location))
    application.add_error_handler(error_handler)

    await application.initialize()
    await application.start()
    await application.bot.set_webhook(url=WEBHOOK_URL)
    await application.updater.start_webhook()
    await application.updater.wait_for_stop()
    await application.stop()
    await application.shutdown()


if __name__ == "__main__":
    asyncio.run(main())


