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

MAX_YOUTUBE_DURATION = int(os.getenv("MAX_YOUTUBE_DURATION", "900"))  # 15 Minutes in seconds
MAX_CONCURRENT_DOWNLOADS = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "20"))

# Dual executors for Priority (Quick Access) & Normal
vip_executor = ThreadPoolExecutor(max_workers=5)
normal_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_DOWNLOADS)

http_session = requests.Session()

tg_client = TelegramClient(
    "session",
    API_ID,
    API_HASH
)

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
bot2 = telebot.TeleBot(BOT2_TOKEN, parse_mode="HTML")

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
    print("✅ MongoDB 2 (Videos, Stats & Feedback) Connected Successfully")
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
    if show_admin:
        kb.add("👑 ADMIN PANEL")
    return kb

def admin_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📊 STATS", "📢 BROADCAST")
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
    kb.add("🗑️ Reset All Feedbacks", "🔓 OPEN 30 MIN")
    kb.add("🔙 BACK MAIN MENU")
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

# ================= YOUTUBE 30 MIN ADMIN CONTROL =================
@bot.message_handler(func=lambda m: m.text == "🔓 OPEN 30 MIN")
def open_30_min_start(m):
    if not is_admin(m.from_user.id): return
    try:
        msg = bot.send_message(m.chat.id, "Send User ID or BOT ID to grant 30-min YouTube access:")
        bot.register_next_step_handler(msg, open_30_min_process)
    except: pass

def open_30_min_process(m):
    if not is_admin(m.from_user.id): return
    uid_str = (m.text or "").strip()
    uid = uid_str if uid_str in users else find_user_by_botid(uid_str)
    
    if not uid or uid not in users:
        try: bot.send_message(m.chat.id, "❌ User not found.")
        except: pass
        return
        
    users[uid]["youtube_30m"] = True
    save_user(uid)
    try: 
        bot.send_message(m.chat.id, f"✅ User {uid} can now download YouTube videos up to 30 minutes.")
        bot.send_message(int(uid), "🎉 Congratulations! You have been granted special access to download YouTube videos up to 30 minutes long!")
    except: pass

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
            "youtube_30m": False,
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
            "• Withdrawal system"
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
                    vip_executor.submit(download_media, user_id, link, msg.message_id)
                else:
                    normal_executor.submit(download_media, user_id, link, msg.message_id)
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
        msg = bot.send_message(m.chat.id, "✍️ Format:\n`Button Name | Link | Qoraal yar`", parse_mode="Markdown")
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
            bot.send_message(m.chat.id, "❌ Format error.")
        except:
            pass
        return
    ADS_BTN_TEXT = parts[0]
    ADS_URL = parts[1]
    ADS_TEXT = parts[2] if len(parts) > 2 else "✨ Nagala soco baraha bulshada!"
    ADS_ENABLED = True
    try:
        bot.send_message(m.chat.id, "✅ Ads saved and enabled!")
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "🗑 DELETE ADS")
def delete_ads(m):
    global ADS_ENABLED, ADS_BTN_TEXT, ADS_URL, ADS_TEXT
    if not is_admin(m.from_user.id):
        return
    ADS_ENABLED = False
    ADS_BTN_TEXT = ""
    ADS_URL = ""
    ADS_TEXT = ""
    try:
        bot.send_message(m.chat.id, "🗑 Ads deleted.")
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "📥 IMPORT USERS")
def import_users_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send Telegram IDs separated by spaces or new lines.")
        bot.register_next_step_handler(msg, import_users_process)
    except:
        pass

def import_users_process(m):
    if not is_admin(m.from_user.id):
        return
    ids = (m.text or "").replace("\n", " ").split()
    added = 0
    for uid in ids:
        uid = uid.strip()
        if uid.isdigit() and uid not in users:
            users[uid] = {
                "balance": 0.0,
                "blocked": 0.0,
                "ref": random_ref(),
                "bot_id": random_botid(),
                "invited": 0,
                "banned": False,
                "verified": False,
                "quick_access": False,
                "youtube_30m": False,
                "month": now_month()
            }
            save_user(uid)
            added += 1
    try:
        bot.send_message(m.chat.id, f"✅ Imported {added} users successfully.")
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "🔗 GET REFERRAL CODE")
def get_ref_code_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send user username (e.g. @username):")
        bot.register_next_step_handler(msg, get_ref_username)
    except:
        pass

