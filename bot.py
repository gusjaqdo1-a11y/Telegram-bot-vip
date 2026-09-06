import os
import json
import random
import re
import shutil
import threading
import asyncio
import uuid
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import requests
import telebot
from telebot.types import (
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputMediaPhoto,
    LabeledPrice
)
from pymongo import MongoClient
import yt_dlp
from telethon import TelegramClient

# ================= CONFIG =================

TOKEN = os.getenv("BOT_TOKEN")
BOT2_TOKEN = os.getenv("BOT2_TOKEN")

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")

PHONE = os.getenv("PHONE")

# Resend API Config for Gmail/Email OTP
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "support@vexdou.space")

# SMESS.io WhatsApp API Config
SMESS_API_KEY = os.getenv("SMESS_API_KEY")
SMESS_DEVICE_ID = os.getenv("SMESS_DEVICE_ID")

# D7 SMS API Config (Fallback)
D7_TOKEN = os.getenv("D7_TOKEN")

MAX_YOUTUBE_DURATION = int(os.getenv("MAX_YOUTUBE_DURATION", "900"))  # 15 Minutes
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

# ----- EMAIL SENDER (RESEND API) -----

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

# ----- SMESS.IO WHATSAPP OTP SENDER -----

def send_smess_whatsapp_otp(phone_number, otp_code):
    """
    Sends WhatsApp OTP code using SMESS.io Gateway API
    """
    if not SMESS_API_KEY:
        print("❌ SMESS_API_KEY is not set in environment variables.")
        return False
    
    url = "https://smess.io/api/v2/send/whatsapp"
    
    # Ensure phone number formatting (Remove + if present)
    clean_phone = phone_number.replace("+", "").replace(" ", "").strip()
    
    payload = {
        "secret": SMESS_API_KEY,
        "account": SMESS_DEVICE_ID,
        "recipient": clean_phone,
        "type": "text",
        "message": f"🔒 Operational Security OTP Code:\n\nYour verification code is: *{otp_code}*\n\nDo not share this code with anyone."
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=12)
        res_data = response.json() if response.content else {}
        if response.status_code in [200, 201] and res_data.get("status") in [200, True, "success"]:
            print(f"✅ SMESS.io WhatsApp OTP Sent to {clean_phone}")
            return True
        else:
            print(f"❌ SMESS.io WhatsApp Error: {response.text}")
            # Fallback to D7 SMS if SMESS.io fails
            return send_d7_sms(phone_number, f"Your verification code is: {otp_code}")
    except Exception as e:
        print(f"❌ SMESS.io Request Exception: {e}")
        return send_d7_sms(phone_number, f"Your verification code is: {otp_code}")

# ----- FALLBACK D7 SMS SENDER -----

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

# ================= ADMIN SMS & WHATSAPP CONTROL =================

@bot.message_handler(func=lambda m: m.text in ["🟢 Open SMS", "🔴 CLOSE SMS"])
def sms_admin_manager(m):
    if not is_admin(m.from_user.id): return
    
    if m.text == "🟢 Open SMS":
        set_setting("sms_enabled", True)
        try:
            bot.send_message(m.chat.id, "🟢 WhatsApp / SMS Verification system is now OPEN. Users can choose Gmail or Phone/WhatsApp.")
        except: pass
    elif m.text == "🔴 CLOSE SMS":
        set_setting("sms_enabled", False)
        try:
            bot.send_message(m.chat.id, "🔴 WhatsApp / SMS Verification system is now CLOSED. Users will only use Gmail.")
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
                InlineKeyboardButton("💬 Verify via WhatsApp", callback_data="verify_choice_phone")
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
            msg = bot.send_message(call.message.chat.id, "Please send your WhatsApp Phone number with country code (e.g., +25261XXXXXXX or +2519XXXXXXX):", reply_markup=kb)
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
    cooldown = 60  # 1 minute
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

# ----- WHATSAPP (SMESS.IO) VERIFICATION LOGIC ----- #

