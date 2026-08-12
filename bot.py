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
PREMIUM_DB_FILE = "premium_data.json"

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

# ================= PREMIUM SYSTEM DATA & STORAGE =================
# Default premium database structure
default_premium_data = {
    "plans": {
        "7": {"days": 7, "price": 50, "name": "7 Days", "active": True},
        "30": {"days": 30, "price": 150, "name": "30 Days", "active": True},
        "90": {"days": 90, "price": 400, "name": "90 Days", "active": True},
        "365": {"days": 365, "price": 1200, "name": "1 Year", "active": True}
    },
    "subscriptions": {}, # user_id -> {plan, start_date, expiry_date, payment_id}
    "payments": [],
    "referrals": {}, # user_id -> [referred_user_ids]
    "referral_rewards": {"3": 7, "5": 14, "10": 30, "25": 90, "50": 180, "100": 365},
    "feature_requests": [],
    "feature_votes": {}, # request_id -> [user_ids]
    "leaderboard_points": {}, # user_id -> points
    "missions": {
        "daily": [
            {"id": "d_download_5", "title": "Download 5 files", "target": 5, "reward_days": 1, "reward_points": 10},
            {"id": "d_vote_1", "title": "Vote on a feature", "target": 1, "reward_days": 0, "reward_points": 5}
        ],
        "weekly": [
            {"id": "w_invite_3", "title": "Invite 3 friends", "target": 3, "reward_days": 7, "reward_points": 50}
        ]
    },
    "mission_progress": {}, # user_id -> {mission_id: count}
    "completed_missions": {}, # user_id -> [mission_ids]
    "coupons": {
        "VIP50": {"reward_type": "days", "reward_value": 7, "max_uses": 100, "uses": 0, "active": True, "expiry": "2026-12-31"}
    },
    "coupon_usage": {}, # user_id -> [coupon_codes]
    "vip_identities": {}, # user_id -> {title, level}
    "download_history": {} # user_id -> [list of links/files]
}

premium_data = load_json(PREMIUM_DB_FILE, default_premium_data)

def save_premium_data():
    save_json(PREMIUM_DB_FILE, premium_data)

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

# ================= PREMIUM HELPER FUNCTIONS =================
def is_premium(user_id):
    uid = str(user_id)
    subs = premium_data.get("subscriptions", {})
    if uid in subs:
        expiry_str = subs[uid].get("expiry_date")
        try:
            expiry_dt = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
            if datetime.now() < expiry_dt:
                return True
            else:
                # Expired
                return False
        except:
            return False
    return False

def get_premium_status_text(user_id):
    uid = str(user_id)
    subs = premium_data.get("subscriptions", {})
    if uid in subs:
        expiry_str = subs[uid].get("expiry_date")
        try:
            expiry_dt = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
            if datetime.now() < expiry_dt:
                days_left = (expiry_dt - datetime.now()).days
                return True, subs[uid].get("plan"), expiry_str, max(1, days_left)
        except:
            pass
    return False, None, None, 0

def activate_premium_user(user_id, days, plan_name="Custom"):
    uid = str(user_id)
    subs = premium_data.get("subscriptions", {})
    
    current_expiry = None
    if uid in subs:
        try:
            curr_dt = datetime.strptime(subs[uid].get("expiry_date"), "%Y-%m-%d %H:%M:%S")
            if datetime.now() < curr_dt:
                current_expiry = curr_dt
        except:
            pass
            
    start_dt = datetime.now()
    if current_expiry:
        expiry_dt = current_expiry + timedelta(days=days)
    else:
        expiry_dt = start_dt + timedelta(days=days)
        
    subs[uid] = {
        "plan": plan_name,
        "start_date": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "expiry_date": expiry_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "active"
    }
    save_premium_data()

def remove_premium_user(user_id):
    uid = str(user_id)
    subs = premium_data.get("subscriptions", {})
    if uid in subs:
        subs.pop(uid)
        save_premium_data()
        return True
    return False

def add_points(user_id, points):
    uid = str(user_id)
    pts = premium_data.setdefault("leaderboard_points", {})
    pts[uid] = pts.get(uid, 0) + points
    save_premium_data()

def get_vip_title(user_id):
    uid = str(user_id)
    identities = premium_data.get("vip_identities", {})
    if uid in identities:
        return identities[uid].get("title", "PRO"), identities[uid].get("level", 1)
    # Default based on premium status
    if is_premium(uid):
        return "ELITE", 3
    return "VIP", 1

# ================= MENUS =================
def user_menu(show_admin=False):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📥 Downloader", "👑 Premium")
    kb.add("💰 BALANCE", "💸 WITHDRAWAL")
    kb.add("👥 REFERRAL", "🆔 GET ID")
    kb.add("☎️ CUSTOMER", "🤖CUSTOMER AI")
    kb.add("⚙️ Settings", "📊 Statistics")
    kb.add("🆘 Help")
    if show_admin:
        kb.add("👑 ADMIN PANEL")
    return kb

