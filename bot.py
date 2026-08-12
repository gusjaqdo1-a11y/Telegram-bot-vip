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
PREMIUM_FILE = "premium.json"
PAYMENTS_FILE = "payments.json"
REFERRALS_FILE = "referrals.json"
REF_REWARDS_FILE = "referral_rewards.json"
REF_MILESTONES_FILE = "referral_milestones.json"
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
premium_data = load_json(PREMIUM_FILE, {})
payments_data = load_json(PAYMENTS_FILE, {})
referrals_data = load_json(REFERRALS_FILE, {})
referral_rewards_data = load_json(REF_REWARDS_FILE, {})
referral_milestones_data = load_json(REF_MILESTONES_FILE, {
    "3": 7, "5": 14, "10": 30, "25": 90, "50": 365
})
feature_requests_data = load_json(FEATURE_REQUESTS_FILE, {})
feature_votes_data = load_json(FEATURE_VOTES_FILE, {})
leaderboard_data = load_json(LEADERBOARD_FILE, {})
missions_data = load_json(MISSIONS_FILE, {
    "mission_1": {"title": "Download 10 Files", "type": "daily", "target": 10, "reward_days": 1},
    "mission_2": {"title": "Invite 3 Friends", "type": "weekly", "target": 3, "reward_days": 2},
    "mission_3": {"title": "Vote on 3 Features", "type": "daily", "target": 3, "reward_days": 1}
})
mission_progress_data = load_json(MISSION_PROGRESS_FILE, {})
coupons_data = load_json(COUPONS_FILE, {})
coupon_usage_data = load_json(COUPON_USAGE_FILE, {})
gift_premium_data = load_json(GIFT_PREMIUM_FILE, {})
vip_identity_data = load_json(VIP_IDENTITY_FILE, {})

def save_users(): save_json(USERS_FILE, users)
def save_withdraws(): save_json(WITHDRAWS_FILE, withdraws)
def save_premium(): save_json(PREMIUM_FILE, premium_data)
def save_payments(): save_json(PAYMENTS_FILE, payments_data)
def save_referrals(): save_json(REFERRALS_FILE, referrals_data)
def save_referral_rewards(): save_json(REF_REWARDS_FILE, referral_rewards_data)
def save_referral_milestones(): save_json(REF_MILESTONES_FILE, referral_milestones_data)
def save_feature_requests(): save_json(FEATURE_REQUESTS_FILE, feature_requests_data)
def save_feature_votes(): save_json(FEATURE_VOTES_FILE, feature_votes_data)
def save_leaderboard(): save_json(LEADERBOARD_FILE, leaderboard_data)
def save_missions(): save_json(MISSIONS_FILE, missions_data)
def save_mission_progress(): save_json(MISSION_PROGRESS_FILE, mission_progress_data)
def save_coupons(): save_json(COUPONS_FILE, coupons_data)
def save_coupon_usage(): save_json(COUPON_USAGE_FILE, coupon_usage_data)
def save_gift_premium(): save_json(GIFT_PREMIUM_FILE, gift_premium_data)
def save_vip_identity(): save_json(VIP_IDENTITY_FILE, vip_identity_data)

