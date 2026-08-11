import telebot
import requests
from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
import os, json, random
from datetime import datetime
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


# ================= DATABASE FILES =================
USERS_FILE = "users.json"
WITHDRAWS_FILE = "withdraws.json"
VIDEOS_FILE = "videos.json"

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

# ================= LOAD DATA =================
users = load_json(USERS_FILE, {})
withdraws = load_json(WITHDRAWS_FILE, [])

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

# ================= MENUS =================
def user_menu(show_admin=False):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
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
    kb.add("✅ VERIFY ON", "❌ VERIFY OFF")
    kb.add("CHANNEL POST", "📡 ADD CHANNEL")
    kb.add("🔒 LOCK BOT", "🔓 UNLOCK BOT")  
    kb.add("❌ CLOSE WINDOWS", "CLOSE CHANNEL POST")
    kb.add("📥 IMPORT USERS")
    kb.add("🔗 GET REFERRAL CODE")
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
    ...

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
            if ref_user:
                users[ref_user]["balance"] += 0.2
                users[ref_user]["invited"] += 1
                bot.send_message(int(ref_user), "🎉 You earned $0.2 from referral!")

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

    # ===== haddii code jiro =====
    if len(args) > 1:

        code = args[1]

        bot2.send_message(
            message.chat.id,
            f"🔑 <b>Your Verification Code</b>\n\n"
            f"<code>{code}</code>\n\n"
            "Copy this code and send it to the downloader bot."
        )

    # ===== haddii code jirin =====
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

⚡ Fast & Easy Downloads
Our system processes your request quickly and sends the highest available quality whenever possible.

💰 Earn Money With Referrals
You can also earn rewards by inviting your friends to use the bot.

Here is how it works:
• Share your personal referral link with others.
• When someone joins the bot using your link, you receive a reward.
• The more people you invite, the more rewards you earn.

🚀 Why use this bot?
• Fast downloading system
• Supports multiple platforms
• Simple and easy to use
• Earn rewards through referrals

📌 Important:
Please make sure you follow the required channel(s) to continue using the bot and to keep the service running.

Now you're ready to start!

