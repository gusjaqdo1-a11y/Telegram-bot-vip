import telebot
from pymongo import MongoClient
import requests
from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, LabeledPrice
from telebot.apihelper import ApiTelegramException
import os, json, random
from datetime import datetime, timedelta
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
def user_menu(show_admin=False, uid=None):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💰 BALANCE", "💸 WITHDRAWAL")
    kb.add("👥 REFERRAL", "🆔 GET ID")
    kb.add("☎️ CUSTOMER", "🤖CUSTOMER AI")
    if uid is not None and can_create_bot(uid):
        kb.add("🤖 BOT BUILDER")
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
    kb.add("👥 Send Users To Create", "📢 Broadcast All Bots")
    kb.add("🤖 All Created Bots", "⚙️ Bot Creation Access")
    kb.add("🗑️ Reset All Feedbacks", "🔙 BACK MAIN MENU")
    return kb

def back_to_main_menu(m):
    uid = str(m.from_user.id)
    try:
        bot.send_message(
            m.chat.id,
            "🔙 Returning to main menu",
            reply_markup=user_menu(is_admin(uid), uid)
        )
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "🔙 BACK MAIN MENU")
def back_button_handler(m):
    back_to_main_menu(m)

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
                reply_markup=user_menu(is_admin(user_id), user_id)
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
            bot.send_message(m.chat.id, "❌ Minimum withdrawal is $1", reply_markup=user_menu(is_admin(uid), uid))
        except:
            pass
        return

    if amt > users[uid]["balance"]:
        try:
            bot.send_message(m.chat.id, "❌ Insufficient balance", reply_markup=user_menu(is_admin(uid), uid))
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
def send_video_with_music(chat_id, file_path, platform=None, message_id=None, bot_instance=None, bot_id=None):
    active_bot = bot_instance or bot

    if not os.path.exists(file_path):
        return

    try:
        active_bot.send_chat_action(chat_id, 'upload_video')
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
    if bot_id is None and ADS_ENABLED and ADS_BTN_TEXT and ADS_URL:
        kb.add(InlineKeyboardButton(ADS_BTN_TEXT, url=ADS_URL))

    caption = CAPTION_TEXT
    if bot_id is None and ADS_ENABLED and ADS_TEXT:
        caption += f"\n\n📢 {ADS_TEXT}"

    if bot_id:
        # Managed (created) bot - track stats separately, isolated per bot
        increment_bot_downloads(bot_id, platform)
        increment_bot_user_downloads(bot_id, chat_id)
    else:
        # Main bot - existing stats logic (unchanged)
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
            active_bot.send_video(chat_id, video, caption=caption, reply_markup=kb)

        if message_id:
            try:
                active_bot.delete_message(chat_id, message_id)
            except:
                pass
        
        if bot_id is None and videos_data.get("feedback_enabled"):
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
def download_media(chat_id, url, message_id, bot_instance=None, bot_id=None):
    active_bot = bot_instance or bot
    try:
        platform = "other"
        if "tiktok.com" in url:
            platform = "tiktok"
            api_url = f"https://www.tikwm.com/api/?url={url}"
            res = requests.get(api_url).json()
            if res.get("code") == 0:
                data = res["data"]
                if "images" in data:
                    images = data["images"]
                    media = [InputMediaPhoto(img) for img in images[:10]]
                    active_bot.send_media_group(chat_id, media)
                    if message_id:
                        active_bot.delete_message(chat_id, message_id)
                    return
                elif "play" in data:
                    vid_url = data["play"]
                    file_path = f"tiktok_{uuid.uuid4().hex[:8]}.mp4"
                    with open(file_path, 'wb') as f:
                        f.write(requests.get(vid_url).content)
                    send_video_with_music(chat_id, file_path, platform, message_id, bot_instance=active_bot, bot_id=bot_id)
                    return

        elif "youtube.com" in url or "youtu.be" in url:
            platform = "youtube"
            # Metadata check for duration up to 10 minutes
            ydl_info_opts = {"quiet": True, "no_warnings": True}
            with yt_dlp.YoutubeDL(ydl_info_opts) as ydl_meta:
                try:
                    info_meta = ydl_meta.extract_info(url, download=False)
                    duration = info_meta.get('duration', 0)
                    if duration and duration > MAX_YOUTUBE_DURATION:
                        active_bot.edit_message_text(f"❌ Sorry, video is too long ({int(duration/60)} mins). Maximum limit is {int(MAX_YOUTUBE_DURATION/60)} minutes.", chat_id, message_id)
                        return
                except Exception:
                    pass

        elif "facebook.com" in url or "fb.watch" in url:
            platform = "facebook"
        elif "instagram.com" in url:
            platform = "instagram"
        elif "pin.it" in url or "pinterest.com" in url:
            platform = "pinterest"
        elif "snapchat.com" in url:
            platform = "snapchat"
        elif "x.com" in url or "twitter.com" in url:
            platform = "twitter"

        ydl_opts = {
            "format": "b[ext=mp4]/best",
            "outtmpl": f"downloads/dl_%(id)s.%(ext)s",
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "socket_timeout": 15,
        }
                   
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if not filename.endswith('.mp4'):
                new_filename = filename.rsplit('.', 1)[0] + '.mp4'
                if os.path.exists(filename):
                    os.rename(filename, new_filename)
                filename = new_filename

            send_video_with_music(chat_id, filename, platform, message_id, bot_instance=active_bot, bot_id=bot_id)

    except Exception as e:
        print(f"Download Error: {e}")
        try:
            active_bot.edit_message_text("❌ Sorry, I couldn't download this media. Please make sure the link is public and try again.", chat_id, message_id)
        except:
            try:
                active_bot.send_message(chat_id, "❌ Sorry, I couldn't download this media. Please make sure the link is public and try again.")
            except:
                pass

