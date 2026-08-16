import os
import re
import uuid
import time
import random
import shutil
import threading
import subprocess
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import requests
import yt_dlp
import telebot
from pymongo import MongoClient
from telebot.types import (
    ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup,
    InlineKeyboardButton, InputMediaPhoto, LabeledPrice
)

# ============================================================
# CONFIG
# ============================================================

TOKEN = os.getenv("BOT_TOKEN")
BOT2_TOKEN = os.getenv("BOT2_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is required")

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
PHONE = os.getenv("PHONE", "")

GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_PASS = os.getenv("GMAIL_PASS", "")

MAX_YOUTUBE_DURATION = int(os.getenv("MAX_YOUTUBE_DURATION", "600"))
MAX_CONCURRENT_DOWNLOADS = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "20"))

ADMIN_IDS = [7983838654]

CHANNEL_USERNAME = "@tiktokvediodownload"
CAPTION_TEXT = "Downloaded by:\n@Downloadvedioytibot"

MONGO_URI_1 = os.getenv(
    "MONGO_URI_1",
    os.getenv("MONGO_URI", "mongodb://localhost:27017/user_db")
)
MONGO_URI_2 = os.getenv(
    "MONGO_URI_2",
    "mongodb://localhost:27017/stats_db"
)

# ============================================================
# TELEGRAM CLIENTS
# ============================================================

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
bot2 = telebot.TeleBot(BOT2_TOKEN, parse_mode="HTML") if BOT2_TOKEN else None

# ============================================================
# MONGODB
# Existing collections are preserved. New collections are added.
# ============================================================

mongo_client1 = MongoClient(MONGO_URI_1)
try:
    db1 = mongo_client1.get_default_database()
except Exception:
    db1 = mongo_client1["user_db"]

mongo_client2 = MongoClient(MONGO_URI_2)
try:
    db2 = mongo_client2.get_default_database()
except Exception:
    db2 = mongo_client2["stats_db"]

users_col = db1["users"]
withdraws_col = db1["withdraws"]

videos_col = db2["videos"]
feedback_col = db2["feedback"]

managed_bots_col = db1["managed_bots"]
bot_users_col = db1["bot_users"]
bot_downloads_col = db1["bot_downloads"]
bot_access_col = db1["bot_creation_access"]

# ============================================================
# RUNTIME STATE
# ============================================================

users = {}
withdraws = []

pending_links = {}
verify_pending = {}
video_files = {}

pending_post = {}
channel_posts = {}

POST_CHANNELS = []
MANAGED_CHANNELS = []
MAX_CHANNELS = 10
CHANNEL_WINDOW_OPEN = False

VERIFY_ENABLED = False

BOT_LOCKED = False
LOCK_MESSAGE = "🔒 Bot is temporarily locked by admin."

ADS_ENABLED = False
ADS_TEXT = ""
ADS_BTN_TEXT = ""
ADS_URL = ""

vip_executor = ThreadPoolExecutor(max_workers=5)
normal_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_DOWNLOADS)

managed_bot_instances = {}
managed_bot_threads = {}
managed_bot_lock = threading.RLock()

broadcast_executor = ThreadPoolExecutor(max_workers=2)

# ============================================================
# DATABASE HELPERS
# ============================================================

def random_ref():
    return str(random.randint(1000000000, 9999999999))


def random_botid():
    return str(random.randint(10000000000, 99999999999))


def now_month():
    return datetime.now().month


def load_users():
    result = {}
    for item in users_col.find():
        uid = str(item["_id"])
        item.pop("_id", None)
        result[uid] = item
    return result


def save_user(uid):
    uid = str(uid)
    if uid not in users:
        return
    data = dict(users[uid])
    data.pop("_id", None)
    users_col.update_one({"_id": uid}, {"$set": data}, upsert=True)


def save_users():
    for uid in users:
        save_user(uid)


def load_withdraws():
    return list(withdraws_col.find({}, {"_id": False}))


def save_withdraws():
    withdraws_col.delete_many({})
    if withdraws:
        withdraws_col.insert_many([dict(x) for x in withdraws])


def load_videos():
    doc = videos_col.find_one({"_id": "stats"})
    if not doc:
        doc = {
            "_id": "stats",
            "total": 0,
            "feedback_enabled": False,
            "platforms": {
                "tiktok": 0, "youtube": 0, "facebook": 0,
                "pinterest": 0, "instagram": 0,
                "snapchat": 0, "twitter": 0
            },
            "users": {}
        }
        videos_col.insert_one(doc)
    doc.pop("_id", None)
    return doc


def save_videos():
    data = dict(videos_data)
    data.pop("_id", None)
    videos_col.update_one({"_id": "stats"}, {"$set": data}, upsert=True)


users = load_users()
withdraws = load_withdraws()
videos_data = load_videos()

# ============================================================
# AUTH / COMMON HELPERS
# ============================================================

def is_admin(uid):
    try:
        return int(uid) in ADMIN_IDS
    except Exception:
        return False


def is_quick_access(uid):
    return users.get(str(uid), {}).get("quick_access", False)


def find_user_by_botid(bid):
    for uid, data in users.items():
        if str(data.get("bot_id")) == str(bid):
            return uid
    return None


def banned_guard(message):
    uid = str(message.from_user.id)
    if users.get(uid, {}).get("banned"):
        try:
            bot.send_message(message.chat.id, "🚫 You are banned.")
        except Exception:
            pass
        return True
    return False


def bot_locked_guard(message):
    if BOT_LOCKED and not is_admin(message.from_user.id):
        try:
            bot.send_message(message.chat.id, LOCK_MESSAGE)
        except Exception:
            pass
        return True
    return False


def extract_url(text):
    urls = re.findall(r"https?://[^\s]+", text or "")
    return urls[0] if urls else None


def ensure_user(message):
    uid = str(message.from_user.id)
    if uid not in users:
        users[uid] = {
            "username": message.from_user.username or "",
            "first_name": message.from_user.first_name or "",
            "balance": 0.0,
            "blocked": 0.0,
            "ref": random_ref(),
            "bot_id": random_botid(),
            "invited": 0,
            "banned": False,
            "verified": False,
            "quick_access": False,
            "month": now_month()
        }
        save_user(uid)
    else:
        changed = False
        if message.from_user.username and users[uid].get("username") != message.from_user.username:
            users[uid]["username"] = message.from_user.username
            changed = True
        if changed:
            save_user(uid)
    return uid

# ============================================================
# MAIN MENUS
# ============================================================

def user_menu(show_admin=False, show_creator=False):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💰 BALANCE", "💸 WITHDRAWAL")
    kb.add("👥 REFERRAL", "🆔 GET ID")
    kb.add("☎️ CUSTOMER", "🤖CUSTOMER AI")
    if show_creator:
        kb.add("🤖 BOT CREATOR")
    if show_admin:
        kb.add("👑 ADMIN PANEL")
    return kb


def admin_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📊 STATS", "📢 BROADCAST")
    kb.add("📢 BROADCAST ALL BOTS", "👥 SEND USERS TO CREATE")
    kb.add("🤖 ALL CREATED BOTS")
    kb.add("⚡ QUICK ACCESS", "👥 SEE LIST")
    kb.add("➕ ADD BALANCE", "➖ REMOVE MONEY")
    kb.add("🚫 BAN USER MANUAL", "💳 WITHDRAWAL CHECK")
    kb.add("💰 UNBLOCK MONEY", "🔍 RAADI")
    kb.add("🔥 UN BAN-USER", "📌 POST CHANNEL")
    kb.add("🔎 SEARCH USER", "📢 ADD ADS")
    kb.add("🗑 DELETE ADS", "✅ VERIFY ON")
    kb.add("❌ VERIFY OFF", "CHANNEL POST")
    kb.add("📡 ADD CHANNEL", "🔒 LOCK BOT")
    kb.add("🔓 UNLOCK BOT", "❌ CLOSE WINDOWS")
    kb.add("CLOSE CHANNEL POST", "📢 BROADCAST MEDIA")
    kb.add("SEND PAY", "📥 IMPORT USERS")
    kb.add("🔗 GET REFERRAL CODE", "📊 Feedback Stats")
    kb.add("🟢 Open Feedback", "🔴 Close Feedback")
    kb.add("🗑️ Reset All Feedbacks", "🔙 BACK MAIN MENU")
    return kb


