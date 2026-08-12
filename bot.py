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

TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
BOT2_TOKEN = os.getenv("BOT2_TOKEN", "YOUR_BOT2_TOKEN")

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")

PHONE = os.getenv("PHONE", "")

GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_PASS = os.getenv("GMAIL_PASS", "")

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

# Plan prices in Telegram Stars (XTR)
STARS_PRICES = {
    "7": 50,
    "30": 150,
    "90": 350,
    "365": 1000
}

# ================= DATABASE FILES =================
USERS_FILE = "users.json"
WITHDRAWS_FILE = "withdraws.json"
VIDEOS_FILE = "videos.json"
COUPONS_FILE = "coupons.json"
REQUESTS_FILE = "requests.json"
MISSIONS_FILE = "missions.json"

# ================= JSON FUNCTIONS =================
def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

users = load_json(USERS_FILE, {})
withdraws = load_json(WITHDRAWS_FILE, [])
coupons = load_json(COUPONS_FILE, {})
feature_requests = load_json(REQUESTS_FILE, {})
missions_data = load_json(MISSIONS_FILE, {})

videos_data = load_json(VIDEOS_FILE, {
    "total": 0,
    "platforms": {
        "tiktok": 0,
        "youtube": 0,
        "facebook": 0,
        "pinterest": 0,
        "instagram": 0,
        "snapchat": 0
    },
    "users": {}
})

def save_users():
    save_json(USERS_FILE, users)

def save_withdraws():
    save_json(WITHDRAWS_FILE, withdraws)

def save_videos():
    save_json(VIDEOS_FILE, videos_data)

def save_coupons():
    save_json(COUPONS_FILE, coupons)

def save_requests():
    save_json(REQUESTS_FILE, feature_requests)

def save_missions():
    save_json(MISSIONS_FILE, missions_data)

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

def ensure_user_data(uid, username=""):
    uid = str(uid)
    if uid not in users:
        users[uid] = {
            "username": username,
            "balance": 0.0,
            "blocked": 0.0,
            "ref": random_ref(),
            "bot_id": random_botid(),
            "invited": 0,
            "referrals": [],
            "banned": False,
            "verified": False,
            "month": now_month(),
            "premium_until": 0,
            "premium_since": "",
            "vip_title": "⭐ VIP",
            "vip_level": 1,
            "points": 0,
            "claimed_milestones": [],
            "missions_progress": {},
            "completed_missions": [],
            "used_coupons": []
        }
    else:
        # Patch keys if missing
        u = users[uid]
        if username and not u.get("username"):
            u["username"] = username
        if "referrals" not in u: u["referrals"] = []
        if "premium_until" not in u: u["premium_until"] = 0
        if "premium_since" not in u: u["premium_since"] = ""
        if "vip_title" not in u: u["vip_title"] = "⭐ VIP"
        if "vip_level" not in u: u["vip_level"] = 1
        if "points" not in u: u["points"] = 0
        if "claimed_milestones" not in u: u["claimed_milestones"] = []
        if "missions_progress" not in u: u["missions_progress"] = {}
        if "completed_missions" not in u: u["completed_missions"] = []
        if "used_coupons" not in u: u["used_coupons"] = []
    save_users()

def is_premium(uid):
    uid = str(uid)
    if uid not in users:
        return False
    until = users[uid].get("premium_until", 0)
    return time.time() < until