👇 Send any video link to begin downloading.""",
                reply_markup=user_menu(is_admin(user_id))
            )
        else:
            send_join_message(user_id)

    except:
        send_join_message(user_id)

    # ================= FG ===============
@bot.callback_query_handler(func=lambda call: call.data.startswith("postbtn_"))
def post_button_click(call):

    index = int(call.data.split("_")[1])

    data = channel_posts.get(call.message.message_id)

    if not data:
        return

    if index >= len(data["buttons"]):
        return

    text = data["buttons"][index]["content"]

    kb = InlineKeyboardMarkup()

    for i, btn in enumerate(data["buttons"]):

        kb.add(
            InlineKeyboardButton(
                btn["name"],
                callback_data=f"postbtn_{i}"
            )
        )

    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=kb
    )


# ================= SEND JOIN MESSAGE =================
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

        bot.send_message(
            call.message.chat.id,
            "📩 Code sent to your Telegram DM.\n\nSend the code here."
        )

    else:

        bot.send_message(
            call.message.chat.id,
            "❌ Cannot send DM.\nUser must message your Telegram account first."
        )

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

    verify_pending[uid] = {
        "code": code
    }

    success = send_gmail_code(email, code)

    if success:

        bot.send_message(
            message.chat.id,
            "📩 Code sent to your Gmail.\nSend the code here."
        )

    else:

        bot.send_message(
            message.chat.id,
            "❌ Failed to send email."
        )
    
# ================= 56 =================
def send_multi_join(user_id):

    kb = InlineKeyboardMarkup(row_width=3)

    buttons = []

    for ch in POST_CHANNELS:

        buttons.append(
            InlineKeyboardButton(
                "➕️ JOIN",
                url=f"https://t.me/{ch}"
            )
        )

    kb.add(*buttons)

    kb.add(
        InlineKeyboardButton(
            "✅ CONFIRM",
            callback_data="multi_checkjoin"
        )
    )

    bot.send_message(
        user_id,
        "⚠️ Join all channels to continue.",
        reply_markup=kb
    )

async def send_code_telegram(user_id, code):

    try:

        user = await tg_client.get_entity(user_id)

        await tg_client.send_message(
            user,
            f"🔐 Your verification code:\n\n{code}"
        )

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

        bot.send_message(
            call.message.chat.id,
            "✅ Code sent to your Telegram messages.\nSend the code here."
        )

    else:

        bot.send_message(
            call.message.chat.id,
            "⚠️ Telegram blocked sending message.\nUser must message your account first."
        )

@bot.callback_query_handler(func=lambda call: call.data == "verify_email")
def verify_email(call):

    msg = bot.send_message(
        call.message.chat.id,
        "📧 Send your Gmail address to receive verification code."
    )

    bot.register_next_step_handler(msg, process_email)

# ================= CONFIRM JOIN =================
@bot.callback_query_handler(func=lambda call: call.data == "confirm_join")
def confirm_join(call):

    user_id = call.from_user.id

    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)

        if member.status in ["member","administrator","creator"]:

            bot.answer_callback_query(call.id,"✅ Join verified")

            # DELETE join message
            bot.delete_message(call.message.chat.id, call.message.message_id)

            bot.send_message(
                user_id,
                "✅ Join confirmed!\nNow you can use the bot.\nSend your video link."
            )

        else:

            bot.answer_callback_query(
                call.id,
                "❌ You must join the channel first!",
                show_alert=True
            )

    except:

        bot.answer_callback_query(
            call.id,
            "❌ Please join the channel first!",
            show_alert=True
        )

# ================= ADMIN PANEL =================
@bot.message_handler(func=lambda m: m.text == "👑 ADMIN PANEL")
def open_admin_panel(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ You are not admin")
        return
    bot.send_message(m.chat.id, "👑 Admin Panel", reply_markup=admin_menu())

    # ================= BALANCE =================
@bot.message_handler(func=lambda m: m.text == "💰 BALANCE")
def balance_handler(m):
    if bot_locked_guard(m):
        return
    if banned_guard(m):
        return
    ...
    uid = str(m.from_user.id)
    bal = users[uid].get("balance", 0.0)
    blocked = users[uid].get("blocked", 0.0)
    bot.send_message(
        m.chat.id,
        f"💰 Available Balance: ${bal:.2f}\n"
        f"⏳ Blocked Amount: ${blocked:.2f}"
    )

# ================= GET ID =================
@bot.message_handler(func=lambda m: m.text == "🆔 GET ID")
def get_id_handler(m):
    if bot_locked_guard(m):
        return
    if banned_guard(m):
        return
    ...
    uid = str(m.from_user.id)
    bot.send_message(
        m.chat.id,
        f"🆔 BOT ID: <code>{users[uid]['bot_id']}</code>\n"
        f"👤 Telegram ID: <code>{uid}</code>"
    )

# ================= REFERRAL =================
@bot.message_handler(func=lambda m: m.text == "👥 REFERRAL")
def referral_handler(m):
    if bot_locked_guard(m):
        return
    if banned_guard(m):
        return
    ...
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

# ================= CUSTOMER SUPPORT =================
@bot.message_handler(func=lambda m: m.text == "☎️ CUSTOMER")
def customer_handler(m):
    if bot_locked_guard(m):
        return
    if banned_guard(m):
        return
    ...
    bot.send_message(
        m.chat.id,
        "☎️ Customer Support:\n@scholes1"
    )

@bot.message_handler(func=lambda m: m.text == "🤖CUSTOMER AI")
def customer_handler(m):
    if bot_locked_guard(m):
        return
    if banned_guard(m):
        return
    ...
    bot.send_message(
        m.chat.id,
        "Ai Customer Support🤖:\n@Aidownoaderbot"
)

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

# ================= WITHDRAWAL METHOD =================
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

# ================= WITHDRAWAL ADDRESS =================
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

# ================= WITHDRAWAL AMOUNT =================
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

    # ================= CREATE WITHDRAWAL REQUEST =================
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

    # ===== Create withdrawal request =====
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

    # ===== Notify user =====
    bot.send_message(
        int(uid),
        f"✅ Withdrawal Request Sent\n"
        f"🧾 Request ID: {wid}\n"
        f"💵 Amount: ${amt:.2f}\n"
        f"🏦 Address: {withdrawal['address']}\n"
        f"💰 Balance Left: ${users[uid]['balance']:.2f}\n"
        f"⏳ Status: Pending"
    )

    # ===== Notify admins =====
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

    # Loop through admin IDs
    for admin in [7983838654]:  # Halkan waxaad ku dari kartaa liiska admin IDs
        bot.send_message(admin, admin_text, reply_markup=markup)

    # ================= ADMIN INLINE CALLBACKS =================
@bot.callback_query_handler(func=lambda call: call.data.startswith(("confirm_", "reject_", "ban_", "block_")))
def admin_callbacks(call):

    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ You are not admin")
        return

    data = call.data

    # ===== CONFIRM WITHDRAWAL =====
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

    # ===== REJECT WITHDRAWAL =====
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

    # ===== BAN USER =====
    elif data.startswith("ban_"):
        uid = data.split("_")[1]
        if uid in users:
            users[uid]["banned"] = True
            save_users()
            bot.answer_callback_query(call.id, "🚫 User banned")
            bot.send_message(int(uid), "🚫 You have been banned by admin.")

    # ===== BLOCK MONEY =====
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

# ================= UNBLOCK MONEY =================
@bot.message_handler(func=lambda m: m.text == "💰 UNBLOCK MONEY")
def unblock_money_start(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ You are not admin")
        return

    msg = bot.send_message(
        m.chat.id,
        "🔢 Send 4-digit Block Code to UNBLOCK funds:"
    )
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

    bot.send_message(
        int(uid),
        f"✅ Your blocked ${amt:.2f} is now available in balance!"
    )
    bot.send_message(
        m.chat.id,
        f"✅ Money unblocked for user {uid}"
    )


# ================= UNBAN USER =================
@bot.message_handler(func=lambda m: m.text == "🔥 UN BAN-USER")
def unban_user_start(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ You are not admin")
        return

    msg = bot.send_message(
        m.chat.id,
        "Send Telegram ID of user to UNBAN:"
    )
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

# ================= WITHDRAWAL CHECK =================
@bot.message_handler(func=lambda m: m.text == "💳 WITHDRAWAL CHECK")
def withdrawal_check_start(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ You are not admin")
        return

    msg = bot.send_message(
        m.chat.id,
        "Enter Withdrawal Request ID (example: 40201):"
    )
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


# ================= STATS =================
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

    msg = (
        f"📊 BOT STATS\n\n"
        f"👥 Total Users: {total_users}\n"
        f"💰 Total Balance: ${total_balance:.2f}\n"
        f"⏳ Total Blocked: ${total_blocked:.2f}\n"
        f"🧾 Total Withdrawals: {total_withdraws}\n"
        f"⏳ Pending Withdrawals: {pending_withdraws}"
    )

    bot.send_message(m.chat.id, msg)

# ================= MANUAL BAN =================
@bot.message_handler(func=lambda m: m.text == "🚫 BAN USER MANUAL")
def manual_ban_start(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ You are not admin")
        return

    msg = bot.send_message(
        m.chat.id,
        "Send Telegram ID or BOT ID to BAN user:"
    )
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

    # ================= ADD CHANNEL =================

@bot.message_handler(func=lambda m: m.text == "📡 ADD CHANNEL")
def add_channel_start(m):

    if not is_admin(m.from_user.id):
        return

    msg = bot.send_message(
        m.chat.id,
        "Send channel username\nExample:\n@mychannel"
    )

    bot.register_next_step_handler(msg, add_channel_process)


def add_channel_process(m):

    username = m.text.strip()

    try:

        member = bot.get_chat_member(username, bot.get_me().id)

        if member.status not in ["administrator", "creator"]:

            bot.send_message(
                m.chat.id,
                "❌ Bot is not admin in this channel"
            )
            return

        if username not in MANAGED_CHANNELS:
            MANAGED_CHANNELS.append(username)

        bot.send_message(
            m.chat.id,
            f"✅ Channel Added\n{username}"
        )

    except:

        bot.send_message(
            m.chat.id,
            "❌ Invalid channel or bot not inside channel"
        )
    
# ================= CHANEL =================
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
            bot.send_message(
                ch,
                text,
                reply_markup=kb
            )
            sent += 1
        except Exception as e:
            print("Channel post error:", e)

    bot.send_message(
        m.chat.id,
        f"✅ Posted to {sent} channel(s)"
    )

# ================= LANGUAGE SWITCH =================

channel_posts = {}

@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def channel_language(call):

    lang = call.data.split("_")[1]

    if call.message.message_id not in channel_posts:
        return

    data = channel_posts[call.message.message_id]

    if lang == "so":
        text = data["so"]
    else:
        text = data["en"]

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("🇸🇴 Somali", callback_data="lang_so"),
        InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    )

    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=kb
    )

# ================= RAADI (DOWNLOAD STATS) =================
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

    # Top downloader
    top_user_id, top_count = max(users_stats.items(), key=lambda x: x[1])

    # Build message
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

    # Top 3 users
    sorted_users = sorted(users_stats.items(), key=lambda x: x[1], reverse=True)
    for i, (uid, count) in enumerate(sorted_users[:40], start=1):
        bot_id = users.get(str(uid), {}).get("bot_id", "N/A")
        msg_lines.append(f"{i}. 👤 <a href='tg://user?id={uid}'>{uid}</a> - 🎬 {count} videos | 🤖 BOT ID: {bot_id}")

    msg_text = "\n".join(msg_lines)
    bot.send_message(m.chat.id, msg_text, parse_mode="HTML")

# ================= BROADCAST =================
@bot.message_handler(func=lambda m: m.text == "📢 BROADCAST")
def broadcast_start(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ You are not admin")
        return

    msg = bot.send_message(
        m.chat.id,
        "📝 Send the broadcast message to all users:"
    )
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

        # ================== POST CHANNEL =================
@bot.message_handler(func=lambda m: m.text == "📌 POST CHANNEL")
def post_channel_start(m):

    global CHANNEL_WINDOW_OPEN

    if not is_admin(m.from_user.id):
        return

    CHANNEL_WINDOW_OPEN = True
    POST_CHANNELS.clear()

    msg = bot.send_message(
        m.chat.id,
        "Send channel usernames\nExample:\n@channel1\n@channel2\n\nMax 10 channels.\nSend DONE when finished."
    )

    bot.register_next_step_handler(msg, post_channel_add)

def post_channel_add(m):

    if m.text.lower() == "done":

        bot.send_message(
            m.chat.id,
            f"✅ {len(POST_CHANNELS)} channels added."
        )
        return

    if len(POST_CHANNELS) >= MAX_CHANNELS:

        bot.send_message(
            m.chat.id,
            "⚠️ Maximum 10 channels allowed."
        )
        return

    username = m.text.replace("@","").strip()

    POST_CHANNELS.append(username)

    msg = bot.send_message(
        m.chat.id,
        f"Channel @{username} added\nTotal: {len(POST_CHANNELS)}\nSend another or DONE"
    )

    bot.register_next_step_handler(msg, post_channel_add)

    # ================= CLOSE CHANEL =================
@bot.message_handler(func=lambda m: m.text == "CLOSE CHANNEL POST")
def close_channel_post(m):

    if not is_admin(m.from_user.id):
        return

    MANAGED_CHANNELS.clear()

    bot.send_message(
        m.chat.id,
        "❌ All channels removed.\n\nYou can now add new channels using ADD CHANNEL."
    )

# ================= SEE USERS LIST =================
@bot.message_handler(func=lambda m: m.text == "👥 SEE LIST")
def see_users(m):

    if not is_admin(m.from_user.id):
        return

    total = len(users)
    count = 0

    for uid in users:

        kb = InlineKeyboardMarkup()

        kb.add(
            InlineKeyboardButton(
                "💬 OPEN CHAT",
                url=f"tg://user?id={uid}"
            )
        )

        bot.send_message(
            m.chat.id,
            f"👤 User ID: {uid}",
            reply_markup=kb
        )

        count += 1

        if count >= 20:
            break

    bot.send_message(
        m.chat.id,
        f"📊 Total Users: {total}"
    )

@bot.message_handler(func=lambda m: m.text == "🔒 LOCK BOT")
def lock_bot_start(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ You are not admin")
        return

    msg = bot.send_message(
        m.chat.id,
        "✍️ Send the lock message users should receive.\n\nExample:\nBotka waa la xanibay, fadlan sug."
    )
    bot.register_next_step_handler(msg, lock_bot_process)


def lock_bot_process(m):
    global BOT_LOCKED, LOCK_MESSAGE

    if not is_admin(m.from_user.id):
        return

    text = (m.text or "").strip()

    if not text:
        bot.send_message(m.chat.id, "❌ Lock message cannot be empty")
        return

    LOCK_MESSAGE = text
    BOT_LOCKED = True

    bot.send_message(
        m.chat.id,
        f"🔒 Bot locked successfully.\n\nLock message:\n{text}"
    )

@bot.message_handler(func=lambda m: m.text == "🔓 UNLOCK BOT")
def unlock_bot(m):
    global BOT_LOCKED

    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ You are not admin")
        return

    BOT_LOCKED = False

    bot.send_message(
        m.chat.id,
        "🔓 Bot unlocked successfully."
    )

# ================= IMPORT USERS =================
@bot.message_handler(func=lambda m: m.text == "📥 IMPORT USERS")
def import_users_start(m):

    if not is_admin(m.from_user.id):
        return

    msg = bot.send_message(
        m.chat.id,
        "Send Telegram IDs separated by spaces or new lines.\n\nExample:\n12345\n67890\n112233"
    )

    bot.register_next_step_handler(msg, import_users_process)


def import_users_process(m):

    if not is_admin(m.from_user.id):
        return

    text = m.text.strip()

    ids = text.replace("\n", " ").split()

    added = 0

    for uid in ids:

        uid = uid.strip()

        if not uid.isdigit():
            continue

        if uid not in users:

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

    bot.send_message(
        m.chat.id,
        f"✅ Imported {added} users successfully."
    )

# ================= GET REFERRAL CODE =================

@bot.message_handler(func=lambda m: m.text == "🔗 GET REFERRAL CODE")
def get_ref_code_start(m):

    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ You are not admin")
        return

    msg = bot.send_message(
        m.chat.id,
        "Send user username:\n\nExample:\n@scholes1"
    )

    bot.register_next_step_handler(msg, get_ref_username)


def get_ref_username(m):

    if not is_admin(m.from_user.id):
        return

    username = m.text.replace("@", "").strip()

    msg = bot.send_message(
        m.chat.id,
        f"User: @{username}\n\nNow send referral code number:\nExample:\n1"
    )

    bot.register_next_step_handler(
        msg,
        lambda x: save_custom_ref_code(x, username)
    )


def save_custom_ref_code(m, username):

    if not is_admin(m.from_user.id):
        return

    code = m.text.strip()

    if not code.isdigit():
        bot.send_message(
            m.chat.id,
            "❌ Code must be a number"
        )
        return


    user_id = None

    for uid, data in users.items():

        # Haddii username hore database-ka ugu jiro
        if data.get("username","").lower() == username.lower():
            user_id = uid
            break


    if not user_id:

        bot.send_message(
            m.chat.id,
            "❌ User not found in database"
        )
        return


    users[user_id]["ref"] = code

    save_users()


    bot.send_message(
        m.chat.id,
        f"✅ Referral code created\n\n"
        f"👤 User: @{username}\n"
        f"🔢 Code: {code}\n\n"
        f"🔗 Link:\n"
        f"https://t.me/{bot.get_me().username}?start={code}"
    )


    bot.send_message(
        int(user_id),
        f"🎉 Your new referral link:\n\n"
        f"https://t.me/{bot.get_me().username}?start={code}"
    )

# ================= SEARCH USER =================
@bot.message_handler(func=lambda m: m.text == "🔎 SEARCH USER")
def search_user(m):

    if not is_admin(m.from_user.id):
        return

    msg = bot.send_message(m.chat.id,"Send User Telegram ID")

    bot.register_next_step_handler(msg, search_user_result)


def search_user_result(m):

    if not is_admin(m.from_user.id):
        return

    uid = m.text.strip()

    if uid in users:

        kb = InlineKeyboardMarkup()

        kb.add(
            InlineKeyboardButton(
                "💬 OPEN CHAT",
                url=f"tg://user?id={uid}"
            )
        )

        kb.add(
            InlineKeyboardButton(
                "✉️ MESSAGE USER",
                callback_data=f"msguser|{uid}"
            )
        )

        bot.send_message(
            m.chat.id,
            f"👤 User Found\nID: {uid}",
            reply_markup=kb
        )

    else:

        bot.send_message(m.chat.id,"❌ User not found")

# ================= CHECKING DOWNLOAD =================
@bot.message_handler(func=lambda m: m.text and "http" in m.text)
def handle_links(message):
    if bot_locked_guard(message):
        return

    user_id = message.from_user.id
    link = message.text
    ...

    # ===== FORCE JOIN MULTI CHANNEL =====
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


    # ===== VERIFY SYSTEM =====
    # ===== VERIFY SYSTEM =====
    if VERIFY_ENABLED and not users.get(str(user_id), {}).get("verified", False):

        code = str(random.randint(10000,99999))

        verify_pending[user_id] = {
            "code": code,
            "link": link
        }

        kb = InlineKeyboardMarkup()

        kb.add(
            InlineKeyboardButton("📩 Verify via DM", callback_data="via_telegram")
        )

        kb.add(
            InlineKeyboardButton(
                "🤖 Verify via Bot",
                url=f"https://t.me/Verifyd_bot?start={code}"
            )
        )

        kb.add(
            InlineKeyboardButton("📧 Verify via Gmail", callback_data="verify_email")
        )

        bot.send_message(
            message.chat.id,
            "🔐 Verification Required\n\nChoose verification method:",
            reply_markup=kb
        )

        return


    # ===== START DOWNLOAD =====
    bot.send_message(message.chat.id, "⏳ Downloading...")
    download_media(message.chat.id, link)

# ================= MULTI CHANNEL CONFIRM =================
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

            bot.send_message(user_id,"Send your video link.")

    else:

        bot.answer_callback_query(
            call.id,
            "❌ You must join all channels first!",
            show_alert=True
        )

# ================= CONFIRM JOIN =================
@bot.callback_query_handler(func=lambda call: call.data == "confirm_join")
def confirm_join(call):
    user_id = call.from_user.id

    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)

        if member.status in ["member", "administrator", "creator"]:

            bot.answer_callback_query(call.id, "✅ Join verified")

            # ✅ Tirtir inline keyboard
            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=None
            )

            # Haddii uu hore link u diray, ka soo qaad pending_links
            if user_id in pending_links:
                link = pending_links[user_id]
                del pending_links[user_id]

                # Fariin u dir user
                msg = bot.send_message(user_id, "⏳ Downloading...")

                # Download video
                download_media(user_id, link)

            else:
                bot.send_message(user_id, "✅ Join confirmed. Send your video link.")

        else:
            bot.answer_callback_query(
                call.id,
                "❌ You must join the channel first!",
                show_alert=True
            )

    except Exception as e:
        bot.answer_callback_query(
            call.id,
            "❌ Please join the channel first!",
            show_alert=True
        )

# ================= CLOSE WINDOWS =================
@bot.message_handler(func=lambda m: m.text == "❌ CLOSE WINDOWS")
def close_channel_windows(m):

    global CHANNEL_WINDOW_OPEN

    if not is_admin(m.from_user.id):
        return

    CHANNEL_WINDOW_OPEN = False

    bot.send_message(
        m.chat.id,
        "✅ Channel join system disabled."
    )

# ================= VERIFY ON ===============
@bot.message_handler(func=lambda m: m.text == "✅ VERIFY ON")
def verify_on(m):

    global VERIFY_ENABLED

    if m.from_user.id not in ADMIN_IDS:
        return

    VERIFY_ENABLED = True

    bot.send_message(m.chat.id, "✅ Verify system enabled")

# ================ VERIFY OF ================
@bot.message_handler(func=lambda m: m.text == "❌ VERIFY OFF")
def verify_off(m):

    global VERIFY_ENABLED

    if m.from_user.id not in ADMIN_IDS:
        return

    VERIFY_ENABLED = False

    bot.send_message(m.chat.id, "❌ Verify system disabled")

    # =============== V ===============
@bot.message_handler(func=lambda m: m.text == "CHANNEL POST")
def start_channel_post(m):

    if not is_admin(m.from_user.id):
        return

    msg = bot.send_message(
        m.chat.id,
        "Send the main text for the channel post."
    )

    bot.register_next_step_handler(msg, post_main_text)


def post_main_text(m):

    pending_post[m.from_user.id] = {
        "text": m.text,
        "buttons": []
    }

    msg = bot.send_message(
        m.chat.id,
        "Send button like:\n\nButton Name | Text when clicked\n\nSend DONE when finished."
    )

    bot.register_next_step_handler(msg, add_buttons)

def add_buttons(m):

    uid = m.from_user.id

    if m.text.lower() == "done":

        data = pending_post[uid]

        kb = InlineKeyboardMarkup()

        for i, btn in enumerate(data["buttons"]):

            kb.add(
                InlineKeyboardButton(
                    btn["name"],
                    callback_data=f"postbtn_{i}"
                )
            )

        for ch in MANAGED_CHANNELS:

            msg = bot.send_message(
                ch,
                data["text"],
                reply_markup=kb
            )

            channel_posts[msg.message_id] = data

        pending_post.pop(uid)

        bot.send_message(m.chat.id,"✅ Post sent")

        return

    try:

        name, content = m.text.split("|",1)

        pending_post[uid]["buttons"].append({
            "name": name.strip(),
            "content": content.strip()
        })

        msg = bot.send_message(
            m.chat.id,
            "Button added. Send another or DONE"
        )

        bot.register_next_step_handler(msg, add_buttons)

    except:

        msg = bot.send_message(
            m.chat.id,
            "❌ Format error\nButton Name | Text"
        )

        bot.register_next_step_handler(msg, add_buttons)

        # ================= FG ===============
@bot.callback_query_handler(func=lambda call: call.data.startswith("postbtn_"))
def post_button_click(call):

    index = int(call.data.split("_")[1])

    data = channel_posts.get(call.message.message_id)

    if not data:
        return

    text = data["buttons"][index]["content"]

    kb = InlineKeyboardMarkup()

    for i, btn in enumerate(data["buttons"]):

        kb.add(
            InlineKeyboardButton(
                btn["name"],
                callback_data=f"postbtn_{i}"
            )
        )

    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=kb
    )

# ================= ADD BALANCE =================
@bot.message_handler(func=lambda m: m.text == "➕ ADD BALANCE")
def add_balance_start(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ You are not admin")
        return

    msg = bot.send_message(
        m.chat.id,
        "Send BOT ID or Telegram ID and amount separated by space:\n"
        "Example:\n123456789 10.5"
    )
    bot.register_next_step_handler(msg, add_balance_process)


def add_balance_process(m):
    if not is_admin(m.from_user.id):
        return

    try:
        uid_str, amt_str = m.text.strip().split()
        amt = float(amt_str)

        # Hubi haddii la isticmaalayo Telegram ID ama BOT ID
        uid = uid_str if uid_str in users else find_user_by_botid(uid_str)

        if not uid or amt <= 0:
            bot.send_message(m.chat.id, "❌ Invalid input")
            return

        users[uid]["balance"] += amt
        save_users()

        bot.send_message(m.chat.id, f"✅ Added ${amt:.2f} to user {uid}")
        bot.send_message(int(uid), f"💰 Your balance increased by ${amt:.2f}")

    except:
        bot.send_message(m.chat.id, "❌ Format error.\nUse:\n<BOT ID or Telegram ID> <amount>")

# ================= REMOVE MONEY =================
@bot.message_handler(func=lambda m: m.text == "➖ REMOVE MONEY")
def remove_balance_start(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ You are not admin")
        return

    msg = bot.send_message(
        m.chat.id,
        "Send BOT ID or Telegram ID and amount separated by space:\n"
        "Example:\n123456789 5.0"
    )
    bot.register_next_step_handler(msg, remove_balance_process)


def remove_balance_process(m):
    if not is_admin(m.from_user.id):
        return

    try:
        uid_str, amt_str = m.text.strip().split()
        amt = float(amt_str)

        # Hubi haddii la isticmaalayo Telegram ID ama BOT ID
        uid = uid_str if uid_str in users else find_user_by_botid(uid_str)

        if not uid or amt <= 0:
            bot.send_message(m.chat.id, "❌ Invalid input")
            return

        if users[uid]["balance"] < amt:
            bot.send_message(m.chat.id, "❌ Insufficient balance")
            return

        users[uid]["balance"] -= amt
        save_users()

        bot.send_message(m.chat.id, f"✅ Removed ${amt:.2f} from user {uid}")
        bot.send_message(int(uid), f"💸 ${amt:.2f} removed from your balance")

    except:
        bot.send_message(m.chat.id, "❌ Format error.\nUse:\n<BOT ID or Telegram ID> <amount>")

CAPTION_TEXT = "Downloaded by:\n@Downloadvedioytibot"

# ================= VERIFY CODE CHECK =================

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


# ================= URL EXTRACTOR =================
def extract_url(text):
    urls = re.findall(r'https?://[^\s]+', text)
    return urls[0] if urls else None

# ================= CLEAN SEND VIDEO FUNCTION =================
def send_video_with_music(chat_id, file_path, platform=None):

    vid_id = str(uuid.uuid4())[:8]
    video_files[vid_id] = file_path

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton(
            "🎵 Convert to Music",
            callback_data=f"music_{vid_id}"
        )
    )

    uid = str(chat_id)

    videos_data["total"] += 1
    videos_data["users"][uid] = videos_data["users"].get(uid, 0) + 1

    if platform:
        if "platforms" not in videos_data:
            videos_data["platforms"] = {}

        videos_data["platforms"][platform] = videos_data["platforms"].get(platform, 0) + 1

    save_videos()

    with open(file_path, "rb") as video:
        bot.send_video(
            chat_id,
            video,
            caption=CAPTION_TEXT,
            reply_markup=kb
        )


# ================= MEDIA DOWNLOADER =================
def download_media(chat_id, text):
    try:
        url = extract_url(text)
        if not url:
            bot.send_message(chat_id, "❌ Invalid link")
            return

        # ================= TIKTOK (PHOTO + VIDEO) =================
        if "tiktok.com" in url:
            try:
                api = f"https://tikwm.com/api/?url={url}"
                res = requests.get(api, timeout=30).json()

                if res.get("code") == 0:
                    data = res["data"]

            

                        # ===== TIKTOK PHOTOS =====
                    if data.get("images"):
                        for i, img in enumerate(data["images"], start=1):
                            img_data = requests.get(img, timeout=30).content
                            filename = f"tiktok_{i}.jpg"

                            with open(filename, "wb") as f:
                                f.write(img_data)

                            with open(filename, "rb") as photo:
                                bot.send_photo(
                                    chat_id,
                                    photo,
                                    caption=f"📸 Photo {i}\n{CAPTION_TEXT}"
                                )

                            os.remove(filename)
                        return


                    # ===== TIKTOK VIDEO =====
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

        # ================= SNAPCHAT =================
        # ================= SNAPCHAT =================
        if "snapchat.com" in url or "snap.com" in url:
            try:

                ydl_opts = {
                    "format": "best",
                    "outtmpl": "snapchat_%(id)s.%(ext)s",
                    "quiet": True
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    file = ydl.prepare_filename(info)

                send_video_with_music(chat_id, file, "snapchat")

                if os.path.exists(file):
                    os.remove(file)

                return

            except Exception as e:
                bot.send_message(chat_id, f"❌ Snapchat download error:\n{e}")
                return

 # ================= PINTEREST =================
        if "pin.it" in url:
            try:
                r = requests.head(url, allow_redirects=True, timeout=10)
                url = r.url
            except Exception:
                pass

        if "pinterest.com" in url:
            try:
                ydl_opts = {
                    "format": "bv*+ba/b",
                    "outtmpl": "pinterest_%(id)s.%(ext)s",
                    "quiet": True,
                    "noplaylist": False,
                    "merge_output_format": "mp4"
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)

                    # ===== haddii ay tahay carousel =====
                    if "entries" in info:
                        entries = info["entries"]
                    else:
                        entries = [info]

                    for entry in entries:
                        file = ydl.prepare_filename(entry)

                        # ===== PHOTO =====
                        if file.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                            with open(file, "rb") as photo:
                                bot.send_photo(chat_id, photo, caption=CAPTION_TEXT)

                        # ===== VIDEO =====
                        else:
                            send_video_with_music(chat_id, file, "pinterest")

                        # delete file
                        try:
                            os.remove(file)
                        except Exception:
                            pass

                return

            except Exception as e:
                bot.send_message(chat_id, f"❌ Download error:\n{e}")
                return

        # ================= INSTAGRAM =================
        if "instagram.com" in url:

            try:

                ydl_opts = {
                    "format": "best",
                    "outtmpl": "instagram_%(id)s.%(ext)s",
                    "quiet": True,
                    "merge_output_format": "mp4"
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:

                    info = ydl.extract_info(url, download=True)

                    if "entries" in info:
                        entries = info["entries"]
                    else:
                        entries = [info]

                    for entry in entries:

                        file = ydl.prepare_filename(entry)

                        # PHOTO
                        if file.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):

                            with open(file, "rb") as photo:

                                bot.send_photo(
                                    chat_id,
                                    photo,
                                    caption=CAPTION_TEXT
                                )

                        # VIDEO
                        else:

                            send_video_with_music(
                                chat_id,
                                file,
                                "instagram"
                            )

                        try:
                            os.remove(file)
                        except:
                            pass

                return

            except Exception as e:

                bot.send_message(
                    chat_id,
                    f"❌ Instagram download error:\n{e}"
                )

                return

        # ================= FACEBOOK =================
        if "facebook.com" in url or "fb.watch" in url:
            ydl_opts = {
                "format": "bestvideo+bestaudio/best",
                "outtmpl": "facebook_%(id)s.%(ext)s",
                "merge_output_format": "mp4",
                "quiet": True
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file = ydl.prepare_filename(info)

            send_video_with_music(chat_id, file, "facebook")
            return

        # ================= YOUTUBE =================
        if "youtube.com" in url or "youtu.be" in url:
            ydl_opts = {
                "format": "bestvideo+bestaudio/best",
                "outtmpl": "youtube_%(id)s.%(ext)s",
                "merge_output_format": "mp4",
                "quiet": True
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file = ydl.prepare_filename(info)

            send_video_with_music(chat_id, file, "youtube")
            return

        bot.send_message(chat_id, "❌ Unsupported link")

    except Exception:
        bot.send_message(
            chat_id,
            "❌ Incorrect Tik Tok link.\n\n"
            "To download the video, send the link in the Tiktok, Facebook, Pinterest, YouTube."
        )
        return
        
# ================= MESSAGE USER =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("msguser|"))
def message_user(call):

    if not is_admin(call.from_user.id):
        return

    uid = call.data.split("|")[1]

    msg = bot.send_message(call.message.chat.id,"Send message for user")

    bot.register_next_step_handler(msg, send_user_message, uid)


def send_user_message(m, uid):

    if not is_admin(m.from_user.id):
        return

    try:

        bot.send_message(int(uid), m.text)

        bot.send_message(m.chat.id,"✅ Message sent")

    except:

        bot.send_message(m.chat.id,"❌ Failed to send message")

# ================= CLEAN SEND VIDEO FUNCTION =================
def send_video_with_music(chat_id, file_path, platform=None):

    vid_id = str(uuid.uuid4())[:8]
    video_files[vid_id] = file_path

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton(
            "🎵 Convert to Music",
            callback_data=f"music_{vid_id}"
        )
    )

    uid = str(chat_id)

    videos_data["total"] += 1
    videos_data["users"][uid] = videos_data["users"].get(uid, 0) + 1

    if platform:
        if "platforms" not in videos_data:
            videos_data["platforms"] = {}

        videos_data["platforms"][platform] = videos_data["platforms"].get(platform, 0) + 1

    save_videos()

    with open(file_path, "rb") as video:
        bot.send_video(
            chat_id,
            video,
            caption=CAPTION_TEXT,
            reply_markup=kb
        )


# ================= MEDIA DOWNLOADER =================
def download_media(chat_id, text):
    try:
        url = extract_url(text)

        if not url:
            bot.send_message(chat_id, "❌ Invalid link")
            return


        # ================= TIKTOK =================
        if "tiktok.com" in url:

            try:

                api = f"https://tikwm.com/api/?url={url}"
                res = requests.get(api, timeout=30).json()

                if res.get("code") == 0:

                    data = res["data"]

                    # ===== PHOTOS =====
                    if data.get("images"):

                        for i, img in enumerate(data["images"], start=1):

                            img_data = requests.get(img, timeout=30).content
                            filename = f"tiktok_{i}.jpg"

                            with open(filename, "wb") as f:
                                f.write(img_data)

                            with open(filename, "rb") as photo:
                                bot.send_photo(
                                    chat_id,
                                    photo,
                                    caption=f"📸 Photo {i}\n{CAPTION_TEXT}"
                                )

                            os.remove(filename)

                        return


                    # ===== VIDEO =====
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


        # ================= SNAPCHAT =================
        if "snapchat.com" in url or "snap.com" in url:

            try:

                ydl_opts = {
                    "format": "best",
                    "outtmpl": "snapchat_%(id)s.%(ext)s",
                    "quiet": True
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:

                    info = ydl.extract_info(url, download=True)
                    file = ydl.prepare_filename(info)

                send_video_with_music(chat_id, file, "snapchat")

                return

            except Exception as e:

                bot.send_message(chat_id, f"❌ Snapchat download error:\n{e}")
                return


        # ================= PINTEREST =================
        if "pin.it" in url:

            try:
                r = requests.head(url, allow_redirects=True, timeout=10)
                url = r.url
            except:
                pass


        if "pinterest.com" in url:

            try:

                ydl_opts = {
                    "format": "bv*+ba/b",
                    "outtmpl": "pinterest_%(id)s.%(ext)s",
                    "quiet": True,
                    "merge_output_format": "mp4"
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:

                    info = ydl.extract_info(url, download=True)

                    if "entries" in info:
                        entries = info["entries"]
                    else:
                        entries = [info]

                    for entry in entries:

                        file = ydl.prepare_filename(entry)

                        if file.lower().endswith((".jpg",".jpeg",".png",".webp")):

                            with open(file,"rb") as photo:
                                bot.send_photo(chat_id, photo, caption=CAPTION_TEXT)

                        else:

                            send_video_with_music(chat_id, file, "pinterest")

                return

            except Exception as e:

                bot.send_message(chat_id, f"❌ Download error:\n{e}")
                return

# ================= FACEBOOK =================
        if "facebook.com" in url or "fb.watch" in url:

            try:

                ydl_opts = {
                    "format": "bestvideo+bestaudio/best",
                    "outtmpl": "facebook_%(id)s.%(ext)s",
                    "merge_output_format": "mp4",
                    "quiet": True
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:

                    info = ydl.extract_info(url, download=True)
                    file = ydl.prepare_filename(info)

                send_video_with_music(chat_id, file, "facebook")

                return

            except Exception as e:

                bot.send_message(chat_id, f"❌ Facebook download error:\n{e}")
                return


        # ================= YOUTUBE =================
        if "youtube.com" in url or "youtu.be" in url:

            try:

                ydl_opts = {
                    "format": "bestvideo+bestaudio/best",
                    "outtmpl": "youtube_%(id)s.%(ext)s",
                    "merge_output_format": "mp4",
                    "quiet": True
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:

                    info = ydl.extract_info(url, download=True)
                    file = ydl.prepare_filename(info)

                send_video_with_music(chat_id, file, "youtube")

                return

            except Exception as e:

                bot.send_message(chat_id, f"❌ YouTube download error:\n{e}")
                return


        bot.send_message(chat_id, "❌ Unsupported link")


    except Exception:

        bot.send_message(
            chat_id,
            "❌ Incorrect link.\n\n"
            "Send a valid link from TikTok, Snapchat, Pinterest, Facebook, or YouTube."
        )



# ================= MESSAGE USER =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("msguser|"))
def message_user(call):

    if not is_admin(call.from_user.id):
        return

    uid = call.data.split("|")[1]

    msg = bot.send_message(
        call.message.chat.id,
        "Send message for user"
    )

    bot.register_next_step_handler(msg, send_user_message, uid)



def send_user_message(m, uid):

    if not is_admin(m.from_user.id):
        return

    try:

        bot.send_message(int(uid), m.text)

        bot.send_message(
            m.chat.id,
            "✅ Message sent"
        )

    except:

        bot.send_message(
            m.chat.id,
            "❌ Failed to send message"
        )



# ================= MUSIC CONVERSION =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("music_"))
def convert_music(call):

    vid_id = call.data.split("_")[1]

    if vid_id not in video_files:

        bot.answer_callback_query(
            call.id,
            "File expired"
        )
        return


    file_path = video_files[vid_id]
    audio_path = file_path.rsplit(".",1)[0] + ".mp3"


    try:

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                file_path,
                "-vn",
                "-acodec","mp3",
                "-ab","128k",
                "-ar","44100",
                audio_path
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )


        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton(
                "📢 BOT CHANNEL",
                url="https://t.me/tiktokvediodownload"
            )
        )


        with open(audio_path,"rb") as audio:

            bot.send_audio(
                call.message.chat.id,
                audio,
                title="Converted Music",
                performer="DownloadBot",
                caption=CAPTION_TEXT,
                reply_markup=kb
            )


        if os.path.exists(audio_path):
            os.remove(audio_path)

        if os.path.exists(file_path):
            os.remove(file_path)


        bot.answer_callback_query(
            call.id,
            "🎵 Music converted"
        )


    except Exception as e:

        bot.send_message(
            call.message.chat.id,
            f"❌ Music conversion failed:\n{e}"
        )

# ================= VERIFY BOT =================
@bot2.message_handler(commands=['start'])
def verify_start(m):

    args = m.text.split()

    if len(args) > 1:
        code = args[1]

        bot2.send_message(
            m.chat.id,
            f"🔑 Your verification code:\n\n{code}\n\nCopy this code and send it to the downloader bot."
        )

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

def run_support_bot():
    while True:
        try:
            subprocess.call(
                ["python", "support_bot.py"]
            )

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
