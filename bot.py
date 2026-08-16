import telebot
from pymongo import MongoClient
import requests
from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, LabeledPrice
import os, json, random
from datetime import datetime
import yt_dlp
import subprocess
import re
import shutil
import threading
import asyncio
import uuid
import time
from concurrent.futures import ThreadPoolExecutor

from telethon import TelegramClient
import smtplib
from email.mime.text import MIMEText

# ================= CONFIG =================

TOKEN = os.getenv("BOT_TOKEN")
BOT2_TOKEN = os.getenv("BOT2_TOKEN")

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")

PHONE = os.getenv("PHONE")

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_PASS")

MAX_YOUTUBE_DURATION = int(os.getenv("MAX_YOUTUBE_DURATION", "600"))  # 10 Minutes in seconds
MAX_CONCURRENT_DOWNLOADS = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "20"))

# Dual executors for Priority (Quick Access) & Normal
vip_executor = ThreadPoolExecutor(max_workers=5)
normal_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_DOWNLOADS)

http_session = requests.Session()

try:
    tg_client = TelegramClient("session", API_ID, API_HASH)
except Exception as e:
    print(f"Warning: Telethon setup failed or missing credentials: {e}")
    tg_client = None

bot = telebot.TeleBot(TOKEN, parse_mode="HTML") if TOKEN else None
bot2 = telebot.TeleBot(BOT2_TOKEN, parse_mode="HTML") if BOT2_TOKEN else None

ADMIN_IDS = [7983838654]

CHANNEL_ID = "@tiktokvediodownload"

POST_CHANNELS = []
pending_links = {}
CHANNEL_WINDOW_OPEN = False
MANAGED_CHANNELS = []
MAX_CHANNELS = 10

BOT_LOCKED = False
LOCK_MESSAGE = "🔒 Bot is temporarily locked by admin."

pending_post = {}
channel_posts = {}

VERIFY_ENABLED = False
verify_pending = {}
video_files = {}

ADS_ENABLED = False
ADS_TEXT = ""
ADS_BTN_TEXT = ""
ADS_URL = "" 

# ================= MONGODB SETUP (DUAL DATABASE) =================
MONGO_URI_1 = os.getenv("MONGO_URI_1", os.getenv("MONGO_URI", "mongodb://localhost:27017/user_db"))
MONGO_URI_2 = os.getenv("MONGO_URI_2", "mongodb://localhost:27017/stats_db")

try:
    mongo_client1 = MongoClient(MONGO_URI_1)
    try:
        db1 = mongo_client1.get_default_database()
    except Exception:
        db1 = mongo_client1["user_db"]
        
    users_col = db1["users"]
    withdraws_col = db1["withdraws"]
    print("✅ MongoDB 1 (Users & Withdraws) Connected Successfully")
except Exception as e:
    print(f"❌ MongoDB 1 Connection Error: {e}")
    exit()

try:
    mongo_client2 = MongoClient(MONGO_URI_2)
    try:
        db2 = mongo_client2.get_default_database()
    except Exception:
        db2 = mongo_client2["stats_db"]
        
    videos_col = db2["videos"]
    feedback_col = db2["feedback"]
    
    # New Collections for Managed Bots System
    managed_bots_col = db2["managed_bots"]
    mbot_users_col = db2["mbot_users"]
    settings_col = db2["settings"]
    print("✅ MongoDB 2 (Videos, Stats, Feedback & Bots) Connected Successfully")
except Exception as e:
    print(f"❌ MongoDB 2 Connection Error: {e}")
    exit()

# ================= MONGODB DATABASE FUNCTIONS =================

def load_users():
    users_dict = {}
    for user in users_col.find():
        uid = str(user["_id"])
        user_data = user.copy()
        user_data.pop("_id", None)
        users_dict[uid] = user_data
    return users_dict

def save_user(uid):
    uid_str = str(uid)
    if uid_str in users:
        data = users[uid_str].copy()
        data.pop("_id", None)
        users_col.update_one({"_id": uid_str}, {"$set": data}, upsert=True)

users = load_users()

def save_users():
    for uid in users:
        save_user(uid)

def load_withdraws():
    return list(withdraws_col.find({}, {"_id": False}))

withdraws = load_withdraws()

def save_withdraws():
    withdraws_col.delete_many({})
    if withdraws:
        clean_withdraws = [{**w} for w in withdraws]
        withdraws_col.insert_many(clean_withdraws)

def load_videos():
    v_data = videos_col.find_one({"_id": "stats"})
    if not v_data:
        default_data = {
            "_id": "stats",
            "total": 0,
            "feedback_enabled": False,
            "platforms": {
                "tiktok": 0,
                "youtube": 0,
                "facebook": 0,
                "pinterest": 0,
                "instagram": 0,
                "snapchat": 0,
                "twitter": 0
            },
            "users": {}
        }
        videos_col.insert_one(default_data)
        return default_data
    v_data.pop("_id", None)
    return v_data

videos_data = load_videos()

def save_videos():
    data = videos_data.copy()
    data.pop("_id", None)
    videos_col.update_one({"_id": "stats"}, {"$set": data}, upsert=True)

# Bot Builder Settings
def is_bot_creation_enabled():
    st = settings_col.find_one({"_id": "bot_creation"})
    return st["enabled"] if st else False

def set_bot_creation(enabled: bool):
    settings_col.update_one({"_id": "bot_creation"}, {"$set": {"enabled": enabled}}, upsert=True)


# ================= HELPER FUNCTIONS =================
def random_ref():
    return str(random.randint(1000000000, 9999999999))

def random_botid():
    return str(random.randint(10000000000, 99999999999))

def now_month():
    return datetime.now().month

def is_admin(uid):
    return int(uid) in ADMIN_IDS

def is_quick_access(uid):
    return users.get(str(uid), {}).get("quick_access", False)

def find_user_by_botid(bid):
    for u, data in users.items():
        if data.get("bot_id") == bid:
            return u
    return None

def banned_guard(m):
    uid = str(m.from_user.id)
    if uid in users and users[uid].get("banned"):
        try:
            bot.send_message(m.chat.id, "🚫 You are banned.")
        except:
            pass
        return True
    return False

def bot_locked_guard(message):
    global BOT_LOCKED, LOCK_MESSAGE
    if BOT_LOCKED and not is_admin(message.from_user.id):
        try:
            bot.send_message(message.chat.id, LOCK_MESSAGE)
        except:
            pass
        return True
    return False

# ================= MENUS =================
def user_menu(show_admin=False):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💰 BALANCE", "💸 WITHDRAWAL")
    kb.add("👥 REFERRAL", "🆔 GET ID")
    kb.add("☎️ CUSTOMER", "🤖CUSTOMER AI")
    if is_bot_creation_enabled() or show_admin:
        kb.add("🤖 Bot Builder")
    if show_admin:
        kb.add("👑 ADMIN PANEL")
    return kb

def admin_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📊 STATS", "📢 BROADCAST")
    kb.add("👥 Send Users To Create", "📢 Broadcast All Bots")
    kb.add("🤖 All Created Bots", "⚙️ Bot Creation Access")
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

def back_to_main_menu(m):
    uid = str(m.from_user.id)
    try:
        bot.send_message(
            m.chat.id,
            "🔙 Returning to main menu",
            reply_markup=user_menu(is_admin(uid))
        )
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "🔙 BACK MAIN MENU")
def back_button_handler(m):
    back_to_main_menu(m)

