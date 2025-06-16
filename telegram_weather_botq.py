import json
import logging
import os
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
from typing import Dict, Any

user_locations = {}

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
                return "Не удалось получить прогноз."

            forecast_lines = ["📅 Прогноз погоды (ближайшие часы):"]
            for item in data["list"][:4]:
                time = item["dt_txt"]
                temp = item["main"]["temp"]
                desc = item["weather"][0]["description"].capitalize()
                wind = item["wind"]["speed"]
                forecast_lines.append(f"🕓 {time} — {desc}, 🌡 {temp}°C, 💨 {wind} м/с")

            return "\n".join(forecast_lines)
    except Exception as e:
        logging.error(f"Ошибка получения прогноза: {e}")
        return "Ошибка получения прогноза."

# === Обработчики Telegram ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    keyboard = [[KeyboardButton(text="📍 Отправить геолокацию", request_location=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        "Привет! Нажми кнопку ниже, чтобы узнать погоду:",
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
        user_locations[user.id] = (lat, lon)

        address = get_address(lat, lon)
        weather = await get_weather(lat, lon)
            map_url = (
            f"https://static-maps.yandex.ru/1.x/"
            f"?ll={lon},{lat}&size=450,300&z=14&l=map&pt={lon},{lat},pm2rdm"
        )

        forecast = await get_forecast(lat, lon)
        
        
        caption = (
            f"📍 Широта: {lat}\n"
            f"Долгота: {lon}\n"
            f"🏠 Адрес: {address}\n\n"
            f"{weather}\n\n"
            f"{forecast}"
        )

     

        await update.message.reply_photo(photo=map_url, caption=caption)

        if OWNER_ID:
            await context.bot.send_photo(chat_id=OWNER_ID, photo=map_url, caption=caption)

    except Exception as e:
        logging.error(f"Ошибка в handle_location: {e}")
        await update.message.reply_text("Произошла ошибка при обработке локации.")

async def forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.message.from_user.id
        user_data = user_locations.get(user_id)
        if not user_data:
            await update.message.reply_text("Сначала отправьте своё местоположение с помощью кнопки /start.")
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
bot_app.add_handler(CommandHandler("forecast", forecast))
bot_app.add_handler(MessageHandler(filters.LOCATION, handle_location))
bot_app.add_handler(MessageHandler(filters.COMMAND, unknown))
bot_app.add_error_handler(error_handler)

@app.get("/")
async def root():
    return {"status": "OK", "message": "Бот работает через webhook."}

@app.post(WEBHOOK_PATH)
async def webhook_handler(update: Dict[str, Any]):
    telegram_update = Update.de_json(update, bot_app.bot)
    await bot_app.process_update(telegram_update)
    return {"status": "ok"}

@app.on_event("startup")
async def on_startup():
    try:
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.bot.set_webhook(WEBHOOK_URL)
        print(f"✅ Webhook установлен: {WEBHOOK_URL}")
    except Exception as e:
        print(f"❌ Не удалось установить webhook: {e}")


    
