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
FEATURES_FILE = "features.json"
MISSIONS_FILE = "missions.json"
COUPONS_FILE = "coupons.json"
PAYMENTS_FILE = "payments.json"

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
features_data = load_json(FEATURES_FILE, [])
missions_data = load_json(MISSIONS_FILE, {
    "milestones": [3, 5, 10, 25, 50],
    "missions_list": [
        {"id": "download_10", "title": "📥 Download 10 Files", "target": 10, "reward_days": 1},
        {"id": "invite_3", "title": "🎁 Invite 3 Friends", "target": 3, "reward_days": 2},
        {"id": "vote_3", "title": "👍 Vote on 3 Features", "target": 3, "reward_days": 1}
    ]
})
coupons_data = load_json(COUPONS_FILE, {})
payments_data = load_json(PAYMENTS_FILE, [])

def save_users():
    save_json(USERS_FILE, users)

def save_withdraws():
    save_json(WITHDRAWS_FILE, withdraws)

def save_features():
    save_json(FEATURES_FILE, features_data)

def save_missions():
    save_json(MISSIONS_FILE, missions_data)

def save_coupons():
    save_json(COUPONS_FILE, coupons_data)

def save_payments():
    save_json(PAYMENTS_FILE, payments_data)

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

def check_premium_status(uid):
    uid_str = str(uid)
    if uid_str not in users:
        return False
    user = users[uid_str]
    if user.get("premium_active", False):
        expiry_str = user.get("premium_expiry")
        if expiry_str:
            try:
                expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
                if datetime.now() > expiry_date:
                    user["premium_active"] = False
                    user["premium_plan"] = None
                    save_users()
                    try:
                        bot.send_message(
                            int(uid),
                            "⏰ <b>Your Premium has expired.</b>\n\n⭐ Renew now to continue enjoying VIP features.",
                            parse_mode="HTML"
                        )
                    except:
                        pass
                    return False
                return True
            except:
                return False
    return False

def get_user_points(uid):
    uid_str = str(uid)
    if uid_str not in users:
        return 0
    u = users[uid_str]
    pts = 0
    pts += u.get("invited", 0) * 10
    pts += len(u.get("completed_missions", [])) * 15
    if u.get("premium_active", False):
        pts += 50
    return pts

def get_user_rank(uid):
    uid_str = str(uid)
    all_users = []
    for u_id, u_data in users.items():
        all_users.append((u_id, get_user_points(u_id)))
    all_users.sort(key=lambda x: x[1], reverse=True)
    for idx, (u_id, pts) in enumerate(all_users, start=1):
        if u_id == uid_str:
            return idx
    return len(all_users) + 1

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
    kb.add("👑 Premium Mgmt", "💳 Stars Payments")
    kb.add("🎁 Ref Mgmt", "💡 Req Mgmt")
    kb.add("🏆 Leaderboard", "🎯 Missions Mgmt")
    kb.add("🎟 Coupons Mgmt", "👑 VIP Identity")
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

# ================= START HANDLER =================
@bot.message_handler(commands=['start'])
def start_handler(message):
    if bot_locked_guard(message):
        return

    uid = message.from_user.id
    args = message.text.split()

    if str(uid) not in users:
        ref = args[1] if len(args) > 1 and not args[1].startswith("ref_") else None
        if len(args) > 1 and args[1].startswith("ref_"):
            ref = args[1].replace("ref_", "")

        users[str(uid)] = {
            "username": message.from_user.username or "",
            "balance": 0.0,
            "blocked": 0.0,
            "ref": random_ref(),
            "bot_id": random_botid(),
            "invited": 0,
            "banned": False,
            "verified": False,
            "month": now_month(),
            "premium_active": False,
            "premium_plan": None,
            "premium_expiry": None,
            "referred_by": None,
            "completed_missions": [],
            "voted_features": [],
            "vip_title": "VIP",
            "vip_level": 1,
            "custom_title": None
        }
        
        if ref:
            ref_user = next((u for u, d in users.items() if d["ref"] == ref or u == ref), None)
            if ref_user and ref_user != str(uid):
                users[str(uid)]["referred_by"] = ref_user
                users[ref_user]["balance"] += 0.2
                users[ref_user]["invited"] += 1
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
    bot.send_message(m.chat.id,
        f"🔗 Your referral link:\n{link}\n\n"
        "Earn money by inviting friends!"
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

# ================= PREMIUM CENTER & HANDLERS =================
@bot.message_handler(func=lambda m: m.text == "👑 Premium")
def premium_center_handler(m):
    if bot_locked_guard(m):
        return
    if banned_guard(m):
        return
    
    uid = str(m.from_user.id)
    is_active = check_premium_status(uid)
    user_data = users.get(uid, {})
    
    if is_active:
        status_text = "ACTIVE"
        plan_text = user_data.get("premium_plan", "30 DAYS")
        expiry_text = user_data.get("premium_expiry", "N/A")
        try:
            exp_dt = datetime.strptime(expiry_text, "%Y-%m-%d %H:%M:%S")
            days_left = (exp_dt - datetime.now()).days
        except:
            days_left = 30
    else:
        status_text = "INACTIVE"
        plan_text = "NONE"
        expiry_text = "N/A"
        days_left = 0

    text = (
        "╭━━━ 👑 PREMIUM CENTER ━━━╮\n\n"
        f"⭐ STATUS: {status_text}\n"
        f"💎 PLAN: {plan_text}\n"
        f"📅 EXPIRES: {expiry_text}\n"
        f"⏳ DAYS LEFT: {days_left}\n\n"
        "✨ Unlock the full VIP experience!\n\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━╯"
    )

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
        InlineKeyboardButton("🔙 Back", callback_data="premium_back"),
        InlineKeyboardButton("🏠 Home", callback_data="premium_home")
    )

    bot.send_message(m.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("premium_"))
