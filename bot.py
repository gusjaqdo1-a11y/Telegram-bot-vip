import os
import re
import json
import time
import uuid
import random
import shutil
import asyncio
import smtplib
import threading
import subprocess
from datetime import datetime
from email.mime.text import MIMEText

import requests
import telebot
from telebot.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice
)
from telethon import TelegramClient
import yt_dlp

# ==============================================================================
#                          1. THREAD-SAFE DATABASE MANAGER
# ==============================================================================

class DBManager:
    """Handles JSON-based state persistence with safe file handling and defaults."""
    
    def __init__(self):
        self.lock = threading.Lock()
        self.USERS_FILE = "users.json"
        self.WITHDRAWS_FILE = "withdraws.json"
        self.VIDEOS_FILE = "videos.json"
        self.CONFIG_FILE = "config.json"
        
        self._init_files()

    def _init_files(self):
        default_config = {
            "vip_price": 100,
            "bot_locked": False,
            "lock_message": "🔒 Bot is Locked By admin @vexdou an update version is comming.",
            "settings_control": True,
            "settings_locked_msg": "⚠️ Setting is not availible !",
            "verify_enabled": False,
            "ads_enabled": False,
            "ads_text": "",
            "ads_btn_text": "",
            "ads_url": "",
            "vip_ads_enabled": False,
            "vip_ads_text": "",
            "vip_ads_btn_text": "",
            "vip_ads_url": ""
        }
        default_videos = {
            "total": 0,
            "platforms": {
                "tiktok": 0, "youtube": 0, "facebook": 0,
                "pinterest": 0, "instagram": 0, "snapchat": 0, "other": 0
            },
            "users": {}
        }
        
        self.load_or_create(self.CONFIG_FILE, default_config)
        self.load_or_create(self.USERS_FILE, {})
        self.load_or_create(self.WITHDRAWS_FILE, [])
        self.load_or_create(self.VIDEOS_FILE, default_videos)

    def load_or_create(self, path, default_data):
        with self.lock:
            if not os.path.exists(path):
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(default_data, f, indent=4, ensure_ascii=False)
                return default_data
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(default_data, f, indent=4, ensure_ascii=False)
                return default_data

    def save(self, path, data):
        with self.lock:
            temp_path = f"{path}.tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            shutil.move(temp_path, path)

    def get_config(self):
        return self.load_or_create(self.CONFIG_FILE, {})

    def save_config(self, data):
        self.save(self.CONFIG_FILE, data)

    def get_users(self):
        return self.load_or_create(self.USERS_FILE, {})

    def save_users(self, data):
        self.save(self.USERS_FILE, data)

    def get_withdraws(self):
        return self.load_or_create(self.WITHDRAWS_FILE, [])

    def save_withdraws(self, data):
        self.save(self.WITHDRAWS_FILE, data)

    def get_videos(self):
        return self.load_or_create(self.VIDEOS_FILE, {})

    def save_videos(self, data):
        self.save(self.VIDEOS_FILE, data)


db = DBManager()

# ==============================================================================
#                          2. CONFIG & ENVIRONMENT SETUP
# ==============================================================================

TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
BOT2_TOKEN = os.getenv("BOT2_TOKEN", "YOUR_BOT2_TOKEN_HERE")

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
PHONE = os.getenv("PHONE", "")

GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_PASS = os.getenv("GMAIL_PASS", "")

STARS_PROVIDER_TOKEN = ""  # Telegram Stars uses an empty string for provider token

ADMIN_IDS = [7983838654]

CHANNEL_USERNAME = "@tiktokvediodownload"

# Global System Runtime States
POST_CHANNELS = []
pending_links = {}
CHANNEL_WINDOW_OPEN = False
MANAGED_CHANNELS = []
MAX_CHANNELS = 10

verify_pending = {}
video_files = {}

CAPTION_TEXT = "Downloaded by:\n@Downloadvedioytibot"

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

# Bot Instances Initialization
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
bot2 = telebot.TeleBot(BOT2_TOKEN, parse_mode="HTML")

tg_client = None
if API_ID and API_HASH:
    try:
        tg_client = TelegramClient("session_verify", API_ID, API_HASH)
    except Exception as e:
        print(f"Telethon initialization skipped or failed: {e}")

# ==============================================================================
#                          3. HELPER UTILITIES
# ==============================================================================

def random_ref():
    return str(random.randint(1000000000, 9999999999))

def random_botid():
    return str(random.randint(10000000000, 99999999999))

def now_month():
    return datetime.now().month

def is_admin(uid):
    return int(uid) in ADMIN_IDS

def is_vip(uid):
    users = db.get_users()
    return users.get(str(uid), {}).get("is_vip", False)

def get_user_settings(uid):
    uid_str = str(uid)
    users = db.get_users()
    if uid_str not in users:
        return DEFAULT_USER_SETTINGS.copy()
    if "settings" not in users[uid_str]:
        users[uid_str]["settings"] = DEFAULT_USER_SETTINGS.copy()
        db.save_users(users)
    return users[uid_str]["settings"]

def find_user_by_botid(bid):
    users = db.get_users()
    for u, data in users.items():
        if data.get("bot_id") == bid:
            return u
    return None

def banned_guard(m):
    uid = str(m.from_user.id)
    users = db.get_users()
    if uid in users and users[uid].get("banned"):
        bot.send_message(m.chat.id, "🚫 You are banned from using this bot.")
        return True
    return False

def bot_locked_guard(message):
    cfg = db.get_config()
    if cfg.get("bot_locked", False) and not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, cfg.get("lock_message", "🔒 Bot-ku waa xidhan yahay."))
        return True
    return False

def get_user_badge(uid):
    if is_vip(uid):
        return "👑 VIP User"
    return "👤 Free User"

def get_user_caption_prefix(m_user):
    if not m_user:
        return ""
    username = f"@{m_user.username}" if m_user.username else m_user.first_name
    if is_vip(m_user.id):
        return f"👑 VIP • {username}\n"
    return f"👤 {username}\n"

def extract_url(text):
    urls = re.findall(r'https?://[^\s]+', text)
    return urls[0] if urls else None

# ==============================================================================
#                          4. UI MENUS AND KEYBOARDS
# ==============================================================================

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
        "🔙 Returning to main menu...",
        reply_markup=user_menu(m.from_user.id)
    )

