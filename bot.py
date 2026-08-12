import telebot
import requests
from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
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

tg_client = TelegramClient(
    "session",
    API_ID,
    API_HASH
).start(bot_token=TOKEN)

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

VERIFY_ENABLED = False
verify_pending = {}
verify_method = {}
video_store = {}
video_files = {}

ADS_ENABLED = False
ADS_TEXT = ""         
ADS_BTN_TEXT = ""     
ADS_URL = "" 

# ================= DATABASE FILES =================
USERS_FILE = "users.json"
WITHDRAWS_FILE = "withdraws.json"
VIDEOS_FILE = "videos.json"

# PREMIUM & ADVANCED MODULE FILES
PREMIUM_FILE = "premium.json"
PAYMENTS_FILE = "payments.json"
REFERRALS_FILE = "referrals.json"
REFERRAL_REWARDS_FILE = "referral_rewards.json"
REFERRAL_MILESTONES_FILE = "referral_milestones.json"
FEATURE_REQUESTS_FILE = "feature_requests.json"
FEATURE_VOTES_FILE = "feature_votes.json"
LEADERBOARD_FILE = "leaderboard.json"
MISSIONS_FILE = "missions.json"
MISSION_PROGRESS_FILE = "mission_progress.json"
COUPONS_FILE = "coupons.json"
COUPON_USAGE_FILE = "coupon_usage.json"
GIFT_PREMIUM_FILE = "gift_premium.json"
VIP_IDENTITY_FILE = "vip_identity.json"
USER_SETTINGS_FILE = "user_settings.json"

# ================= JSON FUNCTIONS =================
def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

# ================= LOAD ALL DATABASES =================
users = load_json(USERS_FILE, {})
withdraws = load_json(WITHDRAWS_FILE, [])

videos_data = load_json(VIDEOS_FILE, {
    "total": 0,
    "platforms": {
        "tiktok": 0,
        "youtube": 0,
        "facebook": 0,
        "pinterest": 0
    },
    "users": {}
})

premium_db = load_json(PREMIUM_FILE, {}) # {user_id: {"plan": str, "duration": int, "start_date": str, "expiry_date": str, "status": "ACTIVE"/"INACTIVE"}}
payments_db = load_json(PAYMENTS_FILE, [])
referrals_db = load_json(REFERRALS_FILE, {}) # {user_id: [referred_user_ids]}
referral_rewards_db = load_json(REFERRAL_REWARDS_FILE, {}) # {user_id: [claimed_milestones]}
referral_milestones_db = load_json(REFERRAL_MILESTONES_FILE, {
    3: "⭐ 3 Days",
    5: "⭐ 7 Days",
    10: "⭐ 15 Days",
    25: "⭐ 30 Days",
    50: "⭐ 90 Days"
})
feature_requests_db = load_json(FEATURE_REQUESTS_FILE, [])
feature_votes_db = load_json(FEATURE_VOTES_FILE, {}) # {request_id: [user_ids]}
leaderboard_db = load_json(LEADERBOARD_FILE, {}) # {user_id: points}
missions_db = load_json(MISSIONS_FILE, [
    {"id": "m1", "type": "daily", "title": "📥 Download 10 Files", "target": 10, "reward": "⭐ 1 Day"},
    {"id": "m2", "type": "daily", "title": "🎁 Invite 3 Friends", "target": 3, "reward": "⭐ 2 Days"},
    {"id": "m3", "type": "special", "title": "💡 Vote on 3 Features", "target": 3, "reward": "⭐ 1 Day"}
])
mission_progress_db = load_json(MISSION_PROGRESS_FILE, {}) # {user_id: {mission_id: progress_int}}
coupons_db = load_json(COUPONS_FILE, {
    "VIP2026": {"reward_days": 30, "max_uses": 100, "uses": 0, "active": True}
})
coupon_usage_db = load_json(COUPON_USAGE_FILE, {}) # {user_id: [coupon_codes]}
gift_premium_db = load_json(GIFT_PREMIUM_FILE, [])
vip_identity_db = load_json(VIP_IDENTITY_FILE, {}) # {user_id: {"title": "💎 PRO", "level": 1, "points": 0, "since": str}}
user_settings_db = load_json(USER_SETTINGS_FILE, {})

def save_users():
    save_json(USERS_FILE, users)

def save_withdraws():
    save_json(WITHDRAWS_FILE, withdraws)

def save_videos():
    save_json(VIDEOS_FILE, videos_data)

def save_premium():
    save_json(PREMIUM_FILE, premium_db)

def save_payments():
    save_json(PAYMENTS_FILE, payments_db)

def save_referrals():
    save_json(REFERRALS_FILE, referrals_db)

def save_referral_rewards():
    save_json(REFERRAL_REWARDS_FILE, referral_rewards_db)

def save_referral_milestones():
    save_json(REFERRAL_MILESTONES_FILE, referral_milestones_db)

def save_feature_requests():
    save_json(FEATURE_REQUESTS_FILE, feature_requests_db)

def save_feature_votes():
    save_json(FEATURE_VOTES_FILE, feature_votes_db)

def save_leaderboard():
    save_json(LEADERBOARD_FILE, leaderboard_db)

def save_missions():
    save_json(MISSIONS_FILE, missions_db)

def save_mission_progress():
    save_json(MISSION_PROGRESS_FILE, mission_progress_db)

def save_coupons():
    save_json(COUPONS_FILE, coupons_db)

def save_coupon_usage():
    save_json(COUPON_USAGE_FILE, coupon_usage_db)

def save_gift_premium():
    save_json(GIFT_PREMIUM_FILE, gift_premium_db)

def save_vip_identity():
    save_json(VIP_IDENTITY_FILE, vip_identity_db)

def save_user_settings():
    save_json(USER_SETTINGS_FILE, user_settings_db)

# ================= CONFIGURABLE PREMIUM PLANS =================
PREMIUM_PLANS = {
    "7_days": {"name": "7 Days", "days": 7, "stars": 50},
    "30_days": {"name": "30 Days", "days": 30, "stars": 150},
    "90_days": {"name": "90 Days", "days": 90, "stars": 350},
    "1_year": {"name": "1 Year", "days": 365, "stars": 1000}
}

# ================= HELPER FUNCTIONS =================
def random_ref():
    return str(random.randint(1000000000, 9999999999))

def random_botid():
    return str(random.randint(10000000000, 99999999999))

def now_month():
    return datetime.now().month

def is_admin(uid):
    return int(uid) in ADMIN_IDS

def find_user_by_botid(bid):
    for u, data in users.items():
        if data.get("bot_id") == bid:
            return u
    return None

def banned_guard(m):
    uid = str(m.from_user.id)
    if uid in users and users[uid].get("banned"):
        bot.send_message(m.chat.id, "🚫 You are banned.")
        return True
    return False

def bot_locked_guard(message):
    global BOT_LOCKED, LOCK_MESSAGE
    if BOT_LOCKED and not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, LOCK_MESSAGE)
        return True
    return False

def is_premium(uid):
    uid_str = str(uid)
    if uid_str not in premium_db:
        return False
    p = premium_db[uid_str]
    if p.get("status") != "ACTIVE":
        return False
    expiry = datetime.strptime(p["expiry_date"], "%Y-%m-%d %H:%M:%S")
    if datetime.now() > expiry:
        p["status"] = "INACTIVE"
        save_premium()
        try:
            bot.send_message(
                int(uid),
                "⏰ Your Premium has expired.\n\n⭐ Renew Premium to continue using VIP features.",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("⭐ Renew Premium", callback_data="prem_buy_menu"),
                    InlineKeyboardButton("🏠 Home", callback_data="home_menu")
                )
            )
        except:
            pass
        return False
    return True