def creator_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Create New Bot")
    kb.add("🤖 My Bots")
    kb.add("🗑 Delete Bot")
    kb.add("🔙 BACK MAIN MENU")
    return kb


def owner_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("👑 ADMIN PANEL")
    kb.add("🤖 My Bots")
    kb.add("🔙 BACK MAIN MENU")
    return kb

# ============================================================
# MANAGED BOT ACCESS SYSTEM
# ============================================================

def has_creator_access(uid):
    uid = str(uid)
    if is_admin(uid):
        return True
    doc = bot_access_col.find_one({"_id": uid})
    return bool(doc and doc.get("enabled", False))


def set_creator_access(uid, enabled=True):
    bot_access_col.update_one(
        {"_id": str(uid)},
        {"$set": {
            "enabled": bool(enabled),
            "updated_at": datetime.now()
        }},
        upsert=True
    )


def creator_request_keyboard():
    # Telegram Bot API 9.6 Managed Bots.
    # This is a ReplyKeyboardButton, NOT an inline callback.
    from telebot.types import KeyboardButtonRequestManagedBot

    request_id = random.randint(-2147483648, 2147483647)
    request = KeyboardButtonRequestManagedBot(
        request_id=request_id,
        suggested_name="Video Downloader Bot",
        suggested_username=None
    )
    button = KeyboardButton(
        "➕ Create New Bot",
        request_managed_bot=request
    )
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    kb.add(button)
    kb.add("🤖 My Bots", "🗑 Delete Bot")
    kb.add("🔙 BACK MAIN MENU")
    return kb


def creator_panel(message):
    uid = message.from_user.id
    if not has_creator_access(uid):
        bot.send_message(
            message.chat.id,
            "❌ You do not have Bot Creator access.\n"
            "Ask the main admin to enable access."
        )
        return

    bot.send_message(
        message.chat.id,
        "🤖 <b>Bot Creator</b>\n\n"
        "Press <b>➕ Create New Bot</b>.\n"
        "Telegram will open its official Managed Bot creation screen.\n\n"
        "You do <b>not</b> need to send a token, OTP, API ID or API HASH.",
        reply_markup=creator_request_keyboard()
    )


def save_managed_bot(owner_id, bot_user, token):
    bot_id = int(bot_user.id)
    username = getattr(bot_user, "username", None) or ""
    name = getattr(bot_user, "first_name", None) or ""

    # Token is stored only in the database for the manager runtime.
    # It is never sent to the user and never printed.
    managed_bots_col.update_one(
        {"_id": bot_id},
        {"$set": {
            "bot_id": bot_id,
            "owner_id": int(owner_id),
            "owner_username": users.get(str(owner_id), {}).get("username", ""),
            "username": username,
            "name": name,
            "token": token,
            "status": "active",
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }},
        upsert=True
    )


def register_bot_user(bot_id, message):
    if not getattr(message, "from_user", None):
        return
    uid = int(message.from_user.id)
    bot_users_col.update_one(
        {"bot_id": int(bot_id), "user_id": uid},
        {"$set": {
            "username": message.from_user.username or "",
            "first_name": message.from_user.first_name or "",
            "last_active": datetime.now()
        }, "$setOnInsert": {
            "joined_at": datetime.now()
        }},
        upsert=True
    )


def get_bot_record(bot_id):
    return managed_bots_col.find_one({"_id": int(bot_id)})


def owned_bots(owner_id):
    return list(
        managed_bots_col.find(
            {"owner_id": int(owner_id), "status": {"$ne": "deleted"}}
        ).sort("created_at", -1)
    )


def bot_display(record):
    username = record.get("username", "")
    return "@" + username if username else str(record.get("bot_id"))


def my_bots_message(owner_id):
    records = owned_bots(owner_id)
    if not records:
        return "🤖 <b>My Bots</b>\n\nYou have not created any managed Downloader Bots yet."

    lines = ["🤖 <b>My Bots</b>\n"]
    for record in records:
        status = "🟢 Active" if record.get("status") == "active" else "🔴 Disabled"
        lines.append(f"{bot_display(record)}\n{status}\n")
    return "\n".join(lines)


def start_managed_bot_worker(record):
    bot_id = int(record["bot_id"])

    with managed_bot_lock:
        if bot_id in managed_bot_threads and managed_bot_threads[bot_id].is_alive():
            return
        if not record.get("token"):
            return

    try:
        child = telebot.TeleBot(record["token"], parse_mode="HTML")
    except Exception:
        return

    managed_bot_instances[bot_id] = child
    register_downloader_handlers(child, bot_id)

    def worker():
        while True:
            current = get_bot_record(bot_id)
            if not current or current.get("status") != "active":
                break
            try:
                child.infinity_polling(
                    timeout=20,
                    long_polling_timeout=20,
                    allowed_updates=None
                )
            except Exception:
                time.sleep(3)

    t = threading.Thread(target=worker, daemon=True, name=f"managed-bot-{bot_id}")
    managed_bot_threads[bot_id] = t
    t.start()


def stop_managed_bot(bot_id):
    bot_id = int(bot_id)
    with managed_bot_lock:
        instance = managed_bot_instances.get(bot_id)
        if instance:
            try:
                instance.stop_polling()
            except Exception:
                pass
        managed_bots_col.update_one(
            {"_id": bot_id},
            {"$set": {"status": "deleted", "updated_at": datetime.now()}}
        )


def process_managed_bot(bot_user, owner_id):
    try:
        bot_id = int(bot_user.id)
        token = bot.get_managed_bot_token(bot_id)

        # Never print token or send it to a Telegram chat.
        save_managed_bot(owner_id, bot_user, token)

        start_managed_bot_worker(get_bot_record(bot_id))

        username = getattr(bot_user, "username", "") or ""
        name = getattr(bot_user, "first_name", "") or "Downloader Bot"

        bot.send_message(
            int(owner_id),
            "✅ <b>Downloader Bot Created</b>\n\n"
            f"🤖 Name: {name}\n"
            f"🔗 Username: @{username}\n"
            "🟢 Status: Active\n\n"
            "Your bot is now running as a Downloader Bot.\n"
            "The bot token was retrieved securely by the Manager Bot and "
            "was not shown to you.",
            reply_markup=creator_menu()
        )
    except Exception:
        try:
            bot.send_message(
                int(owner_id),
                "❌ Managed Bot was created, but the Manager Bot could not "
                "finish configuration.\n\n"
                "Make sure Bot Management Mode is enabled for this Manager Bot."
            )
        except Exception:
            pass


# Service message: Telegram sends ManagedBotCreated in the Message.
@bot.message_handler(content_types=["managed_bot_created"])
def managed_bot_created_handler(message):
    if not has_creator_access(message.from_user.id):
        return
    created = getattr(message, "managed_bot_created", None)
    if not created or not getattr(created, "bot", None):
        return
    process_managed_bot(created.bot, message.from_user.id)


# Update: Telegram also sends ManagedBotUpdated to the manager bot.
@bot.managed_bot_handler()
def managed_bot_updated_handler(update):
    event = getattr(update, "managed_bot", None)
    if not event:
        return
    bot_user = getattr(event, "bot", None)
    owner = getattr(event, "user", None)
    if not bot_user or not owner:
        return
    if not has_creator_access(owner.id):
        return
    process_managed_bot(bot_user, owner.id)


@bot.message_handler(func=lambda m: m.text == "🤖 BOT CREATOR")
def bot_creator_button(message):
    creator_panel(message)


@bot.message_handler(func=lambda m: m.text == "➕ Create New Bot")
def create_new_bot_fallback(message):
    # This handler is intentionally only a fallback for old clients.
    # The real button is request_managed_bot and opens Telegram's
    # official Managed Bot creation UI.
    creator_panel(message)


