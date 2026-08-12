import telebot
import requests
from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery
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

# New Premium System Database Files
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

# ================= JSON FUNCTIONS =================
def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

users = load_json(USERS_FILE, {})
withdraws = load_json(WITHDRAWS_FILE, [])

def save_users():
    save_json(USERS_FILE, users)

def save_withdraws():
    save_json(WITHDRAWS_FILE, withdraws)

# Load Premium System Data
premium_data = load_json(PREMIUM_FILE, {})
payments_data = load_json(PAYMENTS_FILE, [])
referrals_data = load_json(REFERRALS_FILE, {}) # ref -> list of referred uids
referral_rewards_data = load_json(REFERRAL_REWARDS_FILE, {})
referral_milestones_data = load_json(REFERRAL_MILESTONES_FILE, {
    "3": {"reward_days": 3},
    "5": {"reward_days": 7},
    "10": {"reward_days": 15},
    "25": {"reward_days": 30},
    "50": {"reward_days": 90}
})
feature_requests_data = load_json(FEATURE_REQUESTS_FILE, {})
feature_votes_data = load_json(FEATURE_VOTES_FILE, {})
leaderboard_data = load_json(LEADERBOARD_FILE, {})
missions_data = load_json(MISSIONS_FILE, {
    "m1": {"title": "📥 Download 10 Files", "target": 10, "reward_days": 1, "type": "daily"},
    "m2": {"title": "🎁 Invite 3 Friends", "target": 3, "reward_days": 2, "type": "weekly"},
    "m3": {"title": "💡 Vote on 3 Features", "target": 3, "reward_days": 1, "type": "daily"}
})
mission_progress_data = load_json(MISSION_PROGRESS_FILE, {})
coupons_data = load_json(COUPONS_FILE, {
    "VIP2026": {"discount_days": 30, "max_uses": 100, "uses": 0, "active": True},
    "WELCOME": {"discount_days": 7, "max_uses": 500, "uses": 0, "active": True}
})
coupon_usage_data = load_json(COUPON_USAGE_FILE, {})
gift_premium_data = load_json(GIFT_PREMIUM_FILE, [])
vip_identity_data = load_json(VIP_IDENTITY_FILE, {})

def save_premium_data():
    save_json(PREMIUM_FILE, premium_data)
def save_payments_data():
    save_json(PAYMENTS_FILE, payments_data)
def save_referrals_data():
    save_json(REFERRALS_FILE, referrals_data)
def save_referral_rewards_data():
    save_json(REFERRAL_REWARDS_FILE, referral_rewards_data)
def save_referral_milestones_data():
    save_json(REFERRAL_MILESTONES_FILE, referral_milestones_data)
def save_feature_requests_data():
    save_json(FEATURE_REQUESTS_FILE, feature_requests_data)
def save_feature_votes_data():
    save_json(FEATURE_VOTES_FILE, feature_votes_data)
def save_leaderboard_data():
    save_json(LEADERBOARD_FILE, leaderboard_data)
def save_missions_data():
    save_json(MISSIONS_FILE, missions_data)
def save_mission_progress_data():
    save_json(MISSION_PROGRESS_FILE, mission_progress_data)
def save_coupons_data():
    save_json(COUPONS_FILE, coupons_data)
def save_coupon_usage_data():
    save_json(COUPON_USAGE_FILE, coupon_usage_data)
def save_gift_premium_data():
    save_json(GIFT_PREMIUM_FILE, gift_premium_data)
def save_vip_identity_data():
    save_json(VIP_IDENTITY_FILE, vip_identity_data)

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

# ================= PREMIUM CHECK & CORE HELPERS =================
PLAN_PRICES = {
    "7": {"days": 7, "stars": 50, "name": "7 Days"},
    "30": {"days": 30, "stars": 150, "name": "30 Days"},
    "90": {"days": 90, "stars": 350, "name": "90 Days"},
    "365": {"days": 365, "stars": 1000, "name": "1 Year"}
}

def is_premium(uid):
    uid_str = str(uid)
    if uid_str not in premium_data:
        return False
    p = premium_data[uid_str]
    if p.get("status") != "ACTIVE":
        return False
    expiry = datetime.strptime(p.get("expiry_date"), "%Y-%m-%d %H:%M:%S")
    if datetime.now() > expiry:
        p["status"] = "INACTIVE"
        save_premium_data()
        try:
            bot.send_message(
                int(uid),
                "⏰ Your Premium has expired.\n\n⭐ Renew Premium to continue using VIP features.",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("⭐ Renew Premium", callback_data="prem_buy"),
                    InlineKeyboardButton("🏠 Home", callback_data="home_menu")
                )
            )
        except:
            pass
        return False
    return True

def activate_premium(uid, days):
    uid_str = str(uid)
    now = datetime.now()
    if uid_str in premium_data and premium_data[uid_str].get("status") == "ACTIVE":
        current_expiry = datetime.strptime(premium_data[uid_str]["expiry_date"], "%Y-%m-%d %H:%M:%S")
        if current_expiry > now:
            new_expiry = current_expiry + timedelta(days=days)
        else:
            new_expiry = now + timedelta(days=days)
    else:
        new_expiry = now + timedelta(days=days)
    
    plan_name = f"{days} Days"
    for k, v in PLAN_PRICES.items():
        if v["days"] == days:
            plan_name = v["name"]

    premium_data[uid_str] = {
        "status": "ACTIVE",
        "plan": plan_name,
        "duration": days,
        "start_date": now.strftime("%Y-%m-%d %H:%M:%S"),
        "expiry_date": new_expiry.strftime("%Y-%m-%d %H:%M:%S")
    }
    save_premium_data()

    # Initialize VIP Identity if not exists
    if uid_str not in vip_identity_data:
        vip_identity_data[uid_str] = {
            "title": "VIP",
            "level": 1,
            "points": 10
        }
        save_vip_identity_data()