def add_user_points(uid, pts):
    uid_str = str(uid)
    leaderboard_db[uid_str] = leaderboard_db.get(uid_str, 0) + pts
    save_leaderboard()
    if uid_str in vip_identity_db:
        vip_identity_db[uid_str]["points"] = vip_identity_db[uid_str].get("points", 0) + pts
        # Level up logic every 100 points
        new_level = (vip_identity_db[uid_str]["points"] // 100) + 1
        vip_identity_db[uid_str]["level"] = new_level
        save_vip_identity()

def check_mission_progress(uid, mission_type, count=1):
    uid_str = str(uid)
    if uid_str not in mission_progress_db:
        mission_progress_db[uid_str] = {}
    
    for m in missions_db:
        if m["type"] == mission_type:
            mid = m["id"]
            current = mission_progress_db[uid_str].get(mid, 0)
            if current < m["target"]:
                current += count
                mission_progress_db[uid_str][mid] = current
                save_mission_progress()

# ================= MENUS =================
def user_menu(show_admin=False):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💰 BALANCE", "💸 WITHDRAWAL")
    kb.add("👑 PREMIUM", "👥 REFERRAL")
    kb.add("🆔 GET ID", "☎️ CUSTOMER")
    kb.add("🤖CUSTOMER AI")
    if show_admin:
        kb.add("👑 ADMIN PANEL")
    return kb

def admin_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📊 STATS", "📢 BROADCAST")
    kb.add("➕ ADD BALANCE", "➖ REMOVE MONEY")
    kb.add("🚫 BAN USER MANUAL", "💳 WITHDRAWAL CHECK")
    kb.add("💰 UNBLOCK MONEY", "🔍 RAADI")
    kb.add("🔥 UN BAN-USER", "📌 POST CHANNEL")
    kb.add("👥 SEE LIST", "🔎 SEARCH USER")
    kb.add("📢 ADD ADS", "🗑 DELETE ADS")
    kb.add("✅ VERIFY ON", "❌ VERIFY OFF")
    kb.add("CHANNEL POST", "📡 ADD CHANNEL")
    kb.add("🔒 LOCK BOT", "🔓 UNLOCK BOT")  
    kb.add("❌ CLOSE WINDOWS", "CLOSE CHANNEL POST")
    kb.add("📥 IMPORT USERS")
    kb.add("🔗 GET REFERRAL CODE")
    kb.add("👑 PREMIUM MANAGEMENT", "🎁 REFERRAL MGMT")
    kb.add("💡 FEATURE MGMT", "🏆 LEADERBOARD MGMT")
    kb.add("🎯 MISSIONS MGMT", "🎟 COUPONS MGMT")
    kb.add("🎁 GIFT MGMT", "👑 VIP ID MGMT")
    kb.add("💳 STARS PAYMENTS", "📊 PREMIUM STATS")
    kb.add("🔙 BACK MAIN MENU")
    return kb

def back_to_main_menu(m):
    uid = str(m.from_user.id)
    bot.send_message(
        m.chat.id,
        "🔙 Returning to main menu",
        reply_markup=user_menu(is_admin(uid))
    )

@bot.message_handler(func=lambda m: m.text == "🔙 BACK MAIN MENU")
def back_button_handler(m):
    back_to_main_menu(m)

CHANNEL_USERNAME = "@tiktokvediodownload"

# ================= START HANDLER =================
@bot.message_handler(commands=['start'])
def start_handler(message):
    if bot_locked_guard(message):
        return

    uid = str(message.from_user.id)
    args = message.text.split()

    if uid not in users:
        ref = args[1] if len(args) > 1 else None
        users[uid] = {
            "username": message.from_user.username or "",
            "balance": 0.0,
            "blocked": 0.0,
            "ref": random_ref(),
            "bot_id": random_botid(),
            "invited": 0,
            "banned": False,
            "verified": False,
            "month": now_month()
        }
        
        # Initialize VIP identity
        if uid not in vip_identity_db:
            vip_identity_db[uid] = {
                "title": "VIP",
                "level": 1,
                "points": 10,
                "since": datetime.now().strftime("%Y-%m-%d")
            }
            save_vip_identity()

        # Referral handling
        if ref:
            ref_user = next((u for u, d in users.items() if d["ref"] == ref), None)
            if ref_user and ref_user != uid:
                users[ref_user]["balance"] += 0.2
                users[ref_user]["invited"] += 1
                
                if ref_user not in referrals_db:
                    referrals_db[ref_user] = []
                if uid not in referrals_db[ref_user]:
                    referrals_db[ref_user].append(uid)
                    save_referrals()
                
                add_user_points(ref_user, 10)
                check_mission_progress(ref_user, "daily", 0) # Trigger checks if needed
                
                bot.send_message(int(ref_user), "🎉 You earned $0.2 from referral!")
                
                # Check referral milestones
                inv_count = len(referrals_db[ref_user])
                if inv_count in referral_milestones_db:
                    if ref_user not in referral_rewards_db:
                        referral_rewards_db[ref_user] = []
                    milestone_key = f"milestone_{inv_count}"
                    if milestone_key not in referral_rewards_db[ref_user]:
                        referral_rewards_db[ref_user].append(milestone_key)
                        save_referral_rewards()
                        bot.send_message(int(ref_user), f"🎁 Congratulations! You reached {inv_count} referrals milestone and earned {referral_milestones_db[inv_count]}!")

        save_users()

    check_membership(int(uid))

@bot.callback_query_handler(func=lambda call: call.data == "home_menu")
def home_menu_callback(call):
    uid = str(call.from_user.id)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(
        call.message.chat.id,
        "🏠 Main Menu",
        reply_markup=user_menu(is_admin(uid))
    )

# ================= 1. PREMIUM SYSTEM =================
@bot.message_handler(func=lambda m: m.text == "👑 PREMIUM")
def premium_center_handler(m):
    if bot_locked_guard(m):
        return
    if banned_guard(m):
        return
    uid = str(m.from_user.id)
    
    status_str = "ACTIVE" if is_premium(uid) else "INACTIVE"
    plan_name = "None"
    expiry_str = "N/A"
    days_left = 0
    
    if uid in premium_db and premium_db[uid].get("status") == "ACTIVE":
        plan_name = premium_db[uid].get("plan", "30 Days")
        expiry_date_obj = datetime.strptime(premium_db[uid]["expiry_date"], "%Y-%m-%d %H:%M:%S")
        expiry_str = expiry_date_obj.strftime("%d %b %Y")
        days_left = max(0, (expiry_date_obj - datetime.now()).days)

    text = f"""╭━━━ 👑 PREMIUM CENTER ━━━╮

⭐ Status: {status_str}
💎 Plan: {plan_name}
📅 Expires: {expiry_str}
⏳ Days Left: {days_left}

✨ Unlock the full Premium experience!
╰━━━━━━━━━━━━━━━━━━━━━━╯"""

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⭐ Buy Premium", callback_data="prem_buy_menu"),
        InlineKeyboardButton("💎 My Plan", callback_data="prem_my_plan")
    )
    kb.add(
        InlineKeyboardButton("⚙️ Premium Settings", callback_data="prem_settings"),
        InlineKeyboardButton("📊 My Statistics", callback_data="prem_my_stats")
    )
    kb.add(
        InlineKeyboardButton("🎁 Invite Friends", callback_data="prem_invite"),
        InlineKeyboardButton("💡 Feature Requests", callback_data="prem_features")
    )
    kb.add(
        InlineKeyboardButton("🏆 Leaderboard", callback_data="prem_leaderboard"),
        InlineKeyboardButton("🎯 Missions", callback_data="prem_missions")
    )
    kb.add(
        InlineKeyboardButton("🎟️ Coupons", callback_data="prem_coupons"),
        InlineKeyboardButton("🎁 Gift Premium", callback_data="prem_gift")
    )
    kb.add(
        InlineKeyboardButton("👑 My VIP Identity", callback_data="prem_vip_id"),
        InlineKeyboardButton("🔙 Back", callback_data="home_menu")
    )

    bot.send_message(m.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "prem_buy_menu")
def callback_prem_buy(call):
    kb = InlineKeyboardMarkup(row_width=2)
    for key, plan in PREMIUM_PLANS.items():
        kb.add(InlineKeyboardButton(f"⭐ {plan['name']} — {plan['stars']} Stars", callback_data=f"buyplan_{key}"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="prem_back_center"))
    
    bot.edit_message_text(
        "⭐ <b>Choose a Premium Plan</b>\n\nPay securely using Telegram Stars to unlock all VIP features instantly.",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=kb,
        parse_mode="HTML"
    )

@bot.callback_query_handler(func=lambda call: call.data == "prem_back_center")
def callback_prem_back(call):
    uid = str(call.from_user.id)
    status_str = "ACTIVE" if is_premium(uid) else "INACTIVE"
    plan_name = "None"
    expiry_str = "N/A"
    days_left = 0
    
    if uid in premium_db and premium_db[uid].get("status") == "ACTIVE":
        plan_name = premium_db[uid].get("plan", "30 Days")
        expiry_date_obj = datetime.strptime(premium_db[uid]["expiry_date"], "%Y-%m-%d %H:%M:%S")
        expiry_str = expiry_date_obj.strftime("%d %b %Y")
        days_left = max(0, (expiry_date_obj - datetime.now()).days)

    text = f"""╭━━━ 👑 PREMIUM CENTER ━━━╮

⭐ Status: {status_str}
💎 Plan: {plan_name}
📅 Expires: {expiry_str}
⏳ Days Left: {days_left}

✨ Unlock the full Premium experience!
╰━━━━━━━━━━━━━━━━━━━━━━╯"""

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⭐ Buy Premium", callback_data="prem_buy_menu"),
        InlineKeyboardButton("💎 My Plan", callback_data="prem_my_plan")
    )
    kb.add(
        InlineKeyboardButton("⚙️ Premium Settings", callback_data="prem_settings"),
        InlineKeyboardButton("📊 My Statistics", callback_data="prem_my_stats")
    )
    kb.add(
        InlineKeyboardButton("🎁 Invite Friends", callback_data="prem_invite"),
        InlineKeyboardButton("💡 Feature Requests", callback_data="prem_features")
    )
    kb.add(
        InlineKeyboardButton("🏆 Leaderboard", callback_data="prem_leaderboard"),
        InlineKeyboardButton("🎯 Missions", callback_data="prem_missions")
    )
    kb.add(
        InlineKeyboardButton("🎟️ Coupons", callback_data="prem_coupons"),
        InlineKeyboardButton("🎁 Gift Premium", callback_data="prem_gift")
    )
    kb.add(
        InlineKeyboardButton("👑 My VIP Identity", callback_data="prem_vip_id"),
        InlineKeyboardButton("🔙 Back", callback_data="home_menu")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("buyplan_"))