# ================= BOT BUILDER SYSTEM (MULTI-BOT MANAGEMENT) =================
# NOTE ON "MANAGED BOTS": Telegram does not provide a public API that lets one
# bot programmatically create another bot and receive its token automatically.
# The only official way to create a bot is a human talking to @BotFather.
# This system therefore uses the real-world flow every legitimate "bot builder"
# service uses: the user creates the bot themselves via @BotFather, then pastes
# the resulting token here. We validate it (getMe), store it securely, and spin
# it up as an independent downloader bot instance reusing the shared engine above.

managed_bots_col = db1["managed_bots"]
bot_users_col = db1["bot_users"]
builder_settings_col = db1["bot_builder_settings"]

managed_bot_instances = {}   # bot_id -> telebot.TeleBot instance (in-memory, this process only)
managed_bot_threads = {}     # bot_id -> Thread

def load_builder_settings():
    doc = builder_settings_col.find_one({"_id": "config"})
    if not doc:
        doc = {"_id": "config", "creation_enabled": True}
        builder_settings_col.insert_one(doc)
    return doc

_builder_settings_doc = load_builder_settings()
BOT_CREATION_ENABLED = _builder_settings_doc.get("creation_enabled", True)

def save_builder_settings():
    builder_settings_col.update_one({"_id": "config"}, {"$set": {"creation_enabled": BOT_CREATION_ENABLED}}, upsert=True)

def can_create_bot(uid):
    uid = str(uid)
    if is_admin(uid):
        return True
    if BOT_CREATION_ENABLED:
        return not users.get(uid, {}).get("bot_creation_blocked", False)
    return users.get(uid, {}).get("bot_creation_allowed", False)

def get_user_bots(owner_id):
    return list(managed_bots_col.find({"owner_id": str(owner_id), "status": {"$ne": "deleted"}}))

def get_all_bots():
    return list(managed_bots_col.find({"status": {"$ne": "deleted"}}))

def get_bot_owner(bot_id):
    doc = managed_bots_col.find_one({"_id": bot_id})
    return str(doc.get("owner_id")) if doc else None

def track_bot_user(bot_id, tg_user):
    uid = str(tg_user.id)
    existing = bot_users_col.find_one({"bot_id": bot_id, "user_id": uid})
    if not existing:
        bot_users_col.insert_one({
            "bot_id": bot_id,
            "user_id": uid,
            "username": tg_user.username or "",
            "first_name": tg_user.first_name or "",
            "joined_at": datetime.now(),
            "last_active": datetime.now(),
            "downloads": 0
        })
    else:
        bot_users_col.update_one({"_id": existing["_id"]}, {"$set": {"last_active": datetime.now()}})