def get_ref_username(m):
    if not is_admin(m.from_user.id):
        return
    username = m.text.replace("@", "").strip()
    try:
        msg = bot.send_message(m.chat.id, f"User: @{username}\nNow send referral code number:")
        bot.register_next_step_handler(msg, lambda x: save_custom_ref_code(x, username))
    except:
        pass

def save_custom_ref_code(m, username):
    if not is_admin(m.from_user.id):
        return
    code = m.text.strip()
    if not code.isdigit():
        try:
            bot.send_message(m.chat.id, "❌ Code must be a number")
        except:
            pass
        return
    user_id = next((uid for uid, data in users.items() if data.get("username", "").lower() == username.lower()), None)
    if not user_id:
        try:
            bot.send_message(m.chat.id, "❌ User not found")
        except:
            pass
        return
    users[user_id]["ref"] = code
    save_user(user_id)
    try:
        bot.send_message(m.chat.id, f"✅ Referral code updated for @{username}")
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "🔎 SEARCH USER")
def search_user(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send User Telegram ID")
        bot.register_next_step_handler(msg, search_user_result)
    except:
        pass

def search_user_result(m):
    if not is_admin(m.from_user.id):
        return
    uid = m.text.strip()
    if uid in users:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("💬 OPEN CHAT", url=f"tg://user?id={uid}"))
        kb.add(InlineKeyboardButton("✉️ MESSAGE USER", callback_data=f"msguser|{uid}"))
        try:
            bot.send_message(m.chat.id, f"👤 User Found\nID: {uid}", reply_markup=kb)
        except:
            pass
    else:
        try:
            bot.send_message(m.chat.id, "❌ User not found")
        except:
            pass

@bot.message_handler(func=lambda m: m.text and "http" in m.text)
def handle_links(message):
    if bot_locked_guard(message) or banned_guard(message):
        return

    user_id = message.from_user.id
    link = extract_url(message.text)

    if not link:
        return

    if CHANNEL_WINDOW_OPEN and POST_CHANNELS:
        joined_all = True
        for ch in POST_CHANNELS:
            try:
                member = bot.get_chat_member(f"@{ch}", user_id)
                if member.status not in ["member", "administrator", "creator"]:
                    joined_all = False
                    break
            except:
                joined_all = False
                break
        if not joined_all:
            pending_links[user_id] = link
            send_multi_join(user_id)
            return

    if VERIFY_ENABLED and not users.get(str(user_id), {}).get("verified", False):
        code = str(random.randint(10000, 99999))
        verify_pending[user_id] = {"code": code, "link": link}
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📩 Verify via DM", callback_data="via_telegram"))
        kb.add(InlineKeyboardButton("🤖 Verify via Bot", url=f"https://t.me/Verifyd_bot?start={code}"))
        kb.add(InlineKeyboardButton("📧 Verify via Gmail", callback_data="verify_email"))
        try:
            bot.send_message(message.chat.id, "🔐 Verification Required\n\nChoose verification method:", reply_markup=kb)
        except:
            pass
        return

    try:
        msg = bot.send_message(message.chat.id, "⚡ Processing...")
        if is_quick_access(user_id):
            vip_executor.submit(download_media, message.chat.id, link, msg.message_id)
        else:
            normal_executor.submit(download_media, message.chat.id, link, msg.message_id)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "multi_checkjoin")
