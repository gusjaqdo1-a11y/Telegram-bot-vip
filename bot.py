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
REFERRAL_REWARDS_FILE = "referral_rewards.json"
REFERRAL_MILESTONES_FILE = "referral_milestones.json"
FEATURE_REQUESTS_FILE = "feature_requests.json"
FEATURE_VOTES_FILE = "feature_votes.json"
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

users = load_json(USERS_FILE, {})
withdraws = load_json(WITHDRAWS_FILE, [])
premium_data = load_json(PREMIUM_FILE, {
    "plans": {
        "7_days": {"name": "⭐ 7 Days", "duration": 7, "stars": 50, "active": True},
        "30_days": {"name": "⭐ 30 Days", "duration": 30, "stars": 150, "active": True},
        "90_days": {"name": "⭐ 90 Days", "duration": 90, "stars": 400, "active": True},
        "1_year": {"name": "⭐ 1 Year", "duration": 365, "stars": 1200, "active": True}
    },
    "subscriptions": {}
})
payments_data = load_json(PAYMENTS_FILE, [])
referrals_data = load_json(REFERRALS_FILE, {})
referral_rewards_data = load_json(REFERRAL_REWARDS_FILE, {})
referral_milestones_data = load_json(REFERRAL_MILESTONES_FILE, {
    "3": "⭐ 1 Day",
    "5": "⭐ 3 Days",
    "10": "⭐ 7 Days",
    "25": "⭐ 30 Days",
    "50": "⭐ 90 Days"
})
feature_requests_data = load_json(FEATURE_REQUESTS_FILE, [])
feature_votes_data = load_json(FEATURE_VOTES_FILE, {})
missions_data = load_json(MISSIONS_FILE, {
    "active": [
        {"id": "dl_10", "title": "📥 Download 10 Files", "target": 10, "reward_days": 1, "type": "download"},
        {"id": "ref_3", "title": "🎁 Invite 3 Friends", "target": 3, "reward_days": 2, "type": "referral"},
        {"id": "vote_3", "title": "💡 Vote on 3 Features", "target": 3, "reward_days": 1, "type": "vote"}
    ]
})
mission_progress_data = load_json(MISSION_PROGRESS_FILE, {})
coupons_data = load_json(COUPONS_FILE, {
    "VIP2026": {"reward_days": 30, "max_uses": 100, "uses": 0, "active": True},
    "WELCOME": {"reward_days": 7, "max_uses": 1000, "uses": 0, "active": True}
})
coupon_usage_data = load_json(COUPON_USAGE_FILE, {})
gift_premium_data = load_json(GIFT_PREMIUM_FILE, [])
vip_identity_data = load_json(VIP_IDENTITY_FILE, {})
user_settings_data = load_json(USER_SETTINGS_FILE, {})

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

def save_users(): save_json(USERS_FILE, users)
def save_withdraws(): save_json(WITHDRAWS_FILE, withdraws)
def save_videos(): save_json(VIDEOS_FILE, videos_data)
def save_premium(): save_json(PREMIUM_FILE, premium_data)
def save_payments(): save_json(PAYMENTS_FILE, payments_data)
def save_referrals(): save_json(REFERRALS_FILE, referrals_data)
def save_referral_rewards(): save_json(REFERRAL_REWARDS_FILE, referral_rewards_data)
def save_referral_milestones(): save_json(REFERRAL_MILESTONES_FILE, referral_milestones_data)
def save_feature_requests(): save_json(FEATURE_REQUESTS_FILE, feature_requests_data)
def save_feature_votes(): save_json(FEATURE_VOTES_FILE, feature_votes_data)
def save_missions(): save_json(MISSIONS_FILE, missions_data)
def save_mission_progress(): save_json(MISSION_PROGRESS_FILE, mission_progress_data)
def save_coupons(): save_json(COUPONS_FILE, coupons_data)
def save_coupon_usage(): save_json(COUPON_USAGE_FILE, coupon_usage_data)
def save_gift_premium(): save_json(GIFT_PREMIUM_FILE, gift_premium_data)
def save_vip_identity(): save_json(VIP_IDENTITY_FILE, vip_identity_data)
def save_user_settings(): save_json(USER_SETTINGS_FILE, user_settings_data)

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
    if uid_str in premium_data.get("subscriptions", {}):
        sub = premium_data["subscriptions"][uid_str]
        if sub.get("status") == "ACTIVE":
            expiry = datetime.strptime(sub["expiry_date"], "%Y-%m-%d %H:%M:%S")
            if datetime.now() < expiry:
                return True
            else:
                sub["status"] = "INACTIVE"
                save_premium()
                try:
                    bot.send_message(
                        int(uid),
                        "⏰ Your Premium has expired.\n\n⭐ Renew Premium to continue using VIP features.",
                        reply_markup=InlineKeyboardMarkup().add(
                            InlineKeyboardButton("⭐ Renew Premium", callback_data="buy_premium"),
                            InlineKeyboardButton("🏠 Home", callback_data="go_home")
                        )
                    )
                except:
                    pass
    return False

