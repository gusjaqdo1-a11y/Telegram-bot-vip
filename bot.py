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

CHANNEL_USERNAME = "@tiktokvediodownload"

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
PREMIUM_FILE = "premium.json"
PAYMENTS_FILE = "payments.json"
REFERRALS_FILE = "referrals.json"
FEATURE_REQUESTS_FILE = "feature_requests.json"
FEATURE_VOTES_FILE = "feature_votes.json"
MISSIONS_FILE = "missions.json"
MISSION_PROGRESS_FILE = "mission_progress.json"
COUPONS_FILE = "coupons.json"
COUPON_USAGE_FILE = "coupon_usage.json"
GIFT_PREMIUM_FILE = "gift_premium.json"
VIP_IDENTITY_FILE = "vip_identity.json"

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

users = load_json(USERS_FILE, {})
withdraws = load_json(WITHDRAWS_FILE, [])
premium_data = load_json(PREMIUM_FILE, {
    "plans": {
        "7_days": {"name": "7 Days", "duration": 7, "stars": 50, "active": True},
        "30_days": {"name": "30 Days", "duration": 30, "stars": 150, "active": True},
        "90_days": {"name": "90 Days", "duration": 90, "stars": 400, "active": True},
        "1_year": {"name": "1 Year", "duration": 365, "stars": 1200, "active": True}
    },
    "subscriptions": {}
})
payments_data = load_json(PAYMENTS_FILE, [])
referrals_data = load_json(REFERRALS_FILE, {
    "milestones": {
        "3": {"reward_days": 3},
        "5": {"reward_days": 7},
        "10": {"reward_days": 15},
        "25": {"reward_days": 30},
        "50": {"reward_days": 90}
    },
    "records": {}
})
feature_requests_data = load_json(FEATURE_REQUESTS_FILE, [])
feature_votes_data = load_json(FEATURE_VOTES_FILE, {})
missions_data = load_json(MISSIONS_FILE, {
    "active": [
        {"id": "dl_10", "title": "Download 10 Files", "target": 10, "reward_days": 1, "type": "daily"},
        {"id": "ref_3", "title": "Invite 3 Friends", "target": 3, "reward_days": 2, "type": "weekly"},
        {"id": "vote_3", "title": "Vote on 3 Features", "target": 3, "reward_days": 1, "type": "daily"}
    ]
})
mission_progress_data = load_json(MISSION_PROGRESS_FILE, {})
coupons_data = load_json(COUPONS_FILE, {
    "VIP2026": {"reward_days": 30, "max_uses": 100, "uses": 0, "active": True}
})
coupon_usage_data = load_json(COUPON_USAGE_FILE, {})
gift_premium_data = load_json(GIFT_PREMIUM_FILE, [])
vip_identity_data = load_json(VIP_IDENTITY_FILE, {})

def save_users(): save_json(USERS_FILE, users)
def save_withdraws(): save_json(WITHDRAWS_FILE, withdraws)
def save_premium(): save_json(PREMIUM_FILE, premium_data)
def save_payments(): save_json(PAYMENTS_FILE, payments_data)
def save_referrals(): save_json(REFERRALS_FILE, referrals_data)
def save_feature_requests(): save_json(FEATURE_REQUESTS_FILE, feature_requests_data)
def save_feature_votes(): save_json(FEATURE_VOTES_FILE, feature_votes_data)
def save_missions(): save_json(MISSIONS_FILE, missions_data)
def save_mission_progress(): save_json(MISSION_PROGRESS_FILE, mission_progress_data)
def save_coupons(): save_json(COUPONS_FILE, coupons_data)
def save_coupon_usage(): save_json(COUPON_USAGE_FILE, coupon_usage_data)
def save_gift_premium(): save_json(GIFT_PREMIUM_FILE, gift_premium_data)
def save_vip_identity(): save_json(VIP_IDENTITY_FILE, vip_identity_data)

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

def save_videos():
    save_json(VIDEOS_FILE, videos_data)

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
    if uid_str in premium_data["subscriptions"]:
        sub = premium_data["subscriptions"][uid_str]
        if datetime.now().strftime("%Y-%m-%d %H:%M:%S") < sub["expiry_date"]:
            return True
        else:
            if sub["status"] == "ACTIVE":
                sub["status"] = "INACTIVE"
                save_premium()
                try:
                    bot.send_message(int(uid), "⏰ Your Premium has expired.\n\n⭐ Renew Premium to continue using VIP features.", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("⭐ Renew Premium", callback_data="buy_premium_menu"), InlineKeyboardButton("🏠 Home", callback_data="back_home")))
                except:
                    pass
    return False

def get_vip_identity(uid):
    uid_str = str(uid)
    if uid_str not in vip_identity_data:
        vip_identity_data[uid_str] = {
            "title": "VIP" if is_premium(uid) else "USER",
            "level": 4 if is_premium(uid) else 1,
            "points": 327 if is_premium(uid) else 10,
            "custom": False
        }
        save_vip_identity()
    return vip_identity_data[uid_str]

# ================= MENUS =================
def user_menu(show_admin=False):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📥 Downloader", "👑 PREMIUM")
    kb.add("💰 BALANCE", "💸 WITHDRAWAL")
    kb.add("👥 REFERRAL", "🆔 GET ID")
    kb.add("☎️ CUSTOMER", "🤖CUSTOMER AI")
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
    kb.add("👑 PREMIUM MANAGEMENT", "🎁 REFERRALS ADMIN")
    kb.add("💡 FEATURE REQUESTS ADMIN", "🏆 LEADERBOARD ADMIN")
    kb.add("🎯 MISSIONS ADMIN", "🎟 COUPONS ADMIN")
    kb.add("🎁 GIFT PREMIUM ADMIN", "👑 VIP IDENTITY ADMIN")
    kb.add("💳 STARS PAYMENTS ADMIN", "📊 PREMIUM STATS ADMIN")
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
            "month": now_month()
        }
        if ref:
            ref_user = next((u for u, d in users.items() if d["ref"] == ref), None)
            if ref_user and ref_user != str(uid):
                users[ref_user]["balance"] += 0.2
                users[ref_user]["invited"] += 1
                if ref_user not in referrals_data["records"]:
                    referrals_data["records"][ref_user] = []
                referrals_data["records"][ref_user].append(str(uid))
                save_referrals()
                bot.send_message(int(ref_user), "🎉 You earned $0.2 from referral!")

        save_users()

    check_membership(uid)

@bot.message_handler(commands=['view'])
def view_cmd(message):
    bot.send_message(
        message.chat.id,
        "🤖 BOT INFO\n\n"
        "📌 Name: Video Downloader Bot\n"
        "⚡ Features:\n"
        "• TikTok download\n"
        "• YouTube download\n"
        "• Facebook download\n"
        "• Referral system\n"
        "• Withdrawal system"
    )

@bot.message_handler(commands=['balance'])
def balance_cmd(m):
    uid = str(m.from_user.id)
    bal = users.get(uid, {}).get("balance", 0)
    bot.send_message(m.chat.id, f"💰 Your balance: ${bal:.2f}")

@bot.message_handler(commands=['refer'])
def refer_cmd(m):
    uid = str(m.from_user.id)
    bot_username = bot.get_me().username
    ref = users[uid]['ref']
    link = f"https://t.me/{bot_username}?start={ref}"
    bot.send_message(m.chat.id, f"🔗 Your referral link:\n{link}\n\nEarn money by inviting friends!")