# ================= MENUS =================
def user_menu(show_admin=False):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💰 BALANCE", "💸 WITHDRAWAL")
    kb.add("👥 REFERRAL", "👑 PREMIUM")
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
    kb.add("👑 PREMIUM MGMT", "📊 PREM STATS")
    kb.add("🔙 BACK MAIN MENU")
    return kb

# ================= BACK TO MAIN MENU =================
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
        if ref and ref != users[str(uid)]["ref"]:
            ref_user = next((u for u, d in users.items() if d["ref"] == ref), None)
            if ref_user and ref_user != str(uid):
                if ref_user not in referrals_data:
                    referrals_data[ref_user] = []
                if str(uid) not in referrals_data[ref_user]:
                    referrals_data[ref_user].append(str(uid))
                    users[ref_user]["invited"] += 1
                    users[ref_user]["balance"] += 0.2
                    save_referrals_data()
                    save_users()
                    try:
                        bot.send_message(int(ref_user), "🎉 You earned $0.2 from referral!")
                    except:
                        pass

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
        "• Withdrawal system\n"
        "• Premium VIP Center"
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

# ================= VERIFY BOT START =================
@bot2.message_handler(commands=['start'])
def verify_start(message):
    args = message.text.split()
    if len(args) > 1:
        code = args[1]
        bot2.send_message(
            message.chat.id,
            f"🔑 <b>Your Verification Code</b>\n\n<code>{code}</code>\n\nCopy this code and send it to the downloader bot."
        )
    else:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("GET", url="https://t.me/Downloadvedioytibot"))
        bot2.send_message(message.chat.id, "❌ <b>Don't Have Code?</b>\n\nGet code from downloader bot.", reply_markup=kb)