@bot.message_handler(func=lambda m: m.text == "🤖 My Bots")
def my_bots_handler(message):
    if not has_creator_access(message.from_user.id):
        return
    bot.send_message(
        message.chat.id,
        my_bots_message(message.from_user.id),
        reply_markup=creator_menu()
    )


@bot.message_handler(func=lambda m: m.text == "🗑 Delete Bot")
def delete_bot_start(message):
    if not has_creator_access(message.from_user.id):
        return

    records = owned_bots(message.from_user.id)
    if not records:
        bot.send_message(message.chat.id, "❌ You have no managed bots.")
        return

    kb = InlineKeyboardMarkup()
    for record in records:
        kb.add(InlineKeyboardButton(
            bot_display(record),
            callback_data=f"mb_delete_select:{record['bot_id']}"
        ))
    bot.send_message(message.chat.id, "🗑 <b>Select a bot to disable:</b>", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data.startswith("mb_delete_select:"))
def delete_bot_select(call):
    try:
        bot_id = int(call.data.split(":", 1)[1])
    except Exception:
        return

    record = get_bot_record(bot_id)
    if not record or int(record.get("owner_id", 0)) != int(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ You can only manage your own bots.", show_alert=True)
        return

    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("✅ Delete", callback_data=f"mb_delete_confirm:{bot_id}"),
        InlineKeyboardButton("❌ Cancel", callback_data="mb_delete_cancel")
    )
    bot.edit_message_text(
        f"⚠️ <b>Are you sure?</b>\n\nBot: {bot_display(record)}\n\n"
        "Telegram does not provide a true delete method for managed bots "
        "through the Bot API, so this system will disable it and stop its worker.",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=kb
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("mb_delete_confirm:"))
def delete_bot_confirm(call):
    try:
        bot_id = int(call.data.split(":", 1)[1])
    except Exception:
        return

    record = get_bot_record(bot_id)
    if not record or int(record.get("owner_id", 0)) != int(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Not your bot.", show_alert=True)
        return

    stop_managed_bot(bot_id)
    bot.edit_message_text(
        f"🗑 <b>{bot_display(record)}</b> has been disabled.",
        call.message.chat.id,
        call.message.message_id
    )


@bot.callback_query_handler(func=lambda c: c.data == "mb_delete_cancel")
def delete_bot_cancel(call):
    bot.edit_message_text(
        "❌ Delete cancelled.",
        call.message.chat.id,
        call.message.message_id
    )

# ============================================================
# DOWNLOADER ENGINE
# ============================================================

def detect_platform(url):
    if "tiktok.com" in url:
        return "tiktok"
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    if "facebook.com" in url or "fb.watch" in url:
        return "facebook"
    if "instagram.com" in url:
        return "instagram"
    if "pin.it" in url or "pinterest.com" in url:
        return "pinterest"
    if "snapchat.com" in url:
        return "snapchat"
    if "x.com" in url or "twitter.com" in url:
        return "twitter"
    return "other"


def send_video_with_music(target_bot, bot_id, chat_id, file_path, platform, message_id=None):
    if not os.path.exists(file_path):
        return

    vid_id = uuid.uuid4().hex[:10]
    permanent = os.path.join("downloads", f"saved_{bot_id}_{vid_id}.mp4")

    try:
        shutil.move(file_path, permanent)
    except Exception:
        shutil.copy(file_path, permanent)

    video_files[f"{bot_id}:{vid_id}"] = {
        "path": permanent,
        "bot_id": bot_id
    }

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(
        "🎵 Convert Music",
        callback_data=f"music:{bot_id}:{vid_id}"
    ))

    if ADS_ENABLED and ADS_BTN_TEXT and ADS_URL:
        kb.add(InlineKeyboardButton(ADS_BTN_TEXT, url=ADS_URL))

    caption = CAPTION_TEXT
    if ADS_ENABLED and ADS_TEXT:
        caption += f"\n\n📢 {ADS_TEXT}"

    try:
        target_bot.send_chat_action(chat_id, "upload_video")
    except Exception:
        pass

    try:
        with open(permanent, "rb") as video:
            target_bot.send_video(
                chat_id,
                video,
                caption=caption,
                reply_markup=kb,
                supports_streaming=True
            )
        if message_id:
            try:
                target_bot.delete_message(chat_id, message_id)
            except Exception:
                pass
    except Exception:
        try:
            target_bot.send_message(chat_id, "❌ Failed to send the downloaded video.")
        except Exception:
            pass