videos_data = load_json(VIDEOS_FILE, {
    "total": 0,
    "platforms": {"tiktok": 0, "youtube": 0, "facebook": 0, "pinterest": 0},
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
    if uid_str in premium_data:
        p = premium_data[uid_str]
        if p.get("status") == "ACTIVE":
            exp = datetime.strptime(p.get("expiry_date"), "%Y-%m-%d %H:%M:%S")
            if datetime.now() < exp:
                return True
            else:
                p["status"] = "INACTIVE"
                save_premium()
                try:
                    bot.send_message(
                        int(uid_str),
                        "⏰ Your Premium has expired.\n\n⭐ Renew Premium to continue using VIP features.",
                        reply_markup=InlineKeyboardMarkup().add(
                            InlineKeyboardButton("⭐ Renew Premium", callback_data="buy_premium_menu"),
                            InlineKeyboardButton("🏠 Home", callback_data="go_home")
                        )
                    )
                except:
                    pass
    return False

def get_vip_badge(uid):
    uid_str = str(uid)
    if not is_premium(uid_str):
        return ""
    identity = vip_identity_data.get(uid_str, {})
    title = identity.get("title", "VIP")
    if title == "VIP":
        return "⭐"
    elif title == "PRO":
        return "💎"
    elif title == "LEGEND":
        return "🔥"
    elif title == "ELITE":
        return "👑"
    return "👑"

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
    kb.add("👑 PREMIUM MANAGEMENT")
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
    uid_str = str(uid)
    args = message.text.split()

    if uid_str not in users:
        ref = args[1] if len(args) > 1 and not args[1].startswith("ref_") else None
        if len(args) > 1 and args[1].startswith("ref_"):
            ref = args[1].replace("ref_", "")

        users[uid_str] = {
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
            if ref_user and ref_user != uid_str:
                if ref_user not in referrals_data:
                    referrals_data[ref_user] = []
                if uid_str not in referrals_data[ref_user]:
                    referrals_data[ref_user].append(uid_str)
                    users[ref_user]["invited"] = len(referrals_data[ref_user])
                    save_referrals()
                    
                    # Check milestones
                    inv_count = len(referrals_data[ref_user])
                    milestones = referral_milestones_data
                    for m_target, m_days in milestones.items():
                        if inv_count == int(m_target):
                            # give reward days
                            if ref_user not in referral_rewards_data:
                                referral_rewards_data[ref_user] = 0
                            # Add days to premium or record reward
                            break
                    bot.send_message(int(ref_user), "🎉 New user joined via your referral link!")

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
        "• Premium VIP System"
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

# ================= PREMIUM CENTER HANDLER =================
@bot.message_handler(func=lambda m: m.text == "👑 PREMIUM")
def premium_center_handler(m):
    if bot_locked_guard(m):
        return
    if banned_guard(m):
        return
    send_premium_center(m.chat.id, m.from_user.id)

def send_premium_center(chat_id, user_id):
    uid_str = str(user_id)
    active = is_premium(user_id)
    status_text = "ACTIVE" if active else "INACTIVE"
    plan_name = "30 Days"
    expiry_str = "N/A"
    days_left = 0

    if active and uid_str in premium_data:
        p = premium_data[uid_str]
        plan_name = p.get("plan", "30 Days")
        exp_dt = datetime.strptime(p.get("expiry_date"), "%Y-%m-%d %H:%M:%S")
        expiry_str = exp_dt.strftime("%d %b %Y")
        days_left = max(0, (exp_dt - datetime.now()).days)

    text = (
        f"╭━━━ 👑 PREMIUM CENTER ━━━╮\n\n"
        f"⭐ Status: {status_text}\n"
        f"💎 Plan: {plan_name}\n"
        f"📅 Expires: {expiry_str}\n"
        f"⏳ Days Left: {days_left}\n\n"
        f"✨ Unlock the full Premium experience!\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━╯"
    )

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⭐ Buy Premium", callback_data="buy_premium_menu"),
        InlineKeyboardButton("💎 My Plan", callback_data="my_plan_details")
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
        InlineKeyboardButton("👑 My VIP Identity", callback_data="prem_identity"),
        InlineKeyboardButton("🔙 Back", callback_data="go_home")
    )

    bot.send_message(chat_id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "go_home")
def callback_go_home(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "🏠 Home Menu", reply_markup=user_menu(is_admin(call.from_user.id)))

@bot.callback_query_handler(func=lambda call: call.data == "buy_premium_menu")
def callback_buy_premium(call):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⭐ 7 Days (59 Stars)", callback_data="buy_plan_7"),
        InlineKeyboardButton("⭐ 30 Days (199 Stars)", callback_data="buy_plan_30")
    )
    kb.add(
        InlineKeyboardButton("⭐ 90 Days (499 Stars)", callback_data="buy_plan_90"),
        InlineKeyboardButton("⭐ 1 Year (1499 Stars)", callback_data="buy_plan_365")
    )
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="back_to_premium"))

    bot.edit_message_text(
        "╭━━━ ⭐ CHOOSE PLAN ━━━╮\n\nSelect your Premium subscription plan:\n╰━━━━━━━━━━━━━━━━━━━━━━╯",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda call: call.data == "back_to_premium")