def get_premium_days_left(uid):
    uid = str(uid)
    if not is_premium(uid):
        return 0
    until = users[uid].get("premium_until", 0)
    diff = until - time.time()
    return max(0, int(diff // 86400) + 1)

def add_premium_days(uid, days):
    uid = str(uid)
    ensure_user_data(uid)
    current_until = users[uid].get("premium_until", 0)
    now = time.time()
    if current_until < now:
        new_until = now + (days * 86400)
        users[uid]["premium_since"] = datetime.now().strftime("%d %b %Y")
    else:
        new_until = current_until + (days * 86400)
    users[uid]["premium_until"] = new_until
    save_users()

def add_points(uid, pts):
    uid = str(uid)
    ensure_user_data(uid)
    users[uid]["points"] = users[uid].get("points", 0) + pts
    # Update level based on points
    p = users[uid]["points"]
    users[uid]["vip_level"] = (p // 100) + 1
    save_users()

def get_user_rank(uid):
    uid = str(uid)
    sorted_u = sorted(users.items(), key=lambda x: x[1].get("points", 0), reverse=True)
    for index, (u, data) in enumerate(sorted_u, start=1):
        if u == uid:
            return index
    return len(users)

def progress_bar(current, total, length=10):
    percent = min(1.0, max(0.0, current / total))
    filled = int(round(length * percent))
    return "█" * filled + "░" * (length - filled)

# ================= MENUS =================
def user_menu(show_admin=False):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📥 Downloader", "👑 Premium")
    kb.add("💰 BALANCE", "💸 WITHDRAWAL")
    kb.add("👥 REFERRAL", "🆔 GET ID")
    kb.add("☎️ CUSTOMER", "🤖CUSTOMER AI")
    if show_admin:
        kb.add("👑 ADMIN PANEL")
    return kb

def admin_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📊 STATS", "📢 BROADCAST")
    kb.add("👑 PREMIUM ADMIN", "🎟 COUPON ADMIN")
    kb.add("💡 REQUESTS ADMIN", "🎯 MISSIONS ADMIN")
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
    kb.add("📥 IMPORT USERS", "🔗 GET REFERRAL CODE")
    kb.add("🔙 BACK MAIN MENU")
    return kb

def premium_inline_keyboard():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⭐ Buy Premium", callback_data="premium_plans"),
        InlineKeyboardButton("💎 My Plan", callback_data="premium_my_plan")
    )
    kb.add(
        InlineKeyboardButton("🎁 Invite Friends", callback_data="premium_referral"),
        InlineKeyboardButton("💡 Feature Requests", callback_data="premium_requests")
    )
    kb.add(
        InlineKeyboardButton("🏆 Leaderboard", callback_data="premium_leaderboard"),
        InlineKeyboardButton("🎯 Missions", callback_data="premium_missions")
    )
    kb.add(
        InlineKeyboardButton("🎟 Coupons", callback_data="premium_coupons"),
        InlineKeyboardButton("🎁 Gift Premium", callback_data="premium_gift")
    )
    kb.add(
        InlineKeyboardButton("👑 VIP Identity", callback_data="premium_vip")
    )
    kb.add(
        InlineKeyboardButton("🏠 Home", callback_data="premium_home")
    )
    return kb

# ================= BACK TO MAIN MENU =================
def back_to_main_menu(m):
    uid = str(m.from_user.id)
    bot.send_message(
        m.chat.id,
        "🔙 Returning to main menu",
        reply_markup=user_menu(is_admin(uid))
    )

@bot.message_handler(func=lambda m: m.text in ["🔙 BACK MAIN MENU", "📥 Downloader"])
def back_button_handler(m):
    back_to_main_menu(m)

CHANNEL_USERNAME = "@tiktokvediodownload"

# ================= START HANDLER =================
@bot.message_handler(commands=['start'])
def start_handler(message):
    if bot_locked_guard(message):
        return

    uid = message.from_user.id
    username = message.from_user.username or ""
    args = message.text.split()
    
    ensure_user_data(uid, username)

    # Handle Referral code
    if len(args) > 1:
        ref_code = args[1]
        
        # Check if referral code is standard user ref
        if not users[str(uid)].get("referred_by"):
            ref_user = next((u for u, d in users.items() if d.get("ref") == ref_code and u != str(uid)), None)
            if ref_user:
                users[str(uid)]["referred_by"] = ref_user
                users[ref_user]["balance"] = users[ref_user].get("balance", 0.0) + 0.2
                users[ref_user]["invited"] = users[ref_user].get("invited", 0) + 1
                if str(uid) not in users[ref_user].get("referrals", []):
                    users[ref_user]["referrals"].append(str(uid))
                
                add_points(ref_user, 5)
                check_mission_progress(ref_user, "invite")
                check_referral_milestones(ref_user)
                
                try:
                    bot.send_message(int(ref_user), f"🎉 <b>New Referral!</b> You earned $0.20 & 5 VIP Points from @{username or uid}!")
                except Exception:
                    pass
                save_users()

    check_membership(uid)

@bot.message_handler(commands=['view'])
def view_cmd(message):
    bot.send_message(
        message.chat.id,
        "🤖 <b>BOT INFO</b>\n\n"
        "📌 <b>Name:</b> Video Downloader Bot\n"
        "⚡ <b>Features:</b>\n"
        "• TikTok, YouTube, Instagram, FB, Pinterest, Snapchat\n"
        "• 👑 Full Premium VIP System\n"
        "• 🎯 Daily & Weekly Missions\n"
        "• 💡 Feature Requests & Voting\n"
        "• 🏆 VIP Leaderboards\n"
        "• 🎟 Discount Coupons\n"
        "• Referral Rewards & USDT Withdrawal"
    )

@bot.message_handler(commands=['balance'])
def balance_cmd(m):
    uid = str(m.from_user.id)
    ensure_user_data(uid)
    bal = users.get(uid, {}).get("balance", 0.0)
    bot.send_message(m.chat.id, f"💰 <b>Your balance:</b> ${bal:.2f}")

@bot.message_handler(commands=['refer'])
def refer_cmd(m):
    uid = str(m.from_user.id)
    ensure_user_data(uid)
    bot_username = bot.get_me().username
    ref = users[uid]['ref']

    link = f"https://t.me/{bot_username}?start={ref}"

    bot.send_message(
        m.chat.id,
        f"🔗 <b>Your referral link:</b>\n<code>{link}</code>\n\n"
        "Earn $0.20 and 5 VIP Points for every invited friend!"
    )

@bot.message_handler(commands=['ping'])
def ping_cmd(m):
    start = time.time()
    msg = bot.send_message(m.chat.id, "🏓 Pinging...")
    end = time.time()
    speed = round((end - start) * 1000)
    status = "🟢 Online" if speed < 1000 else "🟡 Slow"

    bot.edit_message_text(
        f"🏓 <b>PONG!</b>\n\n"
        f"⚡ <b>Speed:</b> {speed} ms\n"
        f"📡 <b>Status:</b> {status}",
        m.chat.id,
        msg.message_id
    )

# ================= VERIFY BOT START =================
@bot2.message_handler(commands=['start'])
def verify_start(message):
    args = message.text.split()
    if len(args) > 1:
        code = args[1]
        bot2.send_message(
            message.chat.id,
            f"🔑 <b>Your Verification Code</b>\n\n"
            f"<code>{code}</code>\n\n"
            "Copy this code and send it to the downloader bot."
        )
    else:
        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("GET", url=f"https://t.me/{bot.get_me().username}")
        )
        bot2.send_message(
            message.chat.id,
            "❌ <b>Don't Have Code?</b>\n\nGet code from downloader bot.",
            reply_markup=kb
        )

# ================= CHECK MEMBERSHIP =================
def check_membership(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["member", "administrator", "creator"]:
            send_welcome_message(user_id)
        else:
            send_join_message(user_id)
    except Exception:
        send_join_message(user_id)

def send_welcome_message(user_id):
    bot.send_message(
        user_id,
        "🎬 <b>Welcome to Video Downloader Bot!</b>\n\n"
        "Send any link from <b>TikTok, Instagram, YouTube, Facebook, Pinterest, Snapchat</b> to download instantly!\n\n"
        "👑 Tap <b>👑 Premium</b> below to explore VIP perks, Leaderboards, Missions & Rewards!",
        reply_markup=user_menu(is_admin(user_id))
    )

def send_join_message(user_id):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("➕ JOIN CHANNEL", url=f"https://t.me/{CHANNEL_USERNAME.replace('@','')}")
    )
    kb.add(
        InlineKeyboardButton("✅ CONFIRM", callback_data="confirm_join")
    )
    bot.send_message(
        user_id,
        "⚠️ <b>You must join our channel to use this bot.</b>",
        reply_markup=kb
    )

# ================= PREMIUM CENTER SYSTEM =================

@bot.message_handler(func=lambda m: m.text == "👑 Premium")
def open_premium_center(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    uid = str(m.from_user.id)
    ensure_user_data(uid, m.from_user.username or "")
    
    prem = is_premium(uid)
    status_str = "ACTIVE 🟢" if prem else "INACTIVE 🔴"
    days_left = get_premium_days_left(uid)
    
    plan_name = "VIP PRO" if prem else "None"
    until_ts = users[uid].get("premium_until", 0)
    exp_str = datetime.fromtimestamp(until_ts).strftime("%d %b %Y") if prem else "N/A"

    msg_text = (
        "╭━━━ 👑 <b>PREMIUM CENTER</b> ━━━╮\n\n"
        f"⭐ <b>STATUS:</b> {status_str}\n"
        f"💎 <b>PLAN:</b> {plan_name}\n"
        f"📅 <b>EXPIRES:</b> {exp_str}\n"
        f"⏳ <b>DAYS LEFT:</b> {days_left}\n\n"
        "✨ Unlock full high-speed downloads, VIP Identity, Missions & Exclusive Features!\n\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━╯"
    )
    
    bot.send_message(m.chat.id, msg_text, reply_markup=premium_inline_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith("premium_"))
def handle_premium_callbacks(call):
    uid = str(call.from_user.id)
    ensure_user_data(uid, call.from_user.username or "")
    data = call.data

    if data in ["premium_home", "premium_back"]:
        prem = is_premium(uid)
        status_str = "ACTIVE 🟢" if prem else "INACTIVE 🔴"
        days_left = get_premium_days_left(uid)
        plan_name = "VIP PRO" if prem else "None"
        until_ts = users[uid].get("premium_until", 0)
        exp_str = datetime.fromtimestamp(until_ts).strftime("%d %b %Y") if prem else "N/A"

        text = (
            "╭━━━ 👑 <b>PREMIUM CENTER</b> ━━━╮\n\n"
            f"⭐ <b>STATUS:</b> {status_str}\n"
            f"💎 <b>PLAN:</b> {plan_name}\n"
            f"📅 <b>EXPIRES:</b> {exp_str}\n"
            f"⏳ <b>DAYS LEFT:</b> {days_left}\n\n"
            "✨ Unlock full high-speed downloads, VIP Identity, Missions & Exclusive Features!\n\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯"
        )
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=premium_inline_keyboard())
        except Exception:
            pass

    elif data == "premium_my_plan":
        prem = is_premium(uid)
        days_left = get_premium_days_left(uid)
        until_ts = users[uid].get("premium_until", 0)
        exp_str = datetime.fromtimestamp(until_ts).strftime("%d %b %Y %H:%M") if prem else "Not Active"
        
        text = (
            "╭━━━ 💎 <b>MY VIP PLAN</b> ━━━╮\n\n"
            f"👤 <b>User:</b> @{users[uid].get('username') or uid}\n"
            f"👑 <b>Title:</b> {users[uid].get('vip_title', '⭐ VIP')}\n"
            f"🔥 <b>VIP Level:</b> {users[uid].get('vip_level', 1)}\n"
            f"🏆 <b>VIP Points:</b> {users[uid].get('points', 0)}\n"
            f"📅 <b>Expiration:</b> {exp_str}\n"
            f"⏳ <b>Days Remaining:</b> {days_left}\n\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯"
        )
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("⭐ Renew / Buy Plan", callback_data="premium_plans"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_home"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif data == "premium_plans":
        text = (
            "╭━━━ ⭐ <b>CHOOSE PREMIUM PLAN</b> ━━━╮\n\n"
            "Pay seamlessly with 💳 <b>Telegram Stars</b>:\n\n"
            "⭐ <b>7 Days Plan</b> — 50 Stars\n"
            "⭐ <b>30 Days Plan</b> — 150 Stars\n"
            "⭐ <b>90 Days Plan</b> — 350 Stars\n"
            "⭐ <b>1 Year Plan</b> — 1000 Stars\n\n"
            "Select your desired duration below:\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯"
        )
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("⭐ 7 Days (50 Stars)", callback_data="buy_plan_7"),
            InlineKeyboardButton("⭐ 30 Days (150 Stars)", callback_data="buy_plan_30")
        )
        kb.add(
            InlineKeyboardButton("⭐ 90 Days (350 Stars)", callback_data="buy_plan_90"),
            InlineKeyboardButton("⭐ 1 Year (1000 Stars)", callback_data="buy_plan_365")
        )
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_home"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif data == "premium_referral":
        bot_username = bot.get_me().username
        link = f"https://t.me/{bot_username}?start={users[uid]['ref']}"
        invited = users[uid].get("invited", 0)
        rank = get_user_rank(uid)

        text = (
            "╭━━━ 🎁 <b>INVITE & EARN</b> ━━━╮\n\n"
            f"👥 <b>REFERRALS:</b> {invited}\n"
            f"🎁 <b>REWARDS EARNED:</b> ${invited * 0.20:.2f}\n"
            f"🏆 <b>YOUR RANK:</b> #{rank}\n\n"
            f"🔗 <b>Your Link:</b>\n<code>{link}</code>\n\n"
            "Invite friends to get $0.20 cash + VIP Points!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯"
        )
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={link}&text=Join%20the%20best%20Downloader%20Bot!"),
            InlineKeyboardButton("👥 My Referrals", callback_data="premium_my_referrals")
        )
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_home"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif data == "premium_my_referrals":
        refs = users[uid].get("referrals", [])
        ref_text = f"👥 <b>YOUR REFERRALS ({len(refs)}):</b>\n\n"
        if not refs:
            ref_text += "<i>You have not invited anyone yet. Share your link to start earning!</i>"
        else:
            for idx, r_id in enumerate(refs[:15], 1):
                r_name = users.get(r_id, {}).get("username") or r_id
                ref_text += f"{idx}. @{r_name}\n"
            if len(refs) > 15:
                ref_text += f"\n<i>...and {len(refs) - 15} more.</i>"

        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_referral"))
        bot.edit_message_text(ref_text, call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif data == "premium_requests":
        render_feature_requests(call.message)

    elif data == "premium_leaderboard":
        render_leaderboard(call.message, uid)

    elif data == "premium_missions":
        render_missions(call.message, uid)

    elif data == "premium_coupons":
        text = (
            "╭━━━ 🎟 <b>COUPON CENTER</b> ━━━╮\n\n"
            "Have a promo or discount coupon code?\n"
            "Redeem it below for instant VIP Premium Days!\n\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯"
        )
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🎟 Redeem Coupon", callback_data="coupons_redeem"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_home"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif data == "premium_gift":
        text = (
            "╭━━━ 🎁 <b>GIFT PREMIUM</b> ━━━╮\n\n"
            "Surprise a friend with VIP Premium access!\n\n"
            "Tap below to select recipient and choose plan.\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯"
        )
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🎁 Gift a Friend Now", callback_data="gift_start"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_home"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif data == "premium_vip":
        render_vip_identity(call.message, uid)

# ================= TELEGRAM STARS PAYMENT SYSTEM =================

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_plan_"))
def process_stars_buy(call):
    days_key = call.data.split("_")[2]
    if days_key not in STARS_PRICES:
        return
    stars_price = STARS_PRICES[days_key]

    title = f"👑 VIP Premium ({days_key} Days)"
    description = f"Unlock {days_key} days of full VIP features on Downloader Bot!"
    payload = f"stars_prem_{days_key}_{call.from_user.id}_{int(time.time())}"

    prices = [LabeledPrice(label=f"VIP {days_key} Days", amount=stars_price)]

    try:
        bot.send_invoice(
            chat_id=call.message.chat.id,
            title=title,
            description=description,
            invoice_payload=payload,
            provider_token="",  # Blank for Telegram Stars XTR
            currency="XTR",
            prices=prices,
            start_parameter="vip-subscription"
        )
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Payment initialization failed: {e}")

@bot.pre_checkout_query_handler(func=lambda query: True)
def process_pre_checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def handle_successful_payment(message):
    pmt = message.successful_payment
    payload = pmt.invoice_payload

    if payload.startswith("stars_prem_"):
        parts = payload.split("_")
        days = int(parts[2])
        buyer_id = str(message.from_user.id)
        
        add_premium_days(buyer_id, days)
        add_points(buyer_id, days * 5)
        
        bot.send_message(
            message.chat.id,
            f"🎉 <b>PAYMENT SUCCESSFUL!</b>\n\n"
            f"👑 <b>{days} Days VIP Premium</b> activated on your account!\n"
            f"⭐️ Stars Paid: {pmt.total_amount}\n"
            f"🧾 Payment ID: <code>{pmt.telegram_payment_charge_id}</code>\n\n"
            "Enjoy your VIP Experience! 🚀"
        )
    elif payload.startswith("stars_gift_"):
        parts = payload.split("_")
        days = int(parts[2])
        target_uid = parts[3]
        
        add_premium_days(target_uid, days)
        add_points(message.from_user.id, days * 5)
        
        bot.send_message(
            message.chat.id,
            f"🎁 <b>GIFT DELIVERED!</b>\n\n"
            f"You successfully gifted <b>{days} Days VIP Premium</b> to user ID {target_uid}!"
        )
        
        try:
            bot.send_message(
                int(target_uid),
                f"╭━━━ 🎁 <b>PREMIUM GIFT</b> ━━━╮\n\n"
                f"🎉 <b>YOU RECEIVED A VIP GIFT!</b>\n\n"
                f"💎 <b>PLAN:</b> {days} DAYS\n"
                f"👤 <b>FROM:</b> @{message.from_user.username or message.from_user.id}\n\n"
                "Enjoy your VIP experience! 👑\n"
                "╰━━━━━━━━━━━━━━━━━━━━━━╯"
            )
        except Exception:
            pass

# ================= FEATURE REQUESTS & VOTING =================

def render_feature_requests(message):
    req_list = sorted(feature_requests.values(), key=lambda x: len(x.get("votes", [])), reverse=True)
    
    text = "╭━━━ 💡 <b>FEATURE REQUESTS</b> ━━━╮\n\n🔥 <b>MOST REQUESTED FEATURES</b>\n\n"
    if not req_list:
        text += "<i>No feature requests yet. Submit the first one!</i>\n"
    else:
        for idx, r in enumerate(req_list[:5], 1):
            votes_cnt = len(r.get("votes", []))
            text += f"{idx}️⃣ <b>{r['title']}</b> ({r.get('status', '🟡 Pending')})\n👍 {votes_cnt} Votes | ID: <code>{r['id']}</code>\n\n"
            
    text += "╰━━━━━━━━━━━━━━━━━━━━━━╯"

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("👍 Vote", callback_data="req_vote_prompt"),
        InlineKeyboardButton("💡 Submit Request", callback_data="req_submit_start")
    )
    kb.add(
        InlineKeyboardButton("📋 My Requests", callback_data="req_my_requests"),
        InlineKeyboardButton("🔙 Back", callback_data="premium_home")
    )
    bot.edit_message_text(text, message.chat.id, message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("req_"))
