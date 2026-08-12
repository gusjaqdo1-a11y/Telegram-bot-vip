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
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN", "") # Telegram Stars/Payment Provider Token if needed

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
FEATURE_REQUESTS_FILE = "feature_requests.json"
MISSIONS_FILE = "missions.json"
COUPONS_FILE = "coupons.json"
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
premium_data = load_json(PREMIUM_FILE, {"plans": {"7": 50, "30": 150, "90": 350, "365": 1000}, "users": {}, "payments": []})
feature_requests = load_json(FEATURE_REQUESTS_FILE, [])
missions_data = load_json(MISSIONS_FILE, {
    "missions": [
        {"id": "dl_10", "title": "Download 10 Files", "goal": 10, "reward_days": 1, "type": "downloads"},
        {"id": "inv_3", "title": "Invite 3 Friends", "goal": 3, "reward_days": 2, "type": "referrals"},
        {"id": "vote_3", "title": "Vote on 3 Features", "goal": 3, "reward_days": 1, "type": "votes"}
    ],
    "user_progress": {}
})
coupons_data = load_json(COUPONS_FILE, {})
vip_identities = load_json(VIP_IDENTITY_FILE, {})

def save_users():
    save_json(USERS_FILE, users)

def save_withdraws():
    save_json(WITHDRAWS_FILE, withdraws)

def save_premium():
    save_json(PREMIUM_FILE, premium_data)

def save_feature_requests():
    save_json(FEATURE_REQUESTS_FILE, feature_requests)

def save_missions():
    save_json(MISSIONS_FILE, missions_data)

def save_coupons():
    save_json(COUPONS_FILE, coupons_data)

def save_vip_identities():
    save_json(VIP_IDENTITY_FILE, vip_identities)

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
    uid = str(uid)
    if uid in premium_data.get("users", {}):
        p_info = premium_data["users"][uid]
        exp_date = datetime.strptime(p_info["expiry_date"], "%Y-%m-%d %H:%M:%S")
        if datetime.now() < exp_date:
            return True
        else:
            p_info["status"] = "INACTIVE"
            save_premium()
    return False

def get_user_points(uid):
    uid = str(uid)
    points = 0
    # Referrals points
    ref_count = users.get(uid, {}).get("invited", 0)
    points += ref_count * 10
    # Premium activity
    if is_premium(uid):
        points += 50
    # Missions completed
    u_prog = missions_data.get("user_progress", {}).get(uid, {})
    completed_missions = sum(1 for m_id, data in u_prog.items() if data.get("completed"))
    points += completed_missions * 15
    return points

def get_vip_title(uid):
    uid = str(uid)
    if uid in vip_identities and "title" in vip_identities[uid]:
        return vip_identities[uid]["title"]
    if is_premium(uid):
        return "PRO"
    return "STANDARD"

# ================= MENUS =================
def user_menu(show_admin=False):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💰 BALANCE", "💸 WITHDRAWAL")
    kb.add("👥 REFERRAL", "🆔 GET ID")
    kb.add("👑 Premium", "☎️ CUSTOMER")
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
    kb.add("👑 Admin Premium Menu")
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

    # Haddii user cusub, ku dar database
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
            "referred_by": ref
        }
        # Referral reward & track
        if ref:
            ref_user = next((u for u, d in users.items() if d["ref"] == ref or u == ref), None)
            if ref_user and ref_user != str(uid):
                users[ref_user]["balance"] += 0.2
                users[ref_user]["invited"] += 1
                
                # Check missions for referrer
                update_mission_progress(ref_user, "referrals", 1)
                
                try:
                    bot.send_message(int(ref_user), "🎉 You earned $0.2 from referral!")
                except:
                    pass

        save_users()

    # Hubinta join
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
    link = f"https://t.me/{bot_username}?start=ref_{ref}"
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
                """🎬 Welcome to Video Downloader Bot!

This bot helps you easily download videos and music from many popular platforms directly to Telegram.

With this bot you can download content from platforms like:
• TikTok
• Instagram
• Facebook
• Pinterest
• YouTube
• And many other video links available on the internet.

📥 How to use the bot:
1. Copy the video link from any supported platform.
2. Send the link here in the bot.
3. The bot will automatically download the video for you.
4. You will receive the video file directly in this chat.

Now you're ready to start!
👇 Send any video link to begin downloading.""",
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
        if member.status in ["member","administrator","creator"]:
            bot.answer_callback_query(call.id,"✅ Join verified")
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