def premium_callbacks(call):
    uid = str(call.from_user.id)
    data = call.data

    if data == "premium_back" or data == "premium_home":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.send_message(call.message.chat.id, "🏠 Home Menu", reply_markup=user_menu(is_admin(uid)))
        return

    if data == "premium_my_plan":
        is_active = check_premium_status(uid)
        user_data = users.get(uid, {})
        status = "ACTIVE" if is_active else "INACTIVE"
        plan = user_data.get("premium_plan", "NONE")
        expiry = user_data.get("premium_expiry", "N/A")
        text = (
            "╭━━━ 💎 MY PLAN ━━━╮\n\n"
            f"⭐ Status: {status}\n"
            f"💎 Plan: {plan}\n"
            f"📅 Expires: {expiry}\n\n"
            "╰━━━━━━━━━━━━━━━━━╯"
        )
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_home"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        return

    if data == "premium_plans":
        text = (
            "╭━━━ ⭐ SELECT PLAN ━━━╮\n\n"
            "Choose your Telegram Stars plan:\n\n"
            "• ⭐ 7 Days — 50 Stars\n"
            "• ⭐ 30 Days — 150 Stars\n"
            "• ⭐ 90 Days — 350 Stars\n"
            "• ⭐ 1 Year — 1000 Stars\n\n"
            "╰━━━━━━━━━━━━━━━━━━━━╯"
        )
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("⭐ 7 Days (50 Stars)", callback_data="premium_buy_7"),
            InlineKeyboardButton("⭐ 30 Days (150 Stars)", callback_data="premium_buy_30")
        )
        kb.add(
            InlineKeyboardButton("⭐ 90 Days (350 Stars)", callback_data="premium_buy_90"),
            InlineKeyboardButton("⭐ 1 Year (1000 Stars)", callback_data="premium_buy_year")
        )
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_home"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        return

    if data.startswith("premium_buy_"):
        plan_key = data.replace("premium_buy_", "")
        plan_mapping = {
            "7": ("7 Days", 50, 7),
            "30": ("30 Days", 150, 30),
            "90": ("90 Days", 350, 90),
            "year": ("1 Year", 1000, 365)
        }
        if plan_key not in plan_mapping:
            return
        plan_name, stars_amt, days_val = plan_mapping[plan_key]

        prices = [LabeledPrice(label=f"VIP Premium ({plan_name})", amount=stars_amt)]
        try:
            bot.send_invoice(
                chat_id=call.message.chat.id,
                title=f"VIP Premium - {plan_name}",
                description=f"Unlock VIP features for {plan_name}",
                invoice_payload=f"premium_{plan_key}_{uid}_{int(time.time())}",
                provider_token="",
                currency="XTR",
                prices=prices
            )
        except Exception as e:
            bot.answer_callback_query(call.id, f"Error creating invoice: {e}", show_alert=True)
        return

    if data == "premium_referral":
        bot_username = bot.get_me().username
        ref = users[uid].get('ref', random_ref())
        link = f"https://t.me/{bot_username}?start=ref_{ref}"
        invited = users[uid].get("invited", 0)
        rank = get_user_rank(uid)
        text = (
            "╭━━━ 🎁 INVITE & EARN ━━━╮\n\n"
            f"👥 REFERRALS: {invited}\n"
            f"🎁 REWARDS: ⭐ 7 DAYS\n"
            f"🏆 RANK: #{rank}\n\n"
            "Invite friends and earn rewards!\n\n"
            f"🔗 Link:\n<code>{link}</code>\n\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯"
        )
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("👥 My Referrals", callback_data="premium_ref_list"),
            InlineKeyboardButton("🏆 My Rank", callback_data="premium_leaderboard")
        )
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_home"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
        return

    if data == "premium_ref_list":
        invited = users[uid].get("invited", 0)
        text = (
            "╭━━━ 👥 MY REFERRALS ━━━╮\n\n"
            f"Total Invited Users: {invited}\n\n"
            "Share your link to get more rewards!\n\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯"
        )
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_referral"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        return

    if data == "premium_requests":
        reqs = sorted(features_data, key=lambda x: x.get("votes", 0), reverse=True)
        req_lines = []
        for idx, r in enumerate(reqs[:3], start=1):
            req_lines.append(f"{idx}️⃣ {r.get('title')}\n👍 {r.get('votes')} Votes\n")
        req_text = "\n".join(req_lines) if req_lines else "No feature requests yet."
        text = (
            "╭━━━ 💡 FEATURE REQUESTS ━━━╮\n\n"
            "🔥 MOST REQUESTED\n\n"
            f"{req_text}\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯"
        )
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("👍 Vote", callback_data="premium_req_vote"),
            InlineKeyboardButton("💡 Submit", callback_data="premium_req_submit")
        )
        kb.add(
            InlineKeyboardButton("📋 My Requests", callback_data="premium_req_my"),
            InlineKeyboardButton("🔥 Most Requested", callback_data="premium_requests")
        )
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_home"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        return

    if data == "premium_req_submit":
        if not check_premium_status(uid) and not is_admin(uid):
            bot.answer_callback_query(call.id, "❌ Feature requests are for Premium users only!", show_alert=True)
            return
        msg = bot.send_message(call.message.chat.id, "💡 Send the title of your feature request:")
        bot.register_next_step_handler(msg, process_feature_title)
        return

    if data == "premium_req_vote":
        reqs = features_data
        if not reqs:
            bot.answer_callback_query(call.id, "No features to vote on.", show_alert=True)
            return
        kb = InlineKeyboardMarkup(row_width=1)
        for idx, r in enumerate(reqs):
            kb.add(InlineKeyboardButton(f"👍 {r.get('title')} ({r.get('votes')} votes)", callback_data=f"vote_feat_{idx}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_requests"))
        bot.edit_message_text("Choose a feature to vote for:", call.message.chat.id, call.message.message_id, reply_markup=kb)
        return

    if data.startswith("vote_feat_"):
        try:
            idx = int(data.replace("vote_feat_", ""))
            if uid not in users[uid].get("voted_features", []):
                if "voted_features" not in users[uid]:
                    users[uid]["voted_features"] = []
                features_data[idx]["votes"] = features_data[idx].get("votes", 0) + 1
                users[uid]["voted_features"].append(idx)
                save_features()
                save_users()
                bot.answer_callback_query(call.id, "✅ Vote recorded!")
            else:
                bot.answer_callback_query(call.id, "❌ You already voted for this or another feature.", show_alert=True)
        except Exception as e:
            bot.answer_callback_query(call.id, "Error voting", show_alert=True)
        return

    if data == "premium_req_my":
        my_reqs = [r for r in features_data if r.get("user") == uid]
        text = "╭━━━ 📋 MY REQUESTS ━━━╮\n\n"
        if my_reqs:
            for r in my_reqs:
                text += f"• {r.get('title')} — Status: {r.get('status')} | Votes: {r.get('votes')}\n"
        else:
            text += "You have not submitted any requests."
        text += "\n╰━━━━━━━━━━━━━━━━━━━━━━╯"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_requests"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        return

    if data == "premium_leaderboard":
        all_u = []
        for u_id, u_data in users.items():
            all_u.append((u_id, get_user_points(u_id)))
        all_u.sort(key=lambda x: x[1], reverse=True)
        
        medals = ["🥇", "🥈", "🥉"]
        lb_lines = []
        for idx, (u_id, pts) in enumerate(all_u[:3], start=1):
            m_icon = medals[idx-1] if idx <= 3 else f"{idx}️⃣"
            u_name = users[u_id].get("username") or u_id
            lb_lines.append(f"{m_icon} @{u_name} — {pts} POINTS")
        
        my_rank = get_user_rank(uid)
        my_pts = get_user_points(uid)
        
        text = (
            "╭━━━ 🏆 VIP LEADERBOARD ━━━╮\n\n"
            f"{'\n'.join(lb_lines)}\n\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"⭐ YOUR RANK: #{my_rank}\n"
            f"💎 YOUR POINTS: {my_pts}\n\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯"
        )
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("📊 My Rank", callback_data="premium_lb_rank"),
            InlineKeyboardButton("🏆 All Time", callback_data="premium_leaderboard")
        )
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_home"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        return

    if data == "premium_lb_rank":
        my_rank = get_user_rank(uid)
        my_pts = get_user_points(uid)
        text = (
            "╭━━━ 📊 YOUR RANK ━━━╮\n\n"
            f"Your Rank: #{my_rank}\n"
            f"Your Points: {my_pts}\n\n"
            "╰━━━━━━━━━━━━━━━━━━━━╯"
        )
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_leaderboard"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        return

    if data == "premium_missions":
        text = "╭━━━ 🎯 VIP MISSIONS ━━━╮\n\n"
        completed = users[uid].get("completed_missions", [])
        for m_item in missions_data.get("missions_list", []):
            m_id = m_item.get("id")
            m_title = m_item.get("title")
            m_target = m_item.get("target")
            m_reward = m_item.get("reward_days")
            
            progress = 0
            if m_id == "download_10":
                progress = min(videos_data.get("users", {}).get(uid, 0), m_target)
            elif m_id == "invite_3":
                progress = min(users[uid].get("invited", 0), m_target)
            elif m_id == "vote_3":
                progress = min(len(users[uid].get("voted_features", [])), m_target)

            filled = "█" * int((progress / m_target) * 10)
            empty = "░" * (10 - len(filled))
            status_mark = "✅" if progress >= m_target or m_id in completed else f"{progress}/{m_target}"
            text += f"{m_title}\n{filled}{empty} {status_mark}\n🎁 Reward: ⭐ {m_reward} Day(s)\n\n"
        text += "╰━━━━━━━━━━━━━━━━━━━━━━╯"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_home"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        return

    if data == "premium_coupons":
        text = (
            "╭━━━ 🎟 COUPONS ━━━╮\n\n"
            "Have a coupon code? Click below to redeem your reward.\n\n"
            "╰━━━━━━━━━━━━━━━━━━━╯"
        )
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("🎟 Redeem Coupon", callback_data="premium_redeem_coupon"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_home"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        return

    if data == "premium_redeem_coupon":
        msg = bot.send_message(call.message.chat.id, "🎟 Please send your coupon code:")
        bot.register_next_step_handler(msg, process_redeem_coupon)
        return

    if data == "premium_gift":
        text = (
            "╭━━━ 🎁 GIFT PREMIUM ━━━╮\n\n"
            "Gift Premium to another user using Telegram Stars!\n\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━╯"
        )
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🎁 Send Gift", callback_data="premium_send_gift"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_home"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        return

    if data == "premium_send_gift":
        msg = bot.send_message(call.message.chat.id, "🎁 Send recipient username (e.g. @username):")
        bot.register_next_step_handler(msg, process_gift_username)
        return

    if data == "premium_vip":
        user_data = users.get(uid, {})
        title = user_data.get("vip_title", "PRO")
        level = user_data.get("vip_level", 4)
        pts = get_user_points(uid)
        prem_since = user_data.get("premium_since", datetime.now().strftime("%Y-%m-%d"))
        
        text = (
            "╭━━━ 👑 VIP IDENTITY ━━━╮\n\n"
            f"👤 @{user_data.get('username', 'user')}\n\n"
            f"💎 TITLE: {title}\n"
            f"🔥 LEVEL: {level}\n"
            f"🏆 POINTS: {pts}\n\n"
            f"📅 PREMIUM SINCE:\n{prem_since}\n\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯"
        )
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("⭐ VIP", callback_data="set_vip_VIP"),
            InlineKeyboardButton("💎 PRO", callback_data="set_vip_PRO")
        )
        kb.add(
            InlineKeyboardButton("🔥 LEGEND", callback_data="set_vip_LEGEND"),
            InlineKeyboardButton("👑 ELITE", callback_data="set_vip_ELITE")
        )
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_home"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
        return

    if data.startswith("set_vip_"):
        new_title = data.replace("set_vip_", "")
        users[uid]["vip_title"] = new_title
        save_users()
        bot.answer_callback_query(call.id, f"✅ VIP Title updated to {new_title}")
        return