# ================= CHECK MEMBERSHIP =================
def check_membership(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["member", "administrator", "creator"]:
            bot.send_message(
                user_id,
                "🎬 Welcome to Video Downloader Bot!\n\nSend any video link to begin downloading.",
                reply_markup=user_menu(is_admin(user_id))
            )
        else:
            send_join_message(user_id)
    except:
        send_join_message(user_id)

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

def send_join_message(user_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ JOIN CHANNEL", url="https://t.me/tiktokvediodownload"))
    kb.add(InlineKeyboardButton("✅ CONFIRM", callback_data="confirm_join"))
    bot.send_message(user_id, "⚠️ You must join our channel to use this bot.", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "verify_dm")
def verify_dm(call):
    uid = call.from_user.id
    if uid not in verify_pending:
        return
    code = verify_pending[uid]["code"]
    loop = asyncio.get_event_loop()
    success = loop.run_until_complete(send_code_telegram(uid, code))
    if success:
        bot.answer_callback_query(call.id, "Code sent")
        bot.send_message(call.message.chat.id, "📩 Code sent to your Telegram DM.\n\nSend the code here.")
    else:
        bot.send_message(call.message.chat.id, "❌ Cannot send DM.")

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
    email = message.text
    code = str(random.randint(10000,99999))
    verify_pending[uid] = {"code": code}
    success = send_gmail_code(email, code)
    if success:
        bot.send_message(message.chat.id, "📩 Code sent to your Gmail.\nSend the code here.")
    else:
        bot.send_message(message.chat.id, "❌ Failed to send email.")

def send_multi_join(user_id):
    kb = InlineKeyboardMarkup(row_width=3)
    buttons = [InlineKeyboardButton("➕️ JOIN", url=f"https://t.me/{ch}") for ch in POST_CHANNELS]
    kb.add(*buttons)
    kb.add(InlineKeyboardButton("✅ CONFIRM", callback_data="multi_checkjoin"))
    bot.send_message(user_id, "⚠️ Join all channels to continue.", reply_markup=kb)

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
        bot.answer_callback_query(call.id, "Verification expired")
        return
    code = verify_pending[uid]["code"]
    loop = asyncio.get_event_loop()
    success = loop.run_until_complete(send_code_telegram(uid, code))
    if success:
        bot.send_message(call.message.chat.id, "✅ Code sent to your Telegram messages.\nSend the code here.")
    else:
        bot.send_message(call.message.chat.id, "⚠️ Telegram blocked sending message.")

@bot.callback_query_handler(func=lambda call: call.data == "verify_email")
def verify_email(call):
    msg = bot.send_message(call.message.chat.id, "📧 Send your Gmail address to receive verification code.")
    bot.register_next_step_handler(msg, process_email)

@bot.callback_query_handler(func=lambda call: call.data == "confirm_join")
def confirm_join(call):
    user_id = call.from_user.id
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["member","administrator","creator"]:
            bot.answer_callback_query(call.id,"✅ Join verified")
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(user_id, "✅ Join confirmed!\nNow you can use the bot.\nSend your video link.")
        else:
            bot.answer_callback_query(call.id, "❌ You must join the channel first!", show_alert=True)
    except:
        bot.answer_callback_query(call.id, "❌ Please join the channel first!", show_alert=True)


# ================= ⭐ 1. PREMIUM CORE & PREMIUM CENTER =================
@bot.message_handler(func=lambda m: m.text == "👑 PREMIUM")
def premium_center_handler(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    uid = str(m.from_user.id)
    active = is_premium(uid)
    
    if active:
        p = premium_data[uid]
        status = "ACTIVE"
        plan = p.get("plan", "30 Days")
        expiry = p.get("expiry_date", "N/A")
        try:
            exp_dt = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
            days_left = (exp_dt - datetime.now()).days
        except:
            days_left = 0
    else:
        status = "INACTIVE"
        plan = "None"
        expiry = "N/A"
        days_left = 0

    text = (
        f"╭━━━ 👑 PREMIUM CENTER ━━━╮\n\n"
        f"⭐ Status: {status}\n"
        f"💎 Plan: {plan}\n"
        f"📅 Expires: {expiry}\n"
        f"⏳ Days Left: {days_left}\n\n"
        f"✨ Unlock the full Premium experience!\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━╯"
    )

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⭐ Buy Premium", callback_data="prem_buy"),
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
        InlineKeyboardButton("👑 My VIP Identity", callback_data="prem_vip_identity")
    )
    kb.add(
        InlineKeyboardButton("🔙 Back", callback_data="home_menu")
    )
    bot.send_message(m.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "home_menu")
def home_menu_callback(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "🏠 Home Menu", reply_markup=user_menu(is_admin(call.from_user.id)))

@bot.callback_query_handler(func=lambda call: call.data == "prem_buy")
def prem_buy_callback(call):
    kb = InlineKeyboardMarkup(row_width=2)
    for k, v in PLAN_PRICES.items():
        kb.add(InlineKeyboardButton(f"⭐ {v['name']} - {v['stars']} Stars", callback_data=f"buyplan_{k}"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="prem_center_back"))
    bot.edit_message_text(
        "⭐ <b>Choose Premium Plan</b>\n\nSelect a plan to unlock all VIP downloader features using Telegram Stars:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=kb,
        parse_mode="HTML"
    )

@bot.callback_query_handler(func=lambda call: call.data == "prem_center_back")
def prem_center_back(call):
    # Re-trigger premium center view
    call.text = "👑 PREMIUM"
    premium_center_handler(call.message)
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("buyplan_"))
def buy_plan_stars(call):
    plan_key = call.data.split("_")[1]
    if plan_key not in PLAN_PRICES:
        return
    plan = PLAN_PRICES[plan_key]
    title = f"Premium VIP - {plan['name']}"
    description = f"Unlock VIP downloader features for {plan['name']}."
    currency = "XTR" # Telegram Stars
    prices = [LabeledPrice(label=plan['name'], amount=plan['stars'])]

    bot.send_invoice(
        chat_id=call.message.chat.id,
        title=title,
        description=description,
        invoice_payload=f"premium_{plan_key}_{call.from_user.id}",
        provider_token="",
        currency=currency,
        prices=prices
    )

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout_handler(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def successful_payment_handler(message):
    payment = message.successful_payment
    payload = payment.invoice_payload
    if payload.startswith("premium_"):
        parts = payload.split("_")
        plan_key = parts[1]
        uid = parts[2]
        days = PLAN_PRICES[plan_key]["days"]
        stars = PLAN_PRICES[plan_key]["stars"]

        # Prevent duplicate payment / atomic activation
        pay_id = payment.telegram_payment_charge_id
        if any(p.get("payment_id") == pay_id for p in payments_data):
            return

        payments_data.append({
            "user_id": uid,
            "plan": PLAN_PRICES[plan_key]["name"],
            "duration": days,
            "stars_amount": stars,
            "payment_id": pay_id,
            "start_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "SUCCESS",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        save_payments_data()
        activate_premium(uid, days)

        bot.send_message(
            int(uid),
            f"✅ <b>Payment Confirmed!</b>\n\n👑 Premium activated for {PLAN_PRICES[plan_key]['name']}.\nEnjoy your VIP features!",
            parse_mode="HTML"
        )

    elif payload.startswith("gift_"):
        parts = payload.split("_")
        plan_key = parts[1]
        recipient_id = parts[2]
        sender_id = parts[3]
        days = PLAN_PRICES[plan_key]["days"]
        stars = PLAN_PRICES[plan_key]["stars"]
        pay_id = payment.telegram_payment_charge_id

        gift_premium_data.append({
            "sender_id": sender_id,
            "recipient_id": recipient_id,
            "plan": PLAN_PRICES[plan_key]["name"],
            "stars_amount": stars,
            "payment_id": pay_id,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "SUCCESS"
        })
        save_gift_premium_data()
        activate_premium(recipient_id, days)

        bot.send_message(
            int(sender_id),
            f"✅ Gift successfully sent to user <code>{recipient_id}</code>!",
            parse_mode="HTML"
        )
        try:
            bot.send_message(
                int(recipient_id),
                f"╭━━━ 🎁 PREMIUM GIFT ━━━╮\n\n🎉 You received Premium!\n\n💎 Plan: {PLAN_PRICES[plan_key]['name']}\n📅 Expires: {premium_data[recipient_id]['expiry_date']}\n\nEnjoy your Premium experience! 👑\n╰━━━━━━━━━━━━━━━━━━━━━━╯"
            )
        except:
            pass

@bot.callback_query_handler(func=lambda call: call.data == "prem_my_plan")
def prem_my_plan(call):
    uid = str(call.from_user.id)
    if is_premium(uid):
        p = premium_data[uid]
        text = f"💎 <b>Your Active Plan</b>\n\nPlan: {p['name']}\nStarts: {p['start_date']}\nExpires: {p['expiry_date']}"
    else:
        text = "❌ You do not have an active Premium plan."
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="prem_center_back"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "prem_settings")
def prem_settings(call):
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="prem_center_back"))
    bot.edit_message_text("⚙️ <b>Premium Settings</b>\n\nYour VIP status is automatically managed.", call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "prem_my_stats")
def prem_my_stats(call):
    uid = str(call.from_user.id)
    downloads = videos_data.get("users", {}).get(uid, 0)
    refs = len(referrals_data.get(uid, []))
    vip = vip_identity_data.get(uid, {"level": 1, "points": 10})
    text = (
        f"📊 <b>My Statistics</b>\n\n"
        f"📥 Total Downloads: {downloads}\n"
        f"👥 Referrals: {refs}\n"
        f"🔥 VIP Level: {vip['level']}\n"
        f"🏆 Points: {vip['points']}"
    )
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="prem_center_back"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")


# ================= 🎁 2. REFERRAL & REWARDS =================
@bot.callback_query_handler(func=lambda call: call.data == "prem_invite")
def prem_invite_menu(call):
    uid = str(call.from_user.id)
    ref_count = len(referrals_data.get(uid, []))
    bot_username = bot.get_me().username
    ref_code = users[uid]['ref']
    link = f"https://t.me/{bot_username}?start={ref_code}"

    text = (
        f"╭━━━ 🎁 INVITE & EARN ━━━╮\n\n"
        f"👥 Referrals: {ref_count}\n"
        f"🎁 Rewards: ⭐ 7 Days (Milestone)\n"
        f"🏆 Rank: #{random.randint(1, 50)}\n\n"
        f"Invite your friends and earn rewards!\n"
        f"Link: <code>{link}</code>\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━╯"
    )
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={link}&text=Join%20this%20awesome%20Telegram%20Downloader%20Bot!"),
        InlineKeyboardButton("👥 My Referrals", callback_data="prem_my_refs")
    )
    kb.add(
        InlineKeyboardButton("🎁 My Rewards", callback_data="prem_my_rewards"),
        InlineKeyboardButton("🏆 My Rank", callback_data="prem_my_rank")
    )
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="prem_center_back"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "prem_my_refs")
def prem_my_refs(call):
    uid = str(call.from_user.id)
    refs = referrals_data.get(uid, [])
    text = f"👥 <b>Your Referrals ({len(refs)})</b>\n\n"
    for r in refs[:10]:
        text += f"• User ID: <code>{r}</code>\n"
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="prem_invite"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "prem_my_rewards")
def prem_my_rewards(call):
    uid = str(call.from_user.id)
    rewards = referral_rewards_data.get(uid, [])
    text = f"🎁 <b>Your Claimed Rewards</b>\n\n"
    if rewards:
        for r in rewards:
            text += f"• Milestone {r['milestone']} Referrals -> {r['reward']}\n"
    else:
        text += "No rewards claimed yet. Invite friends to reach milestones!"
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="prem_invite"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "prem_my_rank")
def prem_my_rank(call):
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="prem_invite"))
    bot.edit_message_text("🏆 Your Referral Rank is #8 among all users!", call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")


# ================= 💡 3. FEATURE REQUESTS =================
@bot.callback_query_handler(func=lambda call: call.data == "prem_features")
def prem_features_menu(call):
    uid = str(call.from_user.id)
    if not is_premium(uid):
        bot.answer_callback_query(call.id, "❌ Feature Requests is a Premium VIP only feature!", show_alert=True)
        return

    text = (
        f"╭━━━ 💡 FEATURE REQUESTS ━━━╮\n\n"
        f"🔥 MOST REQUESTED\n\n"
    )
    sorted_reqs = sorted(feature_requests_data.values(), key=lambda x: x['votes'], reverse=True)
    for i, req in enumerate(sorted_reqs[:3], start=1):
        text += f"{i}️⃣ {req['title']}\n👍 {req['votes']} Votes [{req['status']}]\n\n"
    text += f"╰━━━━━━━━━━━━━━━━━━━━━━╯"

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💡 Submit Feature", callback_data="feature_submit"),
        InlineKeyboardButton("📋 My Requests", callback_data="feature_my")
    )
    kb.add(
        InlineKeyboardButton("🔥 Most Requested", callback_data="feature_most"),
        InlineKeyboardButton("🔙 Back", callback_data="prem_center_back")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "feature_submit")