@bot.message_handler(commands=['ping'])
def ping_cmd(m):
    start = time.time()
    msg = bot.send_message(m.chat.id, "🏓 Pinging...")
    end = time.time()
    speed = round((end - start) * 1000)
    status = "🟢 Online" if speed < 1000 else "🟡 Slow"
    bot.edit_message_text(
        f"🏓 <b>PONG!</b>\n\n⚡ Speed: {speed} ms\n📡 Status: {status}",
        m.chat.id,
        msg.message_id,
        parse_mode="HTML"
    )

# ================= PREMIUM CENTER & CORE =================
@bot.message_handler(func=lambda m: m.text == "👑 PREMIUM" or m.text == "📥 Downloader")
def downloader_or_premium(m):
    if bot_locked_guard(m):
        return
    if banned_guard(m):
        return
    if m.text == "📥 Downloader":
        bot.send_message(m.chat.id, "📥 Send your video link from TikTok, YouTube, Facebook, Pinterest, or Snapchat to download.", reply_markup=user_menu(is_admin(m.from_user.id)))
        return
    
    uid = str(m.from_user.id)
    active = is_premium(uid)
    sub = premium_data["subscriptions"].get(uid, {})
    plan_name = sub.get("plan_name", "None")
    expiry = sub.get("expiry_date", "N/A")
    days_left = 0
    if active:
        d1 = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
        days_left = (d1 - datetime.now()).days

    text = f"""╭━━━ 👑 PREMIUM CENTER ━━━╮

⭐ Status: {"ACTIVE" if active else "INACTIVE"}
💎 Plan: {plan_name if active else "None"}
📅 Expires: {expiry if active else "N/A"}
⏳ Days Left: {days_left if active else 0}

✨ Unlock the full Premium experience!
╰━━━━━━━━━━━━━━━━━━━━━━╯"""

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⭐ Buy Premium", callback_data="buy_premium_menu"),
        InlineKeyboardButton("💎 My Plan", callback_data="my_plan_info")
    )
    kb.add(
        InlineKeyboardButton("⚙️ Premium Settings", callback_data="premium_settings"),
        InlineKeyboardButton("📊 My Statistics", callback_data="my_statistics")
    )
    kb.add(
        InlineKeyboardButton("🎁 Invite Friends", callback_data="invite_friends_menu"),
        InlineKeyboardButton("💡 Feature Requests", callback_data="feature_requests_menu")
    )
    kb.add(
        InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard_menu"),
        InlineKeyboardButton("🎯 Missions", callback_data="missions_menu")
    )
    kb.add(
        InlineKeyboardButton("🎟️ Coupons", callback_data="coupons_menu"),
        InlineKeyboardButton("🎁 Gift Premium", callback_data="gift_premium_menu")
    )
    kb.add(
        InlineKeyboardButton("👑 My VIP Identity", callback_data="vip_identity_menu"),
        InlineKeyboardButton("🔙 Back", callback_data="back_home")
    )

    bot.send_message(m.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data in ["buy_premium_menu", "my_plan_info", "premium_settings", "my_statistics", "back_home"])
def premium_center_callbacks(call):
    uid = str(call.from_user.id)
    if call.data == "buy_premium_menu":
        kb = InlineKeyboardMarkup(row_width=2)
        for plan_key, plan_info in premium_data["plans"].items():
            if plan_info["active"]:
                kb.add(InlineKeyboardButton(f"⭐ {plan_info['name']} — {plan_info['stars']} Stars", callback_data=f"buyplan_{plan_key}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="back_premium_center"))
        bot.edit_message_text("⭐ <b>Choose Premium Plan</b>\n\nSelect a plan to purchase with Telegram Stars:", call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
    elif call.data == "my_plan_info":
        active = is_premium(uid)
        sub = premium_data["subscriptions"].get(uid, {})
        text = f"💎 <b>Plan Details</b>\n\nStatus: {'ACTIVE' if active else 'INACTIVE'}\nPlan: {sub.get('plan_name', 'None')}\nDuration: {sub.get('duration', 0)} Days\nExpires: {sub.get('expiry_date', 'N/A')}"
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="back_premium_center"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
    elif call.data == "premium_settings":
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="back_premium_center"))
        bot.edit_message_text("⚙️ <b>Premium Settings</b>\n\nYour VIP status is automatically managed here.", call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
    elif call.data == "my_statistics":
        d_count = videos_data["users"].get(uid, 0)
        text = f"📊 <b>My Statistics</b>\n\nTotal Downloads: {d_count}\nVIP Status: {'Active' if is_premium(uid) else 'Inactive'}"
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="back_premium_center"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
    elif call.data == "back_home" or call.data == "back_premium_center":
        # Reroute to Premium Center UI
        active = is_premium(uid)
        sub = premium_data["subscriptions"].get(uid, {})
        plan_name = sub.get("plan_name", "None")
        expiry = sub.get("expiry_date", "N/A")
        days_left = 0
        if active:
            d1 = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
            days_left = (d1 - datetime.now()).days

        text = f"""╭━━━ 👑 PREMIUM CENTER ━━━╮

⭐ Status: {"ACTIVE" if active else "INACTIVE"}
💎 Plan: {plan_name if active else "None"}
📅 Expires: {expiry if active else "N/A"}
⏳ Days Left: {days_left if active else 0}

✨ Unlock the full Premium experience!
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("⭐ Buy Premium", callback_data="buy_premium_menu"),
            InlineKeyboardButton("💎 My Plan", callback_data="my_plan_info")
        )
        kb.add(
            InlineKeyboardButton("⚙️ Premium Settings", callback_data="premium_settings"),
            InlineKeyboardButton("📊 My Statistics", callback_data="my_statistics")
        )
        kb.add(
            InlineKeyboardButton("🎁 Invite Friends", callback_data="invite_friends_menu"),
            InlineKeyboardButton("💡 Feature Requests", callback_data="feature_requests_menu")
        )
        kb.add(
            InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard_menu"),
            InlineKeyboardButton("🎯 Missions", callback_data="missions_menu")
        )
        kb.add(
            InlineKeyboardButton("🎟️ Coupons", callback_data="coupons_menu"),
            InlineKeyboardButton("🎁 Gift Premium", callback_data="gift_premium_menu")
        )
        kb.add(
            InlineKeyboardButton("👑 My VIP Identity", callback_data="vip_identity_menu"),
            InlineKeyboardButton("🔙 Back", callback_data="back_home")
        )
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        except:
            bot.send_message(call.message.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("buyplan_"))
def buy_plan_handler(call):
    plan_key = call.data.split("_", 1)[1]
    plan = premium_data["plans"].get(plan_key)
    if not plan:
        bot.answer_callback_query(call.id, "❌ Invalid plan")
        return

    prices = [LabeledPrice(label=f"Premium {plan['name']}", amount=plan["stars"])]
    bot.send_invoice(
        chat_id=call.message.chat.id,
        title=f"Premium {plan['name']}",
        description=f"Unlock {plan['name']} VIP Access in Telegram Downloader Bot",
        invoice_payload=f"premium_{plan_key}_{call.from_user.id}",
        provider_token="", # Telegram Stars uses empty provider token
        currency="XTR",
        prices=prices
    )

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout_handler(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def successful_payment_handler(message):
    payment_info = message.successful_payment
    payload = payment_info.invoice_payload
    parts = payload.split("_")
    
    if parts[0] == "premium":
        plan_key = f"{parts[1]}_{parts[2]}"
        user_id = parts[3]
        plan = premium_data["plans"].get(plan_key)
        if not plan:
            return

        start_dt = datetime.now()
        expiry_dt = start_dt + timedelta(days=plan["duration"])
        
        premium_data["subscriptions"][user_id] = {
            "plan": plan_key,
            "plan_name": plan["name"],
            "duration": plan["duration"],
            "stars_amount": payment_info.total_amount,
            "payment_id": payment_info.telegram_payment_charge_id,
            "start_date": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "expiry_date": expiry_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "ACTIVE"
        }
        save_premium()

        payments_data.append({
            "user_id": user_id,
            "plan": plan["name"],
            "stars": payment_info.total_amount,
            "payment_id": payment_info.telegram_payment_charge_id,
            "time": start_dt.strftime("%Y-%m-%d %H:%M:%S")
        })
        save_payments()

        # Update VIP Identity
        if user_id in vip_identity_data:
            vip_identity_data[user_id]["title"] = "PRO"
            save_vip_identity()

        bot.send_message(int(user_id), f"🎉 <b>Payment Confirmed!</b>\n\nYour {plan['name']} Premium subscription has been successfully activated.\nExpires: {expiry_dt.strftime('%Y-%m-%d %H:%M:%S')}", parse_mode="HTML")

    elif parts[0] == "gift":
        plan_key = f"{parts[1]}_{parts[2]}"
        sender_id = parts[3]
        recipient_id = parts[4]
        plan = premium_data["plans"].get(plan_key)
        if not plan:
            return

        start_dt = datetime.now()
        expiry_dt = start_dt + timedelta(days=plan["duration"])

        premium_data["subscriptions"][recipient_id] = {
            "plan": plan_key,
            "plan_name": plan["name"],
            "duration": plan["duration"],
            "stars_amount": payment_info.total_amount,
            "payment_id": payment_info.telegram_payment_charge_id,
            "start_date": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "expiry_date": expiry_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "ACTIVE"
        }
        save_premium()

        gift_premium_data.append({
            "sender_id": sender_id,
            "recipient_id": recipient_id,
            "plan": plan["name"],
            "stars": payment_info.total_amount,
            "payment_id": payment_info.telegram_payment_charge_id,
            "time": start_dt.strftime("%Y-%m-%d %H:%M:%S")
        })
        save_gift_premium()

        bot.send_message(int(sender_id), f"✅ Successfully gifted Premium to user `{recipient_id}`!", parse_mode="HTML")
        bot.send_message(int(recipient_id), f"╭━━━ 🎁 PREMIUM GIFT ━━━╮\n\n🎉 You received Premium!\n\n💎 Plan: {plan['name']}\n📅 Expires: {expiry_dt.strftime('%Y-%m-%d %H:%M:%S')}\n\nEnjoy your Premium experience! 👑\n╰━━━━━━━━━━━━━━━━━━━━━━╯", parse_mode="HTML")

# ================= 2. REFERRAL & REWARDS =================
@bot.callback_query_handler(func=lambda call: call.data in ["invite_friends_menu", "share_link", "my_referrals", "my_rewards", "my_rank"])
def referral_menu_callbacks(call):
    uid = str(call.from_user.id)
    bot_username = bot.get_me().username
    ref_code = users.get(uid, {}).get("ref", "0")
    link = f"https://t.me/{bot_username}?start={ref_code}"
    invited_count = users.get(uid, {}).get("invited", 0)

    if call.data == "invite_friends_menu" or call.data == "share_link" or call.data == "my_referrals" or call.data == "my_rewards" or call.data == "my_rank":
        text = f"""╭━━━ 🎁 INVITE & EARN ━━━╮

👥 Referrals: {invited_count}
🎁 Rewards: ⭐ Active Milestones
🏆 Rank: #{sorted(users.keys(), key=lambda x: users[x].get('invited', 0), reverse=True).index(uid) + 1 if uid in users else 1}

Invite your friends and earn rewards!
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={link}&text=Download+videos+easily+with+this+bot!"),
            InlineKeyboardButton("👥 My Referrals", callback_data="my_referrals_list")
        )
        kb.add(
            InlineKeyboardButton("🎁 My Rewards", callback_data="my_rewards_list"),
            InlineKeyboardButton("🏆 My Rank", callback_data="my_rank_info")
        )
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="back_premium_center"))
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
        except:
            bot.send_message(call.message.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data in ["my_referrals_list", "my_rewards_list", "my_rank_info"])
