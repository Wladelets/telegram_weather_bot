import os
import logging
import json
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from geopy.geocoders import Nominatim
from dotenv import load_dotenv
from httpx import AsyncClient

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", 0))
OPENWEATHER_TOKEN = os.getenv("OPENWEATHER_TOKEN")

WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"https://telegram-weather-botq.onrender.com{WEBHOOK_PATH}"

# ⬇️ Вот он, твой FastAPI app, должен быть на верхнем уровне
app = FastAPI()

# === Проверка обязательных переменных ===
assert BOT_TOKEN, "❌ BOT_TOKEN не установлен в .env"
assert OPENWEATHER_TOKEN, "❌ OPENWEATHER_TOKEN не установлен в .env"

# === FastAPI-приложение ===

# === Логирование ===
logging.basicConfig(level=logging.INFO)

# === Геокодер ===
geolocator = Nominatim(user_agent="telegram-weather-bot")

def get_address(lat, lon):
    try:
        location = geolocator.reverse((lat, lon), language="ru")
        return location.address if location else "Адрес не найден"
    except Exception as e:
        logging.error(f"Ошибка при получении адреса: {e}")
        return "Ошибка при определении адреса"

# === Получение погоды ===
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

# === Обработка /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Пришли мне свою геолокацию 📍")

# === Обработка локации ===
async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.message.from_user
        location = update.message.location
        lat, lon = location.latitude, location.longitude

        address = get_address(lat, lon)
        weather = await get_weather(lat, lon)

        map_url = f"https://static-maps.yandex.ru/1.x/?ll={lon},{lat}&size=450,300&z=14&l=map&pt={lon},{lat},pm2rdm"
        caption = f"📍 Широта: {lat}\nДолгота: {lon}\n🏠 Адрес: {address}\n\n{weather}"

        await update.message.reply_photo(photo=map_url, caption=caption)

        if OWNER_ID:
            owner_msg = f"👤 @{user.username or user.first_name} отправил локацию:\n{caption}"
            await context.bot.send_photo(chat_id=OWNER_ID, photo=map_url, caption=owner_msg)

    except Exception as e:
        logging.error(f"Ошибка в handle_location: {e}")
        await update.message.reply_text("Произошла ошибка при обработке локации.")

# === Обработка неизвестных команд ===
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Извини, я не знаю такую команду.")

# === Обработка ошибок ===
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"Ошибка: {context.error}")

# === Telegram-приложение ===
bot_app = ApplicationBuilder().token(BOT_TOKEN).build()
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(MessageHandler(filters.LOCATION, handle_location))
bot_app.add_handler(MessageHandler(filters.COMMAND, unknown))
bot_app.add_error_handler(error_handler)

# === Webhook-обработчик ===
@app.post(WEBHOOK_PATH)
async def telegram_webhook(req: Request):
    data = await req.json()
    logging.info("UPDATE INCOMING:\n%s", json.dumps(data, indent=2, ensure_ascii=False))
    await bot_app.update_queue.put(Update.de_json(data, bot_app.bot))
    return {"ok": True}

# === Установка webhook при запуске ===
@app.on_event("startup")
async def startup():
    await bot_app.bot.set_webhook(WEBHOOK_URL)
    logging.info("✅ Webhook установлен: %s", WEBHOOK_URL)