def feature_submit_prompt(call):
    msg = bot.send_message(call.message.chat.id, "💡 Send the title of your feature request:")
    bot.register_next_step_handler(msg, feature_title_step)

def feature_title_step(m):
    title = m.text.strip()
    msg = bot.send_message(m.chat.id, "📝 Now send the description of your feature request:")
    bot.register_next_step_handler(msg, feature_desc_step, title)

def feature_desc_step(m, title):
    desc = m.text.strip()
    req_id = str(random.randint(10000, 99999))
    feature_requests_data[req_id] = {
        "request_id": req_id,
        "user_id": str(m.from_user.id),
        "title": title,
        "description": desc,
        "votes": 1,
        "status": "🟡 Pending",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    feature_votes_data[req_id] = [str(m.from_user.id)]
    save_feature_requests_data()
    save_feature_votes_data()
    bot.send_message(m.chat.id, f"✅ Feature request submitted successfully!\nID: {req_id}", reply_markup=user_menu(is_admin(m.from_user.id)))

@bot.callback_query_handler(func=lambda call: call.data == "feature_my")
def feature_my_list(call):
    uid = str(call.from_user.id)
    my_reqs = [r for r in feature_requests_data.values() if r['user_id'] == uid]
    text = "📋 <b>Your Feature Requests</b>\n\n"
    for r in my_reqs:
        text += f"• <b>{r['title']}</b> - {r['status']}\n👍 {r['votes']} Votes\n\n"
    if not my_reqs:
        text += "You haven't submitted any feature requests yet."
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="prem_features"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "feature_most")
def feature_most_list(call):
    text = "🔥 <b>Most Requested Features</b>\n\n"
    sorted_reqs = sorted(feature_requests_data.values(), key=lambda x: x['votes'], reverse=True)
    kb = InlineKeyboardMarkup(row_width=2)
    for r in sorted_reqs[:5]:
        text += f"• <b>{r['title']}</b> ({r['votes']} votes) [{r['status']}]\n"
        kb.add(InlineKeyboardButton(f"👍 Vote: {r['title'][:15]}", callback_data=f"vote_{r['request_id']}"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="prem_features"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("vote_"))
def vote_feature(call):
    req_id = call.data.split("_")[1]
    uid = str(call.from_user.id)
    if req_id not in feature_votes_data:
        feature_votes_data[req_id] = []
    if uid in feature_votes_data[req_id]:
        bot.answer_callback_query(call.id, "You already voted for this feature!", show_alert=True)
        return
    feature_votes_data[req_id].append(uid)
    feature_requests_data[req_id]["votes"] += 1
    save_feature_votes_data()
    save_feature_requests_data()
    bot.answer_callback_query(call.id, "✅ Vote recorded successfully!")


# ================= 🏆 4. PREMIUM LEADERBOARD =================
@bot.callback_query_handler(func=lambda call: call.data == "prem_leaderboard")
def prem_leaderboard(call):
    uid = str(call.from_user.id)
    text = (
        f"╭━━━ 🏆 PREMIUM LEADERBOARD ━━━╮\n\n"
        f"🥇 @User1 — 87 Points\n"
        f"🥈 @User2 — 64 Points\n"
        f"🥉 @User3 — 51 Points\n\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"⭐ YOUR POSITION\n"
        f"Rank: #17\n"
        f"Points: 23\n\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━╯"
    )
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📊 My Rank", callback_data="prem_my_rank"),
        InlineKeyboardButton("🎁 My Rewards", callback_data="prem_my_rewards")
    )
    kb.add(
        InlineKeyboardButton("📅 Weekly", callback_data="lb_weekly"),
        InlineKeyboardButton("📆 Monthly", callback_data="lb_monthly")
    )
    kb.add(
        InlineKeyboardButton("🏆 All Time", callback_data="lb_alltime"),
        InlineKeyboardButton("🔙 Back", callback_data="prem_center_back")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data in ["lb_weekly", "lb_monthly", "lb_alltime"])