def get_user_vip_identity(uid):
    uid_str = str(uid)
    if uid_str not in vip_identity_data:
        vip_identity_data[uid_str] = {
            "title": "PRO" if is_user_premium(uid) else "VIP",
            "level": 1,
            "points": 0,
            "premium_since": datetime.now().strftime("%Y-%m-%d")
        }
        save_vip_identity()
    return vip_identity_data[uid_str]

def add_user_points(uid, pts):
    uid_str = str(uid)
    ident = get_user_vip_identity(uid_str)
    ident["points"] += pts
    ident["level"] = 1 + (ident["points"] // 100)
    save_vip_identity()

# ================= MENUS =================
def user_menu(show_admin=False):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📥 Downloader", "👑 Premium")
    kb.add("⚙️ Settings", "📊 My Stats")
    kb.add("💰 BALANCE", "💸 WITHDRAWAL")
    kb.add("👥 REFERRAL", "🆔 GET ID")
    kb.add("☎️ CUSTOMER", "🤖CUSTOMER AI")
    if show_admin:
        kb.add("👑 ADMIN PANEL")
    return kb

def admin_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("👑 PREMIUM MANAGEMENT", "🎁 REFERRALS", "💡 FEATURE REQUESTS")
    kb.add("🏆 LEADERBOARD", "🎯 MISSIONS", "🎟 COUPONS")
    kb.add("🎁 GIFT PREMIUM", "👑 VIP IDENTITY", "💳 STARS PAYMENTS")
    kb.add("📊 PREMIUM STATISTICS")
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

CHANNEL_USERNAME = "@tiktokvediodownload"

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
            ref = args[1].split("_")[1]

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
                referrals_data[str(uid)] = {"referrer": ref_user, "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                save_referrals()
                
                users[ref_user]["balance"] += 0.2
                users[ref_user]["invited"] += 1
                add_user_points(ref_user, 10)
                
                # Check Milestones
                inv_count = users[ref_user]["invited"]
                milestones = [3, 5, 10, 25, 50]
                for m_target in milestones:
                    if inv_count == m_target:
                        rew_key = f"{ref_user}_{m_target}"
                        if rew_key not in referral_rewards_data:
                            referral_rewards_data[rew_key] = True
                            save_referral_rewards()
                            try:
                                bot.send_message(int(ref_user), f"🎁 Congratulations! You reached {m_target} referrals and unlocked a milestone reward!")
                            except:
                                pass

                try:
                    bot.send_message(int(ref_user), "🎉 You earned $0.2 from referral!")
                except:
                    pass

        save_users()

    check_membership(uid)

@bot.message_handler(func=lambda m: m.text == "👑 Premium")
def premium_center_handler(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    uid = str(m.from_user.id)
    is_prem = is_user_premium(uid)
    sub = premium_data.get("subscriptions", {}).get(uid, {})
    
    status = "ACTIVE" if is_prem else "INACTIVE"
    plan_name = sub.get("plan_name", "None")
    expiry = sub.get("expiry_date", "N/A")
    
    days_left = 0
    if is_prem:
        exp_dt = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
        days_left = max(0, (exp_dt - datetime.now()).days)

    text = f"""╭━━━ 👑 PREMIUM CENTER ━━━╮

⭐ Status: {status}
💎 Plan: {plan_name}
📅 Expires: {expiry}
⏳ Days Left: {days_left}

✨ Unlock the full Premium experience!
╰━━━━━━━━━━━━━━━━━━━━━━╯"""

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⭐ Buy Premium", callback_data="buy_premium"),
        InlineKeyboardButton("💎 My Plan", callback_data="my_plan")
    )
    kb.add(
        InlineKeyboardButton("⚙️ Premium Settings", callback_data="prem_settings"),
        InlineKeyboardButton("📊 My Statistics", callback_data="my_stats")
    )
    kb.add(
        InlineKeyboardButton("🎁 Invite Friends", callback_data="invite_friends"),
        InlineKeyboardButton("💡 Feature Requests", callback_data="feature_requests")
    )
    kb.add(
        InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard"),
        InlineKeyboardButton("🎯 Missions", callback_data="missions")
    )
    kb.add(
        InlineKeyboardButton("🎟️ Coupons", callback_data="coupons"),
        InlineKeyboardButton("🎁 Gift Premium", callback_data="gift_premium")
    )
    kb.add(
        InlineKeyboardButton("👑 My VIP Identity", callback_data="vip_identity"),
        InlineKeyboardButton("🔙 Back", callback_data="go_home")
    )

    bot.send_message(m.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "go_home")
def callback_go_home(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "🏠 Main Menu", reply_markup=user_menu(is_admin(call.from_user.id)))

@bot.callback_query_handler(func=lambda call: call.data == "buy_premium")
def callback_buy_premium(call):
    kb = InlineKeyboardMarkup(row_width=2)
    for p_key, p_val in premium_data["plans"].items():
        if p_val.get("active", True):
            kb.add(InlineKeyboardButton(f"{p_val['name']} — ⭐ {p_val['stars']} Stars", callback_data=f"plan_{p_key}"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_center"))
    bot.edit_message_text("⭐ Choose your Premium Plan:", call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "premium_center")
def callback_premium_center(call):
    uid = str(call.from_user.id)
    is_prem = is_user_premium(uid)
    sub = premium_data.get("subscriptions", {}).get(uid, {})
    status = "ACTIVE" if is_prem else "INACTIVE"
    plan_name = sub.get("plan_name", "None")
    expiry = sub.get("expiry_date", "N/A")
    days_left = 0
    if is_prem:
        exp_dt = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
        days_left = max(0, (exp_dt - datetime.now()).days)

    text = f"""╭━━━ 👑 PREMIUM CENTER ━━━╮

⭐ Status: {status}
💎 Plan: {plan_name}
📅 Expires: {expiry}
⏳ Days Left: {days_left}

✨ Unlock the full Premium experience!
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⭐ Buy Premium", callback_data="buy_premium"),
        InlineKeyboardButton("💎 My Plan", callback_data="my_plan")
    )
    kb.add(
        InlineKeyboardButton("⚙️ Premium Settings", callback_data="prem_settings"),
        InlineKeyboardButton("📊 My Statistics", callback_data="my_stats")
    )
    kb.add(
        InlineKeyboardButton("🎁 Invite Friends", callback_data="invite_friends"),
        InlineKeyboardButton("💡 Feature Requests", callback_data="feature_requests")
    )
    kb.add(
        InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard"),
        InlineKeyboardButton("🎯 Missions", callback_data="missions")
    )
    kb.add(
        InlineKeyboardButton("🎟️ Coupons", callback_data="coupons"),
        InlineKeyboardButton("🎁 Gift Premium", callback_data="gift_premium")
    )
    kb.add(
        InlineKeyboardButton("👑 My VIP Identity", callback_data="vip_identity"),
        InlineKeyboardButton("🔙 Back", callback_data="go_home")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("plan_"))
def callback_choose_plan(call):
    p_key = call.data.split("_", 1)[1]
    plan = premium_data["plans"].get(p_key)
    if not plan:
        bot.answer_callback_query(call.id, "❌ Plan not found")
        return
    
    prices = [LabeledPrice(label=plan["name"], amount=plan["stars"] * 1)] # Telegram Stars amount (1 star = 1 unit depending on provider, here XTR)
    try:
        bot.send_invoice(
            chat_id=call.message.chat.id,
            title=f"Premium Subscription: {plan['name']}",
            description=f"Unlock VIP features for {plan['duration']} days.",
            invoice_payload=f"premium_{p_key}_{call.from_user.id}",
            provider_token="", # Empty for Telegram Stars
            currency="XTR",
            prices=[LabeledPrice(label=plan["name"], amount=plan["stars"])]
        )
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Error creating invoice: {e}", show_alert=True)

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    payment = message.successful_payment
    payload = payment.invoice_payload
    uid = str(message.from_user.id)
    
    if payload.startswith("premium_"):
        parts = payload.split("_")
        p_key = f"{parts[1]}_{parts[2]}" if len(parts) > 2 else parts[1]
        plan = premium_data["plans"].get(p_key)
        if plan:
            duration = plan["duration"]
            now = datetime.now()
            if uid in premium_data.get("subscriptions", {}) and premium_data["subscriptions"][uid]["status"] == "ACTIVE":
                cur_exp = datetime.strptime(premium_data["subscriptions"][uid]["expiry_date"], "%Y-%m-%d %H:%M:%S")
                if cur_exp > now:
                    new_exp = cur_exp + timedelta(days=duration)
                else:
                    new_exp = now + timedelta(days=duration)
            else:
                new_exp = now + timedelta(days=duration)

            premium_data.setdefault("subscriptions", {})[uid] = {
                "plan_id": p_key,
                "plan_name": plan["name"],
                "duration": duration,
                "stars_amount": payment.total_amount,
                "payment_id": payment.telegram_payment_charge_id,
                "start_date": now.strftime("%Y-%m-%d %H:%M:%S"),
                "expiry_date": new_exp.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "ACTIVE"
            }
            save_premium()
            
            payments_data.append({
                "user_id": uid,
                "type": "premium",
                "plan": p_key,
                "stars": payment.total_amount,
                "payment_id": payment.telegram_payment_charge_id,
                "time": now.strftime("%Y-%m-%d %H:%M:%S")
            })
            save_payments()
            add_user_points(uid, 50)

            bot.send_message(
                message.chat.id,
                f"🎉 Payment Confirmed!\n\n👑 Premium Activated!\n💎 Plan: {plan['name']}\n📅 Expires: {new_exp.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
    elif payload.startswith("gift_"):
        parts = payload.split("_")
        recipient_id = parts[1]
        p_key = f"{parts[2]}_{parts[3]}" if len(parts) > 3 else parts[2]
        plan = premium_data["plans"].get(p_key)
        if plan:
            duration = plan["duration"]
            now = datetime.now()
            new_exp = now + timedelta(days=duration)
            
            premium_data.setdefault("subscriptions", {})[recipient_id] = {
                "plan_id": p_key,
                "plan_name": plan["name"],
                "duration": duration,
                "stars_amount": payment.total_amount,
                "payment_id": payment.telegram_payment_charge_id,
                "start_date": now.strftime("%Y-%m-%d %H:%M:%S"),
                "expiry_date": new_exp.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "ACTIVE"
            }
            save_premium()
            
            gift_premium_data.append({
                "sender_id": uid,
                "recipient_id": recipient_id,
                "plan": p_key,
                "stars_amount": payment.total_amount,
                "payment_id": payment.telegram_payment_charge_id,
                "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "completed"
            })
            save_gift_premium()
            
            bot.send_message(message.chat.id, "🎁 Gift sent successfully!")
            try:
                bot.send_message(
                    int(recipient_id),
                    f"╭━━━ 🎁 PREMIUM GIFT ━━━╮\n\n🎉 You received Premium!\n\n💎 Plan: {plan['name']}\n📅 Expires: {new_exp.strftime('%Y-%m-%d %H:%M:%S')}\n\nEnjoy your Premium experience! 👑\n╰━━━━━━━━━━━━━━━━━━━━━━╯"
                )
            except:
                pass

@bot.callback_query_handler(func=lambda call: call.data == "my_plan")
def callback_my_plan(call):
    uid = str(call.from_user.id)
    is_prem = is_user_premium(uid)
    sub = premium_data.get("subscriptions", {}).get(uid, {})
    if not is_prem:
        bot.answer_callback_query(call.id, "❌ You do not have an active Premium plan.", show_alert=True)
        return
    text = f"💎 <b>Your Plan Details</b>\n\nPlan: {sub.get('plan_name')}\nStarted: {sub.get('start_date')}\nExpires: {sub.get('expiry_date')}"
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="premium_center"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "prem_settings")
def callback_prem_settings(call):
    uid = str(call.from_user.id)
    if not is_user_premium(uid):
        bot.answer_callback_query(call.id, "❌ Premium required.", show_alert=True)
        return
    text = "⚙️ <b>Premium Settings</b>\n\nManage your exclusive VIP preferences here."
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="premium_center"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "my_stats")
def callback_my_stats(call):
    uid = str(call.from_user.id)
    dl_count = videos_data.get("users", {}).get(uid, 0)
    ident = get_user_vip_identity(uid)
    text = f"📊 <b>Your Statistics</b>\n\n🎬 Downloads: {dl_count}\n🏆 Points: {ident['points']}\n🔥 VIP Level: {ident['level']}"
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="premium_center"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

# REFERRAL & REWARDS
@bot.callback_query_handler(func=lambda call: call.data == "invite_friends")
def callback_invite_friends(call):
    uid = str(call.from_user.id)
    bot_username = bot.get_me().username
    ref_code = users.get(uid, {}).get("ref", random_ref())
    link = f"https://t.me/{bot_username}?start=ref_{ref_code}"
    invited = users.get(uid, {}).get("invited", 0)
    
    text = f"""╭━━━ 🎁 INVITE & EARN ━━━╮

👥 Referrals: {invited}
🎁 Rewards: ⭐ Active
🏆 Rank: #1

Invite your friends and earn rewards!
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={link}&text=Join%20this%20awesome%20Downloader%20Bot!"),
        InlineKeyboardButton("👥 My Referrals", callback_data="my_referrals")
    )
    kb.add(
        InlineKeyboardButton("🎁 My Rewards", callback_data="my_rewards"),
        InlineKeyboardButton("🏆 My Rank", callback_data="my_rank")
    )
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_center"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "my_referrals")
def callback_my_referrals(call):
    uid = str(call.from_user.id)
    invited = users.get(uid, {}).get("invited", 0)
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="invite_friends"))
    bot.edit_message_text(f"👥 <b>My Referrals</b>\n\nTotal Invited Users: {invited}", call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "my_rewards")
def callback_my_rewards(call):
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="invite_friends"))
    bot.edit_message_text("🎁 <b>My Rewards</b>\n\nAll milestones and earned rewards are up to date.", call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "my_rank")