def download_media_for_bot(target_bot, bot_id, chat_id, url, message_id):
    try:
        platform = detect_platform(url)

        if platform == "tiktok":
            try:
                api_url = f"https://www.tikwm.com/api/?url={url}"
                response = requests.get(api_url, timeout=30)
                data = response.json()
                if data.get("code") == 0:
                    item = data.get("data", {})
                    if item.get("images"):
                        media = [
                            InputMediaPhoto(img)
                            for img in item["images"][:10]
                        ]
                        target_bot.send_media_group(chat_id, media)
                        if message_id:
                            try:
                                target_bot.delete_message(chat_id, message_id)
                            except Exception:
                                pass
                        record_download(bot_id, chat_id, platform)
                        return
                    if item.get("play"):
                        path = os.path.join(
                            "downloads", f"tiktok_{uuid.uuid4().hex[:10]}.mp4"
                        )
                        with open(path, "wb") as fh:
                            r = requests.get(item["play"], timeout=60)
                            r.raise_for_status()
                            fh.write(r.content)
                        send_video_with_music(
                            target_bot, bot_id, chat_id, path, platform, message_id
                        )
                        record_download(bot_id, chat_id, platform)
                        return
            except Exception:
                pass

        if platform == "youtube":
            try:
                with yt_dlp.YoutubeDL({
                    "quiet": True,
                    "no_warnings": True,
                    "noplaylist": True
                }) as ydl:
                    info = ydl.extract_info(url, download=False)
                    duration = info.get("duration") or 0
                    if duration > MAX_YOUTUBE_DURATION:
                        target_bot.edit_message_text(
                            f"❌ Video is too long. Maximum is "
                            f"{MAX_YOUTUBE_DURATION // 60} minutes.",
                            chat_id,
                            message_id
                        )
                        return
            except Exception:
                pass

        os.makedirs("downloads", exist_ok=True)

        ydl_opts = {
            "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best",
            "merge_output_format": "mp4",
            "outtmpl": "downloads/dl_%(id)s.%(ext)s",
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "socket_timeout": 20,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        if not os.path.exists(filename):
            base, _ = os.path.splitext(filename)
            mp4 = base + ".mp4"
            if os.path.exists(mp4):
                filename = mp4

        send_video_with_music(
            target_bot, bot_id, chat_id, filename, platform, message_id
        )
        record_download(bot_id, chat_id, platform)

    except Exception:
        try:
            target_bot.edit_message_text(
                "❌ Sorry, I couldn't download this media. "
                "Make sure the link is public and try again.",
                chat_id,
                message_id
            )
        except Exception:
            try:
                target_bot.send_message(
                    chat_id,
                    "❌ Sorry, I couldn't download this media."
                )
            except Exception:
                pass


def record_download(bot_id, user_id, platform):
    bot_downloads_col.insert_one({
        "bot_id": int(bot_id),
        "user_id": int(user_id),
        "platform": platform,
        "created_at": datetime.now()
    })


def register_downloader_handlers(target_bot, bot_id):
    @target_bot.message_handler(commands=["start"])
    def managed_start(message):
        register_bot_user(bot_id, message)
        target_bot.send_message(
            message.chat.id,
            "🎬 <b>Video Downloader Bot</b>\n\n"
            "Send a public video link from YouTube, TikTok, Instagram, "
            "Facebook, Pinterest, Snapchat or X/Twitter."
        )

    @target_bot.message_handler(commands=["view"])
    def managed_view(message):
        register_bot_user(bot_id, message)
        target_bot.send_message(
            message.chat.id,
            "🤖 <b>Downloader Bot</b>\n\n"
            "TikTok • YouTube • Instagram • Facebook • Pinterest • "
            "Snapchat • X/Twitter"
        )

    @target_bot.message_handler(func=lambda m: m.text == "👑 ADMIN PANEL")
    def managed_owner_panel(message):
        register_bot_user(bot_id, message)
        record = get_bot_record(bot_id)
        if not record or int(record.get("owner_id", 0)) != int(message.from_user.id):
            target_bot.send_message(message.chat.id, "❌ Owner only.")
            return
        target_bot.send_message(
            message.chat.id,
            "👑 <b>Bot Admin Panel</b>",
            reply_markup=managed_owner_keyboard()
        )

    @target_bot.message_handler(func=lambda m: m.text == "📊 Stats")
    def managed_owner_stats(message):
        record = get_bot_record(bot_id)
        if not record or int(record.get("owner_id", 0)) != int(message.from_user.id):
            return
        total_users = bot_users_col.count_documents({"bot_id": bot_id})
        total_downloads = bot_downloads_col.count_documents({"bot_id": bot_id})
        active = bot_users_col.count_documents({
            "bot_id": bot_id,
            "last_active": {"$gte": datetime.now().replace(hour=0, minute=0, second=0)}
        })
        target_bot.send_message(
            message.chat.id,
            f"📊 <b>Statistics</b>\n\n"
            f"👥 Total Users: {total_users}\n"
            f"📥 Total Downloads: {total_downloads}\n"
            f"🟢 Active Users: {active}"
        )

    @target_bot.message_handler(func=lambda m: m.text == "📢 Broadcast")
    def managed_owner_broadcast(message):
        record = get_bot_record(bot_id)
        if not record or int(record.get("owner_id", 0)) != int(message.from_user.id):
            return
        prompt = target_bot.send_message(
            message.chat.id,
            "📢 Send the message/media to broadcast to this bot's users."
        )
        target_bot.register_next_step_handler(
            prompt,
            lambda msg: run_single_bot_broadcast(target_bot, bot_id, msg)
        )

    @target_bot.message_handler(func=lambda m: m.text == "⚙️ Bot Settings")
    def managed_settings(message):
        record = get_bot_record(bot_id)
        if not record or int(record.get("owner_id", 0)) != int(message.from_user.id):
            return
        target_bot.send_message(
            message.chat.id,
            f"⚙️ <b>Bot Settings</b>\n\n"
            f"🤖 {bot_display(record)}\n"
            f"🟢 Status: {record.get('status', 'unknown')}"
        )

    @target_bot.message_handler(func=lambda m: bool(m.text and "http" in m.text))
    def managed_link(message):
        register_bot_user(bot_id, message)
        url = extract_url(message.text)
        if not url:
            return

        processing = target_bot.send_message(
            message.chat.id,
            "⚡ Processing..."
        )

        executor = vip_executor if is_quick_access(message.from_user.id) else normal_executor
        executor.submit(
            download_media_for_bot,
            target_bot,
            bot_id,
            message.chat.id,
            url,
            processing.message_id
        )

    @target_bot.callback_query_handler(func=lambda c: c.data.startswith("music:"))
    def managed_music(call):
        parts = call.data.split(":")
        if len(parts) != 3:
            return
        try:
            requested_bot = int(parts[1])
        except Exception:
            return
        if requested_bot != bot_id:
            return

        key = f"{bot_id}:{parts[2]}"
        item = video_files.get(key)
        if not item or not os.path.exists(item["path"]):
            target_bot.answer_callback_query(call.id, "❌ Audio expired.")
            return

        audio_path = os.path.join(
            "downloads", f"audio_{bot_id}_{parts[2]}.mp3"
        )
        try:
            target_bot.send_chat_action(call.message.chat.id, "upload_audio")
            subprocess.run(
                [
                    "ffmpeg", "-i", item["path"],
                    "-q:a", "0", "-map", "a",
                    audio_path, "-y"
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=120
            )
            if not os.path.exists(audio_path):
                raise RuntimeError("No audio stream")
            with open(audio_path, "rb") as audio:
                target_bot.send_audio(call.message.chat.id, audio)
            os.remove(audio_path)
            target_bot.answer_callback_query(call.id, "🎵 Done")
        except Exception:
            target_bot.answer_callback_query(
                call.id, "❌ Failed to convert music."
            )


def managed_owner_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📊 Stats", "📢 Broadcast")
    kb.add("⚙️ Bot Settings")
    kb.add("🔙 BACK MAIN MENU")
    return kb

# ============================================================
# BROADCAST WORKERS
# ============================================================

def send_copy_to_user(target_bot, user_id, source_message):
    try:
        if source_message.text:
            target_bot.send_message(user_id, source_message.text)
        elif source_message.photo:
            target_bot.send_photo(
                user_id,
                source_message.photo[-1].file_id,
                caption=source_message.caption or ""
            )
        elif source_message.video:
            target_bot.send_video(
                user_id,
                source_message.video.file_id,
                caption=source_message.caption or ""
            )
        elif source_message.document:
            target_bot.send_document(
                user_id,
                source_message.document.file_id,
                caption=source_message.caption or ""
            )
        elif source_message.audio:
            target_bot.send_audio(
                user_id,
                source_message.audio.file_id,
                caption=source_message.caption or ""
            )
        else:
            return "failed"
        return "sent"
    except Exception as exc:
        text = str(exc).lower()
        if "blocked" in text or "chat not found" in text or "deactivated" in text:
            return "blocked"
        if "429" in text or "too many requests" in text:
            time.sleep(2)
        return "failed"


def run_single_bot_broadcast(target_bot, bot_id, source_message):
    users_list = list(bot_users_col.find(
        {"bot_id": int(bot_id)},
        {"user_id": 1}
    ))
    sent = failed = blocked = 0

    for item in users_list:
        uid = int(item["user_id"])
        result = send_copy_to_user(target_bot, uid, source_message)
        if result == "sent":
            sent += 1
        elif result == "blocked":
            blocked += 1
        else:
            failed += 1
        time.sleep(0.05)

    try:
        target_bot.send_message(
            source_message.chat.id,
            f"✅ <b>Broadcast Completed</b>\n\n"
            f"Sent: {sent}\nFailed: {failed}\nBlocked: {blocked}"
        )
    except Exception:
        pass


def broadcast_all_bots_worker(manager_chat_id, source_message):
    records = list(managed_bots_col.find({"status": "active"}))
    total_users = 0
    sent = failed = blocked = 0

    for record in records:
        bot_id = int(record["bot_id"])
        target = managed_bot_instances.get(bot_id)
        if not target:
            continue

        bot_users = list(bot_users_col.find(
            {"bot_id": bot_id},
            {"user_id": 1}
        ))
        total_users += len(bot_users)

        for item in bot_users:
            result = send_copy_to_user(
                target,
                int(item["user_id"]),
                source_message
            )
            if result == "sent":
                sent += 1
            elif result == "blocked":
                blocked += 1
            else:
                failed += 1
            time.sleep(0.05)

    try:
        bot.send_message(
            manager_chat_id,
            f"✅ <b>Broadcast All Bots Completed</b>\n\n"
            f"🤖 Bots: {len(records)}\n"
            f"👥 Target Users: {total_users}\n\n"
            f"Sent: {sent}\n"
            f"Failed: {failed}\n"
            f"Blocked: {blocked}"
        )
    except Exception:
        pass

# ============================================================
# START / MAIN BOT
# ============================================================

@bot.message_handler(commands=["start"])
def start_handler(message):
    if bot_locked_guard(message):
        return

    uid = ensure_user(message)
    args = message.text.split()

    if len(args) > 1:
        ref = args[1]
        ref_user = next(
            (u for u, d in users.items() if d.get("ref") == ref),
            None
        )
        if ref_user and ref_user != uid:
            users[ref_user]["balance"] = users[ref_user].get("balance", 0) + 0.2
            users[ref_user]["invited"] = users[ref_user].get("invited", 0) + 1
            save_user(ref_user)

    creator = has_creator_access(message.from_user.id)
    check_membership(message.from_user.id, creator)


def check_membership(user_id, creator=False):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["member", "administrator", "creator"]:
            bot.send_message(
                user_id,
                "🎬 <b>Welcome to Video Downloader Bot!</b>\n\n"
                "Copy a public video link and send it here.",
                reply_markup=user_menu(is_admin(user_id), creator)
            )
        else:
            send_join_message(user_id)
    except Exception:
        send_join_message(user_id)


def send_join_message(user_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(
        "➕ JOIN CHANNEL",
        url="https://t.me/tiktokvediodownload"
    ))
    kb.add(InlineKeyboardButton(
        "✅ CONFIRM",
        callback_data="confirm_join"
    ))
    try:
        bot.send_message(
            user_id,
            "⚠️ You must join our channel to use this bot.",
            reply_markup=kb
        )
    except Exception:
        pass


@bot.callback_query_handler(func=lambda c: c.data == "confirm_join")
def confirm_join(call):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, call.from_user.id)
        if member.status in ["member", "administrator", "creator"]:
            bot.answer_callback_query(call.id, "✅ Join verified")
            bot.send_message(
                call.message.chat.id,
                "✅ Join confirmed. Send your video link.",
                reply_markup=user_menu(
                    is_admin(call.from_user.id),
                    has_creator_access(call.from_user.id)
                )
            )
        else:
            bot.answer_callback_query(
                call.id,
                "❌ Join the channel first.",
                show_alert=True
            )
    except Exception:
        bot.answer_callback_query(
            call.id,
            "❌ Please join the channel first.",
            show_alert=True
        )

# ============================================================
# BASIC USER FEATURES
# ============================================================

@bot.message_handler(commands=["balance"])
def balance_cmd(message):
    uid = ensure_user(message)
    bot.send_message(
        message.chat.id,
        f"💰 Your balance: ${users[uid].get('balance', 0):.2f}"
    )


@bot.message_handler(commands=["ping"])
def ping_cmd(message):
    start = time.time()
    msg = bot.send_message(message.chat.id, "🏓 Pinging...")
    speed = round((time.time() - start) * 1000)
    bot.edit_message_text(
        f"🏓 <b>PONG!</b>\n\n⚡ Speed: {speed} ms",
        message.chat.id,
        msg.message_id
    )


@bot.message_handler(commands=["view"])
def view_cmd(message):
    bot.send_message(
        message.chat.id,
        "🤖 <b>Video Downloader Bot</b>\n\n"
        "TikTok • YouTube • Facebook • Instagram • Pinterest • "
        "Snapchat • X/Twitter\n\n"
        "⚡ Fast downloads\n🎵 Video to MP3"
    )


@bot.message_handler(func=lambda m: m.text == "💰 BALANCE")
def balance_handler(message):
    if bot_locked_guard(message) or banned_guard(message):
        return
    uid = ensure_user(message)
    bot.send_message(
        message.chat.id,
        f"💰 Available Balance: ${users[uid].get('balance', 0):.2f}\n"
        f"⏳ Blocked Amount: ${users[uid].get('blocked', 0):.2f}"
    )


@bot.message_handler(func=lambda m: m.text == "🆔 GET ID")
def get_id_handler(message):
    uid = ensure_user(message)
    bot.send_message(
        message.chat.id,
        f"🆔 BOT ID: <code>{users[uid]['bot_id']}</code>\n"
        f"👤 Telegram ID: <code>{uid}</code>"
    )


@bot.message_handler(func=lambda m: m.text == "☎️ CUSTOMER")
def customer_handler(message):
    bot.send_message(message.chat.id, "☎️ Customer Support:\n@scholes1")


@bot.message_handler(func=lambda m: m.text == "🤖CUSTOMER AI")
def customer_ai_handler(message):
    bot.send_message(message.chat.id, "AI Customer Support 🤖:\n@Aidownoaderbot")


@bot.message_handler(func=lambda m: m.text == "👥 REFERRAL")
def referral_handler(message):
    uid = ensure_user(message)
    username = bot.get_me().username
    link = f"https://t.me/{username}?start={users[uid]['ref']}"
    bot.send_message(
        message.chat.id,
        f"🔗 <b>Your Referral Link</b>\n{link}\n\n"
        f"👥 Invited: {users[uid].get('invited', 0)}\n"
        "🎁 Reward: $0.2 per referral"
    )


@bot.message_handler(func=lambda m: m.text == "🔙 BACK MAIN MENU")
def back_main(message):
    bot.send_message(
        message.chat.id,
        "🔙 Returning to main menu.",
        reply_markup=user_menu(
            is_admin(message.from_user.id),
            has_creator_access(message.from_user.id)
        )
    )

# ============================================================
# ADMIN PANEL
# ============================================================

@bot.message_handler(func=lambda m: m.text == "👑 ADMIN PANEL")
def open_admin_panel(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ You are not admin.")
        return
    bot.send_message(
        message.chat.id,
        "👑 <b>Main Admin Panel</b>",
        reply_markup=admin_menu()
    )


@bot.message_handler(func=lambda m: m.text == "👥 SEND USERS TO CREATE")
def admin_creator_access_start(message):
    if not is_admin(message.from_user.id):
        return
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(
        "➕ Grant Create Access",
        callback_data="creator_access:add"
    ))
    kb.add(InlineKeyboardButton(
        "➖ Revoke Create Access",
        callback_data="creator_access:remove"
    ))
    kb.add(InlineKeyboardButton(
        "📋 Access List",
        callback_data="creator_access:list"
    ))
    bot.send_message(
        message.chat.id,
        "👥 <b>Bot Creator Access</b>\n\n"
        "Grant users permission to create Managed Downloader Bots.",
        reply_markup=kb
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("creator_access:"))
def creator_access_callback(call):
    if not is_admin(call.from_user.id):
        return

    action = call.data.split(":", 1)[1]

    if action in ("add", "remove"):
        prompt = bot.send_message(
            call.message.chat.id,
            "Send the Telegram User ID."
        )
        bot.register_next_step_handler(
            prompt,
            lambda msg: process_creator_access(msg, action == "add")
        )
        return

    if action == "list":
        docs = list(bot_access_col.find({"enabled": True}))
        if not docs:
            bot.send_message(call.message.chat.id, "📋 No users have access.")
            return
        text = "📋 <b>Creator Access</b>\n\n"
        for doc in docs[:100]:
            text += f"• <code>{doc['_id']}</code>\n"
        bot.send_message(call.message.chat.id, text)


def process_creator_access(message, enabled):
    if not is_admin(message.from_user.id):
        return
    uid = (message.text or "").strip()
    if not uid.isdigit():
        bot.send_message(message.chat.id, "❌ Invalid Telegram ID.")
        return
    set_creator_access(uid, enabled)
    try:
        if uid in users:
            save_user(uid)
            bot.send_message(
                int(uid),
                "🤖 Bot Creator access enabled." if enabled
                else "❌ Bot Creator access revoked."
            )
    except Exception:
        pass
    bot.send_message(
        message.chat.id,
        f"✅ Creator access {'granted' if enabled else 'revoked'} for {uid}."
    )


@bot.message_handler(func=lambda m: m.text == "🤖 ALL CREATED BOTS")
def all_created_bots(message):
    if not is_admin(message.from_user.id):
        return

    records = list(managed_bots_col.find(
        {"status": {"$ne": "deleted"}}
    ).sort("created_at", -1))

    if not records:
        bot.send_message(message.chat.id, "🤖 No managed bots created yet.")
        return

    lines = ["🤖 <b>All Created Bots</b>\n"]
    for r in records[:100]:
        users_count = bot_users_col.count_documents({"bot_id": r["bot_id"]})
        lines.append(
            f"{bot_display(r)}\n"
            f"👤 Owner: <code>{r.get('owner_id')}</code>\n"
            f"👥 Users: {users_count}\n"
            f"🟢 Status: {r.get('status')}\n"
        )
    bot.send_message(message.chat.id, "\n".join(lines))


@bot.message_handler(func=lambda m: m.text == "📢 BROADCAST ALL BOTS")
def broadcast_all_bots_start(message):
    if not is_admin(message.from_user.id):
        return
    prompt = bot.send_message(
        message.chat.id,
        "📢 <b>Broadcast All Bots</b>\n\n"
        "Send text, photo, video, document or audio."
    )
    bot.register_next_step_handler(prompt, broadcast_all_bots_receive)


def broadcast_all_bots_receive(message):
    if not is_admin(message.from_user.id):
        return
    active = managed_bots_col.count_documents({"status": "active"})
    target_users = bot_users_col.count_documents({
        "bot_id": {
            "$in": [
                x["bot_id"]
                for x in managed_bots_col.find({"status": "active"}, {"bot_id": 1})
            ]
        }
    })
    bot.send_message(
        message.chat.id,
        f"📢 <b>Broadcasting...</b>\n\n"
        f"Bots: {active}\nUsers: {target_users}\n\n"
        "The broadcast is running in a background worker."
    )
    broadcast_executor.submit(
        broadcast_all_bots_worker,
        message.chat.id,
        message
    )


@bot.message_handler(func=lambda m: m.text == "📊 STATS")
def stats_handler(message):
    if not is_admin(message.from_user.id):
        return

    total_users = len(users)
    total_balance = sum(x.get("balance", 0) for x in users.values())
    total_blocked = sum(x.get("blocked", 0) for x in users.values())
    total_withdraws = len(withdraws)
    pending = sum(1 for x in withdraws if x.get("status") == "pending")
    managed = managed_bots_col.count_documents({"status": "active"})

    bot.send_message(
        message.chat.id,
        f"📊 <b>BOT STATS</b>\n\n"
        f"👥 Users: {total_users}\n"
        f"💰 Balance: ${total_balance:.2f}\n"
        f"⏳ Blocked: ${total_blocked:.2f}\n"
        f"🧾 Withdrawals: {total_withdraws}\n"
        f"⏳ Pending: {pending}\n"
        f"🤖 Active Managed Bots: {managed}"
    )


@bot.message_handler(func=lambda m: m.text == "📢 BROADCAST")
def broadcast_start(message):
    if not is_admin(message.from_user.id):
        return
    prompt = bot.send_message(
        message.chat.id,
        "📢 Send text, photo, video, document or audio."
    )
    bot.register_next_step_handler(prompt, broadcast_receive)


def broadcast_receive(message):
    if not is_admin(message.from_user.id):
        return
    sent = failed = 0
    for uid in list(users.keys()):
        result = send_copy_to_user(bot, int(uid), message)
        if result == "sent":
            sent += 1
        else:
            failed += 1
        time.sleep(0.05)
    bot.send_message(
        message.chat.id,
        f"✅ Broadcast completed.\nSent: {sent}\nFailed: {failed}"
    )


@bot.message_handler(func=lambda m: m.text == "📢 BROADCAST MEDIA")
def broadcast_media_start(message):
    if not is_admin(message.from_user.id):
        return
    prompt = bot.send_message(
        message.chat.id,
        "Send the media to broadcast."
    )
    bot.register_next_step_handler(prompt, broadcast_receive)


@bot.message_handler(func=lambda m: m.text == "👥 SEE LIST")
def see_users(message):
    if not is_admin(message.from_user.id):
        return
    bot.send_message(
        message.chat.id,
        f"📊 Total Users: {len(users)}"
    )
    for uid in list(users.keys())[:20]:
        bot.send_message(
            message.chat.id,
            f"👤 <code>{uid}</code>",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton(
                    "💬 OPEN CHAT",
                    url=f"tg://user?id={uid}"
                )
            )
        )


