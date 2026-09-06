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

# ================= CONFIG =================

TOKEN = os.getenv("BOT_TOKEN")
BOT2_TOKEN = os.getenv("BOT2_TOKEN")

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")

PHONE = os.getenv("PHONE")

# Resend API Config for support@vexdou.space (HTTP Port 443 - Railway-friendly)

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "support@vexdou.space")

# D7 SMS API Config

D7_TOKEN = os.getenv("D7_TOKEN")

MAX_YOUTUBE_DURATION = int(os.getenv("MAX_YOUTUBE_DURATION", "900")) # 15 Minutes in seconds
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
email_verify_pending = {}
phone_verify_pending = {}
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

# ================= SETTINGS SETUP =================

settings_col = db1["settings"]

def get_setting(key, default):
    res = settings_col.find_one({"_id": key})
    return res["value"] if res else default

def set_setting(key, value):
    settings_col.update_one({"_id": key}, {"$set": {"value": value}}, upsert=True)

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

def send_html_email(to_email, subject, html_body):
    if not RESEND_API_KEY:
        print("❌ RESEND_API_KEY is not set in environment variables.")
        return False
    
    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "from": SENDER_EMAIL,
        "to": [to_email],
        "subject": subject,
        "html": html_body
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code in [200, 201]:
            return True
        else:
            print(f"RESEND API ERROR: {response.text}")
            return False
    except Exception as e:
        print(f"EMAIL API ERROR: {e}")
        return False

# NEW: D7 SMS Sender Function

def send_d7_sms(phone_number, text):
    if not D7_TOKEN:
        print("❌ D7_TOKEN is not set in environment variables.")
        return False
        
    url = "https://api.d7networks.com/messages/v1/send"
    headers = {
        "Authorization": f"Bearer {D7_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "messages": [
            {
                "channel": "sms",
                "recipients": [phone_number],
                "content": text,
                "msg_type": "text",
                "data_coding": "text"
            }
        ],
        "message_globals": {
            "originator": "VerifyBot",
            "report_url": "https://vexdou.space"
        }
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code in [200, 201]:
            return True
        else:
            print(f"D7 SMS API ERROR: {response.text}")
            return False
    except Exception as e:
        print(f"D7 SMS EXCEPTION: {e}")
        return False

def extract_url(text):
    if not text:
        return None
    match = re.search(r'(https?://[^\s]+)', text)
    return match.group(0) if match else None

# ================= MENUS =================

def user_menu(show_admin=False):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💰 BALANCE", "💸 WITHDRAWAL")
    kb.add("👥 REFERRAL", "🆔 GET ID")
    kb.add("💳 PAY")
    kb.add("👤 Profile")
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
    kb.add("📉 CHANGE MINIMUM", "➕ ADD FEE")
    kb.add("➕ ADD LOW FEE", "🎁 GIFT ALL")
    kb.add("🗑️ REMOVE ALL")
    kb.add("📢 Send Email All")
    kb.add("✅ Verified Users", "🏷️ Sticker")
    kb.add("Reveral Prices", "Delete Pay", "Open Pay rev")
    kb.add("Send verify")
    kb.add("🟢 Open SMS", "🔴 CLOSE SMS")
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

# ================= ADMIN SMS CONTROL =================

@bot.message_handler(func=lambda m: m.text in ["🟢 Open SMS", "🔴 CLOSE SMS"])
def sms_admin_manager(m):
    if not is_admin(m.from_user.id): return
    
    if m.text == "🟢 Open SMS":
        set_setting("sms_enabled", True)
        try:
            bot.send_message(m.chat.id, "🟢 SMS Verification system is now OPEN. Users can choose Gmail or Phone.")
        except: pass
    elif m.text == "🔴 CLOSE SMS":
        set_setting("sms_enabled", False)
        try:
            bot.send_message(m.chat.id, "🔴 SMS Verification system is now CLOSED. Users will only use Gmail.")
        except: pass

# ================= PROFILE & VERIFICATION LOGIC =================

@bot.message_handler(func=lambda m: m.text == "👤 Profile")
def profile_handler(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    uid = str(m.from_user.id)
    u_data = users.get(uid, {})
    
    verified = u_data.get("verified", False)
    sticker = u_data.get("sticker", "Verified" if verified else "Not Verified")
    status_str = f"Verified ({sticker})" if verified else "Not Verified"
    joined = u_data.get("joined_date", datetime.now().strftime("%Y-%m-%d"))
    downloads = videos_data.get("users", {}).get(uid, 0)
    balance = u_data.get("balance", 0.0)
    email = u_data.get("email", "")
    phone = u_data.get("phone", "")
    contact_info = email if email else (phone if phone else "Not Set")
    
    text = (
        f"<b>👤 USER PROFILE</b>\n\n"
        f"• Status: {status_str}\n"
        f"• Contact: {contact_info}\n"
        f"• Date Joined: {joined}\n"
        f"• Total Downloads: {downloads}\n"
        f"• Balance: ${balance:.2f}"
    )
    kb = InlineKeyboardMarkup()
    if not verified:
        kb.add(InlineKeyboardButton("Verify", callback_data="start_verify_flow"))
    try:
        bot.send_message(m.chat.id, text, reply_markup=kb)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "start_verify_flow")
def start_verify_flow(call):
    try:
        sms_enabled = get_setting("sms_enabled", False)
        if sms_enabled:
            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton("📧 Verify via Gmail", callback_data="verify_choice_gmail"),
                InlineKeyboardButton("📱 Verify via Number", callback_data="verify_choice_phone")
            )
            bot.edit_message_text(
                "Please choose your verification method:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=kb
            )
        else:
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("Cancel Verification", callback_data="cancel_verify_process"))
            msg = bot.send_message(call.message.chat.id, "Please enter your Gmail address:", reply_markup=kb)
            bot.register_next_step_handler(msg, process_verification_email)
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"Verify flow error: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("verify_choice_"))
def handle_verify_choice(call):
    choice = call.data.split("_")[2]
    try:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("Cancel Verification", callback_data="cancel_verify_process"))
        if choice == "gmail":
            msg = bot.send_message(call.message.chat.id, "Please enter your Gmail address:", reply_markup=kb)
            bot.register_next_step_handler(msg, process_verification_email)
        elif choice == "phone":
            msg = bot.send_message(call.message.chat.id, "Please send your phone number with country code (e.g., +25261XXXXXXX or +2519XXXXXXX):", reply_markup=kb)
            bot.register_next_step_handler(msg, process_verification_phone)
        bot.answer_callback_query(call.id)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "cancel_verify_process")