def callback_my_rank(call):
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="invite_friends"))
    bot.edit_message_text("🏆 <b>My Rank</b>\n\nYou are among the top active users!", call.message.chat.id, call.message.message_id, reply_markup=kb)

# FEATURE REQUESTS
@bot.callback_query_handler(func=lambda call: call.data == "feature_requests")
def callback_feature_requests(call):
    uid = str(call.from_user.id)
    if not is_user_premium(uid):
        bot.answer_callback_query(call.id, "❌ Feature Requests is a Premium-only feature.", show_alert=True)
        return
    
    sorted_reqs = sorted(feature_requests_data, key=lambda x: x.get("votes", 0), reverse=True)
    text = "╭━━━ 💡 FEATURE REQUESTS ━━━╮\n\n🔥 MOST REQUESTED\n\n"
    for i, req in enumerate(sorted_reqs[:3], start=1):
        text += f"{i}️⃣ {req['title']}\n👍 {req['votes']} Votes\n\n"
    text += "╰━━━━━━━━━━━━━━━━━━━━━━╯"

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("👍 Vote", callback_data="vote_feature_list"),
        InlineKeyboardButton("💡 Submit Feature", callback_data="submit_feature")
    )
    kb.add(
        InlineKeyboardButton("📋 My Requests", callback_data="my_requests"),
        InlineKeyboardButton("🔥 Most Requested", callback_data="feature_requests")
    )
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_center"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "submit_feature")
def callback_submit_feature(call):
    uid = str(call.from_user.id)
    if not is_user_premium(uid):
        bot.answer_callback_query(call.id, "❌ Premium required.", show_alert=True)
        return
    msg = bot.send_message(call.message.chat.id, "💡 Send the title for your feature request:")
    bot.register_next_step_handler(msg, process_feature_title)