@bot.message_handler(func=lambda m: m.text == "⚡ QUICK ACCESS")
def quick_access_admin(message):
    if not is_admin(message.from_user.id):
        return
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ Add User Access", callback_data="qa_add"))
    kb.add(InlineKeyboardButton("🔴 Remove User Access", callback_data="qa_remove"))
    bot.send_message(message.chat.id, "⚡ Quick Access Management", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data.startswith("qa_"))
def quick_access_callback(call):
    if not is_admin(call.from_user.id):
        return
    add = call.data == "qa_add"
    prompt = bot.send_message(
        call.message.chat.id,
        "Send User ID or BOT ID:"
    )
    bot.register_next_step_handler(
        prompt,
        lambda m: grant_quick_access(m, add)
    )


def grant_quick_access(message, enabled):
    if not is_admin(message.from_user.id):
        return
    value = (message.text or "").strip()
    uid = value if value in users else find_user_by_botid(value)
    if not uid:
        bot.send_message(message.chat.id, "❌ User not found.")
        return
    users[uid]["quick_access"] = enabled
    save_user(uid)
    bot.send_message(
        message.chat.id,
        f"✅ Quick Access {'enabled' if enabled else 'disabled'}."
    )


@bot.message_handler(func=lambda m: m.text == "🚫 BAN USER MANUAL")
def manual_ban_start(message):
    if not is_admin(message.from_user.id):
        return
    prompt = bot.send_message(message.chat.id, "Send Telegram ID or BOT ID:")
    bot.register_next_step_handler(prompt, manual_ban_process)