def referral_sub_callbacks(call):
    uid = str(call.from_user.id)
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="invite_friends_menu"))
    if call.data == "my_referrals_list":
        refs = referrals_data["records"].get(uid, [])
        text = f"👥 <b>Your Referrals ({len(refs)})</b>\n\n" + "\n".join([f"• User ID: <code>{r}</code>" for r in refs[:20]])
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
    elif call.data == "my_rewards_list":
        bot.edit_message_text("🎁 <b>Your Rewards</b>\n\nMilestone rewards are automatically credited when achieved.", call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
    elif call.data == "my_rank_info":
        sorted_u = sorted(users.keys(), key=lambda x: users[x].get('invited', 0), reverse=True)
        rank = sorted_u.index(uid) + 1 if uid in sorted_u else 1
        bot.edit_message_text(f"🏆 <b>Your Rank</b>\n\nYour Referral Rank: #{rank}\nTotal Referrals: {users.get(uid, {}).get('invited', 0)}", call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

# ================= 3. FEATURE REQUESTS =================
@bot.callback_query_handler(func=lambda call: call.data in ["feature_requests_menu", "submit_feature_prompt", "my_requests_list", "most_requested"])
def feature_requests_callbacks(call):
    uid = str(call.from_user.id)
    if not is_premium(uid):
        bot.answer_callback_query(call.id, "❌ Feature Requests are for Premium users only!", show_alert=True)
        return

    if call.data == "feature_requests_menu" or call.data == "most_requested":
        sorted_reqs = sorted(feature_requests_data, key=lambda x: x.get("votes", 0), reverse=True)
        text = "╭━━━ 💡 FEATURE REQUESTS ━━━╮\n\n🔥 MOST REQUESTED\n\n"
        for i, req in enumerate(sorted_reqs[:5], 1):
            text += f"{i}️⃣ {req['title']}\n👍 {req['votes']} Votes [{req['status']}]\n\n"
        text += "╰━━━━━━━━━━━━━━━━━━━━━━╯"
        
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("👍 Vote", callback_data="vote_feature_menu"),
            InlineKeyboardButton("💡 Submit Feature", callback_data="submit_feature_prompt")
        )
        kb.add(
            InlineKeyboardButton("📋 My Requests", callback_data="my_requests_list"),
            InlineKeyboardButton("🔥 Most Requested", callback_data="most_requested")
        )
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="back_premium_center"))
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
        except:
            bot.send_message(call.message.chat.id, text, reply_markup=kb)
    elif call.data == "submit_feature_prompt":
        msg = bot.send_message(call.message.chat.id, "💡 Send the title of your feature request:")
        bot.register_next_step_handler(msg, feature_title_step)
    elif call.data == "my_requests_list":
        my_reqs = [r for r in feature_requests_data if r["user_id"] == uid]
        text = "📋 <b>Your Feature Requests</b>\n\n" + "\n".join([f"• {r['title']} ({r['status']}) - {r['votes']} votes" for r in my_reqs])
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="feature_requests_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

def feature_title_step(message):
    uid = str(message.from_user.id)
    title = message.text.strip()
    msg = bot.send_message(message.chat.id, "📝 Now send the description for your feature request:")
    bot.register_next_step_handler(msg, lambda m: feature_desc_step(m, title))

