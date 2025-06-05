import logging
import os
from datetime import datetime
import pytz
import requests
from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from dotenv import load_dotenv

load_dotenv()

# Конфиденциальные данные
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWM_KEY = os.getenv("OWM_KEY")
GEOCODING_API_URL = "https://nominatim.openstreetmap.org/reverse"

# Настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton("📍 Как ты, друг?", request_location=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Привет! Поделись своим местоположением👇", reply_markup=reply_markup)


# Обработка геолокации
async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user = message.from_user
    latitude = message.location.latitude
    longitude = message.location.longitude

    # Получение имени пользователя
    user_name = user.username if user.username else f"ID:{user.id}"

    # Получение адреса по координатам
    address = await get_address(latitude, longitude)

    # Временная зона
    local_time = get_local_time(latitude, longitude)

    # Погода и прогноз
    weather_info = await get_weather_forecast(latitude, longitude)

    # Ответ
    response = (
        f"@{user_name}, ✅ Получено:\n"
        f"🌍 Широта: {latitude:.5f}\n"
        f"🌍 Долгота: {longitude:.5f}\n\n"
        f"📍 Местоположение: {address}\n\n"
        f"🕒 Местное время: {local_time}\n\n"
        f"{weather_info}"
    )

    await message.reply_text(response, reply_markup=ReplyKeyboardRemove())


# Получение адреса через Nominatim
async def get_address(lat, lon):
    try:
        response = requests.get(GEOCODING_API_URL, params={
            "lat": lat,
            "lon": lon,
            "format": "json",
            "accept-language": "ru"
        }, timeout=10)
        data = response.json()
        return data.get("display_name", "Не удалось определить адрес")
    except Exception as e:
        logger.error(f"Ошибка при получении адреса: {e}")
        return "Не удалось определить адрес"


# Получение локального времени
def get_local_time(lat, lon):
    try:
        timezone = "Europe/Chisinau"  # можно сделать динамическим при необходимости
        tz = pytz.timezone(timezone)
        return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S (%Z)")
    except Exception as e:
        logger.error(f"Ошибка при определении времени: {e}")
        return "Не удалось определить время"


# Получение прогноза погоды
async def get_weather_forecast(lat, lon):
    try:
        url = "https://api.openweathermap.org/data/2.5/forecast"
        params = {
            "lat": lat,
            "lon": lon,
            "appid": OWM_KEY,
            "units": "metric",
            "lang": "ru",
            "cnt": 4  # прогноз на ближайшие 4 трёхчасовых интервала
        }
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if data.get("cod") != "200":
            return "Не удалось получить данные о погоде."

        forecast = "📊 Прогноз погоды (на 12 ч):\n"
        for entry in data["list"]:
            dt = entry["dt_txt"]
            desc = entry["weather"][0]["description"].capitalize()
            temp = entry["main"]["temp"]
            wind = entry["wind"]["speed"]
            forecast += f"🕒 {dt} — {desc}, 🌡 {temp}°C, 💨 {wind} м/с\n"

        return forecast
    except Exception as e:
        logger.error(f"Ошибка при получении погоды: {e}")
        return "Не удалось получить данные о погоде."


# Основной запуск
if __name__ == "__main__":
    if not BOT_TOKEN or not OWM_KEY:
        raise ValueError("Переменные окружения BOT_TOKEN и OWM_KEY не заданы!")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))

    print("Бот запущен...")
    app.run_polling()