def increment_bot_downloads(bot_id, platform=None):
    managed_bots_col.update_one({"_id": bot_id}, {"$inc": {"downloads": 1}})

def increment_bot_user_downloads(bot_id, user_id):
    bot_users_col.update_one({"bot_id": bot_id, "user_id": str(user_id)}, {"$inc": {"downloads": 1}})

def send_broadcast_item(target_bot, chat_id, m):
    """Send one broadcast message (text/photo/video/document) to a single chat_id using target_bot."""
    if m.content_type == "text":
        target_bot.send_message(chat_id, m.text)
    elif m.content_type == "photo":
        target_bot.send_photo(chat_id, m.photo[-1].file_id, caption=m.caption or "")
    elif m.content_type == "video":
        target_bot.send_video(chat_id, m.video.file_id, caption=m.caption or "")
    elif m.content_type == "document":
        target_bot.send_document(chat_id, m.document.file_id, caption=m.caption or "")
    else:
        raise ValueError("unsupported content type")

def broadcast_to_bot_users(target_bot, bot_id, m, progress_cb=None):
    """Broadcast m to all users of one managed bot. Returns (sent, failed)."""
    recipients = list(bot_users_col.find({"bot_id": bot_id}))
    sent = 0
    failed = 0
    for i, r in enumerate(recipients):
        uid = r["user_id"]
        try:
            send_broadcast_item(target_bot, int(uid), m)
            sent += 1
        except ApiTelegramException as e:
            if e.error_code == 429:
                retry_after = 5
                try:
                    retry_after = e.result_json.get("parameters", {}).get("retry_after", 5)
                except:
                    pass
                time.sleep(retry_after)
                try:
                    send_broadcast_item(target_bot, int(uid), m)
                    sent += 1
                except:
                    failed += 1
            else:
                failed += 1
        except Exception:
            failed += 1
        time.sleep(0.05)
        if progress_cb:
            progress_cb(i + 1, len(recipients))
    return sent, failed

def owner_broadcast_process(bi, bot_id, m):
    if not (m.text or m.photo or m.video or m.document):
        try:
            bi.send_message(m.chat.id, "❌ Please send text, a photo, a video, or a document.")
        except:
            pass
        return
    sent, failed = broadcast_to_bot_users(bi, bot_id, m)
    try:
        bi.send_message(m.chat.id, f"✅ Broadcast Completed\n\nSent: {sent}\nFailed: {failed}")
    except:
        pass

