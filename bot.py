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
FEATURE_REQUESTS_FILE = "feature_requests.json"
LEADERBOARD_FILE = "leaderboard.json"
MISSIONS_FILE = "missions.json"
COUPONS_FILE = "coupons.json"
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
videos_data = load_json(VIDEOS_FILE, {
    "total": 0,
    "platforms": {"tiktok": 0, "youtube": 0, "facebook": 0, "pinterest": 0},
    "users": {}
})

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
referrals_data = load_json(REFERRALS_FILE, {"milestones": {3: 7, 5: 15, 10: 30, 25: 90, 50: 365}, "records": {}})
feature_requests_data = load_json(FEATURE_REQUESTS_FILE, [])
leaderboard_data = load_json(LEADERBOARD_FILE, {"points": {}})
missions_data = load_json(MISSIONS_FILE, {
    "active": [
        {"id": "dl_10", "title": "Download 10 Files", "target": 10, "reward_days": 1, "type": "daily"},
        {"id": "inv_3", "title": "Invite 3 Friends", "target": 3, "reward_days": 2, "type": "weekly"},
        {"id": "vote_3", "title": "Vote on 3 Features", "target": 3, "reward_days": 1, "type": "special"}
    ],
    "progress": {}
})
coupons_data = load_json(COUPONS_FILE, {})
gift_premium_data = load_json(GIFT_PREMIUM_FILE, [])
vip_identity_data = load_json(VIP_IDENTITY_FILE, {})

def save_users(): save_json(USERS_FILE, users)
def save_withdraws(): save_json(WITHDRAWS_FILE, withdraws)
def save_videos(): save_json(VIDEOS_FILE, videos_data)
def save_premium(): save_json(PREMIUM_FILE, premium_data)
def save_payments(): save_json(PAYMENTS_FILE, payments_data)
def save_referrals(): save_json(REFERRALS_FILE, referrals_data)
def save_feature_requests(): save_json(FEATURE_REQUESTS_FILE, feature_requests_data)
def save_leaderboard(): save_json(LEADERBOARD_FILE, leaderboard_data)
def save_missions(): save_json(MISSIONS_FILE, missions_data)
def save_coupons(): save_json(COUPONS_FILE, coupons_data)
def save_gift_premium(): save_json(GIFT_PREMIUM_FILE, gift_premium_data)
def save_vip_identity(): save_json(VIP_IDENTITY_FILE, vip_identity_data)

# ================= HELPER FUNCTIONS =================
def random_ref(): return str(random.randint(1000000000, 9999999999))
def random_botid(): return str(random.randint(10000000000, 99999999999))
def now_month(): return datetime.now().month
def is_admin(uid): return int(uid) in ADMIN_IDS

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

def is_user_premium(uid):
    uid_str = str(uid)
    if uid_str in premium_data["subscriptions"]:
        sub = premium_data["subscriptions"][uid_str]
        exp = datetime.strptime(sub["expiry_date"], "%Y-%m-%d %H:%M:%S")
        if datetime.now() < exp:
            return True
        else:
            sub["status"] = "INACTIVE"
            save_premium()
    return False

def add_user_premium(uid, days, plan_key, stars_amount, payment_id="MANUAL"):
    uid_str = str(uid)
    now = datetime.now()
    if is_user_premium(uid_str):
        current_exp = datetime.strptime(premium_data["subscriptions"][uid_str]["expiry_date"], "%Y-%m-%d %H:%M:%S")
        expiry = current_exp + timedelta(days=days)
    else:
        expiry = now + timedelta(days=days)
    
    premium_data["subscriptions"][uid_str] = {
        "user_id": uid_str,
        "plan": plan_key,
        "duration": days,
        "stars_amount": stars_amount,
        "payment_id": payment_id,
        "start_date": now.strftime("%Y-%m-%d %H:%M:%S"),
        "expiry_date": expiry.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "ACTIVE",
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S")
    }
    save_premium()

    # Init VIP identity if not exists
    if uid_str not in vip_identity_data:
        vip_identity_data[uid_str] = {
            "title": "PRO",
            "level": 1,
            "points": 10
        }
    else:
        vip_identity_data[uid_str]["level"] += 1
        vip_identity_data[uid_str]["points"] += 50
    save_vip_identity()

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
    kb.add("👑 PREMIUM ADMIN", "🎟 COUPONS ADMIN")
    kb.add("🎯 MISSIONS ADMIN", "💡 REQUESTS ADMIN")
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
                
                # Referral records tracking
                if ref_user not in referrals_data["records"]:
                    referrals_data["records"][ref_user] = []
                referrals_data["records"][ref_user].append(str(uid))
                
                # Check milestones
                inv_count = len(referrals_data["records"][ref_user])
                milestones = referrals_data["milestones"]
                if inv_count in milestones:
                    reward_days = milestones[str(inv_count)] if str(inv_count) in milestones else milestones[int(inv_count)]
                    add_user_premium(ref_user, reward_days, f"ref_{inv_count}_milestone", 0, "REFERRAL_MILESTONE")
                    try:
                        bot.send_message(int(ref_user), f"🎁 Congratulations! You reached {inv_count} referrals and earned {reward_days} Days Premium!")
                    except:
                        pass

                try:
                    bot.send_message(int(ref_user), "🎉 You earned $0.2 and referral credit from your invite!")
                except:
                    pass

        save_users()
        save_referrals()

    check_membership(uid)