def multi_checkjoin(call):
    user_id = call.from_user.id
    joined_all = True
    for ch in POST_CHANNELS:
        try:
            member = bot.get_chat_member(f"@{ch}", user_id)
            if member.status not in ["member", "administrator", "creator"]:
                joined_all = False
                break
        except:
            joined_all = False
            break

    if joined_all:
        try:
            bot.answer_callback_query(call.id, "✅ Join verified")
        except:
            pass
        if user_id in pending_links:
            link = pending_links[user_id]
            del pending_links[user_id]
            try:
                msg = bot.send_message(user_id, "⬇️ Processing your video...")
                if is_quick_access(user_id):
                    vip_executor.submit(download_media, user_id, link, msg.message_id)
                else:
                    normal_executor.submit(download_media, user_id, link, msg.message_id)
            except:
                pass
        else:
            try:
                bot.send_message(user_id, "Send your video link.")
            except:
                pass
    else:
        try:
            bot.answer_callback_query(call.id, "❌ You must join all channels first!", show_alert=True)
        except:
            pass

@bot.message_handler(func=lambda m: m.text == "❌ CLOSE WINDOWS")
def close_channel_windows(m):
    global CHANNEL_WINDOW_OPEN
    if not is_admin(m.from_user.id):
        return
    CHANNEL_WINDOW_OPEN = False
    try:
        bot.send_message(m.chat.id, "✅ Channel join system disabled.")
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "✅ VERIFY ON")
def verify_on(m):
    global VERIFY_ENABLED
    if not is_admin(m.from_user.id):
        return
    VERIFY_ENABLED = True
    try:
        bot.send_message(m.chat.id, "✅ Verify system enabled")
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "❌ VERIFY OFF")
def verify_off(m):
    global VERIFY_ENABLED
    if not is_admin(m.from_user.id):
        return
    VERIFY_ENABLED = False
    try:
        bot.send_message(m.chat.id, "❌ Verify system disabled")
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "CHANNEL POST")
def start_channel_post(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send the main text for the channel post.")
        bot.register_next_step_handler(msg, post_main_text)
    except:
        pass

def post_main_text(m):
    pending_post[m.from_user.id] = {"text": m.text, "buttons": []}
    try:
        msg = bot.send_message(m.chat.id, "Send button like:\n\nButton Name | Text when clicked\n\nSend DONE when finished.")
        bot.register_next_step_handler(msg, add_buttons)
    except:
        pass

def add_buttons(m):
    uid = m.from_user.id
    if m.text.lower() == "done":
        data = pending_post.get(uid)
        if not data:
            return
        kb = InlineKeyboardMarkup()
        for i, btn in enumerate(data["buttons"]):
            kb.add(InlineKeyboardButton(btn["name"], callback_data=f"postbtn_{i}"))
        for ch in MANAGED_CHANNELS:
            try:
                msg = bot.send_message(ch, data["text"], reply_markup=kb)
                channel_posts[msg.message_id] = data
            except:
                pass
        pending_post.pop(uid, None)
        try:
            bot.send_message(m.chat.id, "✅ Post sent")
        except:
            pass
        return

    try:
        name, content = m.text.split("|", 1)
        pending_post[uid]["buttons"].append({"name": name.strip(), "content": content.strip()})
        msg = bot.send_message(m.chat.id, "Button added. Send another or DONE")
        bot.register_next_step_handler(msg, add_buttons)
    except:
        try:
            msg = bot.send_message(m.chat.id, "❌ Format error\nButton Name | Text")
            bot.register_next_step_handler(msg, add_buttons)
        except:
            pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("postbtn_"))
def post_button_click(call):
    index = int(call.data.split("_")[1])
    data = channel_posts.get(call.message.message_id)
    if not data or index >= len(data["buttons"]):
        return
    text = data["buttons"][index]["content"]
    kb = InlineKeyboardMarkup()
    for i, btn in enumerate(data["buttons"]):
        kb.add(InlineKeyboardButton(btn["name"], callback_data=f"postbtn_{i}"))
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "➕ ADD BALANCE")
def add_balance_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send BOT ID or Telegram ID and amount:")
        bot.register_next_step_handler(msg, add_balance_process)
    except:
        pass