def process_feature_title(message):
    uid = str(message.from_user.id)
    title = message.text.strip()
    msg = bot.send_message(message.chat.id, "📝 Now send the description for your feature request:")
    bot.register_next_step_handler(msg, process_feature_desc, title)

def process_feature_desc(message, title):
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
    add_user_points(uid, 15)
    bot.send_message(message.chat.id, "✅ Feature request submitted successfully!", reply_markup=user_menu(is_admin(uid)))

@bot.callback_query_handler(func=lambda call: call.data == "vote_feature_list")
def callback_vote_feature_list(call):
    kb = InlineKeyboardMarkup(row_width=1)
    for req in feature_requests_data[:10]:
        kb.add(InlineKeyboardButton(f"👍 {req['title']} ({req['votes']} votes)", callback_data=f"vote_req_{req['request_id']}"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="feature_requests"))
    bot.edit_message_text("👍 Select a feature to vote:", call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("vote_req_"))
def callback_vote_req(call):
    uid = str(call.from_user.id)
    req_id = call.data.split("_")[2]
    
    feature_votes_data.setdefault(uid, [])
    if req_id in feature_votes_data[uid]:
        bot.answer_callback_query(call.id, "❌ You have already voted for this feature.", show_alert=True)
        return
    
    feature_votes_data[uid].append(req_id)
    save_feature_votes()
    
    for req in feature_requests_data:
        if req["request_id"] == req_id:
            req["votes"] += 1
            save_feature_requests()
            break
            
    bot.answer_callback_query(call.id, "✅ Vote recorded!")
    callback_feature_requests(call)

