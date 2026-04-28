from dotenv import load_dotenv
import os
import sqlite3
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

load_dotenv()

# 🔑 CONFIG
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = "@nsfw18content"
YOUR_USER_ID = 8789590706
LOG_CHANNEL_ID = -1003873677982  # 👈 REPLACE THIS with your Log Channel ID

DB_FILE = "scheduler.db"

# 📦 SQLITE DATABASE SETUP
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT,
            caption TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# 📥 SAVE VIDEO TO DB
async def save_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != YOUR_USER_ID:
        return

    video = update.message.video
    caption = update.message.caption or ""

    if video:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO videos (file_id, caption) VALUES (?, ?)', (video.file_id, caption))
        conn.commit()
        conn.close()
        await update.message.reply_text("Video saved to Database ✅")

# 📤 POST VIDEO & LOG
async def post_video():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, file_id, caption FROM videos ORDER BY id LIMIT 1')
    video_data = cursor.fetchone()
    
    if video_data:
        db_id, file_id, caption = video_data
        
        try:
            # Post to main channel
            await app.bot.send_video(chat_id=CHANNEL_ID, video=file_id, caption=caption)
            
            # Delete from DB after posting
            cursor.execute('DELETE FROM videos WHERE id = ?', (db_id,))
            conn.commit()
            
            # 📝 LOG TO PRIVATE CHANNEL
            await app.bot.send_message(
                chat_id=LOG_CHANNEL_ID, 
                text=f"✅ SUCCESS: Video posted to {CHANNEL_ID}\nCaption: {caption[:50]}..."
            )
            print("✅ Posted and Logged successfully")
        except Exception as e:
            await app.bot.send_message(chat_id=LOG_CHANNEL_ID, text=f"❌ ERROR: Failed to post video: {e}")
    else:
        print("⚠️ Queue empty")
    
    conn.close()

# 📋 SHOW QUEUE FROM DB
async def show_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != YOUR_USER_ID: return
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT caption FROM videos LIMIT 10')
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("Queue is empty")
        return

    text = "📦 Upcoming videos (Database):\n"
    for i, row in enumerate(rows, start=1):
        text += f"{i}. {row[0][:30]}...\n"
    await update.message.reply_text(text)

# 🗑️ CLEAR DB
async def clear_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != YOUR_USER_ID: return
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM videos')
    conn.commit()
    conn.close()
    await update.message.reply_text("🗑️ Database Queue cleared")

# 🚀 CREATE APP
app = ApplicationBuilder().token(TOKEN).build()

# 🔗 HANDLERS
app.add_handler(MessageHandler(filters.VIDEO, save_video))
app.add_handler(CommandHandler("queue", show_queue))
app.add_handler(CommandHandler("clear", clear_queue))

# ⏰ Scheduler
scheduler = AsyncIOScheduler()
POST_HOURS = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]

for hour in POST_HOURS:
    scheduler.add_job(post_video, "cron", hour=hour, minute=5)

async def on_startup(app):
    scheduler.start()

app.post_init = on_startup

print("🤖 Bot with Database & Logging is running...")
app.run_polling()