def cancel_verify_process(call):
    uid = str(call.from_user.id)
    email_verify_pending.pop(uid, None)
    phone_verify_pending.pop(uid, None)
    try:
        bot.edit_message_text("❌ Verification process cancelled.", call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.answer_callback_query(call.id, "Cancelled successfully!")
    except:
        pass

# Helper to auto delete message/cancel session after 1 min if requested or expired
def delayed_cancel_session(chat_id, message_id, uid):
    time.sleep(60)
    if uid in email_verify_pending or uid in phone_verify_pending:
        email_verify_pending.pop(uid, None)
        phone_verify_pending.pop(uid, None)
        try:
            bot.edit_message_text("❌ Verification session expired or cancelled after 1 minute.", chat_id, message_id, reply_markup=None)
        except:
            pass

# ----- GMAIL VERIFICATION LOGIC ----- #

def process_verification_email(m):
    uid = str(m.from_user.id)
    email = (m.text or "").strip()
    
    menu_buttons = ["👤 Profile", "👑 ADMIN PANEL", "💰 BALANCE", "💸 WITHDRAWAL", "👥 REFERRAL", "🆔 GET ID", "☎️ CUSTOMER", "🤖CUSTOMER AI", "🔙 BACK MAIN MENU", "💳 PAY"]
    if email in menu_buttons or "@" not in email:
        try:
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("Cancel Verification", callback_data="cancel_verify_process"))
            msg = bot.send_message(m.chat.id, "❌ Invalid email address. Please enter a valid Gmail address:", reply_markup=kb)
            bot.register_next_step_handler(msg, process_verification_email)
        except: pass
        return

    code = str(random.randint(100000, 999999))
    current_time = time.time()
    email_verify_pending[uid] = {
        "email": email,
        "code": code,
        "time": current_time,
        "last_resend": current_time
    }
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 600px; background: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <h2 style="color: #333;">Email Verification</h2>
            <p>Hello,</p>
            <p>Your 6-digit verification code for the bot is:</p>
            <div style="font-size: 24px; font-weight: bold; color: #4CAF50; background: #e8f5e9; padding: 15px; text-align: center; border-radius: 4px; letter-spacing: 5px;">
                {code}
            </div>
            <p style="margin-top: 20px; color: #666; font-size: 12px;">If you didn't request this, please ignore this email.</p>
        </div>
    </body>
    </html>
    """
    
    success = send_html_email(email, "Your Bot Verification Code", html_content)
    if success:
        try:
            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton("🔄 Resend", callback_data="resend_verify_code"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process")
            )
            msg = bot.send_message(m.chat.id, f"📩 A 6-digit verification code has been sent to your email ({email}). Please enter the code here:", reply_markup=kb)
            bot.register_next_step_handler(msg, process_verification_code)
            threading.Thread(target=delayed_cancel_session, args=(m.chat.id, msg.message_id, uid), daemon=True).start()
        except: pass
    else:
        try:
            bot.send_message(m.chat.id, "❌ Failed to send verification email. Please try again later.")
        except: pass

@bot.callback_query_handler(func=lambda call: call.data == "resend_verify_code")
def resend_verify_code_callback(call):
    uid = str(call.from_user.id)
    if uid not in email_verify_pending:
        bot.answer_callback_query(call.id, "❌ Verification session expired. Please start again from your profile.", show_alert=True)
        return
        
    data = email_verify_pending[uid]
    current_time = time.time()
    last_resend_time = data.get("last_resend", data.get("time", 0))
    cooldown = 60  # 1 minute for Gmail
    elapsed = current_time - last_resend_time
    
    if elapsed < cooldown:
        remaining = int(cooldown - elapsed)
        bot.answer_callback_query(call.id, f"⏳ Please wait {remaining}s before requesting another code.", show_alert=True)
        return
        
    data["last_resend"] = current_time
    email = data["email"]
    code = str(random.randint(100000, 999999))
    data["code"] = code
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 600px; background: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <h2 style="color: #333;">Email Verification (Resend)</h2>
            <p>Hello,</p>
            <p>Your new 6-digit verification code for the bot is:</p>
            <div style="font-size: 24px; font-weight: bold; color: #4CAF50; background: #e8f5e9; padding: 15px; text-align: center; border-radius: 4px; letter-spacing: 5px;">
                {code}
            </div>
            <p style="margin-top: 20px; color: #666; font-size: 12px;">If you didn't request this, please ignore this email.</p>
        </div>
    </body>
    </html>
    """
    
    success = send_html_email(email, "Your New Bot Verification Code", html_content)
    if success:
        bot.answer_callback_query(call.id, "✅ A new code has been sent to your email!")
        try:
            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton("🔄 Resend", callback_data="resend_verify_code"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process")
            )
            msg = bot.send_message(call.message.chat.id, f"📩 A new 6-digit verification code has been resent to your email ({email}). Please enter the code here:", reply_markup=kb)
            bot.register_next_step_handler(msg, process_verification_code)
            threading.Thread(target=delayed_cancel_session, args=(call.message.chat.id, msg.message_id, uid), daemon=True).start()
        except: pass
    else:
        bot.answer_callback_query(call.id, "❌ Failed to resend verification email.", show_alert=True)

def process_verification_code(m):
    uid = str(m.from_user.id)
    code_input = (m.text or "").strip()
    
    if uid not in email_verify_pending:
        try:
            bot.send_message(m.chat.id, "❌ Verification session expired or already completed. Please start again from your profile.")
        except: pass
        return

    menu_buttons = ["👤 Profile", "👑 ADMIN PANEL", "💰 BALANCE", "💸 WITHDRAWAL", "👥 REFERRAL", "🆔 GET ID", "☎️ CUSTOMER", "🤖CUSTOMER AI", "🔙 BACK MAIN MENU", "💳 PAY"]
    if code_input in menu_buttons or not code_input.isdigit() or len(code_input) != 6:
        try:
            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton("🔄 Resend", callback_data="resend_verify_code"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process")
            )
            msg = bot.send_message(
                m.chat.id,
                "⚠️ <b>Action not allowed!</b>\n"
                "You must enter the 6-digit code sent to your Gmail first.\n\n"
                "Please enter the correct code:",
                reply_markup=kb
            )
            bot.register_next_step_handler(msg, process_verification_code)
        except: pass
        return

    data = email_verify_pending[uid]
    if code_input == data["code"]:
        users[uid]["verified"] = True
        users[uid]["email"] = data["email"]
        if "sticker" not in users[uid] or not users[uid]["sticker"]:
            users[uid]["sticker"] = "🌟"
        save_user(uid)
        email_verify_pending.pop(uid, None)
        try:
            bot.send_message(m.chat.id, "✅ Congratulations! Your account is now Verified. You can check your profile status.", reply_markup=user_menu(is_admin(m.from_user.id)))
        except: pass
    else:
        try:
            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton("🔄 Resend", callback_data="resend_verify_code"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process")
            )
            msg = bot.send_message(m.chat.id, "❌ Incorrect verification code. Please enter the correct 6-digit code:", reply_markup=kb)
            bot.register_next_step_handler(msg, process_verification_code)
            threading.Thread(target=delayed_cancel_session, args=(m.chat.id, msg.message_id, uid), daemon=True).start()
        except: pass

# ----- PHONE VERIFICATION LOGIC ----- #

def process_verification_phone(m):
    uid = str(m.from_user.id)
    phone_input = (m.text or "").strip().replace(" ", "")
    
    menu_buttons = ["👤 Profile", "👑 ADMIN PANEL", "💰 BALANCE", "💸 WITHDRAWAL", "👥 REFERRAL", "🆔 GET ID", "☎️ CUSTOMER", "🤖CUSTOMER AI", "🔙 BACK MAIN MENU", "💳 PAY"]
    if phone_input in menu_buttons or not phone_input.startswith("+") or len(phone_input) < 10:
        try:
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process"))
            msg = bot.send_message(m.chat.id, "❌ Invalid number. Please send a valid phone number with country code (e.g., +252... or +251...):", reply_markup=kb)
            bot.register_next_step_handler(msg, process_verification_phone)
        except: pass
        return

    code = str(random.randint(100000, 999999))
    current_time = time.time()
    phone_verify_pending[uid] = {
        "phone": phone_input,
        "code": code,
        "time": current_time,
        "last_resend": current_time
    }
    
    sms_text = f"Your Downloader Bot Verification Code is: {code}"
    success = send_d7_sms(phone_input, sms_text)
    if success:
        try:
            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton("🔄 Resend SMS", callback_data="resend_phone_code"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process")
            )
            msg = bot.send_message(m.chat.id, f"📲 A 6-digit code has been sent via SMS to your number ({phone_input}). Please enter the code below:", reply_markup=kb)
            bot.register_next_step_handler(msg, process_phone_code)
            threading.Thread(target=delayed_cancel_session, args=(m.chat.id, msg.message_id, uid), daemon=True).start()
        except: pass
    else:
        try:
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process"))
            bot.send_message(m.chat.id, "❌ Failed to send SMS. Please try again later or check your phone number.", reply_markup=kb)
        except: pass