# ================= CORE DOWNLOADER ENGINE =================
def download_media(bot_instance, chat_id, link, msg_id):
    """
    Unified Downloader Engine used by both the Main Bot and all Managed Bots.
    """
    try:
        try:
            bot_instance.edit_message_text("⏳ Downloading media, please wait...", chat_id, msg_id)
        except Exception:
            pass
            
        os.makedirs("downloads", exist_ok=True)
        
        ydl_opts = {
            'outtmpl': f'downloads/{chat_id}_%(id)s.%(ext)s',
            'format': 'best',
            'quiet': True,
            'max_filesize': 50000000, # 50MB telegram limit for standard bots
            'noplaylist': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            filename = ydl.prepare_filename(info)
        
        if os.path.exists(filename):
            with open(filename, 'rb') as video_file:
                bot_instance.send_video(chat_id, video_file, caption="✅ Downloaded successfully!")
            os.remove(filename)
            try:
                bot_instance.delete_message(chat_id, msg_id)
            except Exception:
                pass
        else:
            bot_instance.edit_message_text("❌ Failed to process the downloaded file.", chat_id, msg_id)
            
    except Exception as e:
        try:
            bot_instance.edit_message_text(f"❌ Download failed or file too large.\nError: {str(e)[:50]}", chat_id, msg_id)
        except Exception:
            pass

# ================= MANAGED BOTS SYSTEM =================

running_mbots = {}

def start_managed_bot(bot_data):
    bot_id = str(bot_data["bot_id"])
    token = bot_data["token"]
    owner_id = str(bot_data["owner_id"])
    
    mbot = telebot.TeleBot(token, parse_mode="HTML")
    
    @mbot.message_handler(commands=['start'])
    def mbot_start(message):
        user_id = str(message.from_user.id)
        mbot_users_col.update_one(
            {"bot_id": bot_id, "user_id": user_id},
            {"$set": {"username": message.from_user.username, "joined_at": datetime.now()}},
            upsert=True
        )
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        if user_id == owner_id:
            kb.add("👑 Admin Panel")
        mbot.send_message(message.chat.id, "👋 Welcome to Video Downloader Bot! Send me a link to download.", reply_markup=kb)
        
    @mbot.message_handler(func=lambda m: m.text == "👑 Admin Panel")
    def mbot_admin(message):
        if str(message.from_user.id) == owner_id:
            kb = ReplyKeyboardMarkup(resize_keyboard=True)
            kb.add("📊 Bot Statistics", "📢 Broadcast")
            kb.add("🔙 Close Admin")
            mbot.send_message(message.chat.id, "👑 Managed Bot Admin Panel", reply_markup=kb)

    @mbot.message_handler(func=lambda m: m.text == "🔙 Close Admin")
    def mbot_close_admin(message):
        if str(message.from_user.id) == owner_id:
            kb = ReplyKeyboardMarkup(resize_keyboard=True)
            kb.add("👑 Admin Panel")
            mbot.send_message(message.chat.id, "🔙 Main menu", reply_markup=kb)

    @mbot.message_handler(func=lambda m: m.text == "📊 Bot Statistics")
    def mbot_stats(message):
        if str(message.from_user.id) == owner_id:
            users_count = mbot_users_col.count_documents({"bot_id": bot_id})
            bdata = managed_bots_col.find_one({"bot_id": bot_id})
            dls = bdata.get("downloads", 0) if bdata else 0
            mbot.send_message(message.chat.id, f"📊 <b>Bot Statistics</b>\n\n👥 Users: {users_count}\n📥 Downloads: {dls}")

    @mbot.message_handler(func=lambda m: m.text == "📢 Broadcast")
    def mbot_broadcast_start(message):
        if str(message.from_user.id) == owner_id:
            msg = mbot.send_message(message.chat.id, "📢 Send your broadcast message (Text/Photo/Video):")
            mbot.register_next_step_handler(msg, lambda m: execute_mbot_broadcast(m, mbot, bot_id))
            
    def execute_mbot_broadcast(m, mbot_instance, b_id):
        mbot_instance.send_message(m.chat.id, "📢 Broadcast started...")
        def do_bc():
            users_cursor = mbot_users_col.find({"bot_id": b_id})
            sent, failed = 0, 0
            for u in users_cursor:
                try:
                    if m.content_type == 'text':
                        mbot_instance.send_message(u['user_id'], m.text)
                    elif m.content_type == 'photo':
                        mbot_instance.send_photo(u['user_id'], m.photo[-1].file_id, caption=m.caption)
                    elif m.content_type == 'video':
                        mbot_instance.send_video(u['user_id'], m.video.file_id, caption=m.caption)
                    sent += 1
                    time.sleep(0.05)
                except Exception:
                    failed += 1
            mbot_instance.send_message(m.chat.id, f"✅ Broadcast Completed\n\nSent: {sent}\nFailed: {failed}")
        threading.Thread(target=do_bc, daemon=True).start()
        
    @mbot.message_handler(func=lambda m: m.text and "http" in m.text)
    def mbot_download_request(message):
        managed_bots_col.update_one({"bot_id": bot_id}, {"$inc": {"downloads": 1}})
        videos_col.update_one({"_id": "stats"}, {"$inc": {"total": 1}}, upsert=True)
        msg = mbot.send_message(message.chat.id, "⏳ Processing link...")
        normal_executor.submit(download_media, mbot, message.chat.id, message.text, msg.message_id)
        
    def run_bot():
        try:
            mbot.polling(non_stop=True, skip_pending=True)
        except Exception as e:
            print(f"Error in running managed bot {bot_id}: {e}")
            
    t = threading.Thread(target=run_bot, daemon=True)
    t.start()
    
    running_mbots[bot_id] = (mbot, t)

def load_and_start_mbots():
    bots = managed_bots_col.find({"status": "active"})
    for b in bots:
        try:
            start_managed_bot(b)
            print(f"✅ Started managed bot: @{b['bot_username']}")
        except Exception as e:
            print(f"❌ Failed to start managed bot @{b['bot_username']}: {e}")

# Admin Bot Creation Controls
@bot.message_handler(func=lambda m: m.text == "⚙️ Bot Creation Access")
def toggle_bot_creation(m):
    if not is_admin(m.from_user.id): return
    current = is_bot_creation_enabled()
    set_bot_creation(not current)
    status = "Enabled 🟢" if not current else "Disabled 🔴"
    bot.send_message(m.chat.id, f"⚙️ Bot creation access is now {status}")
    
@bot.message_handler(func=lambda m: m.text in ["👥 Send Users To Create", "🤖 Bot Builder"])
def show_bot_creation_system(m):
    if not is_bot_creation_enabled() and not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ Bot creation is currently unavailable.")
        return
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Create New Bot", "🤖 My Bots")
    kb.add("🗑 Delete Bot", "🔙 BACK MAIN MENU")
    bot.send_message(m.chat.id, "🤖 <b>Bot Creation System</b>", reply_markup=kb)

# Broadcast All Managed Bots
@bot.message_handler(func=lambda m: m.text == "📢 Broadcast All Bots")
def broadcast_all_bots(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "📢 Send message (Text/Photo/Video) to broadcast to ALL users of ALL managed bots:")
    bot.register_next_step_handler(msg, execute_broadcast_all)

def execute_broadcast_all(m):
    if not is_admin(m.from_user.id): return
    bot.send_message(m.chat.id, "📢 Global Broadcast started...")
    
    def do_global_bc():
        sent = 0
        failed = 0
        active_bots = list(managed_bots_col.find({"status": "active"}))
        
        for b in active_bots:
            if b["bot_id"] in running_mbots:
                mbot_instance = running_mbots[b["bot_id"]][0]
                users = mbot_users_col.find({"bot_id": b["bot_id"]})
                for u in users:
                    try:
                        if m.content_type == 'text':
                            mbot_instance.send_message(u['user_id'], m.text)
                        elif m.content_type == 'photo':
                            mbot_instance.send_photo(u['user_id'], m.photo[-1].file_id, caption=m.caption)
                        elif m.content_type == 'video':
                            mbot_instance.send_video(u['user_id'], m.video.file_id, caption=m.caption)
                        sent += 1
                        time.sleep(0.05)
                    except Exception:
                        failed += 1
                        
        bot.send_message(m.chat.id, f"✅ Global Broadcast Completed\n\nBots: {len(active_bots)}\nSent: {sent}\nFailed: {failed}")
    threading.Thread(target=do_global_bc, daemon=True).start()

# View All Created Bots
@bot.message_handler(func=lambda m: m.text == "🤖 All Created Bots")
def all_created_bots(m):
    if not is_admin(m.from_user.id): return
    bots = list(managed_bots_col.find({"status": "active"}))
    msg = f"🤖 <b>Total Active Bots: {len(bots)}</b>\n\n"
    for i, b in enumerate(bots[:50], 1):
        dls = b.get('downloads', 0)
        msg += f"{i}. @{b['bot_username']} (Owner: <code>{b['owner_id']}</code>) - DLs: {dls}\n"
    bot.send_message(m.chat.id, msg)

# Bot Creation Flow
@bot.message_handler(func=lambda m: m.text == "➕ Create New Bot")
def create_new_bot(m):
    if not is_bot_creation_enabled() and not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ Bot creation is currently unavailable.")
        return
    msg = bot.send_message(m.chat.id, "<b>Step 1:</b> Go to @BotFather and create a new bot.\n<b>Step 2:</b> Forward or paste the HTTP API Token here.")
    bot.register_next_step_handler(msg, process_new_bot_token)
    
def process_new_bot_token(m):
    if m.text in ["🔙 BACK MAIN MENU", "🤖 My Bots", "🗑 Delete Bot"]:
        return
        
    token = m.text.strip()
    msg_wait = bot.send_message(m.chat.id, "⏳ Verifying token...")
    
    try:
        req = requests.get(f"https://api.telegram.org/bot{token}/getMe").json()
        if req.get("ok"):
            bot_username = req["result"]["username"]
            bot_name = req["result"]["first_name"]
            
            # Check if exists
            if managed_bots_col.find_one({"bot_username": bot_username}):
                bot.edit_message_text("❌ This bot is already registered in the system.", m.chat.id, msg_wait.message_id)
                return
                
            bot_id = str(uuid.uuid4())
            bot_data = {
                "bot_id": bot_id,
                "owner_id": str(m.from_user.id),
                "owner_username": m.from_user.username,
                "bot_username": bot_username,
                "bot_name": bot_name,
                "token": token,
                "status": "active",
                "created_at": datetime.now(),
                "downloads": 0
            }
            managed_bots_col.insert_one(bot_data)
            
            # Start it up
            start_managed_bot(bot_data)
            
            bot.edit_message_text(f"✅ <b>Bot Successfully Created & Started!</b>\n\n🤖 Name: {bot_name}\n🔗 Username: @{bot_username}\n\nYou are now the owner. Send /start to your bot to access your Admin Panel.", m.chat.id, msg_wait.message_id)
        else:
            bot.edit_message_text("❌ Invalid Token. Please make sure you copied it correctly from @BotFather.", m.chat.id, msg_wait.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ Error verifying token: {e}", m.chat.id, msg_wait.message_id)

@bot.message_handler(func=lambda m: m.text == "🤖 My Bots")
def my_bots(m):
    if not is_bot_creation_enabled() and not is_admin(m.from_user.id): return
    bots = list(managed_bots_col.find({"owner_id": str(m.from_user.id), "status": "active"}))
    if not bots:
        bot.send_message(m.chat.id, "❌ You have no active bots.")
        return
    msg = "🤖 <b>Your Bots:</b>\n\n"
    for b in bots:
        users_c = mbot_users_col.count_documents({"bot_id": b["bot_id"]})
        msg += f"• @{b['bot_username']} - Users: {users_c} - Downloads: {b.get('downloads',0)}\n"
    bot.send_message(m.chat.id, msg)

@bot.message_handler(func=lambda m: m.text == "🗑 Delete Bot")
def delete_bot_prompt(m):
    if not is_bot_creation_enabled() and not is_admin(m.from_user.id): return
    bots = list(managed_bots_col.find({"owner_id": str(m.from_user.id), "status": "active"}))
    if not bots:
        bot.send_message(m.chat.id, "❌ You have no active bots to delete.")
        return
    kb = InlineKeyboardMarkup()
    for b in bots:
        kb.add(InlineKeyboardButton(f"@{b['bot_username']}", callback_data=f"builder_delete_{b['bot_id']}"))
    bot.send_message(m.chat.id, "🗑 Select a bot to delete:", reply_markup=kb)
    
@bot.callback_query_handler(func=lambda call: call.data.startswith("builder_delete_"))
def delete_bot_confirm(call):
    bot_id = call.data.replace("builder_delete_", "")
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Yes, Delete", callback_data=f"builder_confirm_del_{bot_id}"))
    kb.add(InlineKeyboardButton("❌ Cancel", callback_data="builder_cancel_del"))
    bot.edit_message_text("⚠️ <b>Are you sure?</b>\nThis will remove the bot and stop it permanently.", call.message.chat.id, call.message.message_id, reply_markup=kb)
    
@bot.callback_query_handler(func=lambda call: call.data == "builder_cancel_del")
def cancel_del(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    
@bot.callback_query_handler(func=lambda call: call.data.startswith("builder_confirm_del_"))
def execute_delete_bot(call):
    bot_id = call.data.replace("builder_confirm_del_", "")
    managed_bots_col.update_one({"bot_id": bot_id}, {"$set": {"status": "deleted"}})
    
    if bot_id in running_mbots:
        try:
            running_mbots[bot_id][0].stop_polling()
            del running_mbots[bot_id]
        except Exception:
            pass
            
    bot.edit_message_text("✅ Bot successfully deleted and stopped.", call.message.chat.id, call.message.message_id)

# ================= QUICK ACCESS ADMIN CONTROLS =================
@bot.message_handler(func=lambda m: m.text == "⚡ QUICK ACCESS")
def quick_access_admin(m):
    if not is_admin(m.from_user.id):
        return
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ Add User Access", callback_data="qa_add"))
    kb.add(InlineKeyboardButton("🔴 Remove User Access", callback_data="qa_remove"))
    try:
        bot.send_message(m.chat.id, "⚡ Quick Access Management", reply_markup=kb)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("qa_"))
def handle_qa_callbacks(call):
    if not is_admin(call.from_user.id):
        return
    if call.data == "qa_add":
        try:
            msg = bot.send_message(call.message.chat.id, "Send User ID or BOT ID to grant Quick Access:")
            bot.register_next_step_handler(msg, lambda m: grant_qa(m, True))
        except:
            pass
    elif call.data == "qa_remove":
        try:
            msg = bot.send_message(call.message.chat.id, "Send User ID or BOT ID to remove Quick Access:")
            bot.register_next_step_handler(msg, lambda m: grant_qa(m, False))
        except:
            pass

def grant_qa(m, status):
    if not is_admin(m.from_user.id):
        return
    text_input = (m.text or "").strip()
    uid = text_input if text_input in users else find_user_by_botid(text_input)
    if uid and uid in users:
        users[uid]["quick_access"] = status
        save_user(uid)
        try:
            bot.send_message(m.chat.id, f"✅ Quick Access for user {uid} set to {status}")
        except:
            pass
    else:
        try:
            bot.send_message(m.chat.id, "❌ User not found.")
        except:
            pass

# ================= FEEDBACK LOGIC =================

def send_feedback_request(chat_id, platform, download_id):
    feedback_request_id = str(uuid.uuid4())
    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("👍 Good", callback_data=f"rate_good_{feedback_request_id}_{platform}"),
        InlineKeyboardButton("👎 Bad", callback_data=f"rate_bad_{feedback_request_id}_{platform}")
    )
    kb.add(InlineKeyboardButton("💬 Feedback", callback_data=f"rate_text_{feedback_request_id}"))
    
    try:
        bot.send_message(chat_id, "How was your experience with our service? ❤️", reply_markup=kb)
    except Exception as e:
        print(f"Feedback send error: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith(("rate_good_", "rate_bad_")))
def handle_rating(call):
    parts = call.data.split("_")
    rating = parts[1]
    req_id = parts[2]
    platform = parts[3]
    user_id = call.from_user.id
    
    feedback_col.update_one(
        {"user_id": user_id, "feedback_request_id": req_id},
        {"$set": {
            "username": call.from_user.username or "N/A",
            "rating": rating,
            "platform": platform,
            "updated_at": datetime.now()
        }, "$setOnInsert": {"created_at": datetime.now()}},
        upsert=True
    )
    
    bot.answer_callback_query(call.id, "Thank you for your feedback! ❤️")
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.edit_message_text("Thank you for your feedback! ❤️", call.message.chat.id, call.message.message_id)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("rate_text_"))
def ask_written_feedback(call):
    req_id = call.data.split("_")[2]
    try:
        msg = bot.send_message(call.message.chat.id, "Please tell us how we can improve our service.")
        bot.register_next_step_handler(msg, save_written_feedback, req_id)
    except:
        pass

def save_written_feedback(m, req_id):
    if not m.text:
        try:
            bot.send_message(m.chat.id, "Please send text feedback.")
        except:
            pass
        return
        
    feedback_col.update_one(
        {"user_id": m.from_user.id, "feedback_request_id": req_id},
        {"$set": {
            "username": m.from_user.username or "N/A",
            "feedback_text": m.text,
            "updated_at": datetime.now()
        }, "$setOnInsert": {"created_at": datetime.now()}},
        upsert=True
    )
    try:
        bot.send_message(m.chat.id, "Thank you! Your feedback has been received. ❤️")
    except:
        pass

@bot.message_handler(func=lambda m: m.text in ["📊 Feedback Stats", "🟢 Open Feedback", "🔴 Close Feedback", "🗑️ Reset All Feedbacks"])
def feedback_admin_manager(m):
    if not is_admin(m.from_user.id): return
    
    if m.text == "🟢 Open Feedback":
        videos_data["feedback_enabled"] = True
        save_videos()
        try:
            bot.send_message(m.chat.id, "🟢 Feedback system is now OPEN.")
        except:
            pass
        
    elif m.text == "🔴 Close Feedback":
        videos_data["feedback_enabled"] = False
        save_videos()
        try:
            bot.send_message(m.chat.id, "🔴 Feedback system is now CLOSED.")
        except:
            pass
        
    elif m.text == "📊 Feedback Stats":
        goods = feedback_col.count_documents({"rating": "good"})
        bads = feedback_col.count_documents({"rating": "bad"})
        written = feedback_col.count_documents({"feedback_text": {"$exists": True}})
        total = goods + bads
        
        sat = "No ratings yet."
        if total > 0:
            pct = (goods / total) * 100
            sat = f"{pct:.2f}%"
            
        status = "OPEN" if videos_data.get("feedback_enabled") else "CLOSED"
        
        text = f"📊 FEEDBACK STATISTICS\n\n👍 Good: {goods}\n👎 Bad: {bads}\n💬 Written Feedback: {written}\n📊 Total Ratings: {total}\n❤️ Satisfaction: {sat}\n\n🟢 Status: {status}"
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("💬 View Feedback", callback_data="view_fb_0"))
        try:
            bot.send_message(m.chat.id, text, reply_markup=kb)
        except:
            pass
        
    elif m.text == "🗑️ Reset All Feedbacks":
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("✅ Yes, Reset Everything", callback_data="reset_fb_confirm"))
        kb.add(InlineKeyboardButton("❌ Cancel", callback_data="reset_fb_cancel"))
        try:
            bot.send_message(m.chat.id, "⚠️ Are you sure you want to delete all existing feedback data? This action cannot be undone.", reply_markup=kb)
        except:
            pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("view_fb_"))