def callback_buy_plan(call):
    plan_key = call.data.split("_", 1)[1]
    if plan_key not in PREMIUM_PLANS:
        bot.answer_callback_query(call.id, "❌ Invalid plan")
        return
    
    plan = PREMIUM_PLANS[plan_key]
    title = f"Premium Access - {plan['name']}"
    description = f"Unlock VIP Downloader features for {plan['name']}."
    prices = [LabeledPrice(label=plan['name'], amount=plan['stars'])]
    
    try:
        bot.send_invoice(
            chat_id=call.message.chat.id,
            title=title,
            description=description,
            invoice_payload=f"premium_{plan_key}_{call.from_user.id}",
            provider_token="", # Empty token for Telegram Stars
            currency="XTR",
            prices=prices
        )
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Error creating invoice: {e}", show_alert=True)

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout_handler(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def successful_payment_handler(message):
    payment = message.successful_payment
    payload = payment.invoice_payload
    uid = str(message.from_user.id)
    
    if payload.startswith("premium_"):
        parts = payload.split("_")
        plan_key = parts[1]
        if plan_key in PREMIUM_PLANS:
            plan = PREMIUM_PLANS[plan_key]
            days = plan["days"]
            stars = plan["stars"]
            
            start_date = datetime.now()
            if uid in premium_db and premium_db[uid].get("status") == "ACTIVE":
                current_expiry = datetime.strptime(premium_db[uid]["expiry_date"], "%Y-%m-%d %H:%M:%S")
                if current_expiry > start_date:
                    start_date = current_expiry
            
            expiry_date = start_date + timedelta(days=days)
            
            premium_db[uid] = {
                "plan": plan["name"],
                "duration": days,
                "stars_amount": stars,
                "payment_id": payment.telegram_payment_charge_id,
                "start_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "expiry_date": expiry_date.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "ACTIVE",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            save_premium()
            
            payments_db.append({
                "user_id": uid,
                "plan": plan["name"],
                "stars": stars,
                "payment_id": payment.telegram_payment_charge_id,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            save_payments()
            
            add_user_points(uid, 50)
            
            bot.send_message(
                message.chat.id,
                f"🎉 <b>Payment Successful!</b>\n\nYour Premium subscription for <b>{plan['name']}</b> is now active until {expiry_date.strftime('%d %b %Y')}! 👑",
                parse_mode="HTML"
            )
            
    elif payload.startswith("gift_"):
        parts = payload.split("_")
        recipient_id = parts[1]
        plan_key = parts[2]
        if plan_key in PREMIUM_PLANS:
            plan = PREMIUM_PLANS[plan_key]
            days = plan["days"]
            stars = plan["stars"]
            
            start_date = datetime.now()
            if recipient_id in premium_db and premium_db[recipient_id].get("status") == "ACTIVE":
                current_expiry = datetime.strptime(premium_db[recipient_id]["expiry_date"], "%Y-%m-%d %H:%M:%S")
                if current_expiry > start_date:
                    start_date = current_expiry
            
            expiry_date = start_date + timedelta(days=days)
            
            premium_db[recipient_id] = {
                "plan": plan["name"],
                "duration": days,
                "stars_amount": stars,
                "payment_id": payment.telegram_payment_charge_id,
                "start_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "expiry_date": expiry_date.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "ACTIVE",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            save_premium()
            
            gift_record = {
                "sender_id": uid,
                "recipient_id": recipient_id,
                "plan": plan["name"],
                "stars_amount": stars,
                "payment_id": payment.telegram_payment_charge_id,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "completed"
            }
            gift_premium_db.append(gift_record)
            save_gift_premium()
            
            bot.send_message(message.chat.id, f"✅ Gift successfully sent to user `{recipient_id}`!", parse_mode="HTML")
            try:
                bot.send_message(
                    int(recipient_id),
                    f"╭━━━ 🎁 PREMIUM GIFT ━━━╮\n\n🎉 You received Premium!\n\n💎 Plan: {plan['name']}\n📅 Expires: {expiry_date.strftime('%d %b %Y')}\n\nEnjoy your Premium experience! 👑\n╰━━━━━━━━━━━━━━━━━━━━━━╯",
                    parse_mode="HTML"
                )
            except:
                pass

@bot.callback_query_handler(func=lambda call: call.data == "prem_my_plan")
def callback_my_plan(call):
    uid = str(call.from_user.id)
    if not is_premium(uid):
        bot.answer_callback_query(call.id, "❌ You do not have an active Premium subscription.", show_alert=True)
        return
    p = premium_db[uid]
    text = f"""╭━━━ 💎 MY PLAN DETAILS ━━━╮

⭐ Status: ACTIVE
💎 Plan: {p['plan']}
📅 Started: {p['start_date']}
📅 Expires: {p['expiry_date']}
💳 Stars Paid: {p.get('stars_amount', 'N/A')}

╰━━━━━━━━━━━━━━━━━━━━━━╯"""
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="prem_back_center"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "prem_settings")
def callback_prem_settings(call):
    uid = str(call.from_user.id)
    if not is_premium(uid):
        bot.answer_callback_query(call.id, "❌ Premium feature only.", show_alert=True)
        return
    text = "⚙️ <b>Premium Settings</b>\n\nConfigure your exclusive preferences and VIP automation here."
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="prem_back_center"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "prem_my_stats")
def callback_prem_my_stats(call):
    uid = str(call.from_user.id)
    v_count = videos_data.get("users", {}).get(uid, 0)
    ref_count = len(referrals_db.get(uid, []))
    pts = leaderboard_db.get(uid, 0)
    text = f"""📊 <b>Your Statistics</b>

🎬 Total Downloads: {v_count}
👥 Referrals Invited: {ref_count}
🏆 Leaderboard Points: {pts}
"""
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="prem_back_center"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

# ================= 2. REFERRAL & REWARDS =================
@bot.callback_query_handler(func=lambda call: call.data == "prem_invite")
def callback_prem_invite(call):
    uid = str(call.from_user.id)
    bot_username = bot.get_me().username
    ref_code = users.get(uid, {}).get("ref", "123456")
    link = f"https://t.me/{bot_username}?start={ref_code}"
    referrals_count = len(referrals_db.get(uid, []))
    
    rank = "#--"
    sorted_lb = sorted(leaderboard_db.items(), key=lambda x: x[1], reverse=True)
    for i, (u, p) in enumerate(sorted_lb, 1):
        if u == uid:
            rank = f"#{i}"
            break

    text = f"""╭━━━ 🎁 INVITE & EARN ━━━╮

👥 Referrals: {referrals_count}
🎁 Rewards: ⭐ Active Milestones
🏆 Rank: {rank}

Invite your friends and earn rewards!
╰━━━━━━━━━━━━━━━━━━━━━━╯

🔗 Your Link:
<code>{link}</code>"""

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={link}&text=Download%20videos%20easily%20with%20this%20bot!"),
        InlineKeyboardButton("👥 My Referrals", callback_data="ref_my_list")
    )
    kb.add(
        InlineKeyboardButton("🎁 My Rewards", callback_data="ref_my_rewards"),
        InlineKeyboardButton("🏆 My Rank", callback_data="prem_leaderboard")
    )
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="prem_back_center"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "ref_my_list")
def callback_ref_list(call):
    uid = str(call.from_user.id)
    refs = referrals_db.get(uid, [])
    text = f"👥 <b>Your Referrals ({len(refs)})</b>\n\n"
    if not refs:
        text += "No referrals yet. Share your link to start earning!"
    else:
        for r_id in refs[:15]:
            text += f"• User ID: <code>{r_id}</code>\n"
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="prem_invite"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "ref_my_rewards")
def callback_ref_rewards(call):
    uid = str(call.from_user.id)
    claimed = referral_rewards_db.get(uid, [])
    text = "🎁 <b>Your Referral Rewards & Milestones</b>\n\n"
    for count, reward in referral_milestones_db.items():
        status = "✅ Claimed" if f"milestone_{count}" in claimed else "⏳ Locked"
        text += f"• {count} Referrals ➔ {reward} ({status})\n"
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="prem_invite"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

# ================= 3. FEATURE REQUESTS =================
@bot.callback_query_handler(func=lambda call: call.data == "prem_features")
def callback_prem_features(call):
    uid = str(call.from_user.id)
    if not is_premium(uid) and not is_admin(uid):
        bot.answer_callback_query(call.id, "🔒 Feature Requests are exclusively for Premium VIP users!", show_alert=True)
        return

    text = "╭━━━ 💡 FEATURE REQUESTS ━━━╮\n\n🔥 MOST REQUESTED\n\n"
    sorted_reqs = sorted(feature_requests_db, key=lambda x: x.get("votes", 0), reverse=True)
    
    if not sorted_reqs:
        text += "No feature requests submitted yet."
    else:
        for idx, req in enumerate(sorted_reqs[:5], 1):
            text += f"{idx}️⃣ {req['title']}\n👍 {req.get('votes', 0)} Votes — [{req.get('status', '🟡 Pending')}]\n\n"
    text += "╰━━━━━━━━━━━━━━━━━━━━━━╯"

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💡 Submit Feature", callback_data="feat_submit"),
        InlineKeyboardButton("👍 Vote Feature", callback_data="feat_vote_menu")
    )
    kb.add(
        InlineKeyboardButton("📋 My Requests", callback_data="feat_my_list"),
        InlineKeyboardButton("🔥 Most Requested", callback_data="prem_features")
    )
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="prem_back_center"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "feat_submit")
def callback_feat_submit(call):
    msg = bot.send_message(call.message.chat.id, "✍️ Send the title of your feature request:")
    bot.register_next_step_handler(msg, process_feature_title)

def process_feature_title(m):
    title = (m.text or "").strip()
    if not title:
        bot.send_message(m.chat.id, "❌ Title cannot be empty.")
        return
    msg = bot.send_message(m.chat.id, "📝 Now send a short description for your feature request:")
    bot.register_next_step_handler(msg, lambda x: process_feature_desc(x, title))

