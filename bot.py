import telebot
import requests
from telebot.types import (
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice
)
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

CAPTION_TEXT = "Downloaded by:\n@Downloadvedioytibot"
channel_posts = {}

# ================= DATABASE FILES =================
USERS_FILE = "users.json"
WITHDRAWS_FILE = "withdraws.json"
VIDEOS_FILE = "videos.json"
PREMIUM_FILE = "premium.json"

# ================= JSON FUNCTIONS =================
def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving {path}: {e}")

# ================= LOAD & INITIALIZE DATA =================
users = load_json(USERS_FILE, {})
withdraws = load_json(WITHDRAWS_FILE, [])
videos_data = load_json(VIDEOS_FILE, {
    "total": 0,
    "platforms": {
        "tiktok": 0,
        "youtube": 0,
        "facebook": 0,
        "pinterest": 0,
        "snapchat": 0
    },
    "users": {}
})

premium_db = load_json(PREMIUM_FILE, {
    "plans": {
        "7_days": {"name": "⭐ 7 Days", "days": 7, "stars": 50, "enabled": True},
        "30_days": {"name": "⭐ 30 Days", "days": 30, "stars": 150, "enabled": True},
        "90_days": {"name": "⭐ 90 Days", "days": 90, "stars": 350, "enabled": True},
        "1_year": {"name": "⭐ 1 Year", "days": 365, "stars": 1000, "enabled": True}
    },
    "subscriptions": {},
    "payments": [],
    "referrals": {},
    "feature_requests": [],
    "coupons": {},
    "coupon_usage": {},
    "missions": {
        "download_10": {"title": "📥 Download 10 Files", "target": 10, "reward_type": "points", "reward_val": 50, "type": "download"},
        "invite_3": {"title": "🎁 Invite 3 Friends", "target": 3, "reward_type": "days", "reward_val": 2, "type": "invite"},
        "vote_3": {"title": "👍 Vote on 3 Requests", "target": 3, "reward_type": "points", "reward_val": 30, "type": "vote"}
    },
    "user_missions": {},
    "user_vip_identity": {},
    "download_history": {}
})

def save_users():
    save_json(USERS_FILE, users)

def save_withdraws():
    save_json(WITHDRAWS_FILE, withdraws)

def save_videos():
    save_json(VIDEOS_FILE, videos_data)

def save_premium():
    save_json(PREMIUM_FILE, premium_db)

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

# ================= PREMIUM CORE FUNCTIONS =================
def is_premium_user(uid):
    uid = str(uid)
    sub = premium_db.get("subscriptions", {}).get(uid)
    if not sub:
        return False
    if sub.get("status") != "ACTIVE":
        return False
    exp_str = sub.get("expiry_date")
    if not exp_str:
        return False
    try:
        exp_dt = datetime.strptime(exp_str, "%Y-%m-%d %H:%M:%S")
        if datetime.now() > exp_dt:
            sub["status"] = "EXPIRED"
            save_premium()
            return False
        return True
    except:
        return False

def get_premium_status(uid):
    uid = str(uid)
    if is_premium_user(uid):
        sub = premium_db["subscriptions"][uid]
        exp_dt = datetime.strptime(sub["expiry_date"], "%Y-%m-%d %H:%M:%S")
        days_left = max(0, (exp_dt - datetime.now()).days)
        return True, sub.get("plan", "Custom"), sub.get("expiry_date"), days_left
    return False, "FREE", "N/A", 0

def activate_premium(uid, plan_key, days, stars_paid=0, payment_id="MANUAL"):
    uid = str(uid)
    now = datetime.now()
    
    if uid in premium_db.get("subscriptions", {}) and is_premium_user(uid):
        curr_exp = datetime.strptime(premium_db["subscriptions"][uid]["expiry_date"], "%Y-%m-%d %H:%M:%S")
        new_exp = curr_exp + timedelta(days=days)
    else:
        new_exp = now + timedelta(days=days)
        
    premium_db.setdefault("subscriptions", {})[uid] = {
        "status": "ACTIVE",
        "plan": plan_key,
        "start_date": now.strftime("%Y-%m-%d %H:%M:%S"),
        "expiry_date": new_exp.strftime("%Y-%m-%d %H:%M:%S"),
        "stars_paid": stars_paid
    }
    
    premium_db.setdefault("payments", []).append({
        "user_id": uid,
        "plan": plan_key,
        "stars": stars_paid,
        "payment_id": payment_id,
        "date": now.strftime("%Y-%m-%d %H:%M:%S")
    })
    
    if uid not in premium_db.setdefault("user_vip_identity", {}):
        premium_db["user_vip_identity"][uid] = {
            "title": "⭐ VIP",
            "level": 1,
            "points": 100,
            "joined": now.strftime("%Y-%m-%d")
        }
    else:
        premium_db["user_vip_identity"][uid]["points"] = premium_db["user_vip_identity"][uid].get("points", 0) + 50
        
    save_premium()
    
    try:
        bot.send_message(
            int(uid),
            f"🎉 <b>PREMIUM ACTIVATED!</b>\n\n"
            f"Welcome to the VIP Club 👑\n"
            f"💎 Plan: {plan_key}\n"
            f"📅 Expires: {new_exp.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"⚡ Unlimited speeds, high limits & VIP perks unlocked!"
        )
    except:
        pass

def remove_premium(uid):
    uid = str(uid)
    if uid in premium_db.get("subscriptions", {}):
        premium_db["subscriptions"][uid]["status"] = "REMOVED"
        save_premium()
        return True
    return False