@bot.message_handler(commands=['view'])
def view_cmd(message):
    bot.send_message(
        message.chat.id,
        "🤖 BOT INFO\n\n"
        "📌 Name: Video Downloader Bot & VIP System\n"
        "⚡ Features:\n"
        "• TikTok, YouTube, FB, Pinterest, Snapchat\n"
        "• Telegram Stars Premium VIP\n"
        "• Referrals & Rewards\n"
        "• Feature Voting\n"
        "• Leaderboard & Missions"
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
    if bot_locked_guard(m) or banned_guard(m):
        return
    uid = str(m.from_user.id)
    is_active = is_user_premium(uid)
    
    if is_active:
        sub = premium_data["subscriptions"][uid]
        exp_dt = datetime.strptime(sub["expiry_date"], "%Y-%m-%d %H:%M:%S")
        days_left = (exp_dt - datetime.now()).days
        status_str = "ACTIVE"
        plan_str = premium_data["plans"].get(sub["plan"], {}).get("name", sub["plan"])
        exp_str = exp_dt.strftime("%d %b %Y")
    else:
        status_str = "INACTIVE"
        plan_str = "Free"
        exp_str = "N/A"
        days_left = 0

    text = f"""╭━━━ 👑 PREMIUM CENTER ━━━╮

⭐ Status: {status_str}
💎 Plan: {plan_str}
📅 Expires: {exp_str}
⏳ Days Left: {days_left}

✨ Unlock the full Premium experience!
╰━━━━━━━━━━━━━━━━━━━━━━╯"""

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⭐ Buy Premium", callback_data="prem_buy"),
        InlineKeyboardButton("💎 My Plan", callback_data="prem_myplan")
    )
    kb.add(
        InlineKeyboardButton("⚙️ Premium Settings", callback_data="prem_settings"),
        InlineKeyboardButton("📊 My Statistics", callback_data="prem_mystats")
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
        InlineKeyboardButton("🔙 Back", callback_data="prem_back")
    )

    bot.send_message(m.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("prem_"))