# ================= PREMIUM SYSTEM & HANDLERS =================
@bot.message_handler(func=lambda m: m.text == "👑 Premium")
def premium_center_handler(m):
    if bot_locked_guard(m):
        return
    if banned_guard(m):
        return
    show_premium_center(m.chat.id, m.from_user.id)

def show_premium_center(chat_id, user_id, message_id=None):
    uid = str(user_id)
    is_act = is_premium(uid)
    status_str = "ACTIVE" if is_act else "INACTIVE"
    plan_name = "N/A"
    expires_str = "N/A"
    days_left = 0

    if is_act:
        p_info = premium_data["users"][uid]
        plan_name = f"{p_info['plan']} DAYS"
        exp_dt = datetime.strptime(p_info["expiry_date"], "%Y-%m-%d %H:%M:%S")
        expires_str = exp_dt.strftime("%d %b %Y")
        days_left = max(0, (exp_dt - datetime.now()).days)

    text = f"""╭━━━ 👑 PREMIUM CENTER ━━━╮

⭐ STATUS: {status_str}

💎 PLAN: {plan_name}
📅 EXPIRES: {expires_str}
⏳ DAYS LEFT: {days_left}

✨ Unlock the full VIP experience!

╰━━━━━━━━━━━━━━━━━━━━━━╯"""

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⭐ Buy Premium", callback_data="premium_plans"),
        InlineKeyboardButton("💎 My Plan", callback_data="premium_home")
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
        InlineKeyboardButton("🏠 Home", callback_data="premium_home_menu")
    )

    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
            return
        except:
            pass
    bot.send_message(chat_id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("premium_"))