@bot.callback_query_handler(func=lambda call: call.data == "my_requests")
def callback_my_requests(call):
    uid = str(call.from_user.id)
    user_reqs = [r for r in feature_requests_data if r["user_id"] == uid]
    text = "📋 <b>Your Feature Requests</b>\n\n"
    for r in user_reqs:
        text += f"• {r['title']} [{r['status']}] - {r['votes']} votes\n"
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="feature_requests"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

# LEADERBOARD
@bot.callback_query_handler(func=lambda call: call.data == "leaderboard")
def callback_leaderboard(call):
    sorted_users = sorted(vip_identity_data.items(), key=lambda x: x[1].get("points", 0), reverse=True)
    text = "╭━━━ 🏆 PREMIUM LEADERBOARD ━━━╮\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, (u, data) in enumerate(sorted_users[:3], start=1):
        text += f"{medals[i-1]} User {u} — {data.get('points', 0)} Points\n"
    text += "\n━━━━━━━━━━━━━━━━━━\n\n⭐ YOUR POSITION\n"
    uid = str(call.from_user.id)
    my_pts = vip_identity_data.get(uid, {}).get("points", 0)
    my_rank = "N/A"
    for i, (u, data) in enumerate(sorted_users, start=1):
        if u == uid:
            my_rank = f"#{i}"
            break
    text += f"Rank: {my_rank}\nPoints: {my_pts}\n\n╰━━━━━━━━━━━━━━━━━━━━━━╯"
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📊 My Rank", callback_data="my_rank"),
        InlineKeyboardButton("🎁 My Rewards", callback_data="my_rewards")
    )
    kb.add(
        InlineKeyboardButton("📅 Weekly", callback_data="lb_weekly"),
        InlineKeyboardButton("📆 Monthly", callback_data="lb_monthly"),
        InlineKeyboardButton("🏆 All Time", callback_data="leaderboard")
    )
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_center"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data in ["lb_weekly", "lb_monthly"])
def callback_lb_filter(call):
    callback_leaderboard(call)