def process_feature_desc(m, title):
    desc = (m.text or "").strip()
    uid = str(m.from_user.id)
    req_id = str(random.randint(10000, 99999))
    
    feature_requests_db.append({
        "request_id": req_id,
        "user_id": uid,
        "title": title,
        "description": desc,
        "votes": 0,
        "status": "🟡 Pending",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    save_feature_requests()
    check_mission_progress(uid, "special", 1)
    
    bot.send_message(m.chat.id, "✅ Feature request submitted successfully! Admins will review it.")

@bot.callback_query_handler(func=lambda call: call.data == "feat_vote_menu")
def callback_feat_vote_menu(call):
    kb = InlineKeyboardMarkup(row_width=1)
    for req in feature_requests_db[:10]:
        kb.add(InlineKeyboardButton(f"👍 Vote: {req['title']} ({req['votes']})", callback_data=f"vote_{req['request_id']}"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="prem_features"))
    bot.edit_message_text("👍 Select a feature request to vote:", call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("vote_"))
def callback_vote_action(call):
    req_id = call.data.split("_")[1]
    uid = str(call.from_user.id)
    
    if req_id not in feature_votes_db:
        feature_votes_db[req_id] = []
        
    if uid in feature_votes_db[req_id]:
        bot.answer_callback_query(call.id, "⚠️ You have already voted for this feature.", show_alert=True)
        return
        
    feature_votes_db[req_id].append(uid)
    save_feature_votes()
    
    for req in feature_requests_db:
        if req["request_id"] == req_id:
            req["votes"] += 1
            save_feature_requests()
            break
            
    bot.answer_callback_query(call.id, "✅ Vote recorded successfully!")
    callback_prem_features(call)

@bot.callback_query_handler(func=lambda call: call.data == "feat_my_list")
def callback_feat_my_list(call):
    uid = str(call.from_user.id)
    my_reqs = [r for r in feature_requests_db if r["user_id"] == uid]
    text = "📋 <b>Your Feature Requests</b>\n\n"
    if not my_reqs:
        text += "You have not submitted any features yet."
    else:
        for r in my_reqs:
            text += f"• {r['title']} [{r['status']}] — 👍 {r['votes']} Votes\n"
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="prem_features"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

# ================= 4. PREMIUM LEADERBOARD =================
@bot.callback_query_handler(func=lambda call: call.data == "prem_leaderboard")
def callback_prem_leaderboard(call):
    uid = str(call.from_user.id)
    sorted_lb = sorted(leaderboard_db.items(), key=lambda x: x[1], reverse=True)
    
    medals = ["🥇", "🥈", "🥉"]
    text = "╭━━━ 🏆 PREMIUM LEADERBOARD ━━━╮\n\n"
    
    for idx, (u_id, pts) in enumerate(sorted_lb[:3], 1):
        medal = medals[idx-1]
        user_name = users.get(u_id, {}).get("username", u_id)
        text += f"{medal} @{user_name or u_id} — {pts} Points\n"
        
    text += "\n━━━━━━━━━━━━━━━━━━\n\n⭐ YOUR POSITION\n"
    
    my_rank = "#--"
    my_pts = leaderboard_db.get(uid, 0)
    for idx, (u_id, pts) in enumerate(sorted_lb, 1):
        if u_id == uid:
            my_rank = f"#{idx}"
            break
            
    text += f"Rank: {my_rank}\nPoints: {my_pts}\n\n╰━━━━━━━━━━━━━━━━━━━━━━╯"
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📊 My Rank", callback_data="prem_leaderboard"),
        InlineKeyboardButton("🎁 My Rewards", callback_data="ref_my_rewards")
    )
    kb.add(
        InlineKeyboardButton("📅 Weekly", callback_data="lb_filter_weekly"),
        InlineKeyboardButton("📆 Monthly", callback_data="lb_filter_monthly"),
        InlineKeyboardButton("🏆 All Time", callback_data="prem_leaderboard")
    )
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="prem_back_center"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("lb_filter_"))
def callback_lb_filter(call):
    bot.answer_callback_query(call.id, "Showing filter data...")
    callback_prem_leaderboard(call)

# ================= 5. PREMIUM MISSIONS =================
@bot.callback_query_handler(func=lambda call: call.data == "prem_missions")
def callback_prem_missions(call):
    uid = str(call.from_user.id)
    user_prog = mission_progress_db.get(uid, {})
    
    text = "╭━━━ 🎯 PREMIUM MISSIONS ━━━╮\n\n🔥 ACTIVE MISSIONS\n\n"
    for m in missions_db:
        target = m["target"]
        current = user_prog.get(m["id"], 0)
        status_icon = "✅" if current >= target else f"Progress: {current}/{target}"
        text += f"{m['title']}\n{status_icon}\n🎁 Reward: {m['reward']}\n\n"
    text += "╰━━━━━━━━━━━━━━━━━━━━━━╯"
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🎯 Active Missions", callback_data="prem_missions"),
        InlineKeyboardButton("🎁 Completed", callback_data="prem_missions")
    )
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="prem_back_center"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

# ================= 6. PREMIUM COUPONS =================
@bot.callback_query_handler(func=lambda call: call.data == "prem_coupons")
def callback_prem_coupons(call):
    msg = bot.send_message(
        call.message.chat.id,
        "╭━━━ 🎟️ PREMIUM COUPON ━━━╮\n\nEnter your coupon code below.\n\nExample:\n`VIP2026`\n╰━━━━━━━━━━━━━━━━━━━━━━╯",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, process_coupon_code)