def add_balance_process(m):
    if not is_admin(m.from_user.id):
        return
    try:
        uid_str, amt_str = m.text.strip().split()
        amt = float(amt_str)
        uid = uid_str if uid_str in users else find_user_by_botid(uid_str)
        if not uid or amt <= 0:
            try:
                bot.send_message(m.chat.id, "❌ Invalid input")
            except:
                pass
            return
        users[uid]["balance"] += amt
        save_user(uid)
        try:
            bot.send_message(m.chat.id, f"✅ Added ${amt:.2f} to user {uid}")
            bot.send_message(int(uid), f"💰 Your balance increased by ${amt:.2f}")
        except:
            pass
    except:
        try:
            bot.send_message(m.chat.id, "❌ Format error.")
        except:
            pass

@bot.message_handler(func=lambda m: m.text == "➖ REMOVE MONEY")
def remove_balance_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send BOT ID or Telegram ID and amount:")
        bot.register_next_step_handler(msg, remove_balance_process)
    except:
        pass

def remove_balance_process(m):
    if not is_admin(m.from_user.id):
        return
    try:
        uid_str, amt_str = m.text.strip().split()
        amt = float(amt_str)
        uid = uid_str if uid_str in users else find_user_by_botid(uid_str)
        if not uid or amt <= 0:
            try:
                bot.send_message(m.chat.id, "❌ Invalid input")
            except:
                pass
            return
        if users[uid]["balance"] < amt:
            try:
                bot.send_message(m.chat.id, "❌ Insufficient balance")
            except:
                pass
            return
        users[uid]["balance"] -= amt
        save_user(uid)
        try:
            bot.send_message(m.chat.id, f"✅ Removed ${amt:.2f} from user {uid}")
            bot.send_message(int(uid), f"💸 ${amt:.2f} removed from your balance")
        except:
            pass
    except:
        try:
            bot.send_message(m.chat.id, "❌ Format error.")
        except:
            pass

CAPTION_TEXT = "Downloaded by:\n@Downloadvedioytibot"

@bot.message_handler(func=lambda m: m.text and m.text.isdigit())
def verify_code_check(m):
    uid = m.from_user.id
    if uid not in verify_pending:
        return
    data = verify_pending[uid]
    if m.text == data["code"]:
        users[str(uid)]["verified"] = True
        save_user(str(uid))
        link = data["link"]
        del verify_pending[uid]
        try:
            msg = bot.send_message(m.chat.id, "✅ Verification successful\n⬇️ Downloading video...")
            if is_quick_access(uid):
                vip_executor.submit(download_media, m.chat.id, link, msg.message_id)
            else:
                normal_executor.submit(download_media, m.chat.id, link, msg.message_id)
        except:
            pass
    else:
        try:
            bot.send_message(m.chat.id, "❌ Wrong verification code")
        except:
            pass

def extract_url(text):
    urls = re.findall(r'https?://[^\s]+', text)
    return urls[0] if urls else None