def view_feedback_pagination(call):
    if not is_admin(call.from_user.id): return
    page = int(call.data.split("_")[2])
    all_fb = list(feedback_col.find({"feedback_text": {"$exists": True}}).sort("created_at", -1))
    
    if not all_fb:
        bot.answer_callback_query(call.id, "No feedback yet.")
        return
        
    item = all_fb[page]
    text = f"💬 USER FEEDBACK\n\n👤 User: @{item.get('username', 'N/A')}\n📅 Date: {item.get('created_at').strftime('%Y-%m-%d')}\n\n📝 {item.get('feedback_text')}"
    
    kb = InlineKeyboardMarkup()
    btns = []
    if page > 0: btns.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"view_fb_{page-1}"))
    if page < len(all_fb) - 1: btns.append(InlineKeyboardButton("Next ➡️", callback_data=f"view_fb_{page+1}"))
    kb.row(*btns)
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="close_fb"))
    
    try: bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda call: call.data in ["reset_fb_confirm", "reset_fb_cancel", "close_fb"])
def reset_callback_handler(call):
    if not is_admin(call.from_user.id): return
    if call.data == "reset_fb_confirm":
        try:
            feedback_col.delete_many({})
            bot.edit_message_text("✅ ALL FEEDBACKS RESET. All previous feedback data has been successfully deleted.", call.message.chat.id, call.message.message_id)
        except: bot.edit_message_text("❌ RESET FAILED", call.message.chat.id, call.message.message_id)
    elif call.data == "reset_fb_cancel":
        bot.edit_message_text("❌ Reset cancelled.", call.message.chat.id, call.message.message_id)
    elif call.data == "close_fb":
        bot.delete_message(call.message.chat.id, call.message.message_id)