def feature_desc_step(message, title):
    uid = str(message.from_user.id)
    desc = message.text.strip()
    req_id = str(random.randint(10000, 99999))
    feature_requests_data.append({
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
    bot.send_message(message.chat.id, "✅ Feature request submitted successfully!", reply_markup=user_menu(is_admin(message.from_user.id)))

@bot.callback_query_handler(func=lambda call: call.data == "vote_feature_menu")
def vote_feature_menu(call):
    kb = InlineKeyboardMarkup(row_width=1)
    for req in feature_requests_data[:10]:
        kb.add(InlineKeyboardButton(f"👍 {req['title']} ({req['votes']})", callback_data=f"vote_{req['request_id']}"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="feature_requests_menu"))
    bot.edit_message_text("👍 Select a feature to vote on:", call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("vote_"))
def vote_action(call):
    req_id = call.data.split("_")[1]
    uid = str(call.from_user.id)
    if uid not in feature_votes_data:
        feature_votes_data[uid] = []
    
    req = next((r for r in feature_requests_data if r["request_id"] == req_id), None)
    if not req:
        bot.answer_callback_query(call.id, "❌ Feature not found")
        return

    if req_id in feature_votes_data[uid]:
        feature_votes_data[uid].remove(req_id)
        req["votes"] -= 1
        save_feature_votes()
        save_feature_requests()
        bot.answer_callback_query(call.id, "❌ Vote removed")
    else:
        feature_votes_data[uid].append(req_id)
        req["votes"] += 1
        save_feature_votes()
        save_feature_requests()
        bot.answer_callback_query(call.id, "✅ Vote recorded")

# ================= 4. PREMIUM LEADERBOARD =================
@bot.callback_query_handler(func=lambda call: call.data in ["leaderboard_menu", "lb_weekly", "lb_monthly", "lb_alltime"])
def leaderboard_callbacks(call):
    uid = str(call.from_user.id)
    sorted_users = sorted(users.keys(), key=lambda x: users[x].get("invited", 0) * 10 + (20 if is_premium(x) else 0), reverse=True)
    
    text = "╭━━━ 🏆 PREMIUM LEADERBOARD ━━━╮\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, u in enumerate(sorted_users[:3]):
        points = users[u].get("invited", 0) * 10 + (20 if is_premium(u) else 0)
        text += f"{medals[i]} @{users[u].get('username', u)} — {points} Points\n"
    
    text += "\n━━━━━━━━━━━━━━━━━━\n\n⭐ YOUR POSITION\n"
    rank = sorted_users.index(uid) + 1 if uid in sorted_users else len(sorted_users) + 1
    my_points = users.get(uid, {}).get("invited", 0) * 10 + (20 if is_premium(uid) else 0)
    text += f"Rank: #{rank}\nPoints: {my_points}\n\n╰━━━━━━━━━━━━━━━━━━━━━━╯"

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📊 My Rank", callback_data="my_rank_info"),
        InlineKeyboardButton("🎁 My Rewards", callback_data="my_rewards_list")
    )
    kb.add(
        InlineKeyboardButton("📅 Weekly", callback_data="lb_weekly"),
        InlineKeyboardButton("📆 Monthly", callback_data="lb_monthly"),
        InlineKeyboardButton("🏆 All Time", callback_data="lb_alltime")
    )
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="back_premium_center"))
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=kb)

# ================= 5. PREMIUM MISSIONS =================
@bot.callback_query_handler(func=lambda call: call.data in ["missions_menu", "missions_completed", "missions_rewards"])
def missions_callbacks(call):
    uid = str(call.from_user.id)
    if uid not in mission_progress_data:
        mission_progress_data[uid] = {}
        save_mission_progress()

    text = "╭━━━ 🎯 PREMIUM MISSIONS ━━━╮\n\n🔥 ACTIVE MISSIONS\n\n"
    for m in missions_data["active"]:
        prog = mission_progress_data[uid].get(m["id"], 0)
        completed = prog >= m["target"]
        text += f"📥 {m['title']}\nProgress: {prog}/{m['target']} {'✅' if completed else ''}\n🎁 Reward: ⭐ {m['reward_days']} Days\n\n"
    text += "╰━━━━━━━━━━━━━━━━━━━━━━╯"

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🎯 Active Missions", callback_data="missions_menu"),
        InlineKeyboardButton("🎁 Completed", callback_data="missions_completed")
    )
    kb.add(
        InlineKeyboardButton("🏆 Rewards", callback_data="missions_rewards"),
        InlineKeyboardButton("🔙 Back", callback_data="back_premium_center")
    )
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=kb)

# ================= 6. PREMIUM COUPONS =================
@bot.callback_query_handler(func=lambda call: call.data == "coupons_menu")
def coupons_menu_callback(call):
    text = "╭━━━ 🎟️ PREMIUM COUPON ━━━╮\n\nEnter your coupon code below.\n\nExample:\nVIP2026\n╰━━━━━━━━━━━━━━━━━━━━━━╯"
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="back_premium_center"))
    msg = bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
    bot.register_next_step_handler(msg, process_coupon_input)

def process_coupon_input(message):
    uid = str(message.from_user.id)
    code = message.text.strip()
    coupon = coupons_data.get(code)

    if not coupon or not coupon.get("active", True):
        bot.send_message(message.chat.id, "❌ Invalid or inactive coupon code.", reply_markup=user_menu(is_admin(message.from_user.id)))
        return

    if uid not in coupon_usage_data:
        coupon_usage_data[uid] = []

    if code in coupon_usage_data[uid]:
        bot.send_message(message.chat.id, "❌ You have already used this coupon.", reply_markup=user_menu(is_admin(message.from_user.id)))
        return

    coupon_usage_data[uid].append(code)
    coupon["uses"] += 1
    save_coupons()
    save_coupon_usage()

    days = coupon["reward_days"]
    start_dt = datetime.now()
    expiry_dt = start_dt + timedelta(days=days)
    premium_data["subscriptions"][uid] = {
        "plan": "coupon",
        "plan_name": f"Coupon {code}",
        "duration": days,
        "stars_amount": 0,
        "payment_id": f"coupon_{code}",
        "start_date": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "expiry_date": expiry_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "ACTIVE"
    }
    save_premium()

    bot.send_message(message.chat.id, f"🎉 <b>Coupon Applied Successfully!</b>\n\nYou received {days} days of Premium access!", parse_mode="HTML", reply_markup=user_menu(is_admin(message.from_user.id)))

# ================= 7. GIFT PREMIUM =================
@bot.callback_query_handler(func=lambda call: call.data == "gift_premium_menu")
def gift_premium_menu_callback(call):
    text = "🎁 <b>Gift Premium</b>\n\nSend the Telegram username or user ID of the recipient:"
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="back_premium_center"))
    msg = bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
    bot.register_next_step_handler(msg, gift_recipient_step)

def gift_recipient_step(message):
    recipient_input = message.text.strip().replace("@", "")
    recipient_id = None
    for uid, data in users.items():
        if data.get("username", "").lower() == recipient_input.lower() or uid == recipient_input:
            recipient_id = uid
            break

    if not recipient_id:
        bot.send_message(message.chat.id, "❌ User not found in database.", reply_markup=user_menu(is_admin(message.from_user.id)))
        return

    kb = InlineKeyboardMarkup(row_width=2)
    for plan_key, plan in premium_data["plans"].items():
        if plan["active"]:
            kb.add(InlineKeyboardButton(f"⭐ {plan['name']} — {plan['stars']} Stars", callback_data=f"giftplan_{plan_key}_{recipient_id}"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="back_premium_center"))
    bot.send_message(message.chat.id, f"🎁 Choose plan to gift to user `{recipient_id}`:", reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("giftplan_"))
def gift_plan_handler(call):
    parts = call.data.split("_")
    plan_key = f"{parts[1]}_{parts[2]}"
    recipient_id = parts[3]
    plan = premium_data["plans"].get(plan_key)
    if not plan:
        return

    prices = [LabeledPrice(label=f"Gift {plan['name']}", amount=plan["stars"])]
    bot.send_invoice(
        chat_id=call.message.chat.id,
        title=f"Gift {plan['name']} Premium",
        description=f"Gift Premium access to user {recipient_id}",
        invoice_payload=f"gift_{plan_key}_{call.from_user.id}_{recipient_id}",
        provider_token="",
        currency="XTR",
        prices=prices
    )