def handle_requests_callbacks(call):
    uid = str(call.from_user.id)
    data = call.data

    if data == "req_submit_start":
        if not is_premium(uid):
            bot.answer_callback_query(call.id, "👑 Premium users only feature!", show_alert=True)
            return
        msg = bot.send_message(call.message.chat.id, "💡 <b>Enter feature title:</b>")
        bot.register_next_step_handler(msg, process_req_title)

    elif data == "req_vote_prompt":
        msg = bot.send_message(call.message.chat.id, "✍️ Send the ID of the feature request you want to vote for:")
        bot.register_next_step_handler(msg, process_req_vote)

    elif data == "req_my_requests":
        user_reqs = [r for r in feature_requests.values() if str(r.get("user_id")) == uid]
        text = f"📋 <b>YOUR REQUESTS ({len(user_reqs)}):</b>\n\n"
        for r in user_reqs:
            text += f"• <b>{r['title']}</b> - {r.get('status', '🟡 Pending')} (👍 {len(r.get('votes', []))} votes)\n"
        if not user_reqs:
            text += "<i>You haven't submitted any requests yet.</i>"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_requests"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

def process_req_title(m):
    title = (m.text or "").strip()
    if not title:
        bot.send_message(m.chat.id, "❌ Invalid title.")
        return
    msg = bot.send_message(m.chat.id, "💡 Enter detailed description of your feature:")
    bot.register_next_step_handler(msg, lambda x: process_req_desc(x, title))