def process_feature_title(m):
    uid = str(m.from_user.id)
    title = m.text.strip()
    features_data.append({
        "user": uid,
        "title": title,
        "votes": 0,
        "status": "Pending"
    })
    save_features()
    bot.send_message(m.chat.id, "✅ Feature request submitted successfully!")

def process_redeem_coupon(m):
    uid = str(m.from_user.id)
    code = m.text.strip()
    if code in coupons_data:
        coup = coupons_data[code]
        if not coup.get("active", True):
            bot.send_message(m.chat.id, "❌ Coupon is inactive.")
            return
        if uid in coup.get("used_by", []):
            bot.send_message(m.chat.id, "❌ You have already used this coupon.")
            return
        if coup.get("uses", 0) >= coup.get("max_uses", 999):
            bot.send_message(m.chat.id, "❌ Coupon usage limit reached.")
            return
        
        days = coup.get("reward_days", 7)
        user = users[uid]
        try:
            exp_dt = datetime.strptime(user["premium_expiry"], "%Y-%m-%d %H:%M:%S") if user.get("premium_active") else datetime.now()
            if exp_dt < datetime.now():
                exp_dt = datetime.now()
            new_exp = exp_dt + timedelta(days=days)
            user["premium_active"] = True
            user["premium_plan"] = f"{days} Days"
            user["premium_expiry"] = new_exp.strftime("%Y-%m-%d %H:%M:%S")
            user["premium_since"] = datetime.now().strftime("%Y-%m-%d")
        except:
            new_exp = datetime.now() + timedelta(days=days)
            user["premium_active"] = True
            user["premium_plan"] = f"{days} Days"
            user["premium_expiry"] = new_exp.strftime("%Y-%m-%d %H:%M:%S")
            user["premium_since"] = datetime.now().strftime("%Y-%m-%d")

        if "used_by" not in coup:
            coup["used_by"] = []
        coup["used_by"].append(uid)
        coup["uses"] = coup.get("uses", 0) + 1
        save_coupons()
        save_users()
        bot.send_message(m.chat.id, f"🎉 Coupon redeemed successfully! Added {days} days of Premium.")
    else:
        bot.send_message(m.chat.id, "❌ Invalid coupon code.")