@bot.message_handler(func=lambda m: m.text == "🔙 BACK MAIN MENU")
def back_button_handler(m):
    back_to_main_menu(m)

# ==============================================================================
#                          5. CORE START & COMMAND HANDLERS
# ==============================================================================

@bot.message_handler(commands=['start'])
def start_handler(message):
    if bot_locked_guard(message):
        return

    uid = str(message.from_user.id)
    args = message.text.split()
    users = db.get_users()

    if uid not in users:
        ref = args[1] if len(args) > 1 else None
        users[uid] = {
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
            if ref_user and ref_user != uid:
                users[ref_user]["balance"] += 0.2
                users[ref_user]["invited"] += 1
                try:
                    bot.send_message(int(ref_user), "🎉 You earned $0.20 from a new referral!")
                except Exception:
                    pass

        db.save_users(users)
    else:
        users[uid]["username"] = message.from_user.username or ""
        if "is_vip" not in users[uid]:
            users[uid]["is_vip"] = False
        if "settings" not in users[uid]:
            users[uid]["settings"] = DEFAULT_USER_SETTINGS.copy()
        db.save_users(users)

    check_membership(message.from_user.id)

@bot.message_handler(commands=['view'])
def view_cmd(message):
    badge = get_user_badge(message.from_user.id)
    bot.send_message(
        message.chat.id,
        f"🤖 <b>BOT SYSTEM INFO</b>\n"
        f"Your Status: <b>{badge}</b>\n\n"
        "📌 <b>Universal Downloader Infrastructure</b>\n"
        "⚡ Supported Platforms:\n"
        "• <b>TikTok</b> (Videos & Photo Slides)\n"
        "• <b>YouTube</b> (Videos, Shorts & Audio)\n"
        "• <b>Facebook</b> (Reels & Public Videos)\n"
        "• <b>Instagram</b> (Reels, Stories & Posts)\n"
        "• <b>Pinterest</b> (Pins & Short Videos)\n"
        "• <b>Snapchat</b> (Public Spotlight Media)\n"
        "• Direct MP3 High-Quality Audio Engine"
    )

@bot.message_handler(commands=['balance'])
def balance_cmd(m):
    uid = str(m.from_user.id)
    users = db.get_users()
    bal = users.get(uid, {}).get("balance", 0.0)
    bot.send_message(m.chat.id, f"💰 Your balance: <b>${bal:.2f}</b>")

@bot.message_handler(commands=['refer'])
def refer_cmd(m):
    uid = str(m.from_user.id)
    users = db.get_users()
    bot_username = bot.get_me().username
    ref = users.get(uid, {}).get("ref", random_ref())
    link = f"https://t.me/{bot_username}?start={ref}"
    bot.send_message(m.chat.id, f"🔗 <b>Your Referral Link:</b>\n<code>{link}</code>\n\nShare and earn $0.20 per user!")

@bot.message_handler(commands=['ping'])
def ping_cmd(m):
    start = time.time()
    msg = bot.send_message(m.chat.id, "🏓 Measuring latency...")
    end = time.time()
    speed = round((end - start) * 1000)
    status = "🟢 Excellent" if speed < 300 else ("🟡 Moderate" if speed < 800 else "🔴 High Latency")
    bot.edit_message_text(
        f"🏓 <b>PONG!</b>\n\n⚡ Server Latency: <b>{speed} ms</b>\n📡 Operational Status: <b>{status}</b>",
        m.chat.id,
        msg.message_id,
        parse_mode="HTML"
    )

# ==============================================================================
#                          6. USER SETTINGS PANEL ENGINE
# ==============================================================================

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
    kb.add(InlineKeyboardButton("❌ Close Panel", callback_data="st_close"))
    return kb

@bot.message_handler(func=lambda m: m.text == "⚙️ SETTINGS")
def user_settings_handler(m):
    if bot_locked_guard(m) or banned_guard(m):
        return

    cfg = db.get_config()
    if not cfg.get("settings_control", True) and not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, cfg.get("settings_locked_msg", "⚠️ Settings disabled."))
        return

    st = get_user_settings(m.from_user.id)
    badge = get_user_badge(m.from_user.id)

    msg_text = (
        f"⚙️ <b>USER PREFERENCES & CONFIGURATION</b>\n"
        f"Account Status: <b>{badge}</b>\n\n"
        f"🎬 Video Quality Preference: <b>{st['quality']}</b>\n"
        f"🎵 Default Audio Format: <b>{st['audio_format']}</b>\n"
        f"🖼️ Include Thumbnail: <b>{'ON' if st['thumbnail'] else 'OFF'}</b>\n"
        f"📝 Auto Captions: <b>{'ON' if st['caption'] else 'OFF'}</b>\n"
        f"🔗 Show Source Link: <b>{'ON' if st['source_link'] else 'OFF'}</b>\n"
        f"🌐 System Language: <b>{st['language']}</b>\n"
        f"📦 Multi-file Compression: <b>{'ON' if st['auto_zip'] else 'OFF'}</b>\n"
        f"🔔 Download Notifications: <b>{'ON' if st['notifications'] else 'OFF'}</b>\n"
    )

    if is_vip(m.from_user.id):
        msg_text += (
            f"\n👑 <b>EXCLUSIVE VIP AUTOMATIONS:</b>\n"
            f"⚡ Direct Audio Extraction: <b>{'ON' if st.get('vip_auto_mp3') else 'OFF'}</b>\n"
            f"💾 Cloud Storage Vaulting: <b>{'ON' if st.get('vip_auto_save') else 'OFF'}</b>\n"
        )

    msg_text += "\n<i>Click any option below to toggle preferences:</i>"
    bot.send_message(m.chat.id, msg_text, reply_markup=build_settings_keyboard(m.from_user.id), parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("st_"))
