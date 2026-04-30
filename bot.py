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
TOKEN = "8711010513:AAFMdEHtckv7l2mOZbkJ3lnTcJntoBMg7lg"
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

# 🔍 CHECK NEXT POST TIMING
async def check_next_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != YOUR_USER_ID:
        return

# COUNT THE QUEUE 
async def count_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        conn = sqlite3.connect("scheduler.db")
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM scheduled_posts")
        total_videos = cursor.fetchone()[0]

        conn.close()

        await update.message.reply_text(
            f"📦 Total videos currently in queue: {total_videos}"
        )

    except Exception as e:
        await update.message.reply_text(
            f"Error checking queue: {str(e)}"
        )

    # Get all jobs from the scheduler
    jobs = scheduler.get_jobs()
    
    if not jobs:
        await update.message.reply_text("No active schedules found.")
        return

    # Find the job that is scheduled to run next
    next_job = min(jobs, key=lambda j: j.next_run_time)
    
    # Format the time (it will show in your server's timezone)
    next_time = next_job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
    
    await update.message.reply_text(f"⏰ Next post is scheduled for:\n{next_time}")

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
app.add_handler(CommandHandler("countqueue", count_queue))

# ⏰ Scheduler
from pytz import timezone

# Use IST timezone
indian_tz = timezone('Asia/Kolkata')
scheduler = AsyncIOScheduler(timezone=indian_tz)
POST_HOURS = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]

for hour in POST_HOURS:
    scheduler.add_job(post_video, "cron", hour=hour, minute=5)

async def on_startup(app):
    scheduler.start()

app.post_init = on_startup

print("🤖 Bot with Database & Logging is running...")
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
posting_paused = False
ADMIN_ID = 8789590706
POST_INTERVAL_HOURS = 2
clear_confirmation_pending = False

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
    global posting_paused

    if posting_paused:
        print("⏸ Posting is paused.")
        return

    print("⏰ Scheduler triggered")

    videos_queue = load_queue()

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
    if not is_admin(update):
        await update.message.reply_text("❌ Admin only command")
        return


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
    global clear_confirmation_pending

    if not is_admin(update):
        await update.message.reply_text("❌ Admin only command")
        return

    clear_confirmation_pending = True

    await update.message.reply_text(
        "⚠ Are you sure you want to clear the full queue?\n\nReply with /confirmclear"
    )

    if not is_admin(update):
        await update.message.reply_text("❌ Admin only command")
        return


    if update.message.from_user.id != 8789590706:
        return

    videos_queue.clear()
    save_queue(videos_queue)

    await update.message.reply_text("🗑️ Queue cleared")

# COUNT QUEUE
async def count_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    videos_queue = load_queue()

    await update.message.reply_text(
        f"📦 Total videos currently in queue: {len(videos_queue)}"
    )

# BOT HEALTH
async def bot_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    videos_queue = load_queue()

    total_videos = len(videos_queue)

    await update.message.reply_text(
        f"📊 Bot Stats\n\n"
        f"📦 Total videos in queue: {total_videos}\n"
        f"🤖 Bot status: Running ✅"
    )

#Pause
async def pause_posting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ Admin only command")
        return

    global posting_paused
    posting_paused = True

    await update.message.reply_text(
        "⏸ Auto posting paused successfully"
    )

#Resume
async def resume_posting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ Admin only command")
        return


    global posting_paused
    posting_paused = False

    await update.message.reply_text(
        "▶️ Auto posting resumed successfully"
    )

#Bot Health
async def bot_health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global posting_paused

    try:
        videos_queue = load_queue()
        total_videos = len(videos_queue)

        posting_status = "Paused ⏸" if posting_paused else "Active ▶️"

        await update.message.reply_text(
            f"🩺 Bot Health Report\n\n"
            f"🤖 Bot Status: Running ✅\n"
            f"📦 Queue File: OK ✅\n"
            f"⏸ Posting Status: {posting_status}\n"
            f"📊 Videos in Queue: {total_videos}"
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ Health Check Failed:\n{str(e)}"
        )

#Force Post
async def force_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ Admin only command")
        return


    await update.message.reply_text(
        "🚀 Force posting next queued video..."
    )

    await post_video()

#Admin Only
def is_admin(update):
    return update.message.from_user.id == ADMIN_ID

#Set Time
async def set_post_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global POST_INTERVAL_HOURS

    if not is_admin(update):
        await update.message.reply_text("❌ Admin only command")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: /settime 3\nExample: /settime 3 = post every 3 hours"
        )
        return

    try:
        hours = int(context.args[0])

        if hours <= 0:
            await update.message.reply_text("Enter a valid number greater than 0")
            return

        POST_INTERVAL_HOURS = hours

        scheduler.remove_all_jobs()
        scheduler.add_job(
            post_video,
            "interval",
            hours=POST_INTERVAL_HOURS
        )

        await update.message.reply_text(
            f"⏰ Posting schedule updated: every {POST_INTERVAL_HOURS} hour(s)"
        )

    except:
        await update.message.reply_text("Invalid input. Example: /settime 3")

#Broadcast Message
async def broadcast_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ Admin only command")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: /broadcastchannel Your message here"
        )
        return

    message = " ".join(context.args)

    try:
        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=message
        )

        await update.message.reply_text(
            "📢 Message successfully sent to channel"
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ Broadcast failed:\n{str(e)}"
        )

#Clear Confirmation
async def confirm_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global clear_confirmation_pending

    if not is_admin(update):
        await update.message.reply_text("❌ Admin only command")
        return

    if not clear_confirmation_pending:
        await update.message.reply_text(
            "No clear action pending."
        )
        return

    save_queue([])

    clear_confirmation_pending = False

    await update.message.reply_text(
        "🗑 Queue cleared successfully"
    )

# ❌ DELETE SPECIFIC
async def delete_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ Admin only command")
        return


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
app.add_handler(CommandHandler("check", check_next_post))
app.add_handler(CommandHandler("countqueue", count_queue))
app.add_handler(CommandHandler("stats", bot_stats))
app.add_handler(CommandHandler("pause", pause_posting))
app.add_handler(CommandHandler("resume", resume_posting))
app.add_handler(CommandHandler("health", bot_health))
app.add_handler(CommandHandler("forcepost", force_post))
app.add_handler(CommandHandler("settime", set_post_time))
app.add_handler(CommandHandler("broadcastchannel", broadcast_channel))
app.add_handler(CommandHandler("confirmclear", confirm_clear))

# ⏰ SCHEDULE (10 POSTS DAILY AT :05)
scheduler.add_job(
    post_video,
    "interval",
    hours=POST_INTERVAL_HOURS
)

# ▶️ START SCHEDULER AFTER BOT STARTS
async def on_startup(app):
    scheduler.start()

app.post_init = on_startup

# ▶️ RUN BOT
print("🤖 Bot is running...")
app.run_polling()