CHANNEL_USERNAME = "@tiktokvediodownload"

# ================= START HANDLER =================
@bot.message_handler(commands=['start'])
def start_handler(message):
    if bot_locked_guard(message):
        return

    uid = message.from_user.id
    args = message.text.split()

    if str(uid) not in users:
        ref = args[1] if len(args) > 1 else None
        users[str(uid)] = {
            "username": message.from_user.username or "",
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
        if ref:
            ref_user = next((u for u, d in users.items() if d["ref"] == ref), None)
            if ref_user and ref_user != str(uid):
                users[ref_user]["balance"] += 0.2
                users[ref_user]["invited"] += 1
                try:
                    bot.send_message(int(ref_user), "🎉 You earned $0.2 from referral!")
                except:
                    pass

        save_user(str(uid))

    check_membership(uid)

@bot.message_handler(commands=['view'])
def view_cmd(message):
    try:
        bot.send_message(
            message.chat.id,
            "🤖 BOT INFO\n\n"
            "📌 Name: Video Downloader Bot\n"
            "⚡ Features:\n"
            "• TikTok, Instagram, Facebook, Pinterest, YouTube, Snapchat, X/Twitter support\n"
            "• Referral system\n"
            "• Withdrawal system\n"
            "• Bot Builder System"
        )
    except:
        pass

@bot.message_handler(commands=['balance'])
def balance_cmd(m):
    uid = str(m.from_user.id)
    bal = users.get(uid, {}).get("balance", 0)
    try:
        bot.send_message(m.chat.id, f"💰 Your balance: ${bal:.2f}")
    except:
        pass

@bot.message_handler(commands=['refer'])
@bot.message_handler(func=lambda m: m.text == "👥 REFERRAL")
def refer_cmd(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    uid = str(m.from_user.id)
    try:
        bot_username = bot.get_me().username
        ref = users[uid]['ref']
        link = f"https://t.me/{bot_username}?start={ref}"
        invited = users[uid].get("invited", 0)
        
        promo = (
            "🚀 Download videos instantly with DownloadVedioYTBot!\n\n"
            "Supports:\n"
            "🎬 TikTok | ▶️ YouTube | 📘 Facebook | 📸 Instagram | 👻 Snapchat | 📌 Pinterest | 🐦 X / Twitter\n\n"
            "⚡ Fast downloads\n"
            "🎵 Video to MP3\n"
            "💎 Premium features\n"
            "🔥 Easy & free to use\n\n"
            f"{link}"
        )
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📤 Share", switch_inline_query=promo))
        
        bot.send_message(
            m.chat.id,
            f"🔗 Your Referral Link:\n{link}\n\n"
            f"👥 Invited Users: {invited}\n"
            f"🎁 You earn $0.2 per referral!",
            reply_markup=kb
        )
    except:
        pass

@bot.message_handler(commands=['ping'])
def ping_cmd(m):
    start = time.time()
    try:
        msg = bot.send_message(m.chat.id, "🏓 Pinging...")
        end = time.time()
        speed = round((end - start) * 1000)
        status = "🟢 Online" if speed < 1000 else "🟡 Slow"
        bot.edit_message_text(
            f"🏓 <b>PONG!</b>\n\n"
            f"⚡ Speed: {speed} ms\n"
            f"📡 Status: {status}",
            m.chat.id,
            msg.message_id,
            parse_mode="HTML"
        )
    except:
        pass

# ================= VERIFY BOT START =================
if bot2:
    @bot2.message_handler(commands=['start'])
    def verify_start(message):
        args = message.text.split()
        if len(args) > 1:
            code = args[1]
            try:
                bot2.send_message(
                    message.chat.id,
                    f"🔑 <b>Your Verification Code</b>\n\n"
                    f"<code>{code}</code>\n\n"
                    "Copy this code and send it to the downloader bot."
                )
            except:
                pass
        else:
            kb = InlineKeyboardMarkup()
            kb.add(
                InlineKeyboardButton(
                    "GET",
                    url="https://t.me/Downloadvedioytibot"
                )
            )
            try:
                bot2.send_message(
                    message.chat.id,
                    "❌ <b>Don't Have Code?</b>\n\nGet code from downloader bot.",
                    reply_markup=kb
                )
            except:
                pass

# ================= CHECK MEMBERSHIP =================
def check_membership(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["member", "administrator", "creator"]:
            bot.send_message(
                user_id,
                """🎬 Welcome to Video Downloader Bot!

This bot helps you easily download videos and music from many popular platforms directly to Telegram.

📥 How to use the bot:
1. Copy the video link from any supported platform.
2. Send the link here in the bot.
3. The bot will automatically download the video for you.

👇 Send any video link to begin downloading.""",
                reply_markup=user_menu(is_admin(user_id))
            )
        else:
            send_join_message(user_id)
    except:
        send_join_message(user_id)

def send_join_message(user_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ JOIN CHANNEL", url="https://t.me/tiktokvediodownload"))
    kb.add(InlineKeyboardButton("✅ CONFIRM", callback_data="confirm_join"))
    try:
        bot.send_message(
            user_id,
            "⚠️ You must join our channel to use this bot.",
            reply_markup=kb
        )
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "verify_dm")
def verify_dm(call):
    uid = call.from_user.id
    if uid not in verify_pending:
        return
    code = verify_pending[uid]["code"]
    try:
        loop = asyncio.get_event_loop()
        success = loop.run_until_complete(send_code_telegram(uid, code))
    except:
        success = False

    if success:
        try:
            bot.answer_callback_query(call.id, "Code sent")
            bot.send_message(call.message.chat.id, "📩 Code sent to your Telegram DM.\n\nSend the code here.")
        except:
            pass
    else:
        try:
            bot.send_message(call.message.chat.id, "❌ Cannot send DM.\nUser must message your Telegram account first.")
        except:
            pass

def send_gmail_code(email, code):
    subject = "Telegram Bot Verification Code"
    body = f"Your verification code is:\n\n{code}"
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = email
    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(GMAIL_USER, GMAIL_PASS)
        server.sendmail(GMAIL_USER, email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print("EMAIL ERROR:", e)
        return False

def process_email(message):
    uid = message.from_user.id
    email = message.text.strip()
    code = str(random.randint(10000, 99999))
    verify_pending[uid] = {"code": code}
    success = send_gmail_code(email, code)
    try:
        if success:
            bot.send_message(message.chat.id, "📩 Code sent to your Gmail.\nSend the code here.")
        else:
            bot.send_message(message.chat.id, "❌ Failed to send email.")
    except:
        pass

def send_multi_join(user_id):
    kb = InlineKeyboardMarkup(row_width=3)
    buttons = [InlineKeyboardButton("➕️ JOIN", url=f"https://t.me/{ch}") for ch in POST_CHANNELS]
    kb.add(*buttons)
    kb.add(InlineKeyboardButton("✅ CONFIRM", callback_data="multi_checkjoin"))
    try:
        bot.send_message(user_id, "⚠️ Join all channels to continue.", reply_markup=kb)
    except:
        pass

async def send_code_telegram(user_id, code):
    if not tg_client:
        return False
    try:
        user = await tg_client.get_entity(user_id)
        await tg_client.send_message(user, f"🔐 Your verification code:\n\n{code}")
        return True
    except Exception as e:
        print("DM ERROR:", e)
        return False

@bot.callback_query_handler(func=lambda call: call.data == "via_telegram")
def via_telegram(call):
    uid = call.from_user.id
    if uid not in verify_pending:
        try:
            bot.answer_callback_query(call.id, "Verification expired")
        except:
            pass
        return
    code = verify_pending[uid]["code"]
    try:
        loop = asyncio.get_event_loop()
        success = loop.run_until_complete(send_code_telegram(uid, code))
    except:
        success = False

    try:
        if success:
            bot.send_message(call.message.chat.id, "✅ Code sent to your Telegram messages.\nSend the code here.")
        else:
            bot.send_message(call.message.chat.id, "⚠️ Telegram blocked sending message.\nUser must message your account first.")
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "verify_email")
def verify_email(call):
    try:
        msg = bot.send_message(call.message.chat.id, "📧 Send your Gmail address to receive verification code.")
        bot.register_next_step_handler(msg, process_email)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "confirm_join")
def confirm_join(call):
    user_id = call.from_user.id
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["member", "administrator", "creator"]:
            bot.answer_callback_query(call.id, "✅ Join verified")
            try:
                bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
            except:
                pass
            if user_id in pending_links:
                link = pending_links[user_id]
                del pending_links[user_id]
                msg = bot.send_message(user_id, "⏳ Processing...")
                if is_quick_access(user_id):
                    vip_executor.submit(download_media, bot, user_id, link, msg.message_id)
                else:
                    normal_executor.submit(download_media, bot, user_id, link, msg.message_id)
            else:
                bot.send_message(user_id, "✅ Join confirmed. Send your video link.")
        else:
            bot.answer_callback_query(call.id, "❌ You must join the channel first!", show_alert=True)
    except:
        bot.answer_callback_query(call.id, "❌ Please join the channel first!", show_alert=True)

@bot.message_handler(func=lambda m: m.text == "👑 ADMIN PANEL")
def open_admin_panel(m):
    if not is_admin(m.from_user.id):
        try:
            bot.send_message(m.chat.id, "❌ You are not admin")
        except:
            pass
        return
    try:
        bot.send_message(m.chat.id, "👑 Admin Panel", reply_markup=admin_menu())
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "💰 BALANCE")
def balance_handler(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    uid = str(m.from_user.id)
    bal = users.get(uid, {}).get("balance", 0.0)
    blocked = users.get(uid, {}).get("blocked", 0.0)
    try:
        bot.send_message(m.chat.id, f"💰 Available Balance: ${bal:.2f}\n⏳ Blocked Amount: ${blocked:.2f}")
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "🆔 GET ID")
def get_id_handler(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    uid = str(m.from_user.id)
    try:
        bot.send_message(m.chat.id, f"🆔 BOT ID: <code>{users[uid]['bot_id']}</code>\n👤 Telegram ID: <code>{uid}</code>")
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "☎️ CUSTOMER")
def customer_handler(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    try:
        bot.send_message(m.chat.id, "☎️ Customer Support:\n@scholes1")
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "🤖CUSTOMER AI")
def customer_ai_handler(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    try:
        bot.send_message(m.chat.id, "Ai Customer Support🤖:\n@Aidownoaderbot")
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "💸 WITHDRAWAL")
def withdraw_menu(m):
    if banned_guard(m):
        return
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("USDT-BEP20")
    kb.add("🔙 CANCEL")
    try:
        bot.send_message(m.chat.id, "Select withdrawal method:", reply_markup=kb)
    except:
        pass

@bot.message_handler(func=lambda m: m.text in ["USDT-BEP20", "🔙 CANCEL"])
def withdraw_method(m):
    if m.text == "🔙 CANCEL":
        back_to_main_menu(m)
        return
    if m.text == "USDT-BEP20":
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("🔙 CANCEL")
        try:
            msg = bot.send_message(m.chat.id, "Enter your USDT BEP20 address (must start with 0x)\nOr press 🔙 CANCEL", reply_markup=kb)
            bot.register_next_step_handler(msg, withdraw_address_step)
        except:
            pass

def withdraw_address_step(m):
    uid = str(m.from_user.id)
    text = (m.text or "").strip()
    if text == "🔙 CANCEL":
        back_to_main_menu(m)
        return
    if not text.startswith("0x"):
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("🔙 CANCEL")
        try:
            msg = bot.send_message(m.chat.id, "❌ Invalid address. Must start with 0x.\nTry again or press 🔙 CANCEL", reply_markup=kb)
            bot.register_next_step_handler(msg, withdraw_address_step)
        except:
            pass
        return
    users[uid]["temp_addr"] = text
    save_user(uid)
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🔙 CANCEL")
    try:
        msg = bot.send_message(m.chat.id, f"Enter withdrawal amount\nMinimum: $1\nBalance: ${users[uid]['balance']:.2f}\n\nOr press 🔙 CANCEL", reply_markup=kb)
        bot.register_next_step_handler(msg, withdraw_amount_step)
    except:
        pass

def withdraw_amount_step(m):
    uid = str(m.from_user.id)
    text = (m.text or "").strip()
    if text == "🔙 CANCEL":
        back_to_main_menu(m)
        return
    try:
        amt = float(text)
    except:
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("🔙 CANCEL")
        try:
            msg = bot.send_message(m.chat.id, "❌ Invalid number.\nEnter again or press 🔙 CANCEL", reply_markup=kb)
            bot.register_next_step_handler(msg, withdraw_amount_step)
        except:
            pass
        return

    if amt < 1:
        try:
            bot.send_message(m.chat.id, "❌ Minimum withdrawal is $1", reply_markup=user_menu(is_admin(uid)))
        except:
            pass
        return

    if amt > users[uid]["balance"]:
        try:
            bot.send_message(m.chat.id, "❌ Insufficient balance", reply_markup=user_menu(is_admin(uid)))
        except:
            pass
        return

    wid = random.randint(10000, 99999)
    users[uid]["balance"] -= amt
    users[uid]["blocked"] += amt

    withdrawal = {
        "id": wid,
        "user": uid,
        "amount": amt,
        "blocked": amt,
        "address": users[uid].get("temp_addr", "N/A"),
        "status": "pending",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    withdraws.append(withdrawal)
    save_user(uid)
    save_withdraws()

    try:
        bot.send_message(int(uid), f"✅ Withdrawal Request Sent\n🧾 Request ID: {wid}\n💵 Amount: ${amt:.2f}\n🏦 Address: {withdrawal['address']}\n💰 Balance Left: ${users[uid]['balance']:.2f}\n⏳ Status: Pending")
    except:
        pass

    admin_text = f"💳 NEW WITHDRAWAL\n\n👤 User: {uid}\n🤖 BOT ID: {users[uid]['bot_id']}\n👥 Referrals: {users[uid]['invited']}\n💵 Amount: ${amt:.2f}\n🧾 Request ID: {wid}\n🏦 Address: {withdrawal['address']}\n⏳ Status: Pending"
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✅ CONFIRM", callback_data=f"confirm_{wid}"),
        InlineKeyboardButton("❌ REJECT", callback_data=f"reject_{wid}"),
        InlineKeyboardButton("🚫 BAN USER", callback_data=f"ban_{uid}"),
        InlineKeyboardButton("💰 BAN MONEY", callback_data=f"block_{wid}")
    )

    for admin in ADMIN_IDS:
        try:
            bot.send_message(admin, admin_text, reply_markup=markup)
        except:
            pass

@bot.callback_query_handler(func=lambda call: call.data.startswith(("confirm_", "reject_", "ban_", "block_")))
def admin_callbacks(call):
    if not is_admin(call.from_user.id):
        try:
            bot.answer_callback_query(call.id, "❌ You are not admin")
        except:
            pass
        return

    data = call.data
    if data.startswith("confirm_"):
        wid = int(data.split("_")[1])
        w = next((x for x in withdraws if x["id"] == wid), None)
        if not w or w["status"] != "pending":
            return
        w["status"] = "paid"
        users[w["user"]]["blocked"] -= w["blocked"]
        save_user(w["user"])
        save_withdraws()
        try:
            bot.answer_callback_query(call.id, "✅ Confirmed")
            bot.send_message(int(w["user"]), f"✅ Withdrawal #{wid} approved!")
        except:
            pass

    elif data.startswith("reject_"):
        wid = int(data.split("_")[1])
        w = next((x for x in withdraws if x["id"] == wid), None)
        if not w or w["status"] != "pending":
            return
        w["status"] = "rejected"
        users[w["user"]]["balance"] += w["blocked"]
        users[w["user"]]["blocked"] -= w["blocked"]
        save_user(w["user"])
        save_withdraws()
        try:
            bot.answer_callback_query(call.id, "❌ Rejected")
            bot.send_message(int(w["user"]), f"❌ Withdrawal #{wid} rejected")
        except:
            pass

    elif data.startswith("ban_"):
        uid = data.split("_")[1]
        if uid in users:
            users[uid]["banned"] = True
            save_user(uid)
            try:
                bot.answer_callback_query(call.id, "🚫 User banned")
                bot.send_message(int(uid), "🚫 You have been banned by admin.")
            except:
                pass

    elif data.startswith("block_"):
        wid = int(data.split("_")[1])
        w = next((x for x in withdraws if x["id"] == wid), None)
        if not w or w["status"] != "pending":
            return
        uid = w["user"]
        amt = w["blocked"]
        w["status"] = "blocked"
        code = str(random.randint(1000, 9999))
        w["block_code"] = code
        users[uid]["blocked"] -= amt
        save_user(uid)
        save_withdraws()
        try:
            bot.answer_callback_query(call.id, "💰 Money Blocked")
            bot.send_message(int(uid), f"🚫 Your withdrawal of ${amt:.2f} is BLOCKED.\n🔢 Block Code: {code}\nContact admin to unlock.")
        except:
            pass

@bot.message_handler(func=lambda m: m.text == "💰 UNBLOCK MONEY")
def unblock_money_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "🔢 Send 4-digit Block Code to UNBLOCK funds:")
        bot.register_next_step_handler(msg, unblock_money_process)
    except:
        pass