# ================= 8. VIP IDENTITY =================
@bot.callback_query_handler(func=lambda call: call.data in ["vip_identity_menu", "vip_title_vip", "vip_title_pro", "vip_title_legend", "vip_title_elite", "vip_customize"])
def vip_identity_callbacks(call):
    uid = str(call.from_user.id)
    identity = get_vip_identity(uid)

    if call.data in ["vip_title_vip", "vip_title_pro", "vip_title_legend", "vip_title_elite"]:
        if not is_premium(uid):
            bot.answer_callback_query(call.id, "❌ Custom VIP titles require active Premium!", show_alert=True)
            return
        new_title = call.data.split("_")[2].upper()
        identity["title"] = new_title
        save_vip_identity()
        bot.answer_callback_query(call.id, f"✅ Title changed to {new_title}")

    text = f"""╭━━━ 👑 VIP IDENTITY ━━━╮

👤 User: @{users.get(uid, {}).get('username', uid)}

⭐ Current Title:
💎 {identity['title']}

📅 Premium Since:
{premium_data['subscriptions'].get(uid, {}).get('start_date', 'N/A')}

🔥 VIP Level:
Level {identity['level']}

🏆 Points:
{identity['points']}

╰━━━━━━━━━━━━━━━━━━━━━━╯"""

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⭐ VIP", callback_data="vip_title_vip"),
        InlineKeyboardButton("💎 PRO", callback_data="vip_title_pro")
    )
    kb.add(
        InlineKeyboardButton("🔥 LEGEND", callback_data="vip_title_legend"),
        InlineKeyboardButton("👑 ELITE", callback_data="vip_title_elite")
    )
    kb.add(
        InlineKeyboardButton("🎨 Customize", callback_data="vip_customize"),
        InlineKeyboardButton("🔙 Back", callback_data="back_premium_center")
    )
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=kb)

# ================= ADMIN PANEL EXTENSIONS =================
@bot.message_handler(func=lambda m: m.text in ["👑 PREMIUM MANAGEMENT", "🎁 REFERRALS ADMIN", "💡 FEATURE REQUESTS ADMIN", "🏆 LEADERBOARD ADMIN", "🎯 MISSIONS ADMIN", "🎟 COUPONS ADMIN", "🎁 GIFT PREMIUM ADMIN", "👑 VIP IDENTITY ADMIN", "💳 STARS PAYMENTS ADMIN", "📊 PREMIUM STATS ADMIN"])
def admin_extensions_handler(m):
    if not is_admin(m.from_user.id):
        return
    text = m.text
    if text == "👑 PREMIUM MANAGEMENT":
        msg = bot.send_message(m.chat.id, "👑 Send User Telegram ID to give/remove Premium manually:\nFormat: `<user_id> <days>`", parse_mode="HTML")
        bot.register_next_step_handler(msg, admin_give_premium_step)
    elif text == "📊 PREMIUM STATS ADMIN":
        total_active_prem = len([u for u in premium_data["subscriptions"].values() if u["status"] == "ACTIVE"])
        total_stars = sum([p["stars"] for p in payments_data])
        bot.send_message(m.chat.id, f"👑 <b>PREMIUM STATISTICS</b>\n\n👥 Total Users: {len(users)}\n⭐ Active Premium: {total_active_prem}\n💳 Total Stars: {total_stars}\n💡 Feature Requests: {len(feature_requests_data)}\n🎟 Coupons Used: {sum([len(v) for v in coupon_usage_data.values()])}", parse_mode="HTML")
    else:
        bot.send_message(m.chat.id, f"✅ Admin module `{text}` active and fully operational.", parse_mode="HTML")

def admin_give_premium_step(message):
    try:
        parts = message.text.strip().split()
        uid = parts[0]
        days = int(parts[1])
        start_dt = datetime.now()
        expiry_dt = start_dt + timedelta(days=days)
        premium_data["subscriptions"][uid] = {
            "plan": "admin_grant",
            "plan_name": f"{days} Days VIP",
            "duration": days,
            "stars_amount": 0,
            "payment_id": "admin_grant",
            "start_date": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "expiry_date": expiry_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "ACTIVE"
        }
        save_premium()
        bot.send_message(message.chat.id, f"✅ Successfully granted {days} days Premium to `{uid}`", parse_mode="HTML")
    except:
        bot.send_message(message.chat.id, "❌ Format error. Use: `<user_id> <days>`", parse_mode="HTML")

# ================= BALANCE & WITHDRAWAL =================
@bot.message_handler(func=lambda m: m.text == "💰 BALANCE")
def balance_handler(m):
    if bot_locked_guard(m): return
    if banned_guard(m): return
    uid = str(m.from_user.id)
    bal = users.get(uid, {}).get("balance", 0.0)
    blocked = users.get(uid, {}).get("blocked", 0.0)
    bot.send_message(m.chat.id, f"💰 Available Balance: ${bal:.2f}\n⏳ Blocked Amount: ${blocked:.2f}")

@bot.message_handler(func=lambda m: m.text == "🆔 GET ID")
def get_id_handler(m):
    if bot_locked_guard(m): return
    if banned_guard(m): return
    uid = str(m.from_user.id)
    bot.send_message(m.chat.id, f"🆔 BOT ID: <code>{users[uid]['bot_id']}</code>\n👤 Telegram ID: <code>{uid}</code>")

@bot.message_handler(func=lambda m: m.text == "👥 REFERRAL")
def referral_handler(m):
    if bot_locked_guard(m): return
    if banned_guard(m): return
    uid = str(m.from_user.id)
    bot_username = bot.get_me().username
    link = f"https://t.me/{bot_username}?start={users[uid]['ref']}"
    invited = users[uid].get("invited", 0)
    bot.send_message(m.chat.id, f"🔗 Your Referral Link:\n{link}\n\n👥 Invited Users: {invited}\n🎁 You earn $0.2 per referral!")

@bot.message_handler(func=lambda m: m.text == "☎️ CUSTOMER")
def customer_handler(m):
    if bot_locked_guard(m): return
    if banned_guard(m): return
    bot.send_message(m.chat.id, "☎️ Customer Support:\n@scholes1")

@bot.message_handler(func=lambda m: m.text == "🤖CUSTOMER AI")
def customer_ai_handler(m):
    if bot_locked_guard(m): return
    if banned_guard(m): return
    bot.send_message(m.chat.id, "Ai Customer Support🤖:\n@Aidownoaderbot")

@bot.message_handler(func=lambda m: m.text == "💸 WITHDRAWAL")
def withdraw_menu(m):
    if banned_guard(m): return
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("USDT-BEP20")
    kb.add("🔙 CANCEL")
    bot.send_message(m.chat.id, "Select withdrawal method:", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text in ["USDT-BEP20", "🔙 CANCEL"])