@bot.callback_query_handler(func=lambda call: call.data == "resend_phone_code")
def resend_phone_code_callback(call):
    uid = str(call.from_user.id)
    if uid not in phone_verify_pending:
        bot.answer_callback_query(call.id, "❌ Session expired. Please start again from your profile.", show_alert=True)
        return
        
    data = phone_verify_pending[uid]
    current_time = time.time()
    last_resend_time = data.get("last_resend", data.get("time", 0))
    cooldown = 600  # 10 minutes (600 seconds) required for SMS
    elapsed = current_time - last_resend_time
    
    if elapsed < cooldown:
        remaining = int(cooldown - elapsed)
        mins = remaining // 60
        secs = remaining % 60
        time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
        bot.answer_callback_query(call.id, f"⏳ Please wait {time_str} before requesting another SMS code.", show_alert=True)
        return
        
    data["last_resend"] = current_time
    phone = data["phone"]
    code = str(random.randint(100000, 999999))
    data["code"] = code
    
    sms_text = f"Your New Verification Code is: {code}"
    success = send_d7_sms(phone, sms_text)
    if success:
        bot.answer_callback_query(call.id, "✅ A new code has been sent via SMS!")
        try:
            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton("🔄 Resend SMS", callback_data="resend_phone_code"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process")
            )
            msg = bot.send_message(call.message.chat.id, f"📲 A new code has been sent to your number ({phone}). Please enter the code here:", reply_markup=kb)
            bot.register_next_step_handler(msg, process_phone_code)
            threading.Thread(target=delayed_cancel_session, args=(call.message.chat.id, msg.message_id, uid), daemon=True).start()
        except: pass
    else:
        bot.answer_callback_query(call.id, "❌ Error sending SMS, please try again later.", show_alert=True)

def process_phone_code(m):
    uid = str(m.from_user.id)
    code_input = (m.text or "").strip()
    
    if uid not in phone_verify_pending:
        try:
            bot.send_message(m.chat.id, "❌ Verification session expired. Please start again from your profile.")
        except: pass
        return

    menu_buttons = ["👤 Profile", "👑 ADMIN PANEL", "💰 BALANCE", "💸 WITHDRAWAL", "👥 REFERRAL", "🆔 GET ID", "☎️ CUSTOMER", "🤖CUSTOMER AI", "🔙 BACK MAIN MENU", "💳 PAY"]
    if code_input in menu_buttons or not code_input.isdigit() or len(code_input) != 6:
        try:
            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton("🔄 Resend SMS", callback_data="resend_phone_code"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process")
            )
            msg = bot.send_message(
                m.chat.id,
                "⚠️ <b>Action not allowed!</b>\n"
                "You must enter the 6-digit SMS code first.\n\n"
                "Please enter the correct code:",
                reply_markup=kb
            )
            bot.register_next_step_handler(msg, process_phone_code)
        except: pass
        return

    data = phone_verify_pending[uid]
    if code_input == data["code"]:
        users[uid]["verified"] = True
        users[uid]["phone"] = data["phone"]
        if "sticker" not in users[uid] or not users[uid]["sticker"]:
            users[uid]["sticker"] = "🌟"
        save_user(uid)
        phone_verify_pending.pop(uid, None)
        try:
            bot.send_message(m.chat.id, "✅ Congratulations! Your account is now Verified. You can check your profile status.", reply_markup=user_menu(is_admin(m.from_user.id)))
        except: pass
    else:
        try:
            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton("🔄 Resend SMS", callback_data="resend_phone_code"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process")
            )
            msg = bot.send_message(m.chat.id, "❌ Incorrect code. Please enter the correct code sent via SMS:", reply_markup=kb)
            bot.register_next_step_handler(msg, process_phone_code)
            threading.Thread(target=delayed_cancel_session, args=(m.chat.id, msg.message_id, uid), daemon=True).start()
        except: pass

# ================= ADMIN VERIFIED USERS & STICKER MANAGER =================

@bot.message_handler(func=lambda m: m.text == "✅ Verified Users")
def verified_users_list(m):
    if not is_admin(m.from_user.id):
        return
    verified_list = [uid for uid, data in users.items() if data.get("verified")]
    if not verified_list:
        try:
            bot.send_message(m.chat.id, "No verified users found.")
        except: pass
        return
    
    text = f"✅ VERIFIED USERS ({len(verified_list)})\n\n"
    for uid in verified_list[:30]:
        u_data = users[uid]
        sticker = u_data.get("sticker", "N/A")
        email = u_data.get('email', '')
        phone = u_data.get('phone', '')
        contact = email if email else (phone if phone else "No Contact Info")
        text += f"• <a href='tg://user?id={uid}'>{uid}</a> | {contact} | Sticker: {sticker}\n"
    try:
        bot.send_message(m.chat.id, text, parse_mode="HTML")
    except: pass

@bot.message_handler(func=lambda m: m.text == "🏷️ Sticker")
def sticker_admin_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send User ID or BOT ID and the sticker/badge separated by pipe (|)\nExample:\n123456789 | 🌟 Verified")
        bot.register_next_step_handler(msg, sticker_admin_process)
    except: pass

def sticker_admin_process(m):
    if not is_admin(m.from_user.id):
        return
    try:
        parts = m.text.split("|")
        if len(parts) < 2:
            bot.send_message(m.chat.id, "❌ Format error. Use: UserID | StickerText")
            return
        uid_str = parts[0].strip()
        sticker_text = parts[1].strip()
        
        uid = uid_str if uid_str in users else find_user_by_botid(uid_str)
        if not uid or uid not in users:
            bot.send_message(m.chat.id, "❌ User not found.")
            return
        users[uid]["sticker"] = sticker_text
        save_user(uid)
        bot.send_message(m.chat.id, f"✅ Sticker successfully updated for user {uid}!")
        try:
            bot.send_message(int(uid), f"🌟 Your profile status sticker has been updated to: {sticker_text}")
        except: pass
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Error: {e}")

# ================= ADMIN SEND EMAIL ALL =================

@bot.message_handler(func=lambda m: m.text == "📢 Send Email All")
def send_email_all_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send the HTML content or message you want to email to all users who have an email registered:")
        bot.register_next_step_handler(msg, send_email_all_process)
    except: pass

def send_email_all_process(m):
    if not is_admin(m.from_user.id):
        return
    html_content = m.text
    
    count = 0
    for uid, data in users.items():
        email = data.get("email")
        if email:
            success = send_html_email(email, "Announcement from Video Downloader Bot", html_content)
            if success:
                count += 1
    try:
        bot.send_message(m.chat.id, f"✅ HTML Email successfully sent to {count} verified users with email addresses.")
    except: pass

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
        try:
            bot.send_message(m.chat.id, "❌ User not found.")
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
    except: pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("qa_"))
def handle_qa_callbacks(call):
    if not is_admin(call.from_user.id):
        return
    if call.data == "qa_add":
        try:
            msg = bot.send_message(call.message.chat.id, "Send User ID or BOT ID to grant Quick Access:")
            bot.register_next_step_handler(msg, lambda m: grant_qa(m, True))
        except: pass
    elif call.data == "qa_remove":
        try:
            msg = bot.send_message(call.message.chat.id, "Send User ID or BOT ID to remove Quick Access:")
            bot.register_next_step_handler(msg, lambda m: grant_qa(m, False))
        except: pass

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
        except: pass
    else:
        try:
            bot.send_message(m.chat.id, "❌ User not found.")
        except: pass

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
        {
            "$set": {
                "username": call.from_user.username or "N/A",
                "rating": rating,
                "platform": platform,
                "updated_at": datetime.now()
            },
            "$setOnInsert": {"created_at": datetime.now()}
        },
        upsert=True
    )
    bot.answer_callback_query(call.id, "Thank you for your feedback! ❤️")
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.edit_message_text("Thank you for your feedback! ❤️", call.message.chat.id, call.message.message_id)
    except: pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("rate_text_"))
def ask_written_feedback(call):
    req_id = call.data.split("_")[2]
    try:
        msg = bot.send_message(call.message.chat.id, "Please tell us how we can improve our service.")
        bot.register_next_step_handler(msg, save_written_feedback, req_id)
    except: pass

def save_written_feedback(m, req_id):
    if not m.text:
        try:
            bot.send_message(m.chat.id, "Please send text feedback.")
        except: pass
        return
        
    feedback_col.update_one(
        {"user_id": m.from_user.id, "feedback_request_id": req_id},
        {
            "$set": {
                "username": m.from_user.username or "N/A",
                "feedback_text": m.text,
                "updated_at": datetime.now()
            },
            "$setOnInsert": {"created_at": datetime.now()}
        },
        upsert=True
    )
    try:
        bot.send_message(m.chat.id, "Thank you! Your feedback has been received. ❤️")
    except: pass