def register_downloader_handlers(bi, bot_id):
    """Attach the shared downloader engine + per-bot admin panel to a managed bot instance."""

    @bi.message_handler(commands=['start'])
    def mb_start(message):
        track_bot_user(bot_id, message.from_user)
        doc = managed_bots_col.find_one({"_id": bot_id})
        kb = None
        if doc and str(message.from_user.id) == str(doc.get("owner_id")):
            kb = ReplyKeyboardMarkup(resize_keyboard=True)
            kb.add("👑 Admin Panel")
        try:
            bi.send_message(
                message.chat.id,
                "🎬 Welcome!\n\nSend any video link (TikTok, YouTube, Facebook, Instagram, Pinterest, Snapchat, X/Twitter) to download it.",
                reply_markup=kb
            )
        except:
            pass

    @bi.message_handler(func=lambda m: m.text == "👑 Admin Panel")
    def mb_admin_panel(message):
        owner_id = get_bot_owner(bot_id)
        if owner_id != str(message.from_user.id):
            try:
                bi.send_message(message.chat.id, "❌ You are not the owner of this bot.")
            except:
                pass
            return
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📊 Stats", callback_data=f"bld_ownstats_{bot_id}"))
        kb.add(InlineKeyboardButton("📢 Broadcast", callback_data=f"bld_ownbc_{bot_id}"))
        kb.add(InlineKeyboardButton("⚙️ Bot Settings", callback_data=f"bld_ownset_{bot_id}"))
        try:
            bi.send_message(message.chat.id, "👑 Admin Panel", reply_markup=kb)
        except:
            pass

    @bi.callback_query_handler(func=lambda call: call.data.startswith("bld_own"))
    def mb_owner_callbacks(call):
        owner_id = get_bot_owner(bot_id)
        if owner_id != str(call.from_user.id):
            try:
                bi.answer_callback_query(call.id, "❌ Not authorized")
            except:
                pass
            return

        if call.data.startswith("bld_ownstats_"):
            doc = managed_bots_col.find_one({"_id": bot_id}) or {}
            users_count = bot_users_col.count_documents({"bot_id": bot_id})
            downloads = doc.get("downloads", 0)
            active_cutoff = datetime.now() - timedelta(days=7)
            active_count = bot_users_col.count_documents({"bot_id": bot_id, "last_active": {"$gte": active_cutoff}})
            text = f"📊 Bot Statistics\n\n👥 Users: {users_count}\n📥 Downloads: {downloads}\n🟢 Active Users (7d): {active_count}"
            try:
                bi.answer_callback_query(call.id)
                bi.send_message(call.message.chat.id, text)
            except:
                pass

        elif call.data.startswith("bld_ownbc_"):
            try:
                bi.answer_callback_query(call.id)
                msg = bi.send_message(call.message.chat.id, "📝 Send the text / photo / video / document to broadcast to your bot's users:")
                bi.register_next_step_handler(msg, lambda m: owner_broadcast_process(bi, bot_id, m))
            except:
                pass

        elif call.data.startswith("bld_ownset_"):
            doc = managed_bots_col.find_one({"_id": bot_id}) or {}
            text = (
                f"⚙️ Bot Settings\n\n"
                f"🤖 Username: @{doc.get('bot_username')}\n"
                f"📛 Name: {doc.get('bot_name')}\n"
                f"📅 Created: {doc.get('created_at')}\n"
                f"📊 Status: {doc.get('status', 'active')}"
            )
            try:
                bi.answer_callback_query(call.id)
                bi.send_message(call.message.chat.id, text)
            except:
                pass

    @bi.callback_query_handler(func=lambda call: call.data.startswith("music_"))
    def mb_extract_music(call):
        vid_id = call.data.split("_")[1]
        video_path = video_files.get(vid_id)
        if not video_path or not os.path.exists(video_path):
            try:
                bi.answer_callback_query(call.id, "❌ Audio expired.")
            except:
                pass
            return
        audio_path = f"audio_{vid_id}.mp3"
        try:
            bi.send_chat_action(call.message.chat.id, 'upload_audio')
            subprocess.run(['ffmpeg', '-i', video_path, '-q:a', '0', '-map', 'a', audio_path, '-y'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with open(audio_path, 'rb') as audio:
                bi.send_audio(call.message.chat.id, audio)
            os.remove(audio_path)
        except Exception:
            try:
                bi.answer_callback_query(call.id, "❌ Failed to convert music")
            except:
                pass

    @bi.message_handler(func=lambda m: m.text and "http" in m.text)
    def mb_handle_link(message):
        track_bot_user(bot_id, message.from_user)
        link = extract_url(message.text)
        if not link:
            return
        try:
            msg = bi.send_message(message.chat.id, "⚡ Processing...")
            normal_executor.submit(download_media, message.chat.id, link, msg.message_id, bi, bot_id)
        except:
            pass

def start_managed_bot(bot_id, token):
    if bot_id in managed_bot_instances:
        return
    try:
        bi = telebot.TeleBot(token, parse_mode="HTML")
        register_downloader_handlers(bi, bot_id)
        managed_bot_instances[bot_id] = bi

        def run():
            try:
                bi.infinity_polling(timeout=20, long_polling_timeout=20)
            except Exception as e:
                print(f"Managed bot {bot_id} stopped: {e}")

        t = threading.Thread(target=run, daemon=True)
        managed_bot_threads[bot_id] = t
        t.start()
    except Exception as e:
        print(f"Failed to start managed bot {bot_id}: {e}")

def stop_managed_bot(bot_id):
    bi = managed_bot_instances.get(bot_id)
    if bi:
        try:
            bi.stop_polling()
        except:
            pass
        managed_bot_instances.pop(bot_id, None)
    managed_bot_threads.pop(bot_id, None)

def show_bot_builder_menu(chat_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ Create New Bot", callback_data="bld_create"))
    kb.add(InlineKeyboardButton("🤖 My Bots", callback_data="bld_mybots"))
    kb.add(InlineKeyboardButton("🗑 Delete Bot", callback_data="bld_delete"))
    try:
        bot.send_message(chat_id, "🤖 Bot Creation System", reply_markup=kb)
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "👥 Send Users To Create")
def admin_send_users_to_create(m):
    if not is_admin(m.from_user.id):
        return
    show_bot_builder_menu(m.chat.id)

@bot.message_handler(func=lambda m: m.text == "🤖 BOT BUILDER")
def user_bot_builder_entry(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    if not can_create_bot(m.from_user.id):
        try:
            bot.send_message(m.chat.id, "❌ Bot creation is currently unavailable.")
        except:
            pass
        return
    show_bot_builder_menu(m.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "bld_create")
def bld_create_cb(call):
    uid = call.from_user.id
    if not can_create_bot(uid):
        try:
            bot.answer_callback_query(call.id, "❌ Bot creation is currently unavailable.")
        except:
            pass
        return
    try:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            call.message.chat.id,
            "🤖 Create New Bot\n\n"
            "1️⃣ Open @BotFather in Telegram\n"
            "2️⃣ Send /newbot and follow the steps\n"
            "3️⃣ Copy the token BotFather gives you\n"
            "4️⃣ Paste that token here\n\n"
            "⚠️ Your token is stored securely and is never shown again."
        )
        bot.register_next_step_handler(msg, bld_receive_token, uid)
    except:
        pass

def bld_receive_token(m, owner_id):
    token = (m.text or "").strip()
    if not token or ":" not in token:
        try:
            bot.send_message(m.chat.id, "❌ That doesn't look like a valid bot token. Press ➕ Create New Bot to try again.")
        except:
            pass
        return

    try:
        test_bot = telebot.TeleBot(token, parse_mode="HTML")
        me = test_bot.get_me()
    except Exception:
        try:
            bot.send_message(m.chat.id, "❌ Invalid token, or Telegram rejected it. Please check and try again.")
        except:
            pass
        return

    existing = managed_bots_col.find_one({"bot_username": me.username, "status": {"$ne": "deleted"}})
    if existing:
        try:
            bot.send_message(m.chat.id, "❌ This bot is already registered in the system.")
        except:
            pass
        return

    bot_id = str(uuid.uuid4())
    managed_bots_col.insert_one({
        "_id": bot_id,
        "owner_id": str(owner_id),
        "owner_username": m.from_user.username or "",
        "bot_username": me.username,
        "bot_name": me.first_name,
        "token": token,
        "created_at": datetime.now(),
        "status": "active",
        "downloads": 0
    })

    start_managed_bot(bot_id, token)

    try:
        bot.send_message(
            m.chat.id,
            f"✅ Bot Created!\n\n🤖 @{me.username} is now live as a downloader bot.\n"
            "You are the owner — open that bot and press 👑 Admin Panel to manage it."
        )
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "bld_mybots")
def bld_mybots_cb(call):
    uid = call.from_user.id
    bots = get_user_bots(uid)
    try:
        bot.answer_callback_query(call.id)
    except:
        pass
    if not bots:
        try:
            bot.send_message(call.message.chat.id, "You don't own any bots yet.")
        except:
            pass
        return
    lines = ["🤖 Your Bots:\n"]
    for b in bots:
        u_count = bot_users_col.count_documents({"bot_id": b["_id"]})
        lines.append(f"@{b.get('bot_username')} — 👥 {u_count} users | 📥 {b.get('downloads', 0)} downloads | {b.get('status', 'active')}")
    try:
        bot.send_message(call.message.chat.id, "\n".join(lines))
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "bld_delete")
def bld_delete_cb(call):
    uid = call.from_user.id
    bots = get_user_bots(uid)
    try:
        bot.answer_callback_query(call.id)
    except:
        pass
    if not bots:
        try:
            bot.send_message(call.message.chat.id, "You don't own any bots to delete.")
        except:
            pass
        return
    kb = InlineKeyboardMarkup()
    for b in bots:
        kb.add(InlineKeyboardButton(f"@{b.get('bot_username')}", callback_data=f"bld_delpick_{b['_id']}"))
    try:
        bot.send_message(call.message.chat.id, "🤖 Select a bot to delete:", reply_markup=kb)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("bld_delpick_"))