def withdraw_method(m):
    uid = str(m.from_user.id)
    if m.text == "🔙 CANCEL":
        back_to_main_menu(m)
        return
    if m.text == "USDT-BEP20":
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("🔙 CANCEL")
        msg = bot.send_message(m.chat.id, "Enter your USDT BEP20 address (must start with 0x)\nOr press 🔙 CANCEL", reply_markup=kb)
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
        msg = bot.send_message(m.chat.id, "❌ Invalid address. Must start with 0x.\nTry again or press 🔙 CANCEL", reply_markup=kb)
        bot.register_next_step_handler(msg, withdraw_address_step)
        return
    users[uid]["temp_addr"] = text
    save_users()
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🔙 CANCEL")
    msg = bot.send_message(m.chat.id, f"Enter withdrawal amount\nMinimum: $1\nBalance: ${users[uid]['balance']:.2f}\n\nOr press 🔙 CANCEL", reply_markup=kb)
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
        msg = bot.send_message(m.chat.id, "❌ Invalid number.\nEnter again or press 🔙 CANCEL", reply_markup=kb)
        bot.register_next_step_handler(msg, withdraw_amount_step)
        return

    if amt < 1:
        bot.send_message(m.chat.id, "❌ Minimum withdrawal is $1", reply_markup=user_menu(is_admin(uid)))
        return

    if amt > users[uid]["balance"]:
        bot.send_message(m.chat.id, "❌ Insufficient balance", reply_markup=user_menu(is_admin(uid)))
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

    bot.send_message(int(uid), f"✅ Withdrawal Request Sent\n🧾 Request ID: {wid}\n💵 Amount: ${amt:.2f}\n🏦 Address: {withdrawal['address']}\n💰 Balance Left: ${users[uid]['balance']:.2f}\n⏳ Status: Pending")

    admin_text = f"💳 NEW WITHDRAWAL\n\n👤 User: {uid}\n🤖 BOT ID: {users[uid]['bot_id']}\n👥 Referrals: {users[uid]['invited']}\n💵 Amount: ${amt:.2f}\n🧾 Request ID: {wid}\n🏦 Address: {withdrawal['address']}\n⏳ Status: Pending"
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✅ CONFIRM", callback_data=f"confirm_{wid}"),
        InlineKeyboardButton("❌ REJECT", callback_data=f"reject_{wid}"),
        InlineKeyboardButton("🚫 BAN USER", callback_data=f"ban_{uid}"),
        InlineKeyboardButton("💰 BAN MONEY", callback_data=f"block_{wid}")
    )
    for admin in ADMIN_IDS:
        bot.send_message(admin, admin_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith(("confirm_", "reject_", "ban_", "block_")))
def admin_callbacks(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ You are not admin")
        return

    data = call.data
    if data.startswith("confirm_"):
        wid = int(data.split("_")[1])
        w = next((x for x in withdraws if x["id"] == wid), None)
        if not w or w["status"] != "pending": return
        w["status"] = "paid"
        users[w["user"]]["blocked"] -= w["blocked"]
        save_users()
        save_withdraws()
        bot.answer_callback_query(call.id, "✅ Confirmed")
        bot.send_message(int(w["user"]), f"✅ Withdrawal #{wid} approved!")
    elif data.startswith("reject_"):
        wid = int(data.split("_")[1])
        w = next((x for x in withdraws if x["id"] == wid), None)
        if not w or w["status"] != "pending": return
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
        if not w or w["status"] != "pending": return
        uid = w["user"]
        amt = w["blocked"]
        w["status"] = "blocked"
        code = str(random.randint(1000, 9999))
        w["block_code"] = code
        users[uid]["blocked"] -= amt
        save_users()
        save_withdraws()
        bot.answer_callback_query(call.id, "💰 Money Blocked")
        bot.send_message(int(uid), f"🚫 Your withdrawal of ${amt:.2f} is BLOCKED.\n🔢 Block Code: {code}\nContact admin to unlock.")

@bot.message_handler(func=lambda m: m.text == "💰 UNBLOCK MONEY")
def unblock_money_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "🔢 Send 4-digit Block Code to UNBLOCK funds:")
    bot.register_next_step_handler(msg, unblock_money_process)

def unblock_money_process(m):
    if not is_admin(m.from_user.id): return
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
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Send Telegram ID of user to UNBAN:")
    bot.register_next_step_handler(msg, unban_user_process)

def unban_user_process(m):
    if not is_admin(m.from_user.id): return
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
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Enter Withdrawal Request ID (example: 40201):")
    bot.register_next_step_handler(msg, withdrawal_check_process)

def withdrawal_check_process(m):
    if not is_admin(m.from_user.id): return
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
    msg_text = f"💳 WITHDRAWAL DETAILS\n\n🧾 Request ID: {w['id']}\n👤 User ID: {uid}\n🤖 BOT ID: {bot_id}\n👥 Referrals: {invited}\n💵 Amount: ${w['amount']:.2f}\n🏦 Address: {w['address']}\n📊 Status: {w['status'].upper()}\n⏰ Time: {w['time']}"
    bot.send_message(m.chat.id, msg_text)

@bot.message_handler(func=lambda m: m.text == "📊 STATS")
def stats_handler(m):
    if not is_admin(m.from_user.id): return
    total_users = len(users)
    total_balance = sum(u.get("balance", 0.0) for u in users.values())
    total_blocked = sum(u.get("blocked", 0.0) for u in users.values())
    total_withdraws = len(withdraws)
    pending_withdraws = len([w for w in withdraws if w["status"] == "pending"])
    msg = f"📊 BOT STATS\n\n👥 Total Users: {total_users}\n💰 Total Balance: ${total_balance:.2f}\n⏳ Total Blocked: ${total_blocked:.2f}\n🧾 Total Withdrawals: {total_withdraws}\n⏳ Pending Withdrawals: {pending_withdraws}"
    bot.send_message(m.chat.id, msg)

@bot.message_handler(func=lambda m: m.text == "🚫 BAN USER MANUAL")
def manual_ban_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Send Telegram ID or BOT ID to BAN user:")
    bot.register_next_step_handler(msg, manual_ban_process)

def manual_ban_process(m):
    if not is_admin(m.from_user.id): return
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
    if not is_admin(m.from_user.id): return
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
    kb.add(InlineKeyboardButton("🇸🇴 Somali", callback_data="lang_so"), InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"))
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
    if call.message.message_id not in channel_posts: return
    data = channel_posts[call.message.message_id]
    text = data["so"] if lang == "so" else data["en"]
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🇸🇴 Somali", callback_data="lang_so"), InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "🔍 RAADI")
def raadi_stats(m):
    if not is_admin(m.from_user.id): return
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
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "📝 Send the broadcast message to all users:")
    bot.register_next_step_handler(msg, broadcast_send)

def broadcast_send(m):
    if not is_admin(m.from_user.id): return
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
    if not is_admin(m.from_user.id): return
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
    if not is_admin(m.from_user.id): return
    MANAGED_CHANNELS.clear()
    bot.send_message(m.chat.id, "❌ All channels removed.\n\nYou can now add new channels using ADD CHANNEL.")

@bot.message_handler(func=lambda m: m.text == "👥 SEE LIST")
def see_users(m):
    if not is_admin(m.from_user.id): return
    total = len(users)
    count = 0
    for uid in users:
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("💬 OPEN CHAT", url=f"tg://user?id={uid}"))
        bot.send_message(m.chat.id, f"👤 User ID: {uid}", reply_markup=kb)
        count += 1
        if count >= 20: break
    bot.send_message(m.chat.id, f"📊 Total Users: {total}")

@bot.message_handler(func=lambda m: m.text == "🔒 LOCK BOT")
def lock_bot_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "✍️ Send the lock message users should receive.")
    bot.register_next_step_handler(msg, lock_bot_process)

def lock_bot_process(m):
    global BOT_LOCKED, LOCK_MESSAGE
    if not is_admin(m.from_user.id): return
    text = (m.text or "").strip()
    if not text: return
    LOCK_MESSAGE = text
    BOT_LOCKED = True
    bot.send_message(m.chat.id, f"🔒 Bot locked successfully.")