def leaderboard_filter(call):
    bot.answer_callback_query(call.id, f"Showing {call.data.split('_')[1].capitalize()} Leaderboard")


# ================= 🎯 5. PREMIUM MISSIONS =================
@bot.callback_query_handler(func=lambda call: call.data == "prem_missions")
def prem_missions_menu(call):
    text = (
        f"╭━━━ 🎯 PREMIUM MISSIONS ━━━╮\n\n"
        f"🔥 ACTIVE MISSIONS\n\n"
        f"📥 Download 10 Files\nProgress: 7/10\n🎁 Reward: ⭐ 1 Day\n\n"
        f"🎁 Invite 3 Friends\nProgress: 2/3\n🎁 Reward: ⭐ 2 Days\n\n"
        f"💡 Vote on 3 Features\nProgress: 3/3 ✅\n🎁 Reward: Completed\n\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━╯"
    )
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🎯 Active Missions", callback_data="prem_missions"),
        InlineKeyboardButton("🎁 Completed", callback_data="missions_completed")
    )
    kb.add(
        InlineKeyboardButton("🏆 Rewards", callback_data="prem_my_rewards"),
        InlineKeyboardButton("🔙 Back", callback_data="prem_center_back")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "missions_completed")
def missions_completed(call):
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="prem_missions"))
    bot.edit_message_text("🎁 Completed Missions:\n\n• Vote on 3 Features (Completed ✅)", call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")


# ================= 🎟️ 6. PREMIUM COUPONS =================
@bot.callback_query_handler(func=lambda call: call.data == "prem_coupons")
def prem_coupons_menu(call):
    text = (
        f"╭━━━ 🎟️ PREMIUM COUPON ━━━╮\n\n"
        f"Enter your coupon code below.\n\n"
        f"Example:\nVIP2026\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━╯"
    )
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🎟️ Redeem Coupon", callback_data="coupon_redeem_prompt"), InlineKeyboardButton("🔙 Back", callback_data="prem_center_back"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "coupon_redeem_prompt")
def coupon_redeem_prompt(call):
    msg = bot.send_message(call.message.chat.id, "🎟️ Please send your coupon code:")
    bot.register_next_step_handler(msg, coupon_redeem_process)

def coupon_redeem_process(m):
    uid = str(m.from_user.id)
    code = m.text.strip().upper()
    if code not in coupons_data:
        bot.send_message(m.chat.id, "❌ Invalid coupon code.")
        return
    coupon = coupons_data[code]
    if not coupon.get("active", True):
        bot.send_message(m.chat.id, "❌ This coupon is disabled.")
        return
    if coupon["uses"] >= coupon["max_uses"]:
        bot.send_message(m.chat.id, "❌ Coupon usage limit reached.")
        return
    if uid in coupon_usage_data.get(code, []):
        bot.send_message(m.chat.id, "❌ You have already used this coupon.")
        return

    if code not in coupon_usage_data:
        coupon_usage_data[code] = []
    coupon_usage_data[code].append(uid)
    coupon["uses"] += 1
    save_coupons_data()
    save_coupon_usage_data()

    activate_premium(uid, coupon["discount_days"])
    bot.send_message(m.chat.id, f"✅ Coupon applied successfully!\n🎁 {coupon['discount_days']} Days Premium added.")


# ================= 🎁 7. GIFT PREMIUM =================
@bot.callback_query_handler(func=lambda call: call.data == "prem_gift")
def prem_gift_menu(call):
    msg = bot.send_message(call.message.chat.id, "🎁 Send the recipient's Telegram ID or Username (e.g. @username):")
    bot.register_next_step_handler(msg, gift_recipient_step)

def gift_recipient_step(m):
    recipient_input = m.text.strip().replace("@", "")
    recipient_id = None
    for u, d in users.items():
        if d.get("username", "").lower() == recipient_input.lower() or u == recipient_input:
            recipient_id = u
            break
    if not recipient_id:
        recipient_id = recipient_input # fallback if telegram id directly given
    
    kb = InlineKeyboardMarkup(row_width=2)
    for k, v in PLAN_PRICES.items():
        kb.add(InlineKeyboardButton(f"⭐ {v['name']} - {v['stars']} Stars", callback_data=f"giftplan_{k}_{recipient_id}"))
    bot.send_message(m.chat.id, f"🎁 Choose plan to gift to <code>{recipient_input}</code>:", reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("giftplan_"))
def gift_plan_stars(call):
    parts = call.data.split("_")
    plan_key = parts[1]
    recipient_id = parts[2]
    sender_id = str(call.from_user.id)
    if recipient_id == sender_id:
        bot.answer_callback_query(call.id, "You cannot gift premium to yourself!", show_alert=True)
        return

    plan = PLAN_PRICES[plan_key]
    title = f"Gift Premium - {plan['name']}"
    description = f"Gift VIP Premium ({plan['name']}) to user {recipient_id}."
    currency = "XTR"
    prices = [LabeledPrice(label=plan['name'], amount=plan['stars'])]

    bot.send_invoice(
        chat_id=call.message.chat.id,
        title=title,
        description=description,
        invoice_payload=f"gift_{plan_key}_{recipient_id}_{sender_id}",
        provider_token="",
        currency=currency,
        prices=prices
    )


# ================= 👑 8. VIP IDENTITY =================
@bot.callback_query_handler(func=lambda call: call.data == "prem_vip_identity")
def prem_vip_identity(call):
    uid = str(call.from_user.id)
    vip = vip_identity_data.get(uid, {"title": "VIP", "level": 1, "points": 10})
    prem = premium_data.get(uid, {"start_date": "N/A"})
    text = (
        f"╭━━━ 👑 VIP IDENTITY ━━━╮\n\n"
        f"👤 User: @{call.from_user.username or 'User'}\n\n"
        f"⭐ Current Title:\n💎 {vip['title']}\n\n"
        f"📅 Premium Since:\n{prem.get('start_date', 'N/A')}\n\n"
        f"🔥 VIP Level:\nLevel {vip['level']}\n\n"
        f"🏆 Points:\n{vip['points']}\n\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━╯"
    )
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⭐ VIP", callback_data="viptitle_VIP"),
        InlineKeyboardButton("💎 PRO", callback_data="viptitle_PRO")
    )
    kb.add(
        InlineKeyboardButton("🔥 LEGEND", callback_data="viptitle_LEGEND"),
        InlineKeyboardButton("👑 ELITE", callback_data="viptitle_ELITE")
    )
    kb.add(InlineKeyboardButton("🎨 Customize", callback_data="vip_customize"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="prem_center_back"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("viptitle_"))
def change_vip_title(call):
    uid = str(call.from_user.id)
    title = call.data.split("_")[1]
    if uid not in vip_identity_data:
        vip_identity_data[uid] = {"title": title, "level": 1, "points": 10}
    else:
        vip_identity_data[uid]["title"] = title
    save_vip_identity_data()
    bot.answer_callback_query(call.id, f"✅ VIP Title updated to {title}!")


# ================= 👨‍💼 ADMIN PANEL EXTENSIONS =================
@bot.message_handler(func=lambda m: m.text == "👑 PREMIUM MGMT")
def admin_premium_mgmt(m):
    if not is_admin(m.from_user.id):
        return
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("👑 Give Premium", callback_data="adm_give_prem"),
        InlineKeyboardButton("❌ Remove Premium", callback_data="adm_rem_prem")
    )
    kb.add(
        InlineKeyboardButton("🎟️ Coupons", callback_data="adm_coupons"),
        InlineKeyboardButton("🔙 Back", callback_data="home_menu")
    )
    bot.send_message(m.chat.id, "👑 <b>Premium Management</b>", reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "adm_give_prem")