def callback_back_premium(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    send_premium_center(call.message.chat.id, call.from_user.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_plan_"))
def callback_buy_plan(call):
    days = int(call.data.split("_")[2])
    plan_map = {
        7: ("7 Days", 59),
        30: ("30 Days", 199),
        90: ("90 Days", 499),
        365: ("1 Year", 1499)
    }
    plan_name, stars = plan_map.get(days, ("30 Days", 199))
    
    prices = [LabeledPrice(label=f"Premium {plan_name}", amount=stars)]
    bot.send_invoice(
        call.message.chat.id,
        title=f"Premium Subscription ({plan_name})",
        description=f"Unlock VIP features for {plan_name} using Telegram Stars.",
        invoice_payload=f"premium_{days}_{call.from_user.id}",
        provider_token="",
        currency="XTR",
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
        days = int(parts[1])
        uid_str = str(message.from_user.id)
        
        plan_names = {7: "7 Days", 30: "30 Days", 90: "90 Days", 365: "1 Year"}
        plan_name = plan_names.get(days, "30 Days")
        
        start_date = datetime.now()
        if uid_str in premium_data and premium_data[uid_str].get("status") == "ACTIVE":
            curr_exp = datetime.strptime(premium_data[uid_str]["expiry_date"], "%Y-%m-%d %H:%M:%S")
            if curr_exp > start_date:
                start_date = curr_exp
        
        expiry_date = start_date + timedelta(days=days)
        
        premium_data[uid_str] = {
            "user_id": uid_str,
            "plan": plan_name,
            "duration": days,
            "stars_amount": payment.total_amount,
            "payment_id": payment.telegram_payment_charge_id,
            "start_date": start_date.strftime("%Y-%m-%d %H:%M:%S"),
            "expiry_date": expiry_date.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "ACTIVE",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_premium()
        
        payments_data[payment.telegram_payment_charge_id] = premium_data[uid_str]
        save_payments()
        
        bot.send_message(
            message.chat.id,
            f"✅ <b>Payment Successful!</b>\n\n👑 Premium Activated for <b>{plan_name}</b>\n📅 Expires: {expiry_date.strftime('%d %b %Y')}",
            parse_mode="HTML"
        )
    elif payload.startswith("gift_"):
        parts = payload.split("_")
        recipient_id = parts[1]
        days = int(parts[2])
        uid_str = str(message.from_user.id)
        
        plan_names = {7: "7 Days", 30: "30 Days", 90: "90 Days", 365: "1 Year"}
        plan_name = plan_names.get(days, "30 Days")
        
        start_date = datetime.now()
        if recipient_id in premium_data and premium_data[recipient_id].get("status") == "ACTIVE":
            curr_exp = datetime.strptime(premium_data[recipient_id]["expiry_date"], "%Y-%m-%d %H:%M:%S")
            if curr_exp > start_date:
                start_date = curr_exp
        
        expiry_date = start_date + timedelta(days=days)
        
        premium_data[recipient_id] = {
            "user_id": recipient_id,
            "plan": plan_name,
            "duration": days,
            "stars_amount": payment.total_amount,
            "payment_id": payment.telegram_payment_charge_id,
            "start_date": start_date.strftime("%Y-%m-%d %H:%M:%S"),
            "expiry_date": expiry_date.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "ACTIVE",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_premium()
        
        gift_entry = {
            "sender_id": uid_str,
            "recipient_id": recipient_id,
            "plan": plan_name,
            "stars_amount": payment.total_amount,
            "payment_id": payment.telegram_payment_charge_id,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "completed"
        }
        if recipient_id not in gift_premium_data:
            gift_premium_data[recipient_id] = []
        gift_premium_data[recipient_id].append(gift_entry)
        save_gift_premium()
        
        bot.send_message(message.chat.id, "🎁 Gift sent successfully!")
        try:
            bot.send_message(
                int(recipient_id),
                f"╭━━━ 🎁 PREMIUM GIFT ━━━╮\n\n🎉 You received Premium!\n\n💎 Plan: {plan_name}\n📅 Expires: {expiry_date.strftime('%d %b %Y')}\n\nEnjoy your Premium experience! 👑\n╰━━━━━━━━━━━━━━━━━━━━━━╯"
            )
        except:
            pass

@bot.callback_query_handler(func=lambda call: call.data == "my_plan_details")
def callback_my_plan(call):
    uid_str = str(call.from_user.id)
    if is_premium(call.from_user.id):
        p = premium_data[uid_str]
        text = f"💎 <b>My Plan Details</b>\n\nPlan: {p.get('plan')}\nStarted: {p.get('start_date')}\nExpires: {p.get('expiry_date')}"
    else:
        text = "❌ You do not have an active Premium plan."
    bot.answer_callback_query(call.id, text, show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "prem_settings")
def callback_prem_settings(call):
    bot.answer_callback_query(call.id, "⚙️ Premium Settings are active.", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "prem_my_stats")
def callback_prem_stats(call):
    uid_str = str(call.from_user.id)
    v_count = videos_data.get("users", {}).get(uid_str, 0)
    text = f"📊 <b>My Statistics</b>\n\n🎬 Total Downloads: {v_count}\n👥 Referrals: {len(referrals_data.get(uid_str, []))}"
    bot.answer_callback_query(call.id, text, show_alert=True)

# ================= REFERRAL & REWARDS =================
@bot.callback_query_handler(func=lambda call: call.data == "prem_invite")
def callback_prem_invite(call):
    uid_str = str(call.from_user.id)
    bot_username = bot.get_me().username
    ref_code = users.get(uid_str, {}).get("ref", random_ref())
    link = f"https://t.me/{bot_username}?start={ref_code}"
    refs_count = len(referrals_data.get(uid_str, []))
    
    text = (
        f"╭━━━ 🎁 INVITE & EARN ━━━╮\n\n"
        f"👥 Referrals: {refs_count}\n"
        f"🎁 Rewards: ⭐ Active\n"
        f"🏆 Rank: #{random.randint(1, 50)}\n\n"
        f"Invite your friends and earn rewards!\n"
        f"Link: {link}\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━╯"
    )
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={link}&text=Download+videos+easily!"),
        InlineKeyboardButton("👥 My Referrals", callback_data="my_refs_list")
    )
    kb.add(
        InlineKeyboardButton("🎁 My Rewards", callback_data="my_rewards_list"),
        InlineKeyboardButton("🏆 My Rank", callback_data="my_rank_details")
    )
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="back_to_premium"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "my_refs_list")
def callback_my_refs(call):
    uid_str = str(call.from_user.id)
    count = len(referrals_data.get(uid_str, []))
    bot.answer_callback_query(call.id, f"👥 You have invited {count} users.", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "my_rewards_list")
def callback_my_rewards(call):
    bot.answer_callback_query(call.id, "🎁 All milestone rewards are up to date.", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "my_rank_details")
def callback_my_rank(call):
    bot.answer_callback_query(call.id, "🏆 Your rank is active in leaderboard.", show_alert=True)

# ================= FEATURE REQUESTS =================
@bot.callback_query_handler(func=lambda call: call.data == "prem_features")
def callback_prem_features(call):
    if not is_premium(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Premium feature only!", show_alert=True)
        return
    
    text = (
        f"╭━━━ 💡 FEATURE REQUESTS ━━━╮\n\n"
        f"🔥 MOST REQUESTED\n\n"
    )
    if not feature_requests_data:
        text += "1️⃣ No features requested yet.\n"
    else:
        sorted_reqs = sorted(feature_requests_data.values(), key=lambda x: x.get("votes", 0), reverse=True)
        for i, req in enumerate(sorted_reqs[:3], start=1):
            text += f"{i}️⃣ {req.get('title')}\n👍 {req.get('votes', 0)} Votes\n\n"
    text += f"╰━━━━━━━━━━━━━━━━━━━━━━╯"

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("👍 Vote", callback_data="feature_vote_menu"),
        InlineKeyboardButton("💡 Submit Feature", callback_data="feature_submit")
    )
    kb.add(
        InlineKeyboardButton("📋 My Requests", callback_data="feature_my_list"),
        InlineKeyboardButton("🔥 Most Requested", callback_data="prem_features")
    )
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="back_to_premium"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "feature_submit")
def callback_feature_submit(call):
    msg = bot.send_message(call.message.chat.id, "✍️ Send your feature title:")
    bot.register_next_step_handler(msg, process_feature_title)

def process_feature_title(m):
    title = m.text.strip()
    msg = bot.send_message(m.chat.id, "✍️ Now send description for your feature:")
    bot.register_next_step_handler(msg, process_feature_desc, title)

def process_feature_desc(m, title):
    desc = m.text.strip()
    req_id = str(uuid.uuid4())[:8]
    uid_str = str(m.from_user.id)
    
    feature_requests_data[req_id] = {
        "request_id": req_id,
        "user_id": uid_str,
        "title": title,
        "description": desc,
        "votes": 1,
        "status": "🟡 Pending",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    if req_id not in feature_votes_data:
        feature_votes_data[req_id] = [uid_str]
    save_feature_requests()
    save_feature_votes()
    
    bot.send_message(m.chat.id, "✅ Feature submitted successfully!", reply_markup=user_menu(is_admin(m.from_user.id)))

@bot.callback_query_handler(func=lambda call: call.data == "feature_vote_menu")
def callback_feature_vote(call):
    if not feature_requests_data:
        bot.answer_callback_query(call.id, "No features to vote.", show_alert=True)
        return
    kb = InlineKeyboardMarkup(row_width=1)
    for req_id, req in feature_requests_data.items():
        kb.add(InlineKeyboardButton(f"👍 {req['title']} ({req['votes']})", callback_data=f"vote_req_{req_id}"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="prem_features"))
    bot.edit_message_text("Select a feature to vote:", call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("vote_req_"))
def callback_vote_req(call):
    req_id = call.data.split("_")[2]
    uid_str = str(call.from_user.id)
    if req_id in feature_requests_data:
        if req_id not in feature_votes_data:
            feature_votes_data[req_id] = []
        if uid_str in feature_votes_data[req_id]:
            feature_votes_data[req_id].remove(uid_str)
            feature_requests_data[req_id]["votes"] = max(0, feature_requests_data[req_id]["votes"] - 1)
            bot.answer_callback_query(call.id, "Vote removed.")
        else:
            feature_votes_data[req_id].append(uid_str)
            feature_requests_data[req_id]["votes"] += 1
            bot.answer_callback_query(call.id, "Vote added!")
        save_feature_requests()
        save_feature_votes()
    callback_prem_features(call)

@bot.callback_query_handler(func=lambda call: call.data == "feature_my_list")
def callback_my_requests(call):
    uid_str = str(call.from_user.id)
    my_reqs = [r for r in feature_requests_data.values() if r["user_id"] == uid_str]
    text = f"📋 <b>My Feature Requests ({len(my_reqs)})</b>\n\n"
    for r in my_reqs:
        text += f"• {r['title']} [{r['status']}] - 👍 {r['votes']}\n"
    bot.answer_callback_query(call.id, text if my_reqs else "No requests found.", show_alert=True)

# ================= LEADERBOARD =================
@bot.callback_query_handler(func=lambda call: call.data == "prem_leaderboard")
def callback_prem_leaderboard(call):
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
        InlineKeyboardButton("📊 My Rank", callback_data="my_rank_details"),
        InlineKeyboardButton("🎁 My Rewards", callback_data="my_rewards_list")
    )
    kb.add(
        InlineKeyboardButton("📅 Weekly", callback_data="lb_weekly"),
        InlineKeyboardButton("📆 Monthly", callback_data="lb_monthly"),
        InlineKeyboardButton("🏆 All Time", callback_data="lb_alltime")
    )
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="back_to_premium"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("lb_"))
def callback_lb_filter(call):
    bot.answer_callback_query(call.id, "Leaderboard updated.", show_alert=True)

# ================= MISSIONS =================
@bot.callback_query_handler(func=lambda call: call.data == "prem_missions")
def callback_prem_missions(call):
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
        InlineKeyboardButton("🏆 Rewards", callback_data="my_rewards_list"),
        InlineKeyboardButton("🔙 Back", callback_data="back_to_premium")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "missions_completed")