def premium_callback_router(call):
    uid = call.from_user.id
    data = call.data

    if data == "premium_home" or data == "premium_back":
        show_premium_center(call.message.chat.id, uid, call.message.message_id)
    elif data == "premium_home_menu":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.send_message(call.message.chat.id, "🏠 Home Menu", reply_markup=user_menu(is_admin(uid)))
    elif data == "premium_plans":
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("⭐ 7 Days (50 Stars)", callback_data="premium_buy_7"),
            InlineKeyboardButton("⭐ 30 Days (150 Stars)", callback_data="premium_buy_30")
        )
        kb.add(
            InlineKeyboardButton("⭐ 90 Days (350 Stars)", callback_data="premium_buy_90"),
            InlineKeyboardButton("⭐ 1 Year (1000 Stars)", callback_data="premium_buy_365")
        )
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_back"))
        bot.edit_message_text("⭐ **CHOOSE PREMIUM PLAN**\n\nSelect your desired VIP subscription duration:", call.message.chat.id, call.message.message_id, reply_markup=kb)
    elif data.startswith("premium_buy_"):
        days_str = data.split("_")[2]
        days = int(days_str)
        stars_map = {"7": 50, "30": 150, "90": 350, "365": 1000}
        amount = stars_map.get(days_str, 50)

        # Send Telegram Stars Invoice
        try:
            prices = [LabeledPrice(label=f"👑 {days} Days Premium", amount=amount)]
            bot.send_invoice(
                chat_id=call.message.chat.id,
                title=f"👑 {days} Days VIP Premium",
                description=f"Unlock VIP features for {days} days.",
                invoice_payload=f"premium_{uid}_{days}",
                provider_token=PROVIDER_TOKEN if PROVIDER_TOKEN else "",
                currency="XTR", # Telegram Stars currency
                prices=prices
            )
            bot.answer_callback_query(call.id, "Invoice sent!")
        except Exception as e:
            # Fallback for testing/simulation if provider token is missing
            bot.answer_callback_query(call.id, "Simulating instant activation (Test mode)", show_alert=True)
            activate_premium(uid, days)
            show_premium_center(call.message.chat.id, uid, call.message.message_id)
    elif data == "premium_referral":
        bot_username = bot.get_me().username
        ref = users[str(uid)]['ref']
        link = f"https://t.me/{bot_username}?start=ref_{ref}"
        invited = users[str(uid)].get("invited", 0)
        rank = get_user_rank(uid)
        text = f"""╭━━━ 🎁 INVITE & EARN ━━━╮

👥 REFERRALS: {invited}
🎁 REWARDS: ⭐ 7 DAYS
🏆 RANK: #{rank}

Invite friends and earn rewards!

Share your link:
<code>{link}</code>
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_back"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    elif data == "premium_requests":
        if not is_premium(uid):
            bot.answer_callback_query(call.id, "🔒 Feature Requests are for Premium users only!", show_alert=True)
            return
        show_feature_requests_menu(call.message.chat.id, call.message.message_id)
    elif data == "premium_leaderboard":
        show_leaderboard_menu(call.message.chat.id, call.message.message_id)
    elif data == "premium_missions":
        show_missions_menu(call.message.chat.id, call.message.message_id, uid)
    elif data == "premium_coupons":
        show_coupons_menu(call.message.chat.id, call.message.message_id)
    elif data == "premium_gift":
        msg = bot.send_message(call.message.chat.id, "🎁 Enter recipient's Telegram @username to gift Premium:")
        bot.register_next_step_handler(msg, process_gift_username)
    elif data == "premium_vip":
        show_vip_identity_menu(call.message.chat.id, call.message.message_id, uid)

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout_handler(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def successful_payment_handler(message):
    payment_info = message.successful_payment
    payload = payment_info.invoice_payload
    if payload.startswith("premium_"):
        parts = payload.split("_")
        uid = int(parts[1])
        days = int(parts[2])
        activate_premium(uid, days)
        bot.send_message(message.chat.id, f"🎉 Payment successful! Your Premium status is now active for {days} days. 👑")

def activate_premium(uid, days):
    uid = str(uid)
    now = datetime.now()
    if uid in premium_data["users"] and datetime.strptime(premium_data["users"][uid]["expiry_date"], "%Y-%m-%d %H:%M:%S") > now:
        current_exp = datetime.strptime(premium_data["users"][uid]["expiry_date"], "%Y-%m-%d %H:%M:%S")
        new_exp = current_exp + timedelta(days=days)
    else:
        new_exp = now + timedelta(days=days)
    
    premium_data["users"][uid] = {
        "plan": f"{days}",
        "start_date": now.strftime("%Y-%m-%d %H:%M:%S"),
        "expiry_date": new_exp.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "ACTIVE"
    }
    save_premium()

# ================= FEATURE REQUESTS SYSTEM =================
def show_feature_requests_menu(chat_id, message_id=None):
    sorted_reqs = sorted(feature_requests, key=lambda x: x.get("votes", 0), reverse=True)
    lines = ["╭━━━ 💡 FEATURE REQUESTS ━━━╮\n\n🔥 MOST REQUESTED\n"]
    for i, req in enumerate(sorted_reqs[:3], start=1):
        lines.append(f"{i}️⃣ {req['title']}\n👍 {req.get('votes', 0)} Votes — [{req.get('status', '🟡 Pending')}]\n")
    lines.append("╰━━━━━━━━━━━━━━━━━━━━━━╯")
    text = "\n".join(lines)
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💡 Submit Request", callback_data="feat_submit"),
        InlineKeyboardButton("📋 My Requests", callback_data="feat_my")
    )
    kb.add(InlineKeyboardButton("🔥 Most Requested", callback_data="feat_list"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_back"))

    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
            return
        except:
            pass
    bot.send_message(chat_id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("feat_"))
def feature_callbacks(call):
    uid = call.from_user.id
    data = call.data
    if data == "feat_submit":
        msg = bot.send_message(call.message.chat.id, "💡 Send the title of your feature request:")
        bot.register_next_step_handler(msg, process_feature_title)
    elif data == "feat_my":
        user_reqs = [r for r in feature_requests if r["user"] == uid]
        if not user_reqs:
            bot.answer_callback_query(call.id, "You have no feature requests.", show_alert=True)
            return
        text = "📋 **Your Requests:**\n\n"
        for r in user_reqs:
            text += f"• {r['title']} ({r['status']}) — 👍 {r['votes']} votes\n"
        bot.answer_callback_query(call.id, text[:200], show_alert=True)
    elif data == "feat_list":
        show_feature_requests_menu(call.message.chat.id, call.message.message_id)

def process_feature_title(m):
    uid = m.from_user.id
    title = m.text.strip()
    msg = bot.send_message(m.chat.id, "📝 Now send a short description for this feature:")
    bot.register_next_step_handler(msg, lambda x: process_feature_desc(x, title))

def process_feature_desc(m, title):
    uid = m.from_user.id
    desc = m.text.strip()
    req_id = random.randint(1000, 9999)
    feature_requests.append({
        "id": req_id,
        "user": uid,
        "title": title,
        "description": desc,
        "votes": 0,
        "voted_users": [],
        "status": "🟡 Pending"
    })
    save_feature_requests()
    update_mission_progress(uid, "votes", 1)
    bot.send_message(m.chat.id, "✅ Feature request submitted successfully!")
    show_feature_requests_menu(m.chat.id)

# ================= LEADERBOARD SYSTEM =================
def get_user_rank(uid):
    uid = str(uid)
    all_users = list(users.keys())
    sorted_u = sorted(all_users, key=lambda x: get_user_points(x), reverse=True)
    if uid in sorted_u:
        return sorted_u.index(uid) + 1
    return len(sorted_u) + 1

def show_leaderboard_menu(chat_id, message_id=None):
    all_users = list(users.keys())
    sorted_u = sorted(all_users, key=lambda x: get_user_points(x), reverse=True)
    
    lines = ["╭━━━ 🏆 VIP LEADERBOARD ━━━╮\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, u in enumerate(sorted_u[:3], start=1):
        uname = users[u].get("username") or u
        pts = get_user_points(u)
        lines.append(f"{medals[i-1]} @{uname} — {pts} POINTS")
    lines.append("\n━━━━━━━━━━━━━━━━━━\n")
    current_uid = str(chat_id) # approx
    rank = get_user_rank(chat_id)
    pts = get_user_points(chat_id)
    lines.append(f"⭐ YOUR RANK: #{rank}\n💎 YOUR POINTS: {pts}")
    lines.append("╰━━━━━━━━━━━━━━━━━━━━━━╯")
    text = "\n".join(lines)

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_back"))

    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
            return
        except:
            pass
    bot.send_message(chat_id, text, reply_markup=kb)

# ================= MISSIONS SYSTEM =================
def update_mission_progress(uid, mission_type, amount=1):
    uid = str(uid)
    if uid not in missions_data["user_progress"]:
        missions_data["user_progress"][uid] = {}
    
    for m in missions_data["missions"]:
        if m["type"] == mission_type:
            m_id = m["id"]
            if m_id not in missions_data["user_progress"][uid]:
                missions_data["user_progress"][uid][m_id] = {"progress": 0, "completed": False}
            
            if not missions_data["user_progress"][uid][m_id]["completed"]:
                missions_data["user_progress"][uid][m_id]["progress"] += amount
                if missions_data["user_progress"][uid][m_id]["progress"] >= m["goal"]:
                    missions_data["user_progress"][uid][m_id]["progress"] = m["goal"]
                    missions_data["user_progress"][uid][m_id]["completed"] = True
                    # Reward automatic
                    activate_premium(uid, m["reward_days"])
                    try:
                        bot.send_message(int(uid), f"🎉 Mission Completed: {m['title']}!\n🎁 Reward: ⭐ {m['reward_days']} Day(s) Premium added!")
                    except:
                        pass
    save_missions()

def show_missions_menu(chat_id, message_id, uid):
    uid = str(uid)
    if uid not in missions_data["user_progress"]:
        missions_data["user_progress"][uid] = {}
    
    lines = ["╭━━━ 🎯 VIP MISSIONS ━━━╮\n"]
    for m in missions_data["missions"]:
        m_id = m["id"]
        prog = missions_data["user_progress"][uid].get(m_id, {"progress": 0, "completed": False})
        goal = m["goal"]
        current = prog["progress"]
        status_icon = "✅" if prog["completed"] else ""
        
        # ProgressBar
        filled = int((current / goal) * 10)
        bar = "█" * filled + "░" * (10 - filled)
        lines.append(f"📥 {m['title']}\n{bar} {current}/{goal} {status_icon}\n🎁 Reward: ⭐ {m['reward_days']} Day\n")
    lines.append("╰━━━━━━━━━━━━━━━━━━━━━━╯")
    text = "\n".join(lines)

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_back"))
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    except:
        bot.send_message(chat_id, text, reply_markup=kb)

# ================= COUPONS SYSTEM =================
def show_coupons_menu(chat_id, message_id=None):
    text = "🎟 **COUPONS SYSTEM**\n\nEnter your coupon code to claim rewards or discounts!"
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🎟 Redeem Coupon", callback_data="coupon_redeem"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_back"))
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
            return
        except:
            pass
    bot.send_message(chat_id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "coupon_redeem")
def coupon_redeem_cb(call):
    msg = bot.send_message(call.message.chat.id, "🎟 Send your coupon code:")
    bot.register_next_step_handler(msg, process_coupon_code)

def process_coupon_code(m):
    uid = str(m.from_user.id)
    code = m.text.strip().upper()
    if code in coupons_data:
        c = coupons_data[code]
        if not c.get("active", True):
            bot.send_message(m.chat.id, "❌ Coupon is inactive.")
            return
        if uid in c.get("used_by", []):
            bot.send_message(m.chat.id, "❌ You have already used this coupon.")
            return
        if len(c.get("used_by", [])) >= c.get("max_uses", 100):
            bot.send_message(m.chat.id, "❌ Coupon usage limit reached.")
            return
        
        # Apply reward (days of premium)
        days = c.get("reward_days", 7)
        activate_premium(uid, days)
        if "used_by" not in c:
            c["used_by"] = []
        c["used_by"].append(uid)
        save_coupons()
        bot.send_message(m.chat.id, f"🎉 Coupon successfully redeemed! ⭐ {days} Days Premium activated.")
    else:
        bot.send_message(m.chat.id, "❌ Invalid coupon code.")

# ================= GIFT PREMIUM =================
def process_gift_username(m):
    username = m.text.replace("@", "").strip()
    recipient_uid = None
    for u, data in users.items():
        if data.get("username", "").lower() == username.lower():
            recipient_uid = u
            break
    if not recipient_uid:
        bot.send_message(m.chat.id, "❌ User not found in database.")
        return
    
    # Choose plan for gift
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⭐ 7 Days", callback_data=f"gift_plan_{recipient_uid}_7"),
        InlineKeyboardButton("⭐ 30 Days", callback_data=f"gift_plan_{recipient_uid}_30")
    )
    bot.send_message(m.chat.id, f"🎁 Select plan to gift to @{username}:", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("gift_plan_"))
def gift_plan_cb(call):
    parts = call.data.split("_")
    recip_uid = parts[2]
    days = int(parts[3])
    activate_premium(recip_uid, days)
    bot.answer_callback_query(call.id, "Gift sent successfully!")
    bot.send_message(call.message.chat.id, f"🎁 Successfully gifted {days} days of Premium!")
    try:
        bot.send_message(int(recip_uid), f"╭━━━ 🎁 PREMIUM GIFT ━━━╮\n\n🎉 YOU RECEIVED PREMIUM!\n\n💎 PLAN: {days} DAYS\n\nEnjoy your VIP experience! 👑\n╰━━━━━━━━━━━━━━━━━━━━━━╯")
    except:
        pass

# ================= VIP IDENTITY =================
def show_vip_identity_menu(chat_id, message_id, uid):
    uid = str(uid)
    uname = users.get(uid, {}).get("username", "user")
    title = get_vip_title(uid)
    points = get_user_points(uid)
    level = min(5, (points // 100) + 1)
    
    text = f"""╭━━━ 👑 VIP IDENTITY ━━━╮

