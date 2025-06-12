import os
import json
import logging

from fastapi import FastAPI, Request
from telegram import Update, Bot, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from geopy.geocoders import Nominatim
from dotenv import load_dotenv
from httpx import AsyncClient

# === Загрузка переменных окружения ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", 0))
OPENWEATHER_TOKEN = os.getenv("OPENWEATHER_TOKEN")

assert BOT_TOKEN, "❌ BOT_TOKEN не установлен в .env"
assert OPENWEATHER_TOKEN, "❌ OPENWEATHER_TOKEN не установлен в .env"

bot = Bot(token=BOT_TOKEN)

# === Константы ===
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"https://telegram-weather-botq.onrender.com{WEBHOOK_PATH}"

# === FastAPI-приложение ===
app = FastAPI()

# === Геокодер ===
geolocator = Nominatim(user_agent="telegram-weather-bot")


def get_address(lat, lon):
    try:
        location = geolocator.reverse((lat, lon), language="ru")
        return location.address if location else "Адрес не найден"
    except Exception as e:
        logging.error(f"Ошибка при получении адреса: {e}")
        return "Ошибка при определении адреса"


# === Получение текущей погоды ===
async def get_weather(lat: float, lon: float) -> str:
    try:
        async with AsyncClient() as client:
            response = await client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={
                    "lat": lat,
                    "lon": lon,
                    "appid": OPENWEATHER_TOKEN,
                    "units": "metric",
                    "lang": "ru",
                },
            )
            data = response.json()
            if response.status_code != 200 or "main" not in data:
                return "Не удалось получить погоду."
            return (
                f"🌤 {data['weather'][0]['description'].capitalize()}\n"
                f"🌡 Температура: {data['main']['temp']}°C\n"
                f"🤔 Ощущается как: {data['main']['feels_like']}°C\n"
                f"💧 Влажность: {data['main']['humidity']}%\n"
                f"💨 Ветер: {data['wind']['speed']} м/с"
            )
    except Exception as e:
        logging.error(f"Ошибка получения погоды: {e}")
        return "Ошибка получения погоды."


# === Получение прогноза погоды ===
async def get_forecast(lat: float, lon: float) -> str:
    try:
        async with AsyncClient() as client:
            response = await client.get(
                "https://api.openweathermap.org/data/2.5/forecast",
                params={
                    "lat": lat,
                    "lon": lon,
                    "appid": OPENWEATHER_TOKEN,
                    "units": "metric",
                    "lang": "ru",
                },
            )
            data = response.json()
            if response.status_code != 200 or "list" not in data:
                return "Не удалось получить прогноз погоды."

            forecasts = data["list"][:4]  # ближайшие 4 записи (примерно 12 часов)
            result = "📅 Прогноз на ближайшие часы:\n"
            for f in forecasts:
                time = f["dt_txt"][11:16]
                desc = f["weather"][0]["description"].capitalize()
                temp = f["main"]["temp"]
                wind = f["wind"]["speed"]
                result += f"🕒 {time}: {desc}, 🌡 {temp}°C, 💨 {wind} м/с\n"
            return result
    except Exception as e:
        logging.error(f"Ошибка получения прогноза: {e}")
        return "Ошибка получения прогноза погоды."


# === Обработчики Telegram ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    keyboard = [[KeyboardButton(text="📍 Отправить геолокацию", request_location=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        "Привет! Нажми кнопку ниже, чтобы отправить мне своё местоположение:",
        reply_markup=reply_markup
    )

    if OWNER_ID:
        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"👤 Пользователь @{user.username or user.first_name} нажал /start"
        )


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.message.from_user
        location = update.message.location
        lat, lon = location.latitude, location.longitude

        context.user_data["last_location"] = (lat, lon)  # Сохраняем координаты

        address = get_address(lat, lon)
        weather = await get_weather(lat, lon)

        map_url = (
            f"https://static-maps.yandex.ru/1.x/"
            f"?ll={lon},{lat}&size=450,300&z=14&l=map&pt={lon},{lat},pm2rdm"
        )

        caption = (
            f"📍 Широта: {lat}\n"
            f"Долгота: {lon}\n"
            f"🏠 Адрес: {address}\n\n{weather}"
        )

        await update.message.reply_photo(photo=map_url, caption=caption)

        if OWNER_ID:
            owner_msg = (
                f"👤 @{user.username or user.first_name} отправил локацию:\n{caption}"
            )
            await context.bot.send_photo(chat_id=OWNER_ID, photo=map_url, caption=owner_msg)

    except Exception as e:
        logging.error(f"Ошибка в handle_location: {e}")
        await update.message.reply_text("Произошла ошибка при обработке локации.")


async def forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_data = context.user_data.get("last_location")
        if not user_data:
            await update.message.reply_text("Сначала отправьте своё местоположение через /start.")
            return

        lat, lon = user_data
        forecast_text = await get_forecast(lat, lon)
        await update.message.reply_text(forecast_text)

    except Exception as e:
        logging.error(f"Ошибка в forecast: {e}")
        await update.message.reply_text("Произошла ошибка при получении прогноза.")


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Извини, я не знаю такую команду.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"Ошибка: {context.error}")


# === Telegram-приложение ===
bot_app = ApplicationBuilder().token(BOT_TOKEN).build()
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CommandHandler("forecast", forecast))  # ← добавили forecast
bot_app.add_handler(MessageHandler(filters.LOCATION, handle_location))
bot_app.add_handler(MessageHandler(filters.COMMAND, unknown))
bot_app.add_error_handler(error_handler)


# === Webhook FastAPI endpoint ===
@app.post(WEBHOOK_PATH)
async def telegram_webhook(req: Request):
    data = await req.json()
    await bot_app.update_queue.put(Update.de_json(data, bot_app.bot))
    return {"ok": True}


# === Установка webhook при запуске приложения ===
@app.on_event("startup")
async def on_startup():
    try:
        await bot_app.bot.set_webhook(WEBHOOK_URL)
        print(f"✅ Webhook установлен: {WEBHOOK_URL}")
    except Exception as e:
        print(f"❌ Не удалось установить webhook: {e}")