def callback_missions_completed(call):
    bot.answer_callback_query(call.id, "All completed missions shown.", show_alert=True)

# ================= COUPONS =================
@bot.callback_query_handler(func=lambda call: call.data == "prem_coupons")
def callback_prem_coupons(call):
    text = (
        f"╭━━━ 🎟️ PREMIUM COUPON ━━━╮\n\n"
        f"Enter your coupon code below.\n\n"
        f"Example:\nVIP2026\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━╯"
    )
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🎟️ Enter Code", callback_data="enter_coupon_prompt"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="back_to_premium"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "enter_coupon_prompt")
def callback_enter_coupon(call):
    msg = bot.send_message(call.message.chat.id, "🎟️ Send your coupon code:")
    bot.register_next_step_handler(msg, process_coupon_code)

def process_coupon_code(m):
    code = m.text.strip().upper()
    uid_str = str(m.from_user.id)
    
    if code not in coupons_data or not coupons_data[code].get("active", True):
        bot.send_message(m.chat.id, "❌ Invalid or inactive coupon code.")
        return
        
    coupon = coupons_data[code]
    if uid_str not in coupon_usage_data:
        coupon_usage_data[uid_str] = []
        
    if code in coupon_usage_data[uid_str]:
        bot.send_message(m.chat.id, "❌ You have already used this coupon.")
        return
        
    coupon_usage_data[uid_str].append(code)
    save_coupon_usage()
    
    bot.send_message(m.chat.id, f"✅ Coupon applied successfully! Reward: {coupon.get('reward_days', 7)} Days Premium.")