@bot.message_handler(func=lambda m: m.text in ["📊 Feedback Stats", "🟢 Open Feedback", "🔴 Close Feedback", "🗑️ Reset All Feedbacks"])
def feedback_admin_manager(m):
    if not is_admin(m.from_user.id): return
    
    if m.text == "🟢 Open Feedback":
        videos_data["feedback_enabled"] = True
        save_videos()
        try:
            bot.send_message(m.chat.id, "🟢 Feedback system is now OPEN.")
        except: pass
    elif m.text == "🔴 Close Feedback":
        videos_data["feedback_enabled"] = False
        save_videos()
        try:
            bot.send_message(m.chat.id, "🔴 Feedback system is now CLOSED.")
        except: pass
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
        except: pass
    elif m.text == "🗑️ Reset All Feedbacks":
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("✅ Yes, Reset Everything", callback_data="reset_fb_confirm"))
        kb.add(InlineKeyboardButton("❌ Cancel", callback_data="reset_fb_cancel"))
        try:
            bot.send_message(m.chat.id, "⚠️ Are you sure you want to delete all existing feedback data? This action cannot be undone.", reply_markup=kb)
        except: pass

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
    if page > 0:
        btns.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"view_fb_{page-1}"))
    if page < len(all_fb) - 1:
        btns.append(InlineKeyboardButton("Next ➡️", callback_data=f"view_fb_{page+1}"))
    if btns:
        kb.row(*btns)
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="close_fb"))
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda call: call.data in ["reset_fb_confirm", "reset_fb_cancel", "close_fb"])
def reset_callback_handler(call):
    if not is_admin(call.from_user.id): return
    if call.data == "reset_fb_confirm":
        try:
            feedback_col.delete_many({})
            bot.edit_message_text("✅ ALL FEEDBACKS RESET. All previous feedback data has been successfully deleted.", call.message.chat.id, call.message.message_id)
        except:
            bot.edit_message_text("❌ RESET FAILED", call.message.chat.id, call.message.message_id)
    elif call.data == "reset_fb_cancel":
        bot.edit_message_text("❌ Reset cancelled.", call.message.chat.id, call.message.message_id)
    elif call.data == "close_fb":
        bot.delete_message(call.message.chat.id, call.message.message_id)

CHANNEL_USERNAME = "@tiktokvediodownload"

# ================= DOWNLOAD MEDIA FUNCTION =================

def download_media(chat_id, link, message_id):
    platform = "unknown"
    if "tiktok.com" in link:
        platform = "tiktok"
    elif "youtube.com" in link or "youtu.be" in link:
        platform = "youtube"
    elif "facebook.com" in link or "fb.watch" in link:
        platform = "facebook"
    elif "instagram.com" in link:
        platform = "instagram"
    elif "pinterest.com" in link or "pin.it" in link:
        platform = "pinterest"
    elif "snapchat.com" in link:
        platform = "snapchat"
    elif "twitter.com" in link or "x.com" in link:
        platform = "twitter"

    max_duration = MAX_YOUTUBE_DURATION
    uid_str = str(chat_id)
    if platform == "youtube" and users.get(uid_str, {}).get("youtube_30m", False):
        max_duration = 1800 # 30 minutes

    tmp_dir = f"downloads_{uuid.uuid4().hex}"
    os.makedirs(tmp_dir, exist_ok=True)
    ydl_opts = {
        'outtmpl': f'{tmp_dir}/%(id)s.%(ext)s',
        'format': 'best',
        'max_filesize': 500 * 1024 * 1024,
    }
    try:
        with yt_dlp.YoutubeDL({'extract_flat': True, 'quiet': True}) as ydl:
            info = ydl.extract_info(link, download=False)
            if info and 'duration' in info and info['duration']:
                if info['duration'] > max_duration and platform == "youtube":
                    bot.edit_message_text(
                        f"❌ Video is too long. Max allowed duration is {max_duration // 60} minutes.",
                        chat_id,
                        message_id
                    )
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                    return
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            filename = ydl.prepare_filename(info)
            if not os.path.exists(filename):
                files = os.listdir(tmp_dir)
                if files:
                    filename = os.path.join(tmp_dir, files[0])
                else:
                    raise Exception("Downloaded file not found.")
            with open(filename, 'rb') as f:
                if filename.endswith(('.mp4', '.mkv', '.webm', '.mov', '.avi', '.gif')):
                    bot.send_video(chat_id, f, caption="🎬 Downloaded successfully via @Downloadvedioytibot")
                elif filename.endswith(('.mp3', '.m4a', '.wav', '.ogg')):
                    bot.send_audio(chat_id, f, caption="🎵 Audio downloaded successfully via @Downloadvedioytibot")
                else:
                    bot.send_document(chat_id, f, caption="📁 File downloaded successfully via @Downloadvedioytibot")
            bot.delete_message(chat_id, message_id)
            videos_data["total"] = videos_data.get("total", 0) + 1
            if platform in videos_data["platforms"]:
                videos_data["platforms"][platform] += 1
            if uid_str not in videos_data["users"]:
                videos_data["users"][uid_str] = 0
            videos_data["users"][uid_str] += 1
            save_videos()
            if videos_data.get("feedback_enabled", False):
                send_feedback_request(chat_id, platform, uuid.uuid4().hex)
    except Exception as e:
        print(f"Download error: {e}")
        try:
            bot.edit_message_text(f"❌ Failed to download media. Error: {str(e)[:100]}", chat_id, message_id)
        except: pass
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

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
            "joined_date": datetime.now().strftime("%Y-%m-%d"),
            "month": now_month()
        }
        if ref:
            ref_user = next((u for u, d in users.items() if d["ref"] == ref), None)
            if ref_user and ref_user != str(uid):
                users[ref_user]["balance"] += 0.2
                users[ref_user]["invited"] += 1
                try:
                    bot.send_message(int(ref_user), "🎉 You earned $0.2 from referral!")
                except: pass
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
    except: pass

@bot.message_handler(commands=['balance'])
def balance_cmd(m):
    uid = str(m.from_user.id)
    bal = users.get(uid, {}).get("balance", 0)
    try:
        bot.send_message(m.chat.id, f"💰 Your balance: ${bal:.2f}")
    except: pass

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
        kb.add(InlineKeyboardButton("💳 Buy Custom Referral Code (PAY)", callback_data="buy_ref_menu"))
        bot.send_message(
            m.chat.id,
            f"🔗 Your Referral Link:\n{link}\n\n"
            f"👥 Invited Users: {invited}\n"
            f"🎁 You earn $0.2 per referral!",
            reply_markup=kb
        )
    except: pass

@bot.message_handler(commands=['ping'])
def ping_cmd(m):
    start = time.time()
    try:
        msg = bot.send_message(m.chat.id, "🏓 Pinging...")
        end = time.time()
        speed = round((end - start) * 1000)
        status = "🟢 Online" if speed < 1000 else "🟡 Slow"
        bot.edit_message_text(
            f"🏓 PONG!\n\n"
            f"⚡ Speed: {speed} ms\n"
            f"📡 Status: {status}",
            m.chat.id,
            msg.message_id,
            parse_mode="HTML"
        )
    except: pass

# ================= VERIFY BOT START =================

@bot2.message_handler(commands=['start'])
def verify_start(message):
    args = message.text.split()
    if len(args) > 1:
        code = args[1]
        try:
            bot2.send_message(
                message.chat.id,
                f"🔑 Your Verification Code\n\n"
                f"{code}\n\n"
                "Copy this code and send it to the downloader bot."
            )
        except: pass
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
                "❌ Don't Have Code?\n\nGet code from downloader bot.",
                reply_markup=kb
            )
        except: pass

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
    except: pass