# ================= SEND VIDEO & PHOTOS (OPTIMIZED) =================
def send_video_with_music(chat_id, file_path, platform=None, message_id=None):
    if not os.path.exists(file_path):
        return

    try:
        bot.send_chat_action(chat_id, 'upload_video')
    except:
        pass

    vid_id = str(uuid.uuid4())[:8]
    perm_file_path = f"saved_{vid_id}.mp4"
    
    try:
        os.rename(file_path, perm_file_path)
    except:
        shutil.copy(file_path, perm_file_path)
        
    video_files[vid_id] = perm_file_path

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🎵 Convert Music", callback_data=f"music_{vid_id}"))
    if ADS_ENABLED and ADS_BTN_TEXT and ADS_URL:
        kb.add(InlineKeyboardButton(ADS_BTN_TEXT, url=ADS_URL))

    caption = CAPTION_TEXT
    if ADS_ENABLED and ADS_TEXT:
        caption += f"\n\n📢 {ADS_TEXT}"

    uid = str(chat_id)
    videos_data["total"] = videos_data.get("total", 0) + 1
    if "users" not in videos_data:
        videos_data["users"] = {}
    videos_data["users"][uid] = videos_data["users"].get(uid, 0) + 1

    if platform:
        if "platforms" not in videos_data:
            videos_data["platforms"] = {}
        videos_data["platforms"][platform] = videos_data["platforms"].get(platform, 0) + 1
    save_videos()

    try:
        with open(perm_file_path, "rb") as video:
            bot.send_video(chat_id, video, caption=caption, reply_markup=kb)

        if message_id:
            try:
                bot.delete_message(chat_id, message_id)
            except:
                pass
        
        if videos_data.get("feedback_enabled"):
            send_feedback_request(chat_id, platform or "other", vid_id)
            
    except Exception as e:
        print(f"Error sending video: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("music_"))
def extract_music(call):
    vid_id = call.data.split("_")[1]
    video_path = video_files.get(vid_id)
    
    if not video_path or not os.path.exists(video_path):
        bot.answer_callback_query(call.id, "❌ Audio expired.")
        return

    audio_path = f"audio_{vid_id}.mp3"
    
    try:
        bot.send_chat_action(call.message.chat.id, 'upload_audio')
        subprocess.run(['ffmpeg', '-i', video_path, '-q:a', '0', '-map', 'a', audio_path, '-y'], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        with open(audio_path, 'rb') as audio:
            bot.send_audio(call.message.chat.id, audio)
            
        os.remove(audio_path)
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Failed to convert music")

# ================= DOWNLOAD MEDIA =================
# ================= DOWNLOAD MEDIA =================
def download_media(chat_id, url, message_id):
    file_path = None

    try:
        os.makedirs("downloads", exist_ok=True)

        url = url.strip()

        # Detect platform
        if "youtube.com" in url or "youtu.be" in url:
            platform = "youtube"

        elif "pinterest.com" in url or "pin.it" in url:
            platform = "pinterest"

        elif "tiktok.com" in url:
            platform = "tiktok"

        elif "facebook.com" in url or "fb.watch" in url:
            platform = "facebook"

        elif "instagram.com" in url:
            platform = "instagram"

        elif "x.com" in url or "twitter.com" in url:
            platform = "twitter"

        elif "snapchat.com" in url:
            platform = "snapchat"

        else:
            platform = "other"

        print(f"[DOWNLOAD] Platform: {platform}")
        print(f"[DOWNLOAD] URL: {url}")

        # ================= YOUTUBE 10 MIN LIMIT =================
        if platform == "youtube":
            try:
                info_opts = {
                    "quiet": True,
                    "no_warnings": False,
                    "noplaylist": True,
                }

                with yt_dlp.YoutubeDL(info_opts) as ydl:
                    info = ydl.extract_info(
                        url,
                        download=False
                    )

                duration = info.get("duration") or 0

                print(
                    f"[YOUTUBE] Duration: "
                    f"{duration} seconds"
                )

                if duration > 600:
                    bot.edit_message_text(
                        "❌ YouTube videos must be 10 minutes or less.",
                        chat_id,
                        message_id
                    )
                    return

            except Exception as e:
                print(
                    f"[YOUTUBE INFO ERROR] "
                    f"{type(e).__name__}: {e}"
                )

                bot.edit_message_text(
                    "❌ YouTube could not be processed right now.",
                    chat_id,
                    message_id
                )
                return

        # ================= PINTEREST =================
        if "pin.it" in url:

            try:
                r = requests.head(url, allow_redirects=True, timeout=10)
                url = r.url
            except:
                pass


        if "pinterest.com" in url:

            try:

                ydl_opts = {
                    "format": "bv*+ba/b",
                    "outtmpl": "pinterest_%(id)s.%(ext)s",
                    "quiet": True,
                    "merge_output_format": "mp4"
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:

                    info = ydl.extract_info(url, download=True)

                    if "entries" in info:
                        entries = info["entries"]
                    else:
                        entries = [info]

                    for entry in entries:

                        file = ydl.prepare_filename(entry)

                        if file.lower().endswith((".jpg",".jpeg",".png",".webp")):

                            with open(file,"rb") as photo:
                                bot.send_photo(chat_id, photo, caption=CAPTION_TEXT)

                        else:

                            send_video_with_music(chat_id, file, "pinterest")

                return

            except Exception as e:

                bot.send_message(chat_id, f"❌ Download error:\n{e}")
                return

        # ================= YOUTUBE =================
        if "youtube.com" in url or "youtu.be" in url:

            try:

                ydl_opts = {
                    "format": "bestvideo+bestaudio/best",
                    "outtmpl": "youtube_%(id)s.%(ext)s",
                    "merge_output_format": "mp4",
                    "quiet": True
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:

                    info = ydl.extract_info(url, download=True)
                    file = ydl.prepare_filename(info)

                send_video_with_music(chat_id, file, "youtube")

                return

            except Exception as e:

                bot.send_message(chat_id, f"❌ YouTube download error:\n{e}")
                return


        bot.send_message(chat_id, "❌ Unsupported link")


    except Exception:

        bot.send_message(
            chat_id,
            "❌ Incorrect link.\n\n"
            "Send a valid link from TikTok, Snapchat, Pinterest, Facebook, or YouTube."
        )



        # ================= DOWNLOAD OPTIONS =================

        ydl_opts = {
            "format": (
                "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
                "best[ext=mp4]/best"
            ),

            "outtmpl": (
                "downloads/"
                "%(extractor)s_"
                "%(id)s.%(ext)s"
            ),

            "merge_output_format": "mp4",

            "noplaylist": True,

            "quiet": False,
            "no_warnings": False,

            "socket_timeout": 30,

            "retries": 5,
            "fragment_retries": 5,

            "continuedl": True,

            "http_headers": {
                "User-Agent":
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
            }
        }

        print("[DOWNLOAD] Starting yt-dlp...")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            info = ydl.extract_info(
                url,
                download=True
            )

            filename = ydl.prepare_filename(info)

            base = os.path.splitext(filename)[0]

            possible_files = [
                filename,
                base + ".mp4",
                base + ".mkv",
                base + ".webm",
                base + ".mov"
            ]

            file_path = None

            for path in possible_files:
                if os.path.exists(path):
                    file_path = path
                    break

        if not file_path:
            raise FileNotFoundError(
                "yt-dlp finished but output file was not found."
            )

        print(f"[DOWNLOAD] File: {file_path}")

        # ================= SEND =================

        send_video_with_music(
            chat_id,
            file_path,
            platform,
            message_id
        )

        print("[DOWNLOAD] Sent successfully.")

    except Exception as e:

        # IMPORTANT:
        # Don't hide the real error
        print(
            f"[DOWNLOAD ERROR] "
            f"{type(e).__name__}: {e}"
        )

        try:
            bot.edit_message_text(
                "❌ Download failed.\n\n"
                "The link could not be processed.",
                chat_id,
                message_id
            )
        except Exception:
            try:
                bot.send_message(
                    chat_id,
                    "❌ Download failed."
                )
            except Exception:
                pass

    finally:

        # Cleanup
        if file_path:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(
                        f"[CLEANUP] Deleted: {file_path}"
                    )
            except Exception as e:
                print(
                    f"[CLEANUP ERROR] {e}"
                )


# ================= RUN =================
if __name__ == "__main__":
    if not os.path.exists("downloads"):
        os.makedirs("downloads")

    print("🤖 Downloader Bot is running...")
    
    def run_bot1():
        bot.infinity_polling(timeout=20, long_polling_timeout=20)
        
    def run_bot2():
        bot2.infinity_polling(timeout=20, long_polling_timeout=20)

    t1 = threading.Thread(target=run_bot1)
    t2 = threading.Thread(target=run_bot2)
    
    t1.start()
    t2.start()
    
    t1.join()
    t2.join()