def manual_ban_process(message):
    if not is_admin(message.from_user.id):
        return
    value = (message.text or "").strip()
    uid = value if value in users else find_user_by_botid(value)
    if not uid:
        bot.send_message(message.chat.id, "❌ User not found.")
        return
    users[uid]["banned"] = True
    save_user(uid)
    bot.send_message(message.chat.id, f"🚫 User {uid} banned.")


@bot.message_handler(func=lambda m: m.text == "🔥 UN BAN-USER")
def unban_start(message):
    if not is_admin(message.from_user.id):
        return
    prompt = bot.send_message(message.chat.id, "Send Telegram ID:")
    bot.register_next_step_handler(prompt, unban_process)


def unban_process(message):
    if not is_admin(message.from_user.id):
        return
    uid = (message.text or "").strip()
    if uid not in users:
        bot.send_message(message.chat.id, "❌ User not found.")
        return
    users[uid]["banned"] = False
    save_user(uid)
    bot.send_message(message.chat.id, "✅ User unbanned.")


@bot.message_handler(func=lambda m: m.text == "🔒 LOCK BOT")
def lock_start(message):
    global BOT_LOCKED, LOCK_MESSAGE
    if not is_admin(message.from_user.id):
        return
    prompt = bot.send_message(message.chat.id, "Send lock message:")
    bot.register_next_step_handler(prompt, lock_process)


def lock_process(message):
    global BOT_LOCKED, LOCK_MESSAGE
    if not is_admin(message.from_user.id):
        return
    LOCK_MESSAGE = message.text or LOCK_MESSAGE
    BOT_LOCKED = True
    bot.send_message(message.chat.id, "🔒 Bot locked.")


@bot.message_handler(func=lambda m: m.text == "🔓 UNLOCK BOT")
def unlock_bot(message):
    global BOT_LOCKED
    if not is_admin(message.from_user.id):
        return
    BOT_LOCKED = False
    bot.send_message(message.chat.id, "🔓 Bot unlocked.")


# ============================================================
# ADS
# ============================================================

@bot.message_handler(func=lambda m: m.text == "📢 ADD ADS")
def add_ads_start(message):
    global ADS_ENABLED, ADS_BTN_TEXT, ADS_URL, ADS_TEXT
    if not is_admin(message.from_user.id):
        return
    prompt = bot.send_message(
        message.chat.id,
        "Button Name | Link | Text"
    )
    bot.register_next_step_handler(prompt, add_ads_process)


def add_ads_process(message):
    global ADS_ENABLED, ADS_BTN_TEXT, ADS_URL, ADS_TEXT
    if not is_admin(message.from_user.id):
        return
    parts = [x.strip() for x in (message.text or "").split("|")]
    if len(parts) < 2:
        bot.send_message(message.chat.id, "❌ Invalid format.")
        return
    ADS_BTN_TEXT = parts[0]
    ADS_URL = parts[1]
    ADS_TEXT = parts[2] if len(parts) > 2 else ""
    ADS_ENABLED = True
    bot.send_message(message.chat.id, "✅ Ads enabled.")