def bld_delpick_cb(call):
    bot_id = call.data.split("bld_delpick_", 1)[1]
    b = managed_bots_col.find_one({"_id": bot_id})
    uid = call.from_user.id
    if not b or (str(b.get("owner_id")) != str(uid) and not is_admin(uid)):
        try:
            bot.answer_callback_query(call.id, "❌ Not authorized")
        except:
            pass
        return
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Yes, Delete", callback_data=f"bld_delconfirm_{bot_id}"))
    kb.add(InlineKeyboardButton("❌ Cancel", callback_data="bld_delcancel"))
    try:
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            f"⚠️ Are you sure?\n\nThis will remove @{b.get('bot_username')} from your Bot Builder system.",
            call.message.chat.id, call.message.message_id, reply_markup=kb
        )
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("bld_delconfirm_"))
def bld_delconfirm_cb(call):
    bot_id = call.data.split("bld_delconfirm_", 1)[1]
    b = managed_bots_col.find_one({"_id": bot_id})
    uid = call.from_user.id
    if not b or (str(b.get("owner_id")) != str(uid) and not is_admin(uid)):
        try:
            bot.answer_callback_query(call.id, "❌ Not authorized")
        except:
            pass
        return
    stop_managed_bot(bot_id)
    managed_bots_col.update_one({"_id": bot_id}, {"$set": {"status": "deleted"}})
    try:
        bot.answer_callback_query(call.id, "🗑 Bot deleted")
        bot.edit_message_text(f"🗑 @{b.get('bot_username')} has been deleted.", call.message.chat.id, call.message.message_id)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "bld_delcancel")