def unblock_money_process(m):
    if not is_admin(m.from_user.id):
        return
    code = (m.text or "").strip()
    w = next((x for x in withdraws if x.get("block_code") == code), None)
    if not w:
        try:
            bot.send_message(m.chat.id, "❌ Invalid Block Code")
        except:
            pass
        return

    uid = w["user"]
    amt = w["blocked"]
    users[uid]["balance"] += amt
    w["status"] = "unblocked"
    w.pop("block_code", None)
    save_user(uid)
    save_withdraws()

    try:
        bot.send_message(int(uid), f"✅ Your blocked ${amt:.2f} is now available in balance!")
        bot.send_message(m.chat.id, f"✅ Money unblocked for user {uid}")
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "🔥 UN BAN-USER")
def unban_user_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send Telegram ID of user to UNBAN:")
        bot.register_next_step_handler(msg, unban_user_process)
    except:
        pass

def unban_user_process(m):
    if not is_admin(m.from_user.id):
        return
    uid = (m.text or "").strip()
    if uid not in users:
        try:
            bot.send_message(m.chat.id, "❌ User not found")
        except:
            pass
        return
    users[uid]["banned"] = False
    save_user(uid)
    try:
        bot.send_message(m.chat.id, f"✅ User {uid} unbanned")
        bot.send_message(int(uid), "✅ You have been unbanned by admin.")
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "💳 WITHDRAWAL CHECK")
def withdrawal_check_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Enter Withdrawal Request ID:")
        bot.register_next_step_handler(msg, withdrawal_check_process)
    except:
        pass