def process_req_desc(m, title):
    desc = (m.text or "").strip()
    req_id = str(uuid.uuid4())[:6]
    uid = str(m.from_user.id)
    
    feature_requests[req_id] = {
        "id": req_id,
        "user_id": uid,
        "title": title,
        "desc": desc,
        "status": "🟡 Pending",
        "votes": [uid]
    }
    save_requests()
    check_mission_progress(uid, "submit_req")
    add_points(uid, 10)

    bot.send_message(
        m.chat.id,
        f"✅ <b>Feature Request Submitted!</b>\n\n"
        f"🆔 ID: <code>{req_id}</code>\n"
        f"📌 Title: {title}\n"
        f"⏳ Status: 🟡 Pending"
    )

def process_req_vote(m):
    req_id = (m.text or "").strip()
    uid = str(m.from_user.id)
    if req_id not in feature_requests:
        bot.send_message(m.chat.id, "❌ Feature request ID not found.")
        return

    votes = feature_requests[req_id].get("votes", [])
    if uid in votes:
        bot.send_message(m.chat.id, "⚠️ You have already voted for this feature.")
        return

    votes.append(uid)
    feature_requests[req_id]["votes"] = votes
    save_requests()
    check_mission_progress(uid, "vote")
    add_points(uid, 3)

    bot.send_message(m.chat.id, f"👍 <b>Vote counted!</b> Total votes for '{feature_requests[req_id]['title']}': {len(votes)}")

# ================= LEADERBOARD SYSTEM =================

def render_leaderboard(message, uid):
    sorted_u = sorted(users.items(), key=lambda x: x[1].get("points", 0), reverse=True)
    
    text = "╭━━━ 🏆 <b>VIP LEADERBOARD</b> ━━━╮\n\n"
    medals = ["🥇", "🥈", "🥉"]
    
    for idx, (u, data) in enumerate(sorted_u[:5], 1):
        badge = medals[idx-1] if idx <= 3 else f"{idx}️⃣"
        name = data.get("username") or u
        pts = data.get("points", 0)
        text += f"{badge} @{name} — <b>{pts} POINTS</b>\n"

    user_rank = get_user_rank(uid)
    user_pts = users[str(uid)].get("points", 0)

    text += "\n━━━━━━━━━━━━━━━━━━\n"
    text += f"⭐ <b>YOUR RANK:</b> #{user_rank}\n"
    text += f"💎 <b>YOUR POINTS:</b> {user_pts}\n"
    text += "╰━━━━━━━━━━━━━━━━━━━━━━╯"

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("📊 My Rank", callback_data="lb_my_rank"),
        InlineKeyboardButton("🏆 Top 20", callback_data="lb_top20")
    )
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_home"))
    bot.edit_message_text(text, message.chat.id, message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("lb_"))
def handle_lb_callbacks(call):
    uid = str(call.from_user.id)
    if call.data == "lb_my_rank":
        rank = get_user_rank(uid)
        pts = users[uid].get("points", 0)
        bot.answer_callback_query(call.id, f"Your Rank: #{rank} with {pts} Points!", show_alert=True)
    elif call.data == "lb_top20":
        sorted_u = sorted(users.items(), key=lambda x: x[1].get("points", 0), reverse=True)
        top_text = "🏆 <b>TOP 20 VIP LEADERBOARD:</b>\n\n"
        for idx, (u, data) in enumerate(sorted_u[:20], 1):
            name = data.get("username") or u
            pts = data.get("points", 0)
            top_text += f"{idx}. @{name} - {pts} pts\n"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_leaderboard"))
        bot.edit_message_text(top_text, call.message.chat.id, call.message.message_id, reply_markup=kb)

# ================= MISSIONS SYSTEM =================

