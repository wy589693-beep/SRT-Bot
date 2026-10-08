import os
import logging
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import google.generativeai as genai

# 📌 Logging သတ်မှတ်ခြင်း (Bot အလုပ်လုပ်ပုံကို Terminal တွင် ရှင်းလင်းစွာ မြင်ရရန်)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ==========================================
# 1. Background Web Server (24/7 Run ရန်)
# ==========================================
app_web = Flask(name)

@app_web.route('/')
def home() -> str:
    return "Telegram Subtitle Bot is Running 24/7!"

def run_web() -> None:
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host="0.0.0.0", port=port)

def keep_alive() -> None:
    t = Thread(target=run_web, daemon=True)
    t.start()

# ==========================================
# 2. API Keys စစ်ဆေးခြင်းနှင့် ချိတ်ဆက်ခြင်း
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get("8871786955:AAGy7aWgp8OyKIpBUb1pFV6O9JsYleDs8NQ")
GEMINI_API_KEY = os.environ.get("AQ.Ab8RN6JnfAgP4wunO1fYY278tuK_3KIxwmZIQsQs6PeYJXSh_Q")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN ကို ထည့်သွင်းရန် မေ့ကျန်နေပါသည်။")

if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY ကို ထည့်သွင်းရန် မေ့ကျန်နေပါသည်။")

genai.configure(api_key=AQ.Ab8RN6JnfAgP4wunO1fYY278tuK_3KIxwmZIQsQs6PeYJXSh_Q)

# Telegram ၏ အများဆုံး ဖိုင်အရွယ်အစား (20 MB)
MAX_FILE_SIZE = 20 * 1024 * 1024  

# ==========================================
# 3. Media ဖိုင်များကို လက်ခံပြီး SRT ထုတ်ပေးမည့် အပိုင်း
# ==========================================
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    message = update.message
    media = message.audio or message.video or message.document or message.voice

    if not media:
        return

    # ဖိုင်အရွယ်အစား 20MB ထက်ကြီးမကြီး စစ်ဆေးခြင်း
    if media.file_size and media.file_size > MAX_FILE_SIZE:
        await message.reply_text(
            "⚠️ Telegram ၏ ကန့်သတ်ချက်အရ 20 MB ထက်ကြီးသော ဖိုင်များကို ဒေါင်းလုဒ်မဆွဲနိုင်ပါ။\n"
            "💡 ဗီဒီယိုကို MP3 အသံဖိုင်အဖြစ် ပြောင်းပြီးမှ ထပ်ပို့ပေးပါ။"
        )
        return

    await message.reply_text("📥 ဖိုင်ကို လက်ခံရရှိပါပြီ။ Gemini မှ မြန်မာ SRT Subtitle ဖန်တီးနေပါသည်... (ခေတ္တစောင့်ပါ)")

    # ဖိုင်နာမည် မထပ်စေရန် File ID ဖြင့် နာမည်ပေးခြင်း
    file_path = f"temp_{media.file_id}.mp4"
    srt_file_path = f"Myanmar_Subtitle_{media.file_id}.srt"

    # Telegram မှ ဖိုင် ဒေါင်းလုဒ်ဆွဲခြင်း (custom_path အသုံးပြုရမည်)
    try:
        file = await context.bot.get_file(media.file_id)
        await file.download_to_drive(custom_path=file_path)
    except Exception as e:
        await message.reply_text(f"❌ Telegram မှ ဖိုင်ဆွဲယူရာတွင် အမှားဖြစ်နေပါသည်: {str(e)}")
        return

    try:
        # Gemini သို့ ဖိုင်တင်ခြင်း
        uploaded_file = genai.upload_file(file_path)

        model = genai.GenerativeModel("gemini-1.5-pro")
        prompt = (
            "Listen carefully to the audio/video provided. "
            "Transcribe and translate the spoken sentences into natural, conversational, and accurate Myanmar (Burmese) language. "
            "Format the output strictly as a valid SRT subtitle file with standard timestamps (HH:MM:SS,mmm --> HH:MM:SS,mmm). "
            "Do NOT include any extra introductory text, markdown backticks, or explanation. Output strictly raw SRT text only."
        )

        response = model.generate_content([uploaded_file, prompt])
        srt_content = response.text.strip() if response.text else ""

        # Markdown အစအဆုံး (
        if srt_content.startswith("
"):
            lines = srt_content.splitlines()
            if lines[0].startswith("
                lines = lines[1:]
            if lines and lines[-1].startswith("
"):
                lines = lines[:-1]
            srt_content = "\n".join(lines)

        # SRT ဖိုင်အဖြစ် သိမ်းဆည်းခြင်း
        with open(srt_file_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        # သုံးစွဲသူထံသို့ SRT ဖိုင် ပြန်ပို့ပေးခြင်း
        with open(srt_file_path, "rb") as doc_file:
            await message.reply_document(
                document=doc_file,
                filename="Myanmar_Subtitle.srt",
                caption="✨ Gemini မှ သဘာဝကျကျ ဘာသာပြန်ပေးထားသော မြန်မာစာတန်းထိုး (.srt) ဖိုင် ရပါပြီ။"
            )

        # Gemini Server မှ ဖိုင်ဟောင်းကို ပြန်ဖျက်ခြင်း
        genai.delete_file(uploaded_file.name)

    except Exception as e:
        await message.reply_text(f"❌ Gemini Processing Error ဖြစ်ပေါ်ခဲ့သည်: {str(e)}")

    finally:
        # Local မှ ယာယီဖိုင်များကို ပြန်ဖျက်ခြင်း (Server အမှိုက်မပြည့်စေရန်)
        if os.path.exists(file_path):
            os.remove(file_path)
        if os.path.exists(srt_file_path):
            os.remove(srt_file_path)

# ==========================================
# 4. အလုပ်စတင်ခြင်း (Main)
# ==========================================
if name == "main":
    # Web Server ခေါ်ခြင်း (Render တွင် Sleep မဖြစ်စေရန်)
    keep_alive()

    # Bot စတင်ခြင်း
    bot_app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    media_filter = filters.AUDIO | filters.VIDEO | filters.VOICE | filters.Document.ALL
    bot_app.add_handler(MessageHandler(media_filter, handle_media))

    print("✅ Telegram Bot is running successfully...")
    bot_app.run_polling()