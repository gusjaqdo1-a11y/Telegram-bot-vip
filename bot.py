import telebot
import requests
from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
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


# ================= JSON FUNCTIONS =================
def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# ================= CONFIG & ENV VARIABLES =================
TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
BOT2_TOKEN = os.getenv("BOT2_TOKEN", "YOUR_BOT2_TOKEN_HERE")

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")

PHONE = os.getenv("PHONE", "")

GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_PASS = os.getenv("GMAIL_PASS", "")

STARS_PROVIDER_TOKEN = ""

tg_client = TelegramClient(
    "session",
    API_ID,
    API_HASH
)

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
LOCK_MESSAGE = "🔒 Bot-ku si ku-meel-gaar ah ayuu u xidhan yahay."

SETTINGS_CONTROL = True  
SETTINGS_LOCKED_MSG = "⚠️ Qeybta Settings-ka si ku-meel-gaar ah ayaa loo xidhay!"

pending_post = {}
channel_posts = {}

VERIFY_ENABLED = False
verify_pending = {}
verify_method = {}
video_store = {}
video_files = {}

ADS_ENABLED = False
ADS_TEXT = ""         
ADS_BTN_TEXT = ""     
ADS_URL = "" 

VIP_ADS_ENABLED = False
VIP_ADS_TEXT = ""
VIP_ADS_BTN_TEXT = ""
VIP_ADS_URL = ""

CAPTION_TEXT = "Downloaded by:\n@Downloadvedioytibot"

# ================= DATABASE FILES =================
USERS_FILE = "users.json"
WITHDRAWS_FILE = "withdraws.json"
VIDEOS_FILE = "videos.json"
CONFIG_FILE = "config.json"

config_data = load_json(CONFIG_FILE, {
    "vip_price": 100, 
    "bot_locked": False, 
    "lock_message": "🔒 Bot-ku waa xidhan yahay.",
    "settings_control": True,
    "settings_locked_msg": "⚠️ Qeybta Settings-ka si ku-meel-gaar ah ayaa loo xidhay!"
})

VIP_PRICE = config_data.get("vip_price", 100)
BOT_LOCKED = config_data.get("bot_locked", False)
LOCK_MESSAGE = config_data.get("lock_message", "🔒 Bot-ku waa xidhan yahay.")
SETTINGS_CONTROL = config_data.get("settings_control", True)
SETTINGS_LOCKED_MSG = config_data.get("settings_locked_msg", "⚠️ Qeybta Settings-ka si ku-meel-gaar ah ayaa loo xidhay!")

users = load_json(USERS_FILE, {})
withdraws = load_json(WITHDRAWS_FILE, [])

def save_users():
    save_json(USERS_FILE, users)

def save_withdraws():
    save_json(WITHDRAWS_FILE, withdraws)

def save_config():
    save_json(CONFIG_FILE, {
        "vip_price": VIP_PRICE,
        "bot_locked": BOT_LOCKED,
        "lock_message": LOCK_MESSAGE,
        "settings_control": SETTINGS_CONTROL,
        "settings_locked_msg": SETTINGS_LOCKED_MSG
    })

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

def save_videos():
    save_json(VIDEOS_FILE, videos_data)

DEFAULT_USER_SETTINGS = {
    "quality": "Best",
    "audio_format": "MP3",
    "filename": "Original",
    "thumbnail": True,
    "caption": True,
    "source_link": True,
    "language": "Somali",
    "auto_zip": False,
    "notifications": True,
    "vip_auto_mp3": False,
    "vip_custom_thumb": "",
    "vip_custom_caption": "",
    "vip_auto_save": False
}

# ================= HELPER FUNCTIONS =================
def random_ref():
    return str(random.randint(1000000000, 9999999999))

def random_botid():
    return str(random.randint(10000000000, 99999999999))

def now_month():
    return datetime.now().month

def is_admin(uid):
    return int(uid) in ADMIN_IDS

def is_vip(uid):
    uid_str = str(uid)
    return users.get(uid_str, {}).get("is_vip", False)

def get_user_settings(uid):
    uid_str = str(uid)
    if uid_str not in users:
        return DEFAULT_USER_SETTINGS.copy()
    if "settings" not in users[uid_str]:
        users[uid_str]["settings"] = DEFAULT_USER_SETTINGS.copy()
        save_users()
    return users[uid_str]["settings"]

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

def get_user_badge(uid):
    if is_vip(uid):
        return "👑 VIP User"
    return "👤 Free User"

def get_user_caption_prefix(m_user):
    username = f"@{m_user.username}" if m_user.username else m_user.first_name
    if is_vip(m_user.id):
        return f"👑 VIP • {username}\n"
    return f"👤 {username}\n"

# ================= MENUS =================
def user_menu(uid):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💰 BALANCE", "💸 WITHDRAWAL")
    kb.add("👥 REFERRAL", "🆔 GET ID")
    kb.add("⚙️ SETTINGS", "🚀PREMIUM")
    kb.add("👑PREMIUM USERS", "☎️ CUSTOMER")
    kb.add("🤖CUSTOMER AI")
    if is_admin(uid):
        kb.add("👑 ADMIN PANEL")
    return kb

def admin_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📊 STATS", "📢 BROADCAST")
    kb.add("➕ ADD BALANCE", "➖ REMOVE MONEY")
    kb.add("🚫 BAN USER MANUAL", "💳 WITHDRAWAL CHECK")
    kb.add("💰 UNBLOCK MONEY", "🔍 RAADI")
    kb.add("🔥 UN BAN-USER", "📌 POST CHANNEL")
    kb.add("👑 ADD VIP", "❌ REMOVE VIP")
    kb.add("📢 ADD ADS VIP", "🗑 REMOVE ADS VIP")
    kb.add("👥 SEE LIST", "🔎 SEARCH USER")
    kb.add("📢 ADD ADS", "🗑 DELETE ADS")
    kb.add("✅ VERIFY ON", "❌ VERIFY OFF")
    kb.add("CHANNEL POST", "📡 ADD CHANNEL")
    kb.add("🔒 LOCK BOT", "🔓 UNLOCK BOT")  
    kb.add("🛠 SETTINGS CONTROL", "🔓 SETTINGS OPEN")
    kb.add("❌ CLOSE WINDOWS", "CLOSE CHANNEL POST")
    kb.add("📥 IMPORT USERS")
    kb.add("⚙️ SET VIP PRICE")
    kb.add("🔗 GET REFERRAL CODE")
    kb.add("🔙 BACK MAIN MENU")
    return kb

def back_to_main_menu(m):
    bot.send_message(
        m.chat.id,
        "🔙 Returning to main menu",
        reply_markup=user_menu(m.from_user.id)
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
            "is_vip": False,
            "month": now_month(),
            "settings": DEFAULT_USER_SETTINGS.copy()
        }
        if ref:
            ref_user = next((u for u, d in users.items() if d.get("ref") == ref), None)
            if ref_user:
                users[ref_user]["balance"] += 0.2
                users[ref_user]["invited"] += 1
                try:
                    bot.send_message(int(ref_user), "🎉 You earned $0.2 from referral!")
                except Exception:
                    pass

        save_users()
    else:
        users[str(uid)]["username"] = message.from_user.username or ""
        if "is_vip" not in users[str(uid)]:
            users[str(uid)]["is_vip"] = False
        if "settings" not in users[str(uid)]:
            users[str(uid)]["settings"] = DEFAULT_USER_SETTINGS.copy()
        save_users()

    check_membership(uid)

@bot.message_handler(commands=['view'])
def view_cmd(message):
    badge = get_user_badge(message.from_user.id)
    bot.send_message(
        message.chat.id,
        f"🤖 BOT INFO\n"
        f"Status: {badge}\n\n"
        "📌 Name: Video Downloader Bot\n"
        "⚡ Supported Platforms:\n"
        "• TikTok\n"
        "• YouTube\n"
        "• Facebook\n"
        "• Instagram\n"
        "• Pinterest\n"
        "• Snapchat\n"
        "• Direct MP3 Audio Converter"
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

# ================= USER SETTINGS SYSTEM =================
def build_settings_keyboard(uid):
    st = get_user_settings(uid)
    vip = is_vip(uid)
    
    kb = InlineKeyboardMarkup(row_width=2)
    btn_q = InlineKeyboardButton(f"🎬 Quality: {st['quality']}", callback_data="st_toggle_quality")
    btn_a = InlineKeyboardButton(f"🎵 Audio: {st['audio_format']}", callback_data="st_toggle_audio")
    btn_thumb = InlineKeyboardButton(f"🖼️ Thumb: {'ON' if st['thumbnail'] else 'OFF'}", callback_data="st_toggle_thumb")
    btn_cap = InlineKeyboardButton(f"📝 Caption: {'ON' if st['caption'] else 'OFF'}", callback_data="st_toggle_cap")
    btn_link = InlineKeyboardButton(f"🔗 Link: {'ON' if st['source_link'] else 'OFF'}", callback_data="st_toggle_link")
    btn_lang = InlineKeyboardButton(f"🌐 Lang: {st['language']}", callback_data="st_toggle_lang")
    btn_zip = InlineKeyboardButton(f"📦 Auto ZIP: {'ON' if st['auto_zip'] else 'OFF'}", callback_data="st_toggle_zip")
    btn_notif = InlineKeyboardButton(f"🔔 Notif: {'ON' if st['notifications'] else 'OFF'}", callback_data="st_toggle_notif")
    
    kb.add(btn_q, btn_a)
    kb.add(btn_thumb, btn_cap)
    kb.add(btn_link, btn_lang)
    kb.add(btn_zip, btn_notif)

    if vip:
        btn_vip_mp3 = InlineKeyboardButton(f"⚡ Auto MP3: {'ON' if st.get('vip_auto_mp3') else 'OFF'}", callback_data="st_toggle_vip_mp3")
        btn_vip_save = InlineKeyboardButton(f"💾 Auto Vault: {'ON' if st.get('vip_auto_save') else 'OFF'}", callback_data="st_toggle_vip_save")
        kb.add(btn_vip_mp3, btn_vip_save)

    kb.add(InlineKeyboardButton("🔄 Reset Settings", callback_data="st_reset"))
    kb.add(InlineKeyboardButton("❌ Close", callback_data="st_close"))
    return kb

@bot.message_handler(func=lambda m: m.text == "⚙️ SETTINGS")
def user_settings_handler(m):
    if bot_locked_guard(m) or banned_guard(m):
        return

    if not SETTINGS_CONTROL and not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, SETTINGS_LOCKED_MSG)
        return

    st = get_user_settings(m.from_user.id)
    badge = get_user_badge(m.from_user.id)

    msg_text = (
        f"⚙️ <b>USER SETTINGS PANEL</b>\n"
        f"Status: <b>{badge}</b>\n\n"
        f"🎬 Default Quality: <b>{st['quality']}</b>\n"
        f"🎵 Audio Format: <b>{st['audio_format']}</b>\n"
        f"🖼️ Thumbnail: <b>{'ON' if st['thumbnail'] else 'OFF'}</b>\n"
        f"📝 Caption: <b>{'ON' if st['caption'] else 'OFF'}</b>\n"
        f"🔗 Source Link: <b>{'ON' if st['source_link'] else 'OFF'}</b>\n"
        f"🌐 Language: <b>{st['language']}</b>\n"
        f"📦 Auto ZIP: <b>{'ON' if st['auto_zip'] else 'OFF'}</b>\n"
        f"🔔 Download Notif: <b>{'ON' if st['notifications'] else 'OFF'}</b>\n"
    )

    if is_vip(m.from_user.id):
        msg_text += (
            f"\n👑 <b>VIP EXTRAS:</b>\n"
            f"⚡ Auto MP3 Convert: <b>{'ON' if st.get('vip_auto_mp3') else 'OFF'}</b>\n"
            f"💾 Auto Save Vault: <b>{'ON' if st.get('vip_auto_save') else 'OFF'}</b>\n"
        )

    msg_text += "\n<i>Taabo button-ka hoose si aad wax uga beddesho:</i>"
    bot.send_message(m.chat.id, msg_text, reply_markup=build_settings_keyboard(m.from_user.id), parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("st_"))
def settings_callback(call):
    uid = call.from_user.id
    uid_str = str(uid)
    
    if not SETTINGS_CONTROL and not is_admin(uid):
        bot.answer_callback_query(call.id, SETTINGS_LOCKED_MSG, show_alert=True)
        return

    st = get_user_settings(uid)
    action = call.data

    if action == "st_close":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        return
    elif action == "st_reset":
        users[uid_str]["settings"] = DEFAULT_USER_SETTINGS.copy()
        save_users()
        bot.answer_callback_query(call.id, "🔄 Settings-kii default-ka ahaa waa lagu celiyay!")
    elif action == "st_toggle_quality":
        q_list = ["Best", "1080p", "720p", "480p"]
        curr_idx = q_list.index(st["quality"]) if st["quality"] in q_list else 0
        st["quality"] = q_list[(curr_idx + 1) % len(q_list)]
    elif action == "st_toggle_audio":
        st["audio_format"] = "M4A" if st["audio_format"] == "MP3" else "MP3"
    elif action == "st_toggle_thumb":
        st["thumbnail"] = not st["thumbnail"]
    elif action == "st_toggle_cap":
        st["caption"] = not st["caption"]
    elif action == "st_toggle_link":
        st["source_link"] = not st["source_link"]
    elif action == "st_toggle_lang":
        langs = ["Somali", "English", "Arabic"]
        curr_idx = langs.index(st["language"]) if st["language"] in langs else 0
        st["language"] = langs[(curr_idx + 1) % len(langs)]
    elif action == "st_toggle_zip":
        st["auto_zip"] = not st["auto_zip"]
    elif action == "st_toggle_notif":
        st["notifications"] = not st["notifications"]
    elif action == "st_toggle_vip_mp3" and is_vip(uid):
        st["vip_auto_mp3"] = not st.get("vip_auto_mp3", False)
    elif action == "st_toggle_vip_save" and is_vip(uid):
        st["vip_auto_save"] = not st.get("vip_auto_save", False)

    users[uid_str]["settings"] = st
    save_users()

    msg_text = (
        f"⚙️ <b>USER SETTINGS PANEL</b>\n"
        f"Status: <b>{get_user_badge(uid)}</b>\n\n"
        f"🎬 Default Quality: <b>{st['quality']}</b>\n"
        f"🎵 Audio Format: <b>{st['audio_format']}</b>\n"
        f"🖼️ Thumbnail: <b>{'ON' if st['thumbnail'] else 'OFF'}</b>\n"
        f"📝 Caption: <b>{'ON' if st['caption'] else 'OFF'}</b>\n"
        f"🔗 Source Link: <b>{'ON' if st['source_link'] else 'OFF'}</b>\n"
        f"🌐 Language: <b>{st['language']}</b>\n"
        f"📦 Auto ZIP: <b>{'ON' if st['auto_zip'] else 'OFF'}</b>\n"
        f"🔔 Download Notif: <b>{'ON' if st['notifications'] else 'OFF'}</b>\n"
    )
    if is_vip(uid):
        msg_text += (
            f"\n👑 <b>VIP EXTRAS:</b>\n"
            f"⚡ Auto MP3 Convert: <b>{'ON' if st.get('vip_auto_mp3') else 'OFF'}</b>\n"
            f"💾 Auto Save Vault: <b>{'ON' if st.get('vip_auto_save') else 'OFF'}</b>\n"
        )
    msg_text += "\n<i>Taabo button-ka hoose si aad wax uga beddesho:</i>"

    try:
        bot.edit_message_text(
            msg_text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=build_settings_keyboard(uid),
            parse_mode="HTML"
        )
    except Exception:
        pass

# ================= CHECK MEMBERSHIP =================
def check_membership(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["member", "administrator", "creator"]:
            badge = get_user_badge(user_id)
            bot.send_message(
                user_id,
                f"🎬 Welcome to Universal Video & Music Downloader Bot!\n"
                f"Badge: <b>{badge}</b>\n\n"
                "Somalida: Dhammaan Barta Bulshada Linkiyadooda Halkan ku soo dir!\n"
                "Supports: TikTok, YouTube, Facebook, Instagram, Pinterest, Snapchat.\n\n"
                "📥 Direct Link Send Kareey!",
                reply_markup=user_menu(user_id)
            )
        else:
            send_join_message(user_id)
    except Exception:
        send_join_message(user_id)

def send_join_message(user_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ JOIN CHANNEL", url="https://t.me/tiktokvediodownload"))
    kb.add(InlineKeyboardButton("✅ CONFIRM", callback_data="confirm_join"))
    bot.send_message(user_id, "⚠️ You must join our channel to use this bot.", reply_markup=kb)

def send_multi_join(user_id):
    kb = InlineKeyboardMarkup(row_width=3)
    buttons = [InlineKeyboardButton("➕️ JOIN", url=f"https://t.me/{ch}") for ch in POST_CHANNELS]
    kb.add(*buttons)
    kb.add(InlineKeyboardButton("✅ CONFIRM", callback_data="multi_checkjoin"))
    bot.send_message(user_id, "⚠️ Join all channels to continue.", reply_markup=kb)

# ================= VIP SYSTEM =================
@bot.message_handler(func=lambda m: m.text == "🚀PREMIUM")
def unlock_vip_cmd(m):
    if bot_locked_guard(m) or banned_guard(m):
        return

    uid = str(m.from_user.id)
    if is_vip(uid):
        bot.send_message(m.chat.id, "👑 You are already a VIP User!")
        return

    text = (
        "👑 <b>VIP PREMIUM ACCESS</b>\n\n"
        "Unlock VIP Downloader\n\n"
        "🚀 Ultra Fast Download\n"
        "🎬 1080p Full HD Video\n"
        "🎵 Auto Convert MP3\n"
        "⭐ VIP Badge & No Normal Ads\n\n"
        f"Price: {VIP_PRICE} ⭐ Stars"
    )
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(f"⭐ Pay {VIP_PRICE} Stars", callback_data="buy_vip_stars"))
    bot.send_message(m.chat.id, text, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "buy_vip_stars")
def buy_vip_stars_cb(call):
    bot.answer_callback_query(call.id)
    prices = [LabeledPrice(label="VIP Access", amount=VIP_PRICE)]
    bot.send_invoice(
        call.message.chat.id,
        title="👑PREMIUM VIP ACCESS",
        description="Unlock VIP Downloader Features permanently!",
        invoice_payload="vip_subscription_payload",
        provider_token=STARS_PROVIDER_TOKEN,
        currency="XTR",
        prices=prices,
        start_parameter="vip-access"
    )

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout_pre(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    uid = str(message.from_user.id)
    if message.successful_payment.invoice_payload == "vip_subscription_payload":
        users[uid]["is_vip"] = True
        save_users()
        bot.send_message(
            message.chat.id,
            "🎉 <b>Congratulations!</b>\n\nYou are now a 👑 <b>VIP User</b>!",
            reply_markup=user_menu(message.from_user.id)
        )

@bot.message_handler(func=lambda m: m.text == "👑PREMIUM USERS")
def vip_users_list(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    vip_list = []
    for u, data in users.items():
        if data.get("is_vip"):
            uname = f"@{data.get('username')}" if data.get('username') else f"ID: {u}"
            vip_list.append(f"👑 <a href='tg://user?id={u}'>{uname}</a>")

    count = len(vip_list)
    msg = f"👑 <b>VIP USERS COUNT:</b> {count}\n\n"
    msg += "\n".join(vip_list[:50]) if vip_list else "No VIP users yet."
    bot.send_message(m.chat.id, msg, parse_mode="HTML")

# ================= ADMIN VIP MANAGEMENT =================
@bot.message_handler(func=lambda m: m.text == "👑 ADD VIP")
def add_vip_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Send Telegram ID or BOT ID to make VIP:")
    bot.register_next_step_handler(msg, add_vip_proc)

def add_vip_proc(m):
    if not is_admin(m.from_user.id): return
    target = m.text.strip()
    uid = target if target in users else find_user_by_botid(target)
    if not uid:
        bot.send_message(m.chat.id, "❌ User not found.")
        return
    users[uid]["is_vip"] = True
    save_users()
    bot.send_message(m.chat.id, f"✅ User {uid} is now VIP!")

@bot.message_handler(func=lambda m: m.text == "❌ REMOVE VIP")
def remove_vip_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Send Telegram ID or BOT ID to REMOVE VIP:")
    bot.register_next_step_handler(msg, remove_vip_proc)

def remove_vip_proc(m):
    if not is_admin(m.from_user.id): return
    target = m.text.strip()
    uid = target if target in users else find_user_by_botid(target)
    if not uid:
        bot.send_message(m.chat.id, "❌ User not found.")
        return
    users[uid]["is_vip"] = False
    save_users()
    bot.send_message(m.chat.id, f"❌ VIP status removed for user {uid}.")

# ================= ADMIN LOCK BOT & SETTINGS CONTROL =================
@bot.message_handler(func=lambda m: m.text == "🔒 LOCK BOT")
def lock_bot_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "✍️ Send lock message (e.g., 🔒 Bot-ku waa xidhan yahay):")
    bot.register_next_step_handler(msg, lock_bot_process)

def lock_bot_process(m):
    global BOT_LOCKED, LOCK_MESSAGE
    if not is_admin(m.from_user.id): return
    text = (m.text or "").strip()
    if not text:
        bot.send_message(m.chat.id, "❌ Cannot be empty")
        return
    LOCK_MESSAGE = text
    BOT_LOCKED = True
    save_config()
    bot.send_message(m.chat.id, f"🔒 Bot-ka waa la lock gareeyay.\nFariinta:\n{text}")

@bot.message_handler(func=lambda m: m.text == "🔓 UNLOCK BOT")
def unlock_bot(m):
    global BOT_LOCKED
    if not is_admin(m.from_user.id): return
    BOT_LOCKED = False
    save_config()
    bot.send_message(m.chat.id, "🔓 Bot-ka waa la furay (Unlocked).")

@bot.message_handler(func=lambda m: m.text == "🛠 SETTINGS CONTROL")
def settings_control_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "✍️ Geli qoraalka loo tusayo user-ka marka Settings-ka loo xidho:")
    bot.register_next_step_handler(msg, settings_control_proc)

def settings_control_proc(m):
    global SETTINGS_CONTROL, SETTINGS_LOCKED_MSG
    if not is_admin(m.from_user.id): return
    text = (m.text or "").strip()
    if not text:
        bot.send_message(m.chat.id, "❌ Qoraalku ma noqon karo eero.")
        return
    SETTINGS_CONTROL = False
    SETTINGS_LOCKED_MSG = text
    save_config()
    bot.send_message(m.chat.id, f"🚫 Settings-ka waa loo xidhay users-ka.\nQoraalka:: {text}")

@bot.message_handler(func=lambda m: m.text == "🔓 SETTINGS OPEN")
def settings_open(m):
    global SETTINGS_CONTROL
    if not is_admin(m.from_user.id): return
    SETTINGS_CONTROL = True
    save_config()
    bot.send_message(m.chat.id, "✅ Settings-ka waa loo furay dhammaan users-ka.")

# ================= ADMIN VIP ADS MANAGEMENT =================
@bot.message_handler(func=lambda m: m.text == "📢 ADD ADS VIP")
def add_ads_vip_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "✍️ <b>Geli VIP Ads-ka:</b>\n\n`Button Name | Link | Text`", parse_mode="Markdown")
    bot.register_next_step_handler(msg, add_ads_vip_proc)

def add_ads_vip_proc(m):
    global VIP_ADS_ENABLED, VIP_ADS_BTN_TEXT, VIP_ADS_URL, VIP_ADS_TEXT
    if not is_admin(m.from_user.id): return
    parts = [p.strip() for p in (m.text or "").split("|")]
    if len(parts) < 2:
        bot.send_message(m.chat.id, "❌ Format error.")
        return
    VIP_ADS_BTN_TEXT = parts[0]
    VIP_ADS_URL = parts[1]
    VIP_ADS_TEXT = parts[2] if len(parts) > 2 else "🌟 Exclusive VIP Offer"
    VIP_ADS_ENABLED = True
    bot.send_message(m.chat.id, "✅ VIP Ads enabled!")

@bot.message_handler(func=lambda m: m.text == "🗑 REMOVE ADS VIP")
def remove_ads_vip(m):
    global VIP_ADS_ENABLED
    if not is_admin(m.from_user.id): return
    VIP_ADS_ENABLED = False
    bot.send_message(m.chat.id, "🗑 VIP Ads disabled.")

# ================= VERIFY BOT SECOND BOTS =================
@bot2.message_handler(commands=['start'])
def verify_start(message):
    args = message.text.split()
    if len(args) > 1:
        code = args[1]
        bot2.send_message(message.chat.id, f"🔑 <b>Your Verification Code</b>\n\n<code>{code}</code>", parse_mode="HTML")
    else:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("GET", url="https://t.me/Downloadvedioytibot"))
        bot2.send_message(message.chat.id, "❌ <b>Don't Have Code?</b>", reply_markup=kb, parse_mode="HTML")

# ================= EMAIL / DM VERIFICATION =================
def send_gmail_code(email, code):
    body = f"Your verification code is:\n\n{code}"
    msg = MIMEText(body)
    msg["Subject"] = "Telegram Bot Verification Code"
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
    code = str(random.randint(10000, 99999))
    verify_pending[uid] = {"code": code}
    if send_gmail_code(email, code):
        bot.send_message(message.chat.id, "📩 Code sent to your Gmail.")
    else:
        bot.send_message(message.chat.id, "❌ Failed to send email.")

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
        bot.send_message(call.message.chat.id, "✅ Code sent to DM.")
    else:
        bot.send_message(call.message.chat.id, "⚠️ Telegram blocked DM. Start conversation first.")

@bot.callback_query_handler(func=lambda call: call.data == "verify_email")
def verify_email(call):
    msg = bot.send_message(call.message.chat.id, "📧 Send your Gmail address:")
    bot.register_next_step_handler(msg, process_email)

# ================= CONFIRM JOIN CALLBACKS =================
@bot.callback_query_handler(func=lambda call: call.data == "confirm_join")
def confirm_join(call):
    user_id = call.from_user.id
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["member", "administrator", "creator"]:
            bot.answer_callback_query(call.id, "✅ Join verified")
            try: bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception: pass

            if user_id in pending_links:
                link = pending_links[user_id]
                del pending_links[user_id]
                bot.send_message(user_id, "⏳ Downloading...")
                download_media(user_id, link, call.from_user)
            else:
                bot.send_message(user_id, "✅ Join confirmed! Send your link.")
        else:
            bot.answer_callback_query(call.id, "❌ You must join the channel first!", show_alert=True)
    except Exception:
        bot.answer_callback_query(call.id, "❌ Please join the channel first!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "multi_checkjoin")
def multi_checkjoin(call):
    user_id = call.from_user.id
    joined_all = True
    for ch in POST_CHANNELS:
        try:
            member = bot.get_chat_member(f"@{ch}", user_id)
            if member.status not in ["member", "administrator", "creator"]:
                joined_all = False; break
        except Exception:
            joined_all = False; break

    if joined_all:
        bot.answer_callback_query(call.id, "✅ Join verified")
        if user_id in pending_links:
            link = pending_links[user_id]
            del pending_links[user_id]
            bot.send_message(user_id, "⬇️ Processing your video...")
            download_media(user_id, link, call.from_user)
        else:
            bot.send_message(user_id, "Send your video link.")
    else:
        bot.answer_callback_query(call.id, "❌ You must join all channels first!", show_alert=True)

# ================= ADMIN PANEL HANDLERS =================
@bot.message_handler(func=lambda m: m.text == "👑 ADMIN PANEL")
def open_admin_panel(m):
    if not is_admin(m.from_user.id): return
    bot.send_message(m.chat.id, "👑 Admin Panel", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == "💰 BALANCE")
def balance_handler(m):
    if bot_locked_guard(m) or banned_guard(m): return
    uid = str(m.from_user.id)
    bal = users[uid].get("balance", 0.0)
    blocked = users[uid].get("blocked", 0.0)
    badge = get_user_badge(m.from_user.id)
    bot.send_message(m.chat.id, f"Badge: <b>{badge}</b>\n💰 Available Balance: ${bal:.2f}\n⏳ Blocked Amount: ${blocked:.2f}")

@bot.message_handler(func=lambda m: m.text == "🆔 GET ID")
def get_id_handler(m):
    if bot_locked_guard(m) or banned_guard(m): return
    uid = str(m.from_user.id)
    badge = get_user_badge(m.from_user.id)
    bot.send_message(m.chat.id, f"Status: <b>{badge}</b>\n🆔 BOT ID: <code>{users[uid]['bot_id']}</code>\n👤 Telegram ID: <code>{uid}</code>")

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

# ================= WITHDRAWAL SYSTEM =================
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
    try: amt = float(text)
    except Exception:
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("🔙 CANCEL")
        msg = bot.send_message(m.chat.id, "❌ Invalid number. Enter again:", reply_markup=kb)
        bot.register_next_step_handler(msg, withdraw_amount_step)
        return

    if amt < 1 or amt > users[uid]["balance"]:
        bot.send_message(m.chat.id, "❌ Invalid or insufficient amount.", reply_markup=user_menu(m.from_user.id))
        return

    wid = random.randint(10000, 99999)
    users[uid]["balance"] -= amt
    users[uid]["blocked"] += amt

    withdrawal = {
        "id": wid, "user": uid, "amount": amt, "blocked": amt,
        "address": users[uid].get("temp_addr", "N/A"),
        "status": "pending", "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    withdraws.append(withdrawal)
    save_users(); save_withdraws()

    bot.send_message(int(uid), f"✅ Withdrawal Request Sent\n🧾 Request ID: {wid}\n💵 Amount: ${amt:.2f}")

    admin_text = f"💳 NEW WITHDRAWAL\n\n👤 User: {uid}\n💵 Amount: ${amt:.2f}\n🧾 Request ID: {wid}"
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✅ CONFIRM", callback_data=f"confirm_{wid}"),
        InlineKeyboardButton("❌ REJECT", callback_data=f"reject_{wid}"),
        InlineKeyboardButton("🚫 BAN USER", callback_data=f"ban_{uid}"),
        InlineKeyboardButton("💰 BAN MONEY", callback_data=f"block_{wid}")
    )
    for admin in ADMIN_IDS:
        try: bot.send_message(admin, admin_text, reply_markup=markup)
        except Exception: pass

@bot.callback_query_handler(func=lambda call: call.data.startswith(("confirm_", "reject_", "ban_", "block_")))
def admin_callbacks(call):
    if not is_admin(call.from_user.id): return
    data = call.data
    if data.startswith("confirm_"):
        wid = int(data.split("_")[1])
        w = next((x for x in withdraws if x["id"] == wid), None)
        if not w or w["status"] != "pending": return
        w["status"] = "paid"
        users[w["user"]]["blocked"] -= w["blocked"]
        save_users(); save_withdraws()
        bot.answer_callback_query(call.id, "✅ Confirmed")
        bot.send_message(int(w["user"]), f"✅ Withdrawal #{wid} approved!")

    elif data.startswith("reject_"):
        wid = int(data.split("_")[1])
        w = next((x for x in withdraws if x["id"] == wid), None)
        if not w or w["status"] != "pending": return
        w["status"] = "rejected"
        users[w["user"]]["balance"] += w["blocked"]
        users[w["user"]]["blocked"] -= w["blocked"]
        save_users(); save_withdraws()
        bot.answer_callback_query(call.id, "❌ Rejected")
        bot.send_message(int(w["user"]), f"❌ Withdrawal #{wid} rejected")

    elif data.startswith("ban_"):
        uid = data.split("_")[1]
        if uid in users:
            users[uid]["banned"] = True
            save_users()
            bot.answer_callback_query(call.id, "🚫 User banned")

    elif data.startswith("block_"):
        wid = int(data.split("_")[1])
        w = next((x for x in withdraws if x["id"] == wid), None)
        if not w or w["status"] != "pending": return
        uid = w["user"]; amt = w["blocked"]
        w["status"] = "blocked"
        code = str(random.randint(1000, 9999))
        w["block_code"] = code
        users[uid]["blocked"] -= amt
        save_users(); save_withdraws()
        bot.answer_callback_query(call.id, "💰 Money Blocked")

# ================= UNBLOCK / UNBAN / STATS =================
@bot.message_handler(func=lambda m: m.text == "💰 UNBLOCK MONEY")
def unblock_money_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "🔢 Send 4-digit Block Code:")
    bot.register_next_step_handler(msg, unblock_money_process)

def unblock_money_process(m):
    if not is_admin(m.from_user.id): return
    code = (m.text or "").strip()
    w = next((x for x in withdraws if x.get("block_code") == code), None)
    if not w:
        bot.send_message(m.chat.id, "❌ Invalid Block Code")
        return
    uid = w["user"]; amt = w["blocked"]
    users[uid]["balance"] += amt
    w["status"] = "unblocked"
    save_users(); save_withdraws()
    bot.send_message(m.chat.id, f"✅ Money unblocked for user {uid}")

@bot.message_handler(func=lambda m: m.text == "🔥 UN BAN-USER")
def unban_user_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Send Telegram ID to UNBAN:")
    bot.register_next_step_handler(msg, unban_user_process)

def unban_user_process(m):
    if not is_admin(m.from_user.id): return
    uid = (m.text or "").strip()
    if uid in users:
        users[uid]["banned"] = False
        save_users()
        bot.send_message(m.chat.id, f"✅ User {uid} unbanned")

@bot.message_handler(func=lambda m: m.text == "💳 WITHDRAWAL CHECK")
def withdrawal_check_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Enter Request ID:")
    bot.register_next_step_handler(msg, withdrawal_check_process)

def withdrawal_check_process(m):
    if not is_admin(m.from_user.id): return
    try: wid = int(m.text.strip())
    except Exception: return
    w = next((x for x in withdraws if x["id"] == wid), None)
    if w:
        bot.send_message(m.chat.id, f"💳 Request ID: {w['id']}\nStatus: {w['status'].upper()}\nAmount: ${w['amount']}")

@bot.message_handler(func=lambda m: m.text == "📊 STATS")
def stats_handler(m):
    if not is_admin(m.from_user.id): return
    total_users = len(users)
    total_balance = sum(u.get("balance", 0.0) for u in users.values())
    vip_count = len([u for u in users.values() if u.get("is_vip")])
    bot.send_message(m.chat.id, f"📊 BOT STATS\nUsers: {total_users}\nVIP: {vip_count}\nBalance: ${total_balance:.2f}")

@bot.message_handler(func=lambda m: m.text == "🚫 BAN USER MANUAL")
def manual_ban_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Send ID to BAN:")
    bot.register_next_step_handler(msg, manual_ban_process)

def manual_ban_process(m):
    if not is_admin(m.from_user.id): return
    uid_input = (m.text or "").strip()
    uid = uid_input if uid_input in users else find_user_by_botid(uid_input)
    if uid:
        users[uid]["banned"] = True
        save_users()
        bot.send_message(m.chat.id, f"🚫 Banned {uid}")

@bot.message_handler(func=lambda m: m.text == "📡 ADD CHANNEL")
def add_channel_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Send channel username (@channel):")
    bot.register_next_step_handler(msg, add_channel_process)

def add_channel_process(m):
    username = m.text.strip()
    if username not in MANAGED_CHANNELS: MANAGED_CHANNELS.append(username)
    bot.send_message(m.chat.id, f"✅ Channel Added: {username}")

@bot.message_handler(func=lambda m: m.text == "🔍 RAADI")
def raadi_stats(m):
    if not is_admin(m.from_user.id): return
    total_videos = videos_data.get("total", 0)
    bot.send_message(m.chat.id, f"🔍 Total Videos Downloaded: {total_videos}")

@bot.message_handler(func=lambda m: m.text == "📢 BROADCAST")
def broadcast_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "📝 Send broadcast message:")
    bot.register_next_step_handler(msg, broadcast_send)

def broadcast_send(m):
    if not is_admin(m.from_user.id): return
    text = m.text; count = 0
    for uid in users:
        try:
            bot.send_message(int(uid), text)
            count += 1
        except Exception: continue
    bot.send_message(m.chat.id, f"✅ Broadcast sent to {count} users")

@bot.message_handler(func=lambda m: m.text == "📌 POST CHANNEL")
def post_channel_start(m):
    global CHANNEL_WINDOW_OPEN
    if not is_admin(m.from_user.id): return
    CHANNEL_WINDOW_OPEN = True; POST_CHANNELS.clear()
    msg = bot.send_message(m.chat.id, "Send channel usernames (Max 10). Send DONE when finished.")
    bot.register_next_step_handler(msg, post_channel_add)

def post_channel_add(m):
    if m.text.lower() == "done":
        bot.send_message(m.chat.id, f"✅ {len(POST_CHANNELS)} channels added.")
        return
    username = m.text.replace("@", "").strip()
    POST_CHANNELS.append(username)
    msg = bot.send_message(m.chat.id, f"Added @{username}. Send another or DONE.")
    bot.register_next_step_handler(msg, post_channel_add)

@bot.message_handler(func=lambda m: m.text == "CLOSE CHANNEL POST")
def close_channel_post(m):
    if not is_admin(m.from_user.id): return
    MANAGED_CHANNELS.clear()
    bot.send_message(m.chat.id, "❌ Channels removed.")

@bot.message_handler(func=lambda m: m.text == "👥 SEE LIST")
def see_users(m):
    if not is_admin(m.from_user.id): return
    bot.send_message(m.chat.id, f"📊 Total Users: {len(users)}")

@bot.message_handler(func=lambda m: m.text == "📢 ADD ADS")
def add_ads_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Geli ads:\n`Button Name | Link | Qoraal`", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_add_ads)

def process_add_ads(m):
    global ADS_ENABLED, ADS_BTN_TEXT, ADS_URL, ADS_TEXT
    if not is_admin(m.from_user.id): return
    parts = [p.strip() for p in (m.text or "").split("|")]
    if len(parts) >= 2:
        ADS_BTN_TEXT = parts[0]; ADS_URL = parts[1]
        ADS_TEXT = parts[2] if len(parts) > 2 else "✨ Nagala soco baraha bulshada!"
        ADS_ENABLED = True
        bot.send_message(m.chat.id, "✅ Ads enabled!")

@bot.message_handler(func=lambda m: m.text == "🗑 DELETE ADS")
def delete_ads(m):
    global ADS_ENABLED
    if not is_admin(m.from_user.id): return
    ADS_ENABLED = False
    bot.send_message(m.chat.id, "🗑 Ads disabled.")

@bot.message_handler(func=lambda m: m.text == "📥 IMPORT USERS")
def import_users_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Send Telegram IDs:")
    bot.register_next_step_handler(msg, import_users_process)

def import_users_process(m):
    if not is_admin(m.from_user.id): return
    ids = m.text.strip().replace("\n", " ").split()
    added = 0
    for uid in ids:
        if uid.isdigit() and uid not in users:
            users[uid] = {
                "balance": 0.0, "blocked": 0.0, "ref": random_ref(),
                "bot_id": random_botid(), "invited": 0, "banned": False,
                "verified": False, "is_vip": False, "month": now_month(),
                "settings": DEFAULT_USER_SETTINGS.copy()
            }
            added += 1
    save_users()
    bot.send_message(m.chat.id, f"✅ Imported {added} users.")

@bot.message_handler(func=lambda m: m.text == "🔗 GET REFERRAL CODE")
def get_ref_code_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Send username e.g. @scholes1:")
    bot.register_next_step_handler(msg, get_ref_username)

def get_ref_username(m):
    if not is_admin(m.from_user.id): return
    username = m.text.replace("@", "").strip()
    msg = bot.send_message(m.chat.id, f"User: @{username}\nSend referral code number:")
    bot.register_next_step_handler(msg, lambda x: save_custom_ref_code(x, username))

def save_custom_ref_code(m, username):
    if not is_admin(m.from_user.id): return
    code = m.text.strip()
    for uid, data in users.items():
        if data.get("username", "").lower() == username.lower():
            users[uid]["ref"] = code
            save_users()
            bot.send_message(m.chat.id, f"✅ Code set: {code}")
            return

@bot.message_handler(func=lambda m: m.text == "🔎 SEARCH USER")
def search_user(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Send User ID:")
    bot.register_next_step_handler(msg, search_user_result)

def search_user_result(m):
    if not is_admin(m.from_user.id): return
    uid = m.text.strip()
    if uid in users:
        bot.send_message(m.chat.id, f"👤 User Found\nID: {uid}")

@bot.message_handler(func=lambda m: m.text == "⚙️ SET VIP PRICE")
def set_vip_price_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, f"Current VIP Price: `{VIP_PRICE}` ⭐\nSend new price:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, set_vip_price_process)

def set_vip_price_process(m):
    global VIP_PRICE
    if not is_admin(m.from_user.id): return
    text = (m.text or "").strip()
    if text.isdigit() and int(text) > 0:
        VIP_PRICE = int(text)
        save_config()
        bot.send_message(m.chat.id, f"✅ VIP Price updated to **{VIP_PRICE}** ⭐ Stars!", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "➕ ADD BALANCE")
def add_balance_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Send ID and amount (e.g. 1234567 10):")
    bot.register_next_step_handler(msg, add_balance_process)

def add_balance_process(m):
    if not is_admin(m.from_user.id): return
    try:
        uid_str, amt_str = m.text.strip().split()
        amt = float(amt_str)
        uid = uid_str if uid_str in users else find_user_by_botid(uid_str)
        if uid:
            users[uid]["balance"] += amt
            save_users()
            bot.send_message(m.chat.id, f"✅ Added ${amt:.2f}")
    except Exception: pass

@bot.message_handler(func=lambda m: m.text == "➖ REMOVE MONEY")
def remove_balance_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Send ID and amount:")
    bot.register_next_step_handler(msg, remove_balance_process)

def remove_balance_process(m):
    if not is_admin(m.from_user.id): return
    try:
        uid_str, amt_str = m.text.strip().split()
        amt = float(amt_str)
        uid = uid_str if uid_str in users else find_user_by_botid(uid_str)
        if uid:
            users[uid]["balance"] = max(0.0, users[uid]["balance"] - amt)
            save_users()
            bot.send_message(m.chat.id, f"✅ Removed ${amt:.2f}")
    except Exception: pass

# ================= VERIFY CODE CHECK =================
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
        download_media(m.chat.id, link, m.from_user)

# ================= URL EXTRACTOR =================
def extract_url(text):
    urls = re.findall(r'https?://[^\s]+', text)
    return urls[0] if urls else None

# ================= SEND VIDEO WITH MUSIC & ADS =================
def send_video_with_music(chat_id, file_path, platform=None, m_user=None, original_url=None):
    vid_id = str(uuid.uuid4())[:8]
    video_files[vid_id] = {
        "file_path": file_path,
        "url": original_url
    }

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🎵 Convert to Music (MP3)", callback_data=f"music_{vid_id}"))

    uid_str = str(chat_id)
    user_is_vip = is_vip(chat_id)
    st = get_user_settings(chat_id)

    if user_is_vip:
        if VIP_ADS_ENABLED and VIP_ADS_BTN_TEXT and VIP_ADS_URL:
            kb.add(InlineKeyboardButton(VIP_ADS_BTN_TEXT, url=VIP_ADS_URL))
    else:
        if ADS_ENABLED and ADS_BTN_TEXT and ADS_URL:
            kb.add(InlineKeyboardButton(ADS_BTN_TEXT, url=ADS_URL))

    prefix = get_user_caption_prefix(m_user) if m_user else ""
    caption = ""
    
    if st.get("caption", True):
        caption = f"{prefix}{CAPTION_TEXT}"
        if st.get("source_link", True) and platform:
            caption += f"\n🌐 Platform: {platform.title()}"

        if user_is_vip and VIP_ADS_ENABLED and VIP_ADS_TEXT:
            caption += f"\n\n📢 {VIP_ADS_TEXT}"
        elif not user_is_vip and ADS_ENABLED and ADS_TEXT:
            caption += f"\n\n📢 {ADS_TEXT}"

    videos_data["total"] += 1
    videos_data["users"][uid_str] = videos_data["users"].get(uid_str, 0) + 1
    if platform:
        if "platforms" not in videos_data: videos_data["platforms"] = {}
        videos_data["platforms"][platform] = videos_data["platforms"].get(platform, 0) + 1
    save_videos()

    with open(file_path, "rb") as video:
        bot.send_video(chat_id, video, caption=caption, reply_markup=kb)

    # AUTO MP3 CONVERT FOR VIP USERS
    if user_is_vip and st.get("vip_auto_mp3", False):
        try:
            audio_path = f"audio_{vid_id}.mp3"
            subprocess.run(
                ["ffmpeg", "-y", "-i", file_path, "-vn", "-acodec", "libmp3lame", "-ab", "192k", "-ar", "44100", audio_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
            )
            with open(audio_path, "rb") as audio:
                bot.send_audio(chat_id, audio, title="Auto Converted MP3", caption=f"{prefix}🎵 Auto MP3 Express")
            if os.path.exists(audio_path): os.remove(audio_path)
        except Exception as e:
            print("Auto MP3 Error:", e)

# ================= LINK HANDLER =================
@bot.message_handler(func=lambda m: m.text and "http" in m.text)
def handle_links(message):
    if bot_locked_guard(message) or banned_guard(message): return
    user_id = message.from_user.id
    link = message.text

    if CHANNEL_WINDOW_OPEN and POST_CHANNELS:
        joined_all = True
        for ch in POST_CHANNELS:
            try:
                member = bot.get_chat_member(f"@{ch}", user_id)
                if member.status not in ["member", "administrator", "creator"]:
                    joined_all = False; break
            except Exception:
                joined_all = False; break

        if not joined_all:
            pending_links[user_id] = link
            send_multi_join(user_id)
            return

    if VERIFY_ENABLED and not users.get(str(user_id), {}).get("verified", False):
        code = str(random.randint(10000, 99999))
        verify_pending[user_id] = {"code": code, "link": link}
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📩 Verify via DM", callback_data="via_telegram"))
        kb.add(InlineKeyboardButton("🤖 Verify via Bot", url=f"https://t.me/Verifyd_bot?start={code}"))
        kb.add(InlineKeyboardButton("📧 Verify via Gmail", callback_data="verify_email"))
        bot.send_message(message.chat.id, "🔐 Verification Required:", reply_markup=kb)
        return

    fast_msg = "⚡ <b>VIP Processing Media...</b>" if is_vip(user_id) else "⏳ Downloading video..."
    bot.send_message(message.chat.id, fast_msg, parse_mode="HTML")
    threading.Thread(target=download_media, args=(message.chat.id, link, message.from_user)).start()

# ================= MEDIA DOWNLOADER ENGINE (ALL PLATFORMS) =================
# ================= MEDIA DOWNLOADER ENGINE (ALL PLATFORMS) =================
def download_media(chat_id, text, m_user=None):
    try:
        url = extract_url(text)
        if not url:
            bot.send_message(chat_id, "❌ Link-ga aad soo dirtay ma aha mid sax ah.")
            return

        st = get_user_settings(chat_id)

        # 1. TIKTOK OPTIMIZED ENGINE
        if "tiktok.com" in url or "vt.tiktok.com" in url:
            try:
                api = f"https://tikwm.com/api/?url={url}"
                res = requests.get(api, timeout=20).json()
                if res.get("code") == 0:
                    data = res["data"]
                    if data.get("images"):
                        for i, img in enumerate(data["images"], start=1):
                            img_data = requests.get(img, timeout=20).content
                            filename = f"tiktok_{i}.jpg"
                            with open(filename, "wb") as f: 
                                f.write(img_data)
                            with open(filename, "rb") as photo:
                                prefix = get_user_caption_prefix(m_user) if m_user else ""
                                bot.send_photo(chat_id, photo, caption=f"{prefix}📸 Photo {i}\n{CAPTION_TEXT}")
                            if os.path.exists(filename): 
                                os.remove(filename)
                        return

                    if data.get("play"):
                        video_data = requests.get(data["play"], timeout=40).content
                        filename = f"tiktok_{uuid.uuid4().hex[:6]}.mp4"
                        with open(filename, "wb") as f: 
                            f.write(video_data)
                        send_video_with_music(chat_id, filename, "tiktok", m_user, original_url=url)
                        return
            except Exception as e:
                print("TikTok API Fallback error:", e)

        # 2. PINTEREST SHORTENED URL RESOLVER & FIX
        if "pin.it" in url or "pinterest.com" in url:
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
                }
                session = requests.Session()
                resp = session.get(url, allow_redirects=True, timeout=15, headers=headers)
                url = resp.url.split('?')[0]  # Ka bixi tracking query-yada ku jira link-ga
            except Exception as e:
                print("Pinterest resolve error:", e)

        # IDENTIFY PLATFORM
        platform = "other"
        if "instagram.com" in url: platform = "instagram"
        elif "pinterest.com" in url or "pin.it" in url: platform = "pinterest"
        elif "youtube.com" in url or "youtu.be" in url: platform = "youtube"
        elif "facebook.com" in url or "fb.watch" in url: platform = "facebook"
        elif "snapchat.com" in url or "snap.com" in url: platform = "snapchat"

        out_template = f"dl_{platform}_{uuid.uuid4().hex[:6]}.%(ext)s"

        user_quality = st.get("quality", "Best")
        
        # Safe Format Strategy (Ensures Audio + Video are pre-merged by YouTube/Platforms to prevent FFmpeg crashes)
        if user_quality == "1080p":
            format_opt = "best[height<=1080][ext=mp4]/best[height<=1080]/best"
        elif user_quality == "720p":
            format_opt = "best[height<=720][ext=mp4]/best[height<=720]/best"
        elif user_quality == "480p":
            format_opt = "best[height<=480][ext=mp4]/best[height<=480]/best"
        else:
            format_opt = "best[ext=mp4]/best"

        ydl_opts = {
            "format": format_opt,
            "outtmpl": out_template,
            "quiet": True,
            "no_warnings": True,
            "nocheckcertificate": True,
            "geo_bypass": True,
            "ignoreerrors": True,
            # YouTube & Social Media Block Bypass Options
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "ios", "web"]
                }
            },
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.google.com/"
            }
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                raise Exception("No media info retrieved from link")

            entries = info.get("entries") if "entries" in info and info["entries"] else [info]

            downloaded_any = False
            for entry in entries:
                if not entry: 
                    continue
                
                file_path = ydl.prepare_filename(entry)
                
                # Check for extension mismatch (e.g. mkv, webm, jpg, png, etc.)
                if not os.path.exists(file_path):
                    base, _ = os.path.splitext(file_path)
                    for ext in [".mp4", ".mkv", ".webm", ".jpg", ".png", ".jpeg", ".webp"]:
                        if os.path.exists(f"{base}{ext}"):
                            file_path = f"{base}{ext}"
                            break

                if os.path.exists(file_path):
                    downloaded_any = True
                    # Direct photo download handling (Pinterest/Instagram images)
                    if file_path.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                        with open(file_path, "rb") as photo:
                            prefix = get_user_caption_prefix(m_user) if m_user else ""
                            bot.send_photo(chat_id, photo, caption=f"{prefix}{CAPTION_TEXT}")
                        try:
                            os.remove(file_path)
                        except Exception: pass
                    else:
                        send_video_with_music(chat_id, file_path, platform, m_user, original_url=url)

            if not downloaded_any:
                raise Exception("File was not saved correctly to disk.")

        return

    except Exception as e:
        print("DOWNLOAD ERROR:", e)
        bot.send_message(chat_id, "❌ Download failed! Please make sure link is public and accurate..")



# ================= FIXED MUSIC CONVERSION =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("music_"))
def convert_music(call):
    vid_id = call.data.split("_")[1]
    if vid_id not in video_files:
        bot.answer_callback_query(call.id, "❌ Audio conversion expired! Please re-send the link.", show_alert=True)
        return

    vdata = video_files[vid_id]
    file_path = vdata.get("file_path")
    original_url = vdata.get("url")

    bot.answer_callback_query(call.id, "⚡ Converting to MP3 audio...")

    audio_path = f"audio_{vid_id}.mp3"

    try:
        # Check local stored video file first
        if file_path and os.path.exists(file_path):
            subprocess.run(
                ["ffmpeg", "-y", "-i", file_path, "-vn", "-acodec", "libmp3lame", "-ab", "192k", "-ar", "44100", audio_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
            )
        # Fallback to direct redownload audio extraction if file was missing
        elif original_url:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'audio_{vid_id}.%(ext)s',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'quiet': True,
                'no_warnings': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([original_url])
            audio_path = f"audio_{vid_id}.mp3"

        if os.path.exists(audio_path):
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("📢 BOT CHANNEL", url="https://t.me/tiktokvediodownload"))

            prefix = get_user_caption_prefix(call.from_user)
            with open(audio_path, "rb") as audio:
                bot.send_audio(
                    call.message.chat.id, 
                    audio, 
                    title="Converted Music Audio",
                    performer="DownloadBot", 
                    caption=f"{prefix}🎵 Audio Converted Successfully!\n{CAPTION_TEXT}", 
                    reply_markup=kb
                )

            os.remove(audio_path)
            if file_path and os.path.exists(file_path):
                try: os.remove(file_path)
                except Exception: pass
        else:
            bot.send_message(call.message.chat.id, "❌ Audio extraction failed.")

    except Exception as e:
        print("AUDIO CONVERT ERROR:", e)
        bot.send_message(call.message.chat.id, f"❌ Failed to convert music: {str(e)}")

# ================= MESSAGE USER CALLBACK =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("msguser|"))
def message_user(call):
    if not is_admin(call.from_user.id): return
    uid = call.data.split("|")[1]
    msg = bot.send_message(call.message.chat.id, "Send message for user:")
    bot.register_next_step_handler(msg, send_user_message, uid)

def send_user_message(m, uid):
    if not is_admin(m.from_user.id): return
    try:
        bot.send_message(int(uid), m.text)
        bot.send_message(m.chat.id, "✅ Message sent")
    except Exception:
        bot.send_message(m.chat.id, "❌ Failed to send message")

# ================= RUN THREADS =================
def run_bot1():
    while True:
        try:
            bot.infinity_polling(skip_pending=True)
        except Exception as e:
            print("Bot1 restart:", e)
            time.sleep(3)

def run_bot2():
    while True:
        try:
            bot2.infinity_polling(skip_pending=True)
        except Exception as e:
            print("Bot2 restart:", e)
            time.sleep(3)

def run_support_bot():
    while True:
        try:
            subprocess.call(["python", "support_bot.py"])
        except Exception as e:
            print("Support Bot restart:", e)
            time.sleep(5)

if __name__ == "__main__":
    try:
        tg_client.start()
    except Exception as e:
        print("TelegramClient Start Error:", e)

    t1 = threading.Thread(target=run_bot1)
    t2 = threading.Thread(target=run_bot2)
    t3 = threading.Thread(target=run_support_bot)

    t1.start()
    t2.start()
    t3.start()

    t1.join()
    t2.join()
    t3.join()