def admin_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("👑 PREMIUM CONTROL", "📊 STATS")
    kb.add("📢 BROADCAST", "➕ ADD BALANCE")
    kb.add("➖ REMOVE MONEY", "🚫 BAN USER MANUAL")
    kb.add("💳 WITHDRAWAL CHECK", "💰 UNBLOCK MONEY")
    kb.add("🔍 RAADI", "🔥 UN BAN-USER")
    kb.add("📌 POST CHANNEL", "👥 SEE LIST")
    kb.add("🔎 SEARCH USER", "📢 ADD ADS")
    kb.add("🗑 DELETE ADS", "✅ VERIFY ON")
    kb.add("❌ VERIFY OFF", "CHANNEL POST")
    kb.add("📡 ADD CHANNEL", "🔒 LOCK BOT")
    kb.add("🔓 UNLOCK BOT", "❌ CLOSE WINDOWS")
    kb.add("CLOSE CHANNEL POST", "📥 IMPORT USERS")
    kb.add("🔗 GET REFERRAL CODE", "🔙 BACK MAIN MENU")
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

    # Haddii user cusub, ku dar database
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
        # Referral reward
        if ref:
            ref_user = next((u for u, d in users.items() if d["ref"] == ref), None)
            if ref_user and ref_user != str(uid):
                users[ref_user]["balance"] += 0.2
                users[ref_user]["invited"] += 1
                
                # Premium referral tracking
                ref_list = premium_data.setdefault("referrals", {})
                ref_list.setdefault(ref_user, []).append(str(uid))
                
                # Check milestones for referral rewards
                inv_count = len(ref_list[ref_user])
                milestones = premium_data.get("referral_rewards", {})
                if str(inv_count) in milestones:
                    days_reward = milestones[str(inv_count)]
                    activate_premium_user(ref_user, days_reward, f"Referral Milestone ({inv_count})")
                    try:
                        bot.send_message(int(ref_user), f"🎁 Congratulations! You reached {inv_count} referrals and unlocked {days_reward} Days of VIP Premium!")
                    except:
                        pass

                try:
                    bot.send_message(int(ref_user), "🎉 You earned $0.2 and referral progress from invite!")
                except:
                    pass

        save_users()
        save_premium_data()

    # Hubinta join
    check_membership(uid)

@bot.message_handler(commands=['view'])
def view_cmd(message):
    bot.send_message(
        message.chat.id,
        "🤖 BOT INFO\n\n"
        "📌 Name: VIP Video Downloader Bot\n"
        "⚡ Features:\n"
        "• TikTok download\n"
        "• YouTube download\n"
        "• Facebook download\n"
        "• Pinterest download\n"
        "• VIP Membership & Stars\n"
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

    bot.send_message(m.chat.id,
        f"🔗 Your referral link:\n{link}\n\n"
        "Earn money & VIP days by inviting friends!"
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
        msg.message_id,
        parse_mode="HTML"
    )

# ================= PREMIUM CENTER & MENUS (USER) =================
@bot.message_handler(func=lambda m: m.text in ["👑 Premium", "👑 PREMIUM"])
def premium_center_handler(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    uid = str(m.from_user.id)
    active, plan_name, expiry, days_left = get_premium_status_text(uid)
    
    if active:
        text = (
            "╭━━━━━━━━━━━━━━━━━━━━━━╮\n"
            "       👑 <b>VIP PREMIUM CENTER</b>\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
            "⭐ <b>STATUS:</b> ACTIVE\n"
            f"💎 <b>PLAN:</b> {plan_name}\n"
            f"📅 <b>EXPIRES:</b> {expiry}\n"
            f"⏳ <b>DAYS LEFT:</b> {days_left}\n\n"
            "✨ Welcome to the VIP experience!"
        )
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("⭐ BUY / EXTEND", callback_data="prem_buy_menu"),
            InlineKeyboardButton("💎 MY PLAN", callback_data="prem_my_plan")
        )
        kb.add(
            InlineKeyboardButton("🎁 INVITE", callback_data="prem_invite"),
            InlineKeyboardButton("💡 REQUESTS", callback_data="prem_requests")
        )
        kb.add(
            InlineKeyboardButton("🏆 LEADERBOARD", callback_data="prem_leaderboard"),
            InlineKeyboardButton("🎯 MISSIONS", callback_data="prem_missions")
        )
        kb.add(
            InlineKeyboardButton("🎟 COUPONS", callback_data="prem_coupons"),
            InlineKeyboardButton("🎁 GIFT", callback_data="prem_gift")
        )
        kb.add(
            InlineKeyboardButton("👑 VIP IDENTITY", callback_data="prem_identity"),
            InlineKeyboardButton("📊 STATISTICS", callback_data="prem_stats")
        )
        kb.add(InlineKeyboardButton("🏠 HOME", callback_data="prem_home"))
        bot.send_message(m.chat.id, text, reply_markup=kb, parse_mode="HTML")
    else:
        text = (
            "╭━━━ 👑 <b>GO PREMIUM</b> ━━━╮\n\n"
            "🚀 Unlock powerful VIP features.\n\n"
            "⭐ Priority access & higher limits\n"
            "🎁 Rewards & Referral perks\n"
            "🏆 VIP ranking & missions\n"
            "💡 Feature voting & coupons\n"
            "👑 VIP identity & custom look\n\n"
            "Ready to upgrade your experience?\n"
            "╰━━━━━━━━━━━━━━━━━━━━╯"
        )
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("⭐ UNLOCK PREMIUM NOW", callback_data="prem_buy_menu"))
        kb.add(InlineKeyboardButton("🎟 REDEEM COUPON", callback_data="prem_coupons"))
        kb.add(InlineKeyboardButton("🏠 HOME", callback_data="prem_home"))
        bot.send_message(m.chat.id, text, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("prem_"))