def process_coupon_code(m):
    code = (m.text or "").strip().upper()
    uid = str(m.from_user.id)
    
    if code not in coupons_db:
        bot.send_message(m.chat.id, "❌ Invalid coupon code.")
        return
        
    coupon = coupons_db[code]
    if not coupon.get("active", True):
        bot.send_message(m.chat.id, "❌ This coupon is inactive.")
        return
        
    if coupon["uses"] >= coupon["max_uses"]:
        bot.send_message(m.chat.id, "❌ This coupon has reached its maximum usage limit.")
        return
        
    if uid not in coupon_usage_db:
        coupon_usage_db[uid] = []
        
    if code in coupon_usage_db[uid]:
        bot.send_message(m.chat.id, "❌ You have already used this coupon.")
        return
        
    coupon_usage_db[uid].append(code)
    coupon["uses"] += 1
    save_coupons()
    save_coupon_usage()
    
    days = coupon["reward_days"]
    start_date = datetime.now()
    if uid in premium_db and premium_db[uid].get("status") == "ACTIVE":
        current_expiry = datetime.strptime(premium_db[uid]["expiry_date"], "%Y-%m-%d %H:%M:%S")
        if current_expiry > start_date:
            start_date = current_expiry
    expiry_date = start_date + timedelta(days=days)
    
    premium_db[uid] = {
        "plan": f"Coupon ({days} Days)",
        "duration": days,
        "stars_amount": 0,
        "payment_id": f"coupon_{code}",
        "start_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "expiry_date": expiry_date.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "ACTIVE",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_premium()
    
    bot.send_message(m.chat.id, f"🎉 <b>Coupon Redeemed Successfully!</b>\n\nYou received {days} Days of Premium VIP access!", parse_mode="HTML")

# ================= 7. GIFT PREMIUM =================
@bot.callback_query_handler(func=lambda call: call.data == "prem_gift")
def callback_prem_gift(call):
    msg = bot.send_message(call.message.chat.id, "🎁 Send the Telegram Username or ID of the recipient you want to gift Premium to:")
    bot.register_next_step_handler(msg, process_gift_recipient)

def process_gift_recipient(m):
    recipient_input = (m.text or "").strip().replace("@", "")
    recipient_id = None
    
    for u, data in users.items():
        if data.get("username", "").lower() == recipient_input.lower() or u == recipient_input:
            recipient_id = u
            break
            
    if not recipient_id:
        bot.send_message(m.chat.id, "❌ User not found in database.")
        return
        
    kb = InlineKeyboardMarkup(row_width=2)
    for key, plan in PREMIUM_PLANS.items():
        kb.add(InlineKeyboardButton(f"⭐ {plan['name']} — {plan['stars']} Stars", callback_data=f"giftplan_{recipient_id}_{key}"))
    
    bot.send_message(m.chat.id, f"💎 Choose Premium plan to gift to user `@{recipient_input}`:", reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("giftplan_"))
def callback_gift_plan(call):
    parts = call.data.split("_")
    recipient_id = parts[1]
    plan_key = parts[2]
    
    if plan_key not in PREMIUM_PLANS:
        bot.answer_callback_query(call.id, "❌ Invalid plan")
        return
        
    plan = PREMIUM_PLANS[plan_key]
    title = f"Gift Premium - {plan['name']}"
    description = f"Gift {plan['name']} Premium to user {recipient_id}."
    prices = [LabeledPrice(label=plan['name'], amount=plan['stars'])]
    
    try:
        bot.send_invoice(
            chat_id=call.message.chat.id,
            title=title,
            description=description,
            invoice_payload=f"gift_{recipient_id}_{plan_key}_{call.from_user.id}",
            provider_token="",
            currency="XTR",
            prices=prices
        )
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Error: {e}", show_alert=True)

# ================= 8. VIP IDENTITY =================
@bot.callback_query_handler(func=lambda call: call.data == "prem_vip_id")
def callback_vip_identity(call):
    uid = str(call.from_user.id)
    u_data = vip_identity_db.get(uid, {"title": "VIP", "level": 1, "points": 10, "since": "2026-08-12"})
    username = users.get(uid, {}).get("username", uid)
    
    text = f"""╭━━━ 👑 VIP IDENTITY ━━━╮

👤 User: @{username or uid}

⭐ Current Title:
💎 {u_data['title']}

📅 Premium Since:
{u_data['since']}

🔥 VIP Level:
Level {u_data['level']}

🏆 Points:
{u_data['points']}

╰━━━━━━━━━━━━━━━━━━━━━━╯"""

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⭐ VIP", callback_data="viptitle_VIP"),
        InlineKeyboardButton("💎 PRO", callback_data="viptitle_PRO")
    )
    kb.add(
        InlineKeyboardButton("🔥 LEGEND", callback_data="viptitle_LEGEND"),
        InlineKeyboardButton("👑 ELITE", callback_data="viptitle_ELITE")
    )
    kb.add(InlineKeyboardButton("🎨 Customize", callback_data="vip_customize"), InlineKeyboardButton("🔙 Back", callback_data="prem_back_center"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("viptitle_"))
def callback_set_viptitle(call):
    title = call.data.split("_")[1]
    uid = str(call.from_user.id)
    if uid not in vip_identity_db:
        vip_identity_db[uid] = {"title": title, "level": 1, "points": 10, "since": datetime.now().strftime("%Y-%m-%d")}
    else:
        vip_identity_db[uid]["title"] = title
    save_vip_identity()
    bot.answer_callback_query(call.id, f"✅ VIP Title updated to {title}!")
    callback_vip_identity(call)

@bot.callback_query_handler(func=lambda call: call.data == "vip_customize")
def callback_vip_customize(call):
    bot.answer_callback_query(call.id, "🎨 Custom VIP badge customization is active.")
    callback_vip_identity(call)

# ================= ADVANCED ADMIN PANEL EXTENSIONS =================
@bot.message_handler(func=lambda m: m.text == "👑 PREMIUM MANAGEMENT")
def admin_prem_mgmt(m):
    if not is_admin(m.from_user.id):
        return
    bot.send_message(m.chat.id, "👑 <b>Premium Management</b>\n\nUse commands or search user to give/remove premium status.", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "🎁 REFERRAL MGMT")
def admin_ref_mgmt(m):
    if not is_admin(m.from_user.id):
        return
    total_refs = sum(len(v) for v in referrals_db.values())
    bot.send_message(m.chat.id, f"🎁 <b>Referral Management</b>\n\nTotal Referrals Tracked: {total_refs}", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "💡 FEATURE MGMT")
def admin_feat_mgmt(m):
    if not is_admin(m.from_user.id):
        return
    text = "💡 <b>Feature Requests Management</b>\n\n"
    for r in feature_requests_db:
        text += f"ID: {r['request_id']} | {r['title']} [{r['status']}] (Votes: {r['votes']})\n"
    bot.send_message(m.chat.id, text or "No requests found.", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "🏆 LEADERBOARD MGMT")
def admin_lb_mgmt(m):
    if not is_admin(m.from_user.id):
        return
    bot.send_message(m.chat.id, f"🏆 <b>Leaderboard Management</b>\n\nTotal Ranked Users: {len(leaderboard_db)}", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "🎯 MISSIONS MGMT")
def admin_missions_mgmt(m):
    if not is_admin(m.from_user.id):
        return
    bot.send_message(m.chat.id, f"🎯 <b>Missions Management</b>\n\nActive Missions Configured: {len(missions_db)}", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "🎟 COUPONS MGMT")
def admin_coupons_mgmt(m):
    if not is_admin(m.from_user.id):
        return
    text = "🎟 <b>Coupons Management</b>\n\n"
    for code, data in coupons_db.items():
        text += f"• Code: <code>{code}</code> | Days: {data['reward_days']} | Uses: {data['uses']}/{data['max_uses']}\n"
    bot.send_message(m.chat.id, text or "No coupons found.", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "🎁 GIFT MGMT")
def admin_gift_mgmt(m):
    if not is_admin(m.from_user.id):
        return
    bot.send_message(m.chat.id, f"🎁 <b>Gift Premium Management</b>\n\nTotal Gifts Sent: {len(gift_premium_db)}", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "👑 VIP ID MGMT")
def admin_vip_mgmt(m):
    if not is_admin(m.from_user.id):
        return
    bot.send_message(m.chat.id, f"👑 <b>VIP Identity Management</b>\n\nConfigured VIP Profiles: {len(vip_identity_db)}", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "💳 STARS PAYMENTS")
def admin_stars_payments(m):
    if not is_admin(m.from_user.id):
        return
    total_stars = sum(p.get("stars", 0) for p in payments_db)
    bot.send_message(m.chat.id, f"💳 <b>Stars Payments Log</b>\n\nTotal Transactions: {len(payments_db)}\nTotal Stars Collected: ⭐ {total_stars}", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "📊 PREMIUM STATS")
def admin_premium_stats(m):
    if not is_admin(m.from_user.id):
        return
    active_prem = len([u for u, d in premium_db.items() if d.get("status") == "ACTIVE"])
    expired_prem = len(premium_db) - active_prem
    total_stars = sum(p.get("stars", 0) for p in payments_db)
    total_refs = sum(len(v) for v in referrals_db.values())
    total_coupons = sum(d["uses"] for d in coupons_db.values())
    
    text = f"""👑 <b>PREMIUM STATISTICS</b>

👥 Total Users: {len(users)}
⭐ Active Premium: {active_prem}
⏰ Expired Premium: {expired_prem}
💳 Total Stars: ⭐ {total_stars}
📅 Stars Today: ⭐ {total_stars}
📆 Stars This Month: ⭐ {total_stars}
🎁 Total Referrals: {total_refs}
💡 Feature Requests: {len(feature_requests_db)}
🎯 Missions Completed: {sum(len(v) for v in mission_progress_db.values())}
🎟 Coupons Used: {total_coupons}
🎁 Gifts Sent: {len(gift_premium_db)}"""
    bot.send_message(m.chat.id, text, parse_mode="HTML")

# ================= ADMIN PANEL =================
@bot.message_handler(func=lambda m: m.text == "👑 ADMIN PANEL")
def open_admin_panel(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ You are not admin")
        return
    bot.send_message(m.chat.id, "👑 Admin Panel", reply_markup=admin_menu())

# ================= BALANCE =================
@bot.message_handler(func=lambda m: m.text == "💰 BALANCE")
def balance_handler(m):
    if bot_locked_guard(m):
        return
    if banned_guard(m):
        return
    uid = str(m.from_user.id)
    bal = users[uid].get("balance", 0.0)
    blocked = users[uid].get("blocked", 0.0)
    bot.send_message(
        m.chat.id,
        f"💰 Available Balance: ${bal:.2f}\n"
        f"⏳ Blocked Amount: ${blocked:.2f}"
    )

# ================= GET ID =================
@bot.message_handler(func=lambda m: m.text == "🆔 GET ID")
def get_id_handler(m):
    if bot_locked_guard(m):
        return
    if banned_guard(m):
        return
    uid = str(m.from_user.id)
    bot.send_message(
        m.chat.id,
        f"🆔 BOT ID: <code>{users[uid]['bot_id']}</code>\n"
        f"👤 Telegram ID: <code>{uid}</code>"
    )

# ================= REFERRAL =================
@bot.message_handler(func=lambda m: m.text == "👥 REFERRAL")
def referral_handler(m):
    if bot_locked_guard(m):
        return
    if banned_guard(m):
        return
    uid = str(m.from_user.id)
    bot_username = bot.get_me().username
    link = f"https://t.me/{bot_username}?start={users[uid]['ref']}"
    invited = users[uid].get("invited", 0)
    bot.send_message(
        m.chat.id,
        f"🔗 Your Referral Link:\n{link}\n\n"
        f"👥 Invited Users: {invited}\n"
        f"🎁 You earn $0.2 per referral!"
    )

# ================= CUSTOMER SUPPORT =================
@bot.message_handler(func=lambda m: m.text == "☎️ CUSTOMER")
def customer_handler(m):
    if bot_locked_guard(m):
        return
    if banned_guard(m):
        return
    bot.send_message(
        m.chat.id,
        "☎️ Customer Support:\n@scholes1"
    )

@bot.message_handler(func=lambda m: m.text == "🤖CUSTOMER AI")
def customer_ai_handler(m):
    if bot_locked_guard(m):
        return
    if banned_guard(m):
        return
    bot.send_message(
        m.chat.id,
        "Ai Customer Support🤖:\n@Aidownoaderbot"
    )

# ================= WITHDRAWAL MENU =================
@bot.message_handler(func=lambda m: m.text == "💸 WITHDRAWAL")
def withdraw_menu(m):
    if banned_guard(m):
        return
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("USDT-BEP20")
    kb.add("🔙 CANCEL")
    bot.send_message(
        m.chat.id,
        "Select withdrawal method:",
        reply_markup=kb
    )

@bot.message_handler(func=lambda m: m.text in ["USDT-BEP20", "🔙 CANCEL"])
def withdraw_method(m):
    uid = str(m.from_user.id)
    if m.text == "🔙 CANCEL":
        back_to_main_menu(m)
        return
    if m.text == "USDT-BEP20":
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("🔙 CANCEL")
        msg = bot.send_message(
            m.chat.id,
            "Enter your USDT BEP20 address (must start with 0x)\nOr press 🔙 CANCEL",
            reply_markup=kb
        )
        bot.register_next_step_handler(msg, withdraw_address_step)

def withdraw_address_step(m):
    uid = str(m.from_user.id)
    text = (m.text or "").strip()
    if text == "🔙 CANCEL":
        back_to_main_menu(m)
        return
    if not text.startswith("0x"):
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("🔙 CANCEL")
        msg = bot.send_message(
            m.chat.id,
            "❌ Invalid address. Must start with 0x.\nTry again or press 🔙 CANCEL",
            reply_markup=kb
        )
        bot.register_next_step_handler(msg, withdraw_address_step)
        return
    users[uid]["temp_addr"] = text
    save_users()
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🔙 CANCEL")
    msg = bot.send_message(
        m.chat.id,
        f"Enter withdrawal amount\nMinimum: $1\nBalance: ${users[uid]['balance']:.2f}\n\nOr press 🔙 CANCEL",
        reply_markup=kb
    )
    bot.register_next_step_handler(msg, withdraw_amount_step)

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
        msg = bot.send_message(
            m.chat.id,
            "❌ Invalid number.\nEnter again or press 🔙 CANCEL",
            reply_markup=kb
        )
        bot.register_next_step_handler(msg, withdraw_amount_step)
        return
    if amt < 1:
        bot.send_message(
            m.chat.id,
            "❌ Minimum withdrawal is $1",
            reply_markup=user_menu(is_admin(uid))
        )
        return
    if amt > users[uid]["balance"]:
        bot.send_message(
            m.chat.id,
            "❌ Insufficient balance",
            reply_markup=user_menu(is_admin(uid))
        )
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
    save_users()
    save_withdraws()

    bot.send_message(
        int(uid),
        f"✅ Withdrawal Request Sent\n"
        f"🧾 Request ID: {wid}\n"
        f"💵 Amount: ${amt:.2f}\n"
        f"🏦 Address: {withdrawal['address']}\n"
        f"💰 Balance Left: ${users[uid]['balance']:.2f}\n"
        f"⏳ Status: Pending"
    )

    admin_text = (
        f"💳 NEW WITHDRAWAL\n\n"
        f"👤 User: {uid}\n"
        f"🤖 BOT ID: {users[uid]['bot_id']}\n"
        f"👥 Referrals: {users[uid]['invited']}\n"
        f"💵 Amount: ${amt:.2f}\n"
        f"🧾 Request ID: {wid}\n"
        f"🏦 Address: {withdrawal['address']}\n"
        f"⏳ Status: Pending"
    )

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
        bot.answer_callback_query(call.id, "❌ You are not admin")
        return

    data = call.data

    if data.startswith("confirm_"):
        wid = int(data.split("_")[1])
        w = next((x for x in withdraws if x["id"] == wid), None)
        if not w or w["status"] != "pending":
            return
        w["status"] = "paid"
        users[w["user"]]["blocked"] -= w["blocked"]
        save_users()
        save_withdraws()
        bot.answer_callback_query(call.id, "✅ Confirmed")
        bot.send_message(int(w["user"]), f"✅ Withdrawal #{wid} approved!")

    elif data.startswith("reject_"):
        wid = int(data.split("_")[1])
        w = next((x for x in withdraws if x["id"] == wid), None)
        if not w or w["status"] != "pending":
            return
        w["status"] = "rejected"
        users[w["user"]]["balance"] += w["blocked"]
        users[w["user"]]["blocked"] -= w["blocked"]
        save_users()
        save_withdraws()
        bot.answer_callback_query(call.id, "❌ Rejected")
        bot.send_message(int(w["user"]), f"❌ Withdrawal #{wid} rejected")

    elif data.startswith("ban_"):
        uid = data.split("_")[1]
        if uid in users:
            users[uid]["banned"] = True
            save_users()
            bot.answer_callback_query(call.id, "🚫 User banned")
            bot.send_message(int(uid), "🚫 You have been banned by admin.")

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
        save_users()
        save_withdraws()
        bot.answer_callback_query(call.id, "💰 Money Blocked")
        bot.send_message(
            int(uid),
            f"🚫 Your withdrawal of ${amt:.2f} is BLOCKED.\n"
            f"🔢 Block Code: {code}\n"
            f"Contact admin to unlock."
        )

@bot.message_handler(func=lambda m: m.text == "💰 UNBLOCK MONEY")
def unblock_money_start(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ You are not admin")
        return
    msg = bot.send_message(m.chat.id, "🔢 Send 4-digit Block Code to UNBLOCK funds:")
    bot.register_next_step_handler(msg, unblock_money_process)

def unblock_money_process(m):
    if not is_admin(m.from_user.id):
        return
    code = (m.text or "").strip()
    w = next((x for x in withdraws if x.get("block_code") == code), None)
    if not w:
        bot.send_message(m.chat.id, "❌ Invalid Block Code")
        return
    uid = w["user"]
    amt = w["blocked"]
    users[uid]["balance"] += amt
    w["status"] = "unblocked"
    w.pop("block_code", None)
    save_users()
    save_withdraws()
    bot.send_message(int(uid), f"✅ Your blocked ${amt:.2f} is now available in balance!")
    bot.send_message(m.chat.id, f"✅ Money unblocked for user {uid}")

@bot.message_handler(func=lambda m: m.text == "🔥 UN BAN-USER")
def unban_user_start(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ You are not admin")
        return
    msg = bot.send_message(m.chat.id, "Send Telegram ID of user to UNBAN:")
    bot.register_next_step_handler(msg, unban_user_process)

def unban_user_process(m):
    if not is_admin(m.from_user.id):
        return
    uid = (m.text or "").strip()
    if uid not in users:
        bot.send_message(m.chat.id, "❌ User not found")
        return
    users[uid]["banned"] = False
    save_users()
    bot.send_message(m.chat.id, f"✅ User {uid} unbanned")
    bot.send_message(int(uid), "✅ You have been unbanned by admin.")

@bot.message_handler(func=lambda m: m.text == "💳 WITHDRAWAL CHECK")
def withdrawal_check_start(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ You are not admin")
        return
    msg = bot.send_message(m.chat.id, "Enter Withdrawal Request ID (example: 40201):")
    bot.register_next_step_handler(msg, withdrawal_check_process)

def withdrawal_check_process(m):
    if not is_admin(m.from_user.id):
        return
    try:
        wid = int(m.text.strip())
    except:
        bot.send_message(m.chat.id, "❌ Invalid Request ID")
        return
    w = next((x for x in withdraws if x["id"] == wid), None)
    if not w:
        bot.send_message(m.chat.id, "❌ Request not found")
        return
    uid = w["user"]
    bot_id = users.get(uid, {}).get("bot_id", "Unknown")
    invited = users.get(uid, {}).get("invited", 0)
    msg_text = (
        f"💳 WITHDRAWAL DETAILS\n\n"
        f"🧾 Request ID: {w['id']}\n"
        f"👤 User ID: {uid}\n"
        f"🤖 BOT ID: {bot_id}\n"
        f"👥 Referrals: {invited}\n"
        f"💵 Amount: ${w['amount']:.2f}\n"
        f"🏦 Address: {w['address']}\n"
        f"📊 Status: {w['status'].upper()}\n"
        f"⏰ Time: {w['time']}"
    )
    bot.send_message(m.chat.id, msg_text)

@bot.message_handler(func=lambda m: m.text == "📊 STATS")
def stats_handler(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ You are not admin")
        return
    total_users = len(users)
    total_balance = sum(u.get("balance", 0.0) for u in users.values())
    total_blocked = sum(u.get("blocked", 0.0) for u in users.values())
    total_withdraws = len(withdraws)
    pending_withdraws = len([w for w in withdraws if w["status"] == "pending"])
    msg = (
        f"📊 BOT STATS\n\n"
        f"👥 Total Users: {total_users}\n"
        f"💰 Total Balance: ${total_balance:.2f}\n"
        f"⏳ Total Blocked: ${total_blocked:.2f}\n"
        f"🧾 Total Withdrawals: {total_withdraws}\n"
        f"⏳ Pending Withdrawals: {pending_withdraws}"
    )
    bot.send_message(m.chat.id, msg)

@bot.message_handler(func=lambda m: m.text == "🚫 BAN USER MANUAL")
def manual_ban_start(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ You are not admin")
        return
    msg = bot.send_message(m.chat.id, "Send Telegram ID or BOT ID to BAN user:")
    bot.register_next_step_handler(msg, manual_ban_process)

def manual_ban_process(m):
    if not is_admin(m.from_user.id):
        return
    uid_input = (m.text or "").strip()
    uid = uid_input if uid_input in users else find_user_by_botid(uid_input)
    if not uid:
        bot.send_message(m.chat.id, "❌ User not found")
        return
    users[uid]["banned"] = True
    save_users()
    bot.send_message(m.chat.id, f"🚫 User {uid} banned")
    bot.send_message(int(uid), "🚫 You have been banned by admin.")

@bot.message_handler(func=lambda m: m.text == "📡 ADD CHANNEL")
def add_channel_start(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "Send channel username\nExample:\n@mychannel")
    bot.register_next_step_handler(msg, add_channel_process)

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
        bot.send_message(m.chat.id, "❌ Invalid channel or bot not inside channel")

@bot.message_handler(func=lambda m: m.text == "CHANNEL")
def post_channel_process(m):
    text = m.text
    if not MANAGED_CHANNELS:
        bot.send_message(m.chat.id, "❌ No channels added.\nUse 📡 ADD CHANNEL first.")
        return
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("🇸🇴 Somali", callback_data="lang_so"),
        InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    )
    sent = 0
    for ch in MANAGED_CHANNELS:
        try:
            bot.send_message(ch, text, reply_markup=kb)
            sent += 1
        except Exception as e:
            print("Channel post error:", e)
    bot.send_message(m.chat.id, f"✅ Posted to {sent} channel(s)")

channel_posts = {}

@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def channel_language(call):
    lang = call.data.split("_")[1]
    if call.message.message_id not in channel_posts:
        return
    data = channel_posts[call.message.message_id]
    text = data["so"] if lang == "so" else data["en"]
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("🇸🇴 Somali", callback_data="lang_so"),
        InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "🔍 RAADI")
def raadi_stats(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ You are not admin")
        return
    total_videos = videos_data.get("total", 0)
    platform_stats = videos_data.get("platforms", {"tiktok": 0, "youtube": 0, "facebook": 0, "pinterest": 0})
    users_stats = videos_data.get("users", {})
    if not users_stats:
        bot.send_message(m.chat.id, "❌ No video data found yet.")
        return
    top_user_id, top_count = max(users_stats.items(), key=lambda x: x[1])
    msg_lines = [
        f"🔍 DOWNLOAD ANALYTICS\n",
        f"🎬 Total Videos Downloaded: {total_videos}",
        f"🏆 Top Downloader: <a href='tg://user?id={top_user_id}'>{top_user_id}</a> ({top_count} videos)\n",
        "📊 Downloads by Platform:",
        f"• TikTok: {platform_stats.get('tiktok',0)}",
        f"• YouTube: {platform_stats.get('youtube',0)}",
        f"• Facebook: {platform_stats.get('facebook',0)}",
        f"• Pinterest: {platform_stats.get('pinterest',0)}\n",
        "🥇 Top 40 Users:"
    ]
    sorted_users = sorted(users_stats.items(), key=lambda x: x[1], reverse=True)
    for i, (uid, count) in enumerate(sorted_users[:40], start=1):
        bot_id = users.get(str(uid), {}).get("bot_id", "N/A")
        msg_lines.append(f"{i}. 👤 <a href='tg://user?id={uid}'>{uid}</a> - 🎬 {count} videos | 🤖 BOT ID: {bot_id}")
    bot.send_message(m.chat.id, "\n".join(msg_lines), parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "📢 BROADCAST")
def broadcast_start(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ You are not admin")
        return
    msg = bot.send_message(m.chat.id, "📝 Send the broadcast message to all users:")
    bot.register_next_step_handler(msg, broadcast_send)

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
    bot.send_message(m.chat.id, f"✅ Broadcast sent to {count} users")

@bot.message_handler(func=lambda m: m.text == "📌 POST CHANNEL")
def post_channel_start(m):
    global CHANNEL_WINDOW_OPEN
    if not is_admin(m.from_user.id):
        return
    CHANNEL_WINDOW_OPEN = True
    POST_CHANNELS.clear()
    msg = bot.send_message(m.chat.id, "Send channel usernames\nExample:\n@channel1\n@channel2\n\nMax 10 channels.\nSend DONE when finished.")
    bot.register_next_step_handler(msg, post_channel_add)

def post_channel_add(m):
    if m.text.lower() == "done":
        bot.send_message(m.chat.id, f"✅ {len(POST_CHANNELS)} channels added.")
        return
    if len(POST_CHANNELS) >= MAX_CHANNELS:
        bot.send_message(m.chat.id, "⚠️ Maximum 10 channels allowed.")
        return
    username = m.text.replace("@","").strip()
    POST_CHANNELS.append(username)
    msg = bot.send_message(m.chat.id, f"Channel @{username} added\nTotal: {len(POST_CHANNELS)}\nSend another or DONE")
    bot.register_next_step_handler(msg, post_channel_add)

@bot.message_handler(func=lambda m: m.text == "CLOSE CHANNEL POST")
def close_channel_post(m):
    if not is_admin(m.from_user.id):
        return
    MANAGED_CHANNELS.clear()
    bot.send_message(m.chat.id, "❌ All channels removed.")

@bot.message_handler(func=lambda m: m.text == "👥 SEE LIST")
def see_users(m):
    if not is_admin(m.from_user.id):
        return
    total = len(users)
    count = 0
    for uid in users:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("💬 OPEN CHAT", url=f"tg://user?id={uid}"))
        bot.send_message(m.chat.id, f"👤 User ID: {uid}", reply_markup=kb)
        count += 1
        if count >= 20:
            break
    bot.send_message(m.chat.id, f"📊 Total Users: {total}")

@bot.message_handler(func=lambda m: m.text == "🔒 LOCK BOT")
def lock_bot_start(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ You are not admin")
        return
    msg = bot.send_message(m.chat.id, "✍️ Send the lock message users should receive.")
    bot.register_next_step_handler(msg, lock_bot_process)

def lock_bot_process(m):
    global BOT_LOCKED, LOCK_MESSAGE
    if not is_admin(m.from_user.id):
        return
    text = (m.text or "").strip()
    if not text:
        return
    LOCK_MESSAGE = text
    BOT_LOCKED = True
    bot.send_message(m.chat.id, "🔒 Bot locked successfully.")

@bot.message_handler(func=lambda m: m.text == "🔓 UNLOCK BOT")
def unlock_bot(m):
    global BOT_LOCKED
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ You are not admin")
        return
    BOT_LOCKED = False
    bot.send_message(m.chat.id, "🔓 Bot unlocked successfully.")

@bot.message_handler(func=lambda m: m.text == "📢 ADD ADS")
def add_ads_start(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "✍️ Button Name | Link | Text", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_add_ads)

def process_add_ads(m):
    global ADS_ENABLED, ADS_BTN_TEXT, ADS_URL, ADS_TEXT
    if not is_admin(m.from_user.id):
        return
    parts = [p.strip() for p in (m.text or "").split("|")]
    if len(parts) < 2:
        return
    ADS_BTN_TEXT = parts[0]
    ADS_URL = parts[1]
    ADS_TEXT = parts[2] if len(parts) > 2 else "✨ Ad"
    ADS_ENABLED = True
    bot.send_message(m.chat.id, "✅ Ads enabled!")

@bot.message_handler(func=lambda m: m.text == "🗑 DELETE ADS")
def delete_ads(m):
    global ADS_ENABLED, ADS_BTN_TEXT, ADS_URL, ADS_TEXT
    if not is_admin(m.from_user.id):
        return
    ADS_ENABLED = False
    ADS_BTN_TEXT = ""
    ADS_URL = ""
    ADS_TEXT = ""
    bot.send_message(m.chat.id, "🗑 Ads deleted.")

@bot.message_handler(func=lambda m: m.text == "📥 IMPORT USERS")
def import_users_start(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "Send Telegram IDs separated by spaces or new lines.")
    bot.register_next_step_handler(msg, import_users_process)

def import_users_process(m):
    if not is_admin(m.from_user.id):
        return
    ids = (m.text or "").replace("\n", " ").split()
    added = 0
    for uid in ids:
        if uid.isdigit() and uid not in users:
            users[uid] = {
                "balance": 0.0,
                "blocked": 0.0,
                "ref": random_ref(),
                "bot_id": random_botid(),
                "invited": 0,
                "banned": False,
                "verified": False,
                "month": now_month()
            }
            added += 1
    save_users()
    bot.send_message(m.chat.id, f"✅ Imported {added} users.")

@bot.message_handler(func=lambda m: m.text == "🔗 GET REFERRAL CODE")
def get_ref_code_start(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "Send user username:")
    bot.register_next_step_handler(msg, get_ref_username)

def get_ref_username(m):
    if not is_admin(m.from_user.id):
        return
    username = m.text.replace("@", "").strip()
    msg = bot.send_message(m.chat.id, "Now send referral code number:")
    bot.register_next_step_handler(msg, lambda x: save_custom_ref_code(x, username))

def save_custom_ref_code(m, username):
    if not is_admin(m.from_user.id):
        return
    code = m.text.strip()
    user_id = next((u for u, d in users.items() if d.get("username", "").lower() == username.lower()), None)
    if not user_id:
        bot.send_message(m.chat.id, "❌ User not found")
        return
    users[user_id]["ref"] = code
    save_users()
    bot.send_message(m.chat.id, f"✅ Referral code saved for @{username}")

@bot.message_handler(func=lambda m: m.text == "🔎 SEARCH USER")
def search_user(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "Send User Telegram ID")
    bot.register_next_step_handler(msg, search_user_result)

def search_user_result(m):
    if not is_admin(m.from_user.id):
        return
    uid = m.text.strip()
    if uid in users:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("💬 OPEN CHAT", url=f"tg://user?id={uid}"))
        kb.add(InlineKeyboardButton("✉️ MESSAGE USER", callback_data=f"msguser|{uid}"))
        bot.send_message(m.chat.id, f"👤 User Found\nID: {uid}", reply_markup=kb)
    else:
        bot.send_message(m.chat.id, "❌ User not found")

@bot.message_handler(func=lambda m: m.text and "http" in m.text)
def handle_links(message):
    if bot_locked_guard(message):
        return
    user_id = message.from_user.id
    link = message.text
    
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
        code = str(random.randint(10000,99999))
        verify_pending[user_id] = {"code": code, "link": link}
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📩 Verify via DM", callback_data="via_telegram"))
        bot.send_message(message.chat.id, "🔐 Verification Required", reply_markup=kb)
        return

    bot.send_message(message.chat.id, "⏳ Downloading...")
    download_media(message.chat.id, link)

def send_multi_join(user_id):
    kb = InlineKeyboardMarkup(row_width=3)
    buttons = [InlineKeyboardButton("➕️ JOIN", url=f"https://t.me/{ch}") for ch in POST_CHANNELS]
    kb.add(*buttons)
    kb.add(InlineKeyboardButton("✅ CONFIRM", callback_data="multi_checkjoin"))
    bot.send_message(user_id, "⚠️ Join all channels to continue.", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "multi_checkjoin")
def multi_checkjoin(call):
    user_id = call.from_user.id
    joined_all = True
    for ch in POST_CHANNELS:
        try:
            member = bot.get_chat_member(f"@{ch}", user_id)
            if member.status not in ["member","administrator","creator"]:
                joined_all = False
                break
        except:
            joined_all = False
            break
    if joined_all:
        bot.answer_callback_query(call.id,"✅ Join verified")
        if user_id in pending_links:
            link = pending_links[user_id]
            del pending_links[user_id]
            bot.send_message(user_id,"⬇️ Processing your video...")
            download_media(user_id, link)
        else:
            bot.send_message(user_id,"Send your video link.")
    else:
        bot.answer_callback_query(call.id, "❌ You must join all channels first!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "confirm_join")
def confirm_join(call):
    user_id = call.from_user.id
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["member", "administrator", "creator"]:
            bot.answer_callback_query(call.id, "✅ Join verified")
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
            if user_id in pending_links:
                link = pending_links[user_id]
                del pending_links[user_id]
                download_media(user_id, link)
            else:
                bot.send_message(user_id, "✅ Join confirmed.")
        else:
            bot.answer_callback_query(call.id, "❌ You must join the channel first!", show_alert=True)
    except:
        bot.answer_callback_query(call.id, "❌ Please join the channel first!", show_alert=True)

@bot.message_handler(func=lambda m: m.text == "❌ CLOSE WINDOWS")
def close_channel_windows(m):
    global CHANNEL_WINDOW_OPEN
    if not is_admin(m.from_user.id):
        return
    CHANNEL_WINDOW_OPEN = False
    bot.send_message(m.chat.id, "✅ Channel join system disabled.")

@bot.message_handler(func=lambda m: m.text == "✅ VERIFY ON")
def verify_on(m):
    global VERIFY_ENABLED
    if m.from_user.id not in ADMIN_IDS:
        return
    VERIFY_ENABLED = True
    bot.send_message(m.chat.id, "✅ Verify system enabled")

@bot.message_handler(func=lambda m: m.text == "❌ VERIFY OFF")
def verify_off(m):
    global VERIFY_ENABLED
    if m.from_user.id not in ADMIN_IDS:
        return
    VERIFY_ENABLED = False
    bot.send_message(m.chat.id, "❌ Verify system disabled")

@bot.message_handler(func=lambda m: m.text == "CHANNEL POST")
def start_channel_post(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "Send the main text for the channel post.")
    bot.register_next_step_handler(msg, post_main_text)

def post_main_text(m):
    pending_post[m.from_user.id] = {"text": m.text, "buttons": []}
    msg = bot.send_message(m.chat.id, "Send button like:\n\nButton Name | Text when clicked\n\nSend DONE when finished.")
    bot.register_next_step_handler(msg, add_buttons)

def add_buttons(m):
    uid = m.from_user.id
    if m.text.lower() == "done":
        data = pending_post[uid]
        kb = InlineKeyboardMarkup()
        for i, btn in enumerate(data["buttons"]):
            kb.add(InlineKeyboardButton(btn["name"], callback_data=f"postbtn_{i}"))
        for ch in MANAGED_CHANNELS:
            msg = bot.send_message(ch, data["text"], reply_markup=kb)
            channel_posts[msg.message_id] = data
        pending_post.pop(uid)
        bot.send_message(m.chat.id, "✅ Post sent")
        return
    try:
        name, content = m.text.split("|",1)
        pending_post[uid]["buttons"].append({"name": name.strip(), "content": content.strip()})
        msg = bot.send_message(m.chat.id, "Button added. Send another or DONE")
        bot.register_next_step_handler(msg, add_buttons)
    except:
        msg = bot.send_message(m.chat.id, "❌ Format error")
        bot.register_next_step_handler(msg, add_buttons)

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
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "➕ ADD BALANCE")
def add_balance_start(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "Send BOT ID or Telegram ID and amount:")
    bot.register_next_step_handler(msg, add_balance_process)

def add_balance_process(m):
    if not is_admin(m.from_user.id):
        return
    try:
        uid_str, amt_str = m.text.strip().split()
        amt = float(amt_str)
        uid = uid_str if uid_str in users else find_user_by_botid(uid_str)
        if not uid or amt <= 0:
            return
        users[uid]["balance"] += amt
        save_users()
        bot.send_message(m.chat.id, f"✅ Added ${amt:.2f}")
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "➖ REMOVE MONEY")
def remove_balance_start(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "Send BOT ID or Telegram ID and amount:")
    bot.register_next_step_handler(msg, remove_balance_process)

def remove_balance_process(m):
    if not is_admin(m.from_user.id):
        return
    try:
        uid_str, amt_str = m.text.strip().split()
        amt = float(amt_str)
        uid = uid_str if uid_str in users else find_user_by_botid(uid_str)
        if not uid or users[uid]["balance"] < amt:
            return
        users[uid]["balance"] -= amt
        save_users()
        bot.send_message(m.chat.id, f"✅ Removed ${amt:.2f}")
    except:
        pass

CAPTION_TEXT = "Downloaded by:\n@Downloadvedioytibot"

def extract_url(text):
    urls = re.findall(r'https?://[^\s]+', text)
    return urls[0] if urls else None

def send_video_with_music(chat_id, file_path, platform=None):
    vid_id = str(uuid.uuid4())[:8]
    video_files[vid_id] = file_path

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🎵 Convert to Music", callback_data=f"music_{vid_id}"))

    if ADS_ENABLED and ADS_BTN_TEXT and ADS_URL:
        kb.add(InlineKeyboardButton(ADS_BTN_TEXT, url=ADS_URL))

    caption = CAPTION_TEXT
    if ADS_ENABLED and ADS_TEXT:
        caption += f"\n\n📢 {ADS_TEXT}"

    uid = str(chat_id)
    videos_data["total"] += 1
    videos_data["users"][uid] = videos_data["users"].get(uid, 0) + 1

    if platform:
        if "platforms" not in videos_data:
            videos_data["platforms"] = {}
        videos_data["platforms"][platform] = videos_data["platforms"].get(platform, 0) + 1

    save_videos()
    check_mission_progress(uid, "daily", 1)
    add_user_points(uid, 2)

    with open(file_path, "rb") as video:
        bot.send_video(chat_id, video, caption=caption, reply_markup=kb)

def download_media(chat_id, text):
    try:
        url = extract_url(text)
        if not url:
            bot.send_message(chat_id, "❌ Invalid link")
            return

        if "tiktok.com" in url:
            try:
                api = f"https://tikwm.com/api/?url={url}"
                res = requests.get(api, timeout=30).json()
                if res.get("code") == 0:
                    data = res["data"]
                    if data.get("images"):
                        for i, img in enumerate(data["images"], start=1):
                            img_data = requests.get(img, timeout=30).content
                            filename = f"tiktok_{i}.jpg"
                            with open(filename, "wb") as f:
                                f.write(img_data)
                            with open(filename, "rb") as photo:
                                bot.send_photo(chat_id, photo, caption=f"📸 Photo {i}\n{CAPTION_TEXT}")
                            os.remove(filename)
                        return
                    if data.get("play"):
                        video_data = requests.get(data["play"], timeout=60).content
                        filename = "tiktok_video.mp4"
                        with open(filename, "wb") as f:
                            f.write(video_data)
                        send_video_with_music(chat_id, filename, "tiktok")
                        return
            except Exception as e:
                bot.send_message(chat_id, f"❌ TikTok error:\n{e}")
                return

        if "instagram.com" in url:
            try:
                ydl_opts = {"format": "best", "outtmpl": "instagram_%(id)s.%(ext)s", "quiet": True, "merge_output_format": "mp4"}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    entries = info["entries"] if "entries" in info else [info]
                    for entry in entries:
                        file = ydl.prepare_filename(entry)
                        if file.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                            with open(file, "rb") as photo:
                                bot.send_photo(chat_id, photo, caption=CAPTION_TEXT)
                        else:
                            send_video_with_music(chat_id, file, "instagram")
                        try:
                            os.remove(file)
                        except:
                            pass
                return
            except Exception as e:
                bot.send_message(chat_id, f"❌ Instagram error:\n{e}")
                return

        if "facebook.com" in url or "fb.watch" in url:
            ydl_opts = {"format": "bestvideo+bestaudio/best", "outtmpl": "facebook_%(id)s.%(ext)s", "merge_output_format": "mp4", "quiet": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file = ydl.prepare_filename(info)
            send_video_with_music(chat_id, file, "facebook")
            return

        if "youtube.com" in url or "youtu.be" in url:
            ydl_opts = {"format": "bestvideo+bestaudio/best", "outtmpl": "youtube_%(id)s.%(ext)s", "merge_output_format": "mp4", "quiet": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = yt_dlp.YoutubeDL(ydl_opts).extract_info(url, download=True)
                file = ydl_opts.prepare_filename(info) if False else ydl.prepare_filename(info)
            send_video_with_music(chat_id, file, "youtube")
            return

        bot.send_message(chat_id, "❌ Unsupported link")
    except Exception:
        bot.send_message(chat_id, "❌ Incorrect link.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("music_"))
def convert_music(call):
    vid_id = call.data.split("_")[1]
    if vid_id not in video_files:
        bot.answer_callback_query(call.id, "File expired")
        return
    file_path = video_files[vid_id]
    audio_path = file_path.rsplit(".",1)[0] + ".mp3"
    try:
        subprocess.run(["ffmpeg", "-y", "-i", file_path, "-vn", "-acodec","mp3", "-ab","128k", "-ar","44100", audio_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        with open(audio_path,"rb") as audio:
            bot.send_audio(call.message.chat.id, audio, title="Converted Music", performer="DownloadBot", caption=CAPTION_TEXT)
        if os.path.exists(audio_path):
            os.remove(audio_path)
        if os.path.exists(file_path):
            os.remove(file_path)
        bot.answer_callback_query(call.id, "🎵 Music converted")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Music conversion failed:\n{e}")

# ================= RUN BOTS =================
def run_bot1():
    while True:
        try:
            bot.infinity_polling(skip_pending=True)
        except Exception as e:
            print("Bot1 restart:", e)

def run_bot2():
    while True:
        try:
            bot2.infinity_polling(skip_pending=True)
        except Exception as e:
            print("Bot2 restart:", e)

if __name__ == "__main__":
    tg_client.start()
    t1 = threading.Thread(target=run_bot1)
    t2 = threading.Thread(target=run_bot2)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