def adm_give_prem_prompt(call):
    if not is_admin(call.from_user.id):
        return
    msg = bot.send_message(call.message.chat.id, "Send User Telegram ID and Days separated by space (e.g. 123456789 30):")
    bot.register_next_step_handler(msg, adm_give_prem_process)

def adm_give_prem_process(m):
    if not is_admin(m.from_user.id):
        return
    try:
        uid_str, days_str = m.text.strip().split()
        days = int(days_str)
        activate_premium(uid_str, days)
        bot.send_message(m.chat.id, f"✅ Premium activated for user {uid_str} for {days} days.")
    except:
        bot.send_message(m.chat.id, "❌ Format error. Use: <Telegram ID> <days>")

@bot.message_handler(func=lambda m: m.text == "📊 PREM STATS")
def admin_prem_stats(m):
    if not is_admin(m.from_user.id):
        return
    active_prem = len([u for u in premium_data if is_premium(u)])
    total_stars = sum(p.get("stars_amount", 0) for p in payments_data)
    total_refs = sum(len(refs) for refs in referrals_data.values())
    total_feats = len(feature_requests_data)
    total_gifts = len(gift_premium_data)

    text = (
        f"👑 <b>PREMIUM STATISTICS</b>\n\n"
        f"👥 Total Users: {len(users)}\n"
        f"⭐ Active Premium: {active_prem}\n"
        f"💳 Total Stars: {total_stars}\n"
        f"🎁 Total Referrals: {total_refs}\n"
        f"💡 Feature Requests: {total_feats}\n"
        f"🎁 Gifts Sent: {total_gifts}"
    )
    bot.send_message(m.chat.id, text, parse_mode="HTML")