# ================= GIFT PREMIUM =================
@bot.callback_query_handler(func=lambda call: call.data == "prem_gift")
def callback_prem_gift(call):
    msg = bot.send_message(call.message.chat.id, "🎁 Send recipient Telegram username or ID:")
    bot.register_next_step_handler(msg, process_gift_recipient)

def process_gift_recipient(m):
    target = m.text.strip().replace("@", "")
    recipient_id = None
    for u, data in users.items():
        if data.get("username", "").lower() == target.lower() or u == target:
            recipient_id = u
            break
            
    if not recipient_id:
        bot.send_message(m.chat.id, "❌ User not found.")
        return
        
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⭐ 7 Days", callback_data=f"gift_plan_{recipient_id}_7"),
        InlineKeyboardButton("⭐ 30 Days", callback_data=f"gift_plan_{recipient_id}_30")
    )
    kb.add(
        InlineKeyboardButton("⭐ 90 Days", callback_data=f"gift_plan_{recipient_id}_90"),
        InlineKeyboardButton("⭐ 1 Year", callback_data=f"gift_plan_{recipient_id}_365")
    )
    bot.send_message(m.chat.id, "Select plan to gift:", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("gift_plan_"))
def callback_gift_plan(call):
    parts = call.data.split("_")
    recipient_id = parts[2]
    days = int(parts[3])
    plan_names = {7: "7 Days", 30: "30 Days", 90: "90 Days", 365: "1 Year"}
    stars_map = {7: 59, 30: 199, 90: 499, 365: 1499}
    
    prices = [LabeledPrice(label=f"Gift Premium ({plan_names.get(days)})", amount=stars_map.get(days))]
    bot.send_invoice(
        call.message.chat.id,
        title=f"Gift Premium ({plan_names.get(days)})",
        description=f"Gift Premium subscription to user {recipient_id}",
        invoice_payload=f"gift_{recipient_id}_{days}",
        provider_token="",
        currency="XTR",
        prices=prices
    )