# MISSIONS
@bot.callback_query_handler(func=lambda call: call.data == "missions")
def callback_missions(call):
    uid = str(call.from_user.id)
    text = "╭━━━ 🎯 PREMIUM MISSIONS ━━━╮\n\n🔥 ACTIVE MISSIONS\n\n"
    for m in missions_data.get("active", []):
        progress = mission_progress_data.get(uid, {}).get(m["id"], 0)
        status_str = f"{progress}/{m['target']}" if progress < m['target'] else "✅ Completed"
        text += f"• {m['title']}\nProgress: {status_str}\n🎁 Reward: ⭐ {m['reward_days']} Day(s)\n\n"
    text += "╰━━━━━━━━━━━━━━━━━━━━━━╯"
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🎯 Active Missions", callback_data="missions"),
        InlineKeyboardButton("🎁 Completed", callback_data="missions_completed")
    )
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="premium_center"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "missions_completed")
def callback_missions_completed(call):
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="missions"))
    bot.edit_message_text("🎁 <b>Completed Missions</b>\n\nAll claimed mission rewards are recorded.", call.message.chat.id, call.message.message_id, reply_markup=kb)

# COUPONS
@bot.callback_query_handler(func=lambda call: call.data == "coupons")
def callback_coupons(call):
    text = "╭━━━ 🎟️ PREMIUM COUPON ━━━╮\n\nEnter your coupon code below.\n\nExample:\nVIP2026\n╰━━━━━━━━━━━━━━━━━━━━━━╯"
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="premium_center"))
    msg = bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.register_next_step_handler(msg, process_coupon_code)

def process_coupon_code(message):
    uid = str(message.from_user.id)
    code = message.text.strip().upper()
    
    if code not in coupons_data or not coupons_data[code].get("active", True):
        bot.send_message(message.chat.id, "❌ Invalid or inactive coupon code.", reply_markup=user_menu(is_admin(uid)))
        return
        
    coupon = coupons_data[code]
    coupon_usage_data.setdefault(code, [])
    if uid in coupon_usage_data[code]:
        bot.send_message(message.chat.id, "❌ You have already used this coupon.", reply_markup=user_menu(is_admin(uid)))
        return
        
    if coupon["uses"] >= coupon["max_uses"]:
        bot.send_message(message.chat.id, "❌ Coupon usage limit reached.", reply_markup=user_menu(is_admin(uid)))
        return
        
    coupon["uses"] += 1
    coupon_usage_data[code].append(uid)
    save_coupons()
    save_coupon_usage()
    
    duration = coupon["reward_days"]
    now = datetime.now()
    if uid in premium_data.get("subscriptions", {}) and premium_data["subscriptions"][uid]["status"] == "ACTIVE":
        cur_exp = datetime.strptime(premium_data["subscriptions"][uid]["expiry_date"], "%Y-%m-%d %H:%M:%S")
        new_exp = cur_exp + timedelta(days=duration) if cur_exp > now else now + timedelta(days=duration)
    else:
        new_exp = now + timedelta(days=duration)
        
    premium_data.setdefault("subscriptions", {})[uid] = {
        "plan_id": "coupon",
        "plan_name": f"Coupon ({code})",
        "duration": duration,
        "stars_amount": 0,
        "payment_id": f"coupon_{code}",
        "start_date": now.strftime("%Y-%m-%d %H:%M:%S"),
        "expiry_date": new_exp.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "ACTIVE"
    }
    save_premium()
    add_user_points(uid, 30)
    
    bot.send_message(message.chat.id, f"🎉 Coupon applied successfully!\n\n👑 Premium activated for {duration} days!", reply_markup=user_menu(is_admin(uid)))

# GIFT PREMIUM
@bot.callback_query_handler(func=lambda call: call.data == "gift_premium")
def callback_gift_premium(call):
    msg = bot.send_message(call.message.chat.id, "🎁 Send the recipient's @username or Telegram ID:")
    bot.register_next_step_handler(msg, process_gift_recipient)

def process_gift_recipient(message):
    uid = str(message.from_user.id)
    target = message.text.strip().replace("@", "")
    
    recipient_id = None
    if target.isdigit():
        recipient_id = target
    else:
        for u, d in users.items():
            if d.get("username", "").lower() == target.lower():
                recipient_id = u
                break
                
    if not recipient_id:
        bot.send_message(message.chat.id, "❌ User not found.", reply_markup=user_menu(is_admin(uid)))
        return
        
    kb = InlineKeyboardMarkup(row_width=2)
    for p_key, p_val in premium_data["plans"].items():
        if p_val.get("active", True):
            kb.add(InlineKeyboardButton(f"{p_val['name']} — ⭐ {p_val['stars']} Stars", callback_data=f"giftplan_{recipient_id}_{p_key}"))
    bot.send_message(message.chat.id, "⭐ Choose plan to gift:", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("giftplan_"))