def process_verification_phone(m):
    uid = str(m.from_user.id)
    phone_input = (m.text or "").strip().replace(" ", "")
    
    menu_buttons = ["👤 Profile", "👑 ADMIN PANEL", "💰 BALANCE", "💸 WITHDRAWAL", "👥 REFERRAL", "🆔 GET ID", "☎️ CUSTOMER", "🤖CUSTOMER AI", "🔙 BACK MAIN MENU", "💳 PAY"]
    if phone_input in menu_buttons or not phone_input.replace("+", "").isdigit() or len(phone_input) < 10:
        try:
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process"))
            msg = bot.send_message(m.chat.id, "❌ Invalid number. Please send a valid WhatsApp number with country code (e.g., +252... or +251...):", reply_markup=kb)
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
    
    success = send_smess_whatsapp_otp(phone_input, code)
    if success:
        try:
            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton("🔄 Resend WhatsApp OTP", callback_data="resend_phone_code"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process")
            )
            msg = bot.send_message(m.chat.id, f"💬 A 6-digit OTP code has been sent via WhatsApp to your number ({phone_input}). Please enter the code below:", reply_markup=kb)
            bot.register_next_step_handler(msg, process_phone_code)
            threading.Thread(target=delayed_cancel_session, args=(m.chat.id, msg.message_id, uid), daemon=True).start()
        except: pass
    else:
        try:
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process"))
            bot.send_message(m.chat.id, "❌ Failed to send WhatsApp OTP. Please try again later or check your phone number.", reply_markup=kb)
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
    cooldown = 120  # 2 minutes cooldown
    elapsed = current_time - last_resend_time
    
    if elapsed < cooldown:
        remaining = int(cooldown - elapsed)
        bot.answer_callback_query(call.id, f"⏳ Please wait {remaining}s before requesting another WhatsApp OTP.", show_alert=True)
        return
        
    data["last_resend"] = current_time
    phone = data["phone"]
    code = str(random.randint(100000, 999999))
    data["code"] = code
    
    success = send_smess_whatsapp_otp(phone, code)
    if success:
        bot.answer_callback_query(call.id, "✅ A new OTP code has been sent via WhatsApp!")
        try:
            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton("🔄 Resend WhatsApp OTP", callback_data="resend_phone_code"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process")
            )
            msg = bot.send_message(call.message.chat.id, f"💬 A new code has been sent to your WhatsApp number ({phone}). Please enter the code here:", reply_markup=kb)
            bot.register_next_step_handler(msg, process_phone_code)
            threading.Thread(target=delayed_cancel_session, args=(call.message.chat.id, msg.message_id, uid), daemon=True).start()
        except: pass
    else:
        bot.answer_callback_query(call.id, "❌ Error sending WhatsApp OTP, please try again later.", show_alert=True)

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
                InlineKeyboardButton("🔄 Resend WhatsApp OTP", callback_data="resend_phone_code"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process")
            )
            msg = bot.send_message(
                m.chat.id,
                "⚠️ <b>Action not allowed!</b>\n"
                "You must enter the 6-digit WhatsApp OTP code first.\n\n"
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
                InlineKeyboardButton("🔄 Resend WhatsApp OTP", callback_data="resend_phone_code"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process")
            )
            msg = bot.send_message(m.chat.id, "❌ Incorrect code. Please enter the correct code sent via WhatsApp:", reply_markup=kb)
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

# ================= USER BASIC COMMANDS & CORE FUNCTIONS =================

@bot.message_handler(commands=["start"])
def start_cmd(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    uid = str(m.from_user.id)
    args = m.text.split()
    
    if uid not in users:
        ref_by = None
        if len(args) > 1:
            possible_ref = args[1]
            for u, d in users.items():
                if d.get("ref_code") == possible_ref:
                    ref_by = u
                    break
        
        users[uid] = {
            "balance": 0.0,
            "ref_code": random_ref(),
            "bot_id": random_botid(),
            "referred_by": ref_by,
            "referrals": [],
            "quick_access": False,
            "banned": False,
            "verified": False,
            "sticker": "",
            "joined_date": datetime.now().strftime("%Y-%m-%d")
        }
        
        if ref_by and ref_by in users:
            users[ref_by].setdefault("referrals", []).append(uid)
            ref_bonus = float(get_setting("referral_price", 0.10))
            users[ref_by]["balance"] = users[ref_by].get("balance", 0.0) + ref_bonus
            save_user(ref_by)
            try:
                bot.send_message(int(ref_by), f"🎉 New referral joined using your link! You earned ${ref_bonus:.2f}")
            except: pass
            
        save_user(uid)

    text = (
        f"👋 Welcome <a href='tg://user?id={uid}'>{m.from_user.first_name}</a>!\n\n"
        f"Send me any video link from YouTube, TikTok, Facebook, Instagram, or Twitter to download."
    )
    bot.send_message(m.chat.id, text, reply_markup=user_menu(is_admin(uid)))

@bot.message_handler(func=lambda m: m.text == "💰 BALANCE")
def balance_cmd(m):
    if bot_locked_guard(m) or banned_guard(m): return
    uid = str(m.from_user.id)
    bal = users.get(uid, {}).get("balance", 0.0)
    bot.send_message(m.chat.id, f"💰 <b>Your Current Balance:</b> ${bal:.2f}")

@bot.message_handler(func=lambda m: m.text == "👥 REFERRAL")
def referral_cmd(m):
    if bot_locked_guard(m) or banned_guard(m): return
    uid = str(m.from_user.id)
    u_data = users.get(uid, {})
    ref_code = u_data.get("ref_code", "")
    bot_username = bot.get_me().username
    ref_link = f"https://t.me/{bot_username}?start={ref_code}"
    total_refs = len(u_data.get("referrals", []))
    
    text = (
        f"👥 <b>REFERRAL PROGRAM</b>\n\n"
        f"Share your referral link with friends and earn rewards!\n\n"
        f"🔗 <b>Link:</b> <code>{ref_link}</code>\n"
        f"📊 <b>Total Invited:</b> {total_refs}"
    )
    bot.send_message(m.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "🆔 GET ID")
def get_id_cmd(m):
    uid = str(m.from_user.id)
    bot_id = users.get(uid, {}).get("bot_id", "N/A")
    bot.send_message(m.chat.id, f"🆔 <b>Telegram ID:</b> <code>{uid}</code>\n🤖 <b>Bot System ID:</b> <code>{bot_id}</code>")

# ================= ADMIN PANEL HANDLERS =================

@bot.message_handler(func=lambda m: m.text == "👑 ADMIN PANEL")
def admin_panel_cmd(m):
    if not is_admin(m.from_user.id): return
    bot.send_message(m.chat.id, "👑 <b>Welcome to Admin Panel</b>", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == "📊 STATS")
def stats_cmd(m):
    if not is_admin(m.from_user.id): return
    total_users = len(users)
    total_downloads = videos_data.get("total", 0)
    text = (
        f"📊 <b>BOT SYSTEM STATS</b>\n\n"
        f"👥 Total Users: {total_users}\n"
        f"📥 Total Downloads: {total_downloads}\n"
    )
    bot.send_message(m.chat.id, text)

# ================= VIDEO DOWNLOAD ENGINE (YTDLP) =================

def process_video_download(message, url):
    uid = str(message.from_user.id)
    msg = bot.send_message(message.chat.id, "⏳ Processing your request... Please wait.")
    
    ydl_opts = {
        'format': 'best',
        'outtmpl': f'downloads/{uid}_%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            bot.edit_message_text("📤 Uploading video to Telegram...", message.chat.id, msg.message_id)
            
            with open(filename, 'rb') as video:
                bot.send_video(message.chat.id, video, caption=f"✅ Downloaded: {info.get('title', 'Video')}")
            
            bot.delete_message(message.chat.id, msg.message_id)
            
            # Clean up
            if os.path.exists(filename):
                os.remove(filename)
                
            # Stats Update
            videos_data["total"] = videos_data.get("total", 0) + 1
            videos_data["users"][uid] = videos_data.get("users", {}).get(uid, 0) + 1
            save_videos()

    except Exception as e:
        bot.edit_message_text(f"❌ Failed to download video: {str(e)}", message.chat.id, msg.message_id)

@bot.message_handler(func=lambda m: extract_url(m.text) is not None)
def handle_video_links(m):
    if bot_locked_guard(m) or banned_guard(m): return
    url = extract_url(m.text)
    
    if is_quick_access(m.from_user.id):
        vip_executor.submit(process_video_download, m, url)
    else:
        normal_executor.submit(process_video_download, m, url)

# ================= SYSTEM BOT INITIALIZATION =================

def run_telethon():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    if API_ID and API_HASH:
        try:
            tg_client.start(phone=PHONE)
            print("✅ Telethon Client Started Successfully.")
            tg_client.run_until_disconnected()
        except Exception as e:
            print(f"❌ Telethon Error: {e}")

if __name__ == "__main__":
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
        
    print("🚀 Starting Telegram Bot Engine...")
    
    # Run Telethon in background thread
    t_thread = threading.Thread(target=run_telethon, daemon=True)
    t_thread.start()
    
    # Run Telebot
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=30)
    except Exception as e:
        print(f"❌ Bot Polling Crashed: {e}")