👤 @{uname}

💎 TITLE: {title}
🔥 LEVEL: {level}
🏆 POINTS: {points}

📅 PREMIUM SINCE:
{premium_data.get('users', {}).get(uid, {}).get('start_date', 'N/A')}

╰━━━━━━━━━━━━━━━━━━━━━━╯"""

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⭐ VIP", callback_data="vip_set_VIP"),
        InlineKeyboardButton("💎 PRO", callback_data="vip_set_PRO")
    )
    kb.add(
        InlineKeyboardButton("🔥 LEGEND", callback_data="vip_set_LEGEND"),
        InlineKeyboardButton("👑 ELITE", callback_data="vip_set_ELITE")
    )
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_back"))
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    except:
        bot.send_message(chat_id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("vip_set_"))
def vip_set_cb(call):
    uid = str(call.from_user.id)
    title = call.data.split("_")[2]
    if not is_premium(uid):
        bot.answer_callback_query(call.id, "🔒 Premium required to change VIP Identity title!", show_alert=True)
        return
    if uid not in vip_identities:
        vip_identities[uid] = {}
    vip_identities[uid]["title"] = title
    save_vip_identities()
    bot.answer_callback_query(call.id, f"Title updated to {title}!")
    show_vip_identity_menu(call.message.chat.id, call.message.message_id, uid)

# ================= ADMIN PREMIUM PANEL =================
@bot.message_handler(func=lambda m: m.text == "👑 Admin Premium Menu")
def admin_premium_menu(m):
    if not is_admin(m.from_user.id):
        return
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("➕ Create Coupon", callback_data="adm_coupon_create"),
        InlineKeyboardButton("📊 Stats", callback_data="adm_prem_stats")
    )
    bot.send_message(m.chat.id, "👑 **Admin Premium & Coupon Panel**", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "adm_coupon_create")
def adm_coupon_create_cb(call):
    msg = bot.send_message(call.message.chat.id, "Send Coupon Code and Reward Days separated by space:\nExample:\nVIP30 30")
    bot.register_next_step_handler(msg, process_adm_create_coupon)

def process_adm_create_coupon(m):
    if not is_admin(m.from_user.id):
        return
    try:
        parts = m.text.strip().split()
        code = parts[0].upper()
        days = int(parts[1])
        coupons_data[code] = {
            "reward_days": days,
            "max_uses": 50,
            "active": True,
            "used_by": []
        }
        save_coupons()
        bot.send_message(m.chat.id, f"✅ Coupon {code} created with {days} days reward!")
    except:
        bot.send_message(m.chat.id, "❌ Format error. Use: `CODE DAYS`")

# ================= ADMIN PANEL =================
@bot.message_handler(func=lambda m: m.text == "👑 ADMIN PANEL")
def open_admin_panel(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ You are not admin")
        return
    bot.send_message(m.chat.id, "👑 Admin Panel", reply_markup=admin_menu())

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

@bot.message_handler(func=lambda m: m.text == "👥 REFERRAL")
def referral_handler(m):
    if bot_locked_guard(m):
        return
    if banned_guard(m):
        return
    uid = str(m.from_user.id)
    bot_username = bot.get_me().username
    link = f"https://t.me/{bot_username}?start=ref_{users[uid]['ref']}"
    invited = users[uid].get("invited", 0)
    bot.send_message(
        m.chat.id,
        f"🔗 Your Referral Link:\n{link}\n\n"
        f"👥 Invited Users: {invited}\n"
        f"🎁 You earn $0.2 per referral!"
    )

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
    prem_count = len(premium_data.get("users", {}))

    msg = (
        f"📊 BOT STATS\n\n"
        f"👥 Total Users: {total_users}\n"
        f"👑 Premium Users: {prem_count}\n"
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

channel_posts = {}

@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def channel_language(call):
    lang = call.data.split("_")[1]
    if call.message.message_id not in channel_posts:
        return
    data = channel_posts[call.message.message_id]
    text = data["so"] if lang == "so" else data["en"]
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🇸🇴 Somali", callback_data="lang_so"), InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"))
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
        "🥇 Top Users:"
    ]
    sorted_users = sorted(users_stats.items(), key=lambda x: x[1], reverse=True)
    for i, (uid, count) in enumerate(sorted_users[:20], start=1):
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
        return
    BOT_LOCKED = False
    bot.send_message(m.chat.id, "🔓 Bot unlocked successfully.")

@bot.message_handler(func=lambda m: m.text == "📢 ADD ADS")
def add_ads_start(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "✍️ Format: `Button Name | Link | Text`", parse_mode="Markdown")
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
    ADS_TEXT = parts[2] if len(parts) > 2 else "✨ Nagala soco!"
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
    ids = m.text.replace("\n", " ").split()
    added = 0
    for uid in ids:
        uid = uid.strip()
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
    bot.send_message(m.chat.id, f"✅ Imported {added} users successfully.")

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
    msg = bot.send_message(m.chat.id, "Now send referral code number:")
    bot.register_next_step_handler(msg, lambda x: save_custom_ref_code(x, username))

def save_custom_ref_code(m, username):
    if not is_admin(m.from_user.id):
        return
    code = m.text.strip()
    user_id = None
    for uid, data in users.items():
        if data.get("username","").lower() == username.lower():
            user_id = uid
            break
    if not user_id:
        bot.send_message(m.chat.id, "❌ User not found")
        return
    users[user_id]["ref"] = code
    save_users()
    bot.send_message(m.chat.id, f"✅ Referral code created for @{username}: {code}")

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
        kb.add(InlineKeyboardButton("🤖 Verify via Bot", url=f"https://t.me/Verifyd_bot?start={code}"))
        kb.add(InlineKeyboardButton("📧 Verify via Gmail", callback_data="verify_email"))
        bot.send_message(message.chat.id, "🔐 Verification Required\n\nChoose verification method:", reply_markup=kb)
        return

    # Update download mission
    update_mission_progress(user_id, "downloads", 1)

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
        bot.answer_callback_query(call.id, "❌ You must join all channels first!", show_alert=True)

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

@bot.message_handler(func=lambda m: m.text == "➕ ADD BALANCE")
def add_balance_start(m):
    if not is_admin(m.from_user.id):
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
        if not uid or amt <= 0:
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
        bot.send_message(chat_id, "❌ Error downloading link.")

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
    audio_path = file_path.rsplit(".",1)[0] + ".mp3"
    try:
        subprocess.run(["ffmpeg", "-y", "-i", file_path, "-vn", "-acodec","mp3", "-ab","128k", "-ar","44100", audio_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📢 BOT CHANNEL", url="https://t.me/tiktokvediodownload"))
        with open(audio_path,"rb") as audio:
            bot.send_audio(call.message.chat.id, audio, title="Converted Music", performer="DownloadBot", caption=CAPTION_TEXT, reply_markup=kb)
        if os.path.exists(audio_path):
            os.remove(audio_path)
        if os.path.exists(file_path):
            os.remove(file_path)
        bot.answer_callback_query(call.id, "🎵 Music converted")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Music conversion failed:\n{e}")

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