def callback_gift_plan(call):
    parts = call.data.split("_")
    recipient_id = parts[1]
    p_key = f"{parts[2]}_{parts[3]}" if len(parts) > 3 else parts[2]
    plan = premium_data["plans"].get(p_key)
    if not plan:
        bot.answer_callback_query(call.id, "❌ Plan not found")
        return
        
    try:
        bot.send_invoice(
            chat_id=call.message.chat.id,
            title=f"Gift Premium: {plan['name']}",
            description=f"Gift VIP features for {plan['duration']} days to user {recipient_id}.",
            invoice_payload=f"gift_{recipient_id}_{p_key}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label=plan["name"], amount=plan["stars"])]
        )
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Error: {e}", show_alert=True)

# VIP IDENTITY
@bot.callback_query_handler(func=lambda call: call.data == "vip_identity")
def callback_vip_identity(call):
    uid = str(call.from_user.id)
    ident = get_user_vip_identity(uid)
    username = call.from_user.username or "User"
    
    text = f"""╭━━━ 👑 VIP IDENTITY ━━━╮

👤 User: @{username}

⭐ Current Title:
💎 {ident['title']}

📅 Premium Since:
{ident['start'] if 'start' in ident else ident['premium_since']}

🔥 VIP Level:
Level {ident['level']}

🏆 Points:
{ident['points']}

╰━━━━━━━━━━━━━━━━━━━━━━╯"""

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
        InlineKeyboardButton("🎨 Customize", callback_data="cust_identity"),
        InlineKeyboardButton("🔙 Back", callback_data="premium_center")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_title_"))
def callback_set_title(call):
    uid = str(call.from_user.id)
    title = call.data.split("_")[2]
    ident = get_user_vip_identity(uid)
    ident["title"] = title
    save_vip_identity()
    bot.answer_callback_query(call.id, f"✅ Title updated to {title}!")
    callback_vip_identity(call)

@bot.callback_query_handler(func=lambda call: call.data == "cust_identity")
def callback_cust_identity(call):
    bot.answer_callback_query(call.id, "🎨 Customization feature active.")

# ================= ADMIN PANEL ADVANCED =================
@bot.message_handler(func=lambda m: m.text in ["👑 PREMIUM MANAGEMENT", "🎁 REFERRALS", "💡 FEATURE REQUESTS", "🏆 LEADERBOARD", "🎯 MISSIONS", "🎟 COUPONS", "🎁 GIFT PREMIUM", "👑 VIP IDENTITY", "💳 STARS PAYMENTS", "📊 PREMIUM STATISTICS"])
def admin_advanced_router(m):
    if not is_admin(m.from_user.id):
        return
    text = m.text
    if text == "👑 PREMIUM MANAGEMENT":
        bot.send_message(m.chat.id, "👑 Premium Management Panel\n\nOptions:\n- Search User\n- Give/Remove/Extend Premium\n- Change Plan", reply_markup=admin_menu())
    elif text == "🎁 REFERRALS":
        bot.send_message(m.chat.id, f"🎁 Referral Management\n\nTotal Referrals Tracked: {len(referrals_data)}", reply_markup=admin_menu())
    elif text == "💡 FEATURE REQUESTS":
        bot.send_message(m.chat.id, f"💡 Feature Requests Management\n\nTotal Requests: {len(feature_requests_data)}", reply_markup=admin_menu())
    elif text == "🏆 LEADERBOARD":
        bot.send_message(m.chat.id, "🏆 Leaderboard Management\n\nPoints system active.", reply_markup=admin_menu())
    elif text == "🎯 MISSIONS":
        bot.send_message(m.chat.id, "🎯 Missions Management (CRUD Active)", reply_markup=admin_menu())
    elif text == "🎟 COUPONS":
        bot.send_message(m.chat.id, f"🎟 Coupon Management\n\nTotal Coupons: {len(coupons_data)}", reply_markup=admin_menu())
    elif text == "🎁 GIFT PREMIUM":
        bot.send_message(m.chat.id, f"🎁 Gift Premium Management\n\nTotal Gifts Sent: {len(gift_premium_data)}", reply_markup=admin_menu())
    elif text == "👑 VIP IDENTITY":
        bot.send_message(m.chat.id, "👑 VIP Identity Management active.", reply_markup=admin_menu())
    elif text == "💳 STARS PAYMENTS":
        bot.send_message(m.chat.id, f"💳 Stars Payments\n\nTotal Transactions: {len(payments_data)}", reply_markup=admin_menu())
    elif text == "📊 PREMIUM STATISTICS":
        total_users = len(users)
        active_prem = len([u for u, s in premium_data.get("subscriptions", {}).items() if s.get("status") == "ACTIVE"])
        total_stars = sum(p.get("stars", 0) for p in payments_data)
        bot.send_message(
            m.chat.id,
            f"👑 <b>PREMIUM STATISTICS</b>\n\n"
            f"👥 Total Users: {total_users}\n"
            f"⭐ Active Premium: {active_prem}\n"
            f"💳 Total Stars: {total_stars}\n"
            f"🎁 Total Referrals: {len(referrals_data)}\n"
            f"💡 Feature Requests: {len(feature_requests_data)}\n"
            f"🎟 Coupons Used: {len(coupon_usage_data)}\n"
            f"🎁 Gifts Sent: {len(gift_premium_data)}"
        )

