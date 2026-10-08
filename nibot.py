import os
import sys
import logging
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import google.generativeai as genai

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# 1. Background Web Server
app_web = Flask(__name__)

@app_web.route('/')
def home() -> str:
    return "Telegram Subtitle Bot is Running!"

def run_web() -> None:
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host="0.0.0.0", port=port)

def keep_alive() -> None:
    t = Thread(target=run_web, daemon=True)
    t.start()

# ==============================================================================
# ⚠️ အောက်ပါနေရာနှစ်ခုတွင် သင့် Token နှင့် Key ကို မျက်တောင်ကွင်း " " အထဲ အတိအကျ ထည့်ပါ
# ==============================================================================
TELEGRAM_BOT_TOKEN = "8871786955:AAGy7aWgp8OyKIpBUb1pFV6O9JsYleDs8NQ"  # <-- သင့် Telegram Bot Token ထည့်ပါ
GEMINI_API_KEY = "AQ.Ab8RN6JnfAgP4wunO1fYY278tuK_3KIxwmZIQsQs6PeYJXSh_Q"                      # <-- သင့် Gemini API Key ထည့်ပါ
# ==============================================================================

genai.configure(api_key=GEMINI_API_KEY)
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB Limit

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    media = update.message.audio or update.message.video or update.message.document or update.message.voice
    if not media:
        return

    if media.file_size and media.file_size > MAX_FILE_SIZE:
        await update.message.reply_text("⚠️ 20 MB ထက်ကြီးသော ဖိုင်များကို လက်မခံနိုင်ပါ။")
        return

    await update.message.reply_text("📥 ဖိုင်လက်ခံရရှိပါပြီ။ SRT ဘာသာပြန်ဆိုနေပါသည်...")

    file_path = f"temp_{media.file_id}.mp4"
    srt_file_path = f"Myanmar_Subtitle_{media.file_id}.srt"

    try:
        file = await context.bot.get_file(media.file_id)
        await file.download_to_drive(custom_path=file_path)

        uploaded_file = genai.upload_file(file_path)
        model = genai.GenerativeModel("gemini-1.5-pro")
        prompt = (
            "Listen carefully to the audio/video. "
            "Transcribe and translate into natural Myanmar language. "
            "Format strictly as SRT subtitle (HH:MM:SS,mmm --> HH:MM:SS,mmm). "
            "Output raw SRT text only."
        )

        response = model.generate_content([uploaded_file, prompt])
        srt_content = response.text.strip() if response.text else ""

        if srt_content.startswith("```"):
            lines = srt_content.splitlines()
            if lines[0].startswith("```"): 
                lines = lines[1:]
            if lines and lines[-1].startswith("```"): 
                lines = lines[:-1]
            srt_content = "\n".join(lines)

        with open(srt_file_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        with open(srt_file_path, "rb") as doc_file:
            await update.message.reply_document(
                document=doc_file,
                filename="Myanmar_Subtitle.srt"
            )

        genai.delete_file(uploaded_file.name)

    except Exception as e:
        await update.message.reply_text(f"❌ Error ဖြစ်ပေါ်ခဲ့သည်: {str(e)}")

    finally:
        if os.path.exists(file_path): 
            os.remove(file_path)
        if os.path.exists(srt_file_path): 
            os.remove(srt_file_path)

if __name__ == "__main__":
    keep_alive()
    bot_app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    bot_app.add_handler(MessageHandler(filters.AUDIO | filters.VIDEO | filters.VOICE | filters.Document.ALL, handle_media))
    print("✅ Telegram Bot is running successfully...")
    bot_app.run_polling()
        