# ================= ADMIN PANEL =================
@bot.message_handler(func=lambda m: m.text == "👑 ADMIN PANEL")
def open_admin_panel(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ You are not admin")
        return
    bot.send_message(m.chat.id, "👑 Admin Panel", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == "💰 BALANCE")
def balance_handler(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    uid = str(m.from_user.id)
    bal = users.get(uid, {}).get("balance", 0.0)
    blocked = users.get(uid, {}).get("blocked", 0.0)
    bot.send_message(
        m.chat.id,
        f"💰 Available Balance: ${bal:.2f}\n"
        f"⏳ Blocked Amount: ${blocked:.2f}"
    )

@bot.message_handler(func=lambda m: m.text == "🆔 GET ID")
def get_id_handler(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    uid = str(m.from_user.id)
    bot.send_message(
        m.chat.id,
        f"🆔 BOT ID: <code>{users[uid]['bot_id']}</code>\n"
        f"👤 Telegram ID: <code>{uid}</code>"
    )

@bot.message_handler(func=lambda m: m.text == "👥 REFERRAL")
def referral_handler(m):
    if bot_locked_guard(m) or banned_guard(m):
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

@bot.message_handler(func=lambda m: m.text == "☎️ CUSTOMER")
def customer_handler(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    bot.send_message(m.chat.id, "☎️ Customer Support:\n@scholes1")

@bot.message_handler(func=lambda m: m.text == "🤖CUSTOMER AI")
def customer_ai_handler(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    bot.send_message(m.chat.id, "Ai Customer Support🤖:\n@Aidownoaderbot")

@bot.message_handler(func=lambda m: m.text == "💸 WITHDRAWAL")
def withdraw_menu(m):
    if banned_guard(m):
        return
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

    bot.send_message(
        int(uid),
        f"✅ Withdrawal Request Sent\n🧾 Request ID: {wid}\n💵 Amount: ${amt:.2f}\n⏳ Status: Pending"
    )

    admin_text = (
        f"💳 NEW WITHDRAWAL\n\n👤 User: {uid}\n💵 Amount: ${amt:.2f}\n🧾 Request ID: {wid}\n⏳ Status: Pending"
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
        bot.send_message(int(uid), f"🚫 Withdrawal blocked. Code: {code}")

@bot.message_handler(func=lambda m: m.text == "💰 UNBLOCK MONEY")
def unblock_money_start(m):
    if not is_admin(m.from_user.id):
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
    bot.send_message(int(uid), f"✅ Blocked ${amt:.2f} is now available!")
    bot.send_message(m.chat.id, f"✅ Money unblocked for user {uid}")

@bot.message_handler(func=lambda m: m.text == "🔥 UN BAN-USER")
def unban_user_start(m):
    if not is_admin(m.from_user.id):
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
    bot.send_message(int(uid), "✅ You have been unbanned.")

@bot.message_handler(func=lambda m: m.text == "💳 WITHDRAWAL CHECK")
def withdrawal_check_start(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "Enter Withdrawal Request ID:")
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
    bot.send_message(m.chat.id, f"💳 WITHDRAWAL\nID: {w['id']}\nAmount: ${w['amount']:.2f}\nStatus: {w['status'].upper()}")

@bot.message_handler(func=lambda m: m.text == "📊 STATS")
def stats_handler(m):
    if not is_admin(m.from_user.id):
        return
    bot.send_message(m.chat.id, f"📊 STATS\nUsers: {len(users)}\nWithdrawals: {len(withdraws)}")

@bot.message_handler(func=lambda m: m.text == "🚫 BAN USER MANUAL")
def manual_ban_start(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "Send Telegram ID to BAN:")
    bot.register_next_step_handler(msg, manual_ban_process)

def manual_ban_process(m):
    if not is_admin(m.from_user.id):
        return
    uid = m.text.strip()
    if uid in users:
        users[uid]["banned"] = True
        save_users()
        bot.send_message(m.chat.id, f"🚫 User {uid} banned")

@bot.message_handler(func=lambda m: m.text == "📡 ADD CHANNEL")
def add_channel_start(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "Send channel username (e.g. @mychannel)")
    bot.register_next_step_handler(msg, add_channel_process)

def add_channel_process(m):
    username = m.text.strip()
    try:
        if username not in MANAGED_CHANNELS:
            MANAGED_CHANNELS.append(username)
        bot.send_message(m.chat.id, f"✅ Channel Added: {username}")
    except:
        bot.send_message(m.chat.id, "❌ Invalid channel")

@bot.message_handler(func=lambda m: m.text == "🔍 RAADI")
def raadi_stats(m):
    if not is_admin(m.from_user.id):
        return
    bot.send_message(m.chat.id, f"🔍 Total downloads: {videos_data.get('total', 0)}")

@bot.message_handler(func=lambda m: m.text == "📢 BROADCAST")
def broadcast_start(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "Send broadcast text:")
    bot.register_next_step_handler(msg, broadcast_send)

def broadcast_send(m):
    if not is_admin(m.from_user.id):
        return
    text = m.text
    for uid in users:
        try:
            bot.send_message(int(uid), text)
        except:
            pass
    bot.send_message(m.chat.id, "✅ Broadcast completed")

@bot.message_handler(func=lambda m: m.text == "🔒 LOCK BOT")
def lock_bot(m):
    global BOT_LOCKED
    if not is_admin(m.from_user.id):
        return
    BOT_LOCKED = True
    bot.send_message(m.chat.id, "🔒 Bot locked.")

@bot.message_handler(func=lambda m: m.text == "🔓 UNLOCK BOT")
def unlock_bot(m):
    global BOT_LOCKED
    if not is_admin(m.from_user.id):
        return
    BOT_LOCKED = False
    bot.send_message(m.chat.id, "🔓 Bot unlocked.")

@bot.message_handler(func=lambda m: m.text == "📢 ADD ADS")
def add_ads(m):
    if not is_admin(m.from_user.id):
        return
    bot.send_message(m.chat.id, "Send ads format: Button | URL | Text")

@bot.message_handler(func=lambda m: m.text == "🗑 DELETE ADS")
def delete_ads(m):
    global ADS_ENABLED
    if not is_admin(m.from_user.id):
        return
    ADS_ENABLED = False
    bot.send_message(m.chat.id, "🗑 Ads deleted.")

@bot.message_handler(func=lambda m: m.text == "✅ VERIFY ON")
def verify_on(m):
    global VERIFY_ENABLED
    if not is_admin(m.from_user.id):
        return
    VERIFY_ENABLED = True
    bot.send_message(m.chat.id, "✅ Verify ON")

@bot.message_handler(func=lambda m: m.text == "❌ VERIFY OFF")
def verify_off(m):
    global VERIFY_ENABLED
    if not is_admin(m.from_user.id):
        return
    VERIFY_ENABLED = False
    bot.send_message(m.chat.id, "❌ Verify OFF")

@bot.message_handler(func=lambda m: m.text == "➕ ADD BALANCE")
def add_balance(m):
    if not is_admin(m.from_user.id):
        return
    bot.send_message(m.chat.id, "Send UID and Amount")

@bot.message_handler(func=lambda m: m.text == "➖ REMOVE MONEY")
def remove_money(m):
    if not is_admin(m.from_user.id):
        return
    bot.send_message(m.chat.id, "Send UID and Amount")


# ================= URL EXTRACTOR & DOWNLOADER =================
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

    caption = "Downloaded by:\n@Downloadvedioytibot"
    if ADS_ENABLED and ADS_TEXT:
        caption += f"\n\n📢 {ADS_TEXT}"

    uid = str(chat_id)
    videos_data["total"] += 1
    videos_data["users"][uid] = videos_data["users"].get(uid, 0) + 1
    if platform:
        videos_data["platforms"][platform] = videos_data["platforms"].get(platform, 0) + 1
    save_videos()

    with open(file_path, "rb") as video:
        bot.send_video(chat_id, video, caption=caption, reply_markup=kb)

@bot.message_handler(func=lambda m: m.text and "http" in m.text)
def handle_links(message):
    if bot_locked_guard(message):
        return
    user_id = message.from_user.id
    link = message.text

    bot.send_message(message.chat.id, "⏳ Downloading...")
    download_media(message.chat.id, link)

def download_media(chat_id, text):
    try:
        url = extract_url(text)
        if not url:
            bot.send_message(chat_id, "❌ Invalid link")
            return

        if "tiktok.com" in url:
            api = f"https://tikwm.com/api/?url={url}"
            res = requests.get(api, timeout=30).json()
            if res.get("code") == 0:
                data = res["data"]
                if data.get("play"):
                    video_data = requests.get(data["play"], timeout=60).content
                    filename = "tiktok_video.mp4"
                    with open(filename, "wb") as f:
                        f.write(video_data)
                    send_video_with_music(chat_id, filename, "tiktok")
                    return

        ydl_opts = {
            "format": "best",
            "outtmpl": "media_%(id)s.%(ext)s",
            "quiet": True,
            "merge_output_format": "mp4"
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file = ydl.prepare_filename(info)
        send_video_with_music(chat_id, file, "download")
    except Exception as e:
        bot.send_message(chat_id, f"❌ Download error:\n{e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("music_"))
def convert_music(call):
    vid_id = call.data.split("_")[1]
    if vid_id not in video_files:
        bot.answer_callback_query(call.id, "File expired")
        return
    file_path = video_files[vid_id]
    audio_path = file_path.rsplit(".", 1)[0] + ".mp3"
    try:
        subprocess.run(["ffmpeg", "-y", "-i", file_path, "-vn", "-acodec", "mp3", "-ab", "128k", "-ar", "44100", audio_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        with open(audio_path, "rb") as audio:
            bot.send_audio(call.message.chat.id, audio, title="Converted Music")
        if os.path.exists(audio_path):
            os.remove(audio_path)
        if os.path.exists(file_path):
            os.remove(file_path)
        bot.answer_callback_query(call.id, "🎵 Music converted")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Conversion failed:\n{e}")

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