def withdrawal_check_process(m):
    if not is_admin(m.from_user.id):
        return
    try:
        wid = int(m.text.strip())
    except:
        try:
            bot.send_message(m.chat.id, "❌ Invalid Request ID")
        except:
            pass
        return

    w = next((x for x in withdraws if x["id"] == wid), None)
    if not w:
        try:
            bot.send_message(m.chat.id, "❌ Request not found")
        except:
            pass
        return

    uid = w["user"]
    bot_id = users.get(uid, {}).get("bot_id", "Unknown")
    invited = users.get(uid, {}).get("invited", 0)

    msg_text = f"💳 WITHDRAWAL DETAILS\n\n🧾 Request ID: {w['id']}\n👤 User ID: {uid}\n🤖 BOT ID: {bot_id}\n👥 Referrals: {invited}\n💵 Amount: ${w['amount']:.2f}\n🏦 Address: {w['address']}\n📊 Status: {w['status'].upper()}\n⏰ Time: {w['time']}"
    try:
        bot.send_message(m.chat.id, msg_text)
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "📊 STATS")
def stats_handler(m):
    if not is_admin(m.from_user.id):
        return
    total_users = len(users)
    total_balance = sum(u.get("balance", 0.0) for u in users.values())
    total_blocked = sum(u.get("blocked", 0.0) for u in users.values())
    total_withdraws = len(withdraws)
    pending_withdraws = len([w for w in withdraws if w["status"] == "pending"])
    msg = f"📊 BOT STATS\n\n👥 Total Users: {total_users}\n💰 Total Balance: ${total_balance:.2f}\n⏳ Total Blocked: ${total_blocked:.2f}\n🧾 Total Withdrawals: {total_withdraws}\n⏳ Pending Withdrawals: {pending_withdraws}"
    try:
        bot.send_message(m.chat.id, msg)
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "🚫 BAN USER MANUAL")
def manual_ban_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send Telegram ID or BOT ID to BAN user:")
        bot.register_next_step_handler(msg, manual_ban_process)
    except:
        pass

