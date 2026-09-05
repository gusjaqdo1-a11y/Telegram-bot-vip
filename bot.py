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

# SMESS.io WhatsApp API Config (NEW)
SMESS_API_KEY = os.getenv("SMESS_API_KEY")

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
whatsapp_verify_pending = {} # NEW for WhatsApp
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

def extract_url(text):
    if not text:
        return None
    match = re.search(r'(https?://[^\s]+)', text)
    return match.group(0) if match else None

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

# NEW: SMESS.io WhatsApp Sender Function
def send_smess_whatsapp(phone_number, text):
    if not SMESS_API_KEY:
        print("❌ SMESS_API_KEY is not set in environment variables.")
        return False
    
    url = "https://api.smess.io/v1/whatsapp/send" # Halkan ka hubi URL-ka saxda ah ee SMESS.io
    headers = {
        "Authorization": f"Bearer {SMESS_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "to": phone_number,
        "message": text
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        print(f"SMESS Response Status: {response.status_code}")
        print(f"SMESS Response Body: {response.text}")
        
        if response.status_code in [200, 201]:
            return True
        else:
            return False
    except Exception as e:
        print(f"SMESS WHATSAPP EXCEPTION: {e}")
        return False



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
            bot.send_message(m.chat.id, "🟢 Verification system is now OPEN. Users can choose Gmail, Phone, or WhatsApp.")
        except: pass
    elif m.text == "🔴 CLOSE SMS":
        set_setting("sms_enabled", False)
        try:
            bot.send_message(m.chat.id, "🔴 Verification system is now CLOSED. Users will only use Gmail.")
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
            kb = InlineKeyboardMarkup(row_width=1)
            kb.add(
                InlineKeyboardButton("📧 Verify via Gmail", callback_data="verify_choice_gmail"),
                InlineKeyboardButton("📱 Verify via SMS (D7)", callback_data="verify_choice_phone"),
                InlineKeyboardButton("💬 Verify via WhatsApp", callback_data="verify_choice_whatsapp")
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
            msg = bot.send_message(call.message.chat.id, "Please send your phone number for SMS (e.g., +25261XXXXXXX):", reply_markup=kb)
            bot.register_next_step_handler(msg, process_verification_phone)
        elif choice == "whatsapp":
            msg = bot.send_message(call.message.chat.id, "Please send your WhatsApp number with country code (e.g., +25261XXXXXXX):", reply_markup=kb)
            bot.register_next_step_handler(msg, process_verification_whatsapp)
        bot.answer_callback_query(call.id)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "cancel_verify_process")
def cancel_verify_process(call):
    uid = str(call.from_user.id)
    email_verify_pending.pop(uid, None)
    phone_verify_pending.pop(uid, None)
    whatsapp_verify_pending.pop(uid, None)
    try:
        bot.edit_message_text("❌ Verification process cancelled.", call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.answer_callback_query(call.id, "Cancelled successfully!")
    except:
        pass

def delayed_cancel_session(chat_id, message_id, uid):
    time.sleep(60)
    if uid in email_verify_pending or uid in phone_verify_pending or uid in whatsapp_verify_pending:
        email_verify_pending.pop(uid, None)
        phone_verify_pending.pop(uid, None)
        whatsapp_verify_pending.pop(uid, None)
        try:
            bot.edit_message_text("❌ Verification session expired or cancelled after 1 minute.", chat_id, message_id, reply_markup=None)
        except:
            pass

# ----- WHATSAPP VERIFICATION LOGIC (NEW) ----- #

def process_verification_whatsapp(m):
    uid = str(m.from_user.id)
    phone_input = (m.text or "").strip().replace(" ", "")
    
    menu_buttons = ["👤 Profile", "👑 ADMIN PANEL", "💰 BALANCE", "💸 WITHDRAWAL", "👥 REFERRAL", "🆔 GET ID", "☎️ CUSTOMER", "🤖CUSTOMER AI", "🔙 BACK MAIN MENU", "💳 PAY"]
    if phone_input in menu_buttons or not phone_input.startswith("+") or len(phone_input) < 10:
        try:
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process"))
            msg = bot.send_message(m.chat.id, "❌ Invalid number. Please send a valid WhatsApp number with country code:", reply_markup=kb)
            bot.register_next_step_handler(msg, process_verification_whatsapp)
        except: pass
        return

    code = str(random.randint(100000, 999999))
    current_time = time.time()
    whatsapp_verify_pending[uid] = {
        "phone": phone_input,
        "code": code,
        "time": current_time,
        "last_resend": current_time
    }
    
    whatsapp_text = f"🔐 Your Downloader Bot Verification Code is: *{code}*\n\nPlease do not share this code with anyone."
    success = send_smess_whatsapp(phone_input, whatsapp_text)
    
    if success:
        try:
            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton("🔄 Resend WhatsApp", callback_data="resend_whatsapp_code"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process")
            )
            msg = bot.send_message(m.chat.id, f"💬 A 6-digit code has been sent via WhatsApp to ({phone_input}). Please enter the code below:", reply_markup=kb)
            bot.register_next_step_handler(msg, process_whatsapp_code)
            threading.Thread(target=delayed_cancel_session, args=(m.chat.id, msg.message_id, uid), daemon=True).start()
        except: pass
    else:
        try:
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process"))
            bot.send_message(m.chat.id, "❌ Failed to send WhatsApp message. Please try again later or check your number.", reply_markup=kb)
        except: pass

@bot.callback_query_handler(func=lambda call: call.data == "resend_whatsapp_code")
def resend_whatsapp_code_callback(call):
    uid = str(call.from_user.id)
    if uid not in whatsapp_verify_pending:
        bot.answer_callback_query(call.id, "❌ Session expired. Please start again from your profile.", show_alert=True)
        return
        
    data = whatsapp_verify_pending[uid]
    current_time = time.time()
    last_resend_time = data.get("last_resend", data.get("time", 0))
    cooldown = 60  # 1 min required for WhatsApp resend
    elapsed = current_time - last_resend_time
    
    if elapsed < cooldown:
        remaining = int(cooldown - elapsed)
        bot.answer_callback_query(call.id, f"⏳ Please wait {remaining}s before requesting another WhatsApp code.", show_alert=True)
        return
        
    data["last_resend"] = current_time
    phone = data["phone"]
    code = str(random.randint(100000, 999999))
    data["code"] = code
    
    whatsapp_text = f"🔐 Your New Verification Code is: *{code}*"
    success = send_smess_whatsapp(phone, whatsapp_text)
    if success:
        bot.answer_callback_query(call.id, "✅ A new code has been sent via WhatsApp!")
        try:
            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton("🔄 Resend WhatsApp", callback_data="resend_whatsapp_code"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process")
            )
            msg = bot.send_message(call.message.chat.id, f"💬 A new code has been sent to ({phone}). Please enter the code here:", reply_markup=kb)
            bot.register_next_step_handler(msg, process_whatsapp_code)
            threading.Thread(target=delayed_cancel_session, args=(call.message.chat.id, msg.message_id, uid), daemon=True).start()
        except: pass
    else:
        bot.answer_callback_query(call.id, "❌ Error sending WhatsApp message.", show_alert=True)

def process_whatsapp_code(m):
    uid = str(m.from_user.id)
    code_input = (m.text or "").strip()
    
    if uid not in whatsapp_verify_pending:
        try:
            bot.send_message(m.chat.id, "❌ Verification session expired. Please start again.")
        except: pass
        return

    menu_buttons = ["👤 Profile", "👑 ADMIN PANEL", "💰 BALANCE", "💸 WITHDRAWAL", "👥 REFERRAL", "🆔 GET ID", "☎️ CUSTOMER", "🤖CUSTOMER AI", "🔙 BACK MAIN MENU", "💳 PAY"]
    if code_input in menu_buttons or not code_input.isdigit() or len(code_input) != 6:
        try:
            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton("🔄 Resend WhatsApp", callback_data="resend_whatsapp_code"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process")
            )
            msg = bot.send_message(
                m.chat.id,
                "⚠️ <b>Action not allowed!</b>\nYou must enter the 6-digit WhatsApp code first.\n\nPlease enter the correct code:",
                reply_markup=kb
            )
            bot.register_next_step_handler(msg, process_whatsapp_code)
        except: pass
        return

    data = whatsapp_verify_pending[uid]
    if code_input == data["code"]:
        users[uid]["verified"] = True
        users[uid]["phone"] = data["phone"]
        if "sticker" not in users[uid] or not users[uid]["sticker"]:
            users[uid]["sticker"] = "🌟"
        save_user(uid)
        whatsapp_verify_pending.pop(uid, None)
        try:
            bot.send_message(m.chat.id, "✅ Congratulations! Your account is now Verified.", reply_markup=user_menu(is_admin(m.from_user.id)))
        except: pass
    else:
        try:
            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton("🔄 Resend WhatsApp", callback_data="resend_whatsapp_code"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process")
            )
            msg = bot.send_message(m.chat.id, "❌ Incorrect code. Please enter the correct code sent via WhatsApp:", reply_markup=kb)
            bot.register_next_step_handler(msg, process_whatsapp_code)
            threading.Thread(target=delayed_cancel_session, args=(m.chat.id, msg.message_id, uid), daemon=True).start()
        except: pass


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
            bot.send_message(m.chat.id, "❌ Verification session expired or already completed. Please start again.")
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
                "⚠️ <b>Action not allowed!</b>\nYou must enter the 6-digit code sent to your Gmail first.\n\nPlease enter the correct code:",
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
            bot.send_message(m.chat.id, "✅ Congratulations! Your account is now Verified.", reply_markup=user_menu(is_admin(m.from_user.id)))
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

# ----- PHONE VERIFICATION LOGIC (D7 SMS) ----- #

def process_verification_phone(m):
    uid = str(m.from_user.id)
    phone_input = (m.text or "").strip().replace(" ", "")
    
    menu_buttons = ["👤 Profile", "👑 ADMIN PANEL", "💰 BALANCE", "💸 WITHDRAWAL", "👥 REFERRAL", "🆔 GET ID", "☎️ CUSTOMER", "🤖CUSTOMER AI", "🔙 BACK MAIN MENU", "💳 PAY"]
    if phone_input in menu_buttons or not phone_input.startswith("+") or len(phone_input) < 10:
        try:
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process"))
            msg = bot.send_message(m.chat.id, "❌ Invalid number. Please send a valid phone number with country code (e.g., +252...):", reply_markup=kb)
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
    cooldown = 600  # 10 minutes required for SMS
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
                "⚠️ <b>Action not allowed!</b>\nYou must enter the 6-digit SMS code first.\n\nPlease enter the correct code:",
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
            bot.send_message(m.chat.id, "✅ Congratulations! Your account is now Verified.", reply_markup=user_menu(is_admin(m.from_user.id)))
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


# [BINTA KALE EE ADMIN PANEL/VERIFICATION ETC WAA SIDII HORE (LAGA BOODAY INAAN BADALO SI AAN WAX LOOGA TAGIN)]

@bot.message_handler(func=lambda m: m.text == "✅ Verified Users")
def verified_users_list(m):
    if not is_admin(m.from_user.id): return
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
    if not is_admin(m.from_user.id): return
    try:
        msg = bot.send_message(m.chat.id, "Send User ID or BOT ID and the sticker/badge separated by pipe (|)\nExample:\n123456789 | 🌟 Verified")
        bot.register_next_step_handler(msg, sticker_admin_process)
    except: pass

def sticker_admin_process(m):
    if not is_admin(m.from_user.id): return
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
    except Exception as e:
        print(f"Download error: {e}")
        try:
            bot.edit_message_text(f"❌ Failed to download media. Error: {str(e)[:100]}", chat_id, message_id)
        except: pass
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ================= LINK HANDLER & BOT START PROCESS =================

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

# --- (Qaybtii go'day oo la dhammaystiray) ---

@bot.message_handler(func=lambda m: True)
def catch_all_messages(message):
    if bot_locked_guard(message) or banned_guard(message):
        return
    # This acts as a fallback for any other unhandled text messages
    pass

def start_bot_1():
    print("🤖 Downloader Bot is running...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

def start_bot_2():
    if BOT2_TOKEN:
        print("🤖 Verification Bot 2 is running...")
        bot2.infinity_polling(timeout=10, long_polling_timeout=5)

if __name__ == "__main__":
    # Start bot2 in a separate thread if token exists
    if BOT2_TOKEN:
        threading.Thread(target=start_bot_2, daemon=True).start()
    
    # Start the main bot in the main thread
    start_bot_1()