# ================= VIP IDENTITY =================
@bot.callback_query_handler(func=lambda call: call.data == "prem_identity")
def callback_prem_identity(call):
    uid_str = str(call.from_user.id)
    identity = vip_identity_data.get(uid_str, {"title": "PRO", "level": 4, "points": 327})
    
    text = (
        f"╭━━━ 👑 VIP IDENTITY ━━━╮\n\n"
        f"👤 User: @{call.from_user.username or 'User'}\n\n"
        f"⭐ Current Title:\n💎 {identity.get('title')}\n\n"
        f"📅 Premium Since:\n{datetime.now().strftime('%d %b %Y')}\n\n"
        f"🔥 VIP Level:\nLevel {identity.get('level')}\n\n"
        f"🏆 Points:\n{identity.get('points')}\n\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━╯"
    )
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⭐ VIP", callback_data="set_title_VIP"),
        InlineKeyboardButton("💎 PRO", callback_data="set_title_PRO")
    )
    kb.add(
        InlineKeyboardButton("🔥 LEGEND", callback_data="set_title_LEGEND"),
        InlineKeyboardButton("👑 ELITE", callback_data="set_title_ELITE")
    )
    kb.add(
        InlineKeyboardButton("🎨 Customize", callback_data="customize_identity"),
        InlineKeyboardButton("🔙 Back", callback_data="back_to_premium")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_title_"))
def callback_set_title(call):
    title = call.data.split("_")[2]
    uid_str = str(call.from_user.id)
    if uid_str not in vip_identity_data:
        vip_identity_data[uid_str] = {"title": title, "level": 1, "points": 100}
    else:
        vip_identity_data[uid_str]["title"] = title
    save_vip_identity()
    bot.answer_callback_query(call.id, f"✅ Title updated to {title}", show_alert=True)
    callback_prem_identity(call)

@bot.callback_query_handler(func=lambda call: call.data == "customize_identity")
def callback_customize_identity(call):
    bot.answer_callback_query(call.id, "🎨 Identity customization active.", show_alert=True)

# ================= ADMIN PANEL: PREMIUM MANAGEMENT =================
@bot.message_handler(func=lambda m: m.text == "👑 PREMIUM MANAGEMENT")
def admin_premium_management(m):
    if not is_admin(m.from_user.id):
        return
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🔎 Search User", callback_data="adm_prem_search"),
        InlineKeyboardButton("👑 Give Premium", callback_data="adm_prem_give")
    )
    kb.add(
        InlineKeyboardButton("❌ Remove Premium", callback_data="adm_prem_remove"),
        InlineKeyboardButton("📊 Statistics", callback_data="adm_prem_stats")
    )
    bot.send_message(m.chat.id, "👑 <b>Premium Management Panel</b>", reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "adm_prem_stats")
def callback_adm_prem_stats(call):
    if not is_admin(call.from_user.id):
        return
    total_u = len(users)
    active_p = sum(1 for p in premium_data.values() if p.get("status") == "ACTIVE")
    expired_p = total_u - active_p
    total_stars = sum(p.get("stars_amount", 0) for p in payments_data.values())
    
    text = (
        f"👑 <b>PREMIUM STATISTICS</b>\n\n"
        f"👥 Total Users: {total_u}\n"
        f"⭐ Active Premium: {active_p}\n"
        f"⏰ Expired Premium: {expired_p}\n"
        f"💳 Total Stars: {total_stars}\n"
        f"📅 Stars Today: {total_stars}\n"
        f"📆 Stars This Month: {total_stars}\n"
        f"🎁 Total Referrals: {sum(len(v) for v in referrals_data.values())}\n"
        f"💡 Feature Requests: {len(feature_requests_data)}\n"
        f"🎯 Missions Completed: 0\n"
        f"🎟 Coupons Used: {sum(len(v) for v in coupon_usage_data.values())}\n"
        f"🎁 Gifts Sent: {sum(len(v) for v in gift_premium_data.values())}"
    )
    bot.answer_callback_query(call.id, text, show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "adm_prem_give")
def callback_adm_give_prem(call):
    if not is_admin(call.from_user.id):
        return
    msg = bot.send_message(call.message.chat.id, "Send User ID and Days separated by space (e.g. 123456 30):")
    bot.register_next_step_handler(msg, process_adm_give_prem)