MISSIONS_CONFIG = {
    "m_download": {"title": "📥 Download 10 Files", "target": 10, "reward_days": 1, "reward_pts": 20},
    "m_invite": {"title": "🎁 Invite 3 Friends", "target": 3, "reward_days": 2, "reward_pts": 30},
    "m_vote": {"title": "👍 Vote on 3 Features", "target": 3, "reward_days": 1, "reward_pts": 15}
}

def render_missions(message, uid):
    ensure_user_data(uid)
    prog = users[uid].get("missions_progress", {})
    completed = users[uid].get("completed_missions", [])

    text = "╭━━━ 🎯 <b>VIP MISSIONS</b> ━━━╮\n\n"

    for m_id, cfg in MISSIONS_CONFIG.items():
        curr = prog.get(m_id, 0)
        t = cfg["target"]
        bar = progress_bar(curr, t)
        is_done = m_id in completed
        status_icon = "✅" if is_done else f"{curr}/{t}"
        
        text += f"{cfg['title']}\n{bar} {status_icon}\n🎁 Reward: ⭐ {cfg['reward_days']} Day Premium + {cfg['reward_pts']} Pts\n\n"

    text += "╰━━━━━━━━━━━━━━━━━━━━━━╯"

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_home"))
    bot.edit_message_text(text, message.chat.id, message.message_id, reply_markup=kb)

def check_mission_progress(uid, event_type):
    uid = str(uid)
    ensure_user_data(uid)
    
    m_map = {
        "download": "m_download",
        "invite": "m_invite",
        "vote": "m_vote"
    }
    m_id = m_map.get(event_type)
    if not m_id:
        return

    completed = users[uid].get("completed_missions", [])
    if m_id in completed:
        return

    curr = users[uid]["missions_progress"].get(m_id, 0) + 1
    users[uid]["missions_progress"][m_id] = curr
    
    cfg = MISSIONS_CONFIG[m_id]
    if curr >= cfg["target"]:
        users[uid]["completed_missions"].append(m_id)
        add_premium_days(uid, cfg["reward_days"])
        add_points(uid, cfg["reward_pts"])
        try:
            bot.send_message(
                int(uid),
                f"🎉 <b>MISSION COMPLETED!</b>\n\n"
                f"🎯 <b>{cfg['title']}</b>\n"
                f"🎁 Received: ⭐ {cfg['reward_days']} Day Premium + {cfg['reward_pts']} Points!"
            )
        except Exception:
            pass

    save_users()

def check_referral_milestones(uid):
    uid = str(uid)
    invited = users[uid].get("invited", 0)
    claimed = users[uid].get("claimed_milestones", [])
    
    milestones = {
        3: 1,
        5: 2,
        10: 5,
        25: 12,
        50: 30
    }
    
    for count, days in milestones.items():
        if invited >= count and count not in claimed:
            claimed.append(count)
            users[uid]["claimed_milestones"] = claimed
            add_premium_days(uid, days)
            try:
                bot.send_message(
                    int(uid),
                    f"🏆 <b>REFERRAL MILESTONE REACHED!</b>\n\n"
                    f"👥 Reached {count} Referrals!\n"
                    f"🎁 Bonus Reward: ⭐ {days} Days Premium!"
                )
            except Exception:
                pass
            save_users()

# ================= COUPONS SYSTEM =================

@bot.callback_query_handler(func=lambda call: call.data == "coupons_redeem")
def prompt_coupon_entry(call):
    msg = bot.send_message(call.message.chat.id, "🎟 <b>Send your Coupon Code:</b>")
    bot.register_next_step_handler(msg, process_coupon_redeem)

def process_coupon_redeem(m):
    code = (m.text or "").strip().upper()
    uid = str(m.from_user.id)
    ensure_user_data(uid)

    if code not in coupons or not coupons[code].get("active", True):
        bot.send_message(m.chat.id, "❌ Invalid or inactive coupon code.")
        return

    c = coupons[code]
    used_by = c.get("used_by", [])
    
    if uid in used_by:
        bot.send_message(m.chat.id, "⚠️ You have already used this coupon code.")
        return

    if len(used_by) >= c.get("max_uses", 100):
        bot.send_message(m.chat.id, "❌ This coupon usage limit has been reached.")
        return

    used_by.append(uid)
    c["used_by"] = used_by
    save_coupons()

    reward_days = c.get("reward_days", 1)
    add_premium_days(uid, reward_days)
    add_points(uid, 10)

    bot.send_message(
        m.chat.id,
        f"🎉 <b>COUPON REDEEMED!</b>\n\n"
        f"🎟 Code: <b>{code}</b>\n"
        f"🎁 Reward: ⭐ {reward_days} Days VIP Premium!"
    )

# ================= GIFT PREMIUM SYSTEM =================

@bot.callback_query_handler(func=lambda call: call.data == "gift_start")
def prompt_gift_recipient(call):
    msg = bot.send_message(call.message.chat.id, "🎁 <b>Enter @username or Telegram ID of the user you want to gift Premium to:</b>")
    bot.register_next_step_handler(msg, process_gift_recipient)

def process_gift_recipient(m):
    target = (m.text or "").strip().replace("@", "")
    target_uid = None
    
    if target.isdigit() and target in users:
        target_uid = target
    else:
        for u, d in users.items():
            if d.get("username", "").lower() == target.lower():
                target_uid = u
                break

    if not target_uid:
        bot.send_message(m.chat.id, "❌ User not found in database.")
        return

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⭐ 7 Days (50 Stars)", callback_data=f"buy_gift_7_{target_uid}"),
        InlineKeyboardButton("⭐ 30 Days (150 Stars)", callback_data=f"buy_gift_30_{target_uid}")
    )
    kb.add(
        InlineKeyboardButton("⭐ 90 Days (350 Stars)", callback_data=f"buy_gift_90_{target_uid}"),
        InlineKeyboardButton("⭐ 1 Year (1000 Stars)", callback_data=f"buy_gift_365_{target_uid}")
    )
    bot.send_message(m.chat.id, f"🎁 Select Premium Plan duration to gift to @{users[target_uid].get('username') or target_uid}:", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_gift_"))
def process_gift_stars(call):
    parts = call.data.split("_")
    days_key = parts[2]
    target_uid = parts[3]
    
    if days_key not in STARS_PRICES:
        return
    stars_price = STARS_PRICES[days_key]

    title = f"🎁 Gift VIP ({days_key} Days)"
    description = f"Gift {days_key} days of VIP Premium to user {target_uid}"
    payload = f"stars_gift_{days_key}_{target_uid}_{call.from_user.id}"

    prices = [LabeledPrice(label=f"Gift {days_key} Days", amount=stars_price)]

    try:
        bot.send_invoice(
            chat_id=call.message.chat.id,
            title=title,
            description=description,
            invoice_payload=payload,
            provider_token="",
            currency="XTR",
            prices=prices,
            start_parameter="vip-gift"
        )
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Payment initialization failed: {e}")

# ================= VIP IDENTITY SYSTEM =================

def render_vip_identity(message, uid):
    ensure_user_data(uid)
    u = users[uid]
    
    text = (
        "╭━━━ 👑 <b>VIP IDENTITY</b> ━━━╮\n\n"
        f"👤 <b>User:</b> @{u.get('username') or uid}\n\n"
        f"💎 <b>TITLE:</b> {u.get('vip_title', '⭐ VIP')}\n"
        f"🔥 <b>LEVEL:</b> {u.get('vip_level', 1)}\n"
        f"🏆 <b>POINTS:</b> {u.get('points', 0)}\n\n"
        f"📅 <b>PREMIUM SINCE:</b> {u.get('premium_since') or 'N/A'}\n\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━╯"
    )

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⭐ VIP", callback_data="title_⭐ VIP"),
        InlineKeyboardButton("💎 PRO", callback_data="title_💎 PRO")
    )
    kb.add(
        InlineKeyboardButton("🔥 LEGEND", callback_data="title_🔥 LEGEND"),
        InlineKeyboardButton("👑 ELITE", callback_data="title_👑 ELITE")
    )
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_home"))
    bot.edit_message_text(text, message.chat.id, message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("title_"))