def add_user_points(uid, pts):
    uid = str(uid)
    identity = premium_db.setdefault("user_vip_identity", {}).setdefault(uid, {
        "title": "⭐ VIP" if is_premium_user(uid) else "FREE",
        "level": 1,
        "points": 0,
        "joined": datetime.now().strftime("%Y-%m-%d")
    })
    identity["points"] = identity.get("points", 0) + pts
    identity["level"] = 1 + (identity["points"] // 200)
    save_premium()

def track_mission_progress(uid, m_type, increment=1):
    uid = str(uid)
    user_m = premium_db.setdefault("user_missions", {}).setdefault(uid, {})
    
    for m_id, m_data in premium_db.get("missions", {}).items():
        if m_data.get("type") == m_type:
            prog = user_m.get(m_id, {"progress": 0, "claimed": False})
            if not prog["claimed"]:
                prog["progress"] += increment
                user_m[m_id] = prog
    save_premium()

# ================= MENUS =================
def user_menu(show_admin=False):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📥 Downloader", "👑 PREMIUM")
    kb.add("💰 BALANCE", "💸 WITHDRAWAL")
    kb.add("👥 REFERRAL", "🆔 GET ID")
    kb.add("⚙️ Settings", "📊 Statistics")
    kb.add("☎️ CUSTOMER", "🤖CUSTOMER AI")
    if show_admin:
        kb.add("👑 ADMIN PANEL")
    return kb

def admin_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("👨‍💼 PREMIUM CONTROL", "📊 STATS")
    kb.add("📢 BROADCAST", "💳 WITHDRAWAL CHECK")
    kb.add("➕ ADD BALANCE", "➖ REMOVE MONEY")
    kb.add("🚫 BAN USER MANUAL", "🔥 UN BAN-USER")
    kb.add("💰 UNBLOCK MONEY", "🔍 RAADI")
    kb.add("📌 POST CHANNEL", "👥 SEE LIST")
    kb.add("🔎 SEARCH USER", "📢 ADD ADS")
    kb.add("🗑 DELETE ADS", "✅ VERIFY ON")
    kb.add("❌ VERIFY OFF", "CHANNEL POST")
    kb.add("📡 ADD CHANNEL", "🔒 LOCK BOT")
    kb.add("🔓 UNLOCK BOT", "❌ CLOSE WINDOWS")
    kb.add("CLOSE CHANNEL POST", "📥 IMPORT USERS")
    kb.add("🔗 GET REFERRAL CODE", "🔙 BACK MAIN MENU")
    return kb

def premium_center_markup(uid):
    kb = InlineKeyboardMarkup(row_width=2)
    is_vip = is_premium_user(uid)
    
    kb.add(
        InlineKeyboardButton("⭐ BUY PREMIUM", callback_data="vip_buy_plans"),
        InlineKeyboardButton("💎 MY PLAN", callback_data="vip_my_plan")
    )
    kb.add(
        InlineKeyboardButton("🎁 INVITE", callback_data="vip_referral"),
        InlineKeyboardButton("💡 REQUESTS", callback_data="vip_requests")
    )
    kb.add(
        InlineKeyboardButton("🏆 LEADERBOARD", callback_data="vip_leaderboard"),
        InlineKeyboardButton("🎯 MISSIONS", callback_data="vip_missions")
    )
    kb.add(
        InlineKeyboardButton("🎟 COUPONS", callback_data="vip_coupons"),
        InlineKeyboardButton("🎁 GIFT", callback_data="vip_gift")
    )
    kb.add(
        InlineKeyboardButton("👑 VIP IDENTITY", callback_data="vip_identity"),
        InlineKeyboardButton("📊 STATISTICS", callback_data="vip_stats")
    )
    kb.add(
        InlineKeyboardButton("🏠 HOME", callback_data="vip_home")
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

@bot.message_handler(func=lambda m: m.text == "🔙 BACK MAIN MENU")
def back_button_handler(m):
    back_to_main_menu(m)

@bot.message_handler(func=lambda m: m.text == "📥 Downloader")
def downloader_menu_handler(m):
    bot.send_message(m.chat.id, "📥 <b>Send any supported video link</b> (TikTok, YouTube, Snapchat, Pinterest, etc.) to start downloading!")

# ================= START HANDLER =================
@bot.message_handler(commands=['start'])
def start_handler(message):
    if bot_locked_guard(message):
        return

    uid = str(message.from_user.id)
    args = message.text.split()

    if uid not in users:
        ref = args[1] if len(args) > 1 else None
        
        # Check deep link start parameter for custom start links
        if ref and ref.startswith("ref_"):
            ref = ref.replace("ref_", "")

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
        
        if ref:
            ref_user = next((u for u, d in users.items() if d["ref"] == ref or u == ref), None)
            if ref_user and ref_user != uid:
                users[ref_user]["balance"] += 0.2
                users[ref_user]["invited"] += 1
                save_users()
                
                track_mission_progress(ref_user, "invite", 1)
                add_user_points(ref_user, 10)
                
                try:
                    bot.send_message(int(ref_user), "🎉 You earned $0.2 & 10 VIP Points from a referral!")
                except:
                    pass

        save_users()

    check_membership(message.from_user.id)

@bot.message_handler(commands=['view'])
def view_cmd(message):
    bot.send_message(
        message.chat.id,
        "🤖 <b>BOT INFO</b>\n\n"
        "📌 Name: Video Downloader Bot\n"
        "⚡ Features:\n"
        "• TikTok download\n"
        "• YouTube download\n"
        "• Facebook download\n"
        "• Snapchat & Pinterest download\n"
        "• Referral system\n"
        "• VIP / Premium System\n"
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
    bot.send_message(
        m.chat.id,
        f"🔗 Your referral link:\n{link}\n\n"
        "Earn money and VIP rewards by inviting friends!"
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
        f"⚡ Speed: {speed} ms\n"
        f"📡 Status: {status}",
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
            InlineKeyboardButton(
                "GET",
                url="https://t.me/Downloadvedioytibot"
            )
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
            bot.send_message(
                user_id,
                """🎬 <b>Welcome to Video Downloader Bot!</b>

This bot helps you easily download videos and music from many popular platforms directly to Telegram.

With this bot you can download content from platforms like:
• TikTok
• Instagram
• Facebook
• Pinterest
• Snapchat
• YouTube

📥 <b>How to use the bot:</b>
1. Copy the video link from any supported platform.
2. Send the link here in the bot.
3. The bot will automatically download the video for you.

⚡ <b>VIP Features & Rewards</b>
Upgrade to VIP for max speeds, priority, missions, and rewards!

👇 Send any video link to begin downloading.""",
                reply_markup=user_menu(is_admin(user_id))
            )
        else:
            send_join_message(user_id)
    except:
        send_join_message(user_id)

def send_join_message(user_id):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("➕ JOIN CHANNEL", url="https://t.me/tiktokvediodownload")
    )
    kb.add(
        InlineKeyboardButton("✅ CONFIRM", callback_data="confirm_join")
    )
    bot.send_message(
        user_id,
        "⚠️ You must join our channel to use this bot.",
        reply_markup=kb
    )

# ================= PREMIUM CENTER & INTERACTION =================
@bot.message_handler(func=lambda m: m.text in ["👑 PREMIUM", "👑 Premium", "/premium"])
def open_premium_center(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    
    uid = str(m.from_user.id)
    is_vip, plan_name, expiry, days_left = get_premium_status(uid)
    
    if is_vip:
        msg = (
            "╭━━━━━━━━━━━━━━━━━━━━━━╮\n"
            "       👑 <b>PREMIUM VIP CENTER</b>\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
            "⭐ <b>STATUS:</b> <code>ACTIVE</code> 🟢\n"
            f"💎 <b>PLAN:</b> {plan_name}\n"
            f"📅 <b>EXPIRES:</b> {expiry}\n"
            f"⏳ <b>DAYS LEFT:</b> {days_left} Days\n\n"
            "✨ <i>Welcome to your exclusive VIP portal! Enjoy priority processing and max speeds.</i>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
    else:
        msg = (
            "╭━━━ 👑 <b>GO PREMIUM VIP</b> ━━━╮\n\n"
            "🚀 <b>Unlock powerful VIP features today!</b>\n\n"
            "⚡ <b>Priority Processing</b> — Zero wait times\n"
            "📥 <b>Higher Usage Limits</b> — Download without restrictions\n"
            "🎁 <b>Exclusive Referral Rewards</b> — Bonus stars & perks\n"
            "🏆 <b>VIP Ranking</b> — High status badge\n"
            "🎯 <b>VIP Missions</b> — Earn points & extra days\n"
            "💡 <b>Feature Voting</b> — Request direct bot upgrades\n"
            "🎟 <b>Exclusive Coupons</b> — Special discounts\n"
            "👑 <b>Custom VIP Identity</b> — Stand out\n\n"
            "Ready to upgrade your experience?\n"
            "╰━━━━━━━━━━━━━━━━━━━━╯"
        )
        
    bot.send_message(m.chat.id, msg, reply_markup=premium_center_markup(m.from_user.id))

@bot.callback_query_handler(func=lambda c: c.data.startswith("vip_"))
def handle_vip_callbacks(call):
    uid = str(call.from_user.id)
    action = call.data
    
    if action == "vip_home":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        open_premium_center(call.message)
        return

    elif action == "vip_buy_plans":
        kb = InlineKeyboardMarkup(row_width=1)
        plans = premium_db.get("plans", {})
        
        for k, v in plans.items():
            if v.get("enabled", True):
                kb.add(InlineKeyboardButton(
                    f"{v['name']} — ⭐ {v['stars']} Stars",
                    callback_data=f"vip_pay_{k}"
                ))
        kb.add(InlineKeyboardButton("🔙 BACK", callback_data="vip_home"))
        
        bot.edit_message_text(
            "╭━━━ ⭐ <b>CHOOSE YOUR VIP PLAN</b> ━━━╮\n\n"
            "Pay securely using <b>Telegram Stars</b>:\n\n"
            "⚡ Instant Activation\n"
            "🔒 100% Guaranteed Verification\n\n"
            "Select a plan below:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb
        )

    elif action.startswith("vip_pay_"):
        plan_key = action.replace("vip_pay_", "")
        plan = premium_db.get("plans", {}).get(plan_key)
        
        if not plan or not plan.get("enabled"):
            bot.answer_callback_query(call.id, "❌ Plan unavailable", show_alert=True)
            return

        prices = [LabeledPrice(label=plan["name"], amount=plan["stars"])]
        
        try:
            bot.send_invoice(
                call.message.chat.id,
                title=f"VIP Membership - {plan['name']}",
                description=f"Unlock all VIP Features on Downloader Bot for {plan['days']} Days.",
                invoice_payload=f"vip_payload_{plan_key}_{uid}",
                provider_token="", # Empty for Telegram Stars
                currency="XTR",
                prices=prices,
                start_parameter=f"vip_{plan_key}"
            )
            bot.answer_callback_query(call.id, "💳 Payment invoice sent!")
        except Exception as e:
            bot.answer_callback_query(call.id, f"Error: {e}", show_alert=True)

    elif action == "vip_my_plan":
        is_vip, plan_name, expiry, days_left = get_premium_status(uid)
        identity = premium_db.get("user_vip_identity", {}).get(uid, {})
        title = identity.get("title", "FREE")
        
        text = (
            f"╭━━━ 💎 <b>YOUR PLAN DETAILS</b> ━━━╮\n\n"
            f"👤 <b>User:</b> <a href='tg://user?id={uid}'>{uid}</a>\n"
            f"👑 <b>Status:</b> {'ACTIVE 🟢' if is_vip else 'FREE ⚪'}\n"
            f"🏷 <b>Title:</b> {title}\n"
            f"💎 <b>Current Plan:</b> {plan_name}\n"
            f"📅 <b>Expires:</b> {expiry}\n"
            f"⏳ <b>Days Left:</b> {days_left}\n\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯"
        )
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 BACK", callback_data="vip_home"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif action == "vip_referral":
        bot_username = bot.get_me().username
        ref_code = users.get(uid, {}).get("ref", uid)
        ref_link = f"https://t.me/{bot_username}?start=ref_{ref_code}"
        invited = users.get(uid, {}).get("invited", 0)
        
        text = (
            "╭━━━ 🎁 <b>INVITE & EARN VIP</b> ━━━╮\n\n"
            f"👥 <b>Your Referrals:</b> {invited}\n"
            f"🔗 <b>Your Link:</b>\n<code>{ref_link}</code>\n\n"
            "🏆 <b>Milestones & Rewards:</b>\n"
            "• 3 Referrals: 30 VIP Points\n"
            "• 10 Referrals: 100 VIP Points\n"
            "• 25 Referrals: 3 Days Free VIP\n\n"
            "Share your link and get rewarded!"
        )
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(
            InlineKeyboardButton("📤 SHARE LINK", url=f"https://t.me/share/url?url={ref_link}&text=Join%20the%20best%20downloader%20bot!"),
            InlineKeyboardButton("🔙 BACK", callback_data="vip_home")
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif action == "vip_requests":
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("💡 SUBMIT REQUEST", callback_data="vip_req_submit"),
            InlineKeyboardButton("🔥 TOP REQUESTS", callback_data="vip_req_top")
        )
        kb.add(InlineKeyboardButton("🔙 BACK", callback_data="vip_home"))
        
        bot.edit_message_text(
            "╭━━━ 💡 <b>FEATURE REQUESTS</b> ━━━╮\n\n"
            "Premium Users can directly request and vote on new bot features!\n\n"
            "Vote for features you want implemented next.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb
        )

    elif action == "vip_req_top":
        reqs = premium_db.get("feature_requests", [])
        if not reqs:
            bot.answer_callback_query(call.id, "No feature requests yet!", show_alert=True)
            return
            
        reqs_sorted = sorted(reqs, key=lambda x: len(x.get("votes", [])), reverse=True)[:5]
        text = "╭━━━ 🔥 <b>MOST REQUESTED FEATURES</b> ━━━╮\n\n"
        
        kb = InlineKeyboardMarkup(row_width=1)
        for idx, r in enumerate(reqs_sorted, start=1):
            votes_cnt = len(r.get("votes", []))
            text += f"{idx}️⃣ <b>{r['title']}</b>\n status: {r['status']} | 👍 {votes_cnt} votes\n\n"
            kb.add(InlineKeyboardButton(f"👍 Vote for #{r['id']} ({r['title'][:15]}...)", callback_data=f"vip_vote_{r['id']}"))
            
        kb.add(InlineKeyboardButton("🔙 BACK", callback_data="vip_requests"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif action.startswith("vip_vote_"):
        if not is_premium_user(uid):
            bot.answer_callback_query(call.id, "🔒 Premium Users Only!", show_alert=True)
            return
        
        req_id = int(action.replace("vip_vote_", ""))
        reqs = premium_db.get("feature_requests", [])
        target = next((r for r in reqs if r["id"] == req_id), None)
        
        if target:
            if uid in target.setdefault("votes", []):
                bot.answer_callback_query(call.id, "⚠️ You already voted for this!", show_alert=True)
            else:
                target["votes"].append(uid)
                save_premium()
                track_mission_progress(uid, "vote", 1)
                add_user_points(uid, 5)
                bot.answer_callback_query(call.id, "✅ Vote counted! +5 Points")
                bot.delete_message(call.message.chat.id, call.message.message_id)
                open_premium_center(call.message)

    elif action == "vip_req_submit":
        if not is_premium_user(uid):
            bot.answer_callback_query(call.id, "🔒 Premium Users Only!", show_alert=True)
            return
            
        msg = bot.send_message(call.message.chat.id, "💡 Send title and description for feature request:\nFormat: <code>Title | Description</code>")
        bot.register_next_step_handler(msg, process_feature_submit)

    elif action == "vip_leaderboard":
        identities = premium_db.get("user_vip_identity", {})
        sorted_users = sorted(identities.items(), key=lambda x: x[1].get("points", 0), reverse=True)[:10]
        
        text = "╭━━━ 🏆 <b>VIP LEADERBOARD</b> ━━━╮\n\n"
        for idx, (u_id, u_data) in enumerate(sorted_users, start=1):
            badge = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}️⃣"
            text += f"{badge} <a href='tg://user?id={u_id}'>{u_id}</a> — <b>{u_data.get('points', 0)} Pts</b> ({u_data.get('title', 'VIP')})\n"
            
        my_pts = identities.get(uid, {}).get("points", 0)
        text += f"\n━━━━━━━━━━━━━━━━━━━━\n⭐ <b>YOU:</b> {my_pts} Points"
        
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 BACK", callback_data="vip_home"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif action == "vip_missions":
        user_m = premium_db.setdefault("user_missions", {}).setdefault(uid, {})
        missions = premium_db.get("missions", {})
        
        text = "╭━━━ 🎯 <b>VIP MISSIONS</b> ━━━╮\n\n"
        kb = InlineKeyboardMarkup(row_width=1)
        
        for m_id, m_data in missions.items():
            u_prog = user_m.get(m_id, {"progress": 0, "claimed": False})
            prog_val = min(u_prog["progress"], m_data["target"])
            pct = int((prog_val / m_data["target"]) * 10)
            bar = "█" * pct + "░" * (10 - pct)
            
            status_str = "✅ Completed" if u_prog["claimed"] else f"{prog_val}/{m_data['target']}"
            text += f"📌 <b>{m_data['title']}</b>\n{bar} {status_str}\nReward: +{m_data['reward_val']} {m_data['reward_type'].upper()}\n\n"
            
            if prog_val >= m_data["target"] and not u_prog["claimed"]:
                kb.add(InlineKeyboardButton(f"🎁 Claim {m_data['title']}", callback_data=f"vip_claim_m_{m_id}"))
                
        kb.add(InlineKeyboardButton("🔙 BACK", callback_data="vip_home"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif action.startswith("vip_claim_m_"):
        m_id = action.replace("vip_claim_m_", "")
        user_m = premium_db.setdefault("user_missions", {}).setdefault(uid, {})
        m_data = premium_db.get("missions", {}).get(m_id)
        
        if m_data and user_m.get(m_id, {}).get("progress", 0) >= m_data["target"]:
            if not user_m[m_id].get("claimed"):
                user_m[m_id]["claimed"] = True
                if m_data["reward_type"] == "points":
                    add_user_points(uid, m_data["reward_val"])
                elif m_data["reward_type"] == "days":
                    activate_premium(uid, "MISSION_REWARD", m_data["reward_val"])
                save_premium()
                bot.answer_callback_query(call.id, f"🎉 Reward claimed! +{m_data['reward_val']} {m_data['reward_type']}", show_alert=True)
                bot.delete_message(call.message.chat.id, call.message.message_id)
                open_premium_center(call.message)

    elif action == "vip_coupons":
        msg = bot.send_message(call.message.chat.id, "🎟 <b>Enter your Promo / Coupon Code:</b>")
        bot.register_next_step_handler(msg, process_coupon_redeem)

    elif action == "vip_gift":
        msg = bot.send_message(call.message.chat.id, "🎁 <b>Enter recipient Telegram User ID or Username:</b>")
        bot.register_next_step_handler(msg, process_gift_user_step)

    elif action == "vip_identity":
        ident = premium_db.get("user_vip_identity", {}).get(uid, {
            "title": "⭐ VIP" if is_premium_user(uid) else "FREE",
            "level": 1,
            "points": 0,
            "joined": datetime.now().strftime("%Y-%m-%d")
        })
        text = (
            f"╭━━━ 👑 <b>VIP IDENTITY PROFILE</b> ━━━╮\n\n"
            f"👤 <b>User:</b> <a href='tg://user?id={uid}'>{uid}</a>\n"
            f"💎 <b>TITLE:</b> {ident.get('title', 'VIP')}\n"
            f"🔥 <b>LEVEL:</b> {ident.get('level', 1)}\n"
            f"🏆 <b>POINTS:</b> {ident.get('points', 0)}\n"
            f"📅 <b>MEMBER SINCE:</b> {ident.get('joined', 'N/A')}\n\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯"
        )
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 BACK", callback_data="vip_home"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif action == "vip_stats":
        v_data = videos_data.get("users", {}).get(uid, 0)
        u_ref = users.get(uid, {}).get("invited", 0)
        ident = premium_db.get("user_vip_identity", {}).get(uid, {})
        is_vip, _, _, days_left = get_premium_status(uid)
        
        text = (
            f"╭━━━ 📊 <b>MY PERSONAL STATS</b> ━━━╮\n\n"
            f"📥 <b>Downloads:</b> {v_data}\n"
            f"🎁 <b>Referrals:</b> {u_ref}\n"
            f"🏆 <b>VIP Points:</b> {ident.get('points', 0)}\n"
            f"⭐ <b>VIP Active:</b> {'YES (' + str(days_left) + ' Days Left)' if is_vip else 'NO'}\n\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯"
        )
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 BACK", callback_data="vip_home"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

def process_feature_submit(m):
    uid = str(m.from_user.id)
    text = m.text or ""
    if "|" not in text:
        bot.send_message(m.chat.id, "❌ Invalid format. Use: <code>Title | Description</code>")
        return
    title, desc = text.split("|", 1)
    reqs = premium_db.setdefault("feature_requests", [])
    new_id = len(reqs) + 1
    reqs.append({
        "id": new_id,
        "user_id": uid,
        "title": title.strip(),
        "description": desc.strip(),
        "votes": [uid],
        "status": "🟡 Pending"
    })
    save_premium()
    bot.send_message(m.chat.id, f"✅ <b>Feature Request Submitted!</b> (ID: #{new_id})")

def process_coupon_redeem(m):
    uid = str(m.from_user.id)
    code = (m.text or "").strip().upper()
    coupons = premium_db.get("coupons", {})
    
    if code not in coupons:
        bot.send_message(m.chat.id, "❌ Invalid Coupon Code.")
        return
        
    c = coupons[code]
    if not c.get("active", True):
        bot.send_message(m.chat.id, "❌ Coupon is inactive.")
        return
        
    if c.get("uses", 0) >= c.get("max_uses", 999999):
        bot.send_message(m.chat.id, "❌ Coupon usage limit reached.")
        return
        
    used_list = premium_db.setdefault("coupon_usage", {}).setdefault(code, [])
    if uid in used_list:
        bot.send_message(m.chat.id, "⚠️ You have already redeemed this coupon.")
        return
        
    used_list.append(uid)
    c["uses"] = c.get("uses", 0) + 1
    
    # Reward application
    r_type = c.get("reward_type")
    r_val = c.get("reward_value", 0)
    
    if r_type == "premium_days":
        activate_premium(uid, f"COUPON_{code}", int(r_val))
        res_msg = f"🎉 Redeemed! Received {r_val} Premium Days."
    elif r_type == "points":
        add_user_points(uid, int(r_val))
        res_msg = f"🎉 Redeemed! Received {r_val} VIP Points."
    elif r_type == "balance":
        users[uid]["balance"] += float(r_val)
        save_users()
        res_msg = f"🎉 Redeemed! ${r_val} added to your balance."
    else:
        res_msg = "✅ Coupon redeemed successfully."
        
    save_premium()
    bot.send_message(m.chat.id, res_msg)

def process_gift_user_step(m):
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
        bot.send_message(m.chat.id, "❌ Target user not found in bot database.")
        return
        
    kb = InlineKeyboardMarkup(row_width=1)
    plans = premium_db.get("plans", {})
    for k, v in plans.items():
        if v.get("enabled", True):
            kb.add(InlineKeyboardButton(f"🎁 Gift {v['name']} ({v['stars']} Stars)", callback_data=f"gift_pay_{k}_{target_uid}"))
            
    bot.send_message(m.chat.id, f"🎁 Select VIP plan to gift to user <b>{target_uid}</b>:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("gift_pay_"))
def handle_gift_payment(call):
    parts = call.data.split("_")
    plan_key = parts[2]
    target_uid = parts[3]
    
    plan = premium_db.get("plans", {}).get(plan_key)
    if not plan:
        bot.answer_callback_query(call.id, "❌ Plan error")
        return
        
    prices = [LabeledPrice(label=f"GIFT: {plan['name']}", amount=plan["stars"])]
    bot.send_invoice(
        call.message.chat.id,
        title=f"Gift VIP - {plan['name']}",
        description=f"Gift VIP access to Telegram user ID {target_uid}",
        invoice_payload=f"gift_payload_{plan_key}_{target_uid}_{call.from_user.id}",
        provider_token="",
        currency="XTR",
        prices=prices,
        start_parameter=f"gift_{plan_key}"
    )

# ================= TELEGRAM STARS PAYMENT VERIFICATION =================
@bot.pre_checkout_query_handler(func=lambda query: True)
def process_pre_checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def process_successful_payment(message):
    pmt = message.successful_payment
    payload = pmt.invoice_payload
    stars_amount = pmt.total_amount
    
    if payload.startswith("vip_payload_"):
        parts = payload.split("_")
        plan_key = parts[2]
        uid = parts[3]
        
        plan_days = premium_db.get("plans", {}).get(plan_key, {}).get("days", 30)
        activate_premium(uid, plan_key, plan_days, stars_paid=stars_amount, payment_id=pmt.telegram_payment_charge_id)
        
    elif payload.startswith("gift_payload_"):
        parts = payload.split("_")
        plan_key = parts[2]
        target_uid = parts[3]
        sender_uid = parts[4]
        
        plan_days = premium_db.get("plans", {}).get(plan_key, {}).get("days", 30)
        activate_premium(target_uid, f"GIFT_{plan_key}", plan_days, stars_paid=stars_amount, payment_id=pmt.telegram_payment_charge_id)
        
        try:
            bot.send_message(
                int(target_uid),
                f"╭━━━ 🎁 <b>PREMIUM GIFT RECEIVED!</b> ━━━╮\n\n"
                f"🎉 You received a VIP Gift from user {sender_uid}!\n"
                f"💎 <b>PLAN:</b> {plan_days} Days VIP\n\n"
                "Enjoy your VIP experience! 👑\n"
                "╰━━━━━━━━━━━━━━━━━━━━━━╯"
            )
        except:
            pass
        bot.send_message(message.chat.id, f"✅ Gift payment confirmed! {plan_days} Days VIP granted to target user.")

# ================= USER SETTINGS & STATS HANDLERS =================
@bot.message_handler(func=lambda m: m.text in ["⚙️ Settings", "⚙️ SETTINGS"])
def user_settings_handler(m):
    if banned_guard(m): return
    uid = str(m.from_user.id)
    is_vip = is_premium_user(uid)
    
    text = (
        "╭━━━ ⚙️ <b>USER SETTINGS</b> ━━━╮\n\n"
        f"👑 <b>VIP Status:</b> {'ACTIVE 🟢' if is_vip else 'FREE ⚪'}\n\n"
        "Configure your personal downloader preferences below:"
    )
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🎵 Preferred Audio Format", callback_data="cfg_audio"),
        InlineKeyboardButton("🎬 Video Quality", callback_data="cfg_quality")
    )
    bot.send_message(m.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("cfg_"))
def handle_cfg(call):
    bot.answer_callback_query(call.id, "⚙️ Settings saved successfully!")

@bot.message_handler(func=lambda m: m.text in ["📊 Statistics", "📊 STATISTICS"])
def user_stats_menu(m):
    if banned_guard(m): return
    uid = str(m.from_user.id)
    v_cnt = videos_data.get("users", {}).get(uid, 0)
    bal = users.get(uid, {}).get("balance", 0.0)
    ref = users.get(uid, {}).get("invited", 0)
    is_vip, plan_name, _, days_left = get_premium_status(uid)
    
    msg = (
        f"╭━━━ 📊 <b>YOUR ACCOUNT STATS</b> ━━━╮\n\n"
        f"👤 <b>User ID:</b> <code>{uid}</code>\n"
        f"💰 <b>Balance:</b> ${bal:.2f}\n"
        f"👥 <b>Referrals:</b> {ref}\n"
        f"🎬 <b>Downloaded Videos:</b> {v_cnt}\n"
        f"👑 <b>VIP Plan:</b> {plan_name} ({days_left} Days Left)\n\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━╯"
    )
    bot.send_message(m.chat.id, msg)

# ================= ADMIN PANEL & CONTROL =================
@bot.message_handler(func=lambda m: m.text == "👑 ADMIN PANEL")
def open_admin_panel(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ You are not admin")
        return
    bot.send_message(m.chat.id, "👑 <b>Admin Control Panel</b>", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == "👨‍💼 PREMIUM CONTROL")
def admin_premium_control_menu(m):
    if not is_admin(m.from_user.id): return
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("👤 Search / Manage VIP User", callback_data="adm_vip_search"),
        InlineKeyboardButton("🎟 Create Coupon", callback_data="adm_vip_coupon_create")
    )
    kb.add(
        InlineKeyboardButton("📊 Premium Analytics", callback_data="adm_vip_analytics"),
        InlineKeyboardButton("⚙️ Configure Plan Prices", callback_data="adm_vip_plans_cfg")
    )
    bot.send_message(m.chat.id, "👨‍💼 <b>ADVANCED ADMIN PREMIUM CONTROL SUITE</b>", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_vip_"))
def handle_admin_vip_actions(call):
    if not is_admin(call.from_user.id): return
    act = call.data
    
    if act == "adm_vip_search":
        msg = bot.send_message(call.message.chat.id, "👤 Enter Telegram User ID or @Username to manage:")
        bot.register_next_step_handler(msg, process_admin_user_search)
        
    elif act == "adm_vip_analytics":
        subs = premium_db.get("subscriptions", {})
        active_cnt = sum(1 for s in subs.values() if s.get("status") == "ACTIVE")
        pmts = premium_db.get("payments", [])
        total_stars = sum(p.get("stars", 0) for p in pmts)
        
        msg = (
            "╭━━━ 📊 <b>PREMIUM ANALYTICS</b> ━━━╮\n\n"
            f"👑 <b>Active VIP Members:</b> {active_cnt}\n"
            f" Total Subscriptions Recorded: {len(subs)}\n"
            f"⭐ <b>Total Stars Earned:</b> {total_stars} Stars\n"
            f"💡 <b>Feature Requests:</b> {len(premium_db.get('feature_requests', []))}\n\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯"
        )
        bot.send_message(call.message.chat.id, msg)
        
    elif act == "adm_vip_coupon_create":
        msg = bot.send_message(
            call.message.chat.id,
            "🎟 <b>Create Coupon Code:</b>\nFormat: <code>CODE | TYPE | VALUE | MAX_USES</code>\n\nTypes: <code>premium_days</code>, <code>points</code>, <code>balance</code>\nExample: <code>VIP30 | premium_days | 30 | 100</code>"
        )
        bot.register_next_step_handler(msg, process_admin_coupon_create)

def process_admin_user_search(m):
    target = (m.text or "").strip().replace("@", "")
    target_uid = target if target.isdigit() and target in users else None
    
    if not target_uid:
        for u, d in users.items():
            if d.get("username", "").lower() == target.lower():
                target_uid = u
                break
                
    if not target_uid:
        bot.send_message(m.chat.id, "❌ User not found.")
        return
        
    is_vip, plan_name, exp, days_left = get_premium_status(target_uid)
    
    text = (
        f"╭━━━ 👤 <b>MANAGEMENT PROFILE</b> ━━━╮\n\n"
        f"👤 <b>Username:</b> @{users.get(target_uid, {}).get('username', 'N/A')}\n"
        f"🆔 <b>User ID:</b> <code>{target_uid}</code>\n"
        f"⭐ <b>VIP Status:</b> {'ACTIVE' if is_vip else 'INACTIVE'}\n"
        f"💎 <b>Plan:</b> {plan_name}\n"
        f"⏰ <b>Expires:</b> {exp} ({days_left} Days Left)\n\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━╯"
    )
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("👑 GIVE VIP", callback_data=f"adm_give_vip_{target_uid}"),
        InlineKeyboardButton("❌ REMOVE VIP", callback_data=f"adm_rem_vip_{target_uid}")
    )
    kb.add(
        InlineKeyboardButton("➕ EXTEND 30 DAYS", callback_data=f"adm_ext_vip_{target_uid}_30"),
        InlineKeyboardButton("🏷 CHANGE TITLE", callback_data=f"adm_title_vip_{target_uid}")
    )
    bot.send_message(m.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith(("adm_give_vip_", "adm_rem_vip_", "adm_ext_vip_", "adm_title_vip_")))
def handle_admin_user_edits(call):
    if not is_admin(call.from_user.id): return
    data = call.data
    
    if data.startswith("adm_give_vip_"):
        uid = data.replace("adm_give_vip_", "")
        activate_premium(uid, "ADMIN_GIFT", 30)
        bot.answer_callback_query(call.id, "✅ Granted 30 Days VIP", show_alert=True)
        
    elif data.startswith("adm_rem_vip_"):
        uid = data.replace("adm_rem_vip_", "")
        remove_premium(uid)
        bot.answer_callback_query(call.id, "❌ Premium removed", show_alert=True)
        
    elif data.startswith("adm_ext_vip_"):
        parts = data.split("_")
        uid = parts[3]
        days = int(parts[4])
        activate_premium(uid, "EXTENSION", days)
        bot.answer_callback_query(call.id, f"✅ Extended {days} days", show_alert=True)
        
    elif data.startswith("adm_title_vip_"):
        uid = data.replace("adm_title_vip_", "")
        msg = bot.send_message(call.message.chat.id, "Enter new title for user (e.g. ⭐ VIP, 💎 PRO, 🔥 LEGEND):")
        bot.register_next_step_handler(msg, lambda m: set_custom_title(m, uid))

def set_custom_title(m, uid):
    title = (m.text or "").strip()
    premium_db.setdefault("user_vip_identity", {}).setdefault(uid, {})["title"] = title
    save_premium()
    bot.send_message(m.chat.id, f"✅ VIP Title updated to '{title}' for user {uid}")

def process_admin_coupon_create(m):
    try:
        parts = [p.strip() for p in m.text.split("|")]
        code = parts[0].upper()
        r_type = parts[1]
        r_val = float(parts[2])
        max_u = int(parts[3])
        
        premium_db.setdefault("coupons", {})[code] = {
            "reward_type": r_type,
            "reward_value": r_val,
            "max_uses": max_u,
            "uses": 0,
            "active": True
        }
        save_premium()
        bot.send_message(m.chat.id, f"✅ Coupon <b>{code}</b> created successfully!")
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Error creating coupon: {e}")

# ================= EXISTING ADMIN FUNCTIONS =================
@bot.message_handler(func=lambda m: m.text == "💰 BALANCE")
def balance_handler(m):
    if bot_locked_guard(m) or banned_guard(m): return
    uid = str(m.from_user.id)
    bal = users[uid].get("balance", 0.0)
    blocked = users[uid].get("blocked", 0.0)
    bot.send_message(m.chat.id, f"💰 Available Balance: ${bal:.2f}\n⏳ Blocked Amount: ${blocked:.2f}")

@bot.message_handler(func=lambda m: m.text == "🆔 GET ID")
def get_id_handler(m):
    if bot_locked_guard(m) or banned_guard(m): return
    uid = str(m.from_user.id)
    bot.send_message(m.chat.id, f"🆔 BOT ID: <code>{users[uid]['bot_id']}</code>\n👤 Telegram ID: <code>{uid}</code>")

@bot.message_handler(func=lambda m: m.text == "👥 REFERRAL")
def referral_handler(m):
    if bot_locked_guard(m) or banned_guard(m): return
    uid = str(m.from_user.id)
    bot_username = bot.get_me().username
    link = f"https://t.me/{bot_username}?start={users[uid]['ref']}"
    invited = users[uid].get("invited", 0)
    bot.send_message(m.chat.id, f"🔗 Your Referral Link:\n{link}\n\n👥 Invited Users: {invited}\n🎁 You earn $0.2 per referral!")

@bot.message_handler(func=lambda m: m.text == "☎️ CUSTOMER")
def customer_handler(m):
    if bot_locked_guard(m) or banned_guard(m): return
    bot.send_message(m.chat.id, "☎️ Customer Support:\n@scholes1")

@bot.message_handler(func=lambda m: m.text == "🤖CUSTOMER AI")
def customer_ai_handler(m):
    if bot_locked_guard(m) or banned_guard(m): return
    bot.send_message(m.chat.id, "Ai Customer Support🤖:\n@Aidownoaderbot")

@bot.message_handler(func=lambda m: m.text == "💸 WITHDRAWAL")
def withdraw_menu(m):
    if banned_guard(m): return
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("USDT-BEP20", "🔙 CANCEL")
    bot.send_message(m.chat.id, "Select withdrawal method:", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text in ["USDT-BEP20", "🔙 CANCEL"])
def withdraw_method(m):
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
        f"✅ Withdrawal Request Sent\n🧾 Request ID: {wid}\n💵 Amount: ${amt:.2f}\n🏦 Address: {withdrawal['address']}\n💰 Balance Left: ${users[uid]['balance']:.2f}\n⏳ Status: Pending"
    )

    admin_text = (
        f"💳 NEW WITHDRAWAL\n\n👤 User: {uid}\n🤖 BOT ID: {users[uid]['bot_id']}\n👥 Referrals: {users[uid]['invited']}\n💵 Amount: ${amt:.2f}\n🧾 Request ID: {wid}\n🏦 Address: {withdrawal['address']}\n⏳ Status: Pending"
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
    msg_text = (
        f"💳 WITHDRAWAL DETAILS\n\n🧾 Request ID: {w['id']}\n👤 User ID: {uid}\n🤖 BOT ID: {bot_id}\n👥 Referrals: {invited}\n💵 Amount: ${w['amount']:.2f}\n🏦 Address: {w['address']}\n📊 Status: {w['status'].upper()}\n⏰ Time: {w['time']}"
    )
    bot.send_message(m.chat.id, msg_text)

@bot.message_handler(func=lambda m: m.text == "📊 STATS")
def stats_handler(m):
    if not is_admin(m.from_user.id): return
    total_users = len(users)
    total_balance = sum(u.get("balance", 0.0) for u in users.values())
    total_blocked = sum(u.get("blocked", 0.0) for u in users.values())
    total_withdraws = len(withdraws)
    pending_withdraws = len([w for w in withdraws if w["status"] == "pending"])
    
    msg = (
        f"📊 BOT STATS\n\n👥 Total Users: {total_users}\n💰 Total Balance: ${total_balance:.2f}\n⏳ Total Blocked: ${total_blocked:.2f}\n🧾 Total Withdrawals: {total_withdraws}\n⏳ Pending Withdrawals: {pending_withdraws}"
    )
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

@bot.message_handler(func=lambda m: m.text == "🔍 RAADI")
def raadi_stats(m):
    if not is_admin(m.from_user.id): return
    total_videos = videos_data.get("total", 0)
    platform_stats = videos_data.get("platforms", {})
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
        f"• Pinterest: {platform_stats.get('pinterest',0)}",
        f"• Snapchat: {platform_stats.get('snapchat',0)}\n",
        "🥇 Top Users:"
    ]
    sorted_users = sorted(users_stats.items(), key=lambda x: x[1], reverse=True)
    for i, (uid, count) in enumerate(sorted_users[:40], start=1):
        bot_id = users.get(str(uid), {}).get("bot_id", "N/A")
        msg_lines.append(f"{i}. 👤 <a href='tg://user?id={uid}'>{uid}</a> - 🎬 {count} videos | BOT ID: {bot_id}")

    bot.send_message(m.chat.id, "\n".join(msg_lines))

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
    bot.send_message(m.chat.id, "❌ All channels removed.")

@bot.message_handler(func=lambda m: m.text == "👥 SEE LIST")
def see_users(m):
    if not is_admin(m.from_user.id): return
    total = len(users)
    count = 0
    for uid in users:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("💬 OPEN CHAT", url=f"tg://user?id={uid}"))
        bot.send_message(m.chat.id, f"👤 User ID: {uid}", reply_markup=kb)
        count += 1
        if count >= 20: break
    bot.send_message(m.chat.id, f"📊 Total Users: {total}")

@bot.message_handler(func=lambda m: m.text == "🔒 LOCK BOT")
def lock_bot_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "✍️ Send lock message:")
    bot.register_next_step_handler(msg, lock_bot_process)

def lock_bot_process(m):
    global BOT_LOCKED, LOCK_MESSAGE
    if not is_admin(m.from_user.id): return
    text = (m.text or "").strip()
    if not text: return
    LOCK_MESSAGE = text
    BOT_LOCKED = True
    bot.send_message(m.chat.id, f"🔒 Bot locked.\n{text}")

@bot.message_handler(func=lambda m: m.text == "🔓 UNLOCK BOT")
def unlock_bot(m):
    global BOT_LOCKED
    if not is_admin(m.from_user.id): return
    BOT_LOCKED = False
    bot.send_message(m.chat.id, "🔓 Bot unlocked successfully.")

@bot.message_handler(func=lambda m: m.text == "📢 ADD ADS")
def add_ads_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "✍️ Send Ads: <code>Button Name | Link | Text</code>")
    bot.register_next_step_handler(msg, process_add_ads)

def process_add_ads(m):
    global ADS_ENABLED, ADS_BTN_TEXT, ADS_URL, ADS_TEXT
    if not is_admin(m.from_user.id): return
    text = (m.text or "").strip()
    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 2: return
    ADS_BTN_TEXT = parts[0]
    ADS_URL = parts[1]
    ADS_TEXT = parts[2] if len(parts) > 2 else "✨ Ads"
    ADS_ENABLED = True
    bot.send_message(m.chat.id, "✅ Ads enabled!")

@bot.message_handler(func=lambda m: m.text == "🗑 DELETE ADS")
def delete_ads(m):
    global ADS_ENABLED
    if not is_admin(m.from_user.id): return
    ADS_ENABLED = False
    bot.send_message(m.chat.id, "🗑 Ads deleted.")

@bot.message_handler(func=lambda m: m.text == "📥 IMPORT USERS")
def import_users_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Send Telegram IDs separated by space:")
    bot.register_next_step_handler(msg, import_users_process)

def import_users_process(m):
    if not is_admin(m.from_user.id): return
    ids = m.text.strip().replace("\n", " ").split()
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
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Send username (@scholes1):")
    bot.register_next_step_handler(msg, get_ref_username)

def get_ref_username(m):
    if not is_admin(m.from_user.id): return
    username = m.text.replace("@", "").strip()
    msg = bot.send_message(m.chat.id, f"User: @{username}\nSend custom referral code number:")
    bot.register_next_step_handler(msg, lambda x: save_custom_ref_code(x, username))

def save_custom_ref_code(m, username):
    if not is_admin(m.from_user.id): return
    code = m.text.strip()
    user_id = next((u for u, d in users.items() if d.get("username", "").lower() == username.lower()), None)
    if not user_id:
        bot.send_message(m.chat.id, "❌ User not found.")
        return
    users[user_id]["ref"] = code
    save_users()
    bot.send_message(m.chat.id, f"✅ Custom referral code set to {code}")

@bot.message_handler(func=lambda m: m.text == "🔎 SEARCH USER")
def search_user(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Send User Telegram ID:")
    bot.register_next_step_handler(msg, search_user_result)

def search_user_result(m):
    if not is_admin(m.from_user.id): return
    uid = m.text.strip()
    if uid in users:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("💬 OPEN CHAT", url=f"tg://user?id={uid}"))
        bot.send_message(m.chat.id, f"👤 User Found\nID: {uid}", reply_markup=kb)
        
        # Open admin user control directly
        m.text = uid
        process_admin_user_search(m)
    else:
        bot.send_message(m.chat.id, "❌ User not found")

@bot.message_handler(func=lambda m: m.text == "➕ ADD BALANCE")
def add_balance_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Send ID and amount:\nExample:\n123456789 10.5")
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
    msg = bot.send_message(m.chat.id, "Send ID and amount:\nExample:\n123456789 5.0")
    bot.register_next_step_handler(msg, remove_balance_process)

def remove_balance_process(m):
    if not is_admin(m.from_user.id): return
    try:
        uid_str, amt_str = m.text.strip().split()
        amt = float(amt_str)
        uid = uid_str if uid_str in users else find_user_by_botid(uid_str)
        if not uid or amt <= 0 or users[uid]["balance"] < amt: return
        users[uid]["balance"] -= amt
        save_users()
        bot.send_message(m.chat.id, f"✅ Removed ${amt:.2f} from user {uid}")
    except:
        bot.send_message(m.chat.id, "❌ Format error.")

@bot.message_handler(func=lambda m: m.text == "❌ CLOSE WINDOWS")
def close_channel_windows(m):
    global CHANNEL_WINDOW_OPEN
    if not is_admin(m.from_user.id): return
    CHANNEL_WINDOW_OPEN = False
    bot.send_message(m.chat.id, "✅ Channel join window disabled.")

@bot.message_handler(func=lambda m: m.text == "✅ VERIFY ON")
def verify_on(m):
    global VERIFY_ENABLED
    if not is_admin(m.from_user.id): return
    VERIFY_ENABLED = True
    bot.send_message(m.chat.id, "✅ Verify system enabled")

@bot.message_handler(func=lambda m: m.text == "❌ VERIFY OFF")
def verify_off(m):
    global VERIFY_ENABLED
    if not is_admin(m.from_user.id): return
    VERIFY_ENABLED = False
    bot.send_message(m.chat.id, "❌ Verify system disabled")

# ================= LINK HANDLER & DOWNLOADER ENGINE =================
@bot.message_handler(func=lambda m: m.text and "http" in m.text)
def handle_links(message):
    if bot_locked_guard(message) or banned_guard(message):
        return

    user_id = message.from_user.id
    link = message.text

    # Force join multi channels
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

    # Track usage & mission
    track_mission_progress(user_id, "download", 1)
    
    status_text = "⚡ <b>VIP Priority Processing...</b>" if is_premium_user(user_id) else "⏳ <b>Downloading...</b>"
    bot.send_message(message.chat.id, status_text)
    download_media(message.chat.id, link)

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

    uid = str(chat_id)
    videos_data["total"] = videos_data.get("total", 0) + 1
    videos_data["users"][uid] = videos_data.get("users", {}).get(uid, 0) + 1

    if platform:
        videos_data.setdefault("platforms", {})[platform] = videos_data["platforms"].get(platform, 0) + 1

    save_videos()

    caption = CAPTION_TEXT
    if ADS_ENABLED and ADS_TEXT:
        caption += f"\n\n{ADS_TEXT}"

    with open(file_path, "rb") as video:
        bot.send_video(chat_id, video, caption=caption, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("music_"))
def convert_to_music(call):
    vid_id = call.data.replace("music_", "")
    file_path = video_files.get(vid_id)

    if not file_path or not os.path.exists(file_path):
        bot.answer_callback_query(call.id, "❌ File no longer available.", show_alert=True)
        return

    bot.answer_callback_query(call.id, "🎵 Extracting audio...")
    audio_path = f"audio_{vid_id}.mp3"

    try:
        cmd = f'ffmpeg -i "{file_path}" -q:a 0 -map a "{audio_path}" -y'
        subprocess.run(cmd, shell=True, check=True)

        with open(audio_path, "rb") as audio:
            bot.send_audio(call.message.chat.id, audio, caption=CAPTION_TEXT)

        if os.path.exists(audio_path):
            os.remove(audio_path)
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Audio extraction failed: {e}")

def download_media(chat_id, text):
    try:
        url = extract_url(text)
        if not url:
            bot.send_message(chat_id, "❌ Invalid link")
            return

        # TikTok Downloader
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
                        filename = f"tiktok_vid_{uuid.uuid4().hex[:6]}.mp4"
                        with open(filename, "wb") as f:
                            f.write(video_data)
                        send_video_with_music(chat_id, filename, "tiktok")
                        if os.path.exists(filename): os.remove(filename)
                        return
            except Exception as e:
                bot.send_message(chat_id, f"❌ TikTok error:\n{e}")
                return

        # Snapchat Downloader
        if "snapchat.com" in url or "snap.com" in url:
            try:
                ydl_opts = {"format": "best", "outtmpl": "snapchat_%(id)s.%(ext)s", "quiet": True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    file = ydl.prepare_filename(info)
                send_video_with_music(chat_id, file, "snapchat")
                if os.path.exists(file): os.remove(file)
                return
            except Exception as e:
                bot.send_message(chat_id, f"❌ Snapchat error:\n{e}")
                return

        # Pinterest Downloader
        if "pin.it" in url or "pinterest.com" in url:
            try:
                if "pin.it" in url:
                    r = requests.head(url, allow_redirects=True, timeout=10)
                    url = r.url
                ydl_opts = {"format": "bv*+ba/b", "outtmpl": "pinterest_%(id)s.%(ext)s", "quiet": True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    file = ydl.prepare_filename(info)
                send_video_with_music(chat_id, file, "pinterest")
                if os.path.exists(file): os.remove(file)
                return
            except Exception as e:
                bot.send_message(chat_id, f"❌ Pinterest error:\n{e}")
                return

        # YouTube & Universal Fallback Downloader
        ydl_opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": "download_%(id)s.%(ext)s",
            "quiet": True
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file = ydl.prepare_filename(info)
        
        platform = "youtube" if "youtu" in url else "generic"
        send_video_with_music(chat_id, file, platform)
        if os.path.exists(file): os.remove(file)

    except Exception as e:
        bot.send_message(chat_id, f"❌ Download failed: {e}")

# ================= MULTI JOIN CONFIRM HANDLERS =================
def send_multi_join(user_id):
    kb = InlineKeyboardMarkup(row_width=3)
    buttons = [InlineKeyboardButton("➕ JOIN", url=f"https://t.me/{ch}") for ch in POST_CHANNELS]
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
            if member.status not in ["member", "administrator", "creator"]:
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

# ================= TELEGRAM VERIFICATION CALLBACKS =================
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

async def send_code_telegram(user_id, code):
    try:
        user = await tg_client.get_entity(user_id)
        await tg_client.send_message(user, f"🔐 Your verification code:\n\n{code}")
        return True
    except Exception as e:
        print("DM ERROR:", e)
        return False

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
        bot.send_message(m.chat.id, "✅ Verification successful\n⬇️ Downloading video...")
        download_media(m.chat.id, link)
    else:
        bot.send_message(m.chat.id, "❌ Wrong verification code")

# ================= POLLING / MAIN START =================
if __name__ == "__main__":
    print("🚀 Video Downloader Bot with Premium VIP System started successfully...")
    bot.infinity_polling(skip_pending=True)