def send_multi_join(user_id):
    kb = InlineKeyboardMarkup(row_width=3)
    buttons = [InlineKeyboardButton("➕️ JOIN", url=f"https://t.me/{ch}") for ch in POST_CHANNELS]
    kb.add(*buttons)
    kb.add(InlineKeyboardButton("✅ CONFIRM", callback_data="multi_checkjoin"))
    try:
        bot.send_message(user_id, "⚠️ Join all channels to continue.", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda call: call.data == "confirm_join")
def confirm_join(call):
    user_id = call.from_user.id
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["member", "administrator", "creator"]:
            bot.answer_callback_query(call.id, "✅ Join verified")
            try:
                bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
            except: pass
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
        except: pass
        return
    try:
        bot.send_message(m.chat.id, "👑 Admin Panel", reply_markup=admin_menu())
    except: pass

@bot.message_handler(func=lambda m: m.text == "💰 BALANCE")
def balance_handler(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    uid = str(m.from_user.id)
    bal = users.get(uid, {}).get("balance", 0.0)
    blocked = users.get(uid, {}).get("blocked", 0.0)
    try:
        bot.send_message(m.chat.id, f"💰 Available Balance: ${bal:.2f}\n⏳ Blocked Amount: ${blocked:.2f}")
    except: pass

@bot.message_handler(func=lambda m: m.text == "🆔 GET ID")
def get_id_handler(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    uid = str(m.from_user.id)
    try:
        bot.send_message(m.chat.id, f"🆔 BOT ID: {users[uid]['bot_id']}\n👤 Telegram ID: {uid}")
    except: pass

@bot.message_handler(func=lambda m: m.text == "☎️ CUSTOMER")
def customer_handler(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    try:
        bot.send_message(m.chat.id, "☎️ Customer Support:\n@scholes1")
    except: pass

@bot.message_handler(func=lambda m: m.text == "🤖CUSTOMER AI")
def customer_ai_handler(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    try:
        bot.send_message(m.chat.id, "Ai Customer Support🤖:\n@Aidownoaderbot")
    except: pass

@bot.message_handler(func=lambda m: m.text == "💸 WITHDRAWAL")
def withdraw_menu(m):
    if banned_guard(m):
        return
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("USDT-BEP20")
    kb.add("🔙 CANCEL")
    try:
        bot.send_message(m.chat.id, "Select withdrawal method:", reply_markup=kb)
    except: pass

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
        except: pass

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
        except: pass
        return
    users[uid]["temp_addr"] = text
    save_user(uid)
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🔙 CANCEL")
    try:
        min_w = get_setting("min_withdrawal", 1.0)
        msg = bot.send_message(m.chat.id, f"Enter withdrawal amount\nMinimum: ${min_w}\nBalance: ${users[uid]['balance']:.2f}\n\nOr press 🔙 CANCEL", reply_markup=kb)
        bot.register_next_step_handler(msg, withdraw_amount_step)
    except: pass

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
        except: pass
        return

    min_w = get_setting("min_withdrawal", 1.0)
    if amt < min_w:
        try:
            bot.send_message(m.chat.id, f"❌ Minimum withdrawal is ${min_w}", reply_markup=user_menu(is_admin(uid)))
        except: pass
        return
    if amt > users[uid]["balance"]:
        try:
            bot.send_message(m.chat.id, "❌ Insufficient balance", reply_markup=user_menu(is_admin(uid)))
        except: pass
        return

    fee_pct = get_setting("fee_percent", 0.0)
    low_fee = get_setting("low_fee", 0.0)
    calculated_fee = (amt * fee_pct) / 100.0
    amount_sent = amt - calculated_fee - low_fee
    if amount_sent < 0:
        amount_sent = 0.0

    wid = random.randint(10000, 99999)
    users[uid]["balance"] -= amt
    users[uid]["blocked"] += amt

    withdrawal = {
        "id": wid,
        "user": uid,
        "amount": amt,
        "fee": calculated_fee,
        "low_fee": low_fee,
        "amount_sent": amount_sent,
        "blocked": amt,
        "address": users[uid].get("temp_addr", "N/A"),
        "status": "pending",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    withdraws.append(withdrawal)
    save_user(uid)
    save_withdraws()

    if users[uid].get("verified") and users[uid].get("email"):
        w_email = users[uid]["email"]
        html_receipt = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="UTF-8"></head>
        <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
            <div style="max-width: 600px; background: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <h2 style="color: #2c3e50; border-bottom: 2px solid #eee; padding-bottom: 10px;">Withdrawal Request Receipt</h2>
                <p>Hello,</p>
                <p>Your withdrawal request has been successfully submitted and is currently pending review.</p>
                <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #ddd; font-weight: bold;">Request ID:</td>
                        <td style="padding: 10px; border-bottom: 1px solid #ddd;">{wid}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #ddd; font-weight: bold;">Amount Requested:</td>
                        <td style="padding: 10px; border-bottom: 1px solid #ddd;">${amt:.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #ddd; font-weight: bold;">Fee:</td>
                        <td style="padding: 10px; border-bottom: 1px solid #ddd;">${calculated_fee:.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #ddd; font-weight: bold;">Low W/D Fee:</td>
                        <td style="padding: 10px; border-bottom: 1px solid #ddd;">${low_fee:.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #ddd; font-weight: bold;">Amount to Send:</td>
                        <td style="padding: 10px; border-bottom: 1px solid #ddd; color: #27ae60; font-weight: bold;">${amount_sent:.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #ddd; font-weight: bold;">USDT Address:</td>
                        <td style="padding: 10px; border-bottom: 1px solid #ddd; word-break: break-all; font-family: monospace;">{withdrawal['address']}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #ddd; font-weight: bold;">Status:</td>
                        <td style="padding: 10px; border-bottom: 1px solid #ddd; color: #e67e22; font-weight: bold;">Pending</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #ddd; font-weight: bold;">Time:</td>
                        <td style="padding: 10px; border-bottom: 1px solid #ddd;">{withdrawal['time']}</td>
                    </tr>
                </table>
                <p style="margin-top: 30px; color: #7f8c8d; font-size: 12px; text-align: center;">Thank you for using our bot!</p>
            </div>
        </body>
        </html>
        """
        send_html_email(w_email, f"Withdrawal Receipt #{wid}", html_receipt)

    receipt_text = (
        f"✅ Withdrawal Request Sent\n"
        f"🧾 Request ID: {wid}\n"
        f"💲 Fee ({fee_pct:.2f}%): -${calculated_fee:.2f}\n"
        f"💲 Low W/D Fee: -${low_fee:.2f}\n"
        f"💵 Amount: ${amt:.2f}\n"
        f"🏦 Address: {withdrawal['address']}\n"
        f"♾️ Amount Sent: ${amount_sent:.2f}\n"
        f"⏳ Status: Pending"
    )
    try:
        bot.send_message(int(uid), receipt_text)
    except: pass

    admin_text = f"💳 NEW WITHDRAWAL\n\n👤 User: {uid}\n🤖 BOT ID: {users[uid]['bot_id']}\n👥 Referrals: {users[uid]['invited']}\n💵 Amount: ${amt:.2f}\n♾️ Amount Sent: ${amount_sent:.2f}\n🧾 Request ID: {wid}\n🏦 Address: {withdrawal['address']}\n⏳ Status: Pending"
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
        except: pass

@bot.callback_query_handler(func=lambda call: call.data.startswith(("confirm_", "reject_", "ban_", "block_")))
def admin_callbacks(call):
    if not is_admin(call.from_user.id):
        try:
            bot.answer_callback_query(call.id, "❌ You are not admin")
        except: pass
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
        except: pass
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
        except: pass
    elif data.startswith("ban_"):
        uid = data.split("_")[1]
        if uid in users:
            users[uid]["banned"] = True
            save_user(uid)
            try:
                bot.answer_callback_query(call.id, "🚫 User banned")
                bot.send_message(int(uid), "🚫 You have been banned by admin.")
            except: pass
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
        except: pass

@bot.message_handler(func=lambda m: m.text == "💰 UNBLOCK MONEY")
def unblock_money_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "🔢 Send 4-digit Block Code to UNBLOCK funds:")
        bot.register_next_step_handler(msg, unblock_money_process)
    except: pass

def unblock_money_process(m):
    if not is_admin(m.from_user.id):
        return
    code = (m.text or "").strip()
    w = next((x for x in withdraws if x.get("block_code") == code), None)
    if not w:
        try:
            bot.send_message(m.chat.id, "❌ Invalid Block Code")
        except: pass
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
    except: pass

@bot.message_handler(func=lambda m: m.text == "🔥 UN BAN-USER")
def unban_user_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send Telegram ID of user to UNBAN:")
        bot.register_next_step_handler(msg, unban_user_process)
    except: pass

def unban_user_process(m):
    if not is_admin(m.from_user.id):
        return
    uid = (m.text or "").strip()
    if uid not in users:
        try:
            bot.send_message(m.chat.id, "❌ User not found")
        except: pass
        return
    users[uid]["banned"] = False
    save_user(uid)
    try:
        bot.send_message(m.chat.id, f"✅ User {uid} unbanned")
        bot.send_message(int(uid), "✅ You have been unbanned by admin.")
    except: pass

@bot.message_handler(func=lambda m: m.text == "💳 WITHDRAWAL CHECK")
def withdrawal_check_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Enter Withdrawal Request ID:")
        bot.register_next_step_handler(msg, withdrawal_check_process)
    except: pass

def withdrawal_check_process(m):
    if not is_admin(m.from_user.id):
        return
    try:
        wid = int(m.text.strip())
    except:
        try:
            bot.send_message(m.chat.id, "❌ Invalid Request ID")
        except: pass
        return

    w = next((x for x in withdraws if x["id"] == wid), None)
    if not w:
        try:
            bot.send_message(m.chat.id, "❌ Request not found")
        except: pass
        return
    uid = w["user"]
    bot_id = users.get(uid, {}).get("bot_id", "Unknown")
    invited = users.get(uid, {}).get("invited", 0)
    msg_text = f"💳 WITHDRAWAL DETAILS\n\n🧾 Request ID: {w['id']}\n👤 User ID: {uid}\n🤖 BOT ID: {bot_id}\n👥 Referrals: {invited}\n💵 Amount: ${w['amount']:.2f}\n🏦 Address: {w['address']}\n📊 Status: {w['status'].upper()}\n⏰ Time: {w['time']}"
    try:
        bot.send_message(m.chat.id, msg_text)
    except: pass

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
    except: pass

@bot.message_handler(func=lambda m: m.text == "📉 CHANGE MINIMUM")
def change_min_start(m):
    if not is_admin(m.from_user.id): return
    try:
        msg = bot.send_message(m.chat.id, "Send new minimum withdrawal amount (e.g., 0.001 or 1):")
        bot.register_next_step_handler(msg, change_min_process)
    except: pass

def change_min_process(m):
    if not is_admin(m.from_user.id): return
    try:
        new_min = float(m.text.strip())
        set_setting("min_withdrawal", new_min)
        bot.send_message(m.chat.id, f"✅ Minimum withdrawal updated to: ${new_min}")
    except:
        bot.send_message(m.chat.id, "❌ Invalid number.")

@bot.message_handler(func=lambda m: m.text == "➕ ADD FEE")
def add_fee_start(m):
    if not is_admin(m.from_user.id): return
    try:
        msg = bot.send_message(m.chat.id, "Send fee percentage (e.g., 1.5 for 1.5% or 0 for 0%):")
        bot.register_next_step_handler(msg, add_fee_process)
    except: pass

def add_fee_process(m):
    if not is_admin(m.from_user.id): return
    try:
        fee_pct = float(m.text.strip())
        set_setting("fee_percent", fee_pct)
        bot.send_message(m.chat.id, f"✅ Withdrawal fee percentage set to: {fee_pct}%")
    except:
        bot.send_message(m.chat.id, "❌ Invalid number.")

@bot.message_handler(func=lambda m: m.text == "➕ ADD LOW FEE")
def add_low_fee_start(m):
    if not is_admin(m.from_user.id): return
    try:
        msg = bot.send_message(m.chat.id, "Send low withdrawal fee amount (e.g., 0.05):")
        bot.register_next_step_handler(msg, add_low_fee_process)
    except: pass

def add_low_fee_process(m):
    if not is_admin(m.from_user.id): return
    try:
        low_fee = float(m.text.strip())
        set_setting("low_fee", low_fee)
        bot.send_message(m.chat.id, f"✅ Low W/D fee set to: ${low_fee}")
    except:
        bot.send_message(m.chat.id, "❌ Invalid number.")

@bot.message_handler(func=lambda m: m.text == "🎁 GIFT ALL")
def gift_all_start(m):
    if not is_admin(m.from_user.id): return
    try:
        msg = bot.send_message(m.chat.id, "Send amount to gift to ALL users (e.g. 1 or 0.5):")
        bot.register_next_step_handler(msg, gift_all_process)
    except: pass

def gift_all_process(m):
    if not is_admin(m.from_user.id): return
    try:
        amount = float(m.text.strip())
        if amount <= 0:
            bot.send_message(m.chat.id, "❌ Amount must be greater than 0")
            return
        
        users_col.update_many({}, {"$inc": {"balance": amount}})
        for uid in users:
            users[uid]["balance"] = users[uid].get("balance", 0.0) + amount
        bot.send_message(m.chat.id, f"🎁 Successfully added ${amount} to all users' balances!")
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Error: {e}")

@bot.message_handler(func=lambda m: m.text == "🗑️ REMOVE ALL")
def remove_all_start(m):
    if not is_admin(m.from_user.id): return
    try:
        msg = bot.send_message(m.chat.id, "Send amount and reason separated by pipe (|)\nExample:\n0.5 | Reason")
        bot.register_next_step_handler(msg, remove_all_process)
    except: pass

def remove_all_process(m):
    if not is_admin(m.from_user.id): return
    try:
        parts = m.text.split("|")
        if len(parts) < 2:
            bot.send_message(m.chat.id, "❌ Invalid format. Use: Amount | Reason")
            return
        remove_amt = float(parts[0].strip())
        reason = parts[1].strip()
        
        if remove_amt <= 0:
            bot.send_message(m.chat.id, "❌ Amount must be greater than 0")
            return
        users_col.update_many({}, {"$inc": {"balance": -remove_amt}})
        for uid in users:
            users[uid]["balance"] = max(0.0, users[uid].get("balance", 0.0) - remove_amt)
            
        count = 0
        for uid in users:
            try:
                bot.send_message(int(uid), f"⚠️ Your Account Has Been Charged: ${remove_amt:.2f}\nReason: {reason}")
                count += 1
            except: pass
        bot.send_message(m.chat.id, f"✅ Successfully removed ${remove_amt} from all users and notified {count} users. Reason: {reason}")
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Error: {e}")

@bot.message_handler(func=lambda m: m.text == "🚫 BAN USER MANUAL")
def manual_ban_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send Telegram ID or BOT ID to BAN user:")
        bot.register_next_step_handler(msg, manual_ban_process)
    except: pass

def manual_ban_process(m):
    if not is_admin(m.from_user.id):
        return
    uid_input = (m.text or "").strip()
    uid = uid_input if uid_input in users else find_user_by_botid(uid_input)
    if not uid:
        try:
            bot.send_message(m.chat.id, "❌ User not found")
        except: pass
        return
    users[uid]["banned"] = True
    save_user(uid)
    try:
        bot.send_message(m.chat.id, f"🚫 User {uid} banned")
        bot.send_message(int(uid), "🚫 You have been banned by admin.")
    except: pass

@bot.message_handler(func=lambda m: m.text == "📡 ADD CHANNEL")
def add_channel_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send channel username\nExample:\n@mychannel")
        bot.register_next_step_handler(msg, add_channel_process)
    except: pass

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
        except: pass

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
    except: pass

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
    except: pass

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

@bot.message_handler(func=lambda m: m.text == "SEND PAY")
def send_pay_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send payment details in this format:\n\nTitle | Description | Price in Stars\n\nExample:\nVIP Access | 1 Month VIP Subscription | 50")
        bot.register_next_step_handler(msg, send_pay_process)
    except: pass

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
    except: pass

def post_channel_add(m):
    if m.text.lower() == "done":
        try:
            bot.send_message(m.chat.id, f"✅ {len(POST_CHANNELS)} channels added.")
        except: pass
        return
    if len(POST_CHANNELS) >= MAX_CHANNELS:
        try:
            bot.send_message(m.chat.id, "⚠️ Maximum 10 channels allowed.")
        except: pass
        return
    username = m.text.replace("@", "").strip()
    POST_CHANNELS.append(username)
    try:
        msg = bot.send_message(m.chat.id, f"Channel @{username} added\nTotal: {len(POST_CHANNELS)}\nSend another or DONE")
        bot.register_next_step_handler(msg, post_channel_add)
    except: pass

@bot.message_handler(func=lambda m: m.text == "CLOSE CHANNEL POST")
def close_channel_post(m):
    if not is_admin(m.from_user.id):
        return
    MANAGED_CHANNELS.clear()
    try:
        bot.send_message(m.chat.id, "❌ All channels removed.")
    except: pass

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
        except: pass
        count += 1
        if count >= 20:
            break
    try:
        bot.send_message(m.chat.id, f"📊 Total Users: {total}")
    except: pass

@bot.message_handler(func=lambda m: m.text == "🔒 LOCK BOT")
def lock_bot_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "✍️ Send the lock message users should receive.")
        bot.register_next_step_handler(msg, lock_bot_process)
    except: pass

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
        except: pass

@bot.message_handler(func=lambda m: m.text == "🔓 UNLOCK BOT")
def unlock_bot(m):
    global BOT_LOCKED
    if not is_admin(m.from_user.id):
        return
    BOT_LOCKED = False
    try:
        bot.send_message(m.chat.id, "🔓 Bot unlocked successfully.")
    except: pass

@bot.message_handler(func=lambda m: m.text == "📢 ADD ADS")
def add_ads_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "✍️ Format:\nButton Name | Link | Qoraal yar", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_add_ads)
    except: pass

def process_add_ads(m):
    global ADS_ENABLED, ADS_BTN_TEXT, ADS_URL, ADS_TEXT
    if not is_admin(m.from_user.id):
        return
    parts = [p.strip() for p in (m.text or "").split("|")]
    if len(parts) < 2:
        try:
            bot.send_message(m.chat.id, "❌ Format error.")
        except: pass
        return
    ADS_BTN_TEXT = parts[0]
    ADS_URL = parts[1]
    ADS_TEXT = parts[2] if len(parts) > 2 else "✨ Nagala soco baraha bulshada!"
    ADS_ENABLED = True
    try:
        bot.send_message(m.chat.id, "✅ Ads saved and enabled!")
    except: pass

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
    except: pass

@bot.message_handler(func=lambda m: m.text == "📥 IMPORT USERS")
def import_users_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send Telegram IDs separated by spaces or new lines.")
        bot.register_next_step_handler(msg, import_users_process)
    except: pass

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
                "joined_date": datetime.now().strftime("%Y-%m-%d"),
                "month": now_month()
            }
            save_user(uid)
            added += 1
    try:
        bot.send_message(m.chat.id, f"✅ Imported {added} users successfully.")
    except: pass

@bot.message_handler(func=lambda m: m.text == "🔗 GET REFERRAL CODE")
def get_ref_code_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send user username (e.g. @username):")
        bot.register_next_step_handler(msg, get_ref_username)
    except: pass

def get_ref_username(m):
    if not is_admin(m.from_user.id):
        return
    username = m.text.replace("@", "").strip()
    try:
        msg = bot.send_message(m.chat.id, f"User: @{username}\nNow send referral code number:")
        bot.register_next_step_handler(msg, lambda x: save_custom_ref_code(x, username))
    except: pass

def save_custom_ref_code(m, username):
    if not is_admin(m.from_user.id):
        return
    code = m.text.strip()
    if not code.isdigit():
        try:
            bot.send_message(m.chat.id, "❌ Code must be a number")
        except: pass
        return
    user_id = next((uid for uid, data in users.items() if data.get("username", "").lower() == username.lower()), None)
    if not user_id:
        try:
            bot.send_message(m.chat.id, "❌ User not found")
        except: pass
        return
    users[user_id]["ref"] = code
    save_user(user_id)
    try:
        bot.send_message(m.chat.id, f"✅ Referral code updated for @{username}")
    except: pass

@bot.message_handler(func=lambda m: m.text == "🔎 SEARCH USER")
def search_user(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send User Telegram ID")
        bot.register_next_step_handler(msg, search_user_result)
    except: pass

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
        except: pass
    else:
        try:
            bot.send_message(m.chat.id, "❌ User not found")
        except: pass

# ================= NEW FEATURE: CUSTOM REFERRAL CODES & PAY =================

def is_ref_taken(code):
    for uid, data in users.items():
        if str(data.get("ref")) == str(code):
            return True
    return False

@bot.message_handler(func=lambda m: m.text == "💳 PAY")
@bot.callback_query_handler(func=lambda call: call.data == "buy_ref_menu")
def pay_custom_ref_handler(m):
    if bot_locked_guard(m if hasattr(m, "from_user") else m.message) or banned_guard(m if hasattr(m, "from_user") else m.message):
        return
        
    chat_id = m.chat.id if hasattr(m, "chat") else m.message.chat.id
    if not get_setting("pay_rev_enabled", False):
        try:
            bot.send_message(chat_id, "❌ Custom referral code purchase system is currently disabled by admin.")
        except: pass
        if hasattr(m, "id"):
            bot.answer_callback_query(m.id)
        return
    try:
        msg = bot.send_message(chat_id, "💳 **Buy Custom Referral Code**\n\nEnter your desired referral code (letters/numbers):")
        bot.register_next_step_handler(msg, pay_custom_ref_code_input)
        if hasattr(m, "id"):
            bot.answer_callback_query(m.id)
    except: pass

def pay_custom_ref_code_input(m):
    uid = str(m.from_user.id)
    code = (m.text or "").strip()
    if not code or len(code) > 30:
        try:
            msg = bot.send_message(m.chat.id, "❌ Invalid code. Please enter a valid referral code:")
            bot.register_next_step_handler(msg, pay_custom_ref_code_input)
        except: pass
        return

    if is_ref_taken(code):
        try:
            msg = bot.send_message(m.chat.id, "⚠️ This referral code already taken. Please choose another one:")
            bot.register_next_step_handler(msg, pay_custom_ref_code_input)
        except: pass
        return

    length = len(code)
    if length <= 5:
        price = get_setting("ref_price_short", 50)
    else:
        price = get_setting("ref_price_long", 20)

    prices = [LabeledPrice(label=f"Custom Ref: {code}", amount=price)]
    try:
        bot.send_invoice(
            m.chat.id,
            title="Custom Referral Code",
            description=f"Purchase custom referral code: {code}",
            invoice_payload=f"buy_ref_{code}",
            provider_token="",
            currency="XTR",
            prices=prices
        )
    except Exception as e:
        try:
            bot.send_message(m.chat.id, f"❌ Error creating invoice: {e}")
        except: pass

@bot.message_handler(content_types=['successful_payment'])
def successful_payment_handler(message):
    payment = message.successful_payment
    payload = payment.invoice_payload
    uid = str(message.from_user.id)
    
    if payload.startswith("buy_ref_"):
        code = payload.replace("buy_ref_", "")
        if is_ref_taken(code) and users.get(uid, {}).get("ref") != code:
            try:
                bot.send_message(message.chat.id, "⚠️ This referral code has just been taken by someone else. Please contact admin or try another code.")
            except: pass
            return
        users[uid]["ref"] = code
        save_user(uid)
        bot_username = bot.get_me().username
        link = f"https://t.me/{bot_username}?start={code}"
        try:
            bot.send_message(
                message.chat.id,
                f"🎉 <b>Success!</b> Your custom referral code has been successfully activated.\n\n"
                f"🔑 Code: <code>{code}</code>\n"
                f"🔗 New Referral Link:\n{link}",
                parse_mode="HTML"
            )
        except: pass

@bot.message_handler(func=lambda m: m.text == "Reveral Prices")
def admin_referral_prices(m):
    if not is_admin(m.from_user.id): return
    short_p = get_setting("ref_price_short", 50)
    long_p = get_setting("ref_price_long", 20)
    msg = f"⚙️ Referral Code Prices (Telegram Stars)\n\n• 1-5 chars price: {short_p} Stars\n• 6+ chars price: {long_p} Stars\n\nSend new price for short codes (1-5 chars) or type CANCEL:"
    msg_sent = bot.send_message(m.chat.id, msg, parse_mode="Markdown")
    bot.register_next_step_handler(msg_sent, set_short_price)

def set_short_price(m):
    if not is_admin(m.from_user.id): return
    if m.text.strip().lower() == "cancel":
        bot.send_message(m.chat.id, "Cancelled.")
        return
    try:
        p = int(m.text.strip())
        set_setting("ref_price_short", p)
        msg = bot.send_message(m.chat.id, f"✅ Short code price set to {p} Stars.\n\nNow send price for 6+ characters codes:")
        bot.register_next_step_handler(msg, set_long_price)
    except:
        msg = bot.send_message(m.chat.id, "❌ Invalid number. Try again or type CANCEL:")
        bot.register_next_step_handler(msg, set_short_price)

def set_long_price(m):
    if not is_admin(m.from_user.id): return
    if m.text.strip().lower() == "cancel":
        bot.send_message(m.chat.id, "Cancelled.")
        return
    try:
        p = int(m.text.strip())
        set_setting("ref_price_long", p)
        bot.send_message(m.chat.id, f"✅ Long code price set to {p} Stars successfully!")
    except:
        msg = bot.send_message(m.chat.id, "❌ Invalid number. Try again or type CANCEL:")
        bot.register_next_step_handler(msg, set_long_price)

@bot.message_handler(func=lambda m: m.text == "Delete Pay")
def delete_pay_handler(m):
    if not is_admin(m.from_user.id): return
    set_setting("pay_rev_enabled", False)
    bot.send_message(m.chat.id, "🛑 Referral code purchase system is now CLOSED (Deleted Pay).")

@bot.message_handler(func=lambda m: m.text == "Open Pay rev")
def open_pay_handler(m):
    if not is_admin(m.from_user.id): return
    set_setting("pay_rev_enabled", True)
    bot.send_message(m.chat.id, "🟢 Referral code purchase system is now OPEN.")

# ================= NEW FEATURE: SEND VERIFY BROADCAST =================

@bot.message_handler(func=lambda m: m.text == "Send verify")
def send_verify_broadcast_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "✍️ Send the message you want to broadcast with the email verification button to unverified users:")
    bot.register_next_step_handler(msg, send_verify_broadcast_process)

def send_verify_broadcast_process(m):
    if not is_admin(m.from_user.id): return
    text = m.text
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔐 Verify Now", callback_data="start_verify_flow"))
    
    count = 0
    for uid, udata in users.items():
        if not udata.get("verified", False):
            try:
                bot.send_message(int(uid), text, reply_markup=kb)
                count += 1
            except:
                continue
    bot.send_message(m.chat.id, f"✅ Verification broadcast sent to {count} unverified users successfully.")

# ================= LINK HANDLER =================

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
        try:
            bot.send_message(message.chat.id, "🔐 Verification Required\n\nChoose verification method:", reply_markup=kb)
        except: pass
        return

    try:
        msg = bot.send_message(message.chat.id, "⚡ Processing...")
        if is_quick_access(user_id):
            vip_executor.submit(download_media, message.chat.id, link, msg.message_id)
        else:
            normal_executor.submit(download_media, message.chat.id, link, msg.message_id)
    except: pass

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
        except: pass
        if user_id in pending_links:
            link = pending_links[user_id]
            del pending_links[user_id]
            try:
                msg = bot.send_message(user_id, "⬇️ Processing your video...")
                if is_quick_access(user_id):
                    vip_executor.submit(download_media, user_id, link, msg.message_id)
                else:
                    normal_executor.submit(download_media, user_id, link, msg.message_id)
            except: pass
        else:
            try:
                bot.send_message(user_id, "Send your video link.")
            except: pass
    else:
        try:
            bot.answer_callback_query(call.id, "❌ You must join all channels first!", show_alert=True)
        except: pass

@bot.message_handler(func=lambda m: m.text == "❌ CLOSE WINDOWS")
def close_channel_windows(m):
    global CHANNEL_WINDOW_OPEN
    if not is_admin(m.from_user.id):
        return
    CHANNEL_WINDOW_OPEN = False
    try:
        bot.send_message(m.chat.id, "✅ Channel join system disabled.")
    except: pass

@bot.message_handler(func=lambda m: m.text == "✅ VERIFY ON")
def verify_on(m):
    global VERIFY_ENABLED
    if not is_admin(m.from_user.id):
        return
    VERIFY_ENABLED = True
    try:
        bot.send_message(m.chat.id, "✅ Verify system enabled")
    except: pass

@bot.message_handler(func=lambda m: m.text == "❌ VERIFY OFF")
def verify_off(m):
    global VERIFY_ENABLED
    if not is_admin(m.from_user.id):
        return
    VERIFY_ENABLED = False
    try:
        bot.send_message(m.chat.id, "❌ Verify system disabled")
    except: pass

@bot.message_handler(func=lambda m: m.text == "CHANNEL POST")
def start_channel_post(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send the main text for the channel post.")
        bot.register_next_step_handler(msg, post_main_text)
    except: pass

def post_main_text(m):
    pending_post[m.from_user.id] = {"text": m.text, "buttons": []}
    try:
        msg = bot.send_message(m.chat.id, "Send button like:\n\nButton Name | Text when clicked\n\nSend DONE when finished.")
        bot.register_next_step_handler(msg, add_buttons)
    except: pass

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
            except: pass
        pending_post.pop(uid, None)
        try:
            bot.send_message(m.chat.id, "✅ Post sent")
        except: pass
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
        except: pass

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
    except: pass

@bot.message_handler(func=lambda m: m.text == "➕ ADD BALANCE")
def add_balance_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send BOT ID or Telegram ID and amount:")
        bot.register_next_step_handler(msg, add_balance_process)
    except: pass

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
            except: pass
            return
        users[uid]["balance"] += amt
        save_user(uid)
        try:
            bot.send_message(m.chat.id, f"✅ Added ${amt:.2f} to user {uid}")
            bot.send_message(int(uid), f"💰 Your balance increased by ${amt:.2f}")
        except: pass
    except:
        try:
            bot.send_message(m.chat.id, "❌ Format error.")
        except: pass

@bot.message_handler(func=lambda m: m.text == "➖ REMOVE MONEY")
def remove_balance_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send BOT ID or Telegram ID and amount:")
        bot.register_next_step_handler(msg, remove_balance_process)
    except: pass

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
            except: pass
            return
        if users[uid]["balance"] < amt:
            try:
                bot.send_message(m.chat.id, "❌ Insufficient balance")
            except: pass
            return
        users[uid]["balance"] -= amt
        save_user(uid)
        try:
            bot.send_message(m.chat.id, f"✅ Removed ${amt:.2f} from user {uid}")
            bot.send_message(int(uid), f"💸 ${amt:.2f} removed from your balance")
        except: pass
    except:
        try:
            bot.send_message(m.chat.id, "❌ Format error.")
        except: pass

# ================= MAIN RUN LOOP =================

if __name__ == "__main__":
    print("🤖 Bot 1 and Bot 2 are starting...")
    
    def run_bot2():
        try:
            bot2.infinity_polling(skip_pending=True)
        except Exception as e:
            print(f"Bot 2 Error: {e}")
            
    threading.Thread(target=run_bot2, daemon=True).start()
    
    try:
        bot.infinity_polling(skip_pending=True)
    except Exception as e:
        print(f"Bot 1 Error: {e}")