@bot.message_handler(func=lambda m: m.text == "🗑 DELETE ADS")
def delete_ads(message):
    global ADS_ENABLED, ADS_BTN_TEXT, ADS_URL, ADS_TEXT
    if not is_admin(message.from_user.id):
        return
    ADS_ENABLED = False
    ADS_BTN_TEXT = ADS_URL = ADS_TEXT = ""
    bot.send_message(message.chat.id, "🗑 Ads deleted.")

# ============================================================
# DOWNLOADS FOR MAIN BOT
# ============================================================

@bot.message_handler(func=lambda m: m.text and "http" in m.text)
def main_link_handler(message):
    if bot_locked_guard(message) or banned_guard(message):
        return

    uid = ensure_user(message)
    url = extract_url(message.text)
    if not url:
        return

    processing = bot.send_message(
        message.chat.id,
        "⚡ Processing..."
    )

    executor = vip_executor if is_quick_access(uid) else normal_executor
    executor.submit(
        download_media_for_bot,
        bot,
        "main",
        message.chat.id,
        url,
        processing.message_id
    )


# ============================================================
# WITHDRAWAL SYSTEM
# ============================================================

@bot.message_handler(func=lambda m: m.text == "💸 WITHDRAWAL")
def withdraw_menu(message):
    if banned_guard(message):
        return
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("USDT-BEP20", "🔙 CANCEL")
    bot.send_message(message.chat.id, "Select withdrawal method:", reply_markup=kb)


@bot.message_handler(func=lambda m: m.text == "USDT-BEP20")
def withdraw_address_start(message):
    prompt = bot.send_message(
        message.chat.id,
        "Enter USDT BEP20 address (must start with 0x):"
    )
    bot.register_next_step_handler(prompt, withdraw_address_step)


def withdraw_address_step(message):
    uid = ensure_user(message)
    address = (message.text or "").strip()
    if not address.startswith("0x"):
        prompt = bot.send_message(message.chat.id, "❌ Invalid address. Try again:")
        bot.register_next_step_handler(prompt, withdraw_address_step)
        return
    users[uid]["temp_addr"] = address
    save_user(uid)
    prompt = bot.send_message(message.chat.id, "Enter withdrawal amount. Minimum $1:")
    bot.register_next_step_handler(prompt, withdraw_amount_step)


def withdraw_amount_step(message):
    uid = ensure_user(message)
    try:
        amount = float((message.text or "").strip())
    except Exception:
        prompt = bot.send_message(message.chat.id, "❌ Invalid amount. Try again:")
        bot.register_next_step_handler(prompt, withdraw_amount_step)
        return

    if amount < 1:
        bot.send_message(message.chat.id, "❌ Minimum withdrawal is $1.")
        return
    if amount > users[uid].get("balance", 0):
        bot.send_message(message.chat.id, "❌ Insufficient balance.")
        return

    wid = random.randint(10000, 99999)
    users[uid]["balance"] -= amount
    users[uid]["blocked"] = users[uid].get("blocked", 0) + amount

    withdrawal = {
        "id": wid,
        "user": uid,
        "amount": amount,
        "blocked": amount,
        "address": users[uid]["temp_addr"],
        "status": "pending",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    withdraws.append(withdrawal)
    save_user(uid)
    save_withdraws()

    bot.send_message(
        message.chat.id,
        f"✅ Withdrawal request sent.\n"
        f"🧾 ID: {wid}\n💵 Amount: ${amount:.2f}\n"
        f"🏦 Address: {withdrawal['address']}"
    )

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✅ CONFIRM", callback_data=f"confirm_{wid}"),
        InlineKeyboardButton("❌ REJECT", callback_data=f"reject_{wid}")
    )
    for admin in ADMIN_IDS:
        try:
            bot.send_message(
                admin,
                f"💳 <b>NEW WITHDRAWAL</b>\n\n"
                f"👤 User: {uid}\n💵 ${amount:.2f}\n"
                f"🧾 ID: {wid}\n🏦 {withdrawal['address']}",
                reply_markup=markup
            )
        except Exception:
            pass


@bot.callback_query_handler(func=lambda c: c.data.startswith(("confirm_", "reject_")))
def withdrawal_callback(call):
    if not is_admin(call.from_user.id):
        return

    try:
        wid = int(call.data.split("_")[1])
    except Exception:
        return

    item = next((x for x in withdraws if x["id"] == wid), None)
    if not item or item.get("status") != "pending":
        return

    uid = item["user"]

    if call.data.startswith("confirm_"):
        item["status"] = "paid"
        users[uid]["blocked"] = max(
            0,
            users[uid].get("blocked", 0) - item["blocked"]
        )
        bot.send_message(int(uid), f"✅ Withdrawal #{wid} approved.")
    else:
        item["status"] = "rejected"
        users[uid]["balance"] += item["blocked"]
        users[uid]["blocked"] = max(
            0,
            users[uid].get("blocked", 0) - item["blocked"]
        )
        bot.send_message(int(uid), f"❌ Withdrawal #{wid} rejected.")

    save_user(uid)
    save_withdraws()
    bot.answer_callback_query(call.id, "Updated.")

# ============================================================
# PAYMENT / IMPORT / REFERRAL ADMIN FEATURES
# ============================================================

@bot.message_handler(func=lambda m: m.text == "SEND PAY")
def send_pay_start(message):
    if not is_admin(message.from_user.id):
        return
    prompt = bot.send_message(
        message.chat.id,
        "Title | Description | Price in Stars"
    )
    bot.register_next_step_handler(prompt, send_pay_process)


def send_pay_process(message):
    if not is_admin(message.from_user.id):
        return
    try:
        title, description, price = [
            x.strip() for x in message.text.split("|", 2)
        ]
        price = int(price)
        prices = [LabeledPrice(label=title, amount=price)]
        count = 0
        for uid in users:
            try:
                bot.send_invoice(
                    int(uid),
                    title=title,
                    description=description,
                    invoice_payload=f"stars_pay_{price}",
                    provider_token="",
                    currency="XTR",
                    prices=prices
                )
                count += 1
            except Exception:
                pass
        bot.send_message(message.chat.id, f"✅ Payment sent to {count} users.")
    except Exception:
        bot.send_message(message.chat.id, "❌ Invalid payment format.")


@bot.message_handler(func=lambda m: m.text == "📥 IMPORT USERS")
def import_users_start(message):
    if not is_admin(message.from_user.id):
        return
    prompt = bot.send_message(message.chat.id, "Send Telegram IDs separated by spaces/new lines:")
    bot.register_next_step_handler(prompt, import_users_process)


def import_users_process(message):
    if not is_admin(message.from_user.id):
        return
    added = 0
    for uid in (message.text or "").replace("\n", " ").split():
        if uid.isdigit() and uid not in users:
            users[uid] = {
                "balance": 0.0, "blocked": 0.0,
                "ref": random_ref(), "bot_id": random_botid(),
                "invited": 0, "banned": False, "verified": False,
                "quick_access": False, "month": now_month()
            }
            save_user(uid)
            added += 1
    bot.send_message(message.chat.id, f"✅ Imported {added} users.")


@bot.message_handler(func=lambda m: m.text == "➕ ADD BALANCE")
def add_balance_start(message):
    if not is_admin(message.from_user.id):
        return
    prompt = bot.send_message(message.chat.id, "Send BOT ID or Telegram ID and amount:")
    bot.register_next_step_handler(prompt, add_balance_process)


def add_balance_process(message):
    if not is_admin(message.from_user.id):
        return
    try:
        ident, amount = message.text.split()
        amount = float(amount)
        uid = ident if ident in users else find_user_by_botid(ident)
        if not uid or amount <= 0:
            raise ValueError
        users[uid]["balance"] += amount
        save_user(uid)
        bot.send_message(message.chat.id, f"✅ Added ${amount:.2f}.")
    except Exception:
        bot.send_message(message.chat.id, "❌ Invalid format.")