def bld_delcancel_cb(call):
    try:
        bot.answer_callback_query(call.id, "Cancelled")
        bot.edit_message_text("❌ Deletion cancelled.", call.message.chat.id, call.message.message_id)
    except:
        pass

def show_all_bots_page(chat_id, page, message_id=None):
    all_bots = get_all_bots()
    per_page = 5
    total = len(all_bots)
    start = page * per_page
    page_bots = all_bots[start:start + per_page]

    lines = [f"🤖 All Created Bots\n\nTotal Bots: {total}\n"]
    for i, b in enumerate(page_bots, start=start + 1):
        u_count = bot_users_col.count_documents({"bot_id": b["_id"]})
        owner_label = f"@{b['owner_username']}" if b.get("owner_username") else b.get("owner_id")
        lines.append(
            f"{i}. @{b.get('bot_username')}\n"
            f"Owner: {owner_label}\n"
            f"Users: {u_count}\n"
            f"Downloads: {b.get('downloads', 0)}\n"
            f"Status: {b.get('status', 'active')}\n"
        )

    kb = InlineKeyboardMarkup()
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"bld_allbots_{page - 1}"))
    if start + per_page < total:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"bld_allbots_{page + 1}"))
    if nav:
        kb.row(*nav)

    text = "\n".join(lines) if page_bots else "No bots created yet."
    try:
        if message_id:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
        else:
            bot.send_message(chat_id, text, reply_markup=kb)
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "🤖 All Created Bots")
def admin_all_bots(m):
    if not is_admin(m.from_user.id):
        return
    show_all_bots_page(m.chat.id, 0)

@bot.callback_query_handler(func=lambda call: call.data.startswith("bld_allbots_"))
def bld_allbots_page_cb(call):
    if not is_admin(call.from_user.id):
        try:
            bot.answer_callback_query(call.id, "❌ Not admin")
        except:
            pass
        return
    page = int(call.data.split("_")[-1])
    try:
        bot.answer_callback_query(call.id)
    except:
        pass
    show_all_bots_page(call.message.chat.id, page, call.message.message_id)

@bot.message_handler(func=lambda m: m.text == "⚙️ Bot Creation Access")
def admin_toggle_access(m):
    if not is_admin(m.from_user.id):
        return
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🟢 Enable", callback_data="bld_access_on"))
    kb.add(InlineKeyboardButton("🔴 Disable", callback_data="bld_access_off"))
    status = "🟢 Enabled" if BOT_CREATION_ENABLED else "🔴 Disabled"
    try:
        bot.send_message(m.chat.id, f"⚙️ Bot Creation Access\n\nCurrent status: {status}", reply_markup=kb)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data in ["bld_access_on", "bld_access_off"])