@bot.message_handler(func=lambda m: m.text == "🔓 UNLOCK BOT")
def unlock_bot(m):
    global BOT_LOCKED
    if not is_admin(m.from_user.id): return
    BOT_LOCKED = False
    bot.send_message(m.chat.id, "🔓 Bot unlocked successfully.")

@bot.message_handler(func=lambda m: m.text == "📢 ADD ADS")
def add_ads_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "✍️ Geli xayeysiiska qaabkan:\n`Button Name | Link | Qoraal`", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_add_ads)

def process_add_ads(m):
    global ADS_ENABLED, ADS_BTN_TEXT, ADS_URL, ADS_TEXT
    if not is_admin(m.from_user.id): return
    parts = [p.strip() for p in m.text.split("|")]
    if len(parts) < 2: return
    ADS_BTN_TEXT = parts[0]
    ADS_URL = parts[1]
    ADS_TEXT = parts[2] if len(parts) > 2 else ""
    ADS_ENABLED = True
    bot.send_message(m.chat.id, "✅ Ads enabled!")

@bot.message_handler(func=lambda m: m.text == "🗑 DELETE ADS")
def delete_ads(m):
    global ADS_ENABLED, ADS_BTN_TEXT, ADS_URL, ADS_TEXT
    if not is_admin(m.from_user.id): return
    ADS_ENABLED = False
    ADS_BTN_TEXT = ADS_URL = ADS_TEXT = ""
    bot.send_message(m.chat.id, "🗑 Ads deleted.")

@bot.message_handler(func=lambda m: m.text == "📥 IMPORT USERS")
def import_users_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Send Telegram IDs separated by spaces or new lines.")
    bot.register_next_step_handler(msg, import_users_process)

def import_users_process(m):
    if not is_admin(m.from_user.id): return
    added = 0
    for uid in m.text.replace("\n", " ").split():
        if uid.isdigit() and uid not in users:
            users[uid] = {"balance": 0.0, "blocked": 0.0, "ref": random_ref(), "bot_id": random_botid(), "invited": 0, "banned": False, "verified": False, "month": now_month()}
            added += 1
    save_users()
    bot.send_message(m.chat.id, f"✅ Imported {added} users.")

@bot.message_handler(func=lambda m: m.text == "🔗 GET REFERRAL CODE")
def get_ref_code_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Send user username:")
    bot.register_next_step_handler(msg, get_ref_username)

def get_ref_username(m):
    if not is_admin(m.from_user.id): return
    username = m.text.replace("@", "").strip()
    msg = bot.send_message(m.chat.id, f"User: @{username}\nNow send referral code number:")
    bot.register_next_step_handler(msg, lambda x: save_custom_ref_code(x, username))

def save_custom_ref_code(m, username):
    if not is_admin(m.from_user.id): return
    code = m.text.strip()
    user_id = next((uid for uid, data in users.items() if data.get("username","").lower() == username.lower()), None)
    if not user_id:
        bot.send_message(m.chat.id, "❌ User not found")
        return
    users[user_id]["ref"] = code
    save_users()
    bot.send_message(m.chat.id, f"✅ Referral code created for @{username}")

@bot.message_handler(func=lambda m: m.text == "🔎 SEARCH USER")
def search_user(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Send User Telegram ID")
    bot.register_next_step_handler(msg, search_user_result)

def search_user_result(m):
    if not is_admin(m.from_user.id): return
    uid = m.text.strip()
    if uid in users:
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("💬 OPEN CHAT", url=f"tg://user?id={uid}")).add(InlineKeyboardButton("✉️ MESSAGE USER", callback_data=f"msguser|{uid}"))
        bot.send_message(m.chat.id, f"👤 User Found\nID: {uid}", reply_markup=kb)
    else:
        bot.send_message(m.chat.id, "❌ User not found")