def manual_ban_process(m):
    if not is_admin(m.from_user.id):
        return
    uid_input = (m.text or "").strip()
    uid = uid_input if uid_input in users else find_user_by_botid(uid_input)
    if not uid:
        try:
            bot.send_message(m.chat.id, "❌ User not found")
        except:
            pass
        return
    users[uid]["banned"] = True
    save_user(uid)
    try:
        bot.send_message(m.chat.id, f"🚫 User {uid} banned")
        bot.send_message(int(uid), "🚫 You have been banned by admin.")
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "📡 ADD CHANNEL")
def add_channel_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send channel username\nExample:\n@mychannel")
        bot.register_next_step_handler(msg, add_channel_process)
    except:
        pass

def add_channel_process(m):
    username = m.text.strip()
    try:
        member = bot.get_chat_member(username, bot.get_me().id)
        if member.status not in ["administrator", "creator"]:
            bot.send_message(m.chat.id, "❌ Bot is not admin in this channel")
            return
        if username not in MANAGED_CHANNELS:
            MANAGED_CHANNELS.append(username)
        bot.send_message(m.chat.id, f"✅ Channel Added\n{username}")
    except:
        try:
            bot.send_message(m.chat.id, "❌ Invalid channel or bot not inside channel")
        except:
            pass

# ================= EXACT RAADI LAYOUT =================
@bot.message_handler(func=lambda m: m.text == "🔍 RAADI")
def raadi_stats(m):
    if not is_admin(m.from_user.id):
        return
    total_videos = videos_data.get("total", 0)
    platform_stats = videos_data.get("platforms", {})
    users_stats = videos_data.get("users", {})

    top_downloader = "None"
    sorted_users = []
    if users_stats:
        sorted_users = sorted(users_stats.items(), key=lambda x: x[1], reverse=True)
        top_uid, top_cnt = sorted_users[0]
        top_downloader = f'<a href="tg://user?id={top_uid}">{top_uid}</a> ({top_cnt} videos)'

    tt = platform_stats.get("tiktok", 0)
    yt = platform_stats.get("youtube", 0)
    fb = platform_stats.get("facebook", 0)
    pin = platform_stats.get("pinterest", 0)
    ig = platform_stats.get("instagram", 0)
    snap = platform_stats.get("snapchat", 0)
    tw = platform_stats.get("twitter", 0)

    msg_lines = [
        "🔍 DOWNLOAD ANALYTICS\n",
        f"🎬 Total Videos Downloaded: {total_videos}",
        f"🏆 Top Downloader: {top_downloader}\n",
        "📊 Downloads by Platform:",
        f"• TikTok: {tt}",
        f"• YouTube: {yt}",
        f"• Facebook: {fb}",
        f"• Instagram: {ig}",
        f"• Pinterest: {pin}",
        f"• Snapchat: {snap}",
        f"• X/Twitter: {tw}\n",
        "🥇 Top 40 Users:"
    ]

    for i, (uid, count) in enumerate(sorted_users[:40], start=1):
        bot_id = users.get(str(uid), {}).get("bot_id", "N/A")
        msg_lines.append(f'{i}. 👤 <a href="tg://user?id={uid}">{uid}</a> - 🎬 {count} videos | 🤖 BOT ID: {bot_id}')

    try:
        bot.send_message(m.chat.id, "\n".join(msg_lines), parse_mode="HTML")
    except Exception as e:
        print(f"RAADI error: {e}")