def process_gift_username(m):
    uid = str(m.from_user.id)
    recipient_username = m.text.replace("@", "").strip()
    recipient_id = None
    for u_id, u_data in users.items():
        if u_data.get("username", "").lower() == recipient_username.lower():
            recipient_id = u_id
            break
    if not recipient_id:
        bot.send_message(m.chat.id, "❌ Recipient user not found in database.")
        return
    
    users[uid]["gift_recipient"] = recipient_id
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⭐ 7 Days", callback_data="gift_plan_7"),
        InlineKeyboardButton("⭐ 30 Days", callback_data="gift_plan_30")
    )
    kb.add(
        InlineKeyboardButton("⭐ 90 Days", callback_data="gift_plan_90"),
        InlineKeyboardButton("⭐ 1 Year", callback_data="gift_plan_year")
    )
    bot.send_message(m.chat.id, f"🎁 Select plan to gift to @{recipient_username}:", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("gift_plan_"))
def gift_plan_callback(call):
    uid = str(call.from_user.id)
    plan_key = call.data.replace("gift_plan_", "")
    recipient_id = users[uid].get("gift_recipient")
    if not recipient_id:
        bot.answer_callback_query(call.id, "Session expired.", show_alert=True)
        return
    
    plan_mapping = {
        "7": ("7 Days", 50, 7),
        "30": ("30 Days", 150, 30),
        "90": ("90 Days", 350, 90),
        "year": ("1 Year", 1000, 365)
    }
    plan_name, stars_amt, days_val = plan_mapping[plan_key]
    prices = [LabeledPrice(label=f"Gift Premium ({plan_name})", amount=stars_amt)]
    try:
        bot.send_invoice(
            chat_id=call.message.chat.id,
            title=f"Gift Premium - {plan_name}",
            description=f"Gift VIP features to user",
            invoice_payload=f"gift_{plan_key}_{recipient_id}_{int(time.time())}",
            provider_token="",
            currency="XTR",
            prices=prices
        )
    except Exception as e:
        bot.answer_callback_query(call.id, f"Error: {e}", show_alert=True)

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout_handler(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def successful_payment_handler(message):
    payment_info = message.successful_payment
    payload = payment_info.invoice_payload
    uid = str(message.from_user.id)
    
    parts = payload.split("_")
    if parts[0] == "premium":
        plan_key = parts[1]
        plan_mapping = {"7": (7, "7 Days"), "30": (30, "30 Days"), "90": (90, "90 Days"), "year": (365, "1 Year")}
        days, plan_name = plan_mapping.get(plan_key, (30, "30 Days"))
        
        user = users[uid]
        try:
            exp_dt = datetime.strptime(user["premium_expiry"], "%Y-%m-%d %H:%M:%S") if user.get("premium_active") else datetime.now()
            if exp_dt < datetime.now():
                exp_dt = datetime.now()
            new_exp = exp_dt + timedelta(days=days)
            user["premium_active"] = True
            user["premium_plan"] = plan_name
            user["premium_expiry"] = new_exp.strftime("%Y-%m-%d %H:%M:%S")
            user["premium_since"] = datetime.now().strftime("%Y-%m-%d")
        except:
            new_exp = datetime.now() + timedelta(days=days)
            user["premium_active"] = True
            user["premium_plan"] = plan_name
            user["premium_expiry"] = new_exp.strftime("%Y-%m-%d %H:%M:%S")
            user["premium_since"] = datetime.now().strftime("%Y-%m-%d")
        
        save_users()
        bot.send_message(message.chat.id, f"🎉 <b>Payment Successful!</b>\n\nYour Premium plan ({plan_name}) is now activated!", parse_mode="HTML")
        payments_data.append({"user": uid, "payload": payload, "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        save_payments()

    elif parts[0] == "gift":
        plan_key = parts[1]
        recipient_id = parts[2]
        plan_mapping = {"7": (7, "7 Days"), "30": (30, "30 Days"), "90": (90, "90 Days"), "year": (365, "1 Year")}
        days, plan_name = plan_mapping.get(plan_key, (30, "30 Days"))
        
        if recipient_id in users:
            r_user = users[recipient_id]
            try:
                exp_dt = datetime.strptime(r_user["premium_expiry"], "%Y-%m-%d %H:%M:%S") if r_user.get("premium_active") else datetime.now()
                if exp_dt < datetime.now():
                    exp_dt = datetime.now()
                new_exp = exp_dt + timedelta(days=days)
                r_user["premium_active"] = True
                r_user["premium_plan"] = plan_name
                r_user["premium_expiry"] = new_exp.strftime("%Y-%m-%d %H:%M:%S")
                r_user["premium_since"] = datetime.now().strftime("%Y-%m-%d")
            except:
                new_exp = datetime.now() + timedelta(days=days)
                r_user["premium_active"] = True
                r_user["premium_plan"] = plan_name
                r_user["premium_expiry"] = new_exp.strftime("%Y-%m-%d %H:%M:%S")
                r_user["premium_since"] = datetime.now().strftime("%Y-%m-%d")
            save_users()
            
            try:
                bot.send_message(
                    int(recipient_id),
                    "╭━━━ 🎁 PREMIUM GIFT ━━━╮\n\n"
                    "🎉 YOU RECEIVED PREMIUM!\n\n"
                    f"💎 PLAN: {plan_name}\n"
                    f"📅 EXPIRES: {new_exp.strftime('%d %b %Y')}\n\n"
                    "Enjoy your VIP experience! 👑\n\n"
                    "╰━━━━━━━━━━━━━━━━━━━━━━╯",
                    parse_mode="HTML"
                )
            except:
                pass
            bot.send_message(message.chat.id, "✅ Gift successfully sent and activated!")

# ================= CHECK MEMBERSHIP =================
def check_membership(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["member", "administrator", "creator"]:
            bot.send_message(
                user_id,
                """🎬 Welcome to Video Downloader Bot!

This bot helps you easily download videos and music from many popular platforms directly to Telegram.

📥 Send any video link to begin downloading.""",
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
    bot.send_message(
        user_id,
        "⚠️ You must join our channel to use this bot.",
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda call: call.data == "confirm_join")
def confirm_join(call):
    user_id = call.from_user.id
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["member", "administrator", "creator"]:
            bot.answer_callback_query(call.id, "✅ Join verified")
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
            bot.send_message(
                user_id,
                "✅ Join confirmed!\nNow you can use the bot.\nSend your video link.",
                reply_markup=user_menu(is_admin(user_id))
            )
        else:
            bot.answer_callback_query(call.id, "❌ You must join the channel first!", show_alert=True)
    except:
        bot.answer_callback_query(call.id, "❌ Please join the channel first!", show_alert=True)

# ================= ADMIN PANEL =================
@bot.message_handler(func=lambda m: m.text == "👑 ADMIN PANEL")
def open_admin_panel(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ You are not admin")
        return
    bot.send_message(m.chat.id, "👑 Admin Panel", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text in ["👑 Premium Mgmt", "💳 Stars Payments", "🎁 Ref Mgmt", "💡 Req Mgmt", "🏆 Leaderboard", "🎯 Missions Mgmt", "🎟 Coupons Mgmt", "👑 VIP Identity"])
def admin_sub_panels(m):
    if not is_admin(m.from_user.id):
        return
    txt = m.text
    if txt == "👑 Premium Mgmt":
        msg = bot.send_message(m.chat.id, "Send Telegram ID and days to give Premium (e.g., `123456789 30`):")
        bot.register_next_step_handler(msg, admin_give_premium_process)
    elif txt == "🎟 Coupons Mgmt":
        msg = bot.send_message(m.chat.id, "Send Coupon Code and Days separated by space (e.g., `VIP50 30`):")
        bot.register_next_step_handler(msg, admin_create_coupon_process)
    elif txt == "💡 Req Mgmt":
        if not features_data:
            bot.send_message(m.chat.id, "No feature requests found.")
            return
        resp = "💡 Feature Requests:\n"
        for idx, r in enumerate(features_data):
            resp += f"{idx}. {r.get('title')} — Votes: {r.get('votes')} — Status: {r.get('status')}\n"
        bot.send_message(m.chat.id, resp)
    else:
        bot.send_message(m.chat.id, f"✅ {txt} module active.")

def admin_give_premium_process(m):
    if not is_admin(m.from_user.id):
        return
    try:
        parts = m.text.strip().split()
        uid = parts[0]
        days = int(parts[1])
        if uid not in users:
            bot.send_message(m.chat.id, "❌ User not found.")
            return
        user = users[uid]
        exp_dt = datetime.now() + timedelta(days=days)
        user["premium_active"] = True
        user["premium_plan"] = f"{days} Days"
        user["premium_expiry"] = exp_dt.strftime("%Y-%m-%d %H:%M:%S")
        user["premium_since"] = datetime.now().strftime("%Y-%m-%d")
        save_users()
        bot.send_message(m.chat.id, f"✅ Successfully granted {days} days of Premium to {uid}")
    except:
        bot.send_message(m.chat.id, "❌ Format error. Use: `<Telegram ID> <days>`")

def admin_create_coupon_process(m):
    if not is_admin(m.from_user.id):
        return
    try:
        parts = m.text.strip().split()
        code = parts[0].upper()
        days = int(parts[1])
        coupons_data[code] = {
            "reward_days": days,
            "max_uses": 100,
            "uses": 0,
            "active": True,
            "used_by": []
        }
        save_coupons()
        bot.send_message(m.chat.id, f"✅ Coupon <code>{code}</code> created with {days} days reward!", parse_mode="HTML")
    except:
        bot.send_message(m.chat.id, "❌ Format error. Use: `<Code> <days>`")

# ================= BALANCE & WITHDRAWAL =================
@bot.message_handler(func=lambda m: m.text == "💰 BALANCE")
def balance_handler(m):
    if bot_locked_guard(m): return
    if banned_guard(m): return
    uid = str(m.from_user.id)
    bal = users[uid].get("balance", 0.0)
    blocked = users[uid].get("blocked", 0.0)
    bot.send_message(
        m.chat.id,
        f"💰 Available Balance: ${bal:.2f}\n"
        f"⏳ Blocked Amount: ${blocked:.2f}"
    )

@bot.message_handler(func=lambda m: m.text == "🆔 GET ID")
def get_id_handler(m):
    if bot_locked_guard(m): return
    if banned_guard(m): return
    uid = str(m.from_user.id)
    bot.send_message(
        m.chat.id,
        f"🆔 BOT ID: <code>{users[uid]['bot_id']}</code>\n"
        f"👤 Telegram ID: <code>{uid}</code>"
    )

@bot.message_handler(func=lambda m: m.text == "👥 REFERRAL")
def referral_handler(m):
    if bot_locked_guard(m): return
    if banned_guard(m): return
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
        bot.send_message(
            int(uid),
            f"🚫 Your withdrawal of ${amt:.2f} is BLOCKED.\n"
            f"🔢 Block Code: {code}\n"
            f"Contact admin to unlock."
        )

# ================= ADMIN ACTIONS =================
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
    msg = bot.send_message(m.chat.id, "Enter Withdrawal Request ID:")
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
    bot.send_message(
        m.chat.id,
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

@bot.message_handler(func=lambda m: m.text == "📊 STATS")
def stats_handler(m):
    if not is_admin(m.from_user.id): return
    total_users = len(users)
    total_balance = sum(u.get("balance", 0.0) for u in users.values())
    total_blocked = sum(u.get("blocked", 0.0) for u in users.values())
    total_withdraws = len(withdraws)
    pending_withdraws = len([w for w in withdraws if w["status"] == "pending"])
    bot.send_message(
        m.chat.id,
        f"📊 BOT STATS\n\n"
        f"👥 Total Users: {total_users}\n"
        f"💰 Total Balance: ${total_balance:.2f}\n"
        f"⏳ Total Blocked: ${total_blocked:.2f}\n"
        f"🧾 Total Withdrawals: {total_withdraws}\n"
        f"⏳ Pending Withdrawals: {pending_withdraws}"
    )

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
    msg = bot.send_message(m.chat.id, "Send channel username (e.g. @mychannel)")
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
        f"• Pinterest: {platform_stats.get('pinterest',0)}\n"
    ]
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
    msg = bot.send_message(m.chat.id, "Send channel usernames. Send DONE when finished.")
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
    msg = bot.send_message(m.chat.id, f"Channel @{username} added. Send another or DONE")
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
    msg = bot.send_message(m.chat.id, "✍️ Send the lock message users should receive.")
    bot.register_next_step_handler(msg, lock_bot_process)

def lock_bot_process(m):
    global BOT_LOCKED, LOCK_MESSAGE
    if not is_admin(m.from_user.id): return
    text = (m.text or "").strip()
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
    text = (m.text or "").strip()
    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 2: return
    ADS_BTN_TEXT = parts[0]
    ADS_URL = parts[1]
    ADS_TEXT = parts[2] if len(parts) > 2 else "✨ Nagala soco baraha bulshada!"
    ADS_ENABLED = True
    bot.send_message(m.chat.id, "✅ Ads-ka waa la kaydiyay!")

@bot.message_handler(func=lambda m: m.text == "🗑 DELETE ADS")
def delete_ads(m):
    global ADS_ENABLED, ADS_BTN_TEXT, ADS_URL, ADS_TEXT
    if not is_admin(m.from_user.id): return
    ADS_ENABLED = False
    ADS_BTN_TEXT = ""
    ADS_URL = ""
    ADS_TEXT = ""
    bot.send_message(m.chat.id, "🗑 Ads tirtiray.")

@bot.message_handler(func=lambda m: m.text == "📥 IMPORT USERS")
def import_users_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Send Telegram IDs separated by spaces or new lines.")
    bot.register_next_step_handler(msg, import_users_process)

def import_users_process(m):
    if not is_admin(m.from_user.id): return
    text = m.text.strip()
    ids = text.replace("\n", " ").split()
    added = 0
    for uid in ids:
        uid = uid.strip()
        if uid.isdigit() and uid not in users:
            users[uid] = {
                "balance": 0.0, "blocked": 0.0, "ref": random_ref(), "bot_id": random_botid(),
                "invited": 0, "banned": False, "verified": False, "month": now_month(),
                "premium_active": False, "premium_plan": None, "premium_expiry": None
            }
            added += 1
    save_users()
    bot.send_message(m.chat.id, f"✅ Imported {added} users successfully.")

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
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("💬 OPEN CHAT", url=f"tg://user?id={uid}"))
        bot.send_message(m.chat.id, f"👤 User Found\nID: {uid}", reply_markup=kb)
    else:
        bot.send_message(m.chat.id, "❌ User not found")

@bot.message_handler(func=lambda m: m.text == "➕ ADD BALANCE")
def add_balance_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Send BOT ID or Telegram ID and amount:")
    bot.register_next_step_handler(msg, add_balance_process)

def add_balance_process(m):
    if not is_admin(m.from_user.id): return
    try:
        uid_str, amt_str = m.text.strip().split()
        amt = float(amt_str)
        uid = uid_str if uid_str in users else find_user_by_botid(uid_str)
        users[uid]["balance"] += amt
        save_users()
        bot.send_message(m.chat.id, f"✅ Added ${amt:.2f} to user {uid}")
    except:
        bot.send_message(m.chat.id, "❌ Format error.")

@bot.message_handler(func=lambda m: m.text == "➖ REMOVE MONEY")
def remove_balance_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Send BOT ID or Telegram ID and amount:")
    bot.register_next_step_handler(msg, remove_balance_process)

def remove_balance_process(m):
    if not is_admin(m.from_user.id): return
    try:
        uid_str, amt_str = m.text.strip().split()
        amt = float(amt_str)
        uid = uid_str if uid_str in users else find_user_by_botid(uid_str)
        users[uid]["balance"] -= amt
        save_users()
        bot.send_message(m.chat.id, f"✅ Removed ${amt:.2f} from user {uid}")
    except:
        bot.send_message(m.chat.id, "❌ Format error.")

# ================= LINK HANDLER & DOWNLOADER =================
@bot.message_handler(func=lambda m: m.text == "📥 Downloader")
def downloader_menu_handler(m):
    if bot_locked_guard(m): return
    if banned_guard(m): return
    bot.send_message(m.chat.id, "📥 Send any video link from TikTok, Instagram, Facebook, Pinterest, or YouTube to download.")

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

    bot.send_message(message.chat.id, "⏳ Downloading...")
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
                        try: os.remove(file)
                        except: pass
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
        bot.send_message(chat_id, "❌ Incorrect link.")

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
        with open(audio_path, "rb") as audio:
            bot.send_audio(call.message.chat.id, audio, title="Converted Music", performer="DownloadBot", caption=CAPTION_TEXT)
        if os.path.exists(audio_path): os.remove(audio_path)
        if os.path.exists(file_path): os.remove(file_path)
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
    try:
        tg_client.start()
    except:
        pass

    t1 = threading.Thread(target=run_bot1)
    t2 = threading.Thread(target=run_bot2)

    t1.start()
    t2.start()

    t1.join()
    t2.join()