def bld_access_toggle_cb(call):
    global BOT_CREATION_ENABLED
    if not is_admin(call.from_user.id):
        try:
            bot.answer_callback_query(call.id, "❌ Not admin")
        except:
            pass
        return
    BOT_CREATION_ENABLED = call.data == "bld_access_on"
    save_builder_settings()
    status = "🟢 Enabled" if BOT_CREATION_ENABLED else "🔴 Disabled"
    try:
        bot.answer_callback_query(call.id, "✅ Updated")
        bot.edit_message_text(f"⚙️ Bot Creation Access\n\nCurrent status: {status}", call.message.chat.id, call.message.message_id)
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "📢 Broadcast All Bots")
def admin_broadcast_all_bots(m):
    if not is_admin(m.from_user.id):
        return
    all_bots = get_all_bots()
    if not all_bots:
        try:
            bot.send_message(m.chat.id, "No managed bots yet.")
        except:
            pass
        return
    try:
        msg = bot.send_message(m.chat.id, "📝 Send the text / photo / video / document to broadcast to ALL managed bots' users:")
        bot.register_next_step_handler(msg, broadcast_all_bots_process)
    except:
        pass

def broadcast_all_bots_process(m):
    if not is_admin(m.from_user.id):
        return
    if not (m.text or m.photo or m.video or m.document):
        try:
            bot.send_message(m.chat.id, "❌ Please send text, a photo, a video, or a document.")
        except:
            pass
        return

    all_bots = get_all_bots()
    bots_with_recipients = []
    total_users = 0
    for b in all_bots:
        recipients = list(bot_users_col.find({"bot_id": b["_id"]}))
        bots_with_recipients.append((b, recipients))
        total_users += len(recipients)

    progress_msg = None
    try:
        progress_msg = bot.send_message(
            m.chat.id,
            f"📢 Broadcast started...\n\nBots: {len(all_bots)}\nUsers: {total_users}\n\nProgress:\n0 / {total_users}"
        )
    except:
        pass

    sent = 0
    failed = 0
    processed = 0
    already_notified = set()  # avoid duplicate sends if the same telegram user exists in multiple bots
    last_update = time.time()

    for b, recipients in bots_with_recipients:
        bi = managed_bot_instances.get(b["_id"])
        if not bi:
            failed += len(recipients)
            processed += len(recipients)
            continue

        for r in recipients:
            uid = r["user_id"]
            processed += 1
            if uid in already_notified:
                # Already messaged this Telegram user through another managed bot
                time.sleep(0.02)
            else:
                try:
                    send_broadcast_item(bi, int(uid), m)
                    sent += 1
                    already_notified.add(uid)
                except ApiTelegramException as e:
                    if e.error_code == 429:
                        retry_after = 5
                        try:
                            retry_after = e.result_json.get("parameters", {}).get("retry_after", 5)
                        except:
                            pass
                        time.sleep(retry_after)
                        try:
                            send_broadcast_item(bi, int(uid), m)
                            sent += 1
                            already_notified.add(uid)
                        except:
                            failed += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1
                time.sleep(0.05)

            if progress_msg and time.time() - last_update > 3:
                last_update = time.time()
                try:
                    bot.edit_message_text(
                        f"📢 Broadcast in progress...\n\nBots: {len(all_bots)}\nUsers: {total_users}\n\nProgress:\n{processed} / {total_users}",
                        m.chat.id, progress_msg.message_id
                    )
                except:
                    pass

    try:
        bot.send_message(m.chat.id, f"✅ Broadcast Completed\n\nSent: {sent}\nFailed: {failed}")
    except:
        pass

# ================= RUN =================
if __name__ == "__main__":
    if not os.path.exists("downloads"):
        os.makedirs("downloads")

    print("🤖 Downloader Bot is running...")

    # Start all previously created managed (downloader) bots so they resume after a restart
    for _b in get_all_bots():
        if _b.get("status") == "active" and _b.get("token"):
            start_managed_bot(_b["_id"], _b["token"])
    
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