def process_adm_give_prem(m):
    if not is_admin(m.from_user.id):
        return
    try:
        parts = m.text.strip().split()
        uid_str = parts[0]
        days = int(parts[1])
        
        start_date = datetime.now()
        expiry_date = start_date + timedelta(days=days)
        
        premium_data[uid_str] = {
            "user_id": uid_str,
            "plan": f"{days} Days",
            "duration": days,
            "stars_amount": 0,
            "payment_id": "admin_granted",
            "start_date": start_date.strftime("%Y-%m-%d %H:%M:%S"),
            "expiry_date": expiry_date.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "ACTIVE",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_premium()
        bot.send_message(m.chat.id, f"✅ Premium granted to {uid_str} for {days} days.")
        try:
            bot.send_message(int(uid_str), f"👑 Admin granted you Premium for {days} days!")
        except:
            pass
    except:
        bot.send_message(m.chat.id, "❌ Format error. Use: <user_id> <days>")

# ================= CHECK MEMBERSHIP =================
def check_membership(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["member", "administrator", "creator"]:
            badge = get_vip_badge(user_id)
            bot.send_message(
                user_id,
                f"""🎬 Welcome {badge} to Video Downloader Bot!

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
    except:
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
    bal = users[uid].get("balance", 0.0)
    blocked = users[uid].get("blocked", 0.0)
    bot.send_message(m.chat.id, f"💰 Available Balance: ${bal:.2f}\n⏳ Blocked Amount: ${blocked:.2f}")

@bot.message_handler(func=lambda m: m.text == "🆔 GET ID")
def get_id_handler(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    uid = str(m.from_user.id)
    bot.send_message(m.chat.id, f"🆔 BOT ID: <code>{users[uid]['bot_id']}</code>\n👤 Telegram ID: <code>{uid}</code>")

@bot.message_handler(func=lambda m: m.text == "👥 REFERRAL")
def referral_handler(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    uid = str(m.from_user.id)
    bot_username = bot.get_me().username
    link = f"https://t.me/{bot_username}?start={users[uid]['ref']}"
    invited = users[uid].get("invited", 0)
    bot.send_message(m.chat.id, f"🔗 Your Referral Link:\n{link}\n\n👥 Invited Users: {invited}\n🎁 You earn rewards per referral!")

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
        bot.send_message(int(uid), f"🚫 Your withdrawal of ${amt:.2f} is BLOCKED.\n🔢 Block Code: {code}\nContact admin to unlock.")

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
    bot.send_message(int(uid), "✅ You have been unbanned by admin.")

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
    uid = w["user"]
    msg_text = f"💳 WITHDRAWAL DETAILS\n\n🧾 Request ID: {w['id']}\n👤 User ID: {uid}\n💵 Amount: ${w['amount']:.2f}\n🏦 Address: {w['address']}\n📊 Status: {w['status'].upper()}"
    bot.send_message(m.chat.id, msg_text)

@bot.message_handler(func=lambda m: m.text == "📊 STATS")
def stats_handler(m):
    if not is_admin(m.from_user.id):
        return
    total_users = len(users)
    total_balance = sum(u.get("balance", 0.0) for u in users.values())
    msg = f"📊 BOT STATS\n\n👥 Total Users: {total_users}\n💰 Total Balance: ${total_balance:.2f}"
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
    msg = bot.send_message(m.chat.id, "Send channel username (e.g. @mychannel)")
    bot.register_next_step_handler(msg, add_channel_process)

def add_channel_process(m):
    username = m.text.strip()
    try:
        if username not in MANAGED_CHANNELS:
            MANAGED_CHANNELS.append(username)
        bot.send_message(m.chat.id, f"✅ Channel Added\n{username}")
    except:
        bot.send_message(m.chat.id, "❌ Invalid channel")

channel_posts = {}

@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def channel_language(call):
    bot.answer_callback_query(call.id, "Language updated.")

@bot.message_handler(func=lambda m: m.text == "🔍 RAADI")
def raadi_stats(m):
    if not is_admin(m.from_user.id):
        return
    total_videos = videos_data.get("total", 0)
    bot.send_message(m.chat.id, f"🔍 Total Downloads: {total_videos}")

@bot.message_handler(func=lambda m: m.text == "📢 BROADCAST")
def broadcast_start(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "📝 Send broadcast message:")
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
            pass
    bot.send_message(m.chat.id, f"✅ Broadcast sent to {count} users")

@bot.message_handler(func=lambda m: m.text == "📌 POST CHANNEL")
def post_channel_start(m):
    global CHANNEL_WINDOW_OPEN
    if not is_admin(m.from_user.id):
        return
    CHANNEL_WINDOW_OPEN = True
    POST_CHANNELS.clear()
    msg = bot.send_message(m.chat.id, "Send channel usernames. Send DONE when finished.")
    bot.register_next_step_handler(msg, post_channel_add)

def post_channel_add(m):
    if m.text.lower() == "done":
        bot.send_message(m.chat.id, f"✅ {len(POST_CHANNELS)} channels added.")
        return
    POST_CHANNELS.append(m.text.replace("@","").strip())
    msg = bot.send_message(m.chat.id, "Channel added. Send another or DONE")
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
    bot.send_message(m.chat.id, f"📊 Total Users: {len(users)}")

@bot.message_handler(func=lambda m: m.text == "🔒 LOCK BOT")
def lock_bot_start(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "Send lock message:")
    bot.register_next_step_handler(msg, lock_bot_process)

def lock_bot_process(m):
    global BOT_LOCKED, LOCK_MESSAGE
    if not is_admin(m.from_user.id):
        return
    LOCK_MESSAGE = m.text.strip()
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
def add_ads_start(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "Geli xayeysiiska qaabkan: `Button Name | Link | Qoraal`", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_add_ads)

def process_add_ads(m):
    global ADS_ENABLED, ADS_BTN_TEXT, ADS_URL, ADS_TEXT
    if not is_admin(m.from_user.id):
        return
    parts = [p.strip() for p in m.text.split("|")]
    if len(parts) < 2:
        return
    ADS_BTN_TEXT = parts[0]
    ADS_URL = parts[1]
    ADS_TEXT = parts[2] if len(parts) > 2 else ""
    ADS_ENABLED = True
    bot.send_message(m.chat.id, "✅ Ads enabled!")

@bot.message_handler(func=lambda m: m.text == "🗑 DELETE ADS")
def delete_ads(m):
    global ADS_ENABLED
    if not is_admin(m.from_user.id):
        return
    ADS_ENABLED = False
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
    ids = m.text.replace("\n", " ").split()
    added = 0
    for uid in ids:
        if uid.isdigit() and uid not in users:
            users[uid] = {
                "balance": 0.0, "blocked": 0.0, "ref": random_ref(),
                "bot_id": random_botid(), "invited": 0, "banned": False,
                "verified": False, "month": now_month()
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
    bot.send_message(m.chat.id, f"User: @{username}")

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
        bot.send_message(m.chat.id, f"👤 User Found\nID: {uid}")
    else:
        bot.send_message(m.chat.id, "❌ User not found")

@bot.message_handler(func=lambda m: m.text and "http" in m.text)
def handle_links(message):
    if bot_locked_guard(message):
        return
    user_id = message.from_user.id
    link = message.text
    
    if CHANNEL_WINDOW_OPEN and POST_CHANNELS:
        pending_links[user_id] = link
        send_multi_join(user_id)
        return

    bot.send_message(message.chat.id, "⏳ Downloading...")
    download_media(message.chat.id, link)

@bot.callback_query_handler(func=lambda call: call.data == "multi_checkjoin")
def multi_checkjoin(call):
    user_id = call.from_user.id
    bot.answer_callback_query(call.id, "✅ Join verified")
    if user_id in pending_links:
        link = pending_links[user_id]
        del pending_links[user_id]
        download_media(user_id, link)

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
    if not is_admin(m.from_user.id):
        return
    VERIFY_ENABLED = True
    bot.send_message(m.chat.id, "✅ Verify system enabled")

@bot.message_handler(func=lambda m: m.text == "❌ VERIFY OFF")
def verify_off(m):
    global VERIFY_ENABLED
    if not is_admin(m.from_user.id):
        return
    VERIFY_ENABLED = False
    bot.send_message(m.chat.id, "❌ Verify system disabled")

@bot.message_handler(func=lambda m: m.text == "CHANNEL POST")
def start_channel_post(m):
    if not is_admin(m.from_user.id):
        return
    bot.send_message(m.chat.id, "Send the main text for the channel post.")

@bot.message_handler(func=lambda m: m.text == "➕ ADD BALANCE")
def add_balance_start(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "Send ID and amount:")
    bot.register_next_step_handler(msg, add_balance_process)

def add_balance_process(m):
    if not is_admin(m.from_user.id):
        return
    try:
        parts = m.text.strip().split()
        uid = parts[0]
        amt = float(parts[1])
        users[uid]["balance"] += amt
        save_users()
        bot.send_message(m.chat.id, f"✅ Added ${amt:.2f}")
    except:
        bot.send_message(m.chat.id, "❌ Error")

@bot.message_handler(func=lambda m: m.text == "➖ REMOVE MONEY")
def remove_balance_start(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "Send ID and amount:")
    bot.register_next_step_handler(msg, remove_balance_process)

def remove_balance_process(m):
    if not is_admin(m.from_user.id):
        return
    try:
        parts = m.text.strip().split()
        uid = parts[0]
        amt = float(parts[1])
        users[uid]["balance"] -= amt
        save_users()
        bot.send_message(m.chat.id, f"✅ Removed ${amt:.2f}")
    except:
        bot.send_message(m.chat.id, "❌ Error")

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
    badge = get_vip_badge(uid)
    if badge:
        caption = f"{badge} VIP Download\n" + caption

    videos_data["total"] += 1
    videos_data["users"][uid] = videos_data["users"].get(uid, 0) + 1
    if platform:
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

        if "youtube.com" in url or "youtu.be" in url:
            ydl_opts = {"format": "bestvideo+bestaudio/best", "outtmpl": "youtube_%(id)s.%(ext)s", "quiet": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file = ydl.prepare_filename(info)
            send_video_with_music(chat_id, file, "youtube")
            return

        bot.send_message(chat_id, "❌ Unsupported link")
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
        subprocess.run(["ffmpeg", "-y", "-i", file_path, "-vn", "-acodec", "mp3", audio_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        with open(audio_path, "rb") as audio:
            bot.send_audio(call.message.chat.id, audio, caption=CAPTION_TEXT)
        bot.answer_callback_query(call.id, "🎵 Music converted")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Failed:\n{e}")

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