# ================= EXISTING ADMIN & BOT LOGIC =================
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
        bot.send_message(m.chat.id, "❌ No channels added.")
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
        except:
            pass
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
        f"• Pinterest: {platform_stats.get('pinterest',0)}\n"
    ]
    bot.send_message(m.chat.id, "\n".join(msg_lines), parse_mode="HTML")

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
    msg = bot.send_message(m.chat.id, "Send channel usernames\nExample:\n@channel1\n\nSend DONE when finished.")
    bot.register_next_step_handler(msg, post_channel_add)

def post_channel_add(m):
    if m.text.lower() == "done":
        bot.send_message(m.chat.id, f"✅ {len(POST_CHANNELS)} channels added.")
        return
    username = m.text.replace("@", "").strip()
    POST_CHANNELS.append(username)
    msg = bot.send_message(m.chat.id, f"Channel @{username} added. Send another or DONE")
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
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("💬 OPEN CHAT", url=f"tg://user?id={uid}"))
        bot.send_message(m.chat.id, f"👤 User ID: {uid}", reply_markup=kb)
        count += 1
        if count >= 20:
            break
    bot.send_message(m.chat.id, f"📊 Total Users: {total}")

@bot.message_handler(func=lambda m: m.text == "🔒 LOCK BOT")
def lock_bot_start(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "✍️ Send the lock message users should receive.")
    bot.register_next_step_handler(msg, lock_bot_process)

def lock_bot_process(m):
    global BOT_LOCKED, LOCK_MESSAGE
    if not is_admin(m.from_user.id):
        return
    text = (m.text or "").strip()
    LOCK_MESSAGE = text
    BOT_LOCKED = True
    bot.send_message(m.chat.id, "🔒 Bot locked successfully.")

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
    bot.send_message(m.chat.id, "✅ Ads-ka waa la kaydiyay lana shiday!")

@bot.message_handler(func=lambda m: m.text == "🗑 DELETE ADS")
def delete_ads(m):
    global ADS_ENABLED, ADS_BTN_TEXT, ADS_URL, ADS_TEXT
    if not is_admin(m.from_user.id):
        return
    ADS_ENABLED = False
    ADS_BTN_TEXT = ""
    ADS_URL = ""
    ADS_TEXT = ""
    bot.send_message(m.chat.id, "🗑 Ads-kii waa la tirtiray.")

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
                "balance": 0.0, "blocked": 0.0, "ref": random_ref(), "bot_id": random_botid(),
                "invited": 0, "banned": False, "verified": False, "month": now_month()
            }
            added += 1
    save_users()
    bot.send_message(m.chat.id, f"✅ Imported {added} users successfully.")

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
    msg = bot.send_message(m.chat.id, f"User: @{username}\nNow send referral code number:")
    bot.register_next_step_handler(msg, lambda x: save_custom_ref_code(x, username))

def save_custom_ref_code(m, username):
    if not is_admin(m.from_user.id):
        return
    code = m.text.strip()
    user_id = next((uid for uid, data in users.items() if data.get("username", "").lower() == username.lower()), None)
    if not user_id:
        bot.send_message(m.chat.id, "❌ User not found")
        return
    users[user_id]["ref"] = code
    save_users()
    bot.send_message(m.chat.id, f"✅ Referral code created for @{username}")

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
        bot.send_message(m.chat.id, f"👤 User Found\nID: {uid}", reply_markup=kb)
    else:
        bot.send_message(m.chat.id, "❌ User not found")

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
        bot.answer_callback_query(call.id, "✅ Join verified")
        if user_id in pending_links:
            link = pending_links[user_id]
            del pending_links[user_id]
            download_media(user_id, link)
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
        
        platform = "youtube" if "youtube" in url or "youtu.be" in url else "instagram" if "instagram" in url else "facebook" if "facebook" in url else "other"
        send_video_with_music(chat_id, file, platform)
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
            bot.send_audio(call.message.chat.id, audio, title="Converted Music", performer="DownloadBot", caption=CAPTION_TEXT)
        if os.path.exists(audio_path): os.remove(audio_path)
        if os.path.exists(file_path): os.remove(file_path)
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
    t1 = threading.Thread(target=run_bot1)
    t2 = threading.Thread(target=run_bot2)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