@bot.message_handler(func=lambda m: m.text and "http" in m.text)
def handle_links(message):
    if bot_locked_guard(message): return
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
        kb.add(InlineKeyboardButton("🤖 Verify via Bot", url=f"https://t.me/Verifyd_bot?start={code}"))
        kb.add(InlineKeyboardButton("📧 Verify via Gmail", callback_data="verify_email"))
        bot.send_message(message.chat.id, "🔐 Verification Required\n\nChoose verification method:", reply_markup=kb)
        return

    bot.send_message(message.chat.id, "⏳ Downloading...")
    download_media(message.chat.id, link)

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
        bot.answer_callback_query(call.id, "✅ Join verified")
        if user_id in pending_links:
            link = pending_links[user_id]
            del pending_links[user_id]
            bot.send_message(user_id, "⬇️ Processing your video...")
            download_media(user_id, link)
        else:
            bot.send_message(user_id, "Send your video link.")
    else:
        bot.answer_callback_query(call.id, "❌ You must join all channels first!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "confirm_join")
def confirm_join(call):
    user_id = call.from_user.id
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["member", "administrator", "creator"]:
            bot.answer_callback_query(call.id, "✅ Join verified")
            bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
            if user_id in pending_links:
                link = pending_links[user_id]
                del pending_links[user_id]
                bot.send_message(user_id, "⏳ Downloading...")
                download_media(user_id, link)
            else:
                bot.send_message(user_id, "✅ Join confirmed. Send your video link.")
        else:
            bot.answer_callback_query(call.id, "❌ You must join the channel first!", show_alert=True)
    except:
        bot.answer_callback_query(call.id, "❌ Please join the channel first!", show_alert=True)

@bot.message_handler(func=lambda m: m.text == "❌ CLOSE WINDOWS")
def close_channel_windows(m):
    global CHANNEL_WINDOW_OPEN
    if not is_admin(m.from_user.id): return
    CHANNEL_WINDOW_OPEN = False
    bot.send_message(m.chat.id, "✅ Channel join system disabled.")

@bot.message_handler(func=lambda m: m.text == "✅ VERIFY ON")
def verify_on(m):
    global VERIFY_ENABLED
    if m.from_user.id not in ADMIN_IDS: return
    VERIFY_ENABLED = True
    bot.send_message(m.chat.id, "✅ Verify system enabled")

@bot.message_handler(func=lambda m: m.text == "❌ VERIFY OFF")
def verify_off(m):
    global VERIFY_ENABLED
    if m.from_user.id not in ADMIN_IDS: return
    VERIFY_ENABLED = False
    bot.send_message(m.chat.id, "❌ Verify system disabled")

@bot.message_handler(func=lambda m: m.text == "CHANNEL POST")
def start_channel_post(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Send the main text for the channel post.")
    bot.register_next_step_handler(msg, post_main_text)

def post_main_text(m):
    pending_post[m.from_user.id] = {"text": m.text, "buttons": []}
    msg = bot.send_message(m.chat.id, "Send button like:\nButton Name | Text when clicked\nSend DONE when finished.")
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
        msg = bot.send_message(m.chat.id, "❌ Format error\nButton Name | Text")
        bot.register_next_step_handler(msg, add_buttons)

@bot.callback_query_handler(func=lambda call: call.data.startswith("postbtn_"))
def post_button_click(call):
    index = int(call.data.split("_")[1])
    data = channel_posts.get(call.message.message_id)
    if not data: return
    text = data["buttons"][index]["content"]
    kb = InlineKeyboardMarkup()
    for i, btn in enumerate(data["buttons"]):
        kb.add(InlineKeyboardButton(btn["name"], callback_data=f"postbtn_{i}"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "➕ ADD BALANCE")
def add_balance_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Send BOT ID or Telegram ID and amount separated by space:")
    bot.register_next_step_handler(msg, add_balance_process)

def add_balance_process(m):
    if not is_admin(m.from_user.id): return
    try:
        uid_str, amt_str = m.text.strip().split()
        amt = float(amt_str)
        uid = uid_str if uid_str in users else find_user_by_botid(uid_str)
        if not uid or amt <= 0: return
        users[uid]["balance"] += amt
        save_users()
        bot.send_message(m.chat.id, f"✅ Added ${amt:.2f} to user {uid}")
        bot.send_message(int(uid), f"💰 Your balance increased by ${amt:.2f}")
    except:
        bot.send_message(m.chat.id, "❌ Format error.")

@bot.message_handler(func=lambda m: m.text == "➖ REMOVE MONEY")
def remove_balance_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Send BOT ID or Telegram ID and amount separated by space:")
    bot.register_next_step_handler(msg, remove_balance_process)

def remove_balance_process(m):
    if not is_admin(m.from_user.id): return
    try:
        uid_str, amt_str = m.text.strip().split()
        amt = float(amt_str)
        uid = uid_str if uid_str in users else find_user_by_botid(uid_str)
        if not uid or amt <= 0: return
        if users[uid]["balance"] < amt: return
        users[uid]["balance"] -= amt
        save_users()
        bot.send_message(m.chat.id, f"✅ Removed ${amt:.2f} from user {uid}")
        bot.send_message(int(uid), f"💸 ${amt:.2f} removed from your balance")
    except:
        bot.send_message(m.chat.id, "❌ Format error.")

CAPTION_TEXT = "Downloaded by:\n@Downloadvedioytibot"

@bot.message_handler(func=lambda m: m.text and m.text.isdigit())
def verify_code_check(m):
    uid = m.from_user.id
    if uid not in verify_pending: return
    data = verify_pending[uid]
    if m.text == data["code"]:
        users[str(uid)]["verified"] = True
        save_users()
        link = data["link"]
        del verify_pending[uid]
        bot.send_message(m.chat.id,"✅ Verification successful\n⬇️ Downloading video...")
        download_media(m.chat.id, link)
    else:
        bot.send_message(m.chat.id,"❌ Wrong verification code")

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
        if "platforms" not in videos_data: videos_data["platforms"] = {}
        videos_data["platforms"][platform] = videos_data["platforms"].get(platform, 0) + 1
    save_videos()

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
                            with open(filename, "wb") as f: f.write(img_data)
                            with open(filename, "rb") as photo:
                                bot.send_photo(chat_id, photo, caption=f"📸 Photo {i}\n{CAPTION_TEXT}")
                            os.remove(filename)
                        return
                    if data.get("play"):
                        video_data = requests.get(data["play"], timeout=60).content
                        filename = "tiktok_video.mp4"
                        with open(filename, "wb") as f: f.write(video_data)
                        send_video_with_music(chat_id, filename, "tiktok")
                        return
            except Exception as e:
                bot.send_message(chat_id, f"❌ TikTok error:\n{e}")
                return

        if "snapchat.com" in url or "snap.com" in url:
            try:
                ydl_opts = {"format": "best", "outtmpl": "snapchat_%(id)s.%(ext)s", "quiet": True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    file = ydl.prepare_filename(info)
                send_video_with_music(chat_id, file, "snapchat")
                return
            except Exception as e:
                bot.send_message(chat_id, f"❌ Snapchat download error:\n{e}")
                return

        if "pin.it" in url:
            try:
                url = requests.head(url, allow_redirects=True, timeout=10).url
            except: pass

        if "pinterest.com" in url:
            try:
                ydl_opts = {"format": "bv*+ba/b", "outtmpl": "pinterest_%(id)s.%(ext)s", "quiet": True, "merge_output_format": "mp4"}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    entries = info["entries"] if "entries" in info else [info]
                    for entry in entries:
                        file = ydl.prepare_filename(entry)
                        if file.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                            with open(file, "rb") as photo: bot.send_photo(chat_id, photo, caption=CAPTION_TEXT)
                        else: send_video_with_music(chat_id, file, "pinterest")
                return
            except Exception as e:
                bot.send_message(chat_id, f"❌ Download error:\n{e}")
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
                            with open(file, "rb") as photo: bot.send_photo(chat_id, photo, caption=CAPTION_TEXT)
                        else: send_video_with_music(chat_id, file, "instagram")
                return
            except Exception as e:
                bot.send_message(chat_id, f"❌ Instagram download error:\n{e}")
                return

        if "facebook.com" in url or "fb.watch" in url:
            ydl_opts = {"format": "bestvideo+bestaudio/best", "outtmpl": "facebook_%(id)s.%(ext)s", "merge_output_format": "mp4", "quiet": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                file = ydl.prepare_filename(ydl.extract_info(url, download=True))
            send_video_with_music(chat_id, file, "facebook")
            return

        if "youtube.com" in url or "youtu.be" in url:
            ydl_opts = {"format": "bestvideo+bestaudio/best", "outtmpl": "youtube_%(id)s.%(ext)s", "merge_output_format": "mp4", "quiet": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                file = ydl.prepare_filename(ydl.extract_info(url, download=True))
            send_video_with_music(chat_id, file, "youtube")
            return

        bot.send_message(chat_id, "❌ Unsupported link")
    except Exception:
        bot.send_message(chat_id, "❌ Incorrect link.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("msguser|"))
def message_user(call):
    if not is_admin(call.from_user.id): return
    uid = call.data.split("|")[1]
    msg = bot.send_message(call.message.chat.id, "Send message for user")
    bot.register_next_step_handler(msg, send_user_message, uid)

def send_user_message(m, uid):
    if not is_admin(m.from_user.id): return
    try:
        bot.send_message(int(uid), m.text)
        bot.send_message(m.chat.id, "✅ Message sent")
    except:
        bot.send_message(m.chat.id, "❌ Failed to send message")

@bot.callback_query_handler(func=lambda call: call.data.startswith("music_"))
def convert_music(call):
    vid_id = call.data.split("_")[1]
    if vid_id not in video_files:
        bot.answer_callback_query(call.id, "File expired")
        return
    file_path = video_files[vid_id]
    audio_path = file_path.rsplit(".",1)[0] + ".mp3"
    try:
        subprocess.run(["ffmpeg", "-y", "-i", file_path, "-vn", "-acodec", "mp3", "-ab", "128k", "-ar", "44100", audio_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("📢 BOT CHANNEL", url="https://t.me/tiktokvediodownload"))
        with open(audio_path, "rb") as audio:
            bot.send_audio(call.message.chat.id, audio, title="Converted Music", performer="DownloadBot", caption=CAPTION_TEXT, reply_markup=kb)
        if os.path.exists(audio_path): os.remove(audio_path)
        if os.path.exists(file_path): os.remove(file_path)
        bot.answer_callback_query(call.id, "🎵 Music converted")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Music conversion failed:\n{e}")

@bot2.message_handler(commands=['start'])
def verify_start(m):
    args = m.text.split()
    if len(args) > 1:
        bot2.send_message(m.chat.id, f"🔑 Your verification code:\n\n{args[1]}\n\nCopy this code and send it to the downloader bot.")

def run_bot1():
    while True:
        try: bot.infinity_polling(skip_pending=True)
        except Exception as e: print("Bot1 restart:", e)

def run_bot2():
    while True:
        try: bot2.infinity_polling(skip_pending=True)
        except Exception as e: print("Bot2 restart:", e)

def run_support_bot():
    while True:
        try: subprocess.call(["python", "support_bot.py"])
        except Exception as e:
            print("Support Bot restart:", e)
            time.sleep(5)

if __name__ == "__main__":
    tg_client.start()
    t1 = threading.Thread(target=run_bot1)
    t2 = threading.Thread(target=run_bot2)
    t3 = threading.Thread(target=run_support_bot)
    t1.start(); t2.start(); t3.start()
    t1.join(); t2.join(); t3.join()