@bot.message_handler(func=lambda m: m.text == "➖ REMOVE MONEY")
def remove_balance_start(message):
    if not is_admin(message.from_user.id):
        return
    prompt = bot.send_message(message.chat.id, "Send BOT ID or Telegram ID and amount:")
    bot.register_next_step_handler(prompt, remove_balance_process)


def remove_balance_process(message):
    if not is_admin(message.from_user.id):
        return
    try:
        ident, amount = message.text.split()
        amount = float(amount)
        uid = ident if ident in users else find_user_by_botid(ident)
        if not uid or amount <= 0 or users[uid]["balance"] < amount:
            raise ValueError
        users[uid]["balance"] -= amount
        save_user(uid)
        bot.send_message(message.chat.id, f"✅ Removed ${amount:.2f}.")
    except Exception:
        bot.send_message(message.chat.id, "❌ Invalid format or balance.")


@bot.message_handler(func=lambda m: m.text == "🔎 SEARCH USER")
def search_user_start(message):
    if not is_admin(message.from_user.id):
        return
    prompt = bot.send_message(message.chat.id, "Send Telegram ID:")
    bot.register_next_step_handler(prompt, search_user_result)


def search_user_result(message):
    if not is_admin(message.from_user.id):
        return
    uid = (message.text or "").strip()
    if uid not in users:
        bot.send_message(message.chat.id, "❌ User not found.")
        return
    bot.send_message(
        message.chat.id,
        f"👤 User Found\nID: <code>{uid}</code>",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("💬 OPEN CHAT", url=f"tg://user?id={uid}")
        )
    )

# ============================================================
# FEEDBACK
# ============================================================

@bot.message_handler(func=lambda m: m.text in [
    "📊 Feedback Stats", "🟢 Open Feedback",
    "🔴 Close Feedback", "🗑️ Reset All Feedbacks"
])
def feedback_admin(message):
    if not is_admin(message.from_user.id):
        return

    if message.text == "🟢 Open Feedback":
        videos_data["feedback_enabled"] = True
        save_videos()
        bot.send_message(message.chat.id, "🟢 Feedback opened.")
        return

    if message.text == "🔴 Close Feedback":
        videos_data["feedback_enabled"] = False
        save_videos()
        bot.send_message(message.chat.id, "🔴 Feedback closed.")
        return

    if message.text == "🗑️ Reset All Feedbacks":
        feedback_col.delete_many({})
        bot.send_message(message.chat.id, "✅ All feedbacks reset.")
        return

    good = feedback_col.count_documents({"rating": "good"})
    bad = feedback_col.count_documents({"rating": "bad"})
    written = feedback_col.count_documents({"feedback_text": {"$exists": True}})
    total = good + bad
    satisfaction = f"{good / total * 100:.2f}%" if total else "N/A"

    bot.send_message(
        message.chat.id,
        f"📊 <b>Feedback Statistics</b>\n\n"
        f"👍 Good: {good}\n"
        f"👎 Bad: {bad}\n"
        f"💬 Written: {written}\n"
        f"❤️ Satisfaction: {satisfaction}"
    )

# ============================================================
# ADMIN CHANNEL / VERIFY / POST SETTINGS
# ============================================================

@bot.message_handler(func=lambda m: m.text == "📡 ADD CHANNEL")
def add_channel_start(message):
    if not is_admin(message.from_user.id):
        return
    prompt = bot.send_message(message.chat.id, "Send channel username, e.g. @mychannel:")
    bot.register_next_step_handler(prompt, add_channel_process)


def add_channel_process(message):
    if not is_admin(message.from_user.id):
        return
    username = (message.text or "").strip()
    if not username.startswith("@"):
        username = "@" + username
    try:
        member = bot.get_chat_member(username, bot.get_me().id)
        if member.status not in ["administrator", "creator"]:
            bot.send_message(message.chat.id, "❌ Bot is not admin there.")
            return
        if username not in MANAGED_CHANNELS:
            MANAGED_CHANNELS.append(username)
        bot.send_message(message.chat.id, f"✅ Channel added: {username}")
    except Exception:
        bot.send_message(message.chat.id, "❌ Invalid channel or permissions.")


@bot.message_handler(func=lambda m: m.text == "CLOSE CHANNEL POST")
def close_channel_post(message):
    if not is_admin(message.from_user.id):
        return
    MANAGED_CHANNELS.clear()
    bot.send_message(message.chat.id, "❌ All managed channels removed.")


@bot.message_handler(func=lambda m: m.text == "❌ CLOSE WINDOWS")
def close_windows(message):
    global CHANNEL_WINDOW_OPEN
    if not is_admin(message.from_user.id):
        return
    CHANNEL_WINDOW_OPEN = False
    bot.send_message(message.chat.id, "✅ Channel join window closed.")


@bot.message_handler(func=lambda m: m.text == "✅ VERIFY ON")
def verify_on(message):
    global VERIFY_ENABLED
    if not is_admin(message.from_user.id):
        return
    VERIFY_ENABLED = True
    bot.send_message(message.chat.id, "✅ Verify system enabled.")


@bot.message_handler(func=lambda m: m.text == "❌ VERIFY OFF")
def verify_off(message):
    global VERIFY_ENABLED
    if not is_admin(message.from_user.id):
        return
    VERIFY_ENABLED = False
    bot.send_message(message.chat.id, "❌ Verify system disabled.")


@bot.message_handler(func=lambda m: m.text == "📌 POST CHANNEL")
def post_channel_start(message):
    global CHANNEL_WINDOW_OPEN
    if not is_admin(message.from_user.id):
        return
    CHANNEL_WINDOW_OPEN = True
    POST_CHANNELS.clear()
    prompt = bot.send_message(
        message.chat.id,
        "Send channel usernames one per message. Send DONE when finished."
    )
    bot.register_next_step_handler(prompt, post_channel_add)


def post_channel_add(message):
    if not is_admin(message.from_user.id):
        return
    text = (message.text or "").strip()
    if text.lower() == "done":
        bot.send_message(message.chat.id, f"✅ {len(POST_CHANNELS)} channels added.")
        return
    if len(POST_CHANNELS) >= MAX_CHANNELS:
        bot.send_message(message.chat.id, "⚠️ Maximum 10 channels.")
        return
    POST_CHANNELS.append(text.lstrip("@"))
    prompt = bot.send_message(
        message.chat.id,
        f"✅ Added. Total: {len(POST_CHANNELS)}. Send another or DONE."
    )
    bot.register_next_step_handler(prompt, post_channel_add)


# ============================================================
# OPTIONAL SECOND VERIFY BOT
# ============================================================

if bot2:
    @bot2.message_handler(commands=["start"])
    def verify_start(message):
        args = message.text.split()
        if len(args) > 1:
            bot2.send_message(
                message.chat.id,
                f"🔑 <b>Your Verification Code</b>\n\n<code>{args[1]}</code>"
            )
        else:
            bot2.send_message(
                message.chat.id,
                "❌ Don't have a code? Get one from the downloader bot."
            )

# ============================================================
# STARTUP
# ============================================================

def start_existing_managed_bots():
    records = list(managed_bots_col.find({"status": "active"}))
    for record in records:
        try:
            start_managed_bot_worker(record)
        except Exception:
            pass


def run_main_bot():
    bot.infinity_polling(
        timeout=20,
        long_polling_timeout=20,
        allowed_updates=None
    )


def run_verify_bot():
    if bot2:
        bot2.infinity_polling(
            timeout=20,
            long_polling_timeout=20
        )


if __name__ == "__main__":
    os.makedirs("downloads", exist_ok=True)

    # Managed Bot workers are independent from the Manager Bot polling.
    start_existing_managed_bots()

    print("🤖 Downloader Manager Bot is running...")
    print("ℹ️ Managed Bot tokens are never printed.")

    t1 = threading.Thread(target=run_main_bot, daemon=True)
    t1.start()

    if bot2:
        t2 = threading.Thread(target=run_verify_bot, daemon=True)
        t2.start()

    t1.join()