@bot.message_handler(func=lambda m: m.text == "📢 BROADCAST")
def broadcast_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "📝 Send the broadcast message to all users:")
        bot.register_next_step_handler(msg, broadcast_send)
    except:
        pass

def broadcast_send(m):
    if not is_admin(m.from_user.id):
        return
    text = m.text
    count = 0
    for uid in users:
        try:
            bot.send_message(int(uid), text)
            count += 1
            time.sleep(0.05)
        except:
            continue
    try:
        bot.send_message(m.chat.id, f"✅ Broadcast sent to {count} users")
    except:
        pass

# ================= BROADCAST MEDIA =================
@bot.message_handler(func=lambda m: m.text == "📢 BROADCAST MEDIA")
def broadcast_media_start(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "Send the Video or Photo with caption (or without):")
    bot.register_next_step_handler(msg, broadcast_media_process)

def broadcast_media_process(m):
    if not is_admin(m.from_user.id):
        return

    if not (m.video or m.photo):
        bot.send_message(m.chat.id, "❌ Please send a valid Video or Photo.")
        return

    count = 0
    file_id = m.video.file_id if m.video else m.photo[-1].file_id
    caption = m.caption or ""

    for uid in users:
        try:
            if m.video:
                bot.send_video(int(uid), file_id, caption=caption)
            else:
                bot.send_photo(int(uid), file_id, caption=caption)
            count += 1
            time.sleep(0.05)
        except:
            continue

    bot.send_message(m.chat.id, f"✅ Media broadcast sent to {count} users.")

# ================= SEND PAY (TELEGRAM STARS) =================
@bot.message_handler(func=lambda m: m.text == "SEND PAY")
def send_pay_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send payment details in this format:\n\nTitle | Description | Price in Stars\n\nExample:\nVIP Access | 1 Month VIP Subscription | 50")
        bot.register_next_step_handler(msg, send_pay_process)
    except:
        pass

def send_pay_process(m):
    if not is_admin(m.from_user.id):
        return
    try:
        parts = m.text.split("|")
        if len(parts) != 3:
            bot.send_message(m.chat.id, "❌ Invalid format. Use: Title | Description | Price")
            return
        
        title = parts[0].strip()
        desc = parts[1].strip()
        price = int(parts[2].strip())
        
        prices = [LabeledPrice(label=title, amount=price)]
        count = 0
        
        for uid in users:
            try:
                bot.send_invoice(
                    int(uid),
                    title=title,
                    description=desc,
                    invoice_payload=f"stars_pay_{price}",
                    provider_token="",
                    currency="XTR",
                    prices=prices
                )
                count += 1
                time.sleep(0.05)
            except Exception as e:
                continue

        bot.send_message(m.chat.id, f"✅ Telegram Stars payment sent to {count} users.")
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Error processing payment: {e}")

@bot.message_handler(func=lambda m: m.text == "📌 POST CHANNEL")
def post_channel_start(m):
    global CHANNEL_WINDOW_OPEN
    if not is_admin(m.from_user.id):
        return
    CHANNEL_WINDOW_OPEN = True
    POST_CHANNELS.clear()
    try:
        msg = bot.send_message(m.chat.id, "Send channel usernames\nExample:\n@channel1\n\nMax 10 channels. Send DONE when finished.")
        bot.register_next_step_handler(msg, post_channel_add)
    except:
        pass

def post_channel_add(m):
    if m.text.lower() == "done":
        try:
            bot.send_message(m.chat.id, f"✅ {len(POST_CHANNELS)} channels added.")
        except:
            pass
        return
    if len(POST_CHANNELS) >= MAX_CHANNELS:
        try:
            bot.send_message(m.chat.id, "⚠️ Maximum 10 channels allowed.")
        except:
            pass
        return
    username = m.text.replace("@", "").strip()
    POST_CHANNELS.append(username)
    try:
        msg = bot.send_message(m.chat.id, f"Channel @{username} added\nTotal: {len(POST_CHANNELS)}\nSend another or DONE")
        bot.register_next_step_handler(msg, post_channel_add)
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "CLOSE CHANNEL POST")
def close_channel_post(m):
    if not is_admin(m.from_user.id):
        return
    MANAGED_CHANNELS.clear()
    try:
        bot.send_message(m.chat.id, "❌ All channels removed.")
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "👥 SEE LIST")
def see_users(m):
    if not is_admin(m.from_user.id):
        return
    total = len(users)
    count = 0
    for uid in users:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("💬 OPEN CHAT", url=f"tg://user?id={uid}"))
        qa_status = "⚡ Quick Access: YES" if users[str(uid)].get("quick_access") else "Quick Access: NO"
        try:
            bot.send_message(m.chat.id, f"👤 User ID: {uid} | {qa_status}", reply_markup=kb)
        except:
            pass
        count += 1
        if count >= 20:
            break
    try:
        bot.send_message(m.chat.id, f"📊 Total Users: {total}")
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "🔒 LOCK BOT")
def lock_bot_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "✍️ Send the lock message users should receive.")
        bot.register_next_step_handler(msg, lock_bot_process)
    except:
        pass

def lock_bot_process(m):
    global BOT_LOCKED, LOCK_MESSAGE
    if not is_admin(m.from_user.id):
        return
    text = (m.text or "").strip()
    if text:
        LOCK_MESSAGE = text
    BOT_LOCKED = True
    try:
        bot.send_message(m.chat.id, "🔒 Bot locked successfully.")
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "🔓 UNLOCK BOT")
def unlock_bot(m):
    global BOT_LOCKED
    if not is_admin(m.from_user.id):
        return
    BOT_LOCKED = False
    try:
        bot.send_message(m.chat.id, "🔓 Bot unlocked successfully.")
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "📢 ADD ADS")
def add_ads_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "✍️ Format:\n`Button Name | Link | Description`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_add_ads)
    except:
        pass

def process_add_ads(m):
    global ADS_ENABLED, ADS_BTN_TEXT, ADS_URL, ADS_TEXT
    if not is_admin(m.from_user.id):
        return
    parts = [p.strip() for p in (m.text or "").split("|")]
    if len(parts) < 2:
        try:
            bot.send_message(m.chat.id, "❌ Invalid format. Please use: Button Name | Link | Description")
        except:
            pass
        return
        
    ADS_BTN_TEXT = parts[0]
    ADS_URL = parts[1]
    if len(parts) > 2:
        ADS_TEXT = parts[2]
    else:
        ADS_TEXT = ""
        
    ADS_ENABLED = True
    try:
        bot.send_message(m.chat.id, "✅ Ads enabled successfully!")
    except:
        pass

# ================= MAIN BOT DOWNLOAD HANDLER =================
@bot.message_handler(func=lambda m: m.text and "http" in m.text)
def handle_main_bot_links(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
        
    uid = str(m.from_user.id)
    link = m.text.strip()
    
    # Increment Stats
    videos_data["total"] += 1
    videos_col.update_one({"_id": "stats"}, {"$inc": {"total": 1}}, upsert=True)
    
    try:
        msg = bot.send_message(m.chat.id, "⏳ Processing your link...")
        if is_quick_access(uid):
            vip_executor.submit(download_media, bot, m.chat.id, link, msg.message_id)
        else:
            normal_executor.submit(download_media, bot, m.chat.id, link, msg.message_id)
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Failed to process link.")

# ================= RUN MULTIPLE BOTS =================
if __name__ == "__main__":
    # Start any active Managed Bots from database
    load_and_start_mbots()
    
    # Start Main Bot
    if bot:
        print("✅ Starting Main Bot Engine...")
        try:
            bot.infinity_polling(skip_pending=True)
        except Exception as e:
            print(f"❌ Main Bot Engine Error: {e}")