def premium_callbacks(call):
    uid = str(call.from_user.id)
    data = call.data
    
    if data == "prem_home":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "🏠 Home Menu", reply_markup=user_menu(is_admin(uid)))
        
    elif data == "prem_buy_menu":
        plans = premium_data.get("plans", {})
        kb = InlineKeyboardMarkup(row_width=2)
        for key, p in plans.items():
            if p.get("active", True):
                kb.add(InlineKeyboardButton(f"⭐ {p['name']} — {p['price']} Stars", callback_data=f"buyplan_{key}"))
        kb.add(InlineKeyboardButton("🔙 BACK", callback_data="prem_back_center"))
        
        bot.edit_message_text(
            "👑 <b>CHOOSE VIP PLAN</b>\n\nSelect your preferred subscription plan to unlock instant VIP features via Telegram Stars.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb,
            parse_mode="HTML"
        )
        
    elif data == "prem_back_center":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        # Re-trigger premium center message
        m_chat = call.message.chat.id
        active, plan_name, expiry, days_left = get_premium_status_text(uid)
        if active:
            text = f"👑 <b>VIP PREMIUM CENTER</b>\n\n⭐ STATUS: ACTIVE\n💎 PLAN: {plan_name}\n📅 EXPIRES: {expiry}\n⏳ DAYS LEFT: {days_left}"
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(InlineKeyboardButton("⭐ BUY / EXTEND", callback_data="prem_buy_menu"), InlineKeyboardButton("💎 MY PLAN", callback_data="prem_my_plan"))
            kb.add(InlineKeyboardButton("🎁 INVITE", callback_data="prem_invite"), InlineKeyboardButton("💡 REQUESTS", callback_data="prem_requests"))
            kb.add(InlineKeyboardButton("🏆 LEADERBOARD", callback_data="prem_leaderboard"), InlineKeyboardButton("🎯 MISSIONS", callback_data="prem_missions"))
            kb.add(InlineKeyboardButton("🎟 COUPONS", callback_data="prem_coupons"), InlineKeyboardButton("🎁 GIFT", callback_data="prem_gift"))
            kb.add(InlineKeyboardButton("👑 VIP IDENTITY", callback_data="prem_identity"), InlineKeyboardButton("📊 STATISTICS", callback_data="prem_stats"))
            kb.add(InlineKeyboardButton("🏠 HOME", callback_data="prem_home"))
            bot.send_message(m_chat, text, reply_markup=kb, parse_mode="HTML")
        else:
            text = "👑 <b>GO PREMIUM</b>\n\nUnlock powerful VIP features instantly."
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("⭐ UNLOCK PREMIUM NOW", callback_data="prem_buy_menu"))
            kb.add(InlineKeyboardButton("🏠 HOME", callback_data="prem_home"))
            bot.send_message(m_chat, text, reply_markup=kb, parse_mode="HTML")

    elif data.startswith("buyplan_"):
        plan_key = data.split("_")[1]
        plans = premium_data.get("plans", {})
        if plan_key not in plans:
            bot.answer_callback_query(call.id, "❌ Plan not available", show_alert=True)
            return
        p = plans[plan_key]
        title = f"VIP Membership ({p['name']})"
        description = f"Unlock {p['name']} of VIP Downloader Membership with priority processing and exclusive features."
        currency = "XTR" # Telegram Stars
        prices = [LabeledPrice(label=p['name'], amount=p['price'])]
        
        try:
            bot.send_invoice(
                chat_id=call.message.chat.id,
                title=title,
                description=description,
                invoice_payload=f"premium_{plan_key}_{uid}_{int(time.time())}",
                provider_token="",
                currency=currency,
                prices=prices,
                start_parameter="vip_sub"
            )
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Invoice error: {e}", show_alert=True)

    elif data == "prem_my_plan":
        active, plan_name, expiry, days_left = get_premium_status_text(uid)
        title_name, level = get_vip_title(uid)
        text = (
            f"💎 <b>MY VIP PLAN DETAILS</b>\n\n"
            f"👤 User: @{call.from_user.username or 'User'}\n"
            f"⭐ Status: {'ACTIVE ✅' if active else 'FREE ❌'}\n"
            f"📦 Plan: {plan_name or 'None'}\n"
            f"📅 Expires: {expiry or 'N/A'}\n"
            f"⏳ Days Left: {days_left}\n"
            f"👑 Title: {title_name} (Lvl {level})"
        )
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 BACK", callback_data="prem_back_center"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

    elif data == "prem_invite":
        bot_username = bot.get_me().username
        ref_code = users.get(uid, {}).get("ref", "12345")
        link = f"https://t.me/{bot_username}?start={ref_code}"
        ref_count = len(premium_data.get("referrals", {}).get(uid, []))
        text = (
            f"╭━━━ 🎁 <b>INVITE & EARN</b> ━━━╮\n\n"
            f"👥 REFERRALS: {ref_count}\n"
            f"🎁 REWARDS: VIP Days & Stars\n"
            f"🔗 Link:\n<code>{link}</code>\n\n"
            "Invite friends and unlock milestones!"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯"
        )
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("📤 SHARE LINK", url=f"https://t.me/share/url?url={link}&text=Download%20videos%20instantly%20with%20VIP%20speed!"))
        kb.add(InlineKeyboardButton("🔙 BACK", callback_data="prem_back_center"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

    elif data == "prem_requests":
        requests_list = premium_data.get("feature_requests", [])
        text = "╭━━━ 💡 <b>FEATURE REQUESTS</b> ━━━╮\n\n🔥 <b>MOST REQUESTED</b>\n"
        if not requests_list:
            text += "\nNo feature requests yet. Submit yours!"
        else:
            sorted_reqs = sorted(requests_list, key=lambda x: x.get("votes", 0), reverse=True)
            for idx, req in enumerate(sorted_reqs[:5], start=1):
                text += f"\n{idx}️⃣ {req['title']}\n👍 {req.get('votes', 0)} | Status: {req.get('status', 'Pending')}"
        text += "\n\n╰━━━━━━━━━━━━━━━━━━━━━━╯"
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("💡 SUBMIT REQUEST", callback_data="prem_submit_req"))
        kb.add(InlineKeyboardButton("🔙 BACK", callback_data="prem_back_center"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

    elif data == "prem_submit_req":
        msg = bot.send_message(call.message.chat.id, "💡 Send your feature request title and description:\n\nFormat:\n`Title | Description`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_feature_request_step)

    elif data == "prem_leaderboard":
        pts = premium_data.get("leaderboard_points", {})
        sorted_lb = sorted(pts.items(), key=lambda x: x[1], reverse=True)
        text = "╭━━━ 🏆 <b>VIP LEADERBOARD</b> ━━━╮\n\n"
        for i, (u, p) in enumerate(sorted_lb[:5], start=1):
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            medal = medals.get(i, f"{i}️⃣")
            text += f"{medal} User {u[:4]}... — <b>{p} pts</b>\n"
        user_pts = pts.get(uid, 0)
        user_rank = "N/A"
        for idx, (u, p) in enumerate(sorted_lb, start=1):
            if u == uid:
                user_rank = f"#{idx}"
                break
        text += f"\n━━━━━━━━━━━━━━━━━━━━\n⭐ <b>YOU</b>\nRANK: {user_rank}\nPOINTS: {user_pts}\n╰━━━━━━━━━━━━━━━━━━━━━━╯"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 BACK", callback_data="prem_back_center"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

    elif data == "prem_missions":
        missions = premium_data.get("missions", {})
        text = "╭━━━ 🎯 <b>VIP MISSIONS</b> ━━━╮\n\n"
        for m_cat in ["daily", "weekly"]:
            text += f"📌 <b>{m_cat.upper()} MISSIONS</b>\n"
            for m_item in missions.get(m_cat, []):
                prog = premium_data.get("mission_progress", {}).get(uid, {}).get(m_item["id"], 0)
                target = m_item["target"]
                completed = m_item["id"] in premium_data.get("completed_missions", {}).get(uid, [])
                status_icon = "✅" if completed else f"{prog}/{target}"
                text += f"• {m_item['title']}: [{status_icon}]\n"
        text += "\n╰━━━━━━━━━━━━━━━━━━━━━━╯"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 BACK", callback_data="prem_back_center"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

    elif data == "prem_coupons":
        msg = bot.send_message(call.message.chat.id, "🎟 Please send your VIP Coupon Code:")
        bot.register_next_step_handler(msg, process_coupon_redeem)

    elif data == "prem_gift":
        msg = bot.send_message(call.message.chat.id, "🎁 Enter recipient Telegram Username or ID to gift Premium:")
        bot.register_next_step_handler(msg, process_gift_username)

    elif data == "prem_identity":
        title_name, level = get_vip_title(uid)
        text = (
            f"╭━━━ 👑 <b>VIP IDENTITY</b> ━━━╮\n\n"
            f"👤 User: @{call.from_user.username or 'VIP'}\n"
            f"💎 TITLE: {title_name}\n"
            f"🔥 LEVEL: {level}\n"
            f"🏆 POINTS: {premium_data.get('leaderboard_points', {}).get(uid, 0)}\n\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯"
        )
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 BACK", callback_data="prem_back_center"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

    elif data == "prem_stats":
        downloads = videos_data.get("users", {}).get(uid, 0)
        refs = len(premium_data.get("referrals", {}).get(uid, []))
        pts = premium_data.get("leaderboard_points", {}).get(uid, 0)
        text = (
            f"╭━━━ 📊 <b>MY STATISTICS</b> ━━━╮\n\n"
            f"📥 Downloads: {downloads}\n"
            f"🎁 Referrals: {refs}\n"
            f"🏆 Points: {pts}\n"
            f"⭐ VIP Status: {'Active' if is_premium(uid) else 'Free'}\n"
            f"╰━━━━━━━━━━━━━━━━━━━━━━╯"
        )
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 BACK", callback_data="prem_back_center"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

# ================= TELEGRAM STARS PRE-CHECKOUT & SUCCESS =================
@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout_pre_checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def successful_payment_handler(message):
    payment_info = message.successful_payment
    payload = payment_info.invoice_payload
    uid = str(message.from_user.id)
    
    if payload.startswith("premium_"):
        parts = payload.split("_")
        plan_key = parts[1]
        plans = premium_data.get("plans", {})
        if plan_key in plans:
            days = plans[plan_key]["days"]
            plan_name = plans[plan_key]["name"]
            activate_premium_user(uid, days, plan_name)
            
            # Record payment
            payments = premium_data.setdefault("payments", [])
            payments.append({
                "user_id": uid,
                "plan": plan_name,
                "stars": payment_info.total_amount,
                "payment_id": payment_info.telegram_payment_charge_id,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            save_premium_data()
            
            bot.send_message(
                message.chat.id,
                f"🎉 <b>PREMIUM ACTIVATED!</b>\n\n"
                f"Welcome to the VIP Club 👑\n"
                f"💎 Plan: {plan_name}\n"
                f"⏳ Enjoy priority processing and all VIP features!",
                parse_mode="HTML"
            )

# ================= FEATURE REQUEST STEP =================
def process_feature_request_step(message):
    uid = str(message.from_user.id)
    text = message.text.strip()
    if "|" not in text:
        bot.send_message(message.chat.id, "❌ Invalid format. Please use: `Title | Description`", parse_mode="Markdown")
        return
    title, desc = text.split("|", 1)
    reqs = premium_data.setdefault("feature_requests", [])
    req_id = str(uuid.uuid4())[:8]
    reqs.append({
        "request_id": req_id,
        "user_id": uid,
        "title": title.strip(),
        "description": desc.strip(),
        "votes": 1,
        "status": "Pending",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    votes = premium_data.setdefault("feature_votes", {})
    votes[req_id] = [uid]
    save_premium_data()
    bot.send_message(message.chat.id, "✅ Feature request submitted successfully!")

# ================= COUPON REDEEM STEP =================
def process_coupon_redeem(message):
    uid = str(message.from_user.id)
    code = message.text.strip()
    coupons = premium_data.get("coupons", {})
    
    if code not in coupons or not coupons[code].get("active", True):
        bot.send_message(message.chat.id, "❌ Invalid or expired coupon code.")
        return
        
    c_data = coupons[code]
    used_users = premium_data.setdefault("coupon_usage", {})
    if uid in used_users.get(code, []):
        bot.send_message(message.chat.id, "❌ You have already redeemed this coupon.")
        return
        
    if c_data.get("uses", 0) >= c_data.get("max_uses", 999):
        bot.send_message(message.chat.id, "❌ Coupon usage limit reached.")
        return
        
    # Apply reward
    if c_data["reward_type"] == "days":
        activate_premium_user(uid, c_data["reward_value"], f"Coupon ({code})")
        
    c_data["uses"] = c_data.get("uses", 0) + 1
    used_users.setdefault(code, []).append(uid)
    save_premium_data()
    
    bot.send_message(message.chat.id, f"✅ Coupon redeemed successfully! Enjoy your VIP reward 👑")

# ================= GIFT PREMIUM STEP =================
def process_gift_username(message):
    uid = str(message.from_user.id)
    target = message.text.replace("@", "").strip()
    
    recipient_id = None
    for u, d in users.items():
        if d.get("username", "").lower() == target.lower():
            recipient_id = u
            break
            
    if not recipient_id:
        bot.send_message(message.chat.id, "❌ Recipient user not found in bot database. They must start the bot first.")
        return
        
    # Ask for plan
    plans = premium_data.get("plans", {})
    kb = InlineKeyboardMarkup(row_width=2)
    for key, p in plans.items():
        if p.get("active", True):
            kb.add(InlineKeyboardButton(f"🎁 Gift {p['name']} ({p['price']} Stars)", callback_data=f"giftplan_{recipient_id}_{key}"))
            
    bot.send_message(message.chat.id, f"🎁 Select plan to gift to @{target}:", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("giftplan_"))
def gift_plan_callback(call):
    parts = call.data.split("_")
    recipient_id = parts[1]
    plan_key = parts[2]
    p = premium_data.get("plans", {}).get(plan_key)
    if not p:
        return
        
    # Send invoice for gifting
    title = f"Gift VIP Membership ({p['name']})"
    description = f"Gift {p['name']} of VIP membership to user {recipient_id}"
    currency = "XTR"
    prices = [LabeledPrice(label=p['name'], amount=p['price'])]
    
    try:
        bot.send_invoice(
            chat_id=call.message.chat.id,
            title=title,
            description=description,
            invoice_payload=f"gift_{recipient_id}_{plan_key}_{int(time.time())}",
            provider_token="",
            currency=currency,
            prices=prices,
            start_parameter="gift_vip"
        )
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Error: {e}", show_alert=True)

# ================= ADVANCED ADMIN PREMIUM CONTROL PANEL =================
@bot.message_handler(func=lambda m: m.text == "👑 PREMIUM CONTROL")
def admin_premium_control_menu(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ You are not admin")
        return
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("👑 Manage Users", callback_data="adm_prem_users"),
        InlineKeyboardButton("🎟 Manage Coupons", callback_data="adm_prem_coupons")
    )
    kb.add(
        InlineKeyboardButton("📊 Analytics", callback_data="adm_prem_analytics"),
        InlineKeyboardButton("⚙️ Plans Config", callback_data="adm_prem_plans")
    )
    kb.add(InlineKeyboardButton("🔙 Admin Panel", callback_data="adm_back_main"))
    
    bot.send_message(m.chat.id, "╭━━━ 👨‍💼 <b>PREMIUM CONTROL</b> ━━━╮\n\nManage VIP memberships, coupons, stats, and user subscriptions securely.\n╰━━━━━━━━━━━━━━━━━━━━━━╯", reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_"))
def admin_premium_callbacks(call):
    if not is_admin(call.from_user.id):
        return
    data = call.data
    
    if data == "adm_prem_analytics":
        total_users = len(users)
        active_prem = len(premium_data.get("subscriptions", {}))
        payments = premium_data.get("payments", [])
        total_stars = sum(p.get("stars", 0) for p in payments)
        
        text = (
            f"╭━━━ 📊 <b>PREMIUM ANALYTICS</b> ━━━╮\n\n"
            f"👥 Total Users: {total_users}\n"
            f"👑 Active Premium: {active_prem}\n"
            f"⭐ Total Stars Collected: {total_stars}\n"
            f"💳 Total Transactions: {len(payments)}\n"
            f"╰━━━━━━━━━━━━━━━━━━━━━━╯"
        )
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 BACK", callback_data="adm_back_control"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
        
    elif data == "adm_back_control":
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("👑 Manage Users", callback_data="adm_prem_users"),
            InlineKeyboardButton("🎟 Manage Coupons", callback_data="adm_prem_coupons")
        )
        kb.add(
            InlineKeyboardButton("📊 Analytics", callback_data="adm_prem_analytics"),
            InlineKeyboardButton("⚙️ Plans Config", callback_data="adm_prem_plans")
        )
        bot.edit_message_text("╭━━━ 👨‍💼 <b>PREMIUM CONTROL</b> ━━━╮", call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

    elif data == "adm_prem_users":
        msg = bot.send_message(call.message.chat.id, "👤 Send Telegram ID or Username to manage user premium:")
        bot.register_next_step_handler(msg, admin_search_user_step)
        
    elif data == "adm_prem_coupons":
        coupons = premium_data.get("coupons", {})
        text = "🎟 <b>COUPON MANAGEMENT</b>\n\n"
        for code, c in coupons.items():
            text += f"• Code: <code>{code}</code> | Uses: {c.get('uses',0)}/{c.get('max_uses',0)} | Active: {c.get('active')}\n"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("➕ CREATE COUPON", callback_data="adm_create_coupon"))
        kb.add(InlineKeyboardButton("🔙 BACK", callback_data="adm_back_control"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)

    elif data == "adm_create_coupon":
        msg = bot.send_message(call.message.chat.id, "➕ Send new coupon info in format:\n`CODE | DAYS | MAX_USES`\n\nExample:\n`SUMMER2026 | 30 | 500`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_admin_create_coupon)

def admin_search_user_step(message):
    if not is_admin(message.from_user.id):
        return
    query = message.text.replace("@", "").strip()
    target_id = query if query in users else find_user_by_botid(query)
    
    if not target_id:
        for u, d in users.items():
            if d.get("username", "").lower() == query.lower():
                target_id = u
                break
                
    if not target_id or target_id not in users:
        bot.send_message(message.chat.id, "❌ User not found.")
        return
        
    active, plan_name, expiry, days_left = get_premium_status_text(target_id)
    text = (
        f"╭━━━ 👤 <b>USER PROFILE</b> ━━━╮\n\n"
        f"👤 Username: @{users[target_id].get('username', 'N/A')}\n"
        f"🆔 ID: <code>{target_id}</code>\n\n"
        f"⭐ Premium: {'ACTIVE ✅' if active else 'INACTIVE ❌'}\n"
        f"💎 Plan: {plan_name or 'None'}\n"
        f"⏰ Expires: {expiry or 'N/A'}\n"
        f"🎁 Referrals: {len(premium_data.get('referrals', {}).get(target_id, []))}\n"
        f"🏆 Points: {premium_data.get('leaderboard_points', {}).get(target_id, 0)}\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━╯"
    )
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("👑 GIVE 30 DAYS", callback_data=f"adm_giveprem_{target_id}_30"),
        InlineKeyboardButton("❌ REMOVE PREMIUM", callback_data=f"adm_remprem_{target_id}")
    )
    kb.add(InlineKeyboardButton("➕ EXTEND 30 DAYS", callback_data=f"adm_extend_{target_id}_30"))
    bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_giveprem_") or call.data.startswith("adm_remprem_") or call.data.startswith("adm_extend_"))
def admin_user_action_callback(call):
    if not is_admin(call.from_user.id):
        return
    parts = call.data.split("_")
    action = parts[1]
    uid = parts[2]
    
    if action == "giveprem":
        days = int(parts[3])
        activate_premium_user(uid, days, f"Admin Gift ({days}d)")
        bot.answer_callback_query(call.id, f"✅ Granted {days} days premium!", show_alert=True)
        try:
            bot.send_message(int(uid), f"👑 Admin activated {days} Days of VIP Premium for you!")
        except:
            pass
    elif action == "remprem":
        remove_premium_user(uid)
        bot.answer_callback_query(call.id, "✅ Premium removed!", show_alert=True)
        try:
            bot.send_message(int(uid), "❌ Your VIP Premium membership was removed by admin.")
        except:
            pass
    elif action == "extend":
        days = int(parts[3])
        activate_premium_user(uid, days, "Admin Extension")
        bot.answer_callback_query(call.id, f"✅ Extended by {days} days!", show_alert=True)

def process_admin_create_coupon(message):
    if not is_admin(message.from_user.id):
        return
    try:
        parts = [p.strip() for p in message.text.split("|")]
        code = parts[0].upper()
        days = int(parts[1])
        max_uses = int(parts[2])
        
        coupons = premium_data.setdefault("coupons", {})
        coupons[code] = {
            "reward_type": "days",
            "reward_value": days,
            "max_uses": max_uses,
            "uses": 0,
            "active": True,
            "expiry": "2026-12-31"
        }
        save_premium_data()
        bot.send_message(message.chat.id, f"✅ Coupon <code>{code}</code> created successfully!", parse_mode="HTML")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error creating coupon: {e}")

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
        f"🎁 You earn rewards & VIP perks per referral!"
    )

@bot.message_handler(func=lambda m: m.text == "☎️ CUSTOMER")
def customer_handler(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    bot.send_message(
        m.chat.id,
        "☎️ Customer Support:\n@scholes1"
    )

@bot.message_handler(func=lambda m: m.text == "🤖CUSTOMER AI")
def customer_ai_handler(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    bot.send_message(
        m.chat.id,
        "Ai Customer Support🤖:\n@Aidownoaderbot"
    )

@bot.message_handler(func=lambda m: m.text == "⚙️ Settings")
def settings_handler(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    uid = str(m.from_user.id)
    active, plan_name, expiry, days_left = get_premium_status_text(uid)
    text = (
        f"⚙️ <b>USER SETTINGS & PREFERENCES</b>\n\n"
        f"⭐ VIP Membership: {'ACTIVE ✅' if active else 'FREE ❌'}\n"
        f"📥 Default Quality: Best Available\n"
        f"🎵 Audio Extraction: Enabled\n"
        f"🔔 Notifications: Enabled"
    )
    bot.send_message(m.chat.id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "📊 Statistics")
def statistics_handler(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    uid = str(m.from_user.id)
    downloads = videos_data.get("users", {}).get(uid, 0)
    refs = len(premium_data.get("referrals", {}).get(uid, []))
    pts = premium_data.get("leaderboard_points", {}).get(uid, 0)
    text = (
        f"╭━━━ 📊 <b>MY STATISTICS</b> ━━━╮\n\n"
        f"📥 Downloads: {downloads}\n"
        f"🎁 Referrals: {refs}\n"
        f"🏆 Points: {pts}\n"
        f"⭐ VIP Status: {'Active' if is_premium(uid) else 'Free'}\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━╯"
    )
    bot.send_message(m.chat.id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "🆘 Help")
def help_handler(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    bot.send_message(
        m.chat.id,
        "🆘 <b>HELP & SUPPORT</b>\n\n"
        "Send any media link from TikTok, Instagram, YouTube, Facebook, or Pinterest to download.\n"
        "Use /start to check menu options or click 👑 Premium for VIP benefits.",
        parse_mode="HTML"
    )

@bot.message_handler(func=lambda m: m.text == "📥 Downloader")
def downloader_menu_handler(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    bot.send_message(m.chat.id, "📥 <b>DOWNLEDER READY</b>\n\nSend any video or photo link to begin downloading instantly.", parse_mode="HTML")

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
    active_prem = len(premium_data.get("subscriptions", {}))

    msg = (
        f"📊 BOT STATS\n\n"
        f"👥 Total Users: {total_users}\n"
        f"👑 Active Premium: {active_prem}\n"
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
    bot.send_message(m.chat.id, f"🔒 Bot locked successfully.")

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
    msg = bot.send_message(m.chat.id, "✍️ Geli xayeysiiska qaabkan:\n`Button Name | Link | Qoraal`", parse_mode="Markdown")
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
    ADS_TEXT = parts[2] if len(parts) > 2 else "✨ Nagala soco baraha bulshada!"
    ADS_ENABLED = True
    bot.send_message(m.chat.id, "✅ Ads saved and enabled!")

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
    ids = m.text.strip().replace("\n", " ").split()
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
    msg = bot.send_message(m.chat.id, "Send user username:\n@username")
    bot.register_next_step_handler(msg, get_ref_username)

def get_ref_username(m):
    if not is_admin(m.from_user.id):
        return
    username = m.text.replace("@", "").strip()
    msg = bot.send_message(m.chat.id, f"User: @{username}\nNow send referral code number:")
    bot.register_next_step_handler(msg, lambda x: save_custom_ref_code(x, username))

def save_custom_ref_code(m, username):
    if not is_admin(m.from_user.id):
        return
    code = m.text.strip()
    user_id = next((u for u, d in users.items() if d.get("username","").lower() == username.lower()), None)
    if not user_id:
        bot.send_message(m.chat.id, "❌ User not found")
        return
    users[user_id]["ref"] = code
    save_users()
    bot.send_message(m.chat.id, f"✅ Referral code updated for @{username}")

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

# ================= CHECKING DOWNLOAD =================
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
        kb.add(InlineKeyboardButton("🤖 Verify via Bot", url=f"https://t.me/Verifyd_bot?start={code}"))
        kb.add(InlineKeyboardButton("📧 Verify via Gmail", callback_data="verify_email"))
        bot.send_message(message.chat.id, "🔐 Verification Required\n\nChoose verification method:", reply_markup=kb)
        return

    # Mission progress tracking for download
    m_prog = premium_data.setdefault("mission_progress", {}).setdefault(str(user_id), {})
    m_prog["d_download_5"] = m_prog.get("d_download_5", 0) + 1
    save_premium_data()

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
    msg = bot.send_message(m.chat.id, "Send button like:\nButton Name | Text when clicked\n\nSend DONE when finished.")
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
        name, content = m.text.split("|", 1)
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
    if not data:
        return
    text = data["buttons"][index]["content"]
    kb = InlineKeyboardMarkup()
    for i, btn in enumerate(data["buttons"]):
        kb.add(InlineKeyboardButton(btn["name"], callback_data=f"postbtn_{i}"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "➕ ADD BALANCE")
def add_balance_start(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ You are not admin")
        return
    msg = bot.send_message(m.chat.id, "Send BOT ID or Telegram ID and amount separated by space:")
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
        bot.send_message(m.chat.id, f"✅ Added ${amt:.2f} to user {uid}")
        bot.send_message(int(uid), f"💰 Your balance increased by ${amt:.2f}")
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "➖ REMOVE MONEY")
def remove_balance_start(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ You are not admin")
        return
    msg = bot.send_message(m.chat.id, "Send BOT ID or Telegram ID and amount separated by space:")
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
        bot.send_message(m.chat.id, f"✅ Removed ${amt:.2f} from user {uid}")
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
        save_users()
        link = data["link"]
        del verify_pending[uid]
        bot.send_message(m.chat.id, "✅ Verification successful\n⬇️ Downloading video...")
        download_media(m.chat.id, link)
    else:
        bot.send_message(m.chat.id, "❌ Wrong verification code")

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

        if "snapchat.com" in url or "snap.com" in url:
            try:
                ydl_opts = {"format": "best", "outtmpl": "snapchat_%(id)s.%(ext)s", "quiet": True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    file = ydl.prepare_filename(info)
                send_video_with_music(chat_id, file, "snapchat")
                return
            except Exception as e:
                bot.send_message(chat_id, f"❌ Snapchat error:\n{e}")
                return

        if "pin.it" in url:
            try:
                r = requests.head(url, allow_redirects=True, timeout=10)
                url = r.url
            except:
                pass

        if "pinterest.com" in url:
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
                return
            except Exception as e:
                bot.send_message(chat_id, f"❌ Pinterest error:\n{e}")
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
                info = ydl.extract_info(url, download=True)
                file = ydl.prepare_filename(info)
            send_video_with_music(chat_id, file, "youtube")
            return

        bot.send_message(chat_id, "❌ Unsupported link")
    except Exception:
        bot.send_message(chat_id, "❌ Incorrect link format or unsupported platform.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("msguser|"))
def message_user(call):
    if not is_admin(call.from_user.id):
        return
    uid = call.data.split("|")[1]
    msg = bot.send_message(call.message.chat.id, "Send message for user")
    bot.register_next_step_handler(msg, send_user_message, uid)

def send_user_message(m, uid):
    if not is_admin(m.from_user.id):
        return
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
    audio_path = file_path.rsplit(".", 1)[0] + ".mp3"

    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", file_path, "-vn", "-acodec", "mp3", "-ab", "128k", "-ar", "44100", audio_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
        )
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📢 BOT CHANNEL", url="https://t.me/tiktokvediodownload"))

        with open(audio_path, "rb") as audio:
            bot.send_audio(call.message.chat.id, audio, title="Converted Music", performer="DownloadBot", caption=CAPTION_TEXT, reply_markup=kb)

        if os.path.exists(audio_path):
            os.remove(audio_path)
        if os.path.exists(file_path):
            os.remove(file_path)

        bot.answer_callback_query(call.id, "🎵 Music converted")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Music conversion failed:\n{e}")

@bot2.message_handler(commands=['start'])
def verify_start(m):
    args = m.text.split()
    if len(args) > 1:
        code = args[1]
        bot2.send_message(m.chat.id, f"🔑 Your verification code:\n\n{code}\n\nCopy this code and send it to the downloader bot.")

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

def run_support_bot():
    while True:
        try:
            subprocess.call(["python", "support_bot.py"])
        except Exception as e:
            print("Support Bot restart:", e)
            time.sleep(5)

if __name__ == "__main__":
    tg_client.start()

    t1 = threading.Thread(target=run_bot1)
    t2 = threading.Thread(target=run_bot2)
    t3 = threading.Thread(target=run_support_bot)

    t1.start()
    t2.start()
    t3.start()

    t1.join()
    t2.join()
    t3.join()