def change_vip_title(call):
    uid = str(call.from_user.id)
    new_title = call.data.split("_")[1]
    
    if not is_premium(uid):
        bot.answer_callback_query(call.id, "👑 Only Premium users can change VIP Title!", show_alert=True)
        return

    users[uid]["vip_title"] = new_title
    save_users()
    bot.answer_callback_query(call.id, f"✅ VIP Title changed to {new_title}!")
    render_vip_identity(call.message, uid)

# ================= ADMIN EXPANDED CONTROLS =================

@bot.message_handler(func=lambda m: m.text == "👑 PREMIUM ADMIN")
def admin_premium_menu(m):
    if not is_admin(m.from_user.id):
        return
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("➕ Give Premium", callback_data="adm_give_prem"),
        InlineKeyboardButton("➖ Remove Premium", callback_data="adm_rem_prem")
    )
    bot.send_message(m.chat.id, "👑 <b>Premium Management:</b>", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "🎟 COUPON ADMIN")
def admin_coupon_menu(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "🎟 <b>Send Coupon details:</b>\n\nFormat: <code>CODE | DAYS | MAX_USES</code>\nExample: <code>VIP50 | 30 | 100</code>")
    bot.register_next_step_handler(msg, process_add_coupon)

def process_add_coupon(m):
    try:
        parts = [p.strip() for p in m.text.split("|")]
        code = parts[0].upper()
        days = int(parts[1])
        uses = int(parts[2])
        
        coupons[code] = {
            "code": code,
            "reward_days": days,
            "max_uses": uses,
            "used_by": [],
            "active": True
        }
        save_coupons()
        bot.send_message(m.chat.id, f"✅ Coupon <b>{code}</b> created ({days} days, {uses} uses)!")
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Error creating coupon: {e}")

@bot.message_handler(func=lambda m: m.text == "💡 REQUESTS ADMIN")
def admin_requests_menu(m):
    if not is_admin(m.from_user.id):
        return
    text = "💡 <b>FEATURE REQUESTS MANAGEMENT:</b>\n\n"
    for r in list(feature_requests.values())[:10]:
        text += f"🆔 <code>{r['id']}</code> | <b>{r['title']}</b> ({r.get('status')})\n"
    msg = bot.send_message(m.chat.id, text + "\nSend: <code>REQ_ID | STATUS</code> to update status.\n(Statuses: Completed, In Progress, Reviewing, Rejected)")
    bot.register_next_step_handler(msg, process_update_req_status)

def process_update_req_status(m):
    try:
        req_id, status = [p.strip() for p in m.text.split("|")]
        if req_id in feature_requests:
            feature_requests[req_id]["status"] = status
            save_requests()
            bot.send_message(m.chat.id, f"✅ Request {req_id} status updated to {status}!")
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Error: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_"))
def handle_admin_callbacks(call):
    if not is_admin(call.from_user.id):
        return
    if call.data == "adm_give_prem":
        msg = bot.send_message(call.message.chat.id, "Send: <code>USER_ID | DAYS</code>")
        bot.register_next_step_handler(msg, process_adm_give_prem)
    elif call.data == "adm_rem_prem":
        msg = bot.send_message(call.message.chat.id, "Send User ID to strip Premium:")
        bot.register_next_step_handler(msg, process_adm_rem_prem)

def process_adm_give_prem(m):
    try:
        uid, days = [p.strip() for p in m.text.split("|")]
        add_premium_days(uid, int(days))
        bot.send_message(m.chat.id, f"✅ Granted {days} days Premium to {uid}!")
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Error: {e}")

def process_adm_rem_prem(m):
    uid = m.text.strip()
    if uid in users:
        users[uid]["premium_until"] = 0
        save_users()
        bot.send_message(m.chat.id, f"✅ Removed Premium from {uid}!")

# ================= VERIFY SYSTEM HANDLERS =================

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
        bot.send_message(call.message.chat.id, "❌ Cannot send DM.\nUser must message your Telegram account first.")

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

    if send_gmail_code(email, code):
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
        bot.send_message(call.message.chat.id, "⚠️ Telegram blocked sending message.\nUser must message your account first.")

@bot.callback_query_handler(func=lambda call: call.data == "verify_email")
def verify_email(call):
    msg = bot.send_message(call.message.chat.id, "📧 Send your Gmail address to receive verification code.")
    bot.register_next_step_handler(msg, process_email)

# ================= CONFIRM JOIN =================
@bot.callback_query_handler(func=lambda call: call.data == "confirm_join")
def confirm_join(call):
    user_id = call.from_user.id
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["member","administrator","creator"]:
            bot.answer_callback_query(call.id,"✅ Join verified")
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception:
                pass
            bot.send_message(user_id, "✅ Join confirmed!\nNow you can use the bot.\nSend your video link.", reply_markup=user_menu(is_admin(user_id)))
        else:
            bot.answer_callback_query(call.id, "❌ You must join the channel first!", show_alert=True)
    except Exception:
        bot.answer_callback_query(call.id, "❌ Please join the channel first!", show_alert=True)

