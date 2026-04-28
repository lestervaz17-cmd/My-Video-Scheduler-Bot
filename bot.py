from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import json
import os

# 🔑 CONFIG
CHANNEL_ID = "@nsfw18content"
YOUR_USER_ID = 8789590706

QUEUE_FILE = "queue.json"

# 📦 LOAD & SAVE QUEUE
def load_queue():
    if os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE, "r") as f:
            return json.load(f)
    return []

def save_queue(queue):
    with open(QUEUE_FILE, "w") as f:
        json.dump(queue, f)

videos_queue = load_queue()

# ⏰ Scheduler
scheduler = AsyncIOScheduler()

# 📥 SAVE VIDEO
async def save_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != YOUR_USER_ID:
        return

    video = update.message.video
    caption = update.message.caption or ""

    if video:
        file_id = video.file_id

        videos_queue.append({
            "file_id": file_id,
            "caption": caption
        })

        save_queue(videos_queue)

        await update.message.reply_text("Video saved with caption ✅")

# 📤 POST VIDEO
async def post_video():
    print("⏰ Scheduler triggered")

    if videos_queue:
        video_data = videos_queue.pop(0)
        save_queue(videos_queue)

        print("📤 Posting video...")

        await app.bot.send_video(
            chat_id=CHANNEL_ID,
            video=video_data["file_id"],
            caption=video_data["caption"]
        )

        print("✅ Posted successfully")
    else:
        print("⚠️ Queue empty")

# 📋 SHOW QUEUE
async def show_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != 8789590706:
        return

    if not videos_queue:
        await update.message.reply_text("Queue is empty")
        return

    text = "📦 Upcoming videos:\n"
    for i, video in enumerate(videos_queue[:10], start=1):
        text += f"{i}. {video['caption'][:30]}...\n"

    await update.message.reply_text(text)

# ⏭️ SKIP
async def skip_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != 8789590706:
        return

    if not videos_queue:
        await update.message.reply_text("Queue is empty")
        return

    videos_queue.pop(0)
    save_queue(videos_queue)

    await update.message.reply_text("⏭️ Skipped next video")

# 🗑️ CLEAR
async def clear_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != 8789590706:
        return

    videos_queue.clear()
    save_queue(videos_queue)

    await update.message.reply_text("🗑️ Queue cleared")

# ❌ DELETE SPECIFIC
async def delete_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != 8789590706:
        return

    if not context.args:
        await update.message.reply_text("Usage: /delete 3")
        return

    try:
        index = int(context.args[0]) - 1

        if index < 0 or index >= len(videos_queue):
            await update.message.reply_text("Invalid number")
            return

        videos_queue.pop(index)
        save_queue(videos_queue)

        await update.message.reply_text(f"❌ Deleted video #{index+1}")

    except:
        await update.message.reply_text("Enter a valid number")

# 🚀 CREATE APP
app = ApplicationBuilder().token(TOKEN).build()

# 🔗 HANDLERS
app.add_handler(MessageHandler(filters.VIDEO, save_video))
app.add_handler(CommandHandler("queue", show_queue))
app.add_handler(CommandHandler("skip", skip_video))
app.add_handler(CommandHandler("clear", clear_queue))
app.add_handler(CommandHandler("delete", delete_video))

# ⏰ SCHEDULE (10 POSTS DAILY AT :05)
POST_HOURS = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]

for hour in POST_HOURS:
    scheduler.add_job(post_video, "cron", hour=hour, minute=5)

# ▶️ START SCHEDULER AFTER BOT STARTS
async def on_startup(app):
    scheduler.start()

app.post_init = on_startup

# ▶️ RUN BOT
print("🤖 Bot is running...")
app.run_polling()