def settings_callback(call):
    uid = call.from_user.id
    uid_str = str(uid)
    cfg = db.get_config()

    if not cfg.get("settings_control", True) and not is_admin(uid):
        bot.answer_callback_query(call.id, cfg.get("settings_locked_msg", "⚠️ Locked."), show_alert=True)
        return

    users = db.get_users()
    st = get_user_settings(uid)
    action = call.data

    if action == "st_close":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return
    elif action == "st_reset":
        users[uid_str]["settings"] = DEFAULT_USER_SETTINGS.copy()
        db.save_users(users)
        bot.answer_callback_query(call.id, "🔄 Settings reset to factory defaults!")
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
    db.save_users(users)

    msg_text = (
        f"⚙️ <b>USER PREFERENCES & CONFIGURATION</b>\n"
        f"Account Status: <b>{get_user_badge(uid)}</b>\n\n"
        f"🎬 Video Quality Preference: <b>{st['quality']}</b>\n"
        f"🎵 Default Audio Format: <b>{st['audio_format']}</b>\n"
        f"🖼️ Include Thumbnail: <b>{'ON' if st['thumbnail'] else 'OFF'}</b>\n"
        f"📝 Auto Captions: <b>{'ON' if st['caption'] else 'OFF'}</b>\n"
        f"🔗 Show Source Link: <b>{'ON' if st['source_link'] else 'OFF'}</b>\n"
        f"🌐 System Language: <b>{st['language']}</b>\n"
        f"📦 Multi-file Compression: <b>{'ON' if st['auto_zip'] else 'OFF'}</b>\n"
        f"🔔 Download Notifications: <b>{'ON' if st['notifications'] else 'OFF'}</b>\n"
    )
    if is_vip(uid):
        msg_text += (
            f"\n👑 <b>EXCLUSIVE VIP AUTOMATIONS:</b>\n"
            f"⚡ Direct Audio Extraction: <b>{'ON' if st.get('vip_auto_mp3') else 'OFF'}</b>\n"
            f"💾 Cloud Storage Vaulting: <b>{'ON' if st.get('vip_auto_save') else 'OFF'}</b>\n"
        )
    msg_text += "\n<i>Click any option below to toggle preferences:</i>"

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

# ==============================================================================
#                          7. MEMBERSHIP VERIFICATION SYSTEM
# ==============================================================================

def check_membership(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["member", "administrator", "creator"]:
            badge = get_user_badge(user_id)
            bot.send_message(
                user_id,
                f"🎬 <b>Welcome to Universal Media Downloader Bot!</b>\n"
                f"Status: <b>{badge}</b>\n\n"
                "Somalida: Dhammaan Barta Bulshada Linkiyadooda Halkan ku soo dir!\n"
                "Supported Platforms: TikTok, YouTube, Facebook, Instagram, Pinterest, Snapchat.\n\n"
                "📥 Send any video or media link to begin!",
                reply_markup=user_menu(user_id),
                parse_mode="HTML"
            )
        else:
            send_join_message(user_id)
    except Exception:
        send_join_message(user_id)

def send_join_message(user_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ JOIN OFFICIAL CHANNEL", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"))
    kb.add(InlineKeyboardButton("✅ CONFIRM MEMBERSHIP", callback_data="confirm_join"))
    bot.send_message(
        user_id,
        "⚠️ <b>Access Restricted!</b>\n\nYou must subscribe to our channel to use this bot free of charge.",
        reply_markup=kb,
        parse_mode="HTML"
    )

def send_multi_join(user_id):
    kb = InlineKeyboardMarkup(row_width=2)
    buttons = [InlineKeyboardButton(f"➕ JOIN @{ch}", url=f"https://t.me/{ch}") for ch in POST_CHANNELS]
    kb.add(*buttons)
    kb.add(InlineKeyboardButton("✅ VERIFY ALL JOINS", callback_data="multi_checkjoin"))
    bot.send_message(
        user_id,
        "⚠️ <b>Action Required:</b> Please join all mandatory channels listed below to unlock download processing.",
        reply_markup=kb,
        parse_mode="HTML"
    )

# ==============================================================================
#                          8. MONETIZATION & TELEGRAM STARS VIP
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "🚀PREMIUM")
def unlock_vip_cmd(m):
    if bot_locked_guard(m) or banned_guard(m):
        return

    uid = str(m.from_user.id)
    cfg = db.get_config()
    vip_price = cfg.get("vip_price", 100)

    if is_vip(uid):
        bot.send_message(m.chat.id, "👑 <b>You are already a VIP User!</b> Enjoy high-speed downloads and zero ads.")
        return

    text = (
        "👑 <b>UPGRADE TO VIP PREMIUM MEMBERSHIP</b>\n\n"
        "Unlock full bot capability without limitations:\n\n"
        "🚀 <b>Ultra-Fast Downloading Engine</b>\n"
        "🎬 <b>Uncompressed 1080p / 4K Resolutions</b>\n"
        "🎵 <b>Automatic Parallel MP3 Extraction</b>\n"
        "⭐ <b>Official VIP Badge & Zero Ad Interruptions</b>\n\n"
        f"Subscription Cost: <b>{vip_price} Telegram Stars ⭐</b>"
    )
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(f"⭐ Pay {vip_price} Stars Now", callback_data="buy_vip_stars"))
    bot.send_message(m.chat.id, text, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "buy_vip_stars")
def buy_vip_stars_cb(call):
    bot.answer_callback_query(call.id)
    cfg = db.get_config()
    vip_price = cfg.get("vip_price", 100)
    prices = [LabeledPrice(label="VIP Lifetime Access", amount=vip_price)]
    
    bot.send_invoice(
        call.message.chat.id,
        title="👑 PREMIUM VIP ACCESS",
        description="Unlock lifetime high-speed media processing and features!",
        invoice_payload="vip_subscription_payload",
        provider_token=STARS_PROVIDER_TOKEN,
        currency="XTR",
        prices=prices,
        start_parameter="vip-subscription"
    )

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout_pre(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    uid = str(message.from_user.id)
    if message.successful_payment.invoice_payload == "vip_subscription_payload":
        users = db.get_users()
        if uid in users:
            users[uid]["is_vip"] = True
            db.save_users(users)
        bot.send_message(
            message.chat.id,
            "🎉 <b>PAYMENT SUCCESSFUL!</b>\n\nWelcome to the elite club. You are now a 👑 <b>VIP User</b>!",
            reply_markup=user_menu(message.from_user.id),
            parse_mode="HTML"
        )

@bot.message_handler(func=lambda m: m.text == "👑PREMIUM USERS")
def vip_users_list(m):
    if bot_locked_guard(m) or banned_guard(m):
        return
    users = db.get_users()
    vip_list = []
    for u, data in users.items():
        if data.get("is_vip"):
            uname = f"@{data.get('username')}" if data.get('username') else f"ID: {u}"
            vip_list.append(f"👑 <a href='tg://user?id={u}'>{uname}</a>")

    count = len(vip_list)
    msg = f"👑 <b>VIP REGISTERED USERS ({count})</b>\n\n"
    msg += "\n".join(vip_list[:50]) if vip_list else "No active VIP users currently."
    bot.send_message(m.chat.id, msg, parse_mode="HTML")

# ==============================================================================
#                          9. VERIFICATION ENGINE (GMAIL & DM)
# ==============================================================================

@bot2.message_handler(commands=['start'])
def verify_bot2_start(message):
    args = message.text.split()
    if len(args) > 1:
        code = args[1]
        bot2.send_message(message.chat.id, f"🔑 <b>Verification Passcode:</b>\n\n<code>{code}</code>", parse_mode="HTML")
    else:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("Return to Main Bot", url="https://t.me/Downloadvedioytibot"))
        bot2.send_message(message.chat.id, "❌ <b>Missing Passcode Payload!</b>", reply_markup=kb, parse_mode="HTML")

def send_gmail_code(email, code):
    if not GMAIL_USER or not GMAIL_PASS:
        return False
    body = f"Your Verification Passcode is: {code}\n\nEnter this code in the bot to verify."
    msg = MIMEText(body)
    msg["Subject"] = "Telegram Bot Security Verification"
    msg["From"] = GMAIL_USER
    msg["To"] = email
    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(GMAIL_USER, GMAIL_PASS)
        server.sendmail(GMAIL_USER, email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Gmail Dispatch Failure: {e}")
        return False

def process_email_verification(message):
    uid = message.from_user.id
    email = message.text.strip()
    code = str(random.randint(10000, 99999))
    
    if uid in verify_pending:
        verify_pending[uid]["code"] = code
    else:
        verify_pending[uid] = {"code": code, "link": None}

    if send_gmail_code(email, code):
        bot.send_message(message.chat.id, "📩 Verification code successfully dispatched to your email address!")
    else:
        bot.send_message(message.chat.id, "❌ Unable to dispatch email. Check configuration or address.")

async def send_code_telegram_async(user_id, code):
    if not tg_client:
        return False
    try:
        user = await tg_client.get_entity(user_id)
        await tg_client.send_message(user, f"🔐 Your Secret Verification Code:\n\n<code>{code}</code>")
        return True
    except Exception as e:
        print(f"DM Telethon Error: {e}")
        return False

@bot.callback_query_handler(func=lambda call: call.data == "via_telegram")
def via_telegram_cb(call):
    uid = call.from_user.id
    if uid not in verify_pending:
        bot.answer_callback_query(call.id, "Verification session expired.")
        return
    code = verify_pending[uid]["code"]
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    success = loop.run_until_complete(send_code_telegram_async(uid, code))
    if success:
        bot.send_message(call.message.chat.id, "✅ Security code dispatched via Direct Message.")
    else:
        bot.send_message(call.message.chat.id, "⚠️ DM failed. Please initiate a direct chat with the client account first.")

@bot.callback_query_handler(func=lambda call: call.data == "verify_email")
def verify_email_cb(call):
    msg = bot.send_message(call.message.chat.id, "📧 Enter your valid Gmail address:")
    bot.register_next_step_handler(msg, process_email_verification)

# ==============================================================================
#                          10. CALLBACK JOIN & CONFIRMATION
# ==============================================================================

@bot.callback_query_handler(func=lambda call: call.data == "confirm_join")
def confirm_join_cb(call):
    user_id = call.from_user.id
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["member", "administrator", "creator"]:
            bot.answer_callback_query(call.id, "✅ Subscription Verified!")
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception:
                pass

            if user_id in pending_links:
                link = pending_links[user_id]
                del pending_links[user_id]
                bot.send_message(user_id, "⏳ Subscription verified! Downloading requested media...")
                threading.Thread(target=download_media, args=(user_id, link, call.from_user)).start()
            else:
                bot.send_message(user_id, "✅ Welcome! Send any link to download media.")
        else:
            bot.answer_callback_query(call.id, "❌ Channel subscription required!", show_alert=True)
    except Exception:
        bot.answer_callback_query(call.id, "❌ Error verifying membership.", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "multi_checkjoin")
def multi_checkjoin_cb(call):
    user_id = call.from_user.id
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

    if joined_all:
        bot.answer_callback_query(call.id, "✅ All Channels Joined!")
        if user_id in pending_links:
            link = pending_links[user_id]
            del pending_links[user_id]
            bot.send_message(user_id, "⬇️ Processing pending link...")
            threading.Thread(target=download_media, args=(user_id, link, call.from_user)).start()
        else:
            bot.send_message(user_id, "Send your video link now.")
    else:
        bot.answer_callback_query(call.id, "❌ You still haven't joined all required channels!", show_alert=True)

# ==============================================================================
#                          11. ADMIN PANEL & USER MANAGEMENT
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "👑 ADMIN PANEL")
def open_admin_panel(m):
    if not is_admin(m.from_user.id): return
    bot.send_message(m.chat.id, "👑 <b>Control Panel Activated</b>", reply_markup=admin_menu(), parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "💰 BALANCE")
def balance_handler(m):
    if bot_locked_guard(m) or banned_guard(m): return
    uid = str(m.from_user.id)
    users = db.get_users()
    bal = users.get(uid, {}).get("balance", 0.0)
    blocked = users.get(uid, {}).get("blocked", 0.0)
    badge = get_user_badge(m.from_user.id)
    bot.send_message(m.chat.id, f"Badge: <b>{badge}</b>\n💰 Available Balance: <b>${bal:.2f}</b>\n⏳ Pending Lock: <b>${blocked:.2f}</b>", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "🆔 GET ID")
def get_id_handler(m):
    if bot_locked_guard(m) or banned_guard(m): return
    uid = str(m.from_user.id)
    users = db.get_users()
    bid = users.get(uid, {}).get('bot_id', 'N/A')
    badge = get_user_badge(m.from_user.id)
    bot.send_message(m.chat.id, f"Status: <b>{badge}</b>\n🆔 Internal BOT ID: <code>{bid}</code>\n👤 Telegram UID: <code>{uid}</code>", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "👥 REFERRAL")
def referral_handler(m):
    if bot_locked_guard(m) or banned_guard(m): return
    uid = str(m.from_user.id)
    users = db.get_users()
    bot_username = bot.get_me().username
    ref_code = users.get(uid, {}).get('ref', random_ref())
    link = f"https://t.me/{bot_username}?start={ref_code}"
    invited = users.get(uid, {}).get("invited", 0)
    bot.send_message(m.chat.id, f"🔗 <b>Your Invite Link:</b>\n<code>{link}</code>\n\n👥 Successful Referrals: <b>{invited}</b>\n🎁 Earn <b>$0.20</b> for each user invited!", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "☎️ CUSTOMER")
def customer_handler(m):
    if bot_locked_guard(m) or banned_guard(m): return
    bot.send_message(m.chat.id, "☎️ <b>Official Customer Support:</b>\n@scholes1", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "🤖CUSTOMER AI")
def customer_ai_handler(m):
    if bot_locked_guard(m) or banned_guard(m): return
    bot.send_message(m.chat.id, "🤖 <b>Automated AI Support Bot:</b>\n@Aidownoaderbot", parse_mode="HTML")

# --- ADMIN ACTIONS ---

@bot.message_handler(func=lambda m: m.text == "👑 ADD VIP")
def add_vip_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Provide Telegram UID or Bot-ID to convert user to VIP:")
    bot.register_next_step_handler(msg, add_vip_proc)

def add_vip_proc(m):
    if not is_admin(m.from_user.id): return
    target = m.text.strip()
    users = db.get_users()
    uid = target if target in users else find_user_by_botid(target)
    if not uid:
        bot.send_message(m.chat.id, "❌ Specified user not found in database.")
        return
    users[uid]["is_vip"] = True
    db.save_users(users)
    bot.send_message(m.chat.id, f"✅ User <code>{uid}</code> upgraded to VIP status!", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "❌ REMOVE VIP")
def remove_vip_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Provide Telegram UID or Bot-ID to revoke VIP:")
    bot.register_next_step_handler(msg, remove_vip_proc)

def remove_vip_proc(m):
    if not is_admin(m.from_user.id): return
    target = m.text.strip()
    users = db.get_users()
    uid = target if target in users else find_user_by_botid(target)
    if not uid:
        bot.send_message(m.chat.id, "❌ User not found.")
        return
    users[uid]["is_vip"] = False
    db.save_users(users)
    bot.send_message(m.chat.id, f"❌ VIP status revoked for user <code>{uid}</code>.", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "🔒 LOCK BOT")
def lock_bot_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Enter lockout message to show restricted users:")
    bot.register_next_step_handler(msg, lock_bot_proc)

def lock_bot_proc(m):
    if not is_admin(m.from_user.id): return
    text = (m.text or "").strip()
    if not text:
        bot.send_message(m.chat.id, "❌ Lock message cannot be empty.")
        return
    cfg = db.get_config()
    cfg["bot_locked"] = True
    cfg["lock_message"] = text
    db.save_config(cfg)
    bot.send_message(m.chat.id, f"🔒 Bot access locked globally.\nMessage:\n{text}")

@bot.message_handler(func=lambda m: m.text == "🔓 UNLOCK BOT")
def unlock_bot(m):
    if not is_admin(m.from_user.id): return
    cfg = db.get_config()
    cfg["bot_locked"] = False
    db.save_config(cfg)
    bot.send_message(m.chat.id, "🔓 Global bot access restored.")

@bot.message_handler(func=lambda m: m.text == "🛠 SETTINGS CONTROL")
def settings_control_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Enter error text shown to users when Settings panel is disabled:")
    bot.register_next_step_handler(msg, settings_control_proc)

def settings_control_proc(m):
    if not is_admin(m.from_user.id): return
    text = (m.text or "").strip()
    if not text:
        bot.send_message(m.chat.id, "❌ Text cannot be empty.")
        return
    cfg = db.get_config()
    cfg["settings_control"] = False
    cfg["settings_locked_msg"] = text
    db.save_config(cfg)
    bot.send_message(m.chat.id, f"🚫 User settings panel locked.\nDisplay Text: {text}")

@bot.message_handler(func=lambda m: m.text == "🔓 SETTINGS OPEN")
def settings_open(m):
    if not is_admin(m.from_user.id): return
    cfg = db.get_config()
    cfg["settings_control"] = True
    db.save_config(cfg)
    bot.send_message(m.chat.id, "✅ User Settings panel reopened globally.")

@bot.message_handler(func=lambda m: m.text == "📢 ADD ADS VIP")
def add_ads_vip_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Format: `Button Title | URL Link | Ad Caption Text`", parse_mode="Markdown")
    bot.register_next_step_handler(msg, add_ads_vip_proc)

def add_ads_vip_proc(m):
    if not is_admin(m.from_user.id): return
    parts = [p.strip() for p in (m.text or "").split("|")]
    if len(parts) < 2:
        bot.send_message(m.chat.id, "❌ Invalid format.")
        return
    cfg = db.get_config()
    cfg["vip_ads_btn_text"] = parts[0]
    cfg["vip_ads_url"] = parts[1]
    cfg["vip_ads_text"] = parts[2] if len(parts) > 2 else "🌟 Exclusive VIP Announcement"
    cfg["vip_ads_enabled"] = True
    db.save_config(cfg)
    bot.send_message(m.chat.id, "✅ VIP Ad Banner configured and activated!")

@bot.message_handler(func=lambda m: m.text == "🗑 REMOVE ADS VIP")
def remove_ads_vip(m):
    if not is_admin(m.from_user.id): return
    cfg = db.get_config()
    cfg["vip_ads_enabled"] = False
    db.save_config(cfg)
    bot.send_message(m.chat.id, "🗑 VIP Ad Banner deactivated.")

@bot.message_handler(func=lambda m: m.text == "📊 STATS")
def stats_handler(m):
    if not is_admin(m.from_user.id): return
    users = db.get_users()
    vids = db.get_videos()
    total_users = len(users)
    total_balance = sum(u.get("balance", 0.0) for u in users.values())
    vip_count = len([u for u in users.values() if u.get("is_vip")])
    total_downloads = vids.get("total", 0)
    
    msg = (
        f"📊 <b>BOT SYSTEM ANALYTICS</b>\n\n"
        f"👤 Total Registered Users: <b>{total_users}</b>\n"
        f"👑 VIP Subscribers: <b>{vip_count}</b>\n"
        f"💳 User Balance Liability: <b>${total_balance:.2f}</b>\n"
        f"📥 Total Media Downloads: <b>{total_downloads}</b>"
    )
    bot.send_message(m.chat.id, msg, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "📢 BROADCAST")
def broadcast_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "Send broadcast message to transmit to all users:")
    bot.register_next_step_handler(msg, broadcast_send)

def broadcast_send(m):
    if not is_admin(m.from_user.id): return
    text = m.text
    users = db.get_users()
    count = 0
    for uid in users:
        try:
            bot.send_message(int(uid), text)
            count += 1
            time.sleep(0.05)
        except Exception:
            continue
    bot.send_message(m.chat.id, f"✅ Broadcast successfully sent to {count} active chats.")

@bot.message_handler(func=lambda m: m.text == "⚙️ SET VIP PRICE")
def set_vip_price_start(m):
    if not is_admin(m.from_user.id): return
    cfg = db.get_config()
    msg = bot.send_message(m.chat.id, f"Current VIP Price: `{cfg.get('vip_price', 100)}` Stars\nEnter new price in Stars:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, set_vip_price_proc)

def set_vip_price_proc(m):
    if not is_admin(m.from_user.id): return
    text = (m.text or "").strip()
    if text.isdigit() and int(text) > 0:
        cfg = db.get_config()
        cfg["vip_price"] = int(text)
        db.save_config(cfg)
        bot.send_message(m.chat.id, f"✅ VIP Price updated to **{text}** Telegram Stars!", parse_mode="Markdown")

# ==============================================================================
#                          12. WITHDRAWAL SYSTEM ENGINE
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "💸 WITHDRAWAL")
def withdraw_menu(m):
    if banned_guard(m): return
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("USDT-BEP20", "🔙 CANCEL")
    bot.send_message(m.chat.id, "Select withdrawal payout option:", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text in ["USDT-BEP20", "🔙 CANCEL"])
def withdraw_method(m):
    if m.text == "🔙 CANCEL":
        back_to_main_menu(m)
        return
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🔙 CANCEL")
    msg = bot.send_message(m.chat.id, "Enter valid USDT (BEP20) address (starts with 0x):", reply_markup=kb)
    bot.register_next_step_handler(msg, withdraw_address_step)

def withdraw_address_step(m):
    uid = str(m.from_user.id)
    text = (m.text or "").strip()
    if text == "🔙 CANCEL":
        back_to_main_menu(m)
        return
    if not text.startswith("0x") or len(text) < 30:
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("🔙 CANCEL")
        msg = bot.send_message(m.chat.id, "❌ Invalid BEP20 address. Try again:", reply_markup=kb)
        bot.register_next_step_handler(msg, withdraw_address_step)
        return

    users = db.get_users()
    users[uid]["temp_addr"] = text
    db.save_users(users)

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🔙 CANCEL")
    msg = bot.send_message(m.chat.id, f"Enter withdrawal amount (Min $1.00, Available: ${users[uid]['balance']:.2f}):", reply_markup=kb)
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
        msg = bot.send_message(m.chat.id, "❌ Invalid numeric format. Re-enter:", reply_markup=kb)
        bot.register_next_step_handler(msg, withdraw_amount_step)
        return

    users = db.get_users()
    if amt < 1.0 or amt > users[uid]["balance"]:
        bot.send_message(m.chat.id, "❌ Insufficient balance or below minimum threshold.", reply_markup=user_menu(m.from_user.id))
        return

    wid = random.randint(10000, 99999)
    users[uid]["balance"] -= amt
    users[uid]["blocked"] += amt

    withdraws = db.get_withdraws()
    withdrawal = {
        "id": wid, "user": uid, "amount": amt, "blocked": amt,
        "address": users[uid].get("temp_addr", "N/A"),
        "status": "pending", "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    withdraws.append(withdrawal)
    db.save_users(users)
    db.save_withdraws(withdraws)

    bot.send_message(int(uid), f"✅ <b>Withdrawal Submitted</b>\n🧾 Ticket ID: <code>{wid}</code>\n💵 Amount: <b>${amt:.2f}</b>", parse_mode="HTML")

    admin_text = f"💳 <b>NEW WITHDRAWAL REQUEST</b>\n\n👤 User: <code>{uid}</code>\n💵 Amount: <b>${amt:.2f}</b>\n🧾 Ticket ID: <code>{wid}</code>\n📫 Address: <code>{withdrawal['address']}</code>"
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✅ CONFIRM", callback_data=f"confirm_{wid}"),
        InlineKeyboardButton("❌ REJECT", callback_data=f"reject_{wid}"),
        InlineKeyboardButton("🚫 BAN USER", callback_data=f"ban_{uid}"),
        InlineKeyboardButton("💰 LOCK FUNDS", callback_data=f"block_{wid}")
    )
    for admin in ADMIN_IDS:
        try:
            bot.send_message(admin, admin_text, reply_markup=markup, parse_mode="HTML")
        except Exception:
            pass

@bot.callback_query_handler(func=lambda call: call.data.startswith(("confirm_", "reject_", "ban_", "block_")))
def admin_callbacks(call):
    if not is_admin(call.from_user.id): return
    data = call.data
    withdraws = db.get_withdraws()
    users = db.get_users()

    if data.startswith("confirm_"):
        wid = int(data.split("_")[1])
        w = next((x for x in withdraws if x["id"] == wid), None)
        if not w or w["status"] != "pending": return
        w["status"] = "paid"
        users[w["user"]]["blocked"] -= w["blocked"]
        db.save_users(users)
        db.save_withdraws(withdraws)
        bot.answer_callback_query(call.id, "✅ Payout Processed")
        bot.send_message(int(w["user"]), f"✅ Withdrawal request <code>#{wid}</code> has been approved and paid!", parse_mode="HTML")

    elif data.startswith("reject_"):
        wid = int(data.split("_")[1])
        w = next((x for x in withdraws if x["id"] == wid), None)
        if not w or w["status"] != "pending": return
        w["status"] = "rejected"
        users[w["user"]]["balance"] += w["blocked"]
        users[w["user"]]["blocked"] -= w["blocked"]
        db.save_users(users)
        db.save_withdraws(withdraws)
        bot.answer_callback_query(call.id, "❌ Rejected")
        bot.send_message(int(w["user"]), f"❌ Withdrawal request <code>#{wid}</code> was rejected and refunded.", parse_mode="HTML")

    elif data.startswith("ban_"):
        uid = data.split("_")[1]
        if uid in users:
            users[uid]["banned"] = True
            db.save_users(users)
            bot.answer_callback_query(call.id, "🚫 User Banned")

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
        db.save_users(users)
        db.save_withdraws(withdraws)
        bot.answer_callback_query(call.id, "💰 Funds Frozen")

# ==============================================================================
#                          13. MEDIA DISPATCH & AD INJECTION
# ==============================================================================

def send_video_with_music(chat_id, file_path, platform=None, m_user=None, original_url=None):
    vid_id = str(uuid.uuid4())[:8]
    video_files[vid_id] = {
        "file_path": file_path,
        "url": original_url
    }

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🎵 Convert to Audio (MP3)", callback_data=f"music_{vid_id}"))

    uid_str = str(chat_id)
    user_is_vip = is_vip(chat_id)
    st = get_user_settings(chat_id)
    cfg = db.get_config()

    if user_is_vip:
        if cfg.get("vip_ads_enabled") and cfg.get("vip_ads_btn_text") and cfg.get("vip_ads_url"):
            kb.add(InlineKeyboardButton(cfg["vip_ads_btn_text"], url=cfg["vip_ads_url"]))
    else:
        if cfg.get("ads_enabled") and cfg.get("ads_btn_text") and cfg.get("ads_url"):
            kb.add(InlineKeyboardButton(cfg["ads_btn_text"], url=cfg["ads_url"]))

    prefix = get_user_caption_prefix(m_user) if m_user else ""
    caption = ""
    
    if st.get("caption", True):
        caption = f"{prefix}{CAPTION_TEXT}"
        if st.get("source_link", True) and platform:
            caption += f"\n🌐 Platform: {platform.title()}"

        if user_is_vip and cfg.get("vip_ads_enabled") and cfg.get("vip_ads_text"):
            caption += f"\n\n📢 {cfg['vip_ads_text']}"
        elif not user_is_vip and cfg.get("ads_enabled") and cfg.get("ads_text"):
            caption += f"\n\n📢 {cfg['ads_text']}"

    # Track Download Analytics
    vids = db.get_videos()
    vids["total"] = vids.get("total", 0) + 1
    vids["users"][uid_str] = vids["users"].get(uid_str, 0) + 1
    if platform:
        if "platforms" not in vids: vids["platforms"] = {}
        vids["platforms"][platform] = vids["platforms"].get(platform, 0) + 1
    db.save_videos(vids)

    with open(file_path, "rb") as video:
        bot.send_video(chat_id, video, caption=caption, reply_markup=kb, parse_mode="HTML")

    # AUTO MP3 CONVERT FOR VIP USERS
    if user_is_vip and st.get("vip_auto_mp3", False):
        try:
            audio_path = f"audio_{vid_id}.mp3"
            subprocess.run(
                ["ffmpeg", "-y", "-i", file_path, "-vn", "-acodec", "libmp3lame", "-ab", "192k", "-ar", "44100", audio_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
            )
            with open(audio_path, "rb") as audio:
                bot.send_audio(chat_id, audio, title="Auto Converted MP3", caption=f"{prefix}🎵 Express VIP Audio Extraction")
            if os.path.exists(audio_path):
                os.remove(audio_path)
        except Exception as e:
            print(f"Auto MP3 Conversion Error: {e}")

# ==============================================================================
#                          14. UNIVERSAL MEDIA DOWNLOAD ENGINE
# ==============================================================================

@bot.message_handler(func=lambda m: m.text and "http" in m.text)
def handle_links(message):
    if bot_locked_guard(message) or banned_guard(message): return
    user_id = message.from_user.id
    link = message.text.strip()

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

    cfg = db.get_config()
    users = db.get_users()
    
    if cfg.get("verify_enabled") and not users.get(str(user_id), {}).get("verified", False):
        code = str(random.randint(10000, 99999))
        verify_pending[user_id] = {"code": code, "link": link}
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📩 Verify via Direct Message", callback_data="via_telegram"))
        kb.add(InlineKeyboardButton("🤖 Passcode Bot Verification", url=f"https://t.me/Verifyd_bot?start={code}"))
        kb.add(InlineKeyboardButton("📧 Gmail Verification", callback_data="verify_email"))
        bot.send_message(message.chat.id, "🔐 <b>Verification Required to Proceed:</b>", reply_markup=kb, parse_mode="HTML")
        return

    fast_msg = "⚡ <b>VIP Ultra-Speed Processing Media...</b>" if is_vip(user_id) else "⏳ Downloading requested video..."
    bot.send_message(message.chat.id, fast_msg, parse_mode="HTML")
    threading.Thread(target=download_media, args=(message.chat.id, link, message.from_user)).start()

def download_media(chat_id, text, m_user=None):
    file_path = None
    try:
        url = extract_url(text)
        if not url:
            bot.send_message(chat_id, "❌ Invalid media link provided.")
            return

        st = get_user_settings(chat_id)

        # 1. OPTIMIZED TIKTOK DOWNLOADER ENGINE
        if "tiktok.com" in url or "vt.tiktok.com" in url:
            try:
                api = f"https://tikwm.com/api/?url={url}"
                res = requests.get(api, timeout=20).json()
                if res.get("code") == 0:
                    data = res["data"]
                    if data.get("images"):
                        for i, img in enumerate(data["images"], start=1):
                            img_data = requests.get(img, timeout=20).content
                            filename = f"tiktok_{i}_{uuid.uuid4().hex[:4]}.jpg"
                            with open(filename, "wb") as f: f.write(img_data)
                            with open(filename, "rb") as photo:
                                prefix = get_user_caption_prefix(m_user) if m_user else ""
                                bot.send_photo(chat_id, photo, caption=f"{prefix}📸 Photo {i}\n{CAPTION_TEXT}")
                            if os.path.exists(filename): os.remove(filename)
                        return

                    if data.get("play"):
                        video_data = requests.get(data["play"], timeout=40).content
                        filename = f"tiktok_{uuid.uuid4().hex[:6]}.mp4"
                        with open(filename, "wb") as f: f.write(video_data)
                        send_video_with_music(chat_id, filename, "tiktok", m_user, original_url=url)
                        return
            except Exception as e:
                print(f"TikWM Fallback triggered: {e}")

        # 2. PINTEREST SHORTENED URL RESOLVER
        if "pin.it" in url or "pinterest.com" in url:
            try:
                session = requests.Session()
                resp = session.get(url, allow_redirects=True, timeout=15)
                url = resp.url
            except Exception: pass

        # PLATFORM IDENTIFICATION
        platform = "other"
        if "instagram.com" in url: platform = "instagram"
        elif "pinterest.com" in url or "pin.it" in url: platform = "pinterest"
        elif "youtube.com" in url or "youtu.be" in url: platform = "youtube"
        elif "facebook.com" in url or "fb.watch" in url: platform = "facebook"
        elif "snapchat.com" in url or "snap.com" in url: platform = "snapchat"

        out_template = f"dl_{platform}_{uuid.uuid4().hex[:6]}.%(ext)s"

        user_quality = st.get("quality", "Best")
        format_opt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        
        if user_quality == "1080p":
            format_opt = "bestvideo[height<=1080][ext=mp4]+bestaudio/best[height<=1080]"
        elif user_quality == "720p":
            format_opt = "bestvideo[height<=720][ext=mp4]+bestaudio/best[height<=720]"
        elif user_quality == "480p":
            format_opt = "bestvideo[height<=480][ext=mp4]+bestaudio/best[height<=480]"

        ydl_opts = {
            "format": format_opt,
            "outtmpl": out_template,
            "quiet": True,
            "no_warnings": True,
            "merge_output_format": "mp4",
            "nocheckcertificate": True,
            "geo_bypass": True,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            }
        }

        if not is_vip(chat_id):
            ydl_opts["format"] = "best[ext=mp4]/best"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            entries = info["entries"] if "entries" in info and info["entries"] else [info]

            for entry in entries:
                if not entry: continue
                file_path = ydl.prepare_filename(entry)
                if not os.path.exists(file_path):
                    base, _ = os.path.splitext(file_path)
                    if os.path.exists(f"{base}.mp4"): file_path = f"{base}.mp4"

                if os.path.exists(file_path):
                    if file_path.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                        with open(file_path, "rb") as photo:
                            prefix = get_user_caption_prefix(m_user) if m_user else ""
                            bot.send_photo(chat_id, photo, caption=f"{prefix}{CAPTION_TEXT}")
                        os.remove(file_path)
                    else:
                        send_video_with_music(chat_id, file_path, platform, m_user, original_url=url)

        return

    except Exception as e:
        print(f"DOWNLOAD ERROR: {e}")
        bot.send_message(chat_id, "❌ Processing failed! Make sure the link is publicly accessible.")

# ==============================================================================
#                          15. FIXED AUDIO EXTRACTOR CONVERTER
# ==============================================================================

@bot.callback_query_handler(func=lambda call: call.data.startswith("music_"))
def convert_music(call):
    vid_id = call.data.split("_")[1]
    if vid_id not in video_files:
        bot.answer_callback_query(call.id, "❌ Session expired! Re-send link.", show_alert=True)
        return

    vdata = video_files[vid_id]
    file_path = vdata.get("file_path")
    original_url = vdata.get("url")

    bot.answer_callback_query(call.id, "⚡ Converting to MP3 audio track...")
    audio_path = f"audio_{vid_id}.mp3"

    try:
        # Check if local video file exists
        if file_path and os.path.exists(file_path):
            subprocess.run(
                ["ffmpeg", "-y", "-i", file_path, "-vn", "-acodec", "libmp3lame", "-ab", "192k", "-ar", "44100", audio_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
            )
        # Fallback to direct stream download if file cleanup was triggered
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
            kb.add(InlineKeyboardButton("📢 OFFICIAL CHANNEL", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"))

            prefix = get_user_caption_prefix(call.from_user)
            with open(audio_path, "rb") as audio:
                bot.send_audio(
                    call.message.chat.id, 
                    audio, 
                    title="Converted Music Track",
                    performer="Universal Downloader Engine", 
                    caption=f"{prefix}🎵 <b>Audio Converted Successfully!</b>",
                    reply_markup=kb,
                    parse_mode="HTML"
                )
            os.remove(audio_path)
        else:
            bot.send_message(call.message.chat.id, "❌ Failed to convert audio track.")

    except Exception as e:
        print(f"AUDIO EXTRACTION ERROR: {e}")
        bot.send_message(call.message.chat.id, "❌ Audio processing failed.")

# ==============================================================================
#                          16. ASYNC POLLING LAUNCH ENGINE
# ==============================================================================

def run_second_bot():
    """Runs the secondary verification bot instance in a separate thread."""
    if BOT2_TOKEN and BOT2_TOKEN != "YOUR_BOT2_TOKEN_HERE":
        try:
            print("🟢 Secondary Verification Bot starting...")
            bot2.infinity_polling(timeout=20, long_polling_timeout=10)
        except Exception as e:
            print(f"Bot 2 polling error: {e}")

if __name__ == "__main__":
    print("🚀 Initializing Universal Downloader Bot Engine...")

    # Start Secondary Verification Bot in parallel thread
    t2 = threading.Thread(target=run_second_bot, daemon=True)
    t2.start()

    # Start Telethon Client if credentials exist
    if tg_client:
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(tg_client.start(phone=PHONE))
            print("🟢 Telethon DM Verification Client Connected.")
        except Exception as e:
            print(f"Telethon Startup Error: {e}")

    # Primary Bot Polling Loop
    while True:
        try:
            print("🟢 Main Bot Polling Started...")
            bot.infinity_polling(timeout=30, long_polling_timeout=15)
        except Exception as e:
            print(f"Primary Bot encountered an error: {e}")
            time.sleep(5)