# ================= ADMIN PANEL HANDLERS =================
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
    ensure_user_data(uid)
    bal = users[uid].get("balance", 0.0)
    blocked = users[uid].get("blocked", 0.0)
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
    ensure_user_data(uid)
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
    ensure_user_data(uid)
    bot_username = bot.get_me().username
    link = f"https://t.me/{bot_username}?start={users[uid]['ref']}"
    invited = users[uid].get("invited", 0)
    bot.send_message(
        m.chat.id,
        f"🔗 Your Referral Link:\n<code>{link}</code>\n\n"
        f"👥 Invited Users: {invited}\n"
        f"🎁 You earn $0.20 per referral!"
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

# ================= WITHDRAWAL MENU =================
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
    except Exception:
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
        f"✅ Withdrawal Request Sent\n"
        f"🧾 Request ID: {wid}\n"
        f"💵 Amount: ${amt:.2f}\n"
        f"🏦 Address: {withdrawal['address']}\n"
        f"💰 Balance Left: ${users[uid]['balance']:.2f}\n"
        f"⏳ Status: Pending",
        reply_markup=user_menu(is_admin(uid))
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
        except Exception:
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
    try:
        bot.send_message(int(uid), "✅ You have been unbanned by admin.")
    except Exception:
        pass

@bot.message_handler(func=lambda m: m.text == "💳 WITHDRAWAL CHECK")
def withdrawal_check_start(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "Enter Withdrawal Request ID (example: 40201):")
    bot.register_next_step_handler(msg, withdrawal_check_process)

def withdrawal_check_process(m):
    if not is_admin(m.from_user.id):
        return
    try:
        wid = int(m.text.strip())
    except Exception:
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
        return
    total_users = len(users)
    total_balance = sum(u.get("balance", 0.0) for u in users.values())
    total_blocked = sum(u.get("blocked", 0.0) for u in users.values())
    total_withdraws = len(withdraws)
    pending_withdraws = len([w for w in withdraws if w["status"] == "pending"])
    premium_users = len([u for u in users if is_premium(u)])

    msg = (
        f"📊 <b>BOT STATS</b>\n\n"
        f"👥 Total Users: {total_users}\n"
        f"👑 Premium Users: {premium_users}\n"
        f"💰 Total Balance: ${total_balance:.2f}\n"
        f"⏳ Total Blocked: ${total_blocked:.2f}\n"
        f"🧾 Total Withdrawals: {total_withdraws}\n"
        f"⏳ Pending Withdrawals: {pending_withdraws}"
    )
    bot.send_message(m.chat.id, msg)

@bot.message_handler(func=lambda m: m.text == "🚫 BAN USER MANUAL")
def manual_ban_start(m):
    if not is_admin(m.from_user.id):
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
    except Exception:
        bot.send_message(m.chat.id, "❌ Invalid channel or bot not inside channel")

@bot.message_handler(func=lambda m: m.text == "🔍 RAADI")
def raadi_stats(m):
    if not is_admin(m.from_user.id):
        return
    total_videos = videos_data.get("total", 0)
    platform_stats = videos_data.get("platforms", {})
    users_stats = videos_data.get("users", {})

    if not users_stats:
        bot.send_message(m.chat.id, "❌ No video data found yet.")
        return

    top_user_id, top_count = max(users_stats.items(), key=lambda x: x[1])

    msg_lines = [
        "🔍 <b>DOWNLOAD ANALYTICS</b>\n",
        f"🎬 Total Videos Downloaded: {total_videos}",
        f"🏆 Top Downloader: <a href='tg://user?id={top_user_id}'>{top_user_id}</a> ({top_count} videos)\n",
        "📊 Downloads by Platform:",
        f"• TikTok: {platform_stats.get('tiktok',0)}",
        f"• YouTube: {platform_stats.get('youtube',0)}",
        f"• Facebook: {platform_stats.get('facebook',0)}",
        f"• Pinterest: {platform_stats.get('pinterest',0)}\n",
        "🥇 Top Users:"
    ]

    sorted_u = sorted(users_stats.items(), key=lambda x: x[1], reverse=True)
    for i, (uid, count) in enumerate(sorted_u[:20], start=1):
        bot_id = users.get(str(uid), {}).get("bot_id", "N/A")
        msg_lines.append(f"{i}. 👤 <a href='tg://user?id={uid}'>{uid}</a> - 🎬 {count} vids | 🤖 ID: {bot_id}")

    bot.send_message(m.chat.id, "\n".join(msg_lines))

@bot.message_handler(func=lambda m: m.text == "📢 BROADCAST")
def broadcast_start(m):
    if not is_admin(m.from_user.id):
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
        except Exception:
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
        if count >= 15:
            break
    bot.send_message(m.chat.id, f"📊 Total Users: {total}")

@bot.message_handler(func=lambda m: m.text == "🔒 LOCK BOT")
def lock_bot_start(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "✍️ Send lock message:")
    bot.register_next_step_handler(msg, lock_bot_process)

def lock_bot_process(m):
    global BOT_LOCKED, LOCK_MESSAGE
    if not is_admin(m.from_user.id):
        return
    text = (m.text or "").strip()
    if text:
        LOCK_MESSAGE = text
        BOT_LOCKED = True
        bot.send_message(m.chat.id, f"🔒 Bot locked successfully.\nMessage:\n{text}")

@bot.message_handler(func=lambda m: m.text == "🔓 UNLOCK BOT")
def unlock_bot(m):
    global BOT_LOCKED
    if not is_admin(m.from_user.id):
        return
    BOT_LOCKED = False
    bot.send_message(m.chat.id, "🔓 Bot unlocked successfully.")

@bot.message_handler(func=lambda m: m.text == "📢 ADD ADS")
def add_ads_start(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(
        m.chat.id,
        "✍️ <b>Format:</b>\n<code>Button Name | Link | Text</code>\n\nExample:\n<code>FOLLOW MY TIKTOK | https://tiktok.com/@username | Igula soco TikTok!</code>"
    )
    bot.register_next_step_handler(msg, process_add_ads)

def process_add_ads(m):
    global ADS_ENABLED, ADS_BTN_TEXT, ADS_URL, ADS_TEXT
    if not is_admin(m.from_user.id):
        return
    text = (m.text or "").strip()
    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 2:
        bot.send_message(m.chat.id, "❌ Format error.")
        return
    ADS_BTN_TEXT = parts[0]
    ADS_URL = parts[1]
    ADS_TEXT = parts[2] if len(parts) > 2 else "✨ Nagala soco baraha bulshada!"
    ADS_ENABLED = True
    bot.send_message(m.chat.id, "✅ Ads enabled!")

@bot.message_handler(func=lambda m: m.text == "🗑 DELETE ADS")
def delete_ads(m):
    global ADS_ENABLED, ADS_BTN_TEXT, ADS_URL, ADS_TEXT
    if not is_admin(m.from_user.id):
        return
    ADS_ENABLED = False
    ADS_BTN_TEXT, ADS_URL, ADS_TEXT = "", "", ""
    bot.send_message(m.chat.id, "🗑 Ads deleted.")

@bot.message_handler(func=lambda m: m.text == "📥 IMPORT USERS")
def import_users_start(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "Send Telegram IDs separated by spaces or new lines:")
    bot.register_next_step_handler(msg, import_users_process)

def import_users_process(m):
    if not is_admin(m.from_user.id):
        return
    ids = m.text.strip().replace("\n", " ").split()
    added = 0
    for uid in ids:
        uid = uid.strip()
        if uid.isdigit() and uid not in users:
            ensure_user_data(uid)
            added += 1
    save_users()
    bot.send_message(m.chat.id, f"✅ Imported {added} users.")

@bot.message_handler(func=lambda m: m.text == "🔗 GET REFERRAL CODE")
def get_ref_code_start(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "Send user username:\nExample:\n@scholes1")
    bot.register_next_step_handler(msg, get_ref_username)

def get_ref_username(m):
    if not is_admin(m.from_user.id):
        return
    username = m.text.replace("@", "").strip()
    msg = bot.send_message(m.chat.id, f"User: @{username}\nNow send custom code number:")
    bot.register_next_step_handler(msg, lambda x: save_custom_ref_code(x, username))

def save_custom_ref_code(m, username):
    if not is_admin(m.from_user.id):
        return
    code = m.text.strip()
    user_id = next((uid for uid, data in users.items() if data.get("username","").lower() == username.lower()), None)
    if not user_id:
        bot.send_message(m.chat.id, "❌ User not found")
        return
    users[user_id]["ref"] = code
    save_users()
    bot.send_message(m.chat.id, f"✅ Custom Ref Link set for @{username}: https://t.me/{bot.get_me().username}?start={code}")

@bot.message_handler(func=lambda m: m.text == "🔎 SEARCH USER")
def search_user(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "Send User Telegram ID:")
    bot.register_next_step_handler(msg, search_user_result)

def search_user_result(m):
    if not is_admin(m.from_user.id):
        return
    uid = m.text.strip()
    if uid in users:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("💬 OPEN CHAT", url=f"tg://user?id={uid}"))
        bot.send_message(m.chat.id, f"👤 User Found\nID: {uid}", reply_markup=kb)
    else:
        bot.send_message(m.chat.id, "❌ User not found")

# ================= MEDIA DOWNLOADER ENGINE =================

@bot.message_handler(func=lambda m: m.text and "http" in m.text)
def handle_links(message):
    if bot_locked_guard(message) or banned_guard(message):
        return

    user_id = message.from_user.id
    link = message.text.strip()
    ensure_user_data(user_id, message.from_user.username or "")

    # Multi channel check
    if CHANNEL_WINDOW_OPEN and POST_CHANNELS:
        joined_all = True
        for ch in POST_CHANNELS:
            try:
                member = bot.get_chat_member(f"@{ch}", user_id)
                if member.status not in ["member", "administrator", "creator"]:
                    joined_all = False
                    break
            except Exception:
                joined_all = False
                break

        if not joined_all:
            pending_links[user_id] = link
            send_multi_join(user_id)
            return

    # Verification check
    if VERIFY_ENABLED and not users.get(str(user_id), {}).get("verified", False):
        code = str(random.randint(10000, 99999))
        verify_pending[user_id] = {"code": code, "link": link}

        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📩 Verify via DM", callback_data="via_telegram"))
        kb.add(InlineKeyboardButton("🤖 Verify via Bot", url=f"https://t.me/Verifyd_bot?start={code}"))
        kb.add(InlineKeyboardButton("📧 Verify via Gmail", callback_data="verify_email"))
        bot.send_message(message.chat.id, "🔐 Verification Required\n\nChoose verification method:", reply_markup=kb)
        return

    bot.send_message(message.chat.id, "⏳ Downloading media...")
    download_media(message.chat.id, link)

def extract_url(text):
    urls = re.findall(r'https?://[^\s]+', text)
    return urls[0] if urls else None

CAPTION_TEXT = "Downloaded by:\n@Downloadvedioytibot"

def send_video_with_music(chat_id, file_path, platform=None):
    vid_id = str(uuid.uuid4())[:8]
    video_files[vid_id] = file_path

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🎵 Convert to Music", callback_data=f"music_{vid_id}"))

    if ADS_ENABLED and ADS_BTN_TEXT and ADS_URL:
        kb.add(InlineKeyboardButton(ADS_BTN_TEXT, url=ADS_URL))

    uid = str(chat_id)
    ensure_user_data(uid)

    videos_data["total"] = videos_data.get("total", 0) + 1
    videos_data["users"][uid] = videos_data["users"].get(uid, 0) + 1

    if platform:
        if "platforms" not in videos_data:
            videos_data["platforms"] = {}
        videos_data["platforms"][platform] = videos_data["platforms"].get(platform, 0) + 1

    save_videos()
    add_points(uid, 1)
    check_mission_progress(uid, "download")

    caption = CAPTION_TEXT
    if ADS_ENABLED and ADS_TEXT:
        caption += f"\n\n{ADS_TEXT}"

    with open(file_path, "rb") as video:
        bot.send_video(chat_id, video, caption=caption, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("music_"))
def convert_to_music(call):
    vid_id = call.data.split("_")[1]
    if vid_id not in video_files or not os.path.exists(video_files[vid_id]):
        bot.answer_callback_query(call.id, "❌ Video file expired or not found.", show_alert=True)
        return

    bot.answer_callback_query(call.id, "⏳ Converting video to audio...")
    vid_path = video_files[vid_id]
    audio_path = f"audio_{vid_id}.mp3"

    try:
        subprocess.run(["ffmpeg", "-y", "-i", vid_path, "-vn", "-ab", "128k", "-ar", "44100", "-f", "mp3", audio_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with open(audio_path, "rb") as audio:
            bot.send_audio(call.message.chat.id, audio, caption=CAPTION_TEXT)
        if os.path.exists(audio_path):
            os.remove(audio_path)
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Audio conversion failed: {e}")

def download_media(chat_id, text):
    try:
        url = extract_url(text)
        if not url:
            bot.send_message(chat_id, "❌ Invalid link")
            return

        # TikTok
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
                        filename = f"tiktok_{uuid.uuid4().hex[:6]}.mp4"
                        with open(filename, "wb") as f:
                            f.write(video_data)
                        send_video_with_music(chat_id, filename, "tiktok")
                        return
            except Exception as e:
                bot.send_message(chat_id, f"❌ TikTok download error: {e}")
                return

        # Snapchat
        if "snapchat.com" in url or "snap.com" in url:
            try:
                ydl_opts = {"format": "best", "outtmpl": "snapchat_%(id)s.%(ext)s", "quiet": True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    file = ydl.prepare_filename(info)
                send_video_with_music(chat_id, file, "snapchat")
                if os.path.exists(file):
                    os.remove(file)
                return
            except Exception as e:
                bot.send_message(chat_id, f"❌ Snapchat error: {e}")
                return

        # Pinterest
        if "pinterest.com" in url or "pin.it" in url:
            try:
                ydl_opts = {"format": "bv*+ba/b", "outtmpl": "pinterest_%(id)s.%(ext)s", "quiet": True, "merge_output_format": "mp4"}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    entries = info["entries"] if "entries" in info else [info]
                    for entry in entries:
                        file = ydl.prepare_filename(entry)
                        if file.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                            with open(file, "rb") as photo:
                                bot.send_photo(chat_id, photo, caption=CAPTION_TEXT)
                        else:
                            send_video_with_music(chat_id, file, "pinterest")
                        if os.path.exists(file):
                            os.remove(file)
                return
            except Exception as e:
                bot.send_message(chat_id, f"❌ Pinterest error: {e}")
                return

        # Instagram
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
                        if os.path.exists(file):
                            os.remove(file)
                return
            except Exception as e:
                bot.send_message(chat_id, f"❌ Instagram error: {e}")
                return

        # Facebook & YouTube Fallback
        ydl_opts = {"format": "bestvideo+bestaudio/best", "outtmpl": "media_%(id)s.%(ext)s", "merge_output_format": "mp4", "quiet": True}
        platform = "youtube" if "youtube" in url or "youtu.be" in url else "facebook"
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file = ydl.prepare_filename(info)
        send_video_with_music(chat_id, file, platform)
        if os.path.exists(file):
            os.remove(file)

    except Exception as e:
        bot.send_message(chat_id, f"❌ Download failed: {e}")

# ================= POLLING ENGINE =================
if __name__ == "__main__":
    print("🚀 Bot initialized successfully and listening for events...")
    bot.infinity_polling(skip_pending=True)