def premium_callbacks(call):
    uid = str(call.from_user.id)
    data = call.data

    if data == "prem_back":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "🔙 Main Menu", reply_markup=user_menu(is_admin(uid)))
    
    elif data == "prem_buy":
        kb = InlineKeyboardMarkup(row_width=2)
        for key, plan in premium_data["plans"].items():
            if plan["active"]:
                kb.add(InlineKeyboardButton(f"⭐ {plan['name']} - {plan['stars']} Stars", callback_data=f"buyplan_{key}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="prem_center_back"))
        bot.edit_message_text("⭐ **Choose Premium Plan:**\n\nPay securely with Telegram Stars to activate your VIP benefits instantly.", call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif data == "prem_center_back":
        # Re-render main premium center
        is_active = is_user_premium(uid)
        if is_active:
            sub = premium_data["subscriptions"][uid]
            exp_dt = datetime.strptime(sub["expiry_date"], "%Y-%m-%d %H:%M:%S")
            days_left = (exp_dt - datetime.now()).days
            status_str = "ACTIVE"
            plan_str = premium_data["plans"].get(sub["plan"], {}).get("name", sub["plan"])
            exp_str = exp_dt.strftime("%d %b %Y")
        else:
            status_str = "INACTIVE"
            plan_str = "Free"
            exp_str = "N/A"
            days_left = 0

        text = f"""╭━━━ 👑 PREMIUM CENTER ━━━╮

⭐ Status: {status_str}
💎 Plan: {plan_str}
📅 Expires: {exp_str}
⏳ Days Left: {days_left}

✨ Unlock the full Premium experience!
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("⭐ Buy Premium", callback_data="prem_buy"),
            InlineKeyboardButton("💎 My Plan", callback_data="prem_myplan")
        )
        kb.add(
            InlineKeyboardButton("⚙️ Premium Settings", callback_data="prem_settings"),
            InlineKeyboardButton("📊 My Statistics", callback_data="prem_mystats")
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
            InlineKeyboardButton("🔙 Back", callback_data="prem_back")
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif data.startswith("buyplan_"):
        plan_key = data.split("_", 1)[1]
        plan = premium_data["plans"].get(plan_key)
        if not plan:
            bot.answer_callback_query(call.id, "Plan not found!")
            return
        
        prices = [LabeledPrice(label=f"{plan['name']} Premium", amount=plan["stars"])]
        try:
            bot.send_invoice(
                chat_id=call.message.chat.id,
                title=f"VIP {plan['name']} Premium",
                description=f"Unlock {plan['name']} VIP access to download bot features and priority speed.",
                invoice_payload=f"premium_pay_{uid}_{plan_key}",
                provider_token="", # Telegram Stars requires empty provider token
                currency="XTR",
                prices=prices
            )
        except Exception as e:
            bot.answer_callback_query(call.id, f"Error creating invoice: {e}", show_alert=True)

    elif data == "prem_myplan":
        is_active = is_user_premium(uid)
        if not is_active:
            bot.answer_callback_query(call.id, "You do not have an active Premium plan.", show_alert=True)
            return
        sub = premium_data["subscriptions"][uid]
        text = f"💎 **Your Subscription Details**\n\nPlan: {sub['plan']}\nDuration: {sub['duration']} Days\nStarted: {sub['start_date']}\nExpires: {sub['expiry_date']}\nStatus: {sub['status']}"
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="prem_center_back"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif data == "prem_settings":
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="prem_center_back"))
        bot.edit_message_text("⚙️ **Premium Settings**\n\nYour account is linked with Telegram VIP identity and priority queue processing.", call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif data == "prem_mystats":
        dl_count = videos_data["users"].get(uid, 0)
        ref_count = len(referrals_data["records"].get(uid, []))
        text = f"📊 **Your Statistics**\n\n📥 Total Downloads: {dl_count}\n👥 Referrals: {ref_count}\n⭐ Premium Status: {'Active' if is_user_premium(uid) else 'Inactive'}"
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="prem_center_back"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif data == "prem_invite":
        bot_username = bot.get_me().username
        ref_link = f"https://t.me/{bot_username}?start={users[uid]['ref']}"
        ref_count = len(referrals_data["records"].get(uid, []))
        text = f"""╭━━━ 🎁 INVITE & EARN ━━━╮

👥 Referrals: {ref_count}
🎁 Rewards: ⭐ Active Milestones
🏆 Rank: Checked in Leaderboard

Invite your friends and earn rewards!
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={ref_link}&text=Join%20this%20awesome%20video%20downloader%20bot!"),
            InlineKeyboardButton("👥 My Referrals", callback_data="ref_my_list")
        )
        kb.add(
            InlineKeyboardButton("🎁 My Rewards", callback_data="prem_mystats"),
            InlineKeyboardButton("🏆 My Rank", callback_data="prem_leaderboard")
        )
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="prem_center_back"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif data == "ref_my_list":
        refs = referrals_data["records"].get(uid, [])
        text = f"👥 **Your Referrals List**\n\nTotal Invited Users: {len(refs)}\n"
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="prem_invite"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif data == "prem_features":
        if not is_user_premium(uid):
            bot.answer_callback_query(call.id, "❌ Feature Requests is a Premium VIP exclusive feature!", show_alert=True)
            return
        
        sorted_reqs = sorted(feature_requests_data, key=lambda x: x["votes"], reverse=True)
        text = "╭━━━ 💡 FEATURE REQUESTS ━━━╮\n\n🔥 **MOST REQUESTED**\n\n"
        for i, req in enumerate(sorted_reqs[:3], 1):
            text += f"{i}️⃣ {req['title']}\n👍 {req['votes']} Votes [{req['status']}]\n\n"
        text += "╰━━━━━━━━━━━━━━━━━━━━━━╯"

        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("💡 Submit Feature", callback_data="feat_submit"),
            InlineKeyboardButton("📋 My Requests", callback_data="feat_my")
        )
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="prem_center_back"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif data == "feat_submit":
        msg = bot.send_message(call.message.chat.id, "💡 Send the title of your feature request:")
        bot.register_next_step_handler(msg, process_feature_title)

    elif data == "feat_my":
        user_reqs = [r for r in feature_requests_data if r["user_id"] == uid]
        text = f"📋 **Your Feature Requests**\n\nTotal Submitted: {len(user_reqs)}"
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="prem_features"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif data == "prem_leaderboard":
        sorted_lb = sorted(leaderboard_data["points"].items(), key=lambda x: x[1], reverse=True)
        medals = ["🥇", "🥈", "🥉"]
        text = "╭━━━ 🏆 PREMIUM LEADERBOARD ━━━╮\n\n"
        for i, (u, pts) in enumerate(sorted_lb[:3], 1):
            medal = medals[i-1] if i <= 3 else f"{i}️⃣"
            text += f"{medal} User {u[:4]}... — {pts} Points\n"
        text += "\n━━━━━━━━━━━━━━━━━━\n\n⭐ **YOUR POSITION**\nRank: #" + str(sorted_lb.index((uid, leaderboard_data["points"].get(uid, 0))) + 1 if (uid, leaderboard_data["points"].get(uid, 0)) in sorted_lb else "N/A") + f"\nPoints: {leaderboard_data['points'].get(uid, 0)}\n\n╰━━━━━━━━━━━━━━━━━━━━━━╯"
        
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("📅 Weekly", callback_data="lb_time"),
            InlineKeyboardButton("📆 Monthly", callback_data="lb_time")
        )
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="prem_center_back"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif data == "lb_time":
        bot.answer_callback_query(call.id, "Leaderboard updated for current period.")

    elif data == "prem_missions":
        text = "╭━━━ 🎯 PREMIUM MISSIONS ━━━╮\n\n🔥 **ACTIVE MISSIONS**\n\n"
        for m_item in missions_data["active"]:
            prog = missions_data["progress"].get(uid, {}).get(m_item["id"], 0)
            status_icon = "✅ Completed" if prog >= m_item["target"] else f"Progress: {prog}/{m_item['target']}"
            text += f"📥 {m_item['title']}\n{status_icon}\n🎁 Reward: ⭐ {m_item['reward_days']} Days\n\n"
        text += "╰━━━━━━━━━━━━━━━━━━━━━━╯"
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="prem_center_back"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif data == "prem_coupons":
        msg = bot.send_message(call.message.chat.id, "🎟️ **Enter your coupon code below:**\n\nExample: `VIP2026`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_coupon_code)

    elif data == "prem_gift":
        msg = bot.send_message(call.message.chat.id, "🎁 **Gift Premium**\n\nSend the Telegram @username or User ID of the recipient:")
        bot.register_next_step_handler(msg, process_gift_recipient)

    elif data == "prem_identity":
        identity = vip_identity_data.get(uid, {"title": "PRO", "level": 1, "points": 10})
        text = f"""╭━━━ 👑 VIP IDENTITY ━━━╮

👤 User: @{call.from_user.username or 'N/A'}

⭐ Current Title:
💎 {identity['title']}

📅 Premium Since:
Active VIP

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
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="prem_center_back"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif data.startswith("vip_title_"):
        title_choice = data.split("_")[2].upper()
        if uid not in vip_identity_data:
            vip_identity_data[uid] = {"title": "PRO", "level": 1, "points": 10}
        vip_identity_data[uid]["title"] = title_choice
        save_vip_identity()
        bot.answer_callback_query(call.id, f"✅ VIP Title updated to {title_choice}!")

# ================= FEATURE REQUEST STEPS =================
def process_feature_title(message):
    uid = str(message.from_user.id)
    title = message.text.strip()
    msg = bot.send_message(message.chat.id, "📝 Now send the description for this feature request:")
    bot.register_next_step_handler(msg, lambda m: process_feature_desc(m, title))

def process_feature_desc(message, title):
    uid = str(message.from_user.id)
    desc = message.text.strip()
    req_id = str(uuid.uuid4())[:8]
    
    feature_requests_data.append({
        "request_id": req_id,
        "user_id": uid,
        "title": title,
        "description": desc,
        "votes": 1,
        "status": "🟡 Pending",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    save_feature_requests()
    bot.send_message(message.chat.id, "✅ Feature request submitted successfully!")

# ================= COUPON PROCESSING =================
def process_coupon_code(message):
    uid = str(message.from_user.id)
    code = message.text.strip().upper()
    if code not in coupons_data:
        bot.send_message(message.chat.id, "❌ Invalid or expired coupon code.")
        return
    
    coupon = coupons_data[code]
    if not coupon.get("active", True):
        bot.send_message(message.chat.id, "❌ This coupon is inactive.")
        return
    
    if uid in coupon.get("used_by", []):
        bot.send_message(message.chat.id, "❌ You have already used this coupon.")
        return
    
    if coupon.get("max_uses", 0) > 0 and coupon.get("current_uses", 0) >= coupon["max_uses"]:
        bot.send_message(message.chat.id, "❌ Coupon usage limit reached.")
        return

    # Apply reward
    reward_days = coupon.get("reward_days", 7)
    add_user_premium(uid, reward_days, f"coupon_{code}", 0, f"COUPON_{code}")
    
    if "used_by" not in coupon:
        coupon["used_by"] = []
    coupon["used_by"].append(uid)
    coupon["current_uses"] = coupon.get("current_uses", 0) + 1
    save_coupons()
    
    bot.send_message(message.chat.id, f"✅ Coupon applied successfully! You received {reward_days} Days Premium!")

# ================= GIFT PREMIUM STEPS =================
def process_gift_recipient(message):
    uid = str(message.from_user.id)
    recipient_input = message.text.strip().replace("@", "")
    
    recipient_id = None
    for u, data in users.items():
        if data.get("username", "").lower() == recipient_input.lower() or u == recipient_input:
            recipient_id = u
            break
            
    if not recipient_id:
        bot.send_message(message.chat.id, "❌ Recipient user not found in database.")
        return
        
    kb = InlineKeyboardMarkup(row_width=2)
    for key, plan in premium_data["plans"].items():
        if plan["active"]:
            kb.add(InlineKeyboardButton(f"⭐ {plan['name']} - {plan['stars']} Stars", callback_data=f"giftplan_{recipient_id}_{key}"))
    bot.send_message(message.chat.id, f"🎁 Choose plan to gift to @{recipient_input}:", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("giftplan_"))
def gift_plan_callback(call):
    uid = str(call.from_user.id)
    _, recipient_id, plan_key = call.data.split("_", 2)
    plan = premium_data["plans"].get(plan_key)
    
    prices = [LabeledPrice(label=f"Gift {plan['name']} Premium", amount=plan["stars"])]
    try:
        bot.send_invoice(
            chat_id=call.message.chat.id,
            title=f"Gift VIP {plan['name']}",
            description=f"Send Premium gift to user {recipient_id}",
            invoice_payload=f"gift_pay_{uid}_{recipient_id}_{plan_key}",
            provider_token="",
            currency="XTR",
            prices=prices
        )
    except Exception as e:
        bot.answer_callback_query(call.id, f"Error: {e}", show_alert=True)

# ================= TELEGRAM STARS PRECHECK & SUCCESS =================
@bot.pre_checkout_query_handler(func=lambda query: True)
def pre_checkout_query(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def successful_payment_handler(message):
    payment = message.successful_payment
    payload = payment.invoice_payload
    uid = str(message.from_user.id)
    
    if payload.startswith("premium_pay_"):
        _, _, plan_key = payload.split("_", 2)
        plan = premium_data["plans"].get(plan_key)
        if plan:
            add_user_premium(uid, plan["duration"], plan_key, payment.total_amount, payment.telegram_payment_charge_id)
            bot.send_message(message.chat.id, f"🎉 Payment confirmed! Your {plan['name']} Premium has been activated successfully! 👑")
            
    elif payload.startswith("gift_pay_"):
        _, _, sender_id, recipient_id, plan_key = payload.split("_", 4)
        plan = premium_data["plans"].get(plan_key)
        if plan:
            add_user_premium(recipient_id, plan["duration"], plan_key, payment.total_amount, payment.telegram_payment_charge_id)
            gift_premium_data.append({
                "sender_id": sender_id,
                "recipient_id": recipient_id,
                "plan": plan_key,
                "stars_amount": payment.total_amount,
                "payment_id": payment.telegram_payment_charge_id,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "completed"
            })
            save_gift_premium()
            bot.send_message(message.chat.id, f"🎁 Premium successfully gifted to user {recipient_id}!")
            try:
                bot.send_message(int(recipient_id), f"╭━━━ 🎁 PREMIUM GIFT ━━━╮\n\n🎉 You received Premium!\n\n💎 Plan: {plan['name']}\n📅 Expires: {(datetime.now() + timedelta(days=plan['duration'])).strftime('%d %b %Y')}\n\nEnjoy your Premium experience! 👑\n╰━━━━━━━━━━━━━━━━━━━━━━╯")
            except:
                pass

# ================= ADMIN PANEL ADVANCED VIP CONTROLS =================
@bot.message_handler(func=lambda m: m.text in ["👑 PREMIUM ADMIN", "🎟 COUPONS ADMIN", "🎯 MISSIONS ADMIN", "💡 REQUESTS ADMIN"])
def admin_vip_subpanels(m):
    if not is_admin(m.from_user.id):
        return
    text = m.text
    if text == "👑 PREMIUM ADMIN":
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("👑 Give Premium", callback_data="adm_give_prem"),
            InlineKeyboardButton("❌ Remove Premium", callback_data="adm_rem_prem")
        )
        kb.add(InlineKeyboardButton("📊 Premium Statistics", callback_data="adm_prem_stats"))
        bot.send_message(m.chat.id, "👑 **Premium Management Dashboard**", reply_markup=kb)
    elif text == "🎟 COUPONS ADMIN":
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("➕ Create Coupon", callback_data="adm_create_coupon"),
            InlineKeyboardButton("📋 List Coupons", callback_data="adm_list_coupons")
        )
        bot.send_message(m.chat.id, "🎟 **Coupon Management Dashboard**", reply_markup=kb)
    elif text == "🎯 MISSIONS ADMIN":
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("➕ Create Mission", callback_data="adm_create_mission"),
            InlineKeyboardButton("🗑 Delete Mission", callback_data="adm_del_mission")
        )
        bot.send_message(m.chat.id, "🎯 **Missions Management Dashboard**", reply_markup=kb)
    elif text == "💡 REQUESTS ADMIN":
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("📋 All Requests", callback_data="adm_all_requests"),
            InlineKeyboardButton("🔥 Most Voted", callback_data="adm_voted_requests")
        )
        bot.send_message(m.chat.id, "💡 **Feature Requests Management Dashboard**", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_"))
def admin_sub_callbacks(call):
    if not is_admin(call.from_user.id):
        return
    data = call.data
    if data == "adm_prem_stats":
        active_count = len([s for s in premium_data["subscriptions"].values() if s["status"] == "ACTIVE"])
        expired_count = len(premium_data["subscriptions"]) - active_count
        total_stars = sum(p.get("stars_amount", 0) for p in premium_data["subscriptions"].values())
        text = f"""👑 **PREMIUM STATISTICS**

👥 Total Users: {len(users)}
⭐ Active Premium: {active_count}
⏰ Expired Premium: {expired_count}
💳 Total Stars: {total_stars}
🎁 Total Referrals: {sum(len(v) for v in referrals_data['records'].values())}
💡 Feature Requests: {len(feature_requests_data)}
🎟 Coupons Used: {sum(len(c.get('used_by', [])) for c in coupons_data.values())}
🎁 Gifts Sent: {len(gift_premium_data)}"""
        bot.answer_callback_query(call.id, "Stats loaded")
        bot.send_message(call.message.chat.id, text)
    elif data == "adm_create_coupon":
        msg = bot.send_message(call.message.chat.id, "Send coupon details in format:\n`CODE | REWARD_DAYS | MAX_USES`\n\nExample:\n`VIP2026 | 30 | 100`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_admin_create_coupon)

def process_admin_create_coupon(message):
    if not is_admin(message.from_user.id):
        return
    try:
        parts = [p.strip() for p in message.text.split("|")]
        code = parts[0].upper()
        days = int(parts[1])
        max_uses = int(parts[2])
        
        coupons_data[code] = {
            "reward_days": days,
            "max_uses": max_uses,
            "current_uses": 0,
            "active": True,
            "used_by": []
        }
        save_coupons()
        bot.send_message(message.chat.id, f"✅ Coupon `{code}` created successfully!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Format error: {e}")

# ================= STANDARD BOT COMMANDS & HANDLERS =================
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
    bot.send_message(m.chat.id, f"🔗 Your Referral Link:\n{link}\n\n👥 Invited Users: {invited}\n🎁 You earn $0.2 per referral!")

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

    bot.send_message(int(uid), f"✅ Withdrawal Request Sent\n🧾 Request ID: {wid}\n💵 Amount: ${amt:.2f}\n⏳ Status: Pending")

    admin_text = f"💳 NEW WITHDRAWAL\n\n👤 User: {uid}\n💵 Amount: ${amt:.2f}\n🧾 Request ID: {wid}"
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✅ CONFIRM", callback_data=f"confirm_{wid}"),
        InlineKeyboardButton("❌ REJECT", callback_data=f"reject_{wid}")
    )
    for admin in ADMIN_IDS:
        try:
            bot.send_message(admin, admin_text, reply_markup=markup)
        except:
            pass

@bot.callback_query_handler(func=lambda call: call.data.startswith(("confirm_", "reject_")))
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

@bot.message_handler(func=lambda m: m.text == "📊 STATS")
def stats_handler(m):
    if not is_admin(m.from_user.id):
        return
    bot.send_message(m.chat.id, f"📊 BOT STATS\n\n👥 Total Users: {len(users)}\n💰 Total Balance: ${sum(u.get('balance',0) for u in users.values()):.2f}")

@bot.message_handler(func=lambda m: m.text and "http" in m.text)
def handle_links(message):
    if bot_locked_guard(message):
        return
    user_id = message.from_user.id
    link = message.text
    
    # VIP Priority Processing Check
    if is_user_premium(user_id):
        bot.send_message(user_id, "👑 **VIP Priority Download Active**... Processing instantly.")
    
    bot.send_message(message.chat.id, "⏳ Downloading...")
    download_media(message.chat.id, link)

def extract_url(text):
    urls = re.findall(r'https?://[^\s]+', text)
    return urls[0] if urls else None

def send_video_with_music(chat_id, file_path, platform=None):
    vid_id = str(uuid.uuid4())[:8]
    video_files[vid_id] = file_path

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🎵 Convert to Music", callback_data=f"music_{vid_id}"))

    uid = str(chat_id)
    videos_data["total"] += 1
    videos_data["users"][uid] = videos_data["users"].get(uid, 0) + 1

    if platform:
        if "platforms" not in videos_data:
            videos_data["platforms"] = {}
        videos_data["platforms"][platform] = videos_data["platforms"].get(platform, 0) + 1
    save_videos()

    # Track mission progress for download
    if uid in missions_data["progress"]:
        pass

    CAPTION_TEXT = "Downloaded by VIP Downloader Bot"
    with open(file_path, "rb") as video:
        bot.send_video(chat_id, video, caption=CAPTION_TEXT, reply_markup=kb)

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
            ydl_opts = {"format": "bestvideo+bestaudio/best", "outtmpl": "youtube_%(id)s.%(ext)s", "merge_output_format": "mp4", "quiet": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file = ydl.prepare_filename(info)
            send_video_with_music(chat_id, file, "youtube")
            return

        bot.send_message(chat_id, "❌ Unsupported or broken link.")
    except Exception as e:
        bot.send_message(chat_id, f"❌ Download error: {e}")

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
            bot.send_audio(call.message.chat.id, audio, title="Converted Music", performer="VIP Bot")
        if os.path.exists(audio_path): os.remove(audio_path)
        if os.path.exists(file_path): os.remove(file_path)
        bot.answer_callback_query(call.id, "🎵 Music converted")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Conversion failed: {e}")

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
