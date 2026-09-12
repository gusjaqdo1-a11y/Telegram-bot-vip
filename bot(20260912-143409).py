import telebot
from pymongo import MongoClient
import requests
from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, LabeledPrice, KeyboardButton, KeyboardButtonRequestChat, ChatAdministratorRights, ReplyKeyboardRemove
import os, json, random, secrets, string
from datetime import datetime, timedelta, timezone
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None
import yt_dlp
import subprocess
import re
import shutil
import threading
import asyncio
import uuid
import time
import html
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from telethon import TelegramClient

# ================= CONFIG =================

TOKEN = os.getenv("BOT_TOKEN")
BOT2_TOKEN = os.getenv("BOT2_TOKEN")  # Existing verification bot
CUSTOMER_AI_BOT_TOKEN = os.getenv("CUSTOMER_AI_BOT_TOKEN", "").strip()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")

PHONE = os.getenv("PHONE")

# Resend API Config for support@vexdou.space (HTTP Port 443 - Railway-friendly)

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "support@vexdou.space")

# D7 SMS API Config (SMS ONLY)
D7_TOKEN = os.getenv("D7_TOKEN")
D7_VERIFY_BASE_URL = "https://api.d7networks.com/verify/v1"
D7_VERIFY_SEND_URL = f"{D7_VERIFY_BASE_URL}/otp/send-otp"
D7_VERIFY_RESEND_URL = f"{D7_VERIFY_BASE_URL}/otp/resend-otp"
D7_VERIFY_CHECK_URL = f"{D7_VERIFY_BASE_URL}/otp/verify-otp"
D7_VERIFY_STATUS_URL = f"{D7_VERIFY_BASE_URL}/report"

# WaForge WhatsApp OTP (WhatsApp is intentionally separate from D7 SMS)
WAFORGE_API_KEY = os.getenv("WAFORGE_API_KEY", "").strip()
# Optional overrides are useful if WaForge changes the endpoint/auth scheme.
WAFORGE_BASE_URL = os.getenv("WAFORGE_BASE_URL", "https://www.waforge.online/api").rstrip("/")
WAFORGE_API_KEY_HEADER = os.getenv("WAFORGE_API_KEY_HEADER", "Authorization").strip() or "Authorization"
if WAFORGE_BASE_URL.endswith("/api/v1"):
    # Older deployments may still have the legacy base in Railway Variables.
    # Prefer the current WaForge /api contract automatically.
    WAFORGE_BASE_URL = WAFORGE_BASE_URL[:-3]
# WaForge's current public API uses /api/otp/send and /api/otp/verify.
# Keep the legacy /api/v1 paths as a compatibility fallback for older accounts.
WAFORGE_OTP_SEND_URL = f"{WAFORGE_BASE_URL}/otp/send"
WAFORGE_OTP_VERIFY_URL = f"{WAFORGE_BASE_URL}/otp/verify"
WAFORGE_LEGACY_BASE_URL = os.getenv("WAFORGE_LEGACY_BASE_URL", "https://www.waforge.online/api/v1").rstrip("/")
WAFORGE_OTP_SEND_LEGACY_URL = f"{WAFORGE_LEGACY_BASE_URL}/otp/send"
WAFORGE_OTP_VERIFY_LEGACY_URL = f"{WAFORGE_LEGACY_BASE_URL}/otp/verify"
WAFORGE_OTP_TTL = 300
WHATSAPP_OTP_TTL = WAFORGE_OTP_TTL
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "49"))
YTDLP_COOKIES_FILE = os.getenv("YTDLP_COOKIES_FILE", "").strip()
# Optional song-recognition service. If configured, it can identify Original Sounds and return
# the real artist/album artwork. It is never required for normal MP3 conversion.
AUDD_API_TOKEN = os.getenv("AUDD_API_TOKEN", "").strip()  # Optional legacy fallback; AcoustID is primary
# AcoustID + Chromaprint audio fingerprinting. Register an application at AcoustID
# and put its application/client key in ACOUSTID_API_KEY.
ACOUSTID_API_KEY = os.getenv("ACOUSTID_API_KEY", "").strip()
ACOUSTID_TIMEOUT = int(os.getenv("ACOUSTID_TIMEOUT", "30"))
# Jamendo: full-length tracks are used only when Jamendo marks them downloadable.
JAMENDO_CLIENT_ID = os.getenv("JAMENDO_CLIENT_ID", "").strip()
JAMENDO_TIMEOUT = int(os.getenv("JAMENDO_TIMEOUT", "20"))
YOUTUBE_PO_TOKEN = os.getenv("YOUTUBE_PO_TOKEN", "").strip()
YOUTUBE_PLAYER_CLIENT = os.getenv("YOUTUBE_PLAYER_CLIENT", "").strip()

# Download limits (admin-configurable at runtime).
FREE_MAX_MINUTES_DEFAULT = int(os.getenv("FREE_MAX_MINUTES", "10"))
PREMIUM_MAX_MINUTES_DEFAULT = int(os.getenv("PREMIUM_MAX_MINUTES", "120"))
MAX_YOUTUBE_DURATION = FREE_MAX_MINUTES_DEFAULT * 60

# Cobalt: no API key is required when your own Cobalt instance is configured
# without authentication. The bot uses POST / on the configured instance.
# For a monetized/premium bot, use a self-hosted Cobalt instance rather than
# relying on the public api.cobalt.tools service.
COBALT_API_URL = os.getenv("COBALT_API_URL", "").strip().rstrip("/")
COBALT_API_KEY = os.getenv("COBALT_API_KEY", "").strip()
COBALT_TIMEOUT = int(os.getenv("COBALT_TIMEOUT", "180"))

# ================= RAPIDAPI YOUTUBE DOWNLOADER =================
RAPIDAPI_YT_HOST = os.getenv("RAPIDAPI_YT_HOST", "youtube-media-downloader.p.rapidapi.com").strip()
RAPIDAPI_YT_DETAILS_URL = os.getenv("RAPIDAPI_YT_DETAILS_URL", "https://youtube-media-downloader.p.rapidapi.com/v2/video/details").strip()
# Keep the key in your hosting provider's secret/environment settings.
RAPIDAPI_YT_KEY = os.getenv("RAPIDAPI_YT_KEY", "").strip()
RAPIDAPI_TIMEOUT = int(os.getenv("RAPIDAPI_TIMEOUT", "60"))
# Instagram RapidAPI configuration. Values can also be managed from Admin Panel
# and are persisted in MongoDB settings (no environment variable required for limits).
RAPIDAPI_IG_HOST = os.getenv("RAPIDAPI_IG_HOST", "").strip()
RAPIDAPI_IG_URL = os.getenv("RAPIDAPI_IG_URL", "").strip()
RAPIDAPI_IG_KEY = os.getenv("RAPIDAPI_IG_KEY", "").strip()

MAX_CONCURRENT_DOWNLOADS = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "20"))

# Premium configuration
PREMIUM_DEFAULT_PRICES = {
    "1": 5.0,
    "3": 12.0,
    "9": 30.0,
    "12": 40.0,
}
PREMIUM_QUALITY_FORMATS = {
    "720": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
    "1080": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
    "1440": "bestvideo[height<=1440]+bestaudio/best[height<=1440]/best",
    "2160": "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best",
}
FREE_QUALITY_FORMAT = "bestvideo[height<=720]+bestaudio/best[height<=720]/best"

# Platform access / YouTube policy
# Free users: TikTok, Instagram, Facebook, Pinterest, Snapchat, X/Twitter and
# YouTube Shorts. Full YouTube videos are Premium-only unless Admin opens them.
FREE_PLATFORMS = {"tiktok", "instagram", "facebook", "pinterest", "snapchat", "twitter"}
YOUTUBE_FULL_FREE_DEFAULT = False
FREE_YOUTUBE_MAX_MB_DEFAULT = int(os.getenv("FREE_YOUTUBE_MAX_MB", "49"))
TRIAL_YOUTUBE_MAX_MB_DEFAULT = int(os.getenv("TRIAL_YOUTUBE_MAX_MB", "2048"))
PREMIUM_YOUTUBE_MAX_MB_DEFAULT = int(os.getenv("PREMIUM_YOUTUBE_MAX_MB", "0"))  # 0 = Unlimited

# Dual executors for Priority (Quick Access) & Normal

PREMIUM_CONCURRENT_DOWNLOADS = int(os.getenv("PREMIUM_CONCURRENT_DOWNLOADS", "60"))
FREE_CONCURRENT_DOWNLOADS = int(os.getenv("FREE_CONCURRENT_DOWNLOADS", str(min(8, MAX_CONCURRENT_DOWNLOADS))))
QUICK_ACCESS_CONCURRENT_DOWNLOADS = int(os.getenv("QUICK_ACCESS_CONCURRENT_DOWNLOADS", "100"))
vip_executor = ThreadPoolExecutor(max_workers=max(1, PREMIUM_CONCURRENT_DOWNLOADS))
quick_executor = ThreadPoolExecutor(max_workers=max(1, QUICK_ACCESS_CONCURRENT_DOWNLOADS))
normal_executor = ThreadPoolExecutor(max_workers=max(1, FREE_CONCURRENT_DOWNLOADS))

http_session = requests.Session()

tg_client = TelegramClient(
    "session",
    API_ID,
    API_HASH
)

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
bot2 = telebot.TeleBot(BOT2_TOKEN, parse_mode="HTML")
customer_ai_bot = telebot.TeleBot(CUSTOMER_AI_BOT_TOKEN, parse_mode="HTML") if CUSTOMER_AI_BOT_TOKEN else None

ADMIN_IDS = [7983838654]
PRIMARY_ADMIN_ID = 7983838654

CHANNEL_ID = "@tiktokvediodownload"

POST_CHANNELS = []
pending_links = {}
CHANNEL_WINDOW_OPEN = False
MANAGED_CHANNELS = []
MAX_CHANNELS = 10
# User-owned Telegram destinations where this bot has been added/admined.
# Stored in Mongo settings so redeploys do not erase the list.
DESTINATION_KEY = "bot_destinations"
# Pending Telegram chat-picker requests: request_id -> {user_id, type}
DESTINATION_REQUESTS = {}

def _destinations():
    rows=get_setting(DESTINATION_KEY,[]) or []
    return rows if isinstance(rows,list) else []

def _save_destinations(rows):
    clean=[]; seen=set()
    for d in rows or []:
        try:
            cid=int(d.get("chat_id"))
            if cid in seen: continue
            seen.add(cid); clean.append({
                "chat_id":cid,"type":str(d.get("type","group")),"title":str(d.get("title", "")),
                "username":str(d.get("username", "")),"added_by":str(d.get("added_by", "")),
                "added_at":str(d.get("added_at", datetime.now(timezone.utc).isoformat())),
                "intro_sent":bool(d.get("intro_sent", False))
            })
        except Exception: pass
    set_setting(DESTINATION_KEY,clean)

def _destination_intro_text(dtype="group"):
    if dtype == "channel":
        return (
            "🤖 <b>Download Bot Connected</b>\n\n"
            "This channel is now connected to the bot.\n"
            "The bot can send admin broadcasts and updates here. ⚡"
        )
    return (
        "🤖 <b>Download Bot Connected</b>\n\n"
        "This group is now connected to the bot.\n"
        "The bot can send admin broadcasts and updates here. ⚡"
    )

def _send_destination_intro(chat_id, dtype):
    try:
        bot.send_message(chat_id, _destination_intro_text(dtype), parse_mode="HTML")
        return True
    except Exception as e:
        print("Destination intro error:", repr(e))
        return False

def _upsert_destination(chat, added_by=None):
    if not chat: return False, False
    ctype=str(getattr(chat,"type","") or "")
    if ctype not in {"group","supergroup","channel"}: return False, False
    rows=_destinations(); cid=int(chat.id)
    existing=next((x for x in rows if int(x.get("chat_id",0))==cid),None)
    is_new = existing is None
    data={
        "chat_id":cid,
        "type":ctype,
        "title":getattr(chat,"title","") or "",
        "username":getattr(chat,"username","") or "",
        "added_by":str(added_by or (existing or {}).get("added_by", "")),
        "added_at":(existing or {}).get("added_at",datetime.now(timezone.utc).isoformat()),
        "intro_sent":bool((existing or {}).get("intro_sent", False))
    }
    if existing: existing.update(data)
    else: rows.append(data)
    _save_destinations(rows)
    return is_new, data["intro_sent"]

def _remove_destination(chat_id):
    rows=[x for x in _destinations() if str(x.get("chat_id"))!=str(chat_id)]
    _save_destinations(rows)

def _destination_label(d):
    return ("📢 " if d.get("type")=="channel" else "👥 ")+str(d.get("title") or d.get("username") or d.get("chat_id"))


BOT_LOCKED = False
LOCK_MESSAGE = "🔒 Bot is temporarily locked by admin."

pending_post = {}
channel_posts = {}

VERIFY_ENABLED = False
verify_pending = {}
email_verify_pending = {}
phone_verify_pending = {}
whatsapp_verify_pending = {}
video_files = {}
# Short-lived map used by the MUSIC button. The actual media is re-downloaded only when requested.
music_pending = {}
MUSIC_PENDING_TTL = int(os.getenv("MUSIC_PENDING_TTL", "1800"))
song_search_pending = {}
_MAIN_BOT_USERNAME_CACHE = ""
SONG_SEARCH_TTL = int(os.getenv("SONG_SEARCH_TTL", "900"))
SONG_SEARCH_PAGE_SIZE = 5

DOWNLOAD_CAPTION = "Downloaded Via\n@Downloadvedioytibot"
MP3_COVER_DEFAULT = False


ADS_ENABLED = False
ADS_TEXT = ""
ADS_BTN_TEXT = ""
ADS_URL = ""

# Premium/download state
premium_pending = {}
premium_quality_pending = {}
PREMIUM_WARNING_SENT_DAYS = 7
PREMIUM_CHECK_INTERVAL = 3600
LANGUAGES = {
    "en": {"name":"🇬🇧 English","currency":"USD","rate":1.0},
    "so": {"name":"🇸🇴 Soomaali","currency":"SOS","rate":570.0},
    "am": {"name":"🇪🇹 አማርኛ","currency":"ETB","rate":188.0},
    "om": {"name":"🇪🇹 Afaan Oromoo","currency":"ETB","rate":188.0},
    "ar": {"name":"🇸🇦 العربية","currency":"SAR","rate":3.75},
    "fr": {"name":"🇫🇷 Français","currency":"EUR","rate":0.85},
    "es": {"name":"🇪🇸 Español","currency":"EUR","rate":0.85},
    "de": {"name":"🇩🇪 Deutsch","currency":"EUR","rate":0.85},
    "pt": {"name":"🇧🇷 Português","currency":"BRL","rate":5.40},
    "tr": {"name":"🇹🇷 Türkçe","currency":"TRY","rate":41.0},
    "hi": {"name":"🇮🇳 हिन्दी","currency":"INR","rate":83.5},
    "id": {"name":"🇮🇩 Bahasa Indonesia","currency":"IDR","rate":16500.0},
    "ja": {"name":"🇯🇵 日本語","currency":"JPY","rate":147.0},
    "ko": {"name":"🇰🇷 한국어","currency":"KRW","rate":1380.0},
    "zh": {"name":"🇨🇳 中文","currency":"CNY","rate":7.10},
}

MAIN_LABELS = {
 "en":{"balance":"💰 BALANCE","withdraw":"💸 WITHDRAWAL","ref":"👥 REFERRAL","id":"🆔 GET ID","premium":"💎 PREMIUM","music":"🎵 MUSIC","profile":"👤 Profile","topup":"💳 ADD BALANCE","history":"📜 HISTORY","lang":"🌐 CHANGE LANGUAGE","trial":"🎁 1 DAY FREE TRIAL","customer":"☎️ CUSTOMER","ai":"🤖 CUSTOMER AI","promo":"🎟 PROMO CODE","currency":"💱 CHANGE CURRENCY"},
 "so":{"balance":"💰 HARAAGA","withdraw":"💸 BIXID","ref":"👥 CASUUMAAD","id":"🆔 ID","premium":"💎 PREMIUM","music":"🎵 MUSIC","profile":"👤 PROFILE","topup":"💳 LACAG KU DAR","history":"📜 TAARIIKH","lang":"🌐 BEDEL LUQAD","trial":"🎁 1 MAALIN Tijaabo","customer":"☎️ MACMIILKA","ai":"🤖 CAWIMAAD AI","promo":"🎟 PROMO CODE","currency":"💱 BEDEL LACAG"},
 "am":{"balance":"💰 ሂሳብ","withdraw":"💸 ማውጣት","ref":"👥 ሪፈራል","id":"🆔 ID","premium":"💎 PREMIUM","music":"🎵 MUSIC","profile":"👤 መገለጫ","topup":"💳 ገንዘብ ጨምር","history":"📜 ታሪክ","lang":"🌐 ቋንቋ ቀይር","trial":"🎁 1 ቀን ሙከራ","customer":"☎️ ድጋፍ","ai":"🤖 AI","promo":"🎟 PROMO CODE","currency":"💱 ምንዛሬ ቀይር"},
 "om":{"balance":"💰 HINDEEN","withdraw":"💸 BAASI","ref":"👥 REFERRAL","id":"🆔 ID","premium":"💎 PREMIUM","music":"🎵 MUSIC","profile":"👤 PROFILE","topup":"💳 MAALLQA DABALI","history":"📜 SEENSA","lang":"🌐 AFAAN JIJJIIRI","trial":"🎁 YAALI 1 GUYYAA","customer":"☎️ DEEGARSA","ai":"🤖 AI","promo":"🎟 PROMO CODE","currency":"💱 MAALLQA JIJJIIRI"},
 "ar":{"balance":"💰 الرصيد","withdraw":"💸 سحب","ref":"👥 إحالة","id":"🆔 المعرف","premium":"💎 بريميوم","music":"🎵 موسيقى","profile":"👤 الملف الشخصي","topup":"💳 إضافة رصيد","history":"📜 السجل","lang":"🌐 تغيير اللغة","trial":"🎁 تجربة مجانية يوم واحد","customer":"☎️ الدعم","ai":"🤖 دعم AI","promo":"🎟 PROMO CODE","currency":"💱 تغيير العملة"},
 "fr":{"balance":"💰 SOLDE","withdraw":"💸 RETRAIT","ref":"👥 PARRAINAGE","id":"🆔 ID","premium":"💎 PREMIUM","music":"🎵 MUSIQUE","profile":"👤 PROFIL","topup":"💳 AJOUTER","history":"📜 HISTORIQUE","lang":"🌐 CHANGER LANGUE","trial":"🎁 ESSAI 1 JOUR","customer":"☎️ SUPPORT","ai":"🤖 SUPPORT AI","promo":"🎟 PROMO CODE","currency":"💱 CHANGER DEVISE"},
 "es":{"balance":"💰 SALDO","withdraw":"💸 RETIRAR","ref":"👥 REFERIDOS","id":"🆔 ID","premium":"💎 PREMIUM","music":"🎵 MÚSICA","profile":"👤 PERFIL","topup":"💳 AÑADIR SALDO","history":"📜 HISTORIAL","lang":"🌐 CAMBIAR IDIOMA","trial":"🎁 PRUEBA 1 DÍA","customer":"☎️ SOPORTE","ai":"🤖 SOPORTE AI","promo":"🎟 PROMO CODE","currency":"💱 CAMBIAR MONEDA"},
 "de":{"balance":"💰 GUTHABEN","withdraw":"💸 AUSZAHLUNG","ref":"👥 EMPFEHLUNG","id":"🆔 ID","premium":"💎 PREMIUM","music":"🎵 MUSIK","profile":"👤 PROFIL","topup":"💳 GUTHABEN AUFLADEN","history":"📜 VERLAUF","lang":"🌐 SPRACHE ÄNDERN","trial":"🎁 1 TAG TEST","customer":"☎️ SUPPORT","ai":"🤖 AI SUPPORT","promo":"🎟 PROMO CODE","currency":"💱 WÄHRUNG ÄNDERN"},
 "pt":{"balance":"💰 SALDO","withdraw":"💸 SAQUE","ref":"👥 INDICAÇÕES","id":"🆔 ID","premium":"💎 PREMIUM","music":"🎵 MÚSICA","profile":"👤 PERFIL","topup":"💳 ADICIONAR SALDO","history":"📜 HISTÓRICO","lang":"🌐 MUDAR IDIOMA","trial":"🎁 TESTE 1 DIA","customer":"☎️ SUPORTE","ai":"🤖 SUPORTE AI","promo":"🎟 PROMO CODE","currency":"💱 ALTERAR MOEDA"},
 "tr":{"balance":"💰 BAKİYE","withdraw":"💸 ÇEKİM","ref":"👥 REFERANS","id":"🆔 ID","premium":"💎 PREMIUM","music":"🎵 MÜZİK","profile":"👤 PROFİL","topup":"💳 BAKİYE EKLE","history":"📜 GEÇMİŞ","lang":"🌐 DİLİ DEĞİŞTİR","trial":"🎁 1 GÜN DENEME","customer":"☎️ DESTEK","ai":"🤖 AI DESTEK","promo":"🎟 PROMO CODE","currency":"💱 PARA BİRİMİNİ DEĞİŞTİR"},
 "hi":{"balance":"💰 बैलेंस","withdraw":"💸 निकासी","ref":"👥 रेफरल","id":"🆔 ID","premium":"💎 प्रीमियम","music":"🎵 म्यूज़िक","profile":"👤 प्रोफ़ाइल","topup":"💳 बैलेंस जोड़ें","history":"📜 इतिहास","lang":"🌐 भाषा बदलें","trial":"🎁 1 दिन ट्रायल","customer":"☎️ सहायता","ai":"🤖 AI सहायता","promo":"🎟 PROMO CODE","currency":"💱 मुद्रा बदलें"},
 "id":{"balance":"💰 SALDO","withdraw":"💸 PENARIKAN","ref":"👥 REFERAL","id":"🆔 ID","premium":"💎 PREMIUM","music":"🎵 MUSIK","profile":"👤 PROFIL","topup":"💳 TAMBAH SALDO","history":"📜 RIWAYAT","lang":"🌐 GANTI BAHASA","trial":"🎁 UJI COBA 1 HARI","customer":"☎️ BANTUAN","ai":"🤖 BANTUAN AI","promo":"🎟 PROMO CODE","currency":"💱 GANTI MATA UANG"},
 "ja":{"balance":"💰 残高","withdraw":"💸 出金","ref":"👥 紹介","id":"🆔 ID","premium":"💎 プレミアム","music":"🎵 音楽","profile":"👤 プロフィール","topup":"💳 残高追加","history":"📜 履歴","lang":"🌐 言語変更","trial":"🎁 1日無料トライアル","customer":"☎️ サポート","ai":"🤖 AIサポート","promo":"🎟 PROMO CODE","currency":"💱 通貨を変更"},
 "ko":{"balance":"💰 잔액","withdraw":"💸 출금","ref":"👥 추천","id":"🆔 ID","premium":"💎 프리미엄","music":"🎵 음악","profile":"👤 프로필","topup":"💳 잔액 충전","history":"📜 기록","lang":"🌐 언어 변경","trial":"🎁 1일 무료 체험","customer":"☎️ 고객지원","ai":"🤖 AI 지원","promo":"🎟 PROMO CODE","currency":"💱 통화 변경"},
 "zh":{"balance":"💰 余额","withdraw":"💸 提现","ref":"👥 邀请","id":"🆔 ID","premium":"💎 高级版","music":"🎵 音乐","profile":"👤 个人资料","topup":"💳 充值","history":"📜 历史","lang":"🌐 更换语言","trial":"🎁 1天免费试用","customer":"☎️ 客服","ai":"🤖 AI客服","promo":"🎟 PROMO CODE","currency":"💱 更改货币"},
}

def lang_of(uid):
    return users.get(str(uid),{}).get("language") or "en"

# Backward-compatible helper used by Customer AI.
def get_user_lang(uid):
    return lang_of(uid)

# ================= LIVE CURRENCY / CRYPTO ASSET SYSTEM =================
# Each user owns an actual asset: amount + balance_asset. USD is not the hidden base.
FIAT_CURRENCIES = {
    "USD": ("🇺🇸", "US Dollar", 1.0), "SOS": ("🇸🇴", "Somali Shilling", 570.0),
    "ETB": ("🇪🇹", "Ethiopian Birr", 188.0), "EUR": ("🇪🇺", "Euro", 0.85),
    "SAR": ("🇸🇦", "Saudi Riyal", 3.75), "BRL": ("🇧🇷", "Brazilian Real", 5.40),
    "TRY": ("🇹🇷", "Turkish Lira", 41.0), "INR": ("🇮🇳", "Indian Rupee", 83.5),
    "IDR": ("🇮🇩", "Indonesian Rupiah", 16500.0), "JPY": ("🇯🇵", "Japanese Yen", 147.0),
    "KRW": ("🇰🇷", "South Korean Won", 1380.0), "CNY": ("🇨🇳", "Chinese Yuan", 7.10),
}
CRYPTO_CURRENCIES = {
    "BTC": ("₿", "Bitcoin", "bitcoin"), "ETH": ("Ξ", "Ethereum", "ethereum"),
    "USDT": ("₮", "Tether", "tether"), "BNB": ("🟡", "BNB", "binancecoin"),
    "SOL": ("◎", "Solana", "solana"), "XRP": ("✕", "XRP", "ripple"),
    "USDC": ("◉", "USD Coin", "usd-coin"), "ADA": ("₳", "Cardano", "cardano"),
    "DOGE": ("Ð", "Dogecoin", "dogecoin"), "TRX": ("🔺", "TRON", "tron"),
    "AVAX": ("🔺", "Avalanche", "avalanche-2"), "LINK": ("🔗", "Chainlink", "chainlink"),
    "DOT": ("●", "Polkadot", "polkadot"), "LTC": ("Ł", "Litecoin", "litecoin"),
    "BCH": ("₿", "Bitcoin Cash", "bitcoin-cash"), "XLM": ("✦", "Stellar", "stellar"),
    "TON": ("💎", "Toncoin", "the-open-network"), "SHIB": ("🐕", "Shiba Inu", "shiba-inu"),
    "NEAR": ("🟢", "NEAR Protocol", "near"), "UNI": ("🦄", "Uniswap", "uniswap"),
}
AVAILABLE_CURRENCIES={**{k:k for k in FIAT_CURRENCIES},**{k:k for k in CRYPTO_CURRENCIES}}
FX_CACHE={"fiat":{},"crypto":{},"sources":{}}
FX_CACHE_TTL=300; CRYPTO_CACHE_TTL=120; FX_LOCK=threading.Lock(); CRYPTO_TX_LOCK=threading.RLock()

def cur_code(uid):
    u=users.get(str(uid),{}); return u.get("balance_asset") or u.get("currency") or "USD"
def is_crypto(code): return code in CRYPTO_CURRENCIES

def _fetch_fiat_rates():
    now=time.time()
    try:
        quotes=','.join(c for c in FIAT_CURRENCIES if c!="USD")
        r=requests.get("https://api.frankfurter.dev/v2/rates",params={"base":"USD","quotes":quotes},timeout=10); r.raise_for_status()
        data=r.json(); rates={x.get("quote"):float(x.get("rate")) for x in data if x.get("quote") and x.get("rate")}; rates["USD"]=1.0
        FX_CACHE["fiat"]={"rates":rates,"time":now}; FX_CACHE["sources"]["fiat"]="Frankfurter"; return rates
    except Exception as e: print("Frankfurter FX update failed:",e)
    try:
        r=requests.get("https://open.er-api.com/v6/latest/USD",timeout=10); r.raise_for_status(); rates=r.json().get("rates") or {}; rates["USD"]=1.0
        FX_CACHE["fiat"]={"rates":rates,"time":now}; FX_CACHE["sources"]["fiat"]="ExchangeRate-API fallback"; return rates
    except Exception as e: print("FX fallback failed:",e)
    return FX_CACHE.get("fiat",{}).get("rates",{})

def _fetch_crypto_prices(force=False):
    now=time.time(); c=FX_CACHE.get("crypto",{})
    if not force and c and now-c.get("time",0)<CRYPTO_CACHE_TTL: return c.get("prices",{})
    ids=','.join(v[2] for v in CRYPTO_CURRENCIES.values())
    try:
        r=requests.get("https://api.coingecko.com/api/v3/simple/price",params={"ids":ids,"vs_currencies":"usd"},timeout=12); r.raise_for_status(); data=r.json() or {}
        prices={code:float(data[cid]["usd"]) for code,(_,_,cid) in CRYPTO_CURRENCIES.items() if cid in data and data[cid].get("usd") is not None}
        if prices: FX_CACHE["crypto"]={"prices":prices,"time":now}; FX_CACHE["sources"]["crypto"]="CoinGecko"; return prices
    except Exception as e: print("Crypto market update failed:",e)
    return c.get("prices",{})

def refresh_market_rates(force=False):
    with FX_LOCK:
        now=time.time(); f=FX_CACHE.get("fiat",{}); c=FX_CACHE.get("crypto",{})
        if force or not f or now-f.get("time",0)>=FX_CACHE_TTL: _fetch_fiat_rates()
        if force or not c or now-c.get("time",0)>=CRYPTO_CACHE_TTL: _fetch_crypto_prices(force)

def market_refresh_worker():
    """Background market updater. Keeps fiat and crypto prices fresh without blocking Telegram polling."""
    while True:
        try:
            refresh_market_rates(force=False)
        except Exception as e:
            print(f"Market refresh worker error: {e}")
        # Crypto is refreshed every 2 minutes by refresh_market_rates();
        # the worker wakes more often so expired cache is noticed promptly.
        time.sleep(30)

def asset_usd_price(code):
    refresh_market_rates(False)
    if code=="USD": return 1.0
    if is_crypto(code): return float(FX_CACHE.get("crypto",{}).get("prices",{}).get(code,0) or 0)
    return float(FX_CACHE.get("fiat",{}).get("rates",{}).get(code,0) or 0)

def asset_to_usd(code,amount):
    p=asset_usd_price(code); return float(amount or 0)*p if p>0 else 0.0

def usd_to_asset(code,usd):
    p=asset_usd_price(code); return float(usd or 0)/p if p>0 else 0.0

def fx_rate(uid):
    code=cur_code(uid); p=asset_usd_price(code)
    return 1.0 if code=="USD" else (1.0/p if is_crypto(code) and p>0 else p)

def format_asset(code,amount):
    if code=="USD": return f"${float(amount or 0):,.2f} USD"
    return f"{float(amount or 0):,.8f} {code}" if is_crypto(code) else f"{float(amount or 0):,.2f} {code}"

def money_text(uid,usd): return format_asset(cur_code(uid),usd_to_asset(cur_code(uid),usd))
def market_rate_text(code):
    p=asset_usd_price(code)
    return "N/A" if not p else (f"1 {code} = ${p:,.8f}" if is_crypto(code) else f"1 USD = {p:,.4f} {code}")
def balance_amount(uid): return float(users.get(str(uid),{}).get("balance",0) or 0)
def blocked_amount(uid): return float(users.get(str(uid),{}).get("blocked",0) or 0)

def pending_withdrawal_amount(uid):
    """Return the amount currently waiting for admin approval.
    Pending withdrawals are NOT part of Blocked Amount until an admin
    explicitly uses the money-block action.
    """
    uid=str(uid); total=0.0; code=cur_code(uid)
    for w in withdraws if "withdraws" in globals() else []:
        if str(w.get("user")) != uid: continue
        if str(w.get("status","pending")).lower() != "pending": continue
        amount=float(w.get("amount",0) or 0)
        # Pending Amount is displayed in the user's current asset.
        if str(w.get("asset") or code)==code:
            total += amount
        else:
            total += usd_to_asset(code,float(w.get("amount_usd",0) or 0))
    return max(0.0,total)

def pending_withdrawal_usd(uid):
    uid=str(uid); total=0.0
    for w in withdraws if "withdraws" in globals() else []:
        if str(w.get("user")) != uid: continue
        if str(w.get("status","pending")).lower() != "pending": continue
        total += float(w.get("amount_usd",0) or 0)
    return max(0.0,total)
def hold_amount_usd(uid):
    now=datetime.now(timezone.utc); total=0.0
    for h in conversion_holds_col.find({"user_id":str(uid),"status":"hold"}):
        exp=parse_seen_time(h.get("expires_at"))
        if exp and exp>now: total+=float(h.get("usd_amount",0) or 0)
    return total
def available_asset_amount(uid):
    code=cur_code(uid)
    if balance_is_locked(uid): return 0.0
    return max(0.0,balance_amount(uid)-blocked_amount(uid)-usd_to_asset(code,hold_amount_usd(uid)))

def balance_locked_message(uid):
    u=users.get(str(uid),{}); code=u.get("balance_activation_code") or ""; sec=balance_lock_remaining(uid)
    days=max(0,sec//86400); hours=max(0,(sec%86400)//3600)
    snap=balance_freezes_col.find_one({"user_id":str(uid),"status":"closed"}) if "balance_freezes_col" in globals() else None
    saved_usd=0.0
    if snap:
        saved_usd=asset_to_usd(str(snap.get("balance_asset") or "USD"),float(snap.get("balance",0) or 0))+sum(asset_to_usd(c,float(a or 0)) for c,a in (snap.get("portfolio") or {}).items() if c in AVAILABLE_CURRENCIES)
    return ("🔒 <b>Your Balance is temporarily closed.</b>\n\n"
            f"💰 <b>Saved Balance Value:</b> ${saved_usd:,.2f} USD\n"
            "Please contact Customer/Admin to reactivate it.\n"
            f"🗝 <b>Activation Code:</b> <code>{html.escape(str(code))}</code>\n"
            f"⏳ Automatic deletion in: <b>{days}d {hours}h</b>\n\n"
            "⚠️ If it is not opened before the 10-day deadline, the saved balance will be permanently removed.")
def balance_usd_value(uid): return asset_to_usd(cur_code(uid),balance_amount(uid))

def migrate_legacy_ledger_once():
    if get_setting("asset_ledger_migrated_v1",False): return
    for _uid,_u in users.items():
        if float(_u.get("balance",0) or 0)>0 and not balance_ledger_col.find_one({"user_id":_uid}):
            code=_u.get("balance_asset","USD"); amt=float(_u.get("balance",0)); balance_ledger_col.insert_one({"user_id":_uid,"type":"migration","source":"legacy_balance","asset":code,"asset_amount":amt,"usd_amount":asset_to_usd(code,amt),"time":datetime.now(timezone.utc)})
    set_setting("asset_ledger_migrated_v1",True)

def ledger_credit(uid,usd_amount,source,meta=None):
    uid=str(uid); code=cur_code(uid); a=usd_to_asset(code,usd_amount); users[uid]["balance"]=round(balance_amount(uid)+a,12); save_user(uid)
    balance_ledger_col.insert_one({"user_id":uid,"type":"credit","source":source,"usd_amount":float(usd_amount),"asset":code,"asset_amount":a,"meta":meta or {},"time":datetime.now(timezone.utc)})
    return a
def ledger_debit(uid,asset_amount,source,meta=None):
    uid=str(uid); a=float(asset_amount); users[uid]["balance"]=round(max(0,balance_amount(uid)-a),12); save_user(uid)
    balance_ledger_col.insert_one({"user_id":uid,"type":"debit","source":source,"asset":cur_code(uid),"asset_amount":a,"usd_amount":asset_to_usd(cur_code(uid),a),"meta":meta or {},"time":datetime.now(timezone.utc)})
def get_portfolio(uid):
    u = users.get(str(uid), {})
    p = u.get("portfolio")
    if not isinstance(p, dict):
        p = {}
        u["portfolio"] = p
    return p

def portfolio_usd_value(uid):
    total = 0.0
    for code, amount in get_portfolio(uid).items():
        if code in AVAILABLE_CURRENCIES:
            total += asset_to_usd(code, float(amount or 0))
    return total

def total_assets_usd(uid):
    return balance_usd_value(uid) + portfolio_usd_value(uid)

def add_portfolio_asset(uid, code, amount):
    if amount <= 0: return
    p = get_portfolio(uid)
    p[code] = round(float(p.get(code, 0) or 0) + float(amount), 12)
    users[str(uid)]["portfolio"] = p
    save_user(uid)

def portfolio_text(uid):
    rows=[]
    p=get_portfolio(uid)
    for code, amount in p.items():
        amount=float(amount or 0)
        if amount <= 0: continue
        rows.append((asset_to_usd(code,amount), code, amount))
    rows.sort(reverse=True)
    return rows


def migrate_legacy_ledger_once():
    if get_setting("asset_ledger_migrated_v1",False): return
    for _uid,_u in users.items():
        if float(_u.get("balance",0) or 0)>0 and not balance_ledger_col.find_one({"user_id":_uid}):
            code=_u.get("balance_asset","USD"); amt=float(_u.get("balance",0)); balance_ledger_col.insert_one({"user_id":_uid,"type":"migration","source":"legacy_balance","asset":code,"asset_amount":amt,"usd_amount":asset_to_usd(code,amt),"time":datetime.now(timezone.utc)})
    set_setting("asset_ledger_migrated_v1",True)

def ledger_credit(uid,usd_amount,source,meta=None):
    uid=str(uid); code=cur_code(uid); a=usd_to_asset(code,usd_amount); users[uid]["balance"]=round(balance_amount(uid)+a,12); save_user(uid)
    balance_ledger_col.insert_one({"user_id":uid,"type":"credit","source":source,"usd_amount":float(usd_amount),"asset":code,"asset_amount":a,"meta":meta or {},"time":datetime.now(timezone.utc)})
    return a
def ledger_debit(uid,asset_amount,source,meta=None):
    uid=str(uid); a=float(asset_amount); users[uid]["balance"]=round(max(0,balance_amount(uid)-a),12); save_user(uid)
    balance_ledger_col.insert_one({"user_id":uid,"type":"debit","source":source,"asset":cur_code(uid),"asset_amount":a,"usd_amount":asset_to_usd(cur_code(uid),a),"meta":meta or {},"time":datetime.now(timezone.utc)})
def crypto_min_deposit_usd():
    try: return max(0.0,float(get_setting("crypto_min_deposit_usd",10.0) or 0))
    except Exception: return 10.0

def total_account_deposits_usd(uid):
    """Cumulative real account credits, excluding conversions and legacy migration."""
    uid=str(uid); total=0.0
    try:
        for row in balance_ledger_col.find({"user_id":uid,"type":"credit"}):
            source=str(row.get("source","")).lower()
            if source not in {"currency_conversion","crypto_conversion","migration","referral_network_commission"}:
                total += float(row.get("usd_amount",0) or 0)
    except Exception: pass
    return max(0.0,total)

def crypto_access_status(uid):
    minimum=crypto_min_deposit_usd(); deposited=total_account_deposits_usd(uid)
    if minimum<=0: return True,0.0,minimum
    return deposited+1e-9>=minimum,max(0.0,minimum-deposited),minimum

def crypto_system_open():
    return bool(get_setting("crypto_enabled", True))

def user_is_verified(uid):
    """One canonical verification check for Gmail, SMS or WhatsApp."""
    u=users.get(str(uid),{})
    return bool(u.get("verified") or u.get("whatsapp_verified") or u.get("phone_verified") or u.get("email_verified"))

def premium_verification_required():
    return bool(get_setting("premium_verify_required", True))

def balance_is_locked(uid):
    return bool(users.get(str(uid),{}).get("balance_locked", False))

def balance_lock_remaining(uid):
    u=users.get(str(uid),{})
    dt=parse_seen_time(u.get("balance_lock_until"))
    if not dt: return 0
    return max(0,int((dt-datetime.now(timezone.utc)).total_seconds()))

def generate_balance_activation_code():
    alphabet=string.ascii_uppercase+string.digits
    return "".join(secrets.choice(alphabet) for _ in range(25))

def premium_platform_names():
    # These are the complete Premium/Trial download platforms. Keep this list
    # centralized so the Premium UI and access gate always agree.
    base=["TikTok","Instagram","Facebook","Pinterest","Snapchat","X/Twitter","YouTube"]
    return base + list(PREMIUM_EXTRA_PLATFORMS) if "PREMIUM_EXTRA_PLATFORMS" in globals() else base

def premium_platform_keys():
    return {
        "reddit","threads","likee","vimeo","dailymotion","soundcloud","twitch",
        "tumblr","streamable","odnoklassniki",
    }

def platform_display_name(platform):
    names={
        "tiktok":"TikTok","instagram":"Instagram","facebook":"Facebook","pinterest":"Pinterest",
        "snapchat":"Snapchat","twitter":"X/Twitter","youtube":"YouTube","reddit":"Reddit",
        "threads":"Threads","likee":"Likee","vimeo":"Vimeo","dailymotion":"Dailymotion",
        "soundcloud":"SoundCloud","twitch":"Twitch","tumblr":"Tumblr","streamable":"Streamable",
        "odnoklassniki":"OK.ru",
    }
    return names.get(platform, str(platform or "Unknown"))

def youtube_full_free_enabled():
    return bool(get_setting("youtube_full_free", YOUTUBE_FULL_FREE_DEFAULT))

def premium_required_for_platform(platform, uid, link=None):
    """Return whether this exact link requires Premium/Trial access."""
    uid=str(uid)
    if is_admin(uid) or is_quick_access(uid):
        return False
    platform=str(platform or "unknown")
    if platform in premium_platform_keys():
        return True
    if platform == "youtube":
        # Shorts remain available to Free users. Full videos are Premium-only
        # unless Admin explicitly enables full YouTube for Free users.
        if link and youtube_is_short(link):
            return False
        return not youtube_full_free_enabled()
    return False

def premium_gate_message(uid, platform):
    name=html.escape(platform_display_name(platform))
    count=len(premium_platform_names())
    lang=str(users.get(str(uid),{}).get("language") or users.get(str(uid),{}).get("customer_ai_language") or "en")
    if lang=="so":
        return (f"💎 <b>Premium ayaa loo baahan yahay</b>\n\n"
                f"<b>{name}</b> wuxuu u baahan yahay Premium/Trial.\n\n"
                f"🌐 Premium/Trial: <b>{count} platforms</b>\n"
                "⚡ Priority & faster downloads\n🎥 Quality sare\n"
                "Fur Premium si aad u isticmaasho.")
    return (f"💎 <b>Premium Required</b>\n\n"
            f"<b>{name}</b> requires Premium/Trial access.\n\n"
            f"🌐 Premium/Trial includes <b>{count} platforms</b>\n"
            "⚡ Priority & faster downloads\n🎥 Higher quality\n\n"
            "Open Premium to continue.")

def user_timezone(uid):
    """Best-effort timezone from stored city or verified phone country; Telegram does not expose device timezone."""
    u=users.get(str(uid),{})
    city=str(u.get("city") or "").lower()
    city_map={"somalia":"Africa/Mogadishu","mogadishu":"Africa/Mogadishu","ethiopia":"Africa/Addis_Ababa","addis ababa":"Africa/Addis_Ababa","kenya":"Africa/Nairobi","nairobi":"Africa/Nairobi","uganda":"Africa/Kampala","tanzania":"Africa/Dar_es_Salaam","djibouti":"Africa/Djibouti","saudi arabia":"Asia/Riyadh","riyadh":"Asia/Riyadh","uae":"Asia/Dubai","dubai":"Asia/Dubai","united arab emirates":"Asia/Dubai","india":"Asia/Kolkata","pakistan":"Asia/Karachi","turkey":"Europe/Istanbul","uk":"Europe/London","united kingdom":"Europe/London","france":"Europe/Paris","germany":"Europe/Berlin"}
    zone=next((z for k,z in city_map.items() if k in city),None)
    phone=str(u.get("phone") or "")
    if not zone and phone:
        prefix_map={"+252":"Africa/Mogadishu","+251":"Africa/Addis_Ababa","+254":"Africa/Nairobi","+255":"Africa/Dar_es_Salaam","+256":"Africa/Kampala","+253":"Africa/Djibouti","+966":"Asia/Riyadh","+971":"Asia/Dubai","+91":"Asia/Kolkata","+92":"Asia/Karachi","+90":"Europe/Istanbul","+33":"Europe/Paris","+49":"Europe/Berlin","+44":"Europe/London"}
        for prefix,z in prefix_map.items():
            if phone.startswith(prefix): zone=z; break
    if ZoneInfo and zone:
        try: return ZoneInfo(zone)
        except Exception: pass
    return timezone.utc

def local_datetime_text(uid, dt):
    dt=parse_seen_time(dt) or datetime.now(timezone.utc)
    local=dt.astimezone(user_timezone(uid))
    return local.strftime("%Y-%m-%d %H:%M %Z")

def crypto_hold_open():
    return bool(get_setting("crypto_hold_enabled", True))

def crypto_fee_percent():
    try: return max(0.0, float(get_setting("crypto_fee_percent", 1.0) or 0.0))
    except Exception: return 1.0

def live_network_gas_usd(code):
    """Best-effort live network fee estimate; falls back to admin reserve.
    This is an estimate for a normal transfer, not a guaranteed swap/withdrawal fee.
    Internal ledger conversions do not broadcast a blockchain transaction.
    """
    try:
        if code == "ETH":
            r=requests.post("https://ethereum-rpc.publicnode.com",json={"jsonrpc":"2.0","method":"eth_gasPrice","params":[],"id":1},timeout=5); wei=int(r.json()["result"],16)
            return (wei*21000/1e18)*asset_usd_price("ETH")
        if code == "BNB":
            r=requests.post("https://bsc-dataseed.bnbchain.org",json={"jsonrpc":"2.0","method":"eth_gasPrice","params":[],"id":1},timeout=5); wei=int(r.json()["result"],16)
            return (wei*21000/1e18)*asset_usd_price("BNB")
        if code == "BTC":
            r=requests.get("https://mempool.space/api/v1/fees/recommended",timeout=5); sat_vb=float(r.json().get("fastestFee",0) or 0)
            # Approximate simple transaction size; actual UTXO/input/output count varies.
            btc_fee=(sat_vb*140)/100_000_000
            return btc_fee*asset_usd_price("BTC")
    except Exception as e:
        print("Live network fee lookup failed:", code, e)
    return None

def crypto_gas_fee_usd(code=None):
    mode=str(get_setting("crypto_gas_mode","AUTO") or "AUTO").upper()
    if mode=="AUTO" and code in CRYPTO_CURRENCIES:
        live=live_network_gas_usd(code)
        if live is not None and live>=0: return live
    try: return max(0.0, float(get_setting("crypto_gas_fee_usd", 0.10) or 0.0))
    except Exception: return 0.10

def crypto_fee_usd(gross_usd, code=None):
    gross=float(gross_usd or 0.0)
    pct=gross*crypto_fee_percent()/100.0
    gas=crypto_gas_fee_usd(code) if is_crypto(code) else 0.0
    return pct, gas, pct+gas

def conversion_preview(uid,new_code,source_amount=None):
    old=cur_code(uid); available=available_asset_amount(uid)
    amount=available if source_amount is None else float(source_amount)
    gross_usd=asset_to_usd(old,amount)
    fee_usd,gas_usd,total_fee=crypto_fee_usd(gross_usd,new_code)
    net_usd=max(0.0,gross_usd-total_fee)
    new_amt=usd_to_asset(new_code,net_usd)
    return old,amount,gross_usd,fee_usd,gas_usd,total_fee,net_usd,new_amt

def currency_kb():
    kb=InlineKeyboardMarkup(); btn=[]
    if not crypto_system_open():
        for code,(flag,_,_) in FIAT_CURRENCIES.items(): btn.append(InlineKeyboardButton(f"{flag} {code}",callback_data=f"currency:{code}"))
    else:
        for code,(flag,_,_) in FIAT_CURRENCIES.items(): btn.append(InlineKeyboardButton(f"{flag} {code}",callback_data=f"currency:{code}"))
        for code,(icon,_,_) in CRYPTO_CURRENCIES.items(): btn.append(InlineKeyboardButton(f"{icon} {code}",callback_data=f"currency:{code}"))
    for i in range(0,len(btn),2): kb.row(*btn[i:i+2])
    kb.add(InlineKeyboardButton("🔄 UPDATE MARKET",callback_data="currency_refresh"))
    return kb

def currency_is_available(code):
    return code in FIAT_CURRENCIES or (code in CRYPTO_CURRENCIES and crypto_system_open())

def record_crypto_fee(uid, from_code, to_code, gross_usd, fee_usd, gas_usd, source_amount, net_usd):
    crypto_fee_ledger_col.insert_one({
        "user_id":str(uid), "type":"conversion_fee", "from_asset":from_code, "to_asset":to_code,
        "gross_usd":float(gross_usd), "fee_usd":float(fee_usd), "gas_fee_usd":float(gas_usd),
        "net_usd":float(net_usd), "source_amount":float(source_amount),
        "time":datetime.now(timezone.utc)
    })

def get_crypto_fee_stats_today():
    now=datetime.now(timezone.utc); start=now.replace(hour=0,minute=0,second=0,microsecond=0)
    pipe=[{"$match":{"time":{"$gte":start}}},{"$group":{"_id":None,"fee":{"$sum":"$fee_usd"},"gas":{"$sum":"$gas_fee_usd"},"count":{"$sum":1}}}]
    r=list(crypto_fee_ledger_col.aggregate(pipe))
    return (float(r[0].get("fee",0)),float(r[0].get("gas",0)),int(r[0].get("count",0))) if r else (0.0,0.0,0)


def language_kb(prefix="lang"):
    # 15 languages displayed as 3 buttons per row: 1 2 3 / 4 5 6 / ...
    kb=InlineKeyboardMarkup(row_width=3)
    items=[InlineKeyboardButton(v["name"],callback_data=f"{prefix}:{code}") for code,v in LANGUAGES.items()]
    for i in range(0,len(items),3):
        kb.row(*items[i:i+3])
    return kb



START_MESSAGE_DEFAULT = """🎉 <b>WELCOME TO DOWNLOAD BOT</b> 🎉

👋 Hello <b>{name}</b>, Welcome!

🚀 Download your favorite content
quickly and easily.

━━━━━━━━━━━━━━━━━━

🎬 <b>VIDEO</b>
TikTok • Instagram • Facebook
Pinterest • Snapchat • X
YouTube • Reddit • Threads
Likee • Vimeo • Dailymotion
Twitch • Tumblr • OK.ru

🎵 <b>MUSIC</b>
Convert Video → MP3
🎼 Correct Song Name
👤 Correct Artist
💿 Search Your ❤️ Sign

💎 <b>PREMIUM</b>
High Quality • Faster Downloads
More Platforms • More Features

━━━━━━━━━━━━━━━━━━

📥 Send your link now!

⚡ Fast • Easy • Powerful
❤️ Thanks for using us!"""

def welcome_destination_markup():
    """Show only the destination buttons currently opened by admin."""
    kb=InlineKeyboardMarkup(row_width=2)
    buttons=[]
    if bool(get_setting("add_group_enabled", True)):
        buttons.append(InlineKeyboardButton("➕ Add Group",callback_data="add_group:welcome"))
    if bool(get_setting("add_channel_enabled", True)):
        buttons.append(InlineKeyboardButton("➕ Add Channel",callback_data="add_channel:welcome"))
    if buttons:
        kb.add(*buttons)
    return kb if buttons else None

def music_destination_markup():
    """Inline destination buttons for MP3 files, respecting admin open/close controls."""
    kb=InlineKeyboardMarkup(row_width=2)
    buttons=[]
    if bool(get_setting("add_group_enabled", True)):
        buttons.append(InlineKeyboardButton("➕ Add Group",callback_data=f"add_group:mp3_{uuid.uuid4().hex[:12]}"))
    if bool(get_setting("add_channel_enabled", True)):
        buttons.append(InlineKeyboardButton("➕ Add Channel",callback_data=f"add_channel:mp3_{uuid.uuid4().hex[:12]}"))
    if buttons:
        kb.add(*buttons)
    return kb if buttons else None

def render_start_message(uid):
    """Render the admin-configurable welcome message with safe user placeholders."""
    uid = str(uid)
    u = users.get(uid, {})
    name = (u.get("first_name") or "there").strip()
    username = u.get("username") or ""
    text = get_setting("start_message", START_MESSAGE_DEFAULT)
    replacements = {
        "{name}": name,
        "{username}": username,
        "{id}": uid,
    }
    for key, value in replacements.items():
        text = text.replace(key, value)
    return text

# ================= MONGODB SETUP (DUAL DATABASE) =================

MONGO_URI_1 = os.getenv("MONGO_URI_1", os.getenv("MONGO_URI", "mongodb://localhost:27017/user_db"))
MONGO_URI_2 = os.getenv("MONGO_URI_2", "mongodb://localhost:27017/stats_db")

try:
    mongo_client1 = MongoClient(MONGO_URI_1)
    try:
        db1 = mongo_client1.get_default_database()
    except Exception:
        db1 = mongo_client1["user_db"]
    
    users_col = db1["users"]
    withdraws_col = db1["withdraws"]
    print("✅ MongoDB 1 (Users & Withdraws) Connected Successfully")
except Exception as e:
    print(f"❌ MongoDB 1 Connection Error: {e}")
    exit()

try:
    mongo_client2 = MongoClient(MONGO_URI_2)
    try:
        db2 = mongo_client2.get_default_database()
    except Exception:
        db2 = mongo_client2["stats_db"]
    
    videos_col = db2["videos"]
    feedback_col = db2["feedback"]
    print("✅ MongoDB 2 (Videos, Stats & Feedback) Connected Successfully")
except Exception as e:
    print(f"❌ MongoDB 2 Connection Error: {e}")
    exit()

# ================= SETTINGS SETUP =================

settings_col = db1["settings"]
premium_logs_col = db1["premium_logs"]
activity_col = db1["activity_logs"]
ratings_col = db1["bot_ratings"]
rating_campaigns_col = db1["rating_campaigns"]
referral_commissions_col = db1["referral_commissions"]
balance_ledger_col = db1["balance_ledger"]
conversion_holds_col = db1["conversion_holds"]
crypto_fee_ledger_col = db1["crypto_fee_ledger"]
song_stats_col = db2["song_stats"]
balance_freezes_col = db1["balance_freezes"]

def get_setting(key, default):
    res = settings_col.find_one({"_id": key})
    return res["value"] if res else default

def set_setting(key, value):
    settings_col.update_one({"_id": key}, {"$set": {"value": value}}, upsert=True)

def touch_user(uid, save=True):
    uid=str(uid)
    if uid not in users:
        return
    users[uid]["last_seen_at"]=datetime.now(timezone.utc).isoformat()
    if save:
        save_user(uid)
    # Streak progress is driven by real user activity. The helper is defined
    # later in the file, so keep this safe during module initialization.
    try:
        if "_streak_touch" in globals():
            _streak_touch(uid)
    except Exception as e:
        print("Streak touch error:", repr(e))

def current_trial_version():
    return int(get_setting("trial_version",1) or 1)

def trial_days():
    return max(1,int(get_setting("trial_days",1) or 1))

def trial_enabled():
    return bool(get_setting("trial_enabled",True))

def trial_available(uid):
    uid=str(uid)
    if not trial_enabled() or uid not in users:
        return False
    return users[uid].get("trial_version_used") != current_trial_version()

def open_trial_campaign(days):
    days=int(days)
    if days<1 or days>3650:
        raise ValueError("invalid trial days")
    version=current_trial_version()+1
    set_setting("trial_days",days); set_setting("trial_version",version); set_setting("trial_enabled",True)
    return version,days

def referral_reward_amount():
    return max(0.0,float(get_setting("referral_reward",0.2) or 0.0))

def referral_network_percent():
    return max(0.0,float(get_setting("referral_network_percent",0.01) or 0.0))

def process_referral_signup(uid,pending_ref):
    uid=str(uid); code=str(pending_ref or "").strip()
    if not code or uid not in users:
        return None
    ref_user=next((u for u,d in users.items() if str(d.get("ref"))==code and str(u)!=uid),None)
    if not ref_user or users[uid].get("referred_by"):
        return None
    reward=referral_reward_amount()
    users[uid]["referred_by"]=ref_user; users[uid].pop("pending_ref",None)
    ledger_credit(ref_user,reward,"referral_reward",{"referred_user":uid})
    users[ref_user]["invited"]=users[ref_user].get("invited",0)+1
    save_user(uid); save_user(ref_user); log_activity(ref_user,"referral",{"referred_user":uid,"reward":reward})
    try: bot.send_message(int(ref_user),f"🎉 <b>New Referral!</b>\n\n👤 A new user joined through your link.\n💰 Earned: <b>${reward:.2f}</b>")
    except Exception: pass
    if users[ref_user]["invited"]>=50 and not users[ref_user].get("referral_50_rewarded"):
        until=grant_premium_days(ref_user,7,"referral_50_reward"); users[ref_user]["referral_50_rewarded"]=True; save_user(ref_user)
        try: bot.send_message(int(ref_user),"🎉 <b>50 REFERRALS!</b>\n\n💎 You earned 7 days Premium!")
        except Exception: pass
        send_premium_email(ref_user,"Premium Reward — 50 Referrals",0,0,until)
    return ref_user

def distribute_referral_network_commission(source_uid,amount,reason="balance_credit"):
    pct=referral_network_percent(); amount=float(amount or 0); source_uid=str(source_uid)
    if pct<=0 or amount<=0 or source_uid not in users:
        return []
    current=users[source_uid].get("referred_by"); seen={source_uid}; results=[]
    for level in range(1,11):
        if not current or str(current) in seen:
            break
        parent=str(current); seen.add(parent)
        if parent not in users:
            break
        commission=round(amount*pct/100.0,8)
        if commission<=0:
            break
        ledger_credit(parent,commission,"referral_network_commission",{"source_user":source_uid,"level":level})
        referral_commissions_col.insert_one({"source_user":source_uid,"recipient_user":parent,"level":level,"source_amount":amount,"percent":pct,"commission":commission,"reason":reason,"time":datetime.now(timezone.utc)})
        log_activity(parent,"referral_network_commission",{"source_user":source_uid,"level":level,"percent":pct,"commission":commission,"reason":reason})
        results.append((parent,level,commission)); current=users[parent].get("referred_by")
    return results

def credit_user_balance(uid,amount,reason="credit",network_commission=False):
    uid=str(uid); amount=float(amount or 0)
    if uid not in users or amount<=0: return 0.0,[]
    asset_amt=ledger_credit(uid,amount,reason)
    commissions=distribute_referral_network_commission(uid,amount,reason) if network_commission else []
    return asset_amt,commissions

def parse_seen_time(value):
    if isinstance(value,datetime): dt=value
    else:
        try: dt=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        except Exception: return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

# ================= MONGODB DATABASE FUNCTIONS =================

def load_users():
    users_dict = {}
    for user in users_col.find():
        uid = str(user["_id"])
        user_data = user.copy()
        user_data.pop("_id", None)
        users_dict[uid] = user_data
    return users_dict

def save_user(uid):
    uid_str = str(uid)
    if uid_str in users:
        data = users[uid_str].copy()
        data.pop("_id", None)
        users_col.update_one({"_id": uid_str}, {"$set": data}, upsert=True)

users = load_users()
for _uid,_u in users.items():
    _u.setdefault("currency","USD"); _u.setdefault("balance_asset", "USD"); _u.setdefault("blocked",0.0); _u.setdefault("conversion_holds",[]); _u.setdefault("portfolio",{})

def log_activity(uid, action, details=None):
    try:
        activity_col.insert_one({"user_id": str(uid), "action": action, "details": details or {}, "time": datetime.now(timezone.utc)})
    except Exception as e:
        print("Activity log error:", e)

def save_users():
    for uid in users:
        save_user(uid)

def load_withdraws():
    return list(withdraws_col.find({}, {"_id": False}))

withdraws = load_withdraws()

def migrate_pending_withdrawals_v2():
    """One-time migration from the old design where pending withdrawals
    were stored inside user.blocked. New pending withdrawals are separate.
    """
    if get_setting("pending_withdrawals_v2_migrated",False): return
    changed=set()
    for uid in list(users):
        pending=[]
        for w in withdraws:
            if str(w.get("user"))==str(uid) and str(w.get("status","pending")).lower()=="pending":
                amt=float(w.get("amount",w.get("blocked",0)) or 0)
                if str(w.get("asset") or cur_code(uid))==cur_code(uid):
                    pending.append(amt)
                else:
                    pending.append(usd_to_asset(cur_code(uid),float(w.get("amount_usd",0) or 0)))
        if pending:
            reserved=sum(pending); old_block=float(users[uid].get("blocked",0) or 0)
            # Old versions put exactly the pending reservation in blocked.
            # Remove only up to the known pending total; never create negative blocked.
            if old_block>0:
                users[uid]["blocked"]=round(max(0.0,old_block-reserved),12)
                save_user(uid); changed.add(uid)
    set_setting("pending_withdrawals_v2_migrated",True)
    if changed: print("Migrated pending withdrawals for",len(changed),"users")

migrate_pending_withdrawals_v2()

def save_withdraws():
    withdraws_col.delete_many({})
    if withdraws:
        clean_withdraws = [{**w} for w in withdraws]
        withdraws_col.insert_many(clean_withdraws)

def load_videos():
    v_data = videos_col.find_one({"_id": "stats"})
    if not v_data:
        default_data = {
            "_id": "stats",
            "total": 0,
            "feedback_enabled": False,
            "platforms": {
                "tiktok": 0,
                "youtube": 0,
                "facebook": 0,
                "pinterest": 0,
                "instagram": 0,
                "snapchat": 0,
                "twitter": 0
            },
            "users": {}
        }
        videos_col.insert_one(default_data)
        return default_data
    v_data.pop("_id", None)
    return v_data

videos_data = load_videos()

def save_videos():
    data = videos_data.copy()
    data.pop("_id", None)
    videos_col.update_one({"_id": "stats"}, {"$set": data}, upsert=True)

# ================= HELPER FUNCTIONS =================

def random_ref():
    return str(random.randint(1000000000, 9999999999))

def random_botid():
    return str(random.randint(10000000000, 99999999999))

def now_month():
    return datetime.now().month

def get_admin_ids():
    try:
        saved = get_setting("admin_ids", None)
        if isinstance(saved, list):
            ids = [int(x) for x in saved]
        else:
            ids = [int(x) for x in ADMIN_IDS]
    except Exception:
        ids = [int(x) for x in ADMIN_IDS]
    if PRIMARY_ADMIN_ID not in ids:
        ids.insert(0, PRIMARY_ADMIN_ID)
    return list(dict.fromkeys(ids))

def save_admin_ids(ids):
    ids = list(dict.fromkeys(int(x) for x in ids))
    if PRIMARY_ADMIN_ID not in ids:
        ids.insert(0, PRIMARY_ADMIN_ID)
    set_setting("admin_ids", ids)
    ADMIN_IDS[:] = ids

def is_admin(uid):
    try:
        return int(uid) in get_admin_ids()
    except Exception:
        return False

def is_quick_access(uid):
    return bool(users.get(str(uid), {}).get("quick_access", False))

def is_priority_user(uid):
    """Priority tier: Admin Quick Access > active Premium/Trial > Normal."""
    uid=str(uid)
    return is_quick_access(uid) or is_premium(uid) or _is_trial_active(uid)

def download_executor_for(uid):
    """Return the fastest queue available to this user."""
    uid=str(uid)
    if is_quick_access(uid):
        return quick_executor
    if is_priority_user(uid):
        return vip_executor
    return normal_executor

def find_user_by_botid(bid):
    for u, data in users.items():
        if data.get("bot_id") == bid:
            return u
    return None

def banned_guard(m):
    uid = str(m.from_user.id)
    if uid in users and users[uid].get("banned"):
        try:
            bot.send_message(m.chat.id, "🚫 You are banned.")
        except:
            pass
        return True
    return False

def bot_locked_guard(message):
    global BOT_LOCKED, LOCK_MESSAGE
    if BOT_LOCKED and not is_admin(message.from_user.id):
        try:
            bot.send_message(message.chat.id, LOCK_MESSAGE)
        except:
            pass
        return True
    return False

def send_html_email(to_email, subject, html_body):
    if not RESEND_API_KEY:
        print("❌ RESEND_API_KEY is not set in environment variables.")
        return False
    
    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "from": SENDER_EMAIL,
        "to": [to_email],
        "subject": subject,
        "html": html_body
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code in [200, 201]:
            return True
        else:
            print(f"RESEND API ERROR: {response.text}")
            return False
    except Exception as e:
        print(f"EMAIL API ERROR: {e}")
        return False

# ================= OTP PROVIDERS =================

def send_d7_sms(phone_number, text):
    """Send a managed OTP through D7 Verify API.

    Returns (ok, detail, otp_id). D7 generates and validates the OTP itself;
    the bot never stores the plaintext OTP when this provider succeeds.
    """
    if not D7_TOKEN:
        return False, "D7_TOKEN is not configured", None
    headers = {
        "Authorization": f"Bearer {D7_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "originator": os.getenv("D7_ORIGINATOR", "SignOTP"),
        "recipient": phone_number,
        "content": "Your Downloader Bot Verification Code is: {}",
        "expiry": 600,
        "data_coding": "text",
        "channel": "SMS",
        "otp_code_length": 6,
        "otp_type": "numeric",
        "retry_delay": 60,
        "retry_count": 5,
    }
    try:
        r = requests.post(D7_VERIFY_SEND_URL, json=payload, headers=headers, timeout=30)
        try: body = r.json()
        except Exception: body = {"raw": r.text}
        if r.status_code in (200, 201, 202):
            otp_id = body.get("otp_id") or body.get("id") or body.get("request_id")
            if otp_id:
                return True, body, str(otp_id)
        return False, f"HTTP {r.status_code}: {body}", None
    except Exception as e:
        return False, str(e), None

def resend_d7_sms(otp_id):
    if not D7_TOKEN or not otp_id:
        return False, "Missing D7 token or otp_id", None
    headers = {"Authorization": f"Bearer {D7_TOKEN}", "Content-Type": "application/json", "Accept": "application/json"}
    try:
        r=requests.post(D7_VERIFY_RESEND_URL, json={"otp_id": str(otp_id)}, headers=headers, timeout=30)
        try: body=r.json()
        except Exception: body={"raw":r.text}
        if r.status_code in (200,201,202):
            return True, body, str(body.get("otp_id") or otp_id)
        return False, f"HTTP {r.status_code}: {body}", None
    except Exception as e:
        return False, str(e), None

def d7_otp_status(otp_id):
    if not D7_TOKEN or not otp_id:
        return False,"Missing D7 token or otp_id"
    headers={"Authorization":f"Bearer {D7_TOKEN}","Accept":"application/json"}
    try:
        r=requests.get(f"{D7_VERIFY_STATUS_URL}/{urllib.parse.quote(str(otp_id),safe='')}",headers=headers,timeout=20)
        try: body=r.json()
        except Exception: body={"raw":r.text}
        return r.status_code==200,body
    except Exception as e:
        return False,str(e)

def verify_d7_sms(otp_id, code):
    if not D7_TOKEN or not otp_id:
        return False, "Missing D7 token or otp_id"
    headers = {"Authorization": f"Bearer {D7_TOKEN}", "Content-Type": "application/json", "Accept": "application/json"}
    try:
        r=requests.post(D7_VERIFY_CHECK_URL, json={"otp_id": str(otp_id), "otp_code": str(code)}, headers=headers, timeout=30)
        try: body=r.json()
        except Exception: body={"raw":r.text}
        return r.status_code == 200 and str(body.get("status","")).upper() in {"APPROVED","SUCCESS","VERIFIED"}, body
    except Exception as e:
        return False, str(e)

def _waforge_request_urls(primary, legacy):
    return list(dict.fromkeys([primary, legacy]))


def _waforge_headers(api_key_header="Authorization"):
    """Build auth headers while supporting WaForge deployments that use Bearer or X-API-Key."""
    key = WAFORGE_API_KEY
    common = {"Content-Type": "application/json", "Accept": "application/json"}
    if api_key_header.lower() in {"x-api-key", "x_api_key", "api-key", "api_key"}:
        common["X-API-Key"] = key
    elif api_key_header.lower() == "authorization-raw":
        common["Authorization"] = key
    else:
        common["Authorization"] = f"Bearer {key}"
    return common


def _waforge_success(body, status_code):
    if status_code not in (200, 201, 202):
        return False
    if not isinstance(body, dict):
        return True
    status = str(body.get("status") or body.get("message") or "").lower()
    # A 2xx response from the provider is normally a successful send/verify unless
    # it explicitly reports failure.
    if body.get("success") is False or body.get("verified") is False or body.get("sent") is False:
        return False
    if any(word in status for word in ("error", "failed", "invalid", "denied")):
        return False
    return True


def _waforge_response_id(body):
    if not isinstance(body, dict):
        return None
    return body.get("id") or body.get("request_id") or body.get("requestId") or body.get("uuid") or body.get("session_id") or body.get("sessionId")


def send_waforge_whatsapp(phone_number, user_id):
    """Send WhatsApp OTP using WaForge's current documented API contract."""
    if not WAFORGE_API_KEY:
        return False, "WAFORGE_API_KEY is not configured", None

    phone = re.sub(r"[\s().-]", "", str(phone_number or "").strip())
    if not re.fullmatch(r"\+[1-9]\d{7,14}", phone):
        return False, "Invalid international WhatsApp number", None

    # Current WaForge contract: POST /api/otp/send with Bearer wf_sk and {to}.
    attempts = [
        (WAFORGE_OTP_SEND_URL, {"to": phone}, "Authorization"),
        (WAFORGE_OTP_SEND_URL, {"to": phone}, "X-API-Key"),
    ]
    # Compatibility attempts for older account/API deployments.
    for url in _waforge_request_urls(WAFORGE_OTP_SEND_URL, WAFORGE_OTP_SEND_LEGACY_URL):
        for payload in ({"to": phone}, {"phone": phone}):
            for header_mode in (WAFORGE_API_KEY_HEADER, "Authorization", "X-API-Key"):
                item=(url,payload,header_mode)
                if item not in attempts:
                    attempts.append(item)

    last = None
    for url, payload, header_mode in attempts:
        try:
            r = requests.post(url, json=payload, headers=_waforge_headers(header_mode), timeout=30)
            try:
                body = r.json()
            except Exception:
                body = {"raw": r.text[:1000]}
            last = (r.status_code, body, url, header_mode, payload)
            if _waforge_success(body, r.status_code):
                return True, body, _waforge_response_id(body)
        except Exception as e:
            last = ("EXCEPTION", str(e), url, header_mode, payload)

    print("WaForge send failure:", repr(last))
    return False, f"WaForge OTP send failed: {last}", None

def verify_waforge_whatsapp(phone_number, code, request_id=None):
    """Verify against the WaForge OTP session. Never uses D7 for WhatsApp."""
    if not WAFORGE_API_KEY:
        return False, "WAFORGE_API_KEY is not configured"

    endpoints = _waforge_request_urls(WAFORGE_OTP_VERIFY_URL, WAFORGE_OTP_VERIFY_LEGACY_URL)
    payloads = []
    p1 = {"to": phone_number, "code": str(code)}
    if request_id:
        p1["request_id"] = str(request_id)
    payloads.append(p1)
    p2 = {"phone": phone_number, "code": str(code)}
    if request_id:
        p2["request_id"] = str(request_id)
    payloads.append(p2)

    last = None
    for url in endpoints:
        for payload in payloads:
            header_modes = [WAFORGE_API_KEY_HEADER]
            if WAFORGE_API_KEY_HEADER.lower() == "authorization":
                header_modes.append("X-API-Key")
            for header_mode in header_modes:
                try:
                    r = requests.post(url, json=payload, headers=_waforge_headers(header_mode), timeout=30)
                    try:
                        body = r.json()
                    except Exception:
                        body = {"raw": r.text}
                    last = (r.status_code, body, url, header_mode, payload)
                    status = str(body.get("status") or "").lower() if isinstance(body, dict) else ""
                    ok = (
                        r.status_code in (200, 201, 202)
                        and isinstance(body, dict)
                        and (
                            body.get("verified") is True
                            or body.get("success") is True
                            or body.get("matched") is True
                            or status in {"verified", "approved", "success"}
                        )
                    )
                    if ok:
                        return True, body
                    if r.status_code in (401, 403):
                        continue
                    if r.status_code in (404, 405, 415, 422):
                        break
                except Exception as e:
                    last = (None, str(e), url, header_mode, payload)
                    break
    return False, last


def expire_whatsapp_session(uid, created_at):
    """Expire one WhatsApp OTP session after exactly 5 minutes."""
    time.sleep(WHATSAPP_OTP_TTL)
    data = whatsapp_verify_pending.get(str(uid))
    if not data:
        return
    # Do not expire a newer/resend session.
    if data.get("time") != created_at:
        return
    whatsapp_verify_pending.pop(str(uid), None)
    try:
        bot.send_message(
            int(uid),
            "⏰ <b>This code has expired.</b>\n\n"
            "The WhatsApp verification code is valid for 5 minutes. "
            "Please start verification again or request a new code.",
        )
    except Exception:
        pass


def whatsapp_otp_keyboard():
    """Telegram controls for an active WhatsApp OTP session."""
    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("🔄 Resend WhatsApp", callback_data="resend_whatsapp_code"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process"),
    )
    return kb

def extract_url(text):
    if not text:
        return None
    match = re.search(r'(https?://[^\s]+)', text)
    return match.group(0) if match else None

# ================= MENUS =================

def user_menu(show_admin=False):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💰 BALANCE", "💸 WITHDRAWAL")
    kb.add("👥 REFERRAL", "🆔 GET ID")
    kb.add("💎 PREMIUM", "👤 Profile")
    kb.add("☎️ CUSTOMER", "🤖CUSTOMER AI")
    if promo_user_enabled():
        kb.add("🎟 PROMO CODE")
    if show_admin:
        kb.add("👑 ADMIN PANEL")
    return kb

def admin_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📊 STATS", "📢 BROADCAST")
    kb.add("⚡ QUICK ACCESS", "👥 SEE LIST")
    kb.add("➕ ADD BALANCE", "➖ REMOVE MONEY")
    kb.add("🚫 BAN USER MANUAL", "💳 WITHDRAWAL CHECK")
    kb.add("💰 UNBLOCK MONEY", "🔍 RAADI")
    kb.add("⏳ HOLD CHECK", "✅ RELEASE HOLD")
    kb.add("📜 HOLD HISTORY")
    kb.add("🔥 UN BAN-USER", "📌 POST CHANNEL")
    kb.add("🔎 SEARCH USER", "📢 ADD ADS")
    kb.add("🗑 DELETE ADS", "✅ VERIFY ON")
    kb.add("❌ VERIFY OFF", "CHANNEL POST")
    kb.add("🔒 LOCK BOT")
    kb.add("🔓 UNLOCK BOT", "❌ CLOSE WINDOWS")
    kb.add("CLOSE CHANNEL POST", "📢 BROADCAST MEDIA")
    kb.add("SEND PAY", "📥 IMPORT USERS")
    kb.add("🔗 GET REFERRAL CODE", "📊 Feedback Stats")
    kb.add("🟢 Open Feedback", "🔴 Close Feedback")
    kb.add("🗑️ Reset All Feedbacks", "🔓 OPEN 30 MIN")
    kb.add("🟢 Open add group", "🔴 Close add group")
    kb.add("🟢 Open add channel", "🔴 Close add channel")
    kb.add("🟢 Open mp3 Cover", "🔴 Close mp3 Cover")
    kb.add("📢 REFERRAL BROADCAST")
    kb.add("📣 Send all G/CH")
    kb.add("⚡ AUTO SONG SEARCH ON", "⛔ AUTO SONG SEARCH OFF")
    kb.add("📉 CHANGE MINIMUM", "➕ ADD FEE")
    kb.add("➕ ADD LOW FEE", "🎁 GIFT ALL")
    kb.add("🗑️ REMOVE ALL")
    kb.add("📢 Send Email All")
    kb.add("⏱️ FREE MAX MIN", "⏱️ PREMIUM MAX MIN")
    kb.add("📦 FREE MAX MB", "📦 TRIAL MAX MB")
    kb.add("📦 PREMIUM MAX MB", "⚙️ DOWNLOAD LIMITS")
    kb.add("▶️ YOUTUBE FREE ACCESS", "📺 FREE YOUTUBE MB")
    kb.add("📺 PREMIUM YOUTUBE MB", "📋 YOUTUBE LIMITS")
    kb.add("📸 INSTAGRAM API", "📸 INSTAGRAM STATUS")
    kb.add("🛰️ COBALT STATUS")
    kb.add("✅ Verified Users", "🏷️ Sticker")
    kb.add("Reveral Prices", "Delete Pay", "Open Pay rev")
    kb.add("Send verify")
    kb.add("🟢 Open SMS", "🔴 CLOSE SMS")
    kb.add("🟢 OPEN VIA WHATSAPP", "🔴 CLOSE VIA WHATSAPP")
    kb.add("♻️ Reset all Verify")
    # Premium administration
    kb.add("💎 PREMIUM PANEL", "💰 PREMIUM PRICES")
    kb.add("🔓 OPEN PREMIUM", "🔒 CLOSE PREMIUM")
    kb.add("🎁 GIVE PREMIUM ALL", "🎁 TRIAL PREMIUM")
    kb.add("🎁 OPEN TRIAL DAYS")
    kb.add("👑 PREMIUM USERS", "💵 REFERRAL REWARD")
    kb.add("🔗 NETWORK REFERRAL %", "👥 AVAILABLE USERS")
    kb.add("⭐ RATE BOT", "📊 RATE STATS")
    kb.add("🗑 DELETE DATABASE USER", "📨 SEND LANGUAGE")
    kb.add("📨 SEND LANGUAGE", "🌍 LANGUAGE STATS")
    kb.add("⚥ SEND GENDER", "📊 GENDER STATS")
    kb.add("🏙 SEND CITY", "📊 CITY STATS")
    kb.add("💱 CHANGE MONEY", "⭐ STARS SETTINGS")
    kb.add("👥 CURRENCY USERS", "📊 CURRENCY STATS")
    kb.add("📊 MARKET STATUS")
    kb.add("➕ ADD NEW ADMIN", "➖ REMOVE ADMIN")
    kb.add("🔒 CLOSE ALL BALANCE", "🔓 OPEN ALL BALANCE")
    kb.add("🔓 OPEN PERSON BALANCE", "🗑 REMOVE ALL BALANCE")
    kb.add("🔐 PREMIUM VERIFY ON", "🔓 PREMIUM VERIFY OFF")
    kb.add("🤖 CUSTOMER AI")
    kb.add("👑 ADMIN LIST", "💰 SEE BALANCE")
    kb.add("📊 SEE ALL BALANCE", "💼 PORTFOLIO STATS")
    kb.add("➕ ADD CUSTOMER", "💱 MIN CHANGE CURRENCY")
    kb.add("🟢 OPEN CRYPTO", "🔴 CLOSE CRYPTO")
    kb.add("🟢 OPEN HOLD", "🔴 CLOSE HOLD")
    kb.add("💸 CRYPTO FEE", "⛽ GAS FEE")
    kb.add("💰 CRYPTO MIN DEPOSIT")
    kb.add("📈 CRYPTO FEE STATS")
    kb.add("🎟 PROMO CODES", "🔥 STREAK SYSTEM")
    kb.add("✏️ EDIT START MESSAGE")
    kb.add("🔙 BACK MAIN MENU")
    return kb

def localized_user_menu(uid):
    uid=str(uid); lang=lang_of(uid); d=MAIN_LABELS.get(lang,MAIN_LABELS["en"])
    kb=ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(d["balance"],d["withdraw"])
    kb.add(d["ref"],d["id"])
    kb.add(d["premium"],d["profile"])
    kb.add(d["topup"],d.get("currency","💱 CHANGE CURRENCY"))
    if trial_available(uid):
        kb.add(d["trial"])
    kb.add(d["customer"],d["ai"])
    if promo_user_enabled(): kb.add(d.get("promo","🎟 PROMO CODE"))
    if is_admin(uid): kb.add("👑 ADMIN PANEL")
    return kb

@bot.callback_query_handler(func=lambda c: c.data.startswith("setlang:"))
def setlang_callback(call):
    uid=str(call.from_user.id); code=call.data.split(":",1)[1]
    if code not in LANGUAGES: return
    users[uid]["language"]=code; pending=users[uid].pop("pending_ref",None); save_user(uid)
    bot.answer_callback_query(call.id,"✅ Language saved")
    try: bot.edit_message_text(f"✅ {LANGUAGES[code]['name']} selected.",call.message.chat.id,call.message.message_id)
    except Exception: pass
    if pending:
        process_referral_signup(uid,pending)
    check_membership(call.from_user.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("change_lang:"))
def change_lang_callback(call):
    uid=str(call.from_user.id); code=call.data.split(":",1)[1]
    if code in LANGUAGES:
        users.setdefault(uid,{})["language"]=code; save_user(uid); bot.answer_callback_query(call.id,"✅")
        confirmations={
            "en":"🌍 <b>Language updated successfully.</b>","so":"🌍 <b>Luqadda si guul leh ayaa loo beddelay.</b>",
            "am":"🌍 <b>ቋንቋ በተሳካ ሁኔታ ተቀይሯል።</b>","om":"🌍 <b>Afaan milkaa'inaan jijjiirameera.</b>",
            "ar":"🌍 <b>تم تحديث اللغة بنجاح.</b>","fr":"🌍 <b>Langue mise à jour.</b>",
            "es":"🌍 <b>Idioma actualizado.</b>","de":"🌍 <b>Sprache erfolgreich aktualisiert.</b>",
            "pt":"🌍 <b>Idioma atualizado.</b>","tr":"🌍 <b>Dil başarıyla güncellendi.</b>",
            "hi":"🌍 <b>भाषा सफलतापूर्वक अपडेट हो गई।</b>","id":"🌍 <b>Bahasa berhasil diperbarui.</b>",
            "ja":"🌍 <b>言語を更新しました。</b>","ko":"🌍 <b>언어가 업데이트되었습니다.</b>","zh":"🌍 <b>语言已成功更新。</b>"
        }
        bot.send_message(call.message.chat.id,confirmations.get(code,confirmations["en"]),reply_markup=localized_user_menu(uid),parse_mode="HTML")

def back_to_main_menu(m):
    uid = str(m.from_user.id)
    try:
        bot.send_message(
            m.chat.id,
            "🔙 Returning to main menu",
            reply_markup=localized_user_menu(uid)
        )
    except:
        pass

@bot.message_handler(func=lambda m: m.text == "🔙 BACK MAIN MENU")
def back_button_handler(m):
    back_to_main_menu(m)

@bot.message_handler(func=lambda m: m.text == "🎟 PROMO CODE")
def promo_user_menu(m):
    uid=str(m.from_user.id)
    touch_user(uid)
    if bot_locked_guard(m) or banned_guard(m): return
    promos=_active_promo_codes()
    if not promos:
        bot.send_message(m.chat.id,"🎟 <b>PROMO CODE</b>\n\nNo promo code is open right now.",reply_markup=localized_user_menu(uid))
        return
    kb=InlineKeyboardMarkup(row_width=1)
    for x in promos[:20]:
        label=str(x.get("code"))
        kb.add(InlineKeyboardButton(f"🎁 {label} — OPEN",callback_data=f"promo_open:{label}"))
    bot.send_message(m.chat.id,"🎟 <b>AVAILABLE PROMO CODES</b>\n\nTap <b>OPEN</b> to view and claim a promo.",reply_markup=kb)

# ================= PROMO CODE SYSTEM =================

def _promo_collection():
    return db1["promo_codes"]

def promo_user_enabled():
    return bool(get_setting("promo_system_enabled", False)) and bool(_active_promo_codes())

def _promo_dt(value):
    if not value: return None
    try:
        dt=value if isinstance(value,datetime) else datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception: return None

def _active_promo_codes():
    now=datetime.now(timezone.utc)
    rows=[]
    try:
        for x in _promo_collection().find({"enabled":True}).sort("created_at",-1):
            exp=_promo_dt(x.get("expires_at"))
            if exp and exp<=now: continue
            max_uses=int(x.get("max_uses",0) or 0); used=int(x.get("used_count",0) or 0)
            if max_uses>0 and used>=max_uses: continue
            rows.append(x)
    except Exception as e: print("Promo load error:",repr(e))
    return rows

def _promo_get(code):
    return _promo_collection().find_one({"_id":str(code).upper().strip()})

def _promo_format(x):
    code=str(x.get("code") or x.get("_id") or "")
    bal=float(x.get("balance_reward",0) or 0); pd=int(x.get("premium_days",0) or 0)
    maxu=int(x.get("max_uses",0) or 0); used=int(x.get("used_count",0) or 0)
    exp=_promo_dt(x.get("expires_at")); exp_txt=exp.strftime("%Y-%m-%d %H:%M UTC") if exp else "No expiry"
    return (f"🎟 <b>{html.escape(code)}</b>\n\n"
            f"💰 Balance reward: <b>${bal:.2f}</b>\n"
            f"💎 Premium reward: <b>{pd} day(s)</b>\n"
            f"👥 Uses: <b>{used}/{maxu if maxu>0 else '∞'}</b>\n"
            f"⏰ Expiry: <b>{exp_txt}</b>")

def _promo_claim(uid, code):
    uid=str(uid); code=str(code).upper().strip()
    if not bool(get_setting("promo_system_enabled",False)):
        return False,"❌ Promo system is currently closed."
    x=_promo_get(code)
    if not x or not x.get("enabled",False): return False,"❌ This promo code is closed or invalid."
    now=datetime.now(timezone.utc); exp=_promo_dt(x.get("expires_at"))
    if exp and exp<=now: return False,"❌ This promo code has expired."
    maxu=int(x.get("max_uses",0) or 0); used=int(x.get("used_count",0) or 0)
    if maxu>0 and used>=maxu: return False,"❌ This promo code has reached its usage limit."
    per=int(x.get("per_user_limit",1) or 1)
    used_by= x.get("used_by") or {}
    count=int(used_by.get(uid,0) or 0) if isinstance(used_by,dict) else 0
    if count>=per: return False,"❌ You have already used this promo code."
    if bool(x.get("new_users_only",False)):
        joined=_promo_dt(users.get(uid,{}).get("created_at"))
        if not joined:
            try: joined=datetime.strptime(str(users.get(uid,{}).get("joined_date")),"%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception: joined=now-timedelta(days=999)
        if now-joined>timedelta(hours=24): return False,"❌ This promo is for new users only."
    bal=float(x.get("balance_reward",0) or 0); pd=int(x.get("premium_days",0) or 0)
    # Atomic usage reservation prevents two fast taps from both winning the last use.
    filt={"_id":code,"enabled":True}
    if maxu>0: filt["used_count"]={"$lt":maxu}
    if isinstance(used_by,dict): filt[f"used_by.{uid}"]={"$lt":per}
    upd={"$inc":{"used_count":1},"$set":{f"used_by.{uid}":count+1,"last_used_at":now}}
    res=_promo_collection().update_one(filt,upd)
    if res.modified_count!=1: return False,"❌ Promo code is no longer available."
    if bal>0: ledger_credit(uid,bal,"promo_code",{"code":code})
    until=None
    if pd>0: until=grant_premium_days(uid,pd,"promo_code")
    log_activity(uid,"promo_claimed",{"code":code,"balance_reward":bal,"premium_days":pd})
    reward=[]
    if bal>0: reward.append(f"💰 +${bal:.2f}")
    if pd>0: reward.append(f"💎 +{pd} Premium day(s)")
    return True,"🎉 <b>PROMO ACTIVATED!</b>\n\n🎟 Code: <code>"+html.escape(code)+"</code>\n"+"\n".join(reward)+"\n\n❤️ Enjoy your reward!"

@bot.callback_query_handler(func=lambda c:c.data.startswith("promo_open:"))
def promo_open_callback(call):
    code=call.data.split(":",1)[1].strip().upper(); uid=str(call.from_user.id)
    if bot_locked_guard(call.message) or banned_guard(call.message):
        try: bot.answer_callback_query(call.id,"Unavailable",show_alert=True)
        except: pass
        return
    ok,msg=_promo_claim(uid,code)
    try: bot.answer_callback_query(call.id,msg.replace("<b>","").replace("</b>","").replace("<code>","").replace("</code>","")[:190],show_alert=True)
    except Exception: pass
    try: bot.edit_message_text("🎟 <b>PROMO CODE</b>\n\n" + ("✅ Promo opened and claimed successfully." if ok else html.escape(msg)),call.message.chat.id,call.message.message_id,parse_mode="HTML")
    except Exception: pass
    if ok:
        try: bot.send_message(call.message.chat.id,msg,parse_mode="HTML",reply_markup=localized_user_menu(uid))
        except: pass

def _promo_admin_menu():
    kb=InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("➕ CREATE",callback_data="promo_admin:create"),InlineKeyboardButton("📋 LIST",callback_data="promo_admin:list"))
    kb.add(InlineKeyboardButton("📢 SEND ALL",callback_data="promo_admin:send"),InlineKeyboardButton("🟢 OPEN SYSTEM",callback_data="promo_admin:open"))
    kb.add(InlineKeyboardButton("🔴 CLOSE SYSTEM",callback_data="promo_admin:close"),InlineKeyboardButton("📊 STATS",callback_data="promo_admin:stats"))
    kb.add(InlineKeyboardButton("✏️ EDIT",callback_data="promo_admin:edit"),InlineKeyboardButton("🗑 DELETE",callback_data="promo_admin:delete"))
    return kb

@bot.message_handler(func=lambda m: m.text=="🎟 PROMO CODES")
def promo_admin_start(m):
    if not is_admin(m.from_user.id): return
    bot.send_message(m.chat.id,"🎟 <b>PROMO CODE CONTROL</b>\n\nFull control: create, edit, open/close, send to all users, delete and statistics.",reply_markup=_promo_admin_menu(),parse_mode="HTML")

@bot.callback_query_handler(func=lambda c:c.data.startswith("promo_admin:"))
def promo_admin_callback(call):
    if not is_admin(call.from_user.id): return
    action=call.data.split(":",1)[1]
    if action=="open":
        set_setting("promo_system_enabled",True); _refresh_all_user_menus("🔄 Menu updated.")
        bot.answer_callback_query(call.id,"Promo system OPEN")
    elif action=="close":
        set_setting("promo_system_enabled",False); _refresh_all_user_menus("🔄 Menu updated.")
        bot.answer_callback_query(call.id,"Promo system CLOSED")
    elif action=="list":
        rows=list(_promo_collection().find({}).sort("created_at",-1).limit(50))
        text="🎟 <b>PROMO CODES</b>\n\n"+ ("\n\n".join(_promo_format(x) for x in rows) if rows else "No promo codes yet.")
        bot.send_message(call.message.chat.id,text,parse_mode="HTML")
    elif action=="stats":
        rows=list(_promo_collection().find({}))
        total=sum(int(x.get("used_count",0) or 0) for x in rows); open_n=sum(1 for x in rows if x.get("enabled"))
        bot.send_message(call.message.chat.id,f"📊 <b>PROMO STATS</b>\n\nCodes: <b>{len(rows)}</b>\nOpen codes: <b>{open_n}</b>\nTotal claims: <b>{total}</b>",parse_mode="HTML")
    elif action=="create":
        msg=bot.send_message(call.message.chat.id,"➕ <b>CREATE PROMO</b>\n\nSend:\n<code>CODE | balance_usd | premium_days | max_uses | per_user_limit | hours | new_users_only</code>\n\nExample:\n<code>WELCOME50 | 0.50 | 3 | 100 | 1 | 72 | no</code>\n\nUse <b>0</b> for unlimited max uses/hours.",parse_mode="HTML")
        bot.register_next_step_handler(msg,promo_create_process)
    elif action=="send":
        msg=bot.send_message(call.message.chat.id,"📢 <b>SEND PROMO TO ALL</b>\n\nSend the exact promo code to broadcast. The message will show <b>New Promo Code For Free</b> with an inline <b>OPEN</b> button.",parse_mode="HTML")
        bot.register_next_step_handler(msg,promo_send_process)
    elif action=="edit":
        msg=bot.send_message(call.message.chat.id,"✏️ Send: <code>CODE | balance_usd | premium_days | max_uses | per_user_limit | hours | new_users_only | on/off</code>",parse_mode="HTML")
        bot.register_next_step_handler(msg,promo_edit_process)
    elif action=="delete":
        msg=bot.send_message(call.message.chat.id,"🗑 Send the promo code to delete:")
        bot.register_next_step_handler(msg,promo_delete_process)

def promo_create_process(m):
    if not is_admin(m.from_user.id): return
    try:
        parts=[x.strip() for x in (m.text or "").split("|")]
        if len(parts)<7: raise ValueError("Use 7 fields separated by |")
        code=parts[0].upper();
        if not re.fullmatch(r"[A-Z0-9_-]{3,32}",code): raise ValueError("Code must be 3-32 characters")
        bal=float(parts[1]); pd=int(parts[2]); maxu=int(parts[3]); per=int(parts[4]); hours=int(parts[5]); newonly=parts[6].lower() in {"yes","y","true","1","on"}
        if bal<0 or pd<0 or maxu<0 or per<1 or hours<0: raise ValueError("Invalid reward/limit")
        now=datetime.now(timezone.utc); exp=(now+timedelta(hours=hours)) if hours>0 else None
        doc={"_id":code,"code":code,"balance_reward":bal,"premium_days":pd,"max_uses":maxu,"per_user_limit":per,"new_users_only":newonly,"enabled":True,"used_count":0,"used_by":{},"created_at":now,"expires_at":exp,"created_by":str(m.from_user.id)}
        _promo_collection().replace_one({"_id":code},doc,upsert=True); set_setting("promo_system_enabled",True); _refresh_all_user_menus("🔄 New promo code is available.")
        bot.send_message(m.chat.id,"✅ Promo created and opened. Use SEND ALL to announce it.",reply_markup=_promo_admin_menu())
    except Exception as e: bot.send_message(m.chat.id,f"❌ {html.escape(str(e))}")

def promo_send_process(m):
    if not is_admin(m.from_user.id): return
    code=(m.text or "").strip().upper(); x=_promo_get(code)
    if not x: bot.send_message(m.chat.id,"❌ Promo code not found."); return
    kb=InlineKeyboardMarkup(); kb.add(InlineKeyboardButton("OPEN",callback_data=f"promo_open:{code}"))
    text=("🎁 <b>New Promo Code For Free</b>\n\n"
          "🎟 A new free promo reward is available!\n\n"
          "Tap <b>OPEN</b> below to view and claim it.")
    sent=0
    for uid in list(users):
        try: bot.send_message(int(uid),text,reply_markup=kb,parse_mode="HTML"); sent+=1
        except: pass
    bot.send_message(m.chat.id,f"✅ Promo broadcast sent to <b>{sent}</b> users.",parse_mode="HTML")

def promo_edit_process(m):
    if not is_admin(m.from_user.id): return
    try:
        parts=[x.strip() for x in (m.text or "").split("|")]
        if len(parts)<8: raise ValueError("8 fields required")
        code=parts[0].upper(); old=_promo_get(code)
        if not old: raise ValueError("Promo not found")
        bal=float(parts[1]); pd=int(parts[2]); maxu=int(parts[3]); per=int(parts[4]); hours=int(parts[5]); newonly=parts[6].lower() in {"yes","y","true","1","on"}; enabled=parts[7].lower() in {"on","yes","true","1","open"}
        exp=(datetime.now(timezone.utc)+timedelta(hours=hours)) if hours>0 else None
        _promo_collection().update_one({"_id":code},{"$set":{"balance_reward":bal,"premium_days":pd,"max_uses":maxu,"per_user_limit":per,"new_users_only":newonly,"enabled":enabled,"expires_at":exp}})
        bot.send_message(m.chat.id,"✅ Promo updated.",reply_markup=_promo_admin_menu())
    except Exception as e: bot.send_message(m.chat.id,f"❌ {html.escape(str(e))}")

def promo_delete_process(m):
    if not is_admin(m.from_user.id): return
    code=(m.text or "").strip().upper(); res=_promo_collection().delete_one({"_id":code})
    bot.send_message(m.chat.id,"✅ Promo deleted." if res.deleted_count else "❌ Promo not found.",reply_markup=_promo_admin_menu())

def _refresh_all_user_menus(prefix="🔄 Menu updated."):
    for uid in list(users):
        try: bot.send_message(int(uid),prefix,reply_markup=localized_user_menu(uid))
        except: pass

# ================= STREAK SYSTEM =================
STREAK_WINDOW_HOURS=26

def streak_enabled(): return bool(get_setting("streak_system_enabled",False))
def streak_campaign_version(): return int(get_setting("streak_campaign_version",0) or 0)
def streak_reward_balance(): return max(0.0,float(get_setting("streak_reward_balance",0.10) or 0))
def streak_reward_premium_days(): return max(0,int(get_setting("streak_reward_premium_days",0) or 0))
def streak_milestone_every(): return max(1,int(get_setting("streak_milestone_every",7) or 7))
def streak_milestone_balance(): return max(0.0,float(get_setting("streak_milestone_balance",0.50) or 0))
def streak_milestone_premium_days(): return max(0,int(get_setting("streak_milestone_premium_days",1) or 0))

def _streak_dt(v): return _promo_dt(v)
def streak_user_active(uid): return bool(users.get(str(uid),{}).get("streak_active",False)) and users.get(str(uid),{}).get("streak_campaign_version")==streak_campaign_version()

def _streak_touch(uid):
    uid=str(uid)
    u=users.get(uid)
    if not u or not streak_user_active(uid): return
    now=datetime.now(timezone.utc); last=_streak_dt(u.get("streak_last_activity_at")); due=_streak_dt(u.get("streak_next_reward_at"))
    if last and now-last>=timedelta(hours=STREAK_WINDOW_HOURS):
        u["streak_active"]=False; u["streak_broken_at"]=now.isoformat(); save_user(uid)
        return
    u["streak_last_activity_at"]=now.isoformat();
    if due and now>=due:
        count=int(u.get("streak_count",0) or 0)+1; u["streak_count"]=count; u["streak_next_reward_at"]=(now+timedelta(hours=STREAK_WINDOW_HOURS)).isoformat(); u["streak_reminder_10_sent"]=False; u["streak_reminder_5_sent"]=False
        bal=streak_reward_balance(); pd=streak_reward_premium_days()
        if bal>0: ledger_credit(uid,bal,"streak_reward",{"streak":count})
        if pd>0: grant_premium_days(uid,pd,"streak_reward")
        mb=mp=0
        if count%streak_milestone_every()==0:
            mb=streak_milestone_balance(); mp=streak_milestone_premium_days()
            if mb>0: ledger_credit(uid,mb,"streak_milestone",{"streak":count})
            if mp>0: grant_premium_days(uid,mp,"streak_milestone")
        save_user(uid)
        reward=[]
        if bal>0: reward.append(f"💰 +${bal:.2f}")
        if pd>0: reward.append(f"💎 +{pd} Premium day(s)")
        if mb>0: reward.append(f"🏆 Milestone +${mb:.2f}")
        if mp>0: reward.append(f"🏆 Milestone +{mp} Premium day(s)")
        try: bot.send_message(int(uid),f"🔥 <b>STREAK DAY {count}!</b>\n\n"+("\n".join(reward) if reward else "🎉 Streak continued!")+f"\n\n⏳ Next reward window: 26 hours.")
        except: pass
    else:
        u["streak_last_activity_at"]=now.isoformat(); save_user(uid)

def _streak_remaining(uid):
    d=_streak_dt(users.get(str(uid),{}).get("streak_last_activity_at"));
    return max(0.0,(d+timedelta(hours=STREAK_WINDOW_HOURS)-datetime.now(timezone.utc)).total_seconds()) if d else 0

def streak_broadcast_text():
    bal=streak_reward_balance(); pd=streak_reward_premium_days(); me=streak_milestone_every(); mb=streak_milestone_balance(); mp=streak_milestone_premium_days()
    rewards=[]
    if bal>0: rewards.append(f"💰 ${bal:.2f} balance every 26 hours")
    if pd>0: rewards.append(f"💎 {pd} Premium day(s)")
    if mb>0 or mp>0: rewards.append(f"🏆 Milestone every {me} days: ${mb:.2f} + {mp} Premium day(s)")
    return ("🔥 <b>STREAK SYSTEM</b> 🔥\n\n"
            "Use the bot regularly and keep your streak alive!\n\n"
            + "\n".join(rewards) + "\n\n"
            "⏳ You have <b>26 hours</b> between activities.\n"
            "⚠️ If you pass 26 hours without using the bot, your streak breaks.\n\n"
            "Tap <b>START NOW</b> to activate your streak.")

def _streak_start(uid):
    uid=str(uid); now=datetime.now(timezone.utc); ver=streak_campaign_version()
    users[uid]["streak_active"]=True; users[uid]["streak_campaign_version"]=ver; users[uid]["streak_count"]=0; users[uid]["streak_started_at"]=now.isoformat(); users[uid]["streak_last_activity_at"]=now.isoformat(); users[uid]["streak_next_reward_at"]=(now+timedelta(hours=STREAK_WINDOW_HOURS)).isoformat(); users[uid]["streak_reminder_10_sent"]=False; users[uid]["streak_reminder_5_sent"]=False; users[uid].pop("streak_broken_at",None); save_user(uid)

@bot.callback_query_handler(func=lambda c:c.data=="streak_start")
def streak_start_callback(call):
    uid=str(call.from_user.id)
    if not streak_enabled(): bot.answer_callback_query(call.id,"Streak is currently closed.",show_alert=True); return
    _streak_start(uid); bot.answer_callback_query(call.id,"🔥 Streak started!")
    try: bot.delete_message(call.message.chat.id,call.message.message_id)
    except: pass
    bot.send_message(call.message.chat.id,"🔥 <b>STREAK STARTED!</b>\n\nDay <b>0</b> is active. Use the bot before 26 hours to keep it alive and earn your first reward.",reply_markup=localized_user_menu(uid),parse_mode="HTML")

def streak_worker():
    while True:
        try:
            if streak_enabled():
                now=datetime.now(timezone.utc)
                for uid,u in list(users.items()):
                    if not streak_user_active(uid): continue
                    last=_streak_dt(u.get("streak_last_activity_at"))
                    if not last: continue
                    rem=(last+timedelta(hours=STREAK_WINDOW_HOURS)-now).total_seconds()
                    if rem<=0:
                        u["streak_active"]=False; u["streak_broken_at"]=now.isoformat(); save_user(uid); continue
                    # Reminders only while active; after break there are no more streak notifications.
                    for hours_left,key in ((10,"streak_reminder_10_sent"),(5,"streak_reminder_5_sent")):
                        if rem<=hours_left*3600 and not u.get(key):
                            u[key]=True; save_user(uid)
                            try: bot.send_message(int(uid),f"⚠️ <b>STREAK REMINDER</b>\n\n🔥 Your streak is still active. Only about <b>{hours_left} hours</b> remain before the 26-hour deadline.\n\nUse the bot now to keep your streak alive!")
                            except: pass
        except Exception as e: print("Streak worker error:",repr(e))
        time.sleep(60)

@bot.message_handler(func=lambda m: m.text=="🔥 STREAK SYSTEM")
def streak_admin_start(m):
    if not is_admin(m.from_user.id): return
    kb=InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("📢 SEND ALL",callback_data="streak_admin:send"),InlineKeyboardButton("🟢 OPEN",callback_data="streak_admin:open"))
    kb.add(InlineKeyboardButton("🔴 CLOSE",callback_data="streak_admin:close"),InlineKeyboardButton("⚙️ REWARDS",callback_data="streak_admin:rewards"))
    kb.add(InlineKeyboardButton("📊 STATS",callback_data="streak_admin:stats"),InlineKeyboardButton("♻️ RESET USER",callback_data="streak_admin:reset"))
    bot.send_message(m.chat.id,"🔥 <b>STREAK ADMIN CONTROL</b>\n\nUsers never start automatically. They only join after tapping START NOW from your broadcast.\n\nCurrent status: <b>"+("OPEN" if streak_enabled() else "CLOSED")+"</b>",reply_markup=kb,parse_mode="HTML")

@bot.callback_query_handler(func=lambda c:c.data.startswith("streak_admin:"))
def streak_admin_callback(call):
    if not is_admin(call.from_user.id): return
    action=call.data.split(":",1)[1]
    if action=="open": set_setting("streak_system_enabled",True); bot.answer_callback_query(call.id,"Streak OPEN")
    elif action=="close": set_setting("streak_system_enabled",False); bot.answer_callback_query(call.id,"Streak CLOSED")
    elif action=="send":
        ver=streak_campaign_version()+1; set_setting("streak_campaign_version",ver); set_setting("streak_system_enabled",True)
        kb=InlineKeyboardMarkup(); kb.add(InlineKeyboardButton("🔥 START NOW",callback_data="streak_start"))
        text=streak_broadcast_text(); sent=0
        for uid in list(users):
            try: bot.send_message(int(uid),text,reply_markup=kb,parse_mode="HTML"); sent+=1
            except: pass
        bot.send_message(call.message.chat.id,f"✅ Streak campaign sent to <b>{sent}</b> users. Users must tap START NOW.",parse_mode="HTML")
    elif action=="rewards":
        msg=bot.send_message(call.message.chat.id,"⚙️ Send:\n<code>daily_balance | daily_premium_days | milestone_every | milestone_balance | milestone_premium_days</code>\n\nExample: <code>0.10 | 0 | 7 | 0.50 | 1</code>",parse_mode="HTML")
        bot.register_next_step_handler(msg,streak_rewards_process)
    elif action=="stats":
        active=sum(1 for u in users.values() if streak_user_active(str(u.get("_id", "")) or ""))
        active=sum(1 for uid in users if streak_user_active(uid))
        counts=sorted([(int(u.get("streak_count",0) or 0),uid) for uid,u in users.items() if int(u.get("streak_count",0) or 0)>0],reverse=True)[:10]
        lines=["🔥 <b>STREAK STATS</b>","",f"Active: <b>{active}</b>",f"Reward: <b>${streak_reward_balance():.2f}</b> + <b>{streak_reward_premium_days()}d Premium</b>","","Top streaks:"]
        lines += [f"{i}. <code>{uid}</code> — 🔥 {c}" for i,(c,uid) in enumerate(counts,1)]
        bot.send_message(call.message.chat.id,"\n".join(lines),parse_mode="HTML")
    elif action=="reset":
        msg=bot.send_message(call.message.chat.id,"♻️ Send Telegram ID or BOT ID to reset streak:")
        bot.register_next_step_handler(msg,streak_reset_process)

def streak_rewards_process(m):
    if not is_admin(m.from_user.id): return
    try:
        p=[x.strip() for x in (m.text or "").split("|")]
        if len(p)<5: raise ValueError("5 values required")
        set_setting("streak_reward_balance",float(p[0])); set_setting("streak_reward_premium_days",int(p[1])); set_setting("streak_milestone_every",int(p[2])); set_setting("streak_milestone_balance",float(p[3])); set_setting("streak_milestone_premium_days",int(p[4]))
        bot.send_message(m.chat.id,"✅ Streak rewards updated.",reply_markup=admin_menu())
    except Exception as e: bot.send_message(m.chat.id,f"❌ {html.escape(str(e))}")

def streak_reset_process(m):
    if not is_admin(m.from_user.id): return
    target=(m.text or "").strip(); uid=target if target in users else find_user_by_botid(target)
    if not uid: bot.send_message(m.chat.id,"❌ User not found."); return
    for k in ["streak_active","streak_count","streak_started_at","streak_last_activity_at","streak_next_reward_at","streak_broken_at","streak_reminder_10_sent","streak_reminder_5_sent"]: users[uid].pop(k,None)
    save_user(uid); bot.send_message(m.chat.id,f"✅ Streak reset for <code>{uid}</code>.",parse_mode="HTML")

# ================= ADMIN SMS CONTROL =================

@bot.message_handler(func=lambda m: m.text in ["🟢 Open SMS", "🔴 CLOSE SMS", "🟢 OPEN VIA WHATSAPP", "🔴 CLOSE VIA WHATSAPP", "♻️ Reset all Verify"])
def sms_admin_manager(m):
    if not is_admin(m.from_user.id): return
    
    if m.text == "🟢 Open SMS":
        set_setting("sms_enabled", True)
        try:
            bot.send_message(m.chat.id, "🟢 SMS Verification system is now OPEN. Users can choose Gmail or Phone.")
        except: pass
    elif m.text == "🔴 CLOSE SMS":
        set_setting("sms_enabled", False)
        try:
            bot.send_message(m.chat.id, "🔴 SMS Verification system is now CLOSED. Users will only use Gmail.")
        except: pass
    elif m.text == "🟢 OPEN VIA WHATSAPP":
        if not WAFORGE_API_KEY:
            try:
                bot.send_message(m.chat.id, "❌ WhatsApp cannot be opened because WAFORGE_API_KEY is missing.")
            except: pass
            return
        set_setting("whatsapp_verify_enabled", True)
        try:
            bot.send_message(m.chat.id, "🟢 WhatsApp verification is now OPEN. Users can request OTP via WaForge WhatsApp.")
        except: pass
    elif m.text == "🔴 CLOSE VIA WHATSAPP":
        set_setting("whatsapp_verify_enabled", False)
        try:
            bot.send_message(m.chat.id, "🔴 WhatsApp verification is now CLOSED.")
        except: pass
    elif m.text == "♻️ Reset all Verify":
        # Make every user unverified and clear all active verification sessions.
        changed = 0
        for uid, data in users.items():
            if data.get("verified") or data.get("whatsapp_verified") or data.get("email") or data.get("phone"):
                data["verified"] = False
                data["whatsapp_verified"] = False
                data["phone_verified"] = False
                data["email_verified"] = False
                data["verification_method"] = None
                data.pop("email", None)
                data.pop("phone", None)
                data.pop("sticker", None)
                save_user(uid)
                changed += 1
        email_verify_pending.clear()
        phone_verify_pending.clear()
        whatsapp_verify_pending.clear()
        try:
            bot.send_message(m.chat.id, f"♻️ Reset complete. {changed} users are now Unverified and can verify again.")
        except: pass

# ================= PROFILE & VERIFICATION LOGIC =================

@bot.message_handler(func=lambda m: m.text == "👤 Profile")
def profile_handler(m):
    touch_user(m.from_user.id)
    if bot_locked_guard(m) or banned_guard(m):
        return
    uid = str(m.from_user.id)
    u_data = users.get(uid, {})
    
    verified = u_data.get("verified", False)
    sticker = u_data.get("sticker", "Verified" if verified else "Not Verified")
    status_str = f"Verified ({sticker})" if verified else "Not Verified"
    joined = u_data.get("joined_date", datetime.now().strftime("%Y-%m-%d"))
    downloads = videos_data.get("users", {}).get(uid, 0)
    balance = u_data.get("balance", 0.0)
    email = u_data.get("email", "")
    phone = u_data.get("phone", "")
    contact_info = email if email else (phone if phone else "Not Set")
    premium_status = f"💎 Active until {premium_until_text(uid)}" if is_premium(uid) else "❌ Not Active"
    
    text = (
        f"<b>👤 USER PROFILE</b>\n\n"
        f"• Status: {status_str}\n"
        f"• Premium: {premium_status}\n"
        f"• Contact: {contact_info}\n"
        f"• Date Joined: {joined}\n"
        f"• Total Downloads: {downloads}\n"
        f"• Balance: {format_asset(cur_code(uid), balance)}\n• USD Value: ${asset_to_usd(cur_code(uid), balance):,.2f} USD"
    )
    kb = InlineKeyboardMarkup(row_width=1)
    if not verified:
        kb.add(InlineKeyboardButton("🔐 Verify", callback_data="start_verify_flow"))
    try:
        bot.send_message(m.chat.id, text, reply_markup=kb)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "profile_history")
def profile_history_callback(call):
    uid=str(call.from_user.id); rows=list(activity_col.find({"user_id":uid}).sort("time",-1).limit(20)); lines=["📜 <b>YOUR HISTORY</b>",""]
    for r in rows:
        t=r.get("time"); ts=t.strftime("%Y-%m-%d %H:%M") if hasattr(t,"strftime") else str(t); lines.append(f"• {str(r.get('action','event')).replace('_',' ').title()} — {ts}")
    if not rows: lines.append("No history yet.")
    bot.answer_callback_query(call.id); bot.send_message(call.message.chat.id,"\n".join(lines))

@bot.callback_query_handler(func=lambda call: call.data == "profile_language")
def profile_language_callback(call):
    bot.answer_callback_query(call.id); bot.send_message(call.message.chat.id,"🌍 <b>Select your language</b>",reply_markup=language_kb("change_lang"))

@bot.callback_query_handler(func=lambda call: call.data == "start_verify_flow")
def start_verify_flow(call):
    try:
        sms_enabled = get_setting("sms_enabled", False)
        whatsapp_enabled = get_setting("whatsapp_verify_enabled", False) and bool(WAFORGE_API_KEY)
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("📧 Gmail", callback_data="verify_choice_gmail"))
        if sms_enabled:
            kb.add(InlineKeyboardButton("📱 SMS", callback_data="verify_choice_phone"))
        if whatsapp_enabled:
            kb.add(InlineKeyboardButton("🟢 WhatsApp OTP", callback_data="verify_choice_whatsapp"))
        if len(kb.keyboard) > 0:
            bot.edit_message_text(
                "Please choose your verification method:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=kb
            )
        else:
            bot.answer_callback_query(call.id,"No verification method is currently available.",show_alert=True); return
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"Verify flow error: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("verify_choice_"))
def handle_verify_choice(call):
    choice = call.data.split("_", 2)[2]
    try:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("Cancel Verification", callback_data="cancel_verify_process"))
        if choice == "gmail":
            msg = bot.send_message(call.message.chat.id, "Please enter your Gmail address:", reply_markup=kb)
            bot.register_next_step_handler(msg, process_verification_email)
        elif choice == "phone":
            msg = bot.send_message(call.message.chat.id, "Please send your phone number with country code (e.g. +252... or +251...):", reply_markup=kb)
            bot.register_next_step_handler(msg, process_verification_phone)
        elif choice == "whatsapp":
            if not get_setting("whatsapp_verify_enabled", False) or not WAFORGE_API_KEY:
                bot.answer_callback_query(call.id, "WhatsApp verification is not configured.", show_alert=True)
                return
            msg = bot.send_message(call.message.chat.id, "📱 Send the WhatsApp number with country code (e.g. +252... or +251...):", reply_markup=kb)
            bot.register_next_step_handler(msg, process_verification_whatsapp)
        bot.answer_callback_query(call.id)
    except Exception as e:
        print("Verify choice error:", e)

@bot.callback_query_handler(func=lambda call: call.data == "cancel_verify_process")
def cancel_verify_process(call):
    """Cancel verification cleanly and immediately return the user to the normal menu."""
    uid=str(call.from_user.id)
    email_verify_pending.pop(uid,None)
    phone_verify_pending.pop(uid,None)
    whatsapp_verify_pending.pop(uid,None)
    # telebot's next-step handler otherwise remains attached to the chat and can
    # consume the next normal menu button/text as if it were an OTP.
    try:
        bot.clear_step_handler_by_chat_id(call.message.chat.id)
    except Exception:
        pass
    try:
        bot.answer_callback_query(call.id,"✅ Verification cancelled. You can use the menu now.")
    except Exception: pass
    try:
        bot.edit_message_text("❌ <b>Verification cancelled.</b>\n\nYou can use all bot buttons normally now.",call.message.chat.id,call.message.message_id,reply_markup=None)
    except Exception: pass
    try:
        bot.send_message(call.message.chat.id,"🏠 <b>Main Menu</b>",reply_markup=localized_user_menu(uid))
    except Exception: pass

# Expire local verification state after the same 10-minute lifetime used by D7.
def delayed_cancel_session(chat_id,message_id,uid):
    """Expire Gmail/SMS verification 10 minutes after the latest OTP request.

    The loop deliberately re-checks the stored timestamp so a resend extends
    the lifetime instead of letting the original timer kill the new OTP.
    """
    while True:
        data=email_verify_pending.get(uid) or phone_verify_pending.get(uid)
        if not data: return
        created=float(data.get("time",0) or 0)
        remaining=600-(time.time()-created)
        if remaining <= 0: break
        time.sleep(min(remaining,30))
    email_verify_pending.pop(uid,None)
    phone_verify_pending.pop(uid,None)
    try: bot.clear_step_handler_by_chat_id(chat_id)
    except Exception: pass
    try:
        bot.edit_message_text("⏰ <b>Verification session expired.</b>\n\nPlease start verification again if needed.",chat_id,message_id,reply_markup=None)
    except Exception: pass
    try:
        bot.send_message(chat_id,"🏠 <b>Main Menu</b>",reply_markup=localized_user_menu(uid))
    except Exception: pass

# ----- GMAIL VERIFICATION LOGIC ----- #

def process_verification_email(m):
    uid = str(m.from_user.id)
    email = (m.text or "").strip()
    
    menu_buttons = ["👤 Profile", "👑 ADMIN PANEL", "💰 BALANCE", "💸 WITHDRAWAL", "👥 REFERRAL", "🆔 GET ID", "☎️ CUSTOMER", "🤖CUSTOMER AI", "🔙 BACK MAIN MENU", "💳 PAY"]
    if email in menu_buttons or "@" not in email:
        try:
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("Cancel Verification", callback_data="cancel_verify_process"))
            msg = bot.send_message(m.chat.id, "❌ Invalid email address. Please enter a valid Gmail address:", reply_markup=kb)
            bot.register_next_step_handler(msg, process_verification_email)
        except: pass
        return

    code = str(random.randint(100000, 999999))
    current_time = time.time()
    email_verify_pending[uid] = {
        "email": email,
        "code": code,
        "time": current_time,
        "last_resend": current_time
    }
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 600px; background: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <h2 style="color: #333;">Email Verification</h2>
            <p>Hello,</p>
            <p>Your 6-digit verification code for the bot is:</p>
            <div style="font-size: 24px; font-weight: bold; color: #4CAF50; background: #e8f5e9; padding: 15px; text-align: center; border-radius: 4px; letter-spacing: 5px;">
                {code}
            </div>
            <p style="margin-top: 20px; color: #666; font-size: 12px;">If you didn't request this, please ignore this email.</p>
        </div>
    </body>
    </html>
    """
    
    success = send_html_email(email, "Your Bot Verification Code", html_content)
    if success:
        try:
            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton("🔄 Resend", callback_data="resend_verify_code"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process")
            )
            msg = bot.send_message(m.chat.id, f"📩 A 6-digit verification code has been sent to your email ({email}). Please enter the code here:", reply_markup=kb)
            bot.register_next_step_handler(msg, process_verification_code)
            threading.Thread(target=delayed_cancel_session, args=(m.chat.id, msg.message_id, uid), daemon=True).start()
        except: pass
    else:
        try:
            bot.send_message(m.chat.id, "❌ Failed to send verification email. Please try again later.")
        except: pass

@bot.callback_query_handler(func=lambda call: call.data == "resend_verify_code")
def resend_verify_code_callback(call):
    uid = str(call.from_user.id)
    if uid not in email_verify_pending:
        bot.answer_callback_query(call.id, "❌ Verification session expired. Please start again from your profile.", show_alert=True)
        return
        
    data = email_verify_pending[uid]
    current_time = time.time()
    last_resend_time = data.get("last_resend", data.get("time", 0))
    cooldown = 60  # 1 minute for Gmail
    elapsed = current_time - last_resend_time
    
    if elapsed < cooldown:
        remaining = int(cooldown - elapsed)
        bot.answer_callback_query(call.id, f"⏳ Please wait {remaining}s before requesting another code.", show_alert=True)
        return
        
    data["last_resend"] = current_time
    email = data["email"]
    code = str(random.randint(100000, 999999))
    data["code"] = code
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 600px; background: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <h2 style="color: #333;">Email Verification (Resend)</h2>
            <p>Hello,</p>
            <p>Your new 6-digit verification code for the bot is:</p>
            <div style="font-size: 24px; font-weight: bold; color: #4CAF50; background: #e8f5e9; padding: 15px; text-align: center; border-radius: 4px; letter-spacing: 5px;">
                {code}
            </div>
            <p style="margin-top: 20px; color: #666; font-size: 12px;">If you didn't request this, please ignore this email.</p>
        </div>
    </body>
    </html>
    """
    
    success = send_html_email(email, "Your New Bot Verification Code", html_content)
    if success:
        bot.answer_callback_query(call.id, "✅ A new code has been sent to your email!")
        try:
            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton("🔄 Resend", callback_data="resend_verify_code"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process")
            )
            msg = bot.send_message(call.message.chat.id, f"📩 A new 6-digit verification code has been resent to your email ({email}). Please enter the code here:", reply_markup=kb)
            bot.register_next_step_handler(msg, process_verification_code)
            threading.Thread(target=delayed_cancel_session, args=(call.message.chat.id, msg.message_id, uid), daemon=True).start()
        except: pass
    else:
        bot.answer_callback_query(call.id, "❌ Failed to resend verification email.", show_alert=True)

def process_verification_code(m):
    uid = str(m.from_user.id)
    code_input = (m.text or "").strip()
    
    if uid not in email_verify_pending:
        try:
            bot.send_message(m.chat.id, "❌ Verification session expired or already completed. Please start again from your profile.")
        except: pass
        return

    menu_buttons = ["👤 Profile", "👑 ADMIN PANEL", "💰 BALANCE", "💸 WITHDRAWAL", "👥 REFERRAL", "🆔 GET ID", "☎️ CUSTOMER", "🤖CUSTOMER AI", "🔙 BACK MAIN MENU", "💳 PAY"]
    if code_input in menu_buttons or not code_input.isdigit() or len(code_input) != 6:
        try:
            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton("🔄 Resend", callback_data="resend_verify_code"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process")
            )
            msg = bot.send_message(
                m.chat.id,
                "⚠️ <b>Action not allowed!</b>\n"
                "You must enter the 6-digit code sent to your Gmail first.\n\n"
                "Please enter the correct code:",
                reply_markup=kb
            )
            bot.register_next_step_handler(msg, process_verification_code)
        except: pass
        return

    data = email_verify_pending[uid]
    if code_input == data["code"]:
        users[uid]["verified"] = True
        users[uid]["email_verified"] = True
        users[uid]["verification_method"] = "Gmail"
        users[uid]["email"] = data["email"]
        if "sticker" not in users[uid] or not users[uid]["sticker"]:
            users[uid]["sticker"] = "🌟"
        save_user(uid)
        email_verify_pending.pop(uid, None)
        trial_activated=activate_pending_trial(uid,m.chat.id)
        try:
            bot.send_message(m.chat.id, "✅ Congratulations! Your account is now Verified. Your pending 1-Day Trial was activated automatically." if trial_activated else "✅ Congratulations! Your account is now Verified. You can check your profile status.", reply_markup=localized_user_menu(str(m.from_user.id)))
        except: pass
    else:
        try:
            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton("🔄 Resend", callback_data="resend_verify_code"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process")
            )
            msg = bot.send_message(m.chat.id, "❌ Incorrect verification code. Please enter the correct 6-digit code:", reply_markup=kb)
            bot.register_next_step_handler(msg, process_verification_code)
            threading.Thread(target=delayed_cancel_session, args=(m.chat.id, msg.message_id, uid), daemon=True).start()
        except: pass

# ----- PHONE VERIFICATION LOGIC ----- #

def process_verification_phone(m):
    uid = str(m.from_user.id)
    phone_input = (m.text or "").strip().replace(" ", "")
    menu_buttons = ["👤 Profile", "👑 ADMIN PANEL", "💰 BALANCE", "💸 WITHDRAWAL", "👥 REFERRAL", "🆔 GET ID", "☎️ CUSTOMER", "🤖CUSTOMER AI", "🔙 BACK MAIN MENU", "💳 PAY"]
    if phone_input in menu_buttons or not re.fullmatch(r"\+[1-9]\d{9,14}", phone_input):
        kb=InlineKeyboardMarkup(); kb.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process"))
        msg=bot.send_message(m.chat.id,"❌ Invalid number. Please send a valid phone number with country code (e.g. +252... or +251...).",reply_markup=kb)
        bot.register_next_step_handler(msg,process_verification_phone); return
    ok, detail, otp_id = send_d7_sms(phone_input, "")
    if not ok:
        print("D7 Verify send error:", detail)
        kb=InlineKeyboardMarkup(); kb.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify_process"))
        bot.send_message(m.chat.id,"❌ <b>SMS OTP could not be sent.</b>\n\nPlease check the phone number, D7 balance/Sender ID, and try again.",reply_markup=kb); return
    now=time.time()
    phone_verify_pending[uid]={"phone":phone_input,"otp_id":otp_id,"time":now,"last_resend":now}
    kb=InlineKeyboardMarkup(); kb.row(InlineKeyboardButton("🔄 Resend SMS",callback_data="resend_phone_code"),InlineKeyboardButton("❌ Cancel",callback_data="cancel_verify_process"))
    msg=bot.send_message(m.chat.id,f"📲 <b>SMS OTP request accepted</b> for <code>{phone_input}</code>.\n\nEnter the 6-digit code when it arrives.\n⏳ Valid for 10 minutes.",reply_markup=kb)
    bot.register_next_step_handler(msg,process_phone_code)
    threading.Thread(target=delayed_cancel_session,args=(m.chat.id,msg.message_id,uid),daemon=True).start()

@bot.callback_query_handler(func=lambda call: call.data == "resend_phone_code")
def resend_phone_code_callback(call):
    uid=str(call.from_user.id); data=phone_verify_pending.get(uid)
    if not data:
        bot.answer_callback_query(call.id,"❌ Session expired. Start verification again.",show_alert=True); return
    elapsed=time.time()-data.get("last_resend",data.get("time",0))
    if elapsed<60:
        bot.answer_callback_query(call.id,f"⏳ Please wait {int(60-elapsed)}s.",show_alert=True); return
    ok,detail,new_id=resend_d7_sms(data.get("otp_id"))
    if not ok:
        print("D7 Verify resend error:",detail); bot.answer_callback_query(call.id,"❌ SMS resend failed.",show_alert=True); return
    now=time.time(); data["otp_id"]=new_id; data["last_resend"]=now; data["time"]=now
    bot.answer_callback_query(call.id,"✅ New SMS OTP sent")
    kb=InlineKeyboardMarkup(); kb.row(InlineKeyboardButton("🔄 Resend SMS",callback_data="resend_phone_code"),InlineKeyboardButton("❌ Cancel",callback_data="cancel_verify_process"))
    msg=bot.send_message(call.message.chat.id,"📲 <b>New SMS OTP request accepted.</b>\n\nEnter the new 6-digit code when it arrives.",reply_markup=kb)
    bot.register_next_step_handler(msg,process_phone_code)

def process_phone_code(m):
    uid=str(m.from_user.id); code_input=(m.text or "").strip(); data=phone_verify_pending.get(uid)
    if not data:
        bot.send_message(m.chat.id,"❌ Verification session expired. Please start again from your profile."); return
    if not re.fullmatch(r"\d{6}",code_input):
        kb=InlineKeyboardMarkup(); kb.row(InlineKeyboardButton("🔄 Resend SMS",callback_data="resend_phone_code"),InlineKeyboardButton("❌ Cancel",callback_data="cancel_verify_process"))
        msg=bot.send_message(m.chat.id,"⚠️ Enter the 6-digit SMS code first.",reply_markup=kb); bot.register_next_step_handler(msg,process_phone_code); return
    ok,detail=verify_d7_sms(data.get("otp_id"),code_input)
    if ok:
        users[uid]["verified"]=True; users[uid]["phone_verified"]=True; users[uid]["verification_method"]="SMS"; users[uid]["phone"]=data["phone"]; users[uid]["sticker"]=users[uid].get("sticker") or "🌟"; save_user(uid); phone_verify_pending.pop(uid,None)
        trial_activated=activate_pending_trial(uid,m.chat.id)
        bot.send_message(m.chat.id,"✅ Congratulations! Your account is now Verified. Your pending 1-Day Trial was activated automatically." if trial_activated else "✅ Congratulations! Your account is now Verified. You can check your profile status.",reply_markup=localized_user_menu(uid)); return
    print("D7 Verify check error:",detail)
    detail_text=str(detail).lower()
    if "expired" in detail_text:
        phone_verify_pending.pop(uid,None); bot.send_message(m.chat.id,"⏰ <b>This SMS code has expired.</b> Please start verification again."); return
    kb=InlineKeyboardMarkup(); kb.row(InlineKeyboardButton("🔄 Resend SMS",callback_data="resend_phone_code"),InlineKeyboardButton("❌ Cancel",callback_data="cancel_verify_process"))
    msg=bot.send_message(m.chat.id,"❌ Incorrect SMS code. Please enter the correct 6-digit code:",reply_markup=kb); bot.register_next_step_handler(msg,process_phone_code)

# ----- WHATSAPP VERIFICATION LOGIC (WaForge) ----- #

def process_verification_whatsapp(m):
    uid=str(m.from_user.id); phone_input=(m.text or '').strip()
    if phone_input.lower() in {"cancel", "❌ cancel", "cancel verification"}:
        whatsapp_verify_pending.pop(uid,None); bot.clear_step_handler_by_chat_id(m.chat.id); bot.send_message(m.chat.id,"❌ <b>Verification cancelled.</b> You can use the menu now.",reply_markup=localized_user_menu(uid)); return
    if not re.fullmatch(r"\+[1-9]\d{7,14}",phone_input):
        msg=bot.send_message(m.chat.id,"❌ Invalid WhatsApp number. Use full international format, e.g. +2519xxxxxxxx")
        bot.register_next_step_handler(msg,process_verification_whatsapp); return
    ok,detail,request_id=send_waforge_whatsapp(phone_input,uid)
    if not ok:
        print("WhatsApp OTP send error:", detail)
        bot.send_message(m.chat.id,"❌ <b>WhatsApp OTP could not be sent.</b>\n\nPlease check your WhatsApp number and try again. If the problem continues, contact Customer/Admin.")
        return
    now=time.time(); whatsapp_verify_pending[uid]={"phone":phone_input,"request_id":request_id,"time":now,"last_resend":now}
    msg=bot.send_message(m.chat.id,"📲 <b>WhatsApp OTP sent</b>\n\nEnter the 6-digit code sent to your WhatsApp.\n⏳ <b>This code expires in 5 minutes.</b>",reply_markup=whatsapp_otp_keyboard())
    bot.register_next_step_handler(msg,process_whatsapp_code)
    threading.Thread(target=expire_whatsapp_session,args=(uid,now),daemon=True).start()

@bot.callback_query_handler(func=lambda call: call.data == "resend_whatsapp_code")
def resend_whatsapp_code_callback(call):
    uid=str(call.from_user.id); data=whatsapp_verify_pending.get(uid)
    if not data:
        bot.answer_callback_query(call.id,"Session expired.",show_alert=True); return
    if time.time()-data.get("last_resend",data.get("time",0))<60:
        bot.answer_callback_query(call.id,"⏳ Please wait 60 seconds between OTP requests.",show_alert=True); return
    ok,detail,request_id=send_waforge_whatsapp(data["phone"],uid)
    if not ok:
        print("WaForge resend error:",detail); bot.answer_callback_query(call.id,"Could not send WhatsApp OTP.",show_alert=True); return
    now=time.time(); data.update({"request_id":request_id,"last_resend":now,"time":now})
    bot.answer_callback_query(call.id,"✅ New WhatsApp OTP sent")
    msg=bot.send_message(call.message.chat.id,"📲 <b>New WhatsApp OTP sent.</b>\n\nEnter the new 6-digit code.\n⏳ <b>This code expires in 5 minutes.</b>",reply_markup=whatsapp_otp_keyboard())
    bot.register_next_step_handler(msg,process_whatsapp_code)
    threading.Thread(target=expire_whatsapp_session,args=(uid,now),daemon=True).start()

def process_whatsapp_code(m):
    uid=str(m.from_user.id); data=whatsapp_verify_pending.get(uid)
    if (m.text or '').strip().lower() in {"cancel","❌ cancel","cancel verification"}:
        whatsapp_verify_pending.pop(uid,None); bot.clear_step_handler_by_chat_id(m.chat.id); bot.send_message(m.chat.id,"❌ <b>Verification cancelled.</b> You can use the menu now.",reply_markup=localized_user_menu(uid)); return
    if not data:
        bot.send_message(m.chat.id,"⏰ <b>This code has expired.</b>\n\nPlease request a new WhatsApp OTP."); return
    if time.time()-data.get("time",0)>=WAFORGE_OTP_TTL:
        whatsapp_verify_pending.pop(uid,None); bot.send_message(m.chat.id,"⏰ <b>This code has expired.</b>\n\nPlease request a new WhatsApp OTP."); return
    code=(m.text or '').strip()
    if not re.fullmatch(r"\d{6}",code):
        msg=bot.send_message(m.chat.id,"⚠️ Please enter the 6-digit WhatsApp code:",reply_markup=whatsapp_otp_keyboard()); bot.register_next_step_handler(msg,process_whatsapp_code); return
    ok,detail=verify_waforge_whatsapp(data["phone"],code,data.get("request_id"))
    if not ok:
        print("WaForge verify error:",detail); detail_text=str(detail).lower()
        if "expired" in detail_text or "expire" in detail_text or "410" in detail_text:
            whatsapp_verify_pending.pop(uid,None); bot.send_message(m.chat.id,"⏰ <b>This code has expired.</b>\n\nPlease request a new WhatsApp OTP."); return
        msg=bot.send_message(m.chat.id,"❌ Incorrect WhatsApp code. Please try again:",reply_markup=whatsapp_otp_keyboard()); bot.register_next_step_handler(msg,process_whatsapp_code); return
    users[uid]["verified"]=True; users[uid]["phone_verified"]=True; users[uid]["verification_method"]="WhatsApp"; users[uid]["phone"]=data["phone"]; users[uid]["whatsapp_verified"]=True; users[uid]["sticker"]=users[uid].get("sticker") or "🌟"; save_user(uid); whatsapp_verify_pending.pop(uid,None)
    trial_activated=activate_pending_trial(uid,m.chat.id)
    bot.send_message(m.chat.id,"✅ <b>WhatsApp verification successful.</b> Your account is now verified."+("\n\n🎁 Your pending 1-Day Premium Trial was activated automatically." if trial_activated else ""),reply_markup=localized_user_menu(uid))

# ================= ADMIN VERIFIED USERS & STICKER MANAGER =================

@bot.message_handler(func=lambda m: m.text == "✅ Verified Users")
def verified_users_list(m):
    if not is_admin(m.from_user.id):
        return
    verified_list = [uid for uid, data in users.items() if user_is_verified(uid)]
    if not verified_list:
        try:
            bot.send_message(m.chat.id, "No verified users found.")
        except: pass
        return
    
    text = f"✅ VERIFIED USERS ({len(verified_list)})\n\n"
    for uid in verified_list[:30]:
        u_data = users[uid]
        sticker = u_data.get("sticker", "N/A")
        email = u_data.get('email', '')
        phone = u_data.get('phone', '')
        contact = email if email else (phone if phone else "No Contact Info")
        method = u_data.get("verification_method", "Unknown")
        text += f"• <a href='tg://user?id={uid}'>{uid}</a> | {contact} | Method: {method} | Sticker: {sticker}\n"
    try:
        bot.send_message(m.chat.id, text, parse_mode="HTML")
    except: pass

@bot.message_handler(func=lambda m: m.text == "🏷️ Sticker")
def sticker_admin_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send User ID or BOT ID and the sticker/badge separated by pipe (|)\nExample:\n123456789 | 🌟 Verified")
        bot.register_next_step_handler(msg, sticker_admin_process)
    except: pass

def sticker_admin_process(m):
    if not is_admin(m.from_user.id):
        return
    try:
        parts = m.text.split("|")
        if len(parts) < 2:
            bot.send_message(m.chat.id, "❌ Format error. Use: UserID | StickerText")
            return
        uid_str = parts[0].strip()
        sticker_text = parts[1].strip()
        
        uid = uid_str if uid_str in users else find_user_by_botid(uid_str)
        if not uid or uid not in users:
            bot.send_message(m.chat.id, "❌ User not found.")
            return
        users[uid]["sticker"] = sticker_text
        save_user(uid)
        bot.send_message(m.chat.id, f"✅ Sticker successfully updated for user {uid}!")
        try:
            bot.send_message(int(uid), f"🌟 Your profile status sticker has been updated to: {sticker_text}")
        except: pass
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Error: {e}")

# ================= ADMIN SEND EMAIL ALL =================

@bot.message_handler(func=lambda m: m.text == "📢 Send Email All")
def send_email_all_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send the HTML content or message you want to email to all users who have an email registered:")
        bot.register_next_step_handler(msg, send_email_all_process)
    except: pass

def send_email_all_process(m):
    if not is_admin(m.from_user.id):
        return
    html_content = m.text
    
    count = 0
    for uid, data in users.items():
        email = data.get("email")
        if email:
            success = send_html_email(email, "Announcement from Video Downloader Bot", html_content)
            if success:
                count += 1
    try:
        bot.send_message(m.chat.id, f"✅ HTML Email successfully sent to {count} verified users with email addresses.")
    except: pass

# ================= YOUTUBE 30 MIN ADMIN CONTROL =================

@bot.message_handler(func=lambda m: m.text == "🔓 OPEN 30 MIN")
def open_30_min_start(m):
    if not is_admin(m.from_user.id): return
    try:
        msg = bot.send_message(m.chat.id, "Send User ID or BOT ID to grant 30-min YouTube access:")
        bot.register_next_step_handler(msg, open_30_min_process)
    except: pass

def open_30_min_process(m):
    if not is_admin(m.from_user.id): return
    uid_str = (m.text or "").strip()
    uid = uid_str if uid_str in users else find_user_by_botid(uid_str)
    
    if not uid or uid not in users:
        try:
            bot.send_message(m.chat.id, "❌ User not found.")
        except: pass
        return
    users[uid]["youtube_30m"] = True
    save_user(uid)
    try:
        bot.send_message(m.chat.id, f"✅ User {uid} can now download YouTube videos up to 30 minutes.")
        bot.send_message(int(uid), "🎉 Congratulations! You have been granted special access to download YouTube videos up to 30 minutes long!")
    except: pass

# ================= QUICK ACCESS ADMIN CONTROLS =================

@bot.message_handler(func=lambda m: m.text == "⚡ QUICK ACCESS")
def quick_access_admin(m):
    if not is_admin(m.from_user.id):
        return
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ Add User Access", callback_data="qa_add"))
    kb.add(InlineKeyboardButton("🔴 Remove User Access", callback_data="qa_remove"))
    try:
        bot.send_message(m.chat.id, "⚡ Quick Access Management", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("qa_"))
def handle_qa_callbacks(call):
    if not is_admin(call.from_user.id):
        return
    if call.data == "qa_add":
        try:
            msg = bot.send_message(call.message.chat.id, "Send User ID or BOT ID to grant Quick Access:")
            bot.register_next_step_handler(msg, lambda m: grant_qa(m, True))
        except: pass
    elif call.data == "qa_remove":
        try:
            msg = bot.send_message(call.message.chat.id, "Send User ID or BOT ID to remove Quick Access:")
            bot.register_next_step_handler(msg, lambda m: grant_qa(m, False))
        except: pass

def grant_qa(m, status):
    if not is_admin(m.from_user.id):
        return
    text_input = (m.text or "").strip()
    uid = text_input if text_input in users else find_user_by_botid(text_input)
    if uid and uid in users:
        users[uid]["quick_access"] = status
        save_user(uid)
        try:
            if status:
                bot.send_message(m.chat.id, f"⚡ Quick Access enabled for user {uid}. Priority queue, all {len(premium_platform_names())} Premium/Trial platforms, unlimited-duration YouTube access and faster MP3/video processing are now unlocked.")
                bot.send_message(int(uid), "⚡ <b>Quick Access Activated!</b>\n\nYou now have priority download processing, access to all Premium/Trial platforms, and extended YouTube access.\n\n🚀 Your downloads will use the fastest available queue.", parse_mode="HTML")
            else:
                bot.send_message(m.chat.id, f"🔴 Quick Access disabled for user {uid}.")
                bot.send_message(int(uid), "🔴 <b>Quick Access Disabled</b>\n\nYour account has returned to its normal download priority.", parse_mode="HTML")
        except Exception: pass
    else:
        try:
            bot.send_message(m.chat.id, "❌ User not found.")
        except: pass

# ================= FEEDBACK LOGIC =================

def send_feedback_request(chat_id, platform, download_id):
    feedback_request_id = str(uuid.uuid4())
    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("👍 Good", callback_data=f"rate_good_{feedback_request_id}_{platform}"),
        InlineKeyboardButton("👎 Bad", callback_data=f"rate_bad_{feedback_request_id}_{platform}")
    )
    kb.add(InlineKeyboardButton("💬 Feedback", callback_data=f"rate_text_{feedback_request_id}"))
    
    try:
        bot.send_message(chat_id, "How was your experience with our service? ❤️", reply_markup=kb)
    except Exception as e:
        print(f"Feedback send error: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith(("rate_good_", "rate_bad_")))
def handle_rating(call):
    parts = call.data.split("_")
    rating = parts[1]
    req_id = parts[2]
    platform = parts[3]
    user_id = call.from_user.id
    
    feedback_col.update_one(
        {"user_id": user_id, "feedback_request_id": req_id},
        {
            "$set": {
                "username": call.from_user.username or "N/A",
                "rating": rating,
                "platform": platform,
                "updated_at": datetime.now()
            },
            "$setOnInsert": {"created_at": datetime.now()}
        },
        upsert=True
    )
    bot.answer_callback_query(call.id, "Thank you for your feedback! ❤️")
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.edit_message_text("Thank you for your feedback! ❤️", call.message.chat.id, call.message.message_id)
    except: pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("rate_text_"))
def ask_written_feedback(call):
    req_id = call.data.split("_")[2]
    try:
        msg = bot.send_message(call.message.chat.id, "Please tell us how we can improve our service.")
        bot.register_next_step_handler(msg, save_written_feedback, req_id)
    except: pass

def save_written_feedback(m, req_id):
    if not m.text:
        try:
            bot.send_message(m.chat.id, "Please send text feedback.")
        except: pass
        return
        
    feedback_col.update_one(
        {"user_id": m.from_user.id, "feedback_request_id": req_id},
        {
            "$set": {
                "username": m.from_user.username or "N/A",
                "feedback_text": m.text,
                "updated_at": datetime.now()
            },
            "$setOnInsert": {"created_at": datetime.now()}
        },
        upsert=True
    )
    try:
        bot.send_message(m.chat.id, "Thank you! Your feedback has been received. ❤️")
    except: pass

@bot.message_handler(func=lambda m: m.text in ["📊 Feedback Stats", "🟢 Open Feedback", "🔴 Close Feedback", "🗑️ Reset All Feedbacks"])
def feedback_admin_manager(m):
    if not is_admin(m.from_user.id): return
    
    if m.text == "🟢 Open Feedback":
        videos_data["feedback_enabled"] = True
        save_videos()
        try:
            bot.send_message(m.chat.id, "🟢 Feedback system is now OPEN.")
        except: pass
    elif m.text == "🔴 Close Feedback":
        videos_data["feedback_enabled"] = False
        save_videos()
        try:
            bot.send_message(m.chat.id, "🔴 Feedback system is now CLOSED.")
        except: pass
    elif m.text == "📊 Feedback Stats":
        goods = feedback_col.count_documents({"rating": "good"})
        bads = feedback_col.count_documents({"rating": "bad"})
        written = feedback_col.count_documents({"feedback_text": {"$exists": True}})
        total = goods + bads
        sat = "No ratings yet."
        if total > 0:
            pct = (goods / total) * 100
            sat = f"{pct:.2f}%"
        status = "OPEN" if videos_data.get("feedback_enabled") else "CLOSED"
        text = f"📊 FEEDBACK STATISTICS\n\n👍 Good: {goods}\n👎 Bad: {bads}\n💬 Written Feedback: {written}\n📊 Total Ratings: {total}\n❤️ Satisfaction: {sat}\n\n🟢 Status: {status}"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("💬 View Feedback", callback_data="view_fb_0"))
        try:
            bot.send_message(m.chat.id, text, reply_markup=kb)
        except: pass
    elif m.text == "🗑️ Reset All Feedbacks":
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("✅ Yes, Reset Everything", callback_data="reset_fb_confirm"))
        kb.add(InlineKeyboardButton("❌ Cancel", callback_data="reset_fb_cancel"))
        try:
            bot.send_message(m.chat.id, "⚠️ Are you sure you want to delete all existing feedback data? This action cannot be undone.", reply_markup=kb)
        except: pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("view_fb_"))
def view_feedback_pagination(call):
    if not is_admin(call.from_user.id): return
    page = int(call.data.split("_")[2])
    all_fb = list(feedback_col.find({"feedback_text": {"$exists": True}}).sort("created_at", -1))
    
    if not all_fb:
        bot.answer_callback_query(call.id, "No feedback yet.")
        return
    item = all_fb[page]
    text = f"💬 USER FEEDBACK\n\n👤 User: @{item.get('username', 'N/A')}\n📅 Date: {item.get('created_at').strftime('%Y-%m-%d')}\n\n📝 {item.get('feedback_text')}"
    kb = InlineKeyboardMarkup()
    btns = []
    if page > 0:
        btns.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"view_fb_{page-1}"))
    if page < len(all_fb) - 1:
        btns.append(InlineKeyboardButton("Next ➡️", callback_data=f"view_fb_{page+1}"))
    if btns:
        kb.row(*btns)
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="close_fb"))
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda call: call.data in ["reset_fb_confirm", "reset_fb_cancel", "close_fb"])
def reset_callback_handler(call):
    if not is_admin(call.from_user.id): return
    if call.data == "reset_fb_confirm":
        try:
            feedback_col.delete_many({})
            bot.edit_message_text("✅ ALL FEEDBACKS RESET. All previous feedback data has been successfully deleted.", call.message.chat.id, call.message.message_id)
        except:
            bot.edit_message_text("❌ RESET FAILED", call.message.chat.id, call.message.message_id)
    elif call.data == "reset_fb_cancel":
        bot.edit_message_text("❌ Reset cancelled.", call.message.chat.id, call.message.message_id)
    elif call.data == "close_fb":
        bot.delete_message(call.message.chat.id, call.message.message_id)

CHANNEL_USERNAME = "@tiktokvediodownload"

# ================= DOWNLOAD MEDIA FUNCTION =================

PLATFORM_PATTERNS = {
    "tiktok": ("tiktok.com", "vm.tiktok.com", "vt.tiktok.com"),
    "youtube": ("youtube.com", "youtu.be", "youtube-nocookie.com"),
    "facebook": ("facebook.com", "fb.watch", "m.facebook.com", "facebook.watch"),
    "instagram": ("instagram.com",),
    "pinterest": ("pinterest.com", "pin.it"),
    "snapchat": ("snapchat.com",),
    "twitter": ("twitter.com", "x.com"),
    "reddit": ("reddit.com", "redd.it"),
    "threads": ("threads.net", "threads.com"),
    "likee": ("likee.video", "like.video"),
    "vimeo": ("vimeo.com",),
    "dailymotion": ("dailymotion.com", "dai.ly"),
    "soundcloud": ("soundcloud.com", "on.soundcloud.com"),
    "twitch": ("twitch.tv", "clips.twitch.tv"),
    "tumblr": ("tumblr.com",),
    "streamable": ("streamable.com",),
    "odnoklassniki": ("ok.ru", "odnoklassniki.ru"),
}

def detect_platform(link):
    try:
        text = (link or "").strip()
        parsed = urllib.parse.urlparse(text if "://" in text else "https://" + text)
        host = (parsed.netloc or "").lower().split(":", 1)[0]
        host = host[4:] if host.startswith("www.") else host
        # Prefer hostname matching over substring matching so a random URL
        # containing a platform name is not misclassified.
        for platform, patterns in PLATFORM_PATTERNS.items():
            for pattern in patterns:
                p = pattern.lower().removeprefix("www.")
                if host == p or host.endswith("." + p):
                    return platform
        # Short/redirect links can occasionally be malformed; retain a safe
        # substring fallback for the known domains only.
        low = text.lower()
        for platform, patterns in PLATFORM_PATTERNS.items():
            if any(p in low for p in patterns):
                return platform
    except Exception:
        pass
    return "unknown"

def _is_image_file(path):
    return os.path.splitext(path)[1].lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif"}

def _is_video_file(path):
    return os.path.splitext(path)[1].lower() in {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".flv"}

def _is_audio_file(path):
    return os.path.splitext(path)[1].lower() in {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".opus"}

def _download_limit_seconds(uid):
    """Return the duration limit, including admin/special YouTube access."""
    uid=str(uid)
    # Quick Access is an admin-granted priority tier: no artificial duration cap.
    # A large practical ceiling is used because yt-dlp expects a numeric filter.
    if is_quick_access(uid):
        # Practical unlimited ceiling for extractor APIs that require a number.
        return 3650 * 24 * 60 * 60
    if is_admin(uid):
        return max(1, int(get_setting("admin_max_minutes", 1440) or 1440)) * 60
    if users.get(uid,{}).get("youtube_30m"):
        return max(30, int(get_setting("youtube_special_minutes", 30) or 30)) * 60
    if is_premium(uid):
        minutes=int(get_setting("premium_max_minutes",PREMIUM_MAX_MINUTES_DEFAULT))
    else:
        minutes=int(get_setting("free_max_minutes",FREE_MAX_MINUTES_DEFAULT))
    return max(1,minutes)*60


def _extract_youtube_video_id(link):
    """Extract a canonical 11-character YouTube video id from common URL forms."""
    text = (link or "").strip()
    if not text:
        return None
    try:
        parsed = urllib.parse.urlparse(text if "://" in text else "https://" + text)
        host = (parsed.netloc or "").lower().split(":", 1)[0]
        path = parsed.path or ""
        if host in {"youtu.be", "www.youtu.be"}:
            candidate = path.strip("/").split("/")[0]
        elif "youtube.com" in host or host.endswith("youtube-nocookie.com"):
            qs = urllib.parse.parse_qs(parsed.query)
            candidate = (qs.get("v") or [""])[0]
            if not candidate:
                parts = [x for x in path.split("/") if x]
                if parts and parts[0] in {"shorts", "embed", "live", "v"} and len(parts) > 1:
                    candidate = parts[1]
        else:
            candidate = ""
        candidate = urllib.parse.unquote(candidate).split("?", 1)[0].split("&", 1)[0]
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
            return candidate
    except Exception:
        pass
    m = re.search(r"(?:v=|youtu\.be/|/shorts/|/embed/|/live/)([A-Za-z0-9_-]{11})", text)
    return m.group(1) if m else None


def _rapidapi_youtube_details(video_id):
    if not RAPIDAPI_YT_KEY:
        raise RuntimeError("RAPIDAPI_YT_KEY is not configured.")
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_YT_KEY,
        "X-RapidAPI-Host": RAPIDAPI_YT_HOST,
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
    }
    # urlAccess=normal is important: without it this API can return metadata
    # without usable video/audio URLs. Explicit videos/audios also avoids the
    # provider's automatic/blocked mode selecting metadata-only responses.
    params = {"videoId": video_id, "urlAccess": "normal", "videos": "auto", "audios": "auto", "lang": "en-US"}
    urls=[RAPIDAPI_YT_DETAILS_URL]
    last=None
    for endpoint in urls:
        try:
            r=requests.get(endpoint,params=params,headers=headers,timeout=RAPIDAPI_TIMEOUT)
            last=r
            try: data=r.json()
            except Exception: data={"raw":r.text}
            if r.status_code in (200,201) and isinstance(data,dict):
                return data
            if r.status_code==429: raise RuntimeError("RapidAPI YouTube quota/rate limit reached.")
            if r.status_code in (401,403): raise RuntimeError("RapidAPI YouTube authentication/subscription failed.")
            if r.status_code==404: raise RuntimeError("RapidAPI YouTube video was not found.")
        except RuntimeError: raise
        except Exception as e: last=e
    if isinstance(last,Exception): raise last
    raise RuntimeError(f"RapidAPI YouTube HTTP {getattr(last,'status_code','unknown')}")

def _rapid_walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _rapid_walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _rapid_walk(v)

def _rapid_num(d, keys):
    for k in keys:
        v = d.get(k)
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            m = re.search(r"\d+(?:\.\d+)?", v)
            if m:
                try: return float(m.group())
                except Exception: pass
    return None

def _rapid_bool(d, keys):
    for k in keys:
        if k in d:
            v=d.get(k)
            if isinstance(v,bool): return v
            if isinstance(v,str) and v.lower() in {"true","yes","1"}: return True
            if isinstance(v,str) and v.lower() in {"false","no","0"}: return False
    return None

def _rapid_url(d):
    for k in ("url","downloadUrl","download_url","videoUrl","video_url","playbackUrl","playback_url","link"):
        v=d.get(k)
        if isinstance(v,str) and v.startswith(("http://","https://")): return v
    return None

def _rapid_formats(data):
    """Normalize RapidAPI YouTube v2 videos.items/audios.items plus raw fallback shapes."""
    out=[]; seen=set()
    def add_item(d, forced_video=None, forced_audio=None):
        if not isinstance(d,dict): return
        url=_rapid_url(d)
        if not url or url in seen: return
        text=" ".join(str(d.get(k,"")) for k in ("type","mimeType","mime","quality","qualityLabel","format","container","codec","audioQuality","itag")).lower()
        height=_rapid_num(d,("height","videoHeight","resolutionHeight")) or 0
        width=_rapid_num(d,("width","videoWidth","resolutionWidth")) or 0
        fps=_rapid_num(d,("fps","frameRate")) or 0
        has_audio=_rapid_bool(d,("hasAudio","audio","has_audio","isAudioIncluded"))
        has_video=_rapid_bool(d,("hasVideo","video","has_video"))
        video=bool(forced_video) if forced_video is not None else (bool(has_video) if has_video is not None else (height>0 or any(x in text for x in ("video","mp4","webm","avc","h264"))))
        audio=bool(forced_audio) if forced_audio is not None else (bool(has_audio) if has_audio is not None else any(x in text for x in ("audio","mp4a","m4a","opus")))
        if video or audio:
            seen.add(url); out.append({"url":url,"height":int(height),"width":int(width),"fps":fps,"audio":audio,"video":video,"text":text,"raw":d})
    if isinstance(data,dict):
        videos=((data.get("videos") or {}).get("items") if isinstance(data.get("videos"),dict) else data.get("videos")) or []
        audios=((data.get("audios") or {}).get("items") if isinstance(data.get("audios"),dict) else data.get("audios")) or []
        if isinstance(videos,list):
            for d in videos: add_item(d,forced_video=True)
        if isinstance(audios,list):
            for d in audios: add_item(d,forced_audio=True)
    for d in _rapid_walk(data):
        url=_rapid_url(d)
        if not url or url in seen: continue
        text=" ".join(str(d.get(k,"")) for k in ("type","mimeType","mime","quality","qualityLabel","format","container","codec","audioQuality")).lower()
        height=_rapid_num(d,("height","videoHeight","resolutionHeight")) or 0
        width=_rapid_num(d,("width","videoWidth","resolutionWidth")) or 0
        fps=_rapid_num(d,("fps","frameRate")) or 0
        has_audio=_rapid_bool(d,("hasAudio","audio","has_audio","isAudioIncluded"))
        has_video=_rapid_bool(d,("hasVideo","video","has_video"))
        audio = bool(has_audio) if has_audio is not None else any(x in text for x in ("audio","mp4a","m4a","opus"))
        video = bool(has_video) if has_video is not None else (height>0 or any(x in text for x in ("video","mp4","webm","avc","h264")))
        image_only=any(x in text for x in ("image/jpeg","image/png","image/webp","image/gif","thumbnail")) and not any(x in text for x in ("video/mp4","video/webm","video","avc","h264"))
        if image_only:
            continue
        if video or audio:
            seen.add(url)
            out.append({"url":url,"height":int(height),"width":int(width),"fps":fps,"audio":audio,"video":video,"text":text,"raw":d})
    return out

def _rapid_duration(data):
    for d in _rapid_walk(data):
        v=_rapid_num(d,("duration","durationSeconds","lengthSeconds","length"))
        if v and 0<v<172800: return int(v)
    return None

def _rapid_choose_pair(data, quality):
    fs=_rapid_formats(data)
    videos=[x for x in fs if x["video"]]
    audios=[x for x in fs if x["audio"] and not x["video"]]
    if not videos: raise RuntimeError("RapidAPI returned no downloadable video formats.")
    target=2160 if str(quality)=="2160" else int(quality or 720)
    under=[x for x in videos if x["height"] and x["height"]<=target]
    pool=under or videos
    # Prefer MP4 and streams with audio already included.
    pool.sort(key=lambda x:(0 if "mp4" in x["text"] else 1, 0 if x["audio"] else 1, abs((x["height"] or target)-target), -x["fps"]))
    video=pool[0]
    audio=None
    if not video["audio"] and audios:
        audios.sort(key=lambda x:(0 if "mp4" in x["text"] or "m4a" in x["text"] else 1, -x["fps"]))
        audio=audios[0]
    return video,audio

def _rapid_download_file(url, path, max_bytes=0):
    """Stream a provider URL. max_bytes=0 means unlimited."""
    with requests.get(url,headers={"User-Agent":"Mozilla/5.0"},stream=True,timeout=RAPIDAPI_TIMEOUT) as r:
        r.raise_for_status()
        total=0
        with open(path,"wb") as f:
            for chunk in r.iter_content(chunk_size=1024*1024):
                if not chunk: continue
                total += len(chunk)
                if max_bytes and total > max_bytes:
                    raise RuntimeError("Downloaded file is larger than the configured download limit.")
                f.write(chunk)
    return path

def _rapid_download_audio(link,tmp_dir,chat_id=None):
    """Fast YouTube audio path using the configured RapidAPI direct audio URL."""
    vid=_extract_youtube_video_id(link)
    if not vid: raise RuntimeError("Could not extract the YouTube video ID.")
    data=_rapidapi_youtube_details(vid)
    fs=_rapid_formats(data)
    audios=[x for x in fs if x["audio"]]
    if not audios: raise RuntimeError("RapidAPI returned no downloadable audio format.")
    audios.sort(key=lambda x:(0 if "m4a" in x["text"] or "mp4" in x["text"] else 1, -x.get("height",0)))
    src=audios[0]["url"]
    raw=os.path.join(tmp_dir,f"youtube_{vid}_audio.m4a")
    mb=_download_max_mb(str(chat_id) if chat_id is not None else "0", platform="youtube", link=link)
    _rapid_download_file(src,raw,(mb*1024*1024 if mb else 0))
    if not shutil.which("ffmpeg"): return raw
    out=os.path.join(tmp_dir,f"youtube_{vid}.mp3")
    proc=subprocess.run(["ffmpeg","-y","-i",raw,"-vn","-codec:a","libmp3lame","-b:a","192k",out],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
    if proc.returncode!=0 or not os.path.isfile(out): raise RuntimeError("RapidAPI audio conversion failed.")
    return out

def _rapid_download(link,tmp_dir,quality,max_seconds,chat_id=None):
    vid=_extract_youtube_video_id(link)
    if not vid: raise RuntimeError("Could not extract the YouTube video ID.")
    data=_rapidapi_youtube_details(vid)
    duration=_rapid_duration(data)
    if duration and duration>max_seconds:
        raise RuntimeError(f"YouTube video is too long. Maximum is {max_seconds//60} minutes.")
    try:
        video,audio=_rapid_choose_pair(data,quality)
    except Exception:
        # Some API responses expose only raw formats when simplified objects are unavailable.
        data2=_rapidapi_youtube_details(vid)
        video,audio=_rapid_choose_pair(data2,quality)
    mb=_download_max_mb(str(chat_id) if chat_id is not None else "0", platform="youtube", link=link)
    max_bytes=(mb*1024*1024 if mb else 0)
    video_path=os.path.join(tmp_dir,f"youtube_{vid}_video.mp4")
    _rapid_download_file(video["url"],video_path,max_bytes)
    if not audio:
        return [video_path]
    audio_path=os.path.join(tmp_dir,f"youtube_{vid}_audio.m4a")
    _rapid_download_file(audio["url"],audio_path,max_bytes)
    if not shutil.which("ffmpeg"):
        # Separate video/audio streams must be merged; never return a silent video.
        raise RuntimeError("FFmpeg is required to merge RapidAPI video + audio streams.")
    merged=os.path.join(tmp_dir,f"youtube_{vid}.mp4")
    cmd=["ffmpeg","-y","-i",video_path,"-i",audio_path,"-c:v","copy","-c:a","aac","-shortest",merged]
    proc=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=RAPIDAPI_TIMEOUT)
    if proc.returncode!=0 or not os.path.isfile(merged):
        raise RuntimeError("RapidAPI video/audio streams could not be merged. Install FFmpeg on Railway.")
    try: os.remove(video_path); os.remove(audio_path)
    except Exception: pass
    return [merged]

def _instagram_api_config():
    """Load Instagram downloader API config from MongoDB first, env vars second."""
    return (
        str(get_setting("instagram_api_url", RAPIDAPI_IG_URL) or "").strip(),
        str(get_setting("instagram_api_host", RAPIDAPI_IG_HOST) or "").strip(),
        str(get_setting("instagram_api_key", RAPIDAPI_IG_KEY) or "").strip(),
    )

def _instagram_api_enabled():
    url,host,key=_instagram_api_config()
    return bool(url and host and key)

def _instagram_api_walk(obj):
    if isinstance(obj,dict):
        yield obj
        for v in obj.values(): yield from _instagram_api_walk(v)
    elif isinstance(obj,list):
        for v in obj: yield from _instagram_api_walk(v)

def _instagram_api_urls(data):
    """Extract direct media URLs from the RapidAPI Instagram Reels response.

    The API commonly returns data.medias[].url. We also accept a few
    equivalent shapes so the downloader remains compatible with response
    revisions.
    """
    out=[]; seen=set()

    def add(v, media_type=None):
        if not isinstance(v,str) or not v.startswith(("http://","https://")) or v in seen:
            return
        seen.add(v)
        low=v.lower()
        is_video = (str(media_type or '').lower() in {'video','mp4','reel'} or
                    any(x in low for x in ('.mp4','video','videoplayback')))
        out.append((v, '.mp4' if is_video else '.jpg'))

    # Exact/current shape: {"data":{"medias":[{"url":"...","type":"video"}]}}
    medias = data.get('data',{}).get('medias',[]) if isinstance(data,dict) else []
    if isinstance(medias,list):
        for item in medias:
            if isinstance(item,dict):
                add(item.get('url'), item.get('type') or item.get('mediaType'))
                add(item.get('downloadUrl') or item.get('download_url'), item.get('type'))

    # Generic fallback for API response revisions.
    for d in _instagram_api_walk(data):
        if not isinstance(d,dict):
            continue
        media_type=d.get('type') or d.get('mediaType') or d.get('media_type')
        for k in ('url','downloadUrl','download_url','mediaUrl','media_url','videoUrl','video_url','imageUrl','image_url'):
            add(d.get(k), media_type)
    return out

def _instagram_api_download(link,tmp_dir):
    url,host,key=_instagram_api_config()
    if not (url and host and key): raise RuntimeError("Instagram RapidAPI is not configured in Admin Panel.")
    headers={"x-rapidapi-host":host,"x-rapidapi-key":key,"Accept":"application/json","User-Agent":"Mozilla/5.0"}
    try:
        # This endpoint is GET-only: /download?url=<instagram_url>.
        r=requests.get(url,params={"url":link},headers=headers,timeout=RAPIDAPI_TIMEOUT)
        if r.status_code in (401,403):
            raise RuntimeError("Instagram RapidAPI authentication/subscription failed.")
        if r.status_code==429:
            raise RuntimeError("Instagram RapidAPI quota/rate limit reached.")
        r.raise_for_status()
        data=r.json()
        links=_instagram_api_urls(data)
        if not links:
            raise RuntimeError(f"Instagram API returned no media URL. Response: {str(data)[:500]}")
        paths=[]
        for i,(media_url,ext) in enumerate(links[:20]):
            path=os.path.join(tmp_dir,f"instagram_{i}{ext}")
            with requests.get(media_url,headers={"User-Agent":"Mozilla/5.0"},stream=True,timeout=RAPIDAPI_TIMEOUT) as rr:
                rr.raise_for_status(); total=0
                with open(path,"wb") as f:
                    for c in rr.iter_content(1024*256):
                        if not c: continue
                        total+=len(c)
                        if total > 1024*1024*1024:
                            raise RuntimeError("Instagram media is too large.")
                        f.write(c)
            paths.append(path)
        return paths
    except requests.HTTPError as e:
        raise RuntimeError(f"Instagram RapidAPI HTTP error: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Instagram RapidAPI failed: {e}") from e

def _cobalt_headers():
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if COBALT_API_KEY:
        headers["Authorization"] = f"Api-Key {COBALT_API_KEY}"
    return headers


def _cobalt_enabled():
    return bool(COBALT_API_URL)


def _cobalt_process(link, tmp_dir, quality="720", mode="auto"):
    """Resolve a public media URL through a Cobalt instance and save returned media."""
    if not _cobalt_enabled():
        raise RuntimeError("Cobalt is not configured. Set COBALT_API_URL to your own Cobalt instance.")

    q = str(quality or "720")
    if q not in {"144", "240", "360", "480", "720", "1080", "1440", "2160", "4320", "max"}:
        q = "720"
    payload = {
        "url": link,
        "videoQuality": q,
        "downloadMode": mode,
        "filenameStyle": "basic",
        "alwaysProxy": True,
        "youtubeVideoCodec": "h264",
        "disableMetadata": False,
        "youtubeHLS": True,
    }
    r = requests.post(COBALT_API_URL + "/", json=payload, headers=_cobalt_headers(), timeout=COBALT_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    status = data.get("status")

    if status == "error":
        err = data.get("error") or {}
        code = err.get("code", "unknown") if isinstance(err, dict) else str(err)
        context = err.get("context", {}) if isinstance(err, dict) else {}
        limit = context.get("limit") if isinstance(context, dict) else None
        extra = f" (limit: {limit}s)" if limit else ""
        raise RuntimeError(f"Cobalt error: {code}{extra}")

    items = []
    if status in {"tunnel", "redirect"} and data.get("url"):
        items = [{"type": "video", "url": data["url"], "filename": data.get("filename") or "download.mp4"}]
    elif status == "picker":
        items = list(data.get("picker") or [])
        if not items:
            raise RuntimeError("Cobalt returned an empty media picker.")
    else:
        raise RuntimeError(f"Unsupported Cobalt response: {status}")

    saved = []
    for index, item in enumerate(items[:20]):
        url = item.get("url")
        if not url:
            continue
        kind = item.get("type", "video")
        filename = item.get("filename") or os.path.basename(url.split("?", 1)[0]) or f"media_{index}.mp4"
        filename = re.sub(r"[^A-Za-z0-9._-]+", "_", filename)[:180] or f"media_{index}.mp4"
        ext = os.path.splitext(filename)[1].lower()
        if not ext:
            ext = {"photo": ".jpg", "gif": ".gif", "video": ".mp4"}.get(kind, ".mp4")
            filename += ext
        path = os.path.join(tmp_dir, f"{index:02d}_{filename}")

        with requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=COBALT_TIMEOUT) as dl:
            dl.raise_for_status()
            total = 0
            max_bytes = max(1, MAX_UPLOAD_MB) * 1024 * 1024
            with open(path, "wb") as f:
                for chunk in dl.iter_content(chunk_size=1024 * 256):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > max_bytes:
                        raise RuntimeError(f"Downloaded file is larger than Telegram limit ({MAX_UPLOAD_MB} MB).")
                    f.write(chunk)
        saved.append(path)
    if not saved:
        raise RuntimeError("Cobalt returned no downloadable media.")
    return saved


def _cobalt_health():
    if not _cobalt_enabled():
        return False, "COBALT_API_URL is not configured."
    try:
        r = requests.get(COBALT_API_URL + "/", headers=_cobalt_headers(), timeout=15)
        r.raise_for_status()
        data = r.json()
        c = data.get("cobalt", {})
        services = c.get("services") or []
        return True, f"Cobalt {c.get('version','unknown')} • {len(services)} services • duration limit {c.get('durationLimit','?')}s"
    except Exception as e:
        return False, str(e)[:180]


def _is_trial_active(uid):
    """True only while the current Premium access came from a trial campaign."""
    uid=str(uid); u=users.get(uid,{})
    if not u.get("trial_used"): return False
    until=u.get("premium_until")
    try:
        dt=until if isinstance(until,datetime) else datetime.fromisoformat(str(until).replace("Z","+00:00"))
        if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
        return dt > datetime.now(timezone.utc)
    except Exception:
        return False

def _download_max_mb(uid, platform=None, link=None):
    """Return the admin-controlled upload ceiling. 0 means Unlimited."""
    uid=str(uid); platform=platform or ""
    # Quick Access is explicitly unlimited: no artificial MB ceiling for any platform.
    if is_quick_access(uid):
        return 0
    if is_admin(uid):
        return max(1,int(get_setting("admin_max_mb",2048) or 2048))
    if platform == "youtube" or (link and detect_platform(link) == "youtube"):
        if users.get(uid,{}).get("youtube_30m"):
            return max(1,int(get_setting("youtube_special_max_mb",49) or 49))
        if _is_trial_active(uid):
            v=int(get_setting("trial_youtube_max_mb",TRIAL_YOUTUBE_MAX_MB_DEFAULT) or 0)
            return v
        if is_premium(uid):
            v=int(get_setting("premium_youtube_max_mb",PREMIUM_YOUTUBE_MAX_MB_DEFAULT) or 0)
            return v
        return max(1,int(get_setting("free_youtube_max_mb",FREE_YOUTUBE_MAX_MB_DEFAULT) or FREE_YOUTUBE_MAX_MB_DEFAULT))
    if _is_trial_active(uid):
        return max(1,int(get_setting("trial_max_mb",49) or 49))
    if is_premium(uid):
        return max(1,int(get_setting("premium_max_mb",49) or 49))
    return max(1,int(get_setting("free_max_mb",49) or 49))

def _download_max_mb_label(uid):
    if _is_trial_active(uid): return "TRIAL"
    return "PREMIUM" if is_premium(uid) else "FREE"

def _safe_send_file(chat_id, path, caption="", reply_markup=None, platform=None, link=None):
    size_mb = os.path.getsize(path) / (1024 * 1024)
    max_mb = _download_max_mb(chat_id, platform=platform, link=link)
    if max_mb > 0 and size_mb > max_mb:
        raise RuntimeError(f"Telegram upload limit exceeded: {size_mb:.1f} MB > {max_mb} MB. Choose a lower quality/smaller media.")
    with open(path, "rb") as f:
        if _is_image_file(path):
            bot.send_photo(chat_id, f, caption=caption, reply_markup=reply_markup)
        elif _is_video_file(path):
            bot.send_video(chat_id, f, caption=caption, supports_streaming=True, reply_markup=reply_markup)
        elif _is_audio_file(path):
            bot.send_audio(chat_id, f, caption=caption, reply_markup=reply_markup)
        else:
            bot.send_document(chat_id, f, caption=caption, reply_markup=reply_markup)

def _collect_downloaded_files(tmp_dir):
    out = []
    for root, _, names in os.walk(tmp_dir):
        for name in names:
            path = os.path.join(root, name)
            if os.path.isfile(path) and not name.endswith(('.part', '.ytdl', '.temp')):
                out.append(path)
    return sorted(out, key=lambda p: os.path.getmtime(p))

def send_action(chat_id, action):
    try:
        bot.send_chat_action(chat_id, action)
    except Exception:
        pass

def start_action_heartbeat(chat_id, action, stop_event):
    """Telegram chat actions expire quickly; refresh them while work is running."""
    def worker():
        while not stop_event.is_set():
            send_action(chat_id, action)
            stop_event.wait(4)
    t=threading.Thread(target=worker,daemon=True); t.start(); return t

def _send_action_for_file(chat_id, path):
    """Show Telegram's native upload action immediately before each upload."""
    if _is_video_file(path):
        send_action(chat_id, "upload_video")
    elif _is_audio_file(path):
        send_action(chat_id, "upload_audio")
    elif _is_image_file(path):
        send_action(chat_id, "upload_photo")
    else:
        send_action(chat_id, "upload_document")

def is_premium(uid):
    data = users.get(str(uid), {})
    until = data.get("premium_until")
    if not until:
        return False
    try:
        if isinstance(until, datetime):
            dt = until
        else:
            dt = datetime.fromisoformat(str(until).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt > datetime.now(timezone.utc)
    except Exception:
        return False

def premium_until_text(uid):
    until = users.get(str(uid), {}).get("premium_until")
    if not until:
        return "Not active"
    try:
        dt = until if isinstance(until, datetime) else datetime.fromisoformat(str(until).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return local_datetime_text(uid, dt)
    except Exception:
        return str(until)

def youtube_is_short(link, info=None):
    """Return True for YouTube Shorts URLs or metadata identified as a short."""
    try:
        low = (link or "").lower()
        if re.search(r"(?:youtube\.com/(?:shorts|shorts/)|youtube\.com/shorts/)", low):
            return True
        if info:
            url = str(info.get("webpage_url") or info.get("original_url") or "").lower()
            if "/shorts/" in url:
                return True
            if info.get("ie_key", "").lower() == "youtube" and info.get("channel_is_verified") is not None:
                # Do not infer a Short only from duration; many normal videos are <60s.
                pass
    except Exception:
        pass
    return False


def _quality_format(uid, quality=None):
    if (is_quick_access(uid) or is_premium(uid) or _is_trial_active(uid)) and quality in PREMIUM_QUALITY_FORMATS:
        return PREMIUM_QUALITY_FORMATS[quality]
    return FREE_QUALITY_FORMAT


def _youtube_extractor_args():
    """Build optional yt-dlp YouTube extractor arguments from environment variables."""
    args = {}
    if YOUTUBE_PLAYER_CLIENT or YOUTUBE_PO_TOKEN:
        client = YOUTUBE_PLAYER_CLIENT or "mweb"
        yt_args = {"player_client": [client]}
        if YOUTUBE_PO_TOKEN:
            yt_args["po_token"] = [f"{client}.player+{YOUTUBE_PO_TOKEN}"]
        args["youtube"] = yt_args
    return args


def _youtube_duration_filter(max_duration):
    """Reject YouTube entries above the configured duration without a second metadata request."""
    def _filter(info, *, incomplete=False):
        if incomplete:
            return None
        duration = info.get("duration")
        if duration and duration > max_duration:
            return f"YouTube video is too long. Maximum is {max_duration // 60} minutes."
        return None
    return _filter


def _instagram_opts(base_opts):
    """Options that make Instagram extraction more resilient to current API changes."""
    opts = dict(base_opts)
    # Current yt-dlp Instagram extractor uses the web app ID by default and has a
    # GraphQL logged-out fallback. Keeping the explicit web app ID avoids old
    # installations accidentally selecting an unsupported app ID.
    opts["extractor_args"] = {"instagram": {"app_id": ["web"]}}
    opts["noplaylist"] = True
    return opts


def _is_retryable_instagram_error(exc):
    text = str(exc).lower()
    markers = (
        "http error 404", "video info extraction failed", "no csrf token",
        "requested content is not available", "rate-limit", "login required",
        "unable to extract", "instagram api is not granting access",
    )
    return any(x in text for x in markers)


def _youtube_ffmpeg_available():
    try: return bool(shutil.which("ffmpeg"))
    except Exception: return False

def _youtube_direct_formats(quality):
    target=int(quality or 720)
    if _youtube_ffmpeg_available():
        return [f"bestvideo[height<={target}]+bestaudio/best[height<={target}]/best", f"best[height<={target}]/best"]
    return [f"best[height<={target}]/best"]

def _pinterest_direct_media(link, tmp_dir):
    """Best-effort Pinterest fallback using public page metadata.
    Returns downloaded image/video files, one file per discovered media URL.
    """
    headers={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36","Accept":"text/html,application/xhtml+xml"}
    r=requests.get(link,headers=headers,timeout=20,allow_redirects=True)
    r.raise_for_status()
    html_text=r.text or ""
    urls=[]
    # Prefer playable video metadata, then image metadata.
    patterns=[
        (r'<meta[^>]+property=["\']og:video(?::secure_url)?["\'][^>]+content=["\']([^"\']+)',"video"),
        (r'<meta[^>]+name=["\']twitter:player:stream["\'][^>]+content=["\']([^"\']+)',"video"),
        (r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',"image"),
        (r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)',"image"),
    ]
    for pat,kind in patterns:
        for m in re.finditer(pat,html_text,re.I):
            u=html.unescape(m.group(1)).replace("\\/","/")
            u=urllib.parse.unquote(u)
            if u.startswith("http") and u not in {x[0] for x in urls}: urls.append((u,kind))
    saved=[]
    for idx,(u,kind) in enumerate(urls[:20]):
        try:
            rr=requests.get(u,headers={"User-Agent":"Mozilla/5.0","Referer":"https://www.pinterest.com/"},stream=True,timeout=40)
            rr.raise_for_status()
            ctype=(rr.headers.get("content-type") or "").lower()
            ext=".mp4" if kind=="video" or "video/" in ctype else ".jpg"
            path=os.path.join(tmp_dir,f"pinterest_{idx}{ext}")
            total=0
            with open(path,"wb") as f:
                for chunk in rr.iter_content(1024*512):
                    if not chunk: continue
                    total += len(chunk)
                    if total > 4*1024*1024*1024:
                        raise RuntimeError("Pinterest media is too large")
                    f.write(chunk)
            if os.path.getsize(path)>1000:
                saved.append(path)
        except Exception as e:
            print("Pinterest metadata media download failed:",repr(e))
    return saved

def _resolve_pinterest_link(link):
    """Resolve Pinterest short links before extraction; yt-dlp is much more reliable on the final pin URL."""
    try:
        text=(link or "").strip()
        parsed=urllib.parse.urlparse(text if "://" in text else "https://"+text)
        host=(parsed.netloc or "").lower().split(":",1)[0]
        if host in {"pin.it","www.pin.it"}:
            r=requests.get(text,headers={"User-Agent":"Mozilla/5.0"},allow_redirects=True,timeout=15)
            if r.url and detect_platform(r.url)=="pinterest":
                return r.url
    except Exception as e:
        print("Pinterest short-link resolve failed:",repr(e))
    return link


def _run_ytdlp_download(link, tmp_dir, platform, fmt, base_opts, max_duration, uid=None, quality=None):
    """yt-dlp fallback downloader used after the configured API providers."""
    common=dict(base_opts); common["outtmpl"]=os.path.join(tmp_dir,"%(id)s.%(ext)s"); common["merge_output_format"]="mp4"
    common.pop("max_filesize",None); common["overwrites"]=False; common["continuedl"]=True; common["ignoreerrors"]=False; common["noplaylist"]=(False if platform=="tiktok" else True)
    common["retries"]=10; common["fragment_retries"]=10; common["extractor_retries"]=5; common["sleep_interval_requests"]=0
    attempts=[]
    if platform=="youtube":
        for client in (None,"mweb","web_safari","android"):
            for yfmt in _youtube_direct_formats(quality):
                o=dict(common); o["format"]=yfmt; o["match_filter"]=_youtube_duration_filter(max_duration)
                if client:
                    o["extractor_args"]={"youtube":{"player_client":[client]}}
                else:
                    extra_args=_youtube_extractor_args()
                    if extra_args: o["extractor_args"]=extra_args
                attempts.append(o)
    else:
        # Different extractors expose different media shapes. Try a small,
        # deliberate format ladder so image posts, audio-only services and
        # separate video/audio streams all have a working fallback.
        if platform == "soundcloud":
            format_ladder = ["bestaudio/best", "best"]
        elif platform == "twitch":
            format_ladder = ["best", "bestvideo*+bestaudio/best"]
        elif platform == "pinterest":
            # Pinterest may expose either a video stream, a combined stream, or an image pin.
            format_ladder = ["bestvideo*+bestaudio/best", "best", "bestvideo*/best", "bestimage/best"]
        else:
            format_ladder = [fmt, "best", "bestvideo*+bestaudio/best", "bestvideo*/best"]
        for chosen in format_ladder:
            o=dict(common); o["format"]=chosen
            if platform=="instagram": o=_instagram_opts(o)
            attempts.append(o)
            if platform=="instagram" and o.get("cookiefile"):
                public_opts=dict(o); public_opts.pop("cookiefile",None); attempts.append(public_opts)
    last_error=None
    for idx,opts in enumerate(attempts):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl: return ydl.extract_info(link,download=True)
        except Exception as exc:
            last_error=exc; print(f"yt-dlp attempt {idx+1}/{len(attempts)} failed [{platform}]:",repr(exc))
            # Instagram gets an additional public-session retry. Other
            # extractors continue through the format ladder instead of failing
            # after the first unavailable format.
            if platform=="instagram" and idx+1 < len(attempts):
                continue
    raise last_error or RuntimeError("yt-dlp download failed")

def download_media(chat_id, link, message_id, quality=None):
    platform=detect_platform(link)
    if platform=="unknown":
        supported=", ".join(premium_platform_names())
        bot.edit_message_text(f"❌ Unsupported or invalid link.\n\n🌐 Supported Premium/Trial platforms ({len(premium_platform_names())}): {html.escape(supported)}",chat_id,message_id,parse_mode="HTML"); return
    uid=str(chat_id)
    quick=is_quick_access(uid)
    trial=_is_trial_active(uid)
    premium=is_premium(uid)
    priority=quick or premium or trial
    max_seconds=_download_limit_seconds(uid)
    quality=quality or (users.get(uid,{}).get("premium_quality") if priority else "720") or ("1080" if quick else "720")
    tmp=os.path.join("downloads",uuid.uuid4().hex); os.makedirs(tmp,exist_ok=True)
    try:
        bot.edit_message_text("⚡ <b>Quick Access — preparing download...</b>" if quick else ("🚀 <b>Priority download — preparing...</b>" if priority else "✍️ Preparing download..."),chat_id,message_id,parse_mode="HTML")
    except: pass
    action_stop=threading.Event()
    action_thread=start_action_heartbeat(chat_id,"typing",action_stop)
    try:
        media=[]
        provider="yt-dlp"
        if platform == "pinterest":
            link = _resolve_pinterest_link(link)
        # YouTube: RapidAPI is the primary downloader when configured; yt-dlp remains
        # as a local fallback so the bot can still work if RapidAPI is unavailable.
        if platform=="youtube" and RAPIDAPI_YT_KEY:
            try:
                media=_rapid_download(link,tmp,quality,max_seconds,chat_id=chat_id); provider="rapidapi-youtube"
            except Exception as e:
                print("RapidAPI YouTube fallback:",repr(e))
        if not media and platform=="instagram" and _instagram_api_enabled():
            try:
                media=_instagram_api_download(link,tmp); provider="rapidapi-instagram"
            except Exception as e:
                print("RapidAPI Instagram fallback:",repr(e))
        # Pinterest direct page fallback: many pins expose the playable video or
        # image in OpenGraph metadata even when yt-dlp cannot parse the page.
        if not media and platform == "pinterest":
            try:
                media = _pinterest_direct_media(link, tmp)
                if media:
                    provider = "pinterest-og"
            except Exception as e:
                print("Pinterest direct metadata fallback:", repr(e))
        # Cobalt is also useful for Pinterest: current Cobalt builds explicitly
        # support Pinterest photos, GIFs and videos. Keep it as a fallback so
        # Pinterest gets another extractor instead of stopping at yt-dlp.
        if not media and _cobalt_enabled():
            try:
                media=_cobalt_process(link,tmp,quality=quality); provider="cobalt"
            except Exception as e: print(f"Cobalt {platform} fallback:",repr(e))
        if not media:
            cookie_args={}
            if YTDLP_COOKIES_FILE and os.path.isfile(YTDLP_COOKIES_FILE):
                cookie_args["cookiefile"]=YTDLP_COOKIES_FILE
            opts={
                "quiet":True,"no_warnings":True,"noplaylist":True,
                "retries":12 if quick else 8,"fragment_retries":12 if quick else 8,"extractor_retries":7 if quick else 5,
                "socket_timeout":45 if quick else 60,
                "http_headers":{"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36"},
                "concurrent_fragment_downloads":32 if is_quick_access(uid) else (16 if premium or _is_trial_active(uid) else 2),
                "http_chunk_size": 16 * 1024 * 1024 if is_quick_access(uid) else (10 * 1024 * 1024 if premium or _is_trial_active(uid) else 2 * 1024 * 1024),
                "buffersize": 4 * 1024 * 1024 if is_quick_access(uid) else (2 * 1024 * 1024 if premium or _is_trial_active(uid) else 1024 * 1024),
                "ratelimit": None,
                **cookie_args
            }
            fmt=_quality_format(uid,quality)
            if platform in {"tiktok","instagram","facebook","pinterest","snapchat","twitter"}:
                fmt="bestvideo*+bestaudio/best"
            info=_run_ytdlp_download(link,tmp,platform,fmt,opts,max_seconds,uid=uid,quality=quality)
            media=[p for p in _collect_downloaded_files(tmp) if _is_image_file(p) or _is_video_file(p) or _is_audio_file(p)]
        # Pinterest often exposes image pins separately from video pins. If the
        # first extractor pass produced nothing, retry with Pinterest's native
        # best-image/best-video ladder before reporting failure.
        if not media and platform == "pinterest":
            try:
                pin_opts=dict(opts)
                pin_opts["format"]="bestimage/bestvideo*+bestaudio/bestvideo*/best"
                pin_opts["outtmpl"]=os.path.join(tmp,"%(id)s.%(ext)s")
                info=_run_ytdlp_download(link,tmp,platform,pin_opts["format"],pin_opts,max_seconds,uid=uid,quality=quality)
                media=[p for p in _collect_downloaded_files(tmp) if _is_image_file(p) or _is_video_file(p) or _is_audio_file(p)]
            except Exception as e:
                print("Pinterest second-pass failed:",repr(e))
        if not media: raise RuntimeError("No downloadable media was produced.")
        sent=0
        for path in media[:50 if platform=="tiktok" else 20]:
            markup=None
            if _is_video_file(path):
                token=uuid.uuid4().hex[:24]; music_pending[token]={"uid":uid,"link":link,"created":time.time()}; markup=InlineKeyboardMarkup(row_width=1)
                markup.add(InlineKeyboardButton("🎵 MUSIC",callback_data=f"music:{token}"))
            _send_action_for_file(chat_id,path)
            _safe_send_file(chat_id,path,DOWNLOAD_CAPTION,reply_markup=markup,platform=platform,link=link); sent+=1
        try: bot.delete_message(chat_id,message_id)
        except: pass
        videos_data["total"]=videos_data.get("total",0)+sent; videos_data.setdefault("platforms",{}).setdefault(platform,0); videos_data["platforms"][platform]+=sent; videos_data.setdefault("users",{}).setdefault(uid,0); videos_data["users"][uid]+=sent; save_videos(); log_activity(uid,"download",{"platform":platform,"count":sent,"provider":provider})
    except Exception as e:
        print(f"Download error [{platform}] {link}: {e!r}")
        msg="❌ Download failed. Please try again."
        if "too long" in str(e).lower(): msg=f"❌ {e}"
        try: bot.edit_message_text(msg,chat_id,message_id)
        except:
            try: bot.send_message(chat_id,msg)
            except: pass
    finally:
        action_stop.set()
        shutil.rmtree(tmp,ignore_errors=True)

@bot.message_handler(func=lambda m: m.text == "📡 RAPIDAPI STATUS")
def rapidapi_status_handler(m):
    if not is_admin(m.from_user.id): return
    if not RAPIDAPI_YT_KEY:
        bot.send_message(m.chat.id,"❌ RAPIDAPI_YT_KEY is not configured.")
        return
    try:
        _rapidapi_youtube_details("dQw4w9WgXcQ")
        bot.send_message(m.chat.id,"✅ RapidAPI YouTube is responding.\n🔄 If RapidAPI fails during a download, the bot will automatically try yt-dlp.")
    except Exception as e:
        bot.send_message(m.chat.id,f"❌ RapidAPI failed: {str(e)[:700]}")

@bot.message_handler(func=lambda m: m.text == "🟢 Open add group")
def admin_open_add_group(m):
    if not is_admin(m.from_user.id): return
    set_setting("add_group_enabled", True)
    bot.send_message(m.chat.id,
        "🟢 <b>ADD GROUP OPEN</b>\n\n"
        "Users will now see <b>➕ Add Group</b> under the /start welcome message and on MP3 files. "
        "They can use Telegram's <b>Select Chat</b> picker to choose their group and make this bot an administrator.",
        parse_mode="HTML", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == "🔴 Close add group")
def admin_close_add_group(m):
    if not is_admin(m.from_user.id): return
    set_setting("add_group_enabled", False)
    bot.send_message(m.chat.id,
        "🔴 <b>ADD GROUP CLOSED</b>\n\n"
        "New MP3s and the /start welcome message will no longer show the Add Group button. MP3 remains normal.",
        parse_mode="HTML", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == "🟢 Open add channel")
def admin_open_add_channel(m):
    if not is_admin(m.from_user.id): return
    set_setting("add_channel_enabled", True)
    bot.send_message(m.chat.id,
        "🟢 <b>ADD CHANNEL OPEN</b>\n\n"
        "Users will now see <b>➕ Add Channel</b> under the /start welcome message and on MP3 files. "
        "They can use Telegram's <b>Select Chat</b> picker to choose their channel and make this bot an administrator.",
        parse_mode="HTML", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == "🔴 Close add channel")
def admin_close_add_channel(m):
    if not is_admin(m.from_user.id): return
    set_setting("add_channel_enabled", False)
    bot.send_message(m.chat.id,
        "🔴 <b>ADD CHANNEL CLOSED</b>\n\n"
        "New MP3s and the /start welcome message will no longer show the Add Channel button. MP3 remains normal.",
        parse_mode="HTML", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == "🟢 Open mp3 Cover")
def admin_open_mp3_cover(m):
    if not is_admin(m.from_user.id): return
    set_setting("mp3_cover_enabled",True)
    bot.send_message(m.chat.id,"🟢 <b>MP3 COVER OPEN</b>\n\nMP3 conversion may now use the source video thumbnail when available. If a genuine music/artist cover is available, that can be used as well.",parse_mode="HTML",reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == "🔴 Close mp3 Cover")
def admin_close_mp3_cover(m):
    if not is_admin(m.from_user.id): return
    set_setting("mp3_cover_enabled",False)
    bot.send_message(m.chat.id,"🔴 <b>MP3 COVER CLOSED</b>\n\nThe source video thumbnail will not be used. The MP3 will use genuine music/artist artwork only when available.",parse_mode="HTML",reply_markup=admin_menu())

# ================= SONG SEARCH =================
def _song_search_is_open():
    return bool(get_setting("song_search_enabled", True))

def _song_search_closed_message():
    return str(get_setting("song_search_closed_message", "This is Not available Now.") or "This is Not available Now.")

def _song_duration(seconds):
    try:
        seconds = max(0, int(seconds or 0))
    except Exception:
        seconds = 0
    return f"{seconds//60}:{seconds%60:02d}"

def _song_norm(value):
    """Normalize music text for tolerant matching (case, punctuation, accents)."""
    import unicodedata
    text=_music_clean_text(value).lower()
    text=unicodedata.normalize("NFKD", text)
    text="".join(ch for ch in text if not unicodedata.combining(ch))
    text=re.sub(r"[^\w\s]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _song_similarity(query, title, artist, album=""):
    """Rank a result so artist/title matches beat unrelated keyword matches."""
    q=_song_norm(query)
    if not q: return 0
    t=_song_norm(title); a=_song_norm(artist); al=_song_norm(album)
    score=0
    if q == t: score += 1000
    if q == a: score += 950
    if q in t: score += 700
    if q in a: score += 680
    if q in al: score += 300
    qwords=[w for w in q.split() if len(w)>=2]
    if qwords:
        tw=set(t.split()); aw=set(a.split()); allw=tw|aw|set(al.split())
        hits=sum(1 for w in qwords if w in allw)
        score += hits*120
        # Prefix/fuzzy word matching is useful for partial artist/title input.
        for w in qwords:
            if any(x.startswith(w) for x in aw): score += 90
            if any(x.startswith(w) for x in tw): score += 80
    return score


def _jamendo_song_search(query, limit=100):
    """Search Jamendo aggressively while keeping only downloadable tracks.

    Jamendo supports free-text search across track/album/artist/tags plus
    dedicated name/artist searches. We combine those methods and then rank
    the returned licensed/downloadable tracks locally so queries such as
    partial artist names and partial titles behave much better.
    """
    query=_music_clean_text(query)
    if not query or not JAMENDO_CLIENT_ID:
        if not JAMENDO_CLIENT_ID:
            print("Jamendo search skipped: JAMENDO_CLIENT_ID is missing")
        return []

    base={
        "client_id":JAMENDO_CLIENT_ID,
        "format":"json",
        "limit":200,
        "imagesize":600,
        "album_imagesize":600,
        "audiodlformat":"mp32",
        "type":"single albumtrack",
        "order":"relevance",
    }

    def call(extra):
        try:
            params=dict(base); params.update(extra)
            r=requests.get("https://api.jamendo.com/v3.0/tracks/",params=params,timeout=JAMENDO_TIMEOUT)
            r.raise_for_status()
            body=r.json() or {}
            headers=body.get("headers") or {}
            if headers.get("status") not in (None,"success"):
                print("Jamendo API error:",headers)
                return []
            return body.get("results") or []
        except Exception as e:
            print("Jamendo API request failed:",repr(e))
            return []

    raw=[]; seen_raw=set()
    def add_batch(batch):
        for item in batch or []:
            if not isinstance(item,dict): continue
            iid=str(item.get("id") or "")
            if iid and iid not in seen_raw:
                seen_raw.add(iid); raw.append(item)

    # 1) Jamendo's strongest general search.
    modes=[{"search":query}]
    # 2) Dedicated track-title and artist searches.
    modes += [{"namesearch":query},{"artist_name":query}]
    # 3) Prefix/partial-word searches. This helps inputs like "central cee",
    #    "central", "cee", or a partial Somali title.
    words=[w for w in query.split() if len(w)>=2]
    for w in sorted(set(words),key=len,reverse=True)[:4]:
        modes += [{"search":w},{"namesearch":w},{"artist_name":w}]

    for mode in modes:
        # First page is normally enough because relevance ordering is retained.
        add_batch(call(mode))
        if len(raw)>=max(int(limit)*4,300): break

    # 4) Jamendo autocomplete gives exact/prefix entity names. Resolve those
    #    names back through the tracks endpoint.
    try:
        ac_params={"client_id":JAMENDO_CLIENT_ID,"format":"json","prefix":query,"limit":20,"matchcount":"true","entity":"artists tracks albums"}
        ar=requests.get("https://api.jamendo.com/v3.0/autocomplete/",params=ac_params,timeout=JAMENDO_TIMEOUT)
        ar.raise_for_status(); ac=ar.json() or {}
        for group in ac.get("results") or []:
            if isinstance(group,dict):
                name=group.get("name") or group.get("value") or group.get("text")
                if name and name.lower()!=query.lower():
                    add_batch(call({"search":str(name)}))
    except Exception as e:
        print("Jamendo autocomplete failed:",repr(e))

    rows=[]; seen=set()
    for item in raw:
        if not isinstance(item,dict): continue
        iid=str(item.get("id") or "")
        title=_music_clean_text(item.get("name"))
        artist=_music_clean_text(item.get("artist_name")) or "Unknown artist"
        album=_music_clean_text(item.get("album_name"))
        download=item.get("audiodownload") or ""
        allowed=bool(item.get("audiodownload_allowed"))
        if not iid or iid in seen or not title or not allowed or not download:
            continue
        seen.add(iid)
        try: duration=int(float(item.get("duration") or 0))
        except Exception: duration=0
        cover=item.get("album_image") or item.get("image")
        rows.append({
            "id":iid,"title":title,"artist":artist,"duration":duration,"album":album,
            "cover":cover,"download":download,"download_allowed":allowed,
            "license":item.get("license_ccurl") or "","source":"jamendo",
            "_score":_song_similarity(query,title,artist,album),
        })

    # Exact/prefix matches first; then Jamendo relevance/order as a tie-breaker.
    rows.sort(key=lambda x:(x.get("_score",0), -int(x.get("duration",0))), reverse=True)
    for x in rows: x.pop("_score",None)
    return rows[:int(limit)]

def _main_bot_username():
    global _MAIN_BOT_USERNAME_CACHE
    value=str(_MAIN_BOT_USERNAME_CACHE or "").strip().lstrip("@")
    if value: return value
    try:
        me=bot.get_me(); value=str(getattr(me,"username","") or "").strip().lstrip("@")
        if value: _MAIN_BOT_USERNAME_CACHE=value; return value
    except Exception as e: print("Main bot get_me error:",repr(e))
    return "bot"

def _default_song_caption(song):
    title=html.escape(_music_clean_text(song.get("title")) or "Unknown title"); artist=html.escape(_music_clean_text(song.get("artist")) or "Unknown artist")
    return f"🎤 <b>{artist}</b>\n🎵 <b>{title}</b>\n\n@{html.escape(_main_bot_username())}"

def _song_caption(song):
    # Music captions are intentionally bot-only. Artist/album/title stay in the
    # Telegram music metadata where supported, never in the visible caption.
    return DOWNLOAD_CAPTION

def _song_auto_search_should_handle(m):
    if not m or not getattr(m,"text",None): return False
    text=str(m.text).strip()
    if not text or text.startswith("/") or not get_setting("song_auto_search_enabled",False) or is_admin(m.from_user.id): return False
    # Never interpret text belonging to an active withdrawal/verification/payment flow as a song.
    u=users.get(str(m.from_user.id),{})
    if u.get("withdraw_flow") or u.get("temp_addr") or u.get("pending_conversion") or u.get("pending_ref"):
        return False
    excluded={
        "💰 BALANCE","💸 WITHDRAWAL","👥 REFERRAL","🆔 GET ID","💎 PREMIUM","👤 Profile",
        "☎️ CUSTOMER","🤖CUSTOMER AI","🔎 Search Song","👑 ADMIN PANEL","❌ CANCEL","📜 HISTORY",
        "USDT-BEP20","USDT-TRC20","USDT-ERC20","CANCEL","Cancel","❌ Cancel","🔙 BACK",
        "⬅️ BACK","🏠 MAIN MENU","💳 CONFIRM","✅ CONFIRM","🔐 VERIFY ACCOUNT","💎 OPEN PREMIUM",
        "🎵 MUSIC","📤 Share","➕ Add Group","➕ Add Channel"
    }
    try: excluded.update(str(x) for x in _ACTIONS.keys() if x)
    except Exception: pass
    excluded.update({
        "USDT-BEP20","USDT-TRC20","USDT-ERC20","TRX","BEP20","ERC20",
        "❌ CANCEL","❌ Cancel","CANCEL","Cancel","BACK","⬅️ BACK","🔙 BACK",
        "NEXT","PREVIOUS","➡️ NEXT","⬅️ PREVIOUS","⏮️ BACK","⏭️ NEXT"
    })
    try:
        for d in MAIN_LABELS.values(): excluded.update(str(x) for x in d.values() if x)
    except Exception: pass
    return text not in excluded

def _record_song_download(uid, song, file_bytes=None):
    """Store aggregate stats and a small per-user event record."""
    now=datetime.now(timezone.utc)
    try:
        song_stats_col.update_one(
            {"_id":str(song.get("id"))},
            {"$setOnInsert":{"title":song.get("title"),"artist":song.get("artist"),"album":song.get("album"),"source":song.get("source","jamendo")},
             "$inc":{"downloads":1}, "$set":{"last_download":now}}, upsert=True)
        activity_col.insert_one({"user_id":str(uid),"action":"song_download",
            "details":{"song_id":str(song.get("id")),"title":song.get("title"),"artist":song.get("artist"),"source":song.get("source","jamendo")},"time":now})
    except Exception as e: print("Song stats error:",repr(e))

def _song_stats_text():
    try:
        total=int(song_stats_col.aggregate([{"$group":{"_id":None,"n":{"$sum":"$downloads"}}}]).next().get("n",0)) if song_stats_col.count_documents({}) else 0
        unique=int(song_stats_col.count_documents({}))
        top=list(song_stats_col.find().sort("downloads",-1).limit(10))
        lines=["🎵 <b>SONG STATISTICS</b>","",f"⬇️ Total full-track downloads: <b>{total}</b>",f"🎼 Different tracks downloaded: <b>{unique}</b>",""]
        if top:
            lines.append("🏆 <b>TOP SONGS</b>")
            for i,x in enumerate(top,1): lines.append(f"{i}. {html.escape(str(x.get('title','Unknown')))} — {html.escape(str(x.get('artist','Unknown artist')))}: <b>{int(x.get('downloads',0))}</b>")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Could not load song statistics: {html.escape(str(e)[:300])}"

def _cleanup_song_search():
    now=time.time()
    for token,data in list(song_search_pending.items()):
        if now-data.get("created",now)>SONG_SEARCH_TTL:
            song_search_pending.pop(token,None)

def _song_results_markup(token, page, total):
    kb=InlineKeyboardMarkup(row_width=1)
    start=page*SONG_SEARCH_PAGE_SIZE
    end=min(start+SONG_SEARCH_PAGE_SIZE,total)
    data=song_search_pending.get(token,{})
    rows=data.get("results",[])
    for i in range(start,end):
        x=rows[i]
        kb.add(InlineKeyboardButton(
            f"{i+1}. {x['title'][:45]} — {x['artist'][:28]} { _song_duration(x['duration']) }",
            callback_data=f"songpick:{token}:{i}"
        ))
    nav=[]
    if page>0: nav.append(InlineKeyboardButton("⬅️ Back",callback_data=f"songpage:{token}:{page-1}"))
    if end<total: nav.append(InlineKeyboardButton("Next ➡️",callback_data=f"songpage:{token}:{page+1}"))
    if nav: kb.row(*nav)
    kb.add(InlineKeyboardButton("❌ Cancel",callback_data=f"songcancel:{token}"))
    return kb

def _send_song_results(chat_id, token, page=0, edit_message=None):
    data=song_search_pending.get(token)
    if not data: return
    rows=data.get("results",[]); total=len(rows)
    start=page*SONG_SEARCH_PAGE_SIZE; end=min(start+SONG_SEARCH_PAGE_SIZE,total)
    lines=["🔎 <b>SONG SEARCH</b>",f"<b>Search:</b> {html.escape(data.get('query',''))}",""]
    if not rows:
        lines.append("❌ No songs found.")
    else:
        lines.append(f"Showing <b>{start+1}-{end}</b> of <b>{total}</b> songs")
        for i in range(start,end):
            x=rows[i]
            lines.append(f"{i+1}. {html.escape(x['title'])} — {html.escape(x['artist'])} <code>{_song_duration(x['duration'])}</code>")
    text="\n".join(lines)
    kb=_song_results_markup(token,page,total) if rows else InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Cancel",callback_data=f"songcancel:{token}"))
    if edit_message:
        try: bot.edit_message_text(text,edit_message.chat.id,edit_message.message_id,parse_mode="HTML",reply_markup=kb); return
        except Exception: pass
    bot.send_message(chat_id,text,parse_mode="HTML",reply_markup=kb)

@bot.message_handler(func=lambda m: False)
def search_song_button(m):
    if bot_locked_guard(m) or banned_guard(m): return
    if not _song_search_is_open():
        bot.send_message(m.chat.id,_song_search_closed_message(),reply_markup=localized_user_menu(str(m.from_user.id)))
        return
    msg=bot.send_message(m.chat.id,"🔎 <b>Search Song</b>\n\nWrite the song name, part of the name, or an artist name:",parse_mode="HTML")
    bot.register_next_step_handler(msg,search_song_query_step)

def search_song_query_step(m):
    uid=str(m.from_user.id)
    if not _song_search_is_open():
        bot.send_message(m.chat.id,_song_search_closed_message()); return
    query=_music_clean_text(m.text)
    if not query:
        msg=bot.send_message(m.chat.id,"❌ Please enter a song or artist name.")
        bot.register_next_step_handler(msg,search_song_query_step); return
    bot.send_message(m.chat.id,"🔎 Searching songs...")
    rows=_jamendo_song_search(query,100)
    _cleanup_song_search()
    token=uuid.uuid4().hex[:16]
    song_search_pending[token]={"uid":uid,"query":query,"results":rows,"created":time.time()}
    if not rows:
        bot.send_message(m.chat.id,"❌ No songs found. Try another title or artist.",reply_markup=localized_user_menu(uid)); return
    _send_song_results(m.chat.id,token,0)

@bot.message_handler(func=_song_auto_search_should_handle)
def auto_song_search_handler(m):
    if bot_locked_guard(m) or banned_guard(m): return
    query=_music_clean_text(m.text)
    if not query or len(query)<2: return
    bot.send_message(m.chat.id,"🔎 Searching songs...")
    rows=_jamendo_song_search(query,100)
    _cleanup_song_search(); token=uuid.uuid4().hex[:16]
    song_search_pending[token]={"uid":str(m.from_user.id),"query":query,"results":rows,"created":time.time()}
    if not rows:
        bot.send_message(m.chat.id,"❌ No matching downloadable songs found. Try another title, artist, or part of the name.")
        return
    _send_song_results(m.chat.id,token,0)

@bot.callback_query_handler(func=lambda c: c.data.startswith("songpage:"))
def song_page_callback(call):
    parts=call.data.split(":")
    if len(parts)!=3: return
    token=parts[1]
    try: page=int(parts[2])
    except Exception: return
    _cleanup_song_search(); data=song_search_pending.get(token)
    if not data or str(data.get("uid"))!=str(call.from_user.id):
        bot.answer_callback_query(call.id,"❌ Search session expired.",show_alert=True); return
    bot.answer_callback_query(call.id)
    _send_song_results(call.message.chat.id,token,page,edit_message=call.message)

@bot.callback_query_handler(func=lambda c: c.data.startswith("songpick:"))
def song_pick_callback(call):
    parts=call.data.split(":")
    if len(parts)!=3: return
    token=parts[1]
    try: idx=int(parts[2])
    except Exception: return
    _cleanup_song_search(); data=song_search_pending.get(token)
    if not data or str(data.get("uid"))!=str(call.from_user.id):
        bot.answer_callback_query(call.id,"❌ Search session expired.",show_alert=True); return
    rows=data.get("results",[])
    if idx<0 or idx>=len(rows):
        bot.answer_callback_query(call.id,"❌ Song no longer available.",show_alert=True); return
    x=rows[idx]
    if not x.get("download_allowed") or not x.get("download"):
        bot.answer_callback_query(call.id,"❌ Full download is not allowed for this track.",show_alert=True); return
    bot.answer_callback_query(call.id,"⬇️ Downloading full song...")
    status=bot.send_message(call.message.chat.id,"⏳ Downloading the full track...")
    download_executor_for(call.from_user.id).submit(_download_jamendo_song,call.message.chat.id,status.message_id,x,str(call.from_user.id))

def _download_jamendo_song(chat_id,status_id,song,uid):
    tmp=None
    try:
        title=_music_clean_text(song.get("title")) or "Unknown title"; artist=_music_clean_text(song.get("artist")) or "Unknown artist"; url=song.get("download")
        if not url or not song.get("download_allowed"): raise RuntimeError("Track is not downloadable")
        bot.edit_message_text("⏳ <b>Downloading music...</b>",chat_id,status_id,parse_mode="HTML")
        r=requests.get(url,headers={"User-Agent":"Downloadvedioytibot/1.0"},timeout=60,stream=True); r.raise_for_status()
        tmp=os.path.join("downloads","jamendo_"+uuid.uuid4().hex); os.makedirs(tmp,exist_ok=True); path=os.path.join(tmp,_music_safe_filename(title,artist))
        with open(path,"wb") as f:
            for chunk in r.iter_content(1024*256):
                if chunk: f.write(chunk)
        cover=_music_download_image(song["cover"],tmp,"cover.jpg") if song.get("cover") else None
        _embed_music_metadata(path,title,artist,cover_path=cover,album=song.get("album"))
        bot.edit_message_text("🎵 <b>Sending music...</b>",chat_id,status_id,parse_mode="HTML")
        kwargs={"caption":_song_caption(song),"parse_mode":"HTML","title":title,"performer":artist,"duration":int(song.get("duration") or 0)}
        with open(path,"rb") as audio:
            if cover and os.path.isfile(cover): kwargs["thumb"]=cover
            try: bot.send_audio(chat_id,audio,**kwargs)
            except Exception:
                kwargs.pop("thumb",None); audio.seek(0); bot.send_audio(chat_id,audio,**kwargs)
        _record_song_download(uid,song)
        try: bot.delete_message(chat_id,status_id)
        except Exception: pass
    except Exception as e:
        print("Jamendo download error:",repr(e))
        try: bot.edit_message_text("❌ Music could not be sent. Please try another track.",chat_id,status_id)
        except Exception: pass
    finally:
        if tmp: shutil.rmtree(tmp,ignore_errors=True)

@bot.callback_query_handler(func=lambda c: c.data.startswith("songcancel:"))
def song_cancel_callback(call):
    token=call.data.split(":",1)[1]
    data=song_search_pending.get(token,{})
    if data and str(data.get("uid"))!=str(call.from_user.id):
        bot.answer_callback_query(call.id,"❌ This search belongs to another user.",show_alert=True); return
    song_search_pending.pop(token,None)
    bot.answer_callback_query(call.id,"Search closed")
    try: bot.delete_message(call.message.chat.id,call.message.message_id)
    except Exception: pass

# ================= MUSIC / MP3 CONVERTER =================
def _music_clean_text(value):
    if value is None:
        return ""
    value = str(value).strip()
    if not value:
        return ""
    value = re.sub(r"\s+", " ", value)
    return value


def _music_is_original_label(value):
    value = _music_clean_text(value).lower()
    if not value:
        return False
    return value in {
        "original", "original sound", "original audio", "original music",
        "original sound -", "original audio -", "original sound by"
    } or value.startswith("original sound") or value.startswith("original audio")


def _music_source_account_names(info):
    """Names that belong to the account/video uploader, not necessarily the music artist."""
    info = info or {}
    names = set()
    for key in ("uploader", "uploader_id", "creator", "creator_id", "channel", "channel_id"):
        value = info.get(key)
        if isinstance(value, str):
            value = _music_clean_text(value)
            if value:
                names.add(value.casefold().lstrip("@"))
    return names


def _music_artist_from_info(info):
    """Return explicit music-artist metadata without mistaking a lone uploader for the artist."""
    info = info or {}
    account_names = _music_source_account_names(info)
    candidates = []

    for key in ("artist", "track_artist", "album_artist"):
        value = _music_clean_text(info.get(key))
        if value and not _music_is_original_label(value):
            candidates.append(value)

    artists = info.get("artists")
    if isinstance(artists, list):
        names = []
        for item in artists:
            if isinstance(item, dict):
                value = _music_clean_text(item.get("name") or item.get("artist") or item.get("title"))
            else:
                value = _music_clean_text(item)
            if value and not _music_is_original_label(value):
                names.append(value)
        if names:
            candidates.append(", ".join(names))

    for value in candidates:
        cleaned = _music_normalize_artist_names(value)
        if not cleaned:
            continue
        pieces = [p.strip() for p in cleaned.split(",") if p.strip()]
        # If the source explicitly identifies multiple music artists, trust that
        # structured collaboration even when one of them is also the uploader.
        if len(pieces) > 1:
            return ", ".join(pieces)
        # A single name equal to the video account is not enough proof that it is
        # the music artist. Recognition/streaming metadata can confirm it later.
        if pieces[0].casefold().lstrip("@") not in account_names:
            return pieces[0]
    return ""

def _music_normalize_artist_names(value):
    value = _music_clean_text(value)
    if not value:
        return ""
    value = re.sub(r"\s+(?:feat\.?|ft\.?|featuring)\s+", ", ", value, flags=re.I)
    value = re.sub(r"\s+[&+]\s+", ", ", value)
    parts = [p.strip() for p in re.split(r"\s*[,;|/]\s*", value) if p.strip()]
    # Remove duplicate names while preserving the official order.
    seen = set(); out = []
    for p in parts:
        key = p.casefold()
        if key not in seen:
            seen.add(key); out.append(p)
    return ", ".join(out)

def _music_title_from_info(info):
    info = info or {}
    for key in ("track", "song", "track_name", "title", "fulltitle"):
        value = _music_clean_text(info.get(key))
        if value and not _music_is_original_label(value):
            return value
    return ""


def _music_download_image(url, tmp_dir, filename="cover.jpg"):
    url = _music_clean_text(url)
    if not url or not re.match(r"^https?://", url, re.I):
        return None
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        r.raise_for_status()
        data = r.content
        if len(data) < 1000:
            return None
        raw = os.path.join(tmp_dir, "raw_" + filename)
        with open(raw, "wb") as f:
            f.write(data)
        try:
            from PIL import Image
            img = Image.open(raw).convert("RGB")
            out = os.path.join(tmp_dir, filename)
            img.thumbnail((640, 640))
            img.save(out, "JPEG", quality=92, optimize=True)
            return out
        except Exception:
            return raw
    except Exception as e:
        print("Music artwork download failed:", repr(e))
        return None


def _music_musicbrainz_recording_lookup(recording_id):
    """Resolve an exact MusicBrainz recording returned by AcoustID.

    This is intentionally ID-based rather than title-search-based, so the artist
    and artwork belong to the fingerprinted recording instead of the uploader.
    """
    recording_id = _music_clean_text(recording_id)
    if not recording_id:
        return {}
    try:
        r = requests.get(
            f"https://musicbrainz.org/ws/2/recording/{urllib.parse.quote(recording_id, safe='')}",
            params={"fmt": "json", "inc": "artists+releases"},
            headers={"User-Agent": "Downloadvedioytibot/1.0 (music metadata)"},
            timeout=15,
        )
        r.raise_for_status()
        item = r.json() or {}

        title = _music_clean_text(item.get("title"))
        artists = []
        for credit in item.get("artist-credit") or []:
            if isinstance(credit, dict) and isinstance(credit.get("artist"), dict):
                name = _music_clean_text(credit["artist"].get("name"))
                if name:
                    artists.append(name)

        album = ""
        artwork_candidates = []
        releases = item.get("releases") or []
        for release in releases:
            if not isinstance(release, dict):
                continue
            release_title = _music_clean_text(release.get("title"))
            if release_title and not album:
                album = release_title
            release_id = _music_clean_text(release.get("id"))
            if release_id:
                # Cover Art Archive is the real release artwork, not a video frame.
                artwork_candidates.append(
                    f"https://coverartarchive.org/release/{release_id}/front-500"
                )

        return {
            "title": title,
            "artist": ", ".join(dict.fromkeys(artists)),
            "album": album,
            "artwork_candidates": artwork_candidates,
            "recording_id": recording_id,
        }
    except Exception as e:
        print("Exact MusicBrainz recording lookup failed:", repr(e))
        return {}


def _music_recognize_acoustid(mp3_path):
    """Identify a full audio file with AcoustID/Chromaprint.

    AcoustID itself supplies the fingerprint match and MusicBrainz IDs.
    MusicBrainz + Cover Art Archive are then used for exact artist/title/album
    metadata and genuine release artwork.
    """
    if not ACOUSTID_API_KEY or not mp3_path or not os.path.isfile(mp3_path):
        return {}

    try:
        import acoustid

        # AcoustID is designed around full audio files.  pyacoustid uses
        # Chromaprint/fpcalc and limits fingerprint generation to 120 seconds.
        duration, fingerprint = acoustid.fingerprint_file(mp3_path, maxlength=120)

        response = requests.post(
            "https://api.acoustid.org/v2/lookup",
            data={
                "client": ACOUSTID_API_KEY,
                "duration": int(round(duration)),
                "fingerprint": fingerprint,
                "meta": "recordings+releasegroups+compress",
                "format": "json",
            },
            timeout=ACOUSTID_TIMEOUT,
        )
        response.raise_for_status()
        body = response.json() if response.content else {}
        if not isinstance(body, dict) or body.get("status") != "ok":
            return {}

        results = body.get("results") or []
        if not results:
            return {}

        # Prefer the strongest match that actually has a MusicBrainz recording.
        candidates = []
        for result in results:
            if not isinstance(result, dict):
                continue
            score = float(result.get("score") or 0)
            for rec in result.get("recordings") or []:
                if isinstance(rec, dict) and rec.get("id"):
                    candidates.append((score, rec))
        candidates.sort(key=lambda x: x[0], reverse=True)

        for score, rec in candidates:
            if score < 0.50:
                continue
            meta = _music_musicbrainz_recording_lookup(rec.get("id"))
            if not meta.get("title"):
                continue
            return {
                "title": meta.get("title"),
                "artist": meta.get("artist"),
                "album": meta.get("album"),
                "artwork": (meta.get("artwork_candidates") or [None])[0],
                "artwork_candidates": meta.get("artwork_candidates") or [],
                "recording_id": meta.get("recording_id"),
                "score": score,
                "source": "acoustid",
            }

        return {}
    except Exception as e:
        # Do not break MP3 conversion if fingerprinting is unavailable.
        print("AcoustID recognition skipped:", repr(e))
        return {}


def _music_recognize_audd(mp3_path):
    """Optional audio fingerprinting. Returns title/artist/album/artwork when recognized."""
    if not AUDD_API_TOKEN or not mp3_path or not os.path.isfile(mp3_path):
        return {}
    try:
        with open(mp3_path, "rb") as audio:
            r = requests.post(
                "https://api.audd.io/",
                data={"api_token": AUDD_API_TOKEN, "return": "apple_music,spotify"},
                files={"file": (os.path.basename(mp3_path), audio, "audio/mpeg")},
                timeout=45,
            )
        body = r.json() if r.content else {}
        result = body.get("result") if isinstance(body, dict) else None
        if not isinstance(result, dict):
            return {}
        apple = result.get("apple_music") if isinstance(result.get("apple_music"), dict) else {}
        artwork = None
        for source in (apple, result):
            if not isinstance(source, dict):
                continue
            for key in ("artwork", "artworkUrl100", "artworkUrl600", "cover", "cover_url"):
                candidate = source.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    artwork = candidate.strip()
                    break
            if artwork:
                break
        artist = _music_clean_text(result.get("artist") or result.get("artist_name"))
        title = _music_clean_text(result.get("title") or result.get("track"))
        album = _music_clean_text(result.get("album"))
        return {"title": title, "artist": artist, "album": album, "artwork": artwork}
    except Exception as e:
        print("Audio recognition skipped:", repr(e))
        return {}


def _music_musicbrainz_lookup(title, artist=""):
    """Use MusicBrainz as a second independent source for real song credits."""
    title = _music_clean_text(title)
    artist = _music_clean_text(artist)
    if not title or _music_is_original_label(title):
        return {}
    try:
        params = {"query": f'recording:"{title}"', "fmt": "json", "limit": 10}
        if artist and artist.lower() != "unknown artist":
            params["query"] = f'recording:"{title}" AND artist:"{artist}"'
        r = requests.get(
            "https://musicbrainz.org/ws/2/recording",
            params=params,
            headers={"User-Agent": "Downloadvedioytibot/1.0 (music metadata)"},
            timeout=12,
        )
        r.raise_for_status()
        recordings = r.json().get("recordings") or []
        if not recordings:
            return {}

        q = title.casefold()
        wanted_artists = {x.casefold() for x in _music_normalize_artist_names(artist).split(",") if x.strip()}
        best = None; best_score = -1
        for item in recordings:
            name = _music_clean_text(item.get("title"))
            if not name:
                continue
            score = 0
            nq = name.casefold()
            if nq == q:
                score += 20
            elif q in nq or nq in q:
                score += 10
            credits = []
            for ac in item.get("artist-credit") or []:
                if isinstance(ac, dict) and isinstance(ac.get("artist"), dict):
                    nm = _music_clean_text(ac["artist"].get("name"))
                    if nm:
                        credits.append(nm)
            if wanted_artists and any(a in wanted_artists for a in {x.casefold() for x in credits}):
                score += 10
            if credits:
                score += 2
            if score > best_score:
                best_score = score
                best = (item, credits)
        if not best or best_score < 10:
            return {}
        item, credits = best
        result = {
            "title": _music_clean_text(item.get("title")),
            "artist": ", ".join(credits),
            "album": "",
            "artwork": None,
        }
        releases = item.get("releases") or []
        if releases and isinstance(releases[0], dict):
            release_id = releases[0].get("id")
            result["album"] = _music_clean_text(releases[0].get("title"))
            if release_id:
                # Cover Art Archive's front endpoint returns the actual release artwork.
                result["artwork"] = f"https://coverartarchive.org/release/{release_id}/front-500"
        return result
    except Exception as e:
        print("MusicBrainz lookup failed:", repr(e))
        return {}


def _music_deezer_lookup(title, artist=""):
    """Use Deezer's public search API for song title, artist and genuine album art."""
    title = _music_clean_text(title)
    artist = _music_clean_text(artist)
    if not title or _music_is_original_label(title):
        return {}
    queries = []
    if artist and artist.lower() != "unknown artist":
        queries.append(f'artist:"{artist}" track:"{title}"')
        queries.append(f"{artist} {title}")
    queries.append(title)
    for query in queries:
        try:
            r = requests.get(
                "https://api.deezer.com/search",
                params={"q": query, "limit": 10},
                headers={"User-Agent": "Mozilla/5.0"}, timeout=12,
            )
            r.raise_for_status()
            rows = (r.json() or {}).get("data") or []
            if not rows:
                continue
            q = title.casefold()
            a = artist.casefold()
            def score(item):
                st = _music_clean_text(item.get("title")).casefold()
                sa = _music_clean_text((item.get("artist") or {}).get("name")).casefold()
                score = 0
                if st == q: score += 20
                elif q in st or st in q: score += 10
                if a and a != "unknown artist" and (a == sa or a in sa): score += 10
                if item.get("album", {}).get("cover_xl") or item.get("album", {}).get("cover_big"): score += 2
                return score
            best = max(rows, key=score)
            if score(best) < 10:
                continue
            return {
                "title": _music_clean_text(best.get("title")),
                "artist": _music_clean_text((best.get("artist") or {}).get("name")),
                "album": _music_clean_text((best.get("album") or {}).get("title")),
                "artwork": (best.get("album") or {}).get("cover_xl") or (best.get("album") or {}).get("cover_big"),
            }
        except Exception as e:
            print("Deezer music lookup failed:", repr(e))
    return {}


def _music_itunes_lookup(title, artist=""):
    """Find the closest real song in iTunes metadata without using video thumbnails."""
    title = _music_clean_text(title)
    artist = _music_clean_text(artist)
    if not title or _music_is_original_label(title):
        return {}
    terms = []
    if artist and artist.lower() != "unknown artist":
        terms.append(f"{artist} {title}")
    terms.append(title)
    for term in terms:
        try:
            r = requests.get(
                "https://itunes.apple.com/search",
                params={"term": term, "media": "music", "entity": "song", "limit": 10, "country": "US"},
                headers={"User-Agent": "Mozilla/5.0"}, timeout=10,
            )
            r.raise_for_status()
            results = r.json().get("results") or []
            if not results:
                continue
            q = title.lower()
            a = artist.lower()
            def score(item):
                st = _music_clean_text(item.get("trackName")).lower()
                sa = _music_clean_text(item.get("artistName")).lower()
                score = 0
                if st == q: score += 12
                elif q in st or st in q: score += 7
                if a and a != "unknown artist" and (sa == a or a in sa): score += 10
                if item.get("artworkUrl100"): score += 2
                return score
            best = max(results, key=score)
            st = _music_clean_text(best.get("trackName"))
            sa = _music_clean_text(best.get("artistName"))
            artwork = best.get("artworkUrl600") or best.get("artworkUrl100")
            if artwork:
                artwork = artwork.replace("100x100bb", "600x600bb")
            # Only accept a lookup when title has a meaningful match. This prevents
            # an unrelated song from becoming the cover/artist for an Original Sound.
            if score(best) < 7:
                continue
            return {"title": st, "artist": sa, "album": _music_clean_text(best.get("collectionName")), "artwork": artwork}
        except Exception as e:
            print("iTunes music lookup failed:", repr(e))
    return {}


def _embed_music_metadata(mp3_path, title, artist, cover_path=None, album=None):
    """Embed title/artist/album/cover when Mutagen is installed; Telegram still gets thumb separately."""
    try:
        from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, ID3NoHeaderError
        try:
            tags = ID3(mp3_path)
        except ID3NoHeaderError:
            tags = ID3()
        tags.delall("TIT2"); tags.delall("TPE1"); tags.delall("TALB"); tags.delall("APIC")
        if title: tags.add(TIT2(encoding=3, text=str(title)))
        if artist: tags.add(TPE1(encoding=3, text=str(artist)))
        if album: tags.add(TALB(encoding=3, text=str(album)))
        if cover_path and os.path.isfile(cover_path):
            with open(cover_path, "rb") as f:
                tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=f.read()))
        tags.save(mp3_path)
    except Exception as e:
        print("MP3 metadata embedding skipped:", repr(e))


def _download_music_cover(info, tmp_dir, title=None, artist=None, recognized=None):
    """Return the configured MP3 cover. Open mode may use source thumbnail;
    closed mode uses genuine music/artist artwork only."""
    info = info or {}
    recognized = recognized or {}
    artwork_candidates = []
    if get_setting("mp3_cover_enabled", MP3_COVER_DEFAULT):
        thumb = info.get("thumbnail")
        if isinstance(thumb, str) and thumb.strip():
            artwork_candidates.append(thumb.strip())
        for t in info.get("thumbnails") or []:
            if isinstance(t, dict) and isinstance(t.get("url"), str) and t.get("url").strip():
                artwork_candidates.append(t["url"].strip())

    # AcoustID -> exact MusicBrainz release artwork has highest priority.
    for value in recognized.get("artwork_candidates") or []:
        if isinstance(value, str) and value.strip():
            artwork_candidates.append(value.strip())

    # Other recognition artwork sources.
    for key in ("artwork", "artwork_url", "cover", "cover_url"):
        value = recognized.get(key)
        if isinstance(value, str) and value.strip():
            artwork_candidates.append(value.strip())

    # Some extractors provide explicit album artwork fields. These are acceptable;
    # generic `thumbnail`/`thumbnails` are intentionally excluded because they are video frames.
    for key in ("album_art", "album_artwork", "album_cover", "cover_url", "artwork_url", "artwork"):
        value = info.get(key)
        if isinstance(value, str) and value.strip():
            artwork_candidates.append(value.strip())

    for idx, url in enumerate(dict.fromkeys(artwork_candidates)):
        cover = _music_download_image(url, tmp_dir, f"music_cover_{idx}.jpg")
        if cover:
            return cover

    # If the song is identifiable, fetch its real album artwork from iTunes.
    lookup = _music_itunes_lookup(title or _music_title_from_info(info), artist or _music_artist_from_info(info))
    if lookup.get("artwork"):
        cover = _music_download_image(lookup["artwork"], tmp_dir, "itunes_music_cover.jpg")
        if cover:
            return cover
    return None


def _cleanup_music_pending():
    now = time.time()
    for token, data in list(music_pending.items()):
        if now - data.get("created", now) > MUSIC_PENDING_TTL:
            music_pending.pop(token, None)

def _music_safe_filename(title, artist):
    """Create a clean MP3 filename instead of an opaque video/Telegram ID."""
    title = _music_clean_text(title) or "Unknown title"
    artist = _music_clean_text(artist) or "Unknown artist"
    name = f"{title} - {artist}"
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip(" .")
    return (name[:180] or "Unknown title - Unknown artist") + ".mp3"


def convert_link_to_mp3(chat_id, link, status_message_id):
    uid=str(chat_id)
    quick=is_quick_access(uid)
    priority=is_priority_user(uid)
    tmp_dir = os.path.join("downloads", "music_" + uuid.uuid4().hex)
    os.makedirs(tmp_dir, exist_ok=True)
    cookie_args = {}
    if YTDLP_COOKIES_FILE and os.path.isfile(YTDLP_COOKIES_FILE):
        cookie_args["cookiefile"] = YTDLP_COOKIES_FILE
    opts = {
        "quiet": True, "no_warnings": True, "noplaylist": True,
        "retries": 10 if quick else (7 if priority else 3),
        "fragment_retries": 10 if quick else (7 if priority else 3),
        "extractor_retries": 6 if priority else 3,
        "socket_timeout": 25 if quick else 30,
        "http_headers": {"User-Agent": "Mozilla/5.0 Chrome/131 Safari/537.36"},
        "concurrent_fragment_downloads": 24 if quick else (12 if priority else 2),
        "http_chunk_size": 16 * 1024 * 1024 if quick else (8 * 1024 * 1024 if priority else 2 * 1024 * 1024),
        "buffersize": 4 * 1024 * 1024 if quick else (2 * 1024 * 1024 if priority else 1024 * 1024),
        "ratelimit": None,
        "format": "bestaudio/best", "outtmpl": os.path.join(tmp_dir, "%(id)s.%(ext)s"),
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
        "prefer_ffmpeg": True, "overwrites": True, **cookie_args
    }
    try:
        send_action(chat_id, "typing")
        bot.edit_message_text("⚡ <b>Preparing MP3...</b>", chat_id, status_message_id, parse_mode="HTML")
        rapid_mp3=None
        if detect_platform(link)=="youtube" and RAPIDAPI_YT_KEY:
            try:
                rapid_mp3=_rapid_download_audio(link,tmp_dir,chat_id=chat_id)
            except Exception as e:
                print("RapidAPI YouTube MP3 fallback:",repr(e))
        if rapid_mp3 and os.path.isfile(rapid_mp3):
            info={}
            prepared=None
        else:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=True)
                prepared = ydl.prepare_filename(info) if info else None
        if rapid_mp3 and os.path.isfile(rapid_mp3):
            mp3_files=[rapid_mp3]
        else:
            mp3_files = [p for p in _collect_downloaded_files(tmp_dir) if _is_audio_file(p)]
        if not mp3_files and prepared:
            candidate = os.path.splitext(prepared)[0] + ".mp3"
            if os.path.isfile(candidate):
                mp3_files = [candidate]
        if not mp3_files:
            raise RuntimeError("MP3 file was not created. Make sure FFmpeg is installed.")
        path = mp3_files[0]
        if os.path.getsize(path) > _download_max_mb(chat_id) * 1024 * 1024:
            raise RuntimeError("The MP3 is too large for Telegram upload.")

        info = info or {}
        source_title = _music_title_from_info(info)
        source_artist = _music_artist_from_info(info)
        if not source_title:
            raw_title = _music_clean_text(info.get("title") or info.get("fulltitle"))
            source_title = raw_title if raw_title and not _music_is_original_label(raw_title) else "Unknown title"

        # 1) PRIMARY: exact audio fingerprint recognition with AcoustID/Chromaprint.
        # This is especially important for TikTok/Instagram "Original Sound" where
        # uploader metadata is NOT the real music artist.
        recognized = _music_recognize_acoustid(path)

        # Optional legacy fallback if an AudD token is still configured.
        if not recognized and AUDD_API_TOKEN:
            recognized = _music_recognize_audd(path)

        recognized_title = _music_clean_text(recognized.get("title"))
        recognized_artist = _music_clean_text(recognized.get("artist"))
        recognized_album = _music_clean_text(recognized.get("album"))

        # Never use uploader/channel as an artist. If recognition/catalog metadata
        # cannot establish a real artist, the required fallback is "Unknown artist".
        title = recognized_title or source_title or "Unknown title"
        artist = recognized_artist or ""
        album = recognized_album

        # If AcoustID found no exact recording, try independent music catalogs only
        # when we have a meaningful song title. These lookups must never use the
        # source video's thumbnail as artwork.
        catalog_meta = {}
        if not recognized_title or not recognized_artist:
            for lookup_fn in (_music_musicbrainz_lookup, _music_deezer_lookup, _music_itunes_lookup):
                try:
                    catalog_meta = lookup_fn(title, "")
                except Exception:
                    catalog_meta = {}
                if catalog_meta.get("title") and catalog_meta.get("artist"):
                    break

            if catalog_meta:
                title = catalog_meta.get("title") or title
                artist = catalog_meta.get("artist") or artist
                album = album or catalog_meta.get("album") or ""

        if not artist or _music_is_original_label(artist):
            artist = "Unknown artist"

        recognized_for_cover = dict(recognized)
        if recognized_for_cover.get("artwork_candidates"):
            recognized_for_cover["artwork_candidates"] = list(recognized_for_cover["artwork_candidates"])
        if not recognized_for_cover.get("artwork") and catalog_meta.get("artwork"):
            recognized_for_cover["artwork"] = catalog_meta.get("artwork")

        cover_path = _download_music_cover(
            info,
            tmp_dir,
            title=title,
            artist=artist,
            recognized=recognized_for_cover,
        )

        # Embed the same real artwork into the MP3 when possible. No source video frame is used.
        _embed_music_metadata(path, title, artist, cover_path=cover_path, album=album)

        # Give the uploaded MP3 a real music filename, not the source video ID.
        final_path = os.path.join(tmp_dir, _music_safe_filename(title, artist))
        if os.path.abspath(final_path) != os.path.abspath(path):
            try:
                os.replace(path, final_path)
                path = final_path
            except Exception as rename_error:
                print("MP3 filename rename skipped:", repr(rename_error))

        caption = DOWNLOAD_CAPTION
        music_markup = music_destination_markup()
        send_action(chat_id, "upload_audio")
        with open(path, "rb") as audio:
            if cover_path and os.path.isfile(cover_path):
                with open(cover_path, "rb") as thumb:
                    bot.send_audio(chat_id, audio, caption=caption, title=title, performer=artist, thumb=thumb, reply_markup=music_markup, parse_mode="HTML")
            else:
                # No cover was found; Telegram still receives the MP3 and the destination controls.
                bot.send_audio(chat_id, audio, caption=caption, title=title, performer=artist, reply_markup=music_markup, parse_mode="HTML")
        try:
            bot.delete_message(chat_id, status_message_id)
        except Exception:
            pass
    except Exception as e:
        print(f"MP3 conversion error: {repr(e)}")
        friendly = "❌ Music download failed. Please try again."
        if "Sign in to confirm" in str(e) or "not a bot" in str(e):
            friendly = "❌ YouTube music is not available right now.\n\n💎 Open Premium and try again."
        try:
            bot.edit_message_text(friendly, chat_id, status_message_id)
        except Exception:
            pass
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

def _user_destination_rows(uid, dtype=None):
    # The old version showed a custom list and required an admin to pre-register
    # destinations. Users now choose their own chat directly from Telegram's
    # native "Select Chat" picker.
    rows=[]
    for d in _destinations():
        if dtype:
            actual=str(d.get("type"))
            if dtype == "group" and actual not in {"group","supergroup"}:
                continue
            if dtype == "channel" and actual != "channel":
                continue
        rows.append(d)
    return rows

def _new_destination_request_id():
    # Telegram requires a signed 32-bit request_id. Keep it positive and unique
    # among our currently pending requests.
    while True:
        rid=random.randint(1, 2_000_000_000)
        if rid not in DESTINATION_REQUESTS:
            return rid

def _destination_admin_rights(dtype):
    # ChatAdministratorRights has several required base fields in current
    # pyTelegramBotAPI versions. Request only the minimum admin capability
    # needed to keep the bot able to post later.
    return ChatAdministratorRights(
        is_anonymous=False,
        can_manage_chat=True,
        can_delete_messages=False,
        can_manage_video_chats=False,
        can_restrict_members=False,
        can_promote_members=False,
        can_change_info=False,
        can_invite_users=False,
        can_post_messages=True if dtype == "channel" else None,
        can_edit_messages=False if dtype == "channel" else None,
        can_pin_messages=False if dtype == "group" else None,
    )

def _destination_request_keyboard(uid, dtype):
    request_id=_new_destination_request_id()
    DESTINATION_REQUESTS[request_id]={"user_id":str(uid),"type":str(dtype),"created":time.time()}
    rights=_destination_admin_rights(dtype)
    if dtype == "channel":
        req=KeyboardButtonRequestChat(
            request_id=request_id,
            chat_is_channel=True,
            user_administrator_rights=rights,
            bot_administrator_rights=rights,
            bot_is_member=False,
            request_title=True,
            request_username=True,
            request_photo=False,
        )
        label="➕ Add Channel"
    else:
        # Require the user to be an administrator and request administrator
        # rights for the bot so it can reliably post later.
        req=KeyboardButtonRequestChat(
            request_id=request_id,
            chat_is_channel=False,
            user_administrator_rights=rights,
            bot_administrator_rights=rights,
            bot_is_member=False,
            request_title=True,
            request_username=True,
            request_photo=False,
        )
        label="➕ Add Group"
    kb=ReplyKeyboardMarkup(resize_keyboard=True,one_time_keyboard=True,row_width=1)
    kb.add(KeyboardButton(label,request_chat=req))
    kb.add(KeyboardButton("❌ Cancel"))
    return kb

def _destination_picker(uid, dtype):
    # Kept for compatibility with older callers. The actual picker is Telegram's
    # native Select Chat screen, not an admin-managed list.
    return _destination_request_keyboard(uid,dtype), []

def _destination_feature_open(dtype):
    return bool(get_setting("add_group_enabled" if dtype == "group" else "add_channel_enabled", True))

def _destination_feature_status_text():
    g=_destination_feature_open("group")
    c=_destination_feature_open("channel")
    return f"👥 Add Group: <b>{'OPEN' if g else 'CLOSED'}</b>\n📢 Add Channel: <b>{'OPEN' if c else 'CLOSED'}</b>"

@bot.message_handler(func=lambda m: m.text == "❌ Cancel")
def destination_cancel_button(message):
    # Cancel the native Select Chat keyboard and immediately restore the user's menu.
    uid=str(message.from_user.id)
    for rid,data in list(DESTINATION_REQUESTS.items()):
        if str(data.get("user_id"))==uid:
            DESTINATION_REQUESTS.pop(rid,None)
    try:
        bot.send_message(message.chat.id,"❌ Cancelled.",reply_markup=ReplyKeyboardRemove())
        bot.send_message(message.chat.id,"👇 <b>Main Menu</b>",reply_markup=localized_user_menu(uid),parse_mode="HTML")
    except Exception as e:
        print("Destination cancel error:",repr(e))

@bot.callback_query_handler(func=lambda call: call.data.startswith("add_group:"))
def add_group_inline(call):
    if not _destination_feature_open("group"):
        bot.answer_callback_query(call.id, "🔴 Add Group is currently closed.", show_alert=True)
        return
    try:
        bot.answer_callback_query(call.id)
        # Telegram's native request-chat picker can only be launched from a
        # KeyboardButtonRequestChat reply-keyboard button; Telegram does not
        # allow an InlineKeyboardButton to directly open Select Chat. Send only
        # that native request button (no extra instruction/selection screen).
        kb=_destination_request_keyboard(call.from_user.id,"group")
        bot.send_message(
            call.from_user.id,
            "",
            reply_markup=kb,
            parse_mode="HTML"
        )
    except Exception as e:
        print("Add Group picker error:",repr(e))

@bot.callback_query_handler(func=lambda call: call.data.startswith("add_channel:"))
def add_channel_inline(call):
    if not _destination_feature_open("channel"):
        bot.answer_callback_query(call.id, "🔴 Add Channel is currently closed.", show_alert=True)
        return
    try:
        bot.answer_callback_query(call.id)
        # Same Telegram API limitation as Add Group: request_chat is a reply
        # keyboard feature, so this is the shortest possible path to Select Chat.
        kb=_destination_request_keyboard(call.from_user.id,"channel")
        bot.send_message(
            call.from_user.id,
            "",
            reply_markup=kb,
            parse_mode="HTML"
        )
    except Exception as e:
        print("Add Channel picker error:",repr(e))

@bot.message_handler(content_types=["chat_shared"])
def destination_chat_shared(message):
    """Receive Telegram's native chat selection and persist the user's destination."""
    shared=getattr(message,"chat_shared",None)
    if not shared:
        return
    rid=int(getattr(shared,"request_id",0) or 0)
    req=DESTINATION_REQUESTS.pop(rid,None)
    uid=str(message.from_user.id)
    if not req or str(req.get("user_id")) != uid:
        bot.send_message(message.chat.id,"❌ This chat-selection request has expired. Tap Add Group/Add Channel again.")
        return
    dtype=str(req.get("type"))
    chat_id=int(shared.chat_id)
    try:
        chat=bot.get_chat(chat_id)
        member=bot.get_chat_member(chat_id,bot.get_me().id)
        status=str(getattr(member,"status","") or "")
        if status not in {"administrator","creator"}:
            bot.send_message(
                message.chat.id,
                "❌ <b>Bot admin access was not completed.</b>\n\n"
                "Please choose the chat again and make this bot an administrator.\n"
                "The bot needs admin access so it can send messages there later.",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML"
            )
            return
        ctype=str(getattr(chat,"type","") or "")
        if dtype=="group" and ctype not in {"group","supergroup"}:
            bot.send_message(message.chat.id,"❌ Please select a group/supergroup, not a channel.",reply_markup=ReplyKeyboardRemove())
            return
        if dtype=="channel" and ctype!="channel":
            bot.send_message(message.chat.id,"❌ Please select a channel, not a group.",reply_markup=ReplyKeyboardRemove())
            return
        _upsert_destination(chat,uid)
        name=html.escape(getattr(chat,"title","") or getattr(shared,"title","") or str(chat_id))
        kind="Group" if dtype=="group" else "Channel"
        bot.send_message(
            message.chat.id,
            f"✅ <b>{kind} connected successfully</b>\n\n"
            f"📍 {name}\n"
            "🤖 Bot admin: <b>YES</b>\n"
            "📨 The bot can now send messages there when this destination is used.",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML"
        )
    except Exception as e:
        print("Destination chat_shared error:",repr(e))
        bot.send_message(
            message.chat.id,
            "❌ Could not connect this chat. Make sure the bot was added and made administrator, then try again.",
            reply_markup=ReplyKeyboardRemove()
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith("music:"))
def music_callback_handler(call):
    token = call.data.split(":", 1)[1]
    _cleanup_music_pending()
    data = music_pending.get(token)
    if not data:
        bot.answer_callback_query(call.id, "❌ This MUSIC button has expired. Download the video again.", show_alert=True); return
    if str(call.from_user.id) != str(data.get("uid")):
        bot.answer_callback_query(call.id, "❌ This button belongs to another user.", show_alert=True); return
    music_pending.pop(token, None)
    try:
        bot.answer_callback_query(call.id, "🎵 MP3 conversion started...")
        status = bot.send_message(call.message.chat.id, "⏳ Preparing your MP3...")
        download_executor_for(call.from_user.id).submit(convert_link_to_mp3, call.message.chat.id, data["link"], status.message_id)
    except Exception as e:
        print("MUSIC callback error:", e)

@bot.message_handler(func=lambda m: m.text == "🎵 MUSIC")
def music_menu_button(m):
    if bot_locked_guard(m) or banned_guard(m): return
    bot.send_message(m.chat.id, "🎵 Send a video link and tap the 🎵 MUSIC button under the downloaded video. I will convert it to MP3 with the song/album cover and artist. If no real artist can be identified, the artist will be shown as <b>Unknown artist</b>.")

# ================= LANGUAGE COMMAND =================
@bot.message_handler(commands=["language", "lang"])
def language_command(message):
    uid=str(message.from_user.id)
    touch_user(uid)
    lang=lang_of(uid)
    prompt={
        "en":"🌍 <b>Select your language</b>\n\nYour language is saved automatically.",
        "so":"🌍 <b>Dooro luqaddaada</b>\n\nLuqadda aad doorato si otomaatig ah ayaa loo keydinayaa.",
        "am":"🌍 <b>ቋንቋዎን ይምረጡ</b>\n\nየመረጡት ቋንቋ በራስ-ሰር ይቀመጣል።",
        "om":"🌍 <b>Afaana kee filadhu</b>\n\nAfaan ati filattu ofumaan ni kuufama.",
        "ar":"🌍 <b>اختر لغتك</b>\n\nسيتم حفظ اللغة تلقائياً.",
        "fr":"🌍 <b>Choisissez votre langue</b>\n\nVotre choix sera enregistré automatiquement.",
        "es":"🌍 <b>Elige tu idioma</b>\n\nTu idioma se guardará automáticamente.",
        "de":"🌍 <b>Sprache auswählen</b>\n\nDeine Sprache wird automatisch gespeichert.",
        "pt":"🌍 <b>Escolha seu idioma</b>\n\nSeu idioma será salvo automaticamente.",
        "tr":"🌍 <b>Dilinizi seçin</b>\n\nSeçtiğiniz dil otomatik olarak kaydedilir.",
        "hi":"🌍 <b>अपनी भाषा चुनें</b>\n\nआपकी भाषा अपने आप सेव हो जाएगी।",
        "id":"🌍 <b>Pilih bahasa Anda</b>\n\nBahasa Anda akan disimpan otomatis.",
        "ja":"🌍 <b>言語を選択</b>\n\n選択した言語は自動的に保存されます。",
        "ko":"🌍 <b>언어를 선택하세요</b>\n\n선택한 언어는 자동으로 저장됩니다.",
        "zh":"🌍 <b>选择语言</b>\n\n您选择的语言会自动保存。",
    }.get(lang,"🌍 <b>Select your language</b>\n\nYour language is saved automatically.")
    bot.send_message(message.chat.id,prompt,reply_markup=language_kb("change_lang"),parse_mode="HTML")

@bot.my_chat_member_handler()
def bot_chat_membership_update(update):
    try:
        chat=update.chat
        new_status=str(update.new_chat_member.status)
        if new_status in {"member","administrator","creator"}:
            _, intro_sent = _upsert_destination(chat, update.from_user.id if getattr(update,"from_user",None) else None)
            # Send the short introduction only after the bot has admin access.
            if new_status in {"administrator","creator"} and not intro_sent:
                if _send_destination_intro(chat.id, str(getattr(chat,"type","") or "group")):
                    rows=_destinations()
                    row=next((x for x in rows if str(x.get("chat_id"))==str(chat.id)),None)
                    if row:
                        row["intro_sent"] = True
                        _save_destinations(rows)
        elif new_status in {"left","kicked"}:
            _remove_destination(chat.id)
    except Exception as e:
        print("Destination membership update error:",repr(e))

# ================= GROUP / CHANNEL BROADCAST =================

@bot.message_handler(func=lambda m: m.text == "📣 Send all G/CH")
def admin_send_all_destinations_start(m):
    if not is_admin(m.from_user.id):
        return
    destinations = _destinations()
    if not destinations:
        bot.send_message(
            m.chat.id,
            "❌ <b>No connected groups/channels yet.</b>\n\n"
            "Add this bot as an administrator to a group or channel first.",
            parse_mode="HTML",
            reply_markup=admin_menu()
        )
        return
    msg = bot.send_message(
        m.chat.id,
        "📣 <b>Send all G/CH</b>\n\n"
        "Send the message you want to broadcast now.\n"
        "You can send <b>text, photo, video, document, audio, voice</b> or another supported message type.\n\n"
        f"📍 Connected destinations: <b>{len(destinations)}</b>",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, admin_send_all_destinations_step)

def admin_send_all_destinations_step(m):
    if not is_admin(m.from_user.id):
        return
    destinations = list(_destinations())
    if not destinations:
        bot.send_message(m.chat.id, "❌ No connected groups/channels found.", reply_markup=admin_menu())
        return

    sent = 0
    failed = 0
    removed = 0
    for d in destinations:
        try:
            cid = int(d.get("chat_id"))
            bot.copy_message(cid, m.chat.id, m.message_id)
            sent += 1
        except Exception as e:
            failed += 1
            err = str(e).lower()
            # If the bot has left/is no longer allowed to access a destination,
            # remove it so future broadcasts stay clean.
            if any(x in err for x in ("chat not found", "bot was kicked", "not enough rights", "forbidden")):
                try:
                    _remove_destination(cid)
                    removed += 1
                except Exception:
                    pass

    bot.send_message(
        m.chat.id,
        "✅ <b>G/CH broadcast completed</b>\n\n"
        f"📨 Sent: <b>{sent}</b>\n"
        f"❌ Failed: <b>{failed}</b>\n"
        f"🗑 Removed unavailable: <b>{removed}</b>",
        parse_mode="HTML",
        reply_markup=admin_menu()
    )

# ================= START HANDLER =================

@bot.message_handler(commands=['start'])
def start_handler(message):
    if bot_locked_guard(message): return
    uid=str(message.from_user.id); args=message.text.split()
    if uid not in users:
        users[uid]={"username":message.from_user.username or "","first_name":message.from_user.first_name or "there","balance":0.0,"blocked":0.0,"ref":random_ref(),"bot_id":random_botid(),"invited":0,"banned":False,"verified":False,"email_verified":False,"phone_verified":False,"whatsapp_verified":False,"verification_method":None,"balance_locked":False,"balance_activation_code":None,"balance_lock_until":None,"quick_access":False,"youtube_30m":False,"premium_until":None,"premium_warning_sent":False,"trial_used":False,"trial_pending":False,"trial_version_used":None,"trial_pending_version":None,"referral_50_rewarded":False,"referred_by":None,"joined_date":datetime.now().strftime("%Y-%m-%d"),"last_seen_at":datetime.now(timezone.utc).isoformat(),"month":now_month(),"language":None,"currency":"USD","balance_asset":"USD","gender":None,"city":None,"pending_ref":args[1] if len(args)>1 else None}
        save_user(uid)
    users[uid].setdefault("currency","USD")
    users[uid].setdefault("balance_asset",users[uid].get("currency","USD"))
    users[uid].setdefault("blocked",0.0)
    users[uid].setdefault("first_name", message.from_user.first_name or "there")
    users[uid]["first_name"] = message.from_user.first_name or users[uid].get("first_name") or "there"
    users[uid]["username"] = message.from_user.username or users[uid].get("username") or ""
    users[uid].setdefault("trial_pending",False)
    users[uid].setdefault("trial_version_used",None)
    users[uid].setdefault("trial_pending_version",None)
    users[uid].setdefault("referred_by",None)
    users[uid].setdefault("email_verified",False)
    users[uid].setdefault("phone_verified",False)
    users[uid].setdefault("whatsapp_verified",False)
    users[uid].setdefault("verification_method",None)
    users[uid].setdefault("balance_locked",False)
    users[uid].setdefault("balance_activation_code",None)
    users[uid].setdefault("balance_lock_until",None)
    users[uid].setdefault("portfolio",{})
    touch_user(uid)
    if not users[uid].get("language"):
        bot.send_message(message.chat.id,"🌍 <b>Select language</b>\n\nChoose the language you want to use:",reply_markup=language_kb("setlang")); return
    check_membership(message.from_user.id)

@bot.message_handler(commands=['view'])
def view_cmd(message):
    try:
        bot.send_message(
            message.chat.id,
            "🤖 BOT INFO\n\n"
            "📌 Name: DOWNLOADER BOT\n"
            "⚡ Features:\n"
            "• TikTok, Instagram, Facebook, Pinterest, YouTube, Snapchat, X/Twitter support\n"
            "• Referral system\n"
            "• Withdrawal system"
        )
    except: pass

@bot.message_handler(commands=['balance'])
def balance_cmd(m):
    uid = str(m.from_user.id)
    bal = users.get(uid, {}).get("balance", 0)
    try:
        bot.send_message(m.chat.id, f"💰 Your balance: {format_asset(cur_code(uid),bal)}")
    except: pass

@bot.message_handler(commands=['refer'])
@bot.message_handler(func=lambda m: m.text == "👥 REFERRAL")
def refer_cmd(m):
    touch_user(m.from_user.id)
    if bot_locked_guard(m) or banned_guard(m):
        return
    uid = str(m.from_user.id)
    try:
        bot_username = bot.get_me().username
        ref = users[uid]['ref']
        link = f"https://t.me/{bot_username}?start={ref}"
        invited = users[uid].get("invited", 0)
        
        reward = referral_reward_amount()
        # Users see only their unique referral link; the internal referral code is hidden.
        # Share contains only the link, with no advertisement/promo prefix.
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📤 Share", switch_inline_query=link))
        kb.add(InlineKeyboardButton("💳 Buy Custom Referral Code", callback_data="buy_ref_menu"))
        bot.send_message(
            m.chat.id,
            f"🔗 <b>Your Referral Link</b>:\n<code>{html.escape(link)}</code>\n\n"
            f"👥 <b>Invited Users</b>: {invited}\n"
            f"🎁 <b>You earn ${reward:.2f} per referral!</b>\n\n"
            "📤 Tap <b>Share</b> to send your referral link to friends.",
            reply_markup=kb,
            parse_mode="HTML"
        )
    except: pass

@bot.message_handler(commands=['ping'])
def ping_cmd(m):
    start = time.time()
    try:
        msg = bot.send_message(m.chat.id, "🏓 Pinging...")
        end = time.time()
        speed = round((end - start) * 1000)
        status = "🟢 Online" if speed < 1000 else "🟡 Slow"
        bot.edit_message_text(
            f"🏓 PONG!\n\n"
            f"⚡ Speed: {speed} ms\n"
            f"📡 Status: {status}",
            m.chat.id,
            msg.message_id,
            parse_mode="HTML"
        )
    except: pass

# ================= VERIFY BOT START =================

@bot2.message_handler(commands=['start'])
def verify_start(message):
    args = message.text.split()
    if len(args) > 1:
        code = args[1]
        try:
            bot2.send_message(
                message.chat.id,
                f"🔑 Your Verification Code\n\n"
                f"{code}\n\n"
                "Copy this code and send it to the downloader bot."
            )
        except: pass
    else:
        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton(
                "GET",
                url="https://t.me/Downloadvedioytibot"
            )
        )
        try:
            bot2.send_message(
                message.chat.id,
                "❌ Don't Have Code?\n\nGet code from downloader bot.",
                reply_markup=kb
            )
        except: pass

# ================= CHECK MEMBERSHIP =================

def check_membership(user_id):
    touch_user(user_id)
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["member", "administrator", "creator"]:
            bot.send_message(
                user_id,
                render_start_message(str(user_id)),
                reply_markup=welcome_destination_markup(),
                parse_mode="HTML"
            )
            bot.send_message(user_id, "👇 <b>Main Menu</b>", reply_markup=localized_user_menu(str(user_id)), parse_mode="HTML")
        else:
            send_join_message(user_id)
    except Exception as e:
        print("FORCE JOIN CHECK ERROR:", repr(e))
        send_join_message(user_id)

def send_join_message(user_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ JOIN CHANNEL", url="https://t.me/tiktokvediodownload"))
    kb.add(InlineKeyboardButton("✅ CONFIRM", callback_data="confirm_join"))
    try:
        bot.send_message(
            user_id,
            "⚠️ You must join our channel to use this bot.",
            reply_markup=kb
        )
    except: pass

def send_multi_join(user_id):
    kb = InlineKeyboardMarkup(row_width=3)
    buttons = [InlineKeyboardButton("➕️ JOIN", url=f"https://t.me/{ch}") for ch in POST_CHANNELS]
    kb.add(*buttons)
    kb.add(InlineKeyboardButton("✅ CONFIRM", callback_data="multi_checkjoin"))
    try:
        bot.send_message(user_id, "⚠️ Join all channels to continue.", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda call: call.data == "confirm_join")
def confirm_join(call):
    user_id = call.from_user.id
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["member", "administrator", "creator"]:
            bot.answer_callback_query(call.id, "✅ Join verified")
            try:
                bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
            except: pass
            # After the user's first successful channel confirmation, show the
            # same welcome message + main menu used by the normal /start flow.
            # Do NOT replace this with a bare "Join confirmed" message.
            # The welcome is part of the onboarding system.
            try:
                bot.send_message(
                    user_id,
                    render_start_message(str(user_id)),
                    reply_markup=welcome_destination_markup(),
                    parse_mode="HTML"
                )
                bot.send_message(user_id, "👇 <b>Main Menu</b>", reply_markup=localized_user_menu(str(user_id)), parse_mode="HTML")
            except Exception as e:
                print("WELCOME AFTER CONFIRM ERROR:", repr(e))
            if user_id in pending_links:
                link = pending_links.pop(user_id, None)
                if link:
                    msg = bot.send_message(user_id, "⏳ Processing...")
                    download_executor_for(user_id).submit(
                        download_media, user_id, link, msg.message_id,
                        users.get(str(user_id), {}).get("premium_quality") or ("1080" if is_quick_access(user_id) else None)
                    )
        else:
            bot.answer_callback_query(call.id, "❌ You must join the channel first!", show_alert=True)
    except:
        bot.answer_callback_query(call.id, "❌ Please join the channel first!", show_alert=True)

@bot.message_handler(func=lambda m: False)
def admin_open_song(m):
    if not is_admin(m.from_user.id): return
    set_setting("song_search_enabled",True)
    bot.send_message(m.chat.id,"🟢 <b>SONG SEARCH OPENED IN BOT</b>\n\nUsers can now use 🔎 Search Song.",parse_mode="HTML",reply_markup=admin_menu())

@bot.message_handler(func=lambda m: False)
def admin_close_song(m):
    if not is_admin(m.from_user.id): return
    set_setting("song_search_enabled",False)
    bot.send_message(m.chat.id,"🔴 <b>SONG SEARCH CLOSED IN BOT</b>\n\nUsers will see the configured closed message.",parse_mode="HTML",reply_markup=admin_menu())

@bot.message_handler(func=lambda m: False)
def admin_song_closed_message(m):
    if not is_admin(m.from_user.id): return
    current=_song_search_closed_message()
    msg=bot.send_message(m.chat.id,f"✏️ <b>SONG CLOSED MESSAGE</b>\n\nCurrent:\n<code>{html.escape(current)}</code>\n\nSend the new message:",parse_mode="HTML")
    bot.register_next_step_handler(msg,admin_song_closed_message_step)

def admin_song_closed_message_step(m):
    if not is_admin(m.from_user.id): return
    value=_music_clean_text(m.text)
    if not value:
        bot.send_message(m.chat.id,"❌ Message cannot be empty."); return
    set_setting("song_search_closed_message",value)
    bot.send_message(m.chat.id,f"✅ <b>Song closed message updated.</b>\n\n{html.escape(value)}",parse_mode="HTML",reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == "⚡ AUTO SONG SEARCH ON")
def admin_auto_song_on(m):
    if not is_admin(m.from_user.id): return
    set_setting("song_auto_search_enabled",True); set_setting("song_search_enabled",True)
    bot.send_message(m.chat.id,"⚡ <b>AUTO SONG SEARCH ON</b>\n\nAny normal text that is not a button or command can be used to search for a song/artist automatically.",parse_mode="HTML",reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == "⛔ AUTO SONG SEARCH OFF")
def admin_auto_song_off(m):
    if not is_admin(m.from_user.id): return
    set_setting("song_auto_search_enabled",False); set_setting("song_search_enabled",False)
    bot.send_message(m.chat.id,"⛔ <b>AUTO SONG SEARCH OFF</b>\n\nUsers can no longer use the old Search Song button; turn AUTO SONG SEARCH ON to search normal text automatically.",parse_mode="HTML",reply_markup=admin_menu())

@bot.message_handler(func=lambda m: False)
def admin_add_song_caption(m):
    if not is_admin(m.from_user.id): return
    set_setting("song_caption", "")
    bot.send_message(m.chat.id, "🔒 <b>SONG CAPTION LOCKED</b>\n\nAll MP3/music captions are fixed to:\n<code>Downloaded Via\n@Downloadvedioytibot</code>\n\nArtist, album and title are not shown in the visible caption.", parse_mode="HTML", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: False)
def admin_song_stats(m):
    if not is_admin(m.from_user.id): return
    bot.send_message(m.chat.id,_song_stats_text(),parse_mode="HTML",reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == "👑 ADMIN PANEL")
def open_admin_panel(m):
    if not is_admin(m.from_user.id):
        try:
            bot.send_message(m.chat.id, "❌ You are not admin")
        except: pass
        return
    try:
        bot.send_message(m.chat.id, "👑 Admin Panel", reply_markup=admin_menu())
    except: pass

@bot.message_handler(func=lambda m: m.text == "💰 BALANCE")
def balance_handler(m):
    touch_user(m.from_user.id)
    if bot_locked_guard(m) or banned_guard(m): return
    uid=str(m.from_user.id)
    if balance_is_locked(uid):
        bot.send_message(m.chat.id,balance_locked_message(uid),reply_markup=localized_user_menu(uid),parse_mode="HTML")
        return

    code=cur_code(uid)
    available=available_asset_amount(uid)
    blocked=blocked_amount(uid)
    pending=pending_withdrawal_amount(uid)
    hold=hold_amount_usd(uid)
    crypto_open=crypto_system_open()
    portfolio=get_portfolio(uid)
    crypto_rows=[(usd,c,a) for usd,c,a in portfolio_text(uid) if is_crypto(c) and float(a or 0)>0]
    current_is_crypto=is_crypto(code) and balance_amount(uid)>1e-12
    has_crypto=bool(crypto_rows or current_is_crypto)

    # When Crypto is closed (or the user has no crypto), keep Balance clean:
    # Available / Blocked / Pending are the only account buckets shown.
    if not crypto_open or not has_crypto:
        pending_block=(
            f"⏳ <b>Pending Amount</b>\n"
            f"   <code>{html.escape(format_asset(code,pending))}</code>\n\n"
            if pending > 1e-12 else ""
        )
        text=(
            "💰 <b>YOUR BALANCE</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 <b>Available Balance</b>\n"
            f"   <code>{html.escape(format_asset(code,available))}</code>\n\n"
            f"🔒 <b>Blocked Amount</b>\n"
            f"   <code>{html.escape(format_asset(code,blocked))}</code>\n\n"
            + pending_block +
            "━━━━━━━━━━━━━━━━━━"
        )
        bot.send_message(m.chat.id,text,reply_markup=localized_user_menu(uid),parse_mode="HTML")
        return

    # Crypto OPEN: show the three cash buckets first, then crypto holdings.
    total_usd=total_assets_usd(uid)
    text=(
        "💰 <b>YOUR BALANCE & ASSETS</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 <b>Available Balance</b>\n"
        f"   <code>{html.escape(format_asset(code,available))}</code>"
        f"   <i>≈ ${asset_to_usd(code,available):,.2f} USD</i>\n\n"
        f"🔒 <b>Blocked Amount</b>\n"
        f"   <code>{html.escape(format_asset(code,blocked))}</code>"
        f"   <i>≈ ${asset_to_usd(code,blocked):,.2f} USD</i>\n\n"
        + (
            f"⏳ <b>Pending Amount</b>\n"
            f"   <code>{html.escape(format_asset(code,pending))}</code>"
            f"   <i>≈ ${pending_withdrawal_usd(uid):,.2f} USD</i>\n\n"
            if pending > 1e-12 else ""
        ) +
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🪙 <b>CRYPTO / INVESTMENTS</b>\n"
    )
    if current_is_crypto:
        text += f"\n• <b>{code}</b>: {balance_amount(uid):,.8f} ≈ ${balance_usd_value(uid):,.2f}\n"
    if crypto_rows:
        for usd,c,a in crypto_rows[:30]:
            text += f"• <b>{html.escape(c)}</b>: {a:,.8f} ≈ ${usd:,.2f}\n"
    if not current_is_crypto and not crypto_rows:
        text += "\n• No crypto holdings\n"
    text += (
        "\n━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Total Asset Value:</b> ${total_usd:,.2f} USD\n"
    )
    if hold > 0.0000000001:
        text += f"⏱️ <b>Conversion Hold:</b> ${hold:,.2f} USD\n"

    kb=InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("💼 VIEW CRYPTO PORTFOLIO", callback_data="view_portfolio"))
    if hold > 0.0000000001:
        kb.add(InlineKeyboardButton("❓ WHAT IS HOLD?",callback_data="what_hold"))
    bot.send_message(m.chat.id,text,reply_markup=kb,parse_mode="HTML")

@bot.callback_query_handler(func=lambda c:c.data=="view_portfolio")
def view_portfolio_callback(call):
    uid=str(call.from_user.id); refresh_market_rates(False); rows=portfolio_text(uid)
    lines=["💼 <b>YOUR CRYPTO / CURRENCY PORTFOLIO</b>",""]
    current=balance_amount(uid)
    if current>0: lines.append(f"💰 Current: <b>{format_asset(cur_code(uid),current)}</b> ≈ ${balance_usd_value(uid):,.2f}")
    for usd,c,a in rows: lines.append(f"• <b>{c}</b>: {a:.12f} ≈ ${usd:,.2f}")
    lines.append("")
    lines.append(f"📊 <b>Total value:</b> ${total_assets_usd(uid):,.2f} USD")
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id,"\n".join(lines))

@bot.callback_query_handler(func=lambda c:c.data=="what_hold")
def what_hold_callback(call):
    uid=str(call.from_user.id); now=datetime.now(timezone.utc); hs=list(conversion_holds_col.find({"user_id":uid,"status":"hold"}).sort("created_at",-1).limit(10))
    lines=["❓ <b>WHAT MEANS HOLD?</b>","","A hold is a temporary security lock applied to funds after a crypto → USD conversion.","","⏱️ Hold duration: <b>1 hour</b>","💵 Held money cannot be withdrawn while the hold is active.","✅ After 1 hour it automatically becomes Available.","👑 Admin can check the source/history and release it early.",""]
    if hs:
        for h in hs:
            exp=parse_seen_time(h.get("expires_at")); sec=max(0,int((exp-now).total_seconds())) if exp else 0; lines.append(f"• ${float(h.get('usd_amount',0)):,.2f} USD — {sec//60}m {sec%60}s remaining")
    else: lines.append("No active holds.")
    bot.answer_callback_query(call.id); bot.send_message(call.message.chat.id,"\n".join(lines))


@bot.message_handler(func=lambda m: m.text == "🆔 GET ID")
def get_id_handler(m):
    touch_user(m.from_user.id)
    if bot_locked_guard(m) or banned_guard(m):
        return
    uid = str(m.from_user.id)
    bot_id = str(users.get(uid, {}).get("bot_id", ""))
    # Use the raw Bot API for copy_text so this keeps working even when
    # the installed pyTelegramBotAPI version does not expose CopyTextButton.
    reply_markup = {"inline_keyboard": [
        [{"text": "📋 Copy BOT ID", "copy_text": {"text": bot_id}}],
        [{"text": "📋 Copy Telegram ID", "copy_text": {"text": uid}}]
    ]}
    try:
        telegram_api_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        r = requests.post(telegram_api_url, json={
            "chat_id": m.chat.id,
            "text": f"🆔 <b>YOUR IDS</b>\n\n🤖 BOT ID: <code>{bot_id}</code>\n👤 Telegram ID: <code>{uid}</code>\n\nTap a button below to copy the ID.",
            "parse_mode": "HTML",
            "reply_markup": reply_markup
        }, timeout=20)
        if not r.ok:
            print("GET ID Telegram API error:", r.text[:500])
    except Exception as e:
        print("GET ID error:", e)
        try:
            bot.send_message(m.chat.id, f"🆔 BOT ID: <code>{bot_id}</code>\n👤 Telegram ID: <code>{uid}</code>")
        except Exception:
            pass

@bot.message_handler(func=lambda m: m.text == "➕ ADD CUSTOMER")
def add_customer_handler(m):
    if not is_admin(m.from_user.id):
        return
    current = str(get_setting("customer_username", "scholes1") or "scholes1").strip().lstrip("@")
    msg = bot.send_message(m.chat.id, "➕ <b>ADD CUSTOMER</b>\n\n" f"Current Customer: <b>@{html.escape(current)}</b>\n\nSend the new customer username.\nExample: <code>@scholes1</code>")
    bot.register_next_step_handler(msg, save_customer_username)

def save_customer_username(m):
    if not is_admin(m.from_user.id):
        return
    username=(m.text or "").strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
        msg=bot.send_message(m.chat.id,"❌ Invalid Telegram username. Example: <code>@scholes1</code>")
        bot.register_next_step_handler(msg, save_customer_username)
        return
    old=str(get_setting("customer_username", "scholes1") or "scholes1").strip().lstrip("@")
    set_setting("customer_username", username)
    bot.send_message(m.chat.id, f"✅ <b>CUSTOMER UPDATED</b>\n\nOld: <code>@{html.escape(old)}</code>\nNew: <code>@{html.escape(username)}</code>")

# Backward-compatible handler for old keyboards.
@bot.message_handler(func=lambda m: m.text == "☎️ CUSTOMER")
def customer_handler(m):
    if is_admin(m.from_user.id):
        return add_customer_handler(m)
    touch_user(m.from_user.id)
    if bot_locked_guard(m) or banned_guard(m): return
    customer = str(get_setting("customer_username", "scholes1") or "scholes1").strip().lstrip("@")
    try: bot.send_message(m.chat.id, f"☎️ Customer Support:\n@{html.escape(customer)}")
    except Exception: pass

# ================= CUSTOMER AI — DEDICATED, ACCOUNT-AWARE SUPPORT BOT =================
# The Customer AI is a separate BotFather bot. It shares the same MongoDB user
# database as the main bot, so it can answer using the user's live account data.
# No reply/inline keyboards are used inside the Customer AI: users operate it
# with /commands or normal natural-language messages.

AI_SUPPORT_PENDING=set()
_CUSTOMER_AI_USERNAME_CACHE=None

CUSTOMER_AI_SYSTEM_PROMPT = """
You are the dedicated Customer AI for this Telegram service. Be accurate,
helpful, calm and professional. Understand Somali and English. Never invent
account data, balances, Premium expiry, verification state, withdrawal status,
crypto prices, bans, or system settings. Use live MongoDB/system data when
available. The Customer AI knows the complete user-facing system: account,
profile, balance, blocked/hold, balance lock, Premium/trial, verification,
Gmail/D7 SMS/WaForge WhatsApp, crypto, fees, deposits, YouTube Premium-only,
downloads, music/MP3, referral, withdrawal, Force Join, language and support.
For admins it can also inspect system health and user reports through admin-only
commands. It must never expose another user's private data to a normal user.
"""


def _customer_ai_identity():
    """Return the real Customer AI username from BotFather, never a fake default."""
    global _CUSTOMER_AI_USERNAME_CACHE
    if _CUSTOMER_AI_USERNAME_CACHE:
        return _CUSTOMER_AI_USERNAME_CACHE
    configured=str(get_setting("customer_ai_username", "") or "").strip().lstrip("@")
    if configured:
        _CUSTOMER_AI_USERNAME_CACHE=configured
        return configured
    if customer_ai_bot:
        try:
            me=customer_ai_bot.get_me()
            if me and me.username:
                _CUSTOMER_AI_USERNAME_CACHE=me.username
                set_setting("customer_ai_username",me.username)
                return me.username
        except Exception as e:
            print("Customer AI get_me error:",e)
    return ""


def _ai_language(uid):
    uid=str(uid)
    value=users.get(uid,{}).get("customer_ai_language")
    return value if value in ("en","so") else None


def _set_ai_language(uid, language):
    uid=str(uid)
    if uid not in users:
        return False
    users[uid]["customer_ai_language"]="so" if language=="so" else "en"
    # Keep the main bot language aligned only when it is unset.
    if not users[uid].get("language"):
        users[uid]["language"]=users[uid]["customer_ai_language"]
    save_user(uid)
    return True


def _ai_choose_language_text():
    return (
        "🤖 <b>WELCOME TO CUSTOMER AI</b>\n\n"
        "Choose your language / Dooro luqaddaada:\n\n"
        "🇬🇧 <b>English:</b> send <code>/english</code>\n"
        "🇸🇴 <b>Somali:</b> dir <code>/somali</code>\n\n"
        "You can change it any time with <code>/language</code>.\n"
        "Waxaad beddeli kartaa goor kasta adigoo isticmaalaya <code>/language</code>."
    )


def _ai_help_text(lang="en", admin=False):
    if lang=="so":
        base=(
            "🤖 <b>CUSTOMER AI — CAWIMAAD BUUXDA</b>\n\n"
            "Waxaad iigu qori kartaa su'aashaada si caadi ah; buttons looma baahna. Waxaan akhriyaa xogta account-kaaga live marka ay jirto.\n\n"
            "<b>Commands:</b>\n"
            "/balance — Haraaga iyo lacagta blocked\n"
            "/profile — Profile, Telegram ID iyo Bot ID\n"
            "/premium — Premium/Trial iyo expiry\n"
            "/verification — Xaqiijinta account-ka\n"
            "/crypto — Crypto access iyo xaaladdaada\n"
            "/downloads — Download help\n"
            "/music — Music/MP3 help\n"
            "/withdrawal — Withdrawal iyo status-kaaga\n"
            "/referral — Referral-kaaga\n"
            "/system — Adeegyada aan kaa caawin karo\n"
            "/language — Beddel English/Somali\n"
            "/help — Help-kan\n\n"
            "Tusaale: <i>“Maxaa balance-kayga loo xiray?”</i>, <i>“Withdrawal-kaygu xaggee marayaa?”</i>, ama <i>“YouTube maxaa Premium looga dhigay?”</i>."
        )
        if admin:
            base += ("\n\n<b>ADMIN COMMANDS:</b>\n"
                     "/system — Live system dashboard\n"
                     "/user ID|BOTID|@username — User report\n"
                     "/users — User statistics\n"
                     "/balances — Balance statistics\n"
                     "/withdrawals — Withdrawal statistics\n"
                     "/banned — Banned users\n"
                     "/locks — Balance locks\n"
                     "/admins — Admin list")
        return base
    base=(
        "🤖 <b>CUSTOMER AI — FULL SUPPORT</b>\n\n"
        "Ask me anything naturally; no buttons are required. I can read your live account data when available.\n\n"
        "<b>Commands:</b>\n"
        "/balance — Your balance and blocked amount\n"
        "/profile — Profile, Telegram ID and Bot ID\n"
        "/premium — Premium/Trial and expiry\n"
        "/verification — Account verification\n"
        "/crypto — Crypto access and your status\n"
        "/downloads — Download help\n"
        "/music — Music/MP3 help\n"
        "/withdrawal — Your withdrawal status\n"
        "/referral — Referral information\n"
        "/system — What I can help you with\n"
        "/language — Change English/Somali\n"
        "/help — This help\n\n"
        "Examples: <i>“Why is my balance closed?”</i>, <i>“Check my withdrawal”</i>, or <i>“Why is YouTube Premium-only?”</i>."
    )
    if admin:
        base += ("\n\n<b>ADMIN COMMANDS:</b>\n"
                 "/system — Live system dashboard\n"
                 "/user ID|BOTID|@username — User report\n"
                 "/users — User statistics\n"
                 "/balances — Balance statistics\n"
                 "/withdrawals — Withdrawal statistics\n"
                 "/banned — Banned users\n"
                 "/locks — Balance locks\n"
                 "/admins — Admin list")
    return base


def _ai_user_context(uid):
    uid=str(uid)
    u=users.get(uid,{})
    try:
        deposited=total_account_deposits_usd(uid)
        allowed,remaining,minimum=crypto_access_status(uid)
    except Exception:
        deposited=0.0; allowed=False; remaining=0.0; minimum=crypto_min_deposit_usd()
    try:
        downloads=int(videos_data.get("users",{}).get(uid,0) or 0)
    except Exception:
        downloads=0
    try: verified=user_is_verified(uid) if uid in users else False
    except Exception: verified=bool(u.get("verified"))
    try: premium=is_premium(uid)
    except Exception: premium=False
    try: locked=balance_is_locked(uid)
    except Exception: locked=bool(u.get("balance_locked"))
    return {
        "uid":uid,"username":u.get("username") or "","name":u.get("first_name") or "User",
        "bot_id":u.get("bot_id") or "N/A","balance":balance_amount(uid),"asset":cur_code(uid),
        "balance_usd":balance_usd_value(uid),"blocked":blocked_amount(uid),"pending":pending_withdrawal_amount(uid),"pending_usd":pending_withdrawal_usd(uid),
        "portfolio_usd":portfolio_usd_value(uid),"total_assets_usd":total_assets_usd(uid),
        "premium_platforms":premium_platform_names(),"premium_platform_count":len(premium_platform_names()),
        "verified":verified,"verification_method":u.get("verification_method") or "N/A",
        "email":u.get("email") or "N/A","phone":u.get("phone") or "N/A", "banned":bool(u.get("banned")),
        "premium":premium,"premium_until":premium_until_text(uid) if premium else "Not active",
        "trial_available":trial_available(uid) if uid in users else False,"downloads":downloads,
        "language":lang_of(uid),"ai_language":_ai_language(uid) or "Not selected",
        "crypto_open":crypto_system_open(),"crypto_allowed":allowed,"crypto_remaining":remaining,
        "crypto_minimum":minimum,"deposited":deposited,"balance_locked":locked,
        "youtube_special":bool(u.get("youtube_30m")),"referrals":int(u.get("invited",0) or 0),
        "city":u.get("city") or "N/A","gender":u.get("gender") or "N/A",
    }


def _ai_system_context():
    return {
        "crypto":"OPEN" if crypto_system_open() else "CLOSED",
        "crypto_hold":"OPEN" if crypto_hold_open() else "CLOSED",
        "crypto_min_deposit":crypto_min_deposit_usd(),"crypto_fee_percent":crypto_fee_percent(),
        "premium":"OPEN" if bool(get_setting("premium_enabled",True)) else "CLOSED",
        "premium_verification":"REQUIRED" if premium_verification_required() else "NOT REQUIRED",
        "sms":"OPEN" if bool(get_setting("sms_enabled",False)) else "CLOSED",
        "whatsapp":"OPEN" if bool(get_setting("whatsapp_verify_enabled",False)) and bool(WAFORGE_API_KEY) else "CLOSED",
        "verify":"ON" if VERIFY_ENABLED else "OFF",
        "free_minutes":int(get_setting("free_max_minutes",FREE_MAX_MINUTES_DEFAULT) or FREE_MAX_MINUTES_DEFAULT),
        "premium_minutes":int(get_setting("premium_max_minutes",PREMIUM_MAX_MINUTES_DEFAULT) or PREMIUM_MAX_MINUTES_DEFAULT),
        "free_mb":int(get_setting("free_max_mb",49) or 49),"premium_mb":int(get_setting("premium_max_mb",49) or 49),
        "rapidapi_youtube":bool(RAPIDAPI_YT_KEY),"cobalt":bool(COBALT_API_URL),"d7_sms":bool(D7_TOKEN),
        "waforge_whatsapp":bool(WAFORGE_API_KEY),"resend_email":bool(RESEND_API_KEY),
        "force_join":bool(CHANNEL_WINDOW_OPEN),"users":len(users),"admins":len(get_admin_ids()),
        "downloads":int(videos_data.get("total",0) or 0),
    }


def _ai_find_user(query):
    q=(query or "").strip().lstrip("@").lower()
    if not q: return None
    if q in users: return q
    found=find_user_by_botid(q)
    if found: return found
    for uid,data in users.items():
        if str(data.get("username","")).lstrip("@").lower()==q: return uid
    return None


def _ai_withdrawals_for(uid):
    uid=str(uid)
    return [w for w in withdraws if str(w.get("user"))==uid or str(w.get("user_id"))==uid]


def _ai_user_report(uid, admin=False, lang="en"):
    c=_ai_user_context(uid)
    username=("@"+c["username"]) if c["username"] else "No username"
    status="LOCKED" if c["balance_locked"] else "OPEN"
    verify="Verified" if c["verified"] else "Not verified"
    premium="ACTIVE" if c["premium"] else "Not active"
    if lang=="so":
        lines=["🤖 <b>CUSTOMER AI — XOGTA ACCOUNT-KA</b>","",
               f"👤 Magac: <b>{html.escape(c['name'])}</b>",f"🔗 Username: <b>{html.escape(username)}</b>",
               f"🆔 Telegram ID: <code>{c['uid']}</code>",f"🤖 Bot ID: <code>{html.escape(str(c['bot_id']))}</code>",
               f"🌍 Luqadda AI: <b>{html.escape(str(c['ai_language']))}</b>",f"🔐 Verification: <b>{verify}</b>",
               f"💎 Premium: <b>{premium}</b>"+(f" ilaa <b>{html.escape(c['premium_until'])}</b>" if c['premium'] else ""),
               f"💰 Balance: <b>{html.escape(format_asset(c['asset'],c['balance']))}</b>",f"💵 USD value: <b>${c['balance_usd']:,.2f}</b>",
               f"🔒 Blocked: <b>{html.escape(format_asset(c['asset'],c['blocked']))}</b>",
               f"💼 Total assets: <b>${c['total_assets_usd']:,.2f}</b>",f"🔐 Balance status: <b>{status}</b>",
               f"🪙 Crypto access: <b>{'ALLOWED' if c['crypto_allowed'] else 'LOCKED'}</b>",
               f"💳 Deposited/credited: <b>${c['deposited']:,.2f}</b>",f"📥 Downloads: <b>{c['downloads']}</b>",
               f"👥 Referrals: <b>{c['referrals']}</b>",f"🚫 Banned: <b>{'YES' if c['banned'] else 'NO'}</b>"]
        if c["pending"] > 1e-12:
            lines.insert(11, f"⏳ Pending: <b>{html.escape(format_asset(c['asset'],c['pending']))}</b>")
        if admin: lines += [f"📧 Email: <code>{html.escape(str(c['email']))}</code>",f"📱 Phone: <code>{html.escape(str(c['phone']))}</code>",f"🏙 City: <b>{html.escape(str(c['city']))}</b>"]
        return "\n".join(lines)
    lines=["🤖 <b>CUSTOMER AI — ACCOUNT REPORT</b>","",
           f"👤 Name: <b>{html.escape(c['name'])}</b>",f"🔗 Username: <b>{html.escape(username)}</b>",
           f"🆔 Telegram ID: <code>{c['uid']}</code>",f"🤖 Bot ID: <code>{html.escape(str(c['bot_id']))}</code>",
           f"🌍 AI language: <b>{html.escape(str(c['ai_language']))}</b>",f"🔐 Verification: <b>{verify}</b>",
           f"💎 Premium: <b>{premium}</b>"+(f" until <b>{html.escape(c['premium_until'])}</b>" if c['premium'] else ""),
           f"💰 Balance: <b>{html.escape(format_asset(c['asset'],c['balance']))}</b>",f"💵 USD value: <b>${c['balance_usd']:,.2f}</b>",
           f"🔒 Blocked: <b>{html.escape(format_asset(c['asset'],c['blocked']))}</b>",
           f"💼 Total assets: <b>${c['total_assets_usd']:,.2f}</b>",f"🔐 Balance status: <b>{status}</b>",
           f"🪙 Crypto access: <b>{'ALLOWED' if c['crypto_allowed'] else 'LOCKED'}</b>",
           f"💳 Deposited/credited: <b>${c['deposited']:,.2f}</b>",f"📥 Downloads: <b>{c['downloads']}</b>",
           f"👥 Referrals: <b>{c['referrals']}</b>",f"🚫 Banned: <b>{'YES' if c['banned'] else 'NO'}</b>"]
    if c["pending"] > 1e-12:
        lines.insert(11, f"⏳ Pending: <b>{html.escape(format_asset(c['asset'],c['pending']))}</b>")
    if admin: lines += [f"📧 Email: <code>{html.escape(str(c['email']))}</code>",f"📱 Phone: <code>{html.escape(str(c['phone']))}</code>",f"🏙 City: <b>{html.escape(str(c['city']))}</b>"]
    return "\n".join(lines)


def _ai_withdrawal_report(uid, lang="en"):
    rows=_ai_withdrawals_for(uid)
    if not rows:
        return "💸 <b>Withdrawal</b>\n\nYou have no withdrawal requests yet." if lang=="en" else "💸 <b>Withdrawal</b>\n\nWeli ma lihid withdrawal request."
    rows=sorted(rows,key=lambda x:str(x.get("time", "")),reverse=True)[:10]
    lines=["💸 <b>YOUR WITHDRAWALS</b>",""] if lang=="en" else ["💸 <b>WITHDRAWAL-KAAGA</b>",""]
    for w in rows:
        lines.append(f"🧾 <code>{html.escape(str(w.get('id','N/A')))}</code> | {html.escape(str(w.get('status','unknown')).upper())} | {html.escape(str(w.get('asset','USD')))} {float(w.get('amount',0) or 0):,.6f} | ${float(w.get('amount_usd',0) or 0):,.2f}")
    return "\n".join(lines)


def _ai_system_overview(lang="en", admin=False):
    if admin:
        sc=_ai_system_context()
        if lang=="so":
            return ("👑 <b>ADMIN AI — LIVE SYSTEM DASHBOARD</b>\n\n"
                    f"👥 Users: <b>{sc['users']}</b>\n👑 Admins: <b>{sc['admins']}</b>\n📥 Downloads: <b>{sc['downloads']}</b>\n"
                    f"💎 Premium: <b>{sc['premium']}</b>\n🔐 Premium verification: <b>{sc['premium_verification']}</b>\n"
                    f"🪙 Crypto: <b>{sc['crypto']}</b>\n⏳ Hold: <b>{sc['crypto_hold']}</b>\n💰 Minimum: <b>${sc['crypto_min_deposit']:.2f}</b>\n"
                    f"💸 Crypto fee: <b>{sc['crypto_fee_percent']:.2f}%</b>\n📲 Verification: <b>{sc['verify']}</b>\n📢 Force Join: <b>{'OPEN' if sc['force_join'] else 'CLOSED'}</b>")
        return ("👑 <b>ADMIN AI — LIVE SYSTEM DASHBOARD</b>\n\n"
                f"👥 Users: <b>{sc['users']}</b>\n👑 Admins: <b>{sc['admins']}</b>\n📥 Downloads: <b>{sc['downloads']}</b>\n"
                f"💎 Premium: <b>{sc['premium']}</b>\n🔐 Premium verification: <b>{sc['premium_verification']}</b>\n"
                f"🪙 Crypto: <b>{sc['crypto']}</b>\n⏳ Hold: <b>{sc['crypto_hold']}</b>\n💰 Minimum: <b>${sc['crypto_min_deposit']:.2f}</b>\n"
                f"💸 Crypto fee: <b>{sc['crypto_fee_percent']:.2f}%</b>\n📲 Verification: <b>{sc['verify']}</b>\n📢 Force Join: <b>{'OPEN' if sc['force_join'] else 'CLOSED'}")
    count=len(premium_platform_names())
    if lang=="so":
        return ("🤖 <b>CAWIMAADDA ADEEGGA</b>\n\n"
                "Waxaan kaa caawin karaa account-kaaga, Balance, Premium/Trial, downloads, Music, Withdrawal, Referral, verification, Crypto iyo khaladaadka adeegga.\n\n"
                f"💎 Premium/Trial: <b>{count} platforms</b>\n"
                "Waxaan kuu sharxi karaa waxa aad samaynayso marka dhibaato dhacdo, laakiin ma bixinayo xogta gudaha, maamulka, amniga ama hababka system-ka.")
    return ("🤖 <b>SERVICE HELP</b>\n\n"
            "I can help with your account, Balance, Premium/Trial, downloads, Music, Withdrawal, Referral, verification, Crypto and service errors.\n\n"
            f"💎 Premium/Trial: <b>{count} platforms</b>\n"
            "I can explain what you should do when something goes wrong, but I do not expose internal system, admin, security or implementation details.")


def _ai_intent_answer(uid, q, admin=False, lang="en"):
    q=re.sub(r"\s+"," ",(q or "").lower().strip())
    c=_ai_user_context(uid)
    if not q: return _ai_help_text(lang,admin)

    # Admin/system queries first so an admin asking about the system gets the dashboard.
    if admin and any(x in q for x in ["system status","system dashboard","dashboard","settings","xaaladda bot","system-ka","system"]):
        sc=_ai_system_context()
        if lang=="so":
            return ("👑 <b>ADMIN AI — LIVE SYSTEM DASHBOARD</b>\n\n"
                    f"👥 Users: <b>{sc['users']}</b>\n👑 Admins: <b>{sc['admins']}</b>\n📥 Downloads: <b>{sc['downloads']}</b>\n"
                    f"💎 Premium: <b>{sc['premium']}</b>\n🔐 Premium verification: <b>{sc['premium_verification']}</b>\n"
                    f"🪙 Crypto: <b>{sc['crypto']}</b>\n⏳ Hold: <b>{sc['crypto_hold']}</b>\n💰 Minimum: <b>${sc['crypto_min_deposit']:.2f}</b>\n"
                    f"💸 Crypto fee: <b>{sc['crypto_fee_percent']:.2f}%</b>\n📲 SMS: <b>{sc['sms']}</b> | WhatsApp: <b>{sc['whatsapp']}</b> | Verify: <b>{sc['verify']}</b>\n"
                    f"▶️ RapidAPI YouTube: <b>{'READY' if sc['rapidapi_youtube'] else 'NOT SET'}</b>\n📧 Email API: <b>{'READY' if sc['resend_email'] else 'NOT SET'}</b>\n📢 Force Join: <b>{'OPEN' if sc['force_join'] else 'CLOSED'}</b>")
        return ("👑 <b>ADMIN AI — LIVE SYSTEM DASHBOARD</b>\n\n"
                f"👥 Users: <b>{sc['users']}</b>\n👑 Admins: <b>{sc['admins']}</b>\n📥 Downloads: <b>{sc['downloads']}</b>\n"
                f"💎 Premium: <b>{sc['premium']}</b>\n🔐 Premium verification: <b>{sc['premium_verification']}</b>\n"
                f"🪙 Crypto: <b>{sc['crypto']}</b>\n⏳ Hold: <b>{sc['crypto_hold']}</b>\n💰 Minimum: <b>${sc['crypto_min_deposit']:.2f}</b>\n"
                f"💸 Crypto fee: <b>{sc['crypto_fee_percent']:.2f}%</b>\n📲 SMS: <b>{sc['sms']}</b> | WhatsApp: <b>{sc['whatsapp']}</b> | Verify: <b>{sc['verify']}</b>\n"
                f"▶️ RapidAPI YouTube: <b>{'READY' if sc['rapidapi_youtube'] else 'NOT SET'}</b>\n📧 Email API: <b>{'READY' if sc['resend_email'] else 'NOT SET'}</b>\n📢 Force Join: <b>{'OPEN' if sc['force_join'] else 'CLOSED'}")

    if any(x in q for x in ["balance","haraag","haraaga","my money","how much money","lacag intee"]):
        if c["balance_locked"]:
            if lang=="so": return _ai_user_report(uid,False,lang)+"\n\n🔒 Balance-kaagu hadda waa xiran yahay. La xiriir Customer/Admin si dib loogu furo."
            return _ai_user_report(uid,False,lang)+"\n\n🔒 Your balance is currently closed. Contact Customer/Admin to reactivate it."
        pending_line=(f"\nPending: <b>{html.escape(format_asset(c['asset'],c['pending']))}</b>" if c["pending"]>1e-12 else "")
        crypto_visible=crypto_system_open() and (c["portfolio_usd"]>1e-12 or is_crypto(c["asset"]))
        if lang=="so":
            base=f"💰 <b>HARAAGAAGA</b>\n\nAvailable: <b>{html.escape(format_asset(c['asset'],c['balance']))}</b>\nBlocked: <b>{html.escape(format_asset(c['asset'],c['blocked']))}</b>{pending_line}"
            if crypto_visible: base+=f"\nPortfolio: <b>${c['portfolio_usd']:,.2f}</b>\nTotal assets: <b>${c['total_assets_usd']:,.2f}</b>"
            return base
        base=f"💰 <b>YOUR BALANCE</b>\n\nAvailable: <b>{html.escape(format_asset(c['asset'],c['balance']))}</b>\nBlocked: <b>{html.escape(format_asset(c['asset'],c['blocked']))}</b>{pending_line}"
        if crypto_visible: base+=f"\nPortfolio: <b>${c['portfolio_usd']:,.2f}</b>\nTotal assets: <b>${c['total_assets_usd']:,.2f}</b>"
        return base

    if any(x in q for x in ["blocked","block","xiran","locked","hold","lacagta la qabtay"]):
        if lang=="so": return f"🔒 <b>BLOCKED / HOLD</b>\n\nBlocked amount: <b>{html.escape(format_asset(c['asset'],c['blocked']))}</b>\nBalance status: <b>{'CLOSED' if c['balance_locked'] else 'OPEN'}</b>\n" + (f"\n⏳ Pending withdrawal: <b>{html.escape(format_asset(c['asset'],c['pending']))}</b>" if c['pending']>1e-12 else "") + "\n\nHaddii lacagtu xanniban tahay ama withdrawal-ku sugayo, waxaan kuu sharxi karaa tallaabada xigta."
        return f"🔒 <b>BLOCKED / HOLD</b>\n\nBlocked amount: <b>{html.escape(format_asset(c['asset'],c['blocked']))}</b>\nBalance status: <b>{'CLOSED' if c['balance_locked'] else 'OPEN'}</b>" + (f"\n\n⏳ Pending withdrawal: <b>{html.escape(format_asset(c['asset'],c['pending']))}</b>" if c['pending']>1e-12 else "") + "\n\nIf funds are blocked or a withdrawal is waiting, I can explain the next step."

    if any(x in q for x in ["premium","vip","trial","tijaabo"]):
        platforms=", ".join(c["premium_platforms"])
        if lang=="so": return f"💎 <b>PREMIUM / TRIAL</b>\n\nStatus: <b>{'ACTIVE' if c['premium'] else 'NOT ACTIVE'}</b>\nExpiry: <b>{html.escape(c['premium_until'])}</b>\nTrial available: <b>{'YES' if c['trial_available'] else 'NO'}</b>\n\n🌐 <b>{c['premium_platform_count']} Platforms:</b>\n{html.escape(platforms)}\n\n⚡ Priority downloads\n🎥 Quality sare\n▶️ YouTube access\n🎵 Music/MP3 support."
        return f"💎 <b>PREMIUM / TRIAL</b>\n\nStatus: <b>{'ACTIVE' if c['premium'] else 'NOT ACTIVE'}</b>\nExpiry: <b>{html.escape(c['premium_until'])}</b>\nTrial available: <b>{'YES' if c['trial_available'] else 'NO'}</b>\n\n🌐 <b>{c['premium_platform_count']} Platforms:</b>\n{html.escape(platforms)}\n\n⚡ Priority downloads\n🎥 Higher quality\n▶️ YouTube access\n🎵 Music/MP3 support."

    if any(x in q for x in ["whatsapp","waforge"]):
        if lang=="so": return "📱 <b>WHATSAPP VERIFICATION</b>\n\nWaxaan kaa caawin karaa xaaladda verification-ka iyo tallaabada xigta. Fadlan raac verification screen-ka marka lagu weydiiyo. Xogta amniga iyo habka gudaha ee verification-ka lama soo bandhigo."
        return "📱 <b>WHATSAPP VERIFICATION</b>\n\nI can help you check your verification status and the next step. Follow the verification screen when prompted. Internal security and verification implementation details are not exposed."

    if any(x in q for x in ["sms","d7","phone verification"]):
        if lang=="so": return "📲 <b>PHONE VERIFICATION</b>\n\nWaxaan kuu sheegi karaa haddii account-kaagu verified yahay iyo waxa aad samayn karto xiga. Habka gudaha ee verification-ka lama soo bandhigo."
        return "📲 <b>PHONE VERIFICATION</b>\n\nI can tell you whether your account is verified and guide you on the next step. Internal verification implementation details are not exposed."

    if any(x in q for x in ["gmail","email verification","email code"]):
        if lang=="so": return "📧 <b>EMAIL VERIFICATION</b>\n\nHaddii account-kaagu u baahan yahay verification, raac tilmaamaha verification-ka ee bot-ka. Ha la wadaagin qof kale code ama xogtaada gaarka ah."
        return "📧 <b>EMAIL VERIFICATION</b>\n\nIf your account requires verification, follow the verification instructions shown by the bot. Never share your verification code or private account information."

    if any(x in q for x in ["verify","verification","otp","code","xaqiijin"]):
        if lang=="so": return f"🔐 <b>VERIFICATION</b>\n\nXaaladda account-kaaga: <b>{'Verified' if c['verified'] else 'Not Verified'}</b>.\n\nHaddii aan la xaqiijin, raac verification-ka bot-ka. Ha la wadaagin code-kaaga qof kale."
        return f"🔐 <b>VERIFICATION</b>\n\nYour account status: <b>{'Verified' if c['verified'] else 'Not Verified'}</b>.\n\nIf you are not verified, follow the bot's verification flow. Never share your verification code."

    if any(x in q for x in ["crypto","bitcoin","btc","ethereum","eth","usdt","coin"]):
        if not c["crypto_open"]:
            return "🪙 <b>CRYPTO</b>\n\n🔴 Crypto is currently closed by Admin." if lang=="en" else "🪙 <b>CRYPTO</b>\n\n🔴 Crypto hadda Admin ayaa xiray."
        if lang=="so": return f"🪙 <b>CRYPTO</b>\n\nStatus: <b>OPEN</b>\nDeposited/credited: <b>${c['deposited']:,.2f}</b>\nMinimum: <b>${c['crypto_minimum']:,.2f}</b>\nAccess: <b>{'ALLOWED' if c['crypto_allowed'] else 'LOCKED'}</b>\nRemaining: <b>${c['crypto_remaining']:,.2f}</b>\nFee: <b>{crypto_fee_percent():.2f}%</b>\n\nHaddii aad rabto, waxaan kuu sharxi karaa sida aad Crypto uga isticmaali karto account-kaaga."
        return f"🪙 <b>CRYPTO</b>\n\nStatus: <b>OPEN</b>\nDeposited/credited: <b>${c['deposited']:,.2f}</b>\nMinimum: <b>${c['crypto_minimum']:,.2f}</b>\nAccess: <b>{'ALLOWED' if c['crypto_allowed'] else 'LOCKED'}</b>\nRemaining: <b>${c['crypto_remaining']:,.2f}</b>\nFee: <b>{crypto_fee_percent():.2f}%</b>\n\nI can explain how to use Crypto from your account."

    if any(x in q for x in ["youtube","yt","shorts"]):
        full_free = youtube_full_free_enabled()
        if lang=="so":
            return ("▶️ <b>YOUTUBE</b>\n\n"
                    "🆓 YouTube Shorts waa Free.\n"
                    f"🎬 Full YouTube videos: <b>{'Free hadda waa furan yahay' if full_free else 'Premium/Trial ayaa loo baahan yahay'}</b>.\n"
                    "Haddii download-ku diido, ii soo dir fariinta qaladka.")
        return ("▶️ <b>YOUTUBE</b>\n\n"
                "🆓 YouTube Shorts are Free.\n"
                f"🎬 Full YouTube videos: <b>{'Free access is currently open' if full_free else 'Premium/Trial is required'}</b>.\n"
                "If the download fails, send me the error message.")

    extra_platform_terms = {
        "reddit":"Reddit", "threads":"Threads", "likee":"Likee", "vimeo":"Vimeo",
        "dailymotion":"Dailymotion", "soundcloud":"SoundCloud", "twitch":"Twitch",
        "tumblr":"Tumblr", "streamable":"Streamable", "ok.ru":"OK.ru", "okru":"OK.ru"
    }
    for term, pname in extra_platform_terms.items():
        if term in q:
            if lang=="so":
                return (f"🌐 <b>{pname}</b>\n\n"
                        f"💎 {pname} waa Premium/Trial platform.\n"
                        "🆓 Free account-ku ma download-gareyn karo platform-kan.\n"
                        "⚡ Premium/Trial wuxuu helayaa priority/high-concurrency download.\n"
                        "Haddii link-ku diido, ii soo dir link-ga iyo error-ka.")
            return (f"🌐 <b>{pname}</b>\n\n"
                    f"💎 {pname} is a Premium/Trial platform.\n"
                    "🆓 Free accounts cannot download this platform.\n"
                    "⚡ Premium/Trial gets priority/high-concurrency downloading.\n"
                    "If the link fails, send me the link and the error.")

    if any(x in q for x in [
        "download","video","tiktok","instagram","facebook","pinterest","snapchat","twitter","x.com",
        "reddit","threads","likee","vimeo","dailymotion","soundcloud","twitch","tumblr","streamable","ok.ru","okru"
    ]):
        if lang=="so": return ("📥 <b>DOWNLOADS</b>\n\n"
            "🆓 Free: TikTok, Instagram, Facebook, Pinterest, Snapchat, X/Twitter + YouTube Shorts.\n"
            "💎 Premium/Trial: dhammaan 17-ka platform: TikTok, Instagram, Facebook, Pinterest, Snapchat, X/Twitter, YouTube, Reddit, Threads, Likee, Vimeo, Dailymotion, SoundCloud, Twitch, Tumblr, Streamable iyo OK.ru.\n"
            "⚡ Premium/Trial wuxuu leeyahay priority/high-concurrency download si uu uga dheereeyo Free marka server-ka iyo platform-ku oggolaadaan.\n"
            "Haddii platform ama link gaar ahi shaqayn waayo, ii soo dir link-ga iyo fariinta qaladka; waxaan kuu tilmaami karaa tallaabada saxda ah.")
        return ("📥 <b>DOWNLOADS</b>\n\n"
            "🆓 Free: TikTok, Instagram, Facebook, Pinterest, Snapchat, X/Twitter + YouTube Shorts.\n"
            "💎 Premium/Trial: all 17 platforms: TikTok, Instagram, Facebook, Pinterest, Snapchat, X/Twitter, YouTube, Reddit, Threads, Likee, Vimeo, Dailymotion, SoundCloud, Twitch, Tumblr, Streamable and OK.ru.\n"
            "⚡ Premium/Trial uses priority/high-concurrency downloading for higher throughput when the server and platform allow it.\n"
            "If a platform or link fails, send me the link and the exact error so I can guide you to the correct next step.")

    if any(x in q for x in ["music","mp3","song","hees"]):
        if lang=="so": return "🎵 <b>MUSIC / MP3</b>\n\nWaxaad isticmaali kartaa Music flow-ka bot-ka. Audio extraction + FFmpeg ayaa loo isticmaalaa MP3. Haddii metadata la helo title/artist waa la muujin karaa."
        return "🎵 <b>MUSIC / MP3</b>\n\nUse the Music flow in the bot. Audio extraction + FFmpeg are used to create MP3. When metadata is available, title/artist can be shown."

    if any(x in q for x in ["withdraw","withdrawal","bixid","bixi","cash out","check withdrawal","withdrawal check"]):
        return _ai_withdrawal_report(uid,lang)

    if any(x in q for x in ["referral","refer","casuum","invite"]):
        if lang=="so": return f"👥 <b>REFERRAL</b>\n\nUsers aad casuuntay: <b>{c['referrals']}</b>. Reward-ka hadda: <b>${referral_reward_amount():.2f}</b> haddii system-ku sidaas u configured yahay."
        return f"👥 <b>REFERRAL</b>\n\nUsers invited: <b>{c['referrals']}</b>. Current reward: <b>${referral_reward_amount():.2f}</b> when configured by the system."

    if any(x in q for x in ["banned","ban","mamnuuc","mamnuucay"]):
        ban_status = "BANNED" if c.get("banned", False) else "NOT BANNED"
        if lang=="so": return f"🚫 <b>BAN STATUS</b>\n\nAccount-kaaga: <b>{ban_status}</b>."
        return f"🚫 <b>BAN STATUS</b>\n\nYour account: <b>{ban_status}</b>."

    if any(x in q for x in ["profile","my id","telegram id","bot id","username"]):
        return _ai_user_report(uid,False,lang)

    if any(x in q for x in ["language","luqad","afaan"]):
        return _ai_choose_language_text()

    if any(x in q for x in ["force join","channel","join channel"]):
        if lang=="so": return f"📢 <b>FORCE JOIN</b>\n\nSystem status: <b>{'OPEN' if CHANNEL_WINDOW_OPEN else 'CLOSED'}</b>. Haddii channels la maamulo, user-ku waa inuu ku biiro channels-ka loo baahan yahay kadibna CONFIRM sameeyo."
        return f"📢 <b>FORCE JOIN</b>\n\nSystem status: <b>{'OPEN' if CHANNEL_WINDOW_OPEN else 'CLOSED'}</b>. If channels are active, the user must join the required channels and then confirm."

    if any(x in q for x in ["fee","gas","commission"]):
        if lang=="so": return f"💸 <b>FEES</b>\n\nCrypto fee-ga hadda waa <b>{crypto_fee_percent():.2f}%</b>. Haddii aad ii sheegto waxa aad samaynayso, waxaan kuu sharxi karaa kharashka ku khuseeya."
        return f"💸 <b>FEES</b>\n\nThe current Crypto fee is <b>{crypto_fee_percent():.2f}%</b>. Tell me what you are doing and I can explain the applicable charge."

    if any(x in q for x in ["help","caawi","sidee","what can you do","maxaad qaban","all system"]):
        return _ai_help_text(lang,admin)

    if admin:
        candidates=re.findall(r"(?:@?[A-Za-z0-9_]{5,32}|\d{6,20})",q)
        for cand in candidates:
            found=_ai_find_user(cand)
            if found: return _ai_user_report(found,True,lang)

    if lang=="so":
        return ("🤖 <b>Waan fahmay.</b>\n\nWaxaan kaa caawin karaa Balance, Premium/Trial, downloads, Music, Withdrawal, Referral, verification, Crypto iyo khaladaadka adeegga.\n\nQor dhibaatadaada sida aad u aragtay; button looma baahna.")
    return ("🤖 <b>I understand.</b>\n\nI can help with Balance, Premium/Trial, downloads, Music, Withdrawal, Referral, verification, Crypto and service errors.\n\nDescribe the problem in your own words; no button is required.")


def _admin_stats_text(kind, lang="en"):
    if kind=="users":
        active=sum(1 for u in users.values() if not u.get("banned")); banned=sum(1 for u in users.values() if u.get("banned"))
        return (f"👥 <b>USERS</b>\n\nTotal: <b>{len(users)}</b>\nActive: <b>{active}</b>\nBanned: <b>{banned}</b>" if lang=="en" else f"👥 <b>USERS</b>\n\nDhammaan: <b>{len(users)}</b>\nActive: <b>{active}</b>\nBanned: <b>{banned}</b>")
    if kind=="balances":
        total=sum(float(u.get("balance",0) or 0) for u in users.values()); blocked=sum(float(u.get("blocked",0) or 0) for u in users.values())
        locked=sum(1 for u in users.values() if u.get("balance_locked"))
        return (f"💰 <b>BALANCE STATS</b>\n\nUser balances (stored assets): <b>{total:,.6f}</b>\nBlocked: <b>{blocked:,.6f}</b>\nLocked accounts: <b>{locked}</b>" if lang=="en" else f"💰 <b>BALANCE STATS</b>\n\nBalance-yada users-ka: <b>{total:,.6f}</b>\nBlocked: <b>{blocked:,.6f}</b>\nAccounts xiran: <b>{locked}</b>")
    if kind=="withdrawals":
        pending=sum(1 for w in withdraws if str(w.get("status","pending")).lower()=="pending")
        confirmed=sum(1 for w in withdraws if str(w.get("status","")).lower() in ("confirmed","paid","completed"))
        rejected=sum(1 for w in withdraws if str(w.get("status","")).lower() in ("rejected","reject"))
        return (f"💸 <b>WITHDRAWAL STATS</b>\n\nTotal: <b>{len(withdraws)}</b>\nPending: <b>{pending}</b>\nConfirmed/Paid: <b>{confirmed}</b>\nRejected: <b>{rejected}</b>" if lang=="en" else f"💸 <b>WITHDRAWAL STATS</b>\n\nDhammaan: <b>{len(withdraws)}</b>\nPending: <b>{pending}</b>\nConfirmed/Paid: <b>{confirmed}</b>\nRejected: <b>{rejected}</b>")
    if kind=="banned":
        rows=[(uid,u) for uid,u in users.items() if u.get("banned")][:30]
        if not rows: return "🚫 No banned users." if lang=="en" else "🚫 Ma jiraan users banned ah."
        return ("🚫 <b>BANNED USERS</b>\n\n" if lang=="en" else "🚫 <b>BANNED USERS</b>\n\n")+"\n".join(f"{i+1}. {('@'+str(u.get('username'))) if u.get('username') else uid} — <code>{uid}</code>" for i,(uid,u) in enumerate(rows))
    if kind=="locks":
        rows=[(uid,u) for uid,u in users.items() if u.get("balance_locked")][:30]
        return ("🔒 <b>BALANCE LOCKS</b>\n\n"+ ("No locked users." if not rows else "\n".join(f"{i+1}. {('@'+str(u.get('username'))) if u.get('username') else uid} — <code>{uid}</code>" for i,(uid,u) in enumerate(rows))))
    if kind=="admins":
        admins=get_admin_ids()
        return ("👑 <b>ADMINS</b>\n\n"+"\n".join(f"• <code>{a}</code>" for a in admins))
    return ""


# ---------- Main bot entry: opens the dedicated Customer AI bot ----------
@bot.message_handler(func=lambda m: m.text == "🤖CUSTOMER AI")
def customer_ai_handler(m):
    global _CUSTOMER_AI_USERNAME_CACHE
    touch_user(m.from_user.id)
    if bot_locked_guard(m) or banned_guard(m): return
    username=_customer_ai_identity()
    if is_admin(m.from_user.id):
        token_ready=bool(CUSTOMER_AI_BOT_TOKEN)
        status="🟢 CONFIGURED" if token_ready and username else "🔴 NOT CONFIGURED"
        bot.send_message(m.chat.id,
            "🤖 <b>CUSTOMER AI ADMIN</b>\n\n"
            f"Status: <b>{status}</b>\n"
            f"AI Bot: <b>{('@'+username) if username else 'Not detected'}</b>\n"
            f"Token variable: <code>CUSTOMER_AI_BOT_TOKEN</code>\n\n"
            "Customer AI-ga wuxuu isticmaalaa isla MongoDB-ga main bot-ka, sidaas darteed account-ka user-ka ayuu si toos ah uga akhriyaa.\n\n"
            "AI bot-ka dhexdiisa buttons ma jiraan; waxaa lagu shaqeeyaa /commands iyo su'aalo caadi ah.\n\n"
            "<b>Admin commands:</b> <code>/system</code>, <code>/user ID|BOTID|@username</code>, <code>/users</code>, <code>/balances</code>, <code>/withdrawals</code>, <code>/banned</code>, <code>/locks</code>, <code>/admins</code>")
        return
    if CUSTOMER_AI_BOT_TOKEN and username:
        lang = get_user_lang(m.from_user.id)
        if lang == "so":
            ai_text = f"🤖 <b>CAWIMAAD AI</b>\n@{html.escape(username)}"
        else:
            ai_text = f"🤖 <b>CUSTOMER AI</b>\n@{html.escape(username)}"
        kb=InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🤖 OPEN CUSTOMER AI", url=f"https://t.me/{username}"))
        bot.send_message(m.chat.id, ai_text, reply_markup=kb)
    else:
        bot.send_message(m.chat.id,
            "⚠️ <b>Customer AI lama shidin.</b>\n\n"
            "Ku dar Railway Variable: <code>CUSTOMER_AI_BOT_TOKEN</code> oo ah token-ka BotFather ee Customer AI bot-ka, kadib Redeploy samee.")


# ---------- Dedicated Customer AI bot handlers ----------
if customer_ai_bot:
    @customer_ai_bot.message_handler(commands=['start'])
    def customer_ai_start(message):
        uid=str(message.from_user.id)
        if uid not in users:
            users[uid]={"username":message.from_user.username or "","first_name":message.from_user.first_name or "User",
                        "balance":0.0,"blocked":0.0,"ref":random_ref(),"bot_id":random_botid(),"invited":0,"banned":False,
                        "verified":False,"email_verified":False,"phone_verified":False,"whatsapp_verified":False,"verification_method":None,
                        "balance_locked":False,"balance_activation_code":None,"balance_lock_until":None,"quick_access":False,"youtube_30m":False,
                        "premium_until":None,"premium_warning_sent":False,"trial_used":False,"trial_pending":False,"trial_version_used":None,
                        "trial_pending_version":None,"referral_50_rewarded":False,"referred_by":None,"joined_date":datetime.now().strftime("%Y-%m-%d"),
                        "last_seen_at":datetime.now(timezone.utc).isoformat(),"month":now_month(),"language":None,"currency":"USD","balance_asset":"USD",
                        "gender":None,"city":None,"customer_ai_language":None}
            save_user(uid)
        else:
            users[uid]["username"]=message.from_user.username or users[uid].get("username","")
            users[uid]["first_name"]=message.from_user.first_name or users[uid].get("first_name","User")
            touch_user(uid)
        if users[uid].get("banned"):
            customer_ai_bot.send_message(message.chat.id,"🚫 You are banned from this service. / Waxaad ka mamnuucan tahay adeeggan."); return
        if not _ai_language(uid):
            customer_ai_bot.send_message(message.chat.id,_ai_choose_language_text()); return
        lang=_ai_language(uid)
        customer_ai_bot.send_message(message.chat.id,
            ("🤖 <b>SOO DHAWOOW CUSTOMER AI</b>\n\nQor su'aashaada si caadi ah. Waxaan kuu hayaa account-aware support, system explanations iyo live account checks marka xogtu jirto.\n\n<code>/help</code> si aad u aragto commands-ka."
             if lang=="so" else
             "🤖 <b>WELCOME TO CUSTOMER AI</b>\n\nAsk your question naturally. I provide account-aware support, system explanations and live account checks when data is available.\n\nUse <code>/help</code> to see all commands."))

    @customer_ai_bot.message_handler(commands=['english','en'])
    def customer_ai_english(message):
        uid=str(message.from_user.id); touch_user(uid) if uid in users else None
        if uid not in users: customer_ai_start(message); return
        _set_ai_language(uid,"en")
        customer_ai_bot.send_message(message.chat.id,"🇬🇧 <b>English selected.</b>\n\nYou can now ask me anything about your account or the system. Use <code>/help</code> for commands.")

    @customer_ai_bot.message_handler(commands=['somali','so'])
    def customer_ai_somali(message):
        uid=str(message.from_user.id); touch_user(uid) if uid in users else None
        if uid not in users: customer_ai_start(message); return
        _set_ai_language(uid,"so")
        customer_ai_bot.send_message(message.chat.id,"🇸🇴 <b>Somali waa la doortay.</b>\n\nHadda wax kasta waad i weydiin kartaa. Isticmaal <code>/help</code> si aad u aragto commands-ka.")

    @customer_ai_bot.message_handler(commands=['language','lang'])
    def customer_ai_language(message):
        customer_ai_bot.send_message(message.chat.id,_ai_choose_language_text())

    @customer_ai_bot.message_handler(commands=['help'])
    def customer_ai_help(message):
        uid=str(message.from_user.id); lang=_ai_language(uid) or "en"
        customer_ai_bot.send_message(message.chat.id,_ai_help_text(lang,is_admin(uid)))

    @customer_ai_bot.message_handler(commands=['balance'])
    def customer_ai_balance(message):
        uid=str(message.from_user.id); lang=_ai_language(uid) or "en"
        customer_ai_bot.send_chat_action(message.chat.id,"typing"); customer_ai_bot.send_message(message.chat.id,_ai_intent_answer(uid,"balance",is_admin(uid),lang))

    @customer_ai_bot.message_handler(commands=['profile','id'])
    def customer_ai_profile(message):
        uid=str(message.from_user.id); lang=_ai_language(uid) or "en"
        customer_ai_bot.send_message(message.chat.id,_ai_user_report(uid,False,lang))

    @customer_ai_bot.message_handler(commands=['premium','trial'])
    def customer_ai_premium(message):
        uid=str(message.from_user.id); lang=_ai_language(uid) or "en"
        customer_ai_bot.send_message(message.chat.id,_ai_intent_answer(uid,"premium trial",is_admin(uid),lang))

    @customer_ai_bot.message_handler(commands=['verification','verify','otp'])
    def customer_ai_verification(message):
        uid=str(message.from_user.id); lang=_ai_language(uid) or "en"
        customer_ai_bot.send_message(message.chat.id,_ai_intent_answer(uid,"verification otp",is_admin(uid),lang))

    @customer_ai_bot.message_handler(commands=['crypto'])
    def customer_ai_crypto(message):
        uid=str(message.from_user.id); lang=_ai_language(uid) or "en"
        customer_ai_bot.send_message(message.chat.id,_ai_intent_answer(uid,"crypto usdt btc",is_admin(uid),lang))

    @customer_ai_bot.message_handler(commands=['downloads','download'])
    def customer_ai_downloads(message):
        uid=str(message.from_user.id); lang=_ai_language(uid) or "en"
        customer_ai_bot.send_message(message.chat.id,_ai_intent_answer(uid,"download video tiktok youtube instagram",is_admin(uid),lang))

    @customer_ai_bot.message_handler(commands=['music','mp3'])
    def customer_ai_music(message):
        uid=str(message.from_user.id); lang=_ai_language(uid) or "en"
        customer_ai_bot.send_message(message.chat.id,_ai_intent_answer(uid,"music mp3",is_admin(uid),lang))

    @customer_ai_bot.message_handler(commands=['withdrawal','withdraw'])
    def customer_ai_withdrawal(message):
        uid=str(message.from_user.id); lang=_ai_language(uid) or "en"
        customer_ai_bot.send_message(message.chat.id,_ai_withdrawal_report(uid,lang))

    @customer_ai_bot.message_handler(commands=['referral','refer'])
    def customer_ai_referral(message):
        uid=str(message.from_user.id); lang=_ai_language(uid) or "en"
        customer_ai_bot.send_message(message.chat.id,_ai_intent_answer(uid,"referral",is_admin(uid),lang))

    @customer_ai_bot.message_handler(commands=['system'])
    def customer_ai_system(message):
        uid=str(message.from_user.id); lang=_ai_language(uid) or "en"
        if is_admin(uid):
            customer_ai_bot.send_message(message.chat.id,_ai_intent_answer(uid,"system dashboard",True,lang))
        else:
            customer_ai_bot.send_message(message.chat.id,_ai_system_overview(lang,False))

    @customer_ai_bot.message_handler(commands=['user'])
    def customer_ai_user(message):
        uid=str(message.from_user.id); lang=_ai_language(uid) or "en"
        if not is_admin(uid):
            customer_ai_bot.send_message(message.chat.id,"❌ Admin-only command." if lang=="en" else "❌ Command-kan Admin oo keliya ayaa isticmaali kara."); return
        parts=message.text.split(maxsplit=1)
        if len(parts)<2:
            customer_ai_bot.send_message(message.chat.id,"Usage: <code>/user USER_ID</code> or <code>/user BOT_ID</code> or <code>/user @username</code>"); return
        found=_ai_find_user(parts[1])
        customer_ai_bot.send_message(message.chat.id,_ai_user_report(found,True,lang) if found else ("❌ User not found." if lang=="en" else "❌ User-ka lama helin."))

    @customer_ai_bot.message_handler(commands=['panel','admin','stats'])
    def customer_ai_admin_panel(message):
        uid=str(message.from_user.id); lang=_ai_language(uid) or "en"
        if not is_admin(uid):
            customer_ai_bot.send_message(message.chat.id,"❌ Admin-only command."); return
        kb=InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("📊 USERS",callback_data="cai:users"),InlineKeyboardButton("💰 BALANCES",callback_data="cai:balances"))
        kb.add(InlineKeyboardButton("💸 WITHDRAWALS",callback_data="cai:withdrawals"),InlineKeyboardButton("👑 ADMINS",callback_data="cai:admins"))
        kb.add(InlineKeyboardButton("📢 BROADCAST",callback_data="cai:broadcast"),InlineKeyboardButton("🔄 REFRESH",callback_data="cai:users"))
        customer_ai_bot.send_message(message.chat.id,"🤖 <b>CUSTOMER AI ADMIN PANEL</b>\n\nChoose an admin action:",reply_markup=kb)

    @customer_ai_bot.callback_query_handler(func=lambda c:c.data.startswith("cai:"))
    def customer_ai_admin_callback(call):
        uid=str(call.from_user.id)
        if not is_admin(uid):
            customer_ai_bot.answer_callback_query(call.id,"Admin only",show_alert=True); return
        action=call.data.split(":",1)[1]
        if action=="broadcast":
            msg=customer_ai_bot.send_message(call.message.chat.id,"📢 Send the broadcast text for all users:")
            customer_ai_bot.register_next_step_handler(msg,customer_ai_broadcast_process)
            customer_ai_bot.answer_callback_query(call.id)
            return
        customer_ai_bot.answer_callback_query(call.id)
        customer_ai_bot.send_message(call.message.chat.id,_admin_stats_text(action if action in {"users","balances","withdrawals","admins"} else "users","en"))

    def customer_ai_broadcast_process(message):
        if not is_admin(message.from_user.id): return
        text=(message.text or "").strip()
        if not text:
            customer_ai_bot.send_message(message.chat.id,"❌ Empty message."); return
        sent=0
        for uid in list(users):
            try: customer_ai_bot.send_message(int(uid),text); sent+=1
            except: pass
        customer_ai_bot.send_message(message.chat.id,f"✅ Broadcast sent to {sent} users.")

    @customer_ai_bot.message_handler(commands=['promo','streak','health','broadcast'])
    def customer_ai_extra_admin_commands(message):
        uid=str(message.from_user.id)
        if not is_admin(uid):
            customer_ai_bot.send_message(message.chat.id,"❌ Admin-only command."); return
        cmd=(message.text or "").split()[0].lower()
        if cmd=="/promo":
            customer_ai_bot.send_message(message.chat.id,"🎟 Promo control is available in the main bot Admin Panel → 🎟 PROMO CODES.")
        elif cmd=="/streak":
            customer_ai_bot.send_message(message.chat.id,"🔥 Streak control is available in the main bot Admin Panel → 🔥 STREAK SYSTEM.")
        elif cmd=="/health":
            customer_ai_bot.send_message(message.chat.id,f"🟢 <b>HEALTH</b>\n\nUsers: {len(users)}\nDownloads: {int(videos_data.get('total',0) or 0)}\nAdmins: {len(get_admin_ids())}\nCustomer AI: {'ONLINE' if customer_ai_bot else 'OFFLINE'}")
        elif cmd=="/broadcast":
            msg=customer_ai_bot.send_message(message.chat.id,"📢 Send broadcast text:"); customer_ai_bot.register_next_step_handler(msg,customer_ai_broadcast_process)

    @customer_ai_bot.message_handler(commands=['users','balances','withdrawals','withdrawal_stats','banned','locks','admins'])
    def customer_ai_admin_reports(message):
        uid=str(message.from_user.id); lang=_ai_language(uid) or "en"
        if not is_admin(uid):
            customer_ai_bot.send_message(message.chat.id,"❌ Admin-only command." if lang=="en" else "❌ Command-kan Admin oo keliya ayaa isticmaali kara."); return
        cmd=(message.text or "").split()[0].lower()
        kind={"/users":"users","/balances":"balances","/withdrawals":"withdrawals","/withdrawal_stats":"withdrawals","/banned":"banned","/locks":"locks","/admins":"admins"}.get(cmd,"users")
        customer_ai_bot.send_message(message.chat.id,_admin_stats_text(kind,lang))

    @customer_ai_bot.message_handler(func=lambda m: bool(m.text))
    def customer_ai_message(message):
        uid=str(message.from_user.id)
        if uid not in users:
            customer_ai_start(message); return
        if users[uid].get("banned"):
            customer_ai_bot.send_message(message.chat.id,"🚫 You are banned from this service."); return
        touch_user(uid)
        lang=_ai_language(uid)
        if not lang:
            customer_ai_bot.send_message(message.chat.id,_ai_choose_language_text()); return
        customer_ai_bot.send_chat_action(message.chat.id,"typing")
        answer=_ai_intent_answer(uid,message.text or "",is_admin(uid),lang)
        customer_ai_bot.send_message(message.chat.id,answer)


@bot.message_handler(func=lambda m: m.text == "💸 WITHDRAWAL")
def withdraw_menu(m):
    touch_user(m.from_user.id)
    users.setdefault(str(m.from_user.id),{})["withdraw_flow"]=True
    save_user(str(m.from_user.id))
    if balance_is_locked(str(m.from_user.id)):
        bot.send_message(m.chat.id,balance_locked_message(str(m.from_user.id)),reply_markup=localized_user_menu(str(m.from_user.id))); return
    if banned_guard(m):
        return
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("USDT-BEP20")
    kb.add("🔙 CANCEL")
    try:
        bot.send_message(m.chat.id, "Select withdrawal method:", reply_markup=kb)
    except: pass

@bot.message_handler(func=lambda m: m.text in ["USDT-BEP20", "🔙 CANCEL"])
def withdraw_method(m):
    if m.text == "🔙 CANCEL":
        uid=str(m.from_user.id); users.get(uid,{}).pop("withdraw_flow",None); users.get(uid,{}).pop("temp_addr",None); save_user(uid); back_to_main_menu(m)
        return
    if m.text == "USDT-BEP20":
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("🔙 CANCEL")
        try:
            msg = bot.send_message(m.chat.id, "Enter your USDT BEP20 address (must start with 0x)\nOr press 🔙 CANCEL", reply_markup=kb)
            bot.register_next_step_handler(msg, withdraw_address_step)
        except: pass

def withdraw_address_step(m):
    uid = str(m.from_user.id)
    text = (m.text or "").strip()
    if text == "🔙 CANCEL":
        users.get(uid,{}).pop("withdraw_flow",None); users.get(uid,{}).pop("temp_addr",None); save_user(uid); back_to_main_menu(m)
        return
    if not text.startswith("0x"):
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("🔙 CANCEL")
        try:
            msg = bot.send_message(m.chat.id, "❌ Invalid address. Must start with 0x.\nTry again or press 🔙 CANCEL", reply_markup=kb)
            bot.register_next_step_handler(msg, withdraw_address_step)
        except: pass
        return
    users[uid]["temp_addr"] = text
    save_user(uid)
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🔙 CANCEL")
    try:
        min_w = get_setting("min_withdrawal", 1.0)
        msg = bot.send_message(m.chat.id, f"Enter withdrawal amount in {cur_code(uid)}\nMinimum: {money_text(uid,min_w)}\nBalance: {money_text(uid,users[uid]['balance'])}\n💲 Fee: {float(get_setting('fee_percent',0.0) or 0.0):.4f}%\n📉 Low W/D Fee: ${float(get_setting('low_fee',0.0) or 0.0):.8f}\n\nOr press 🔙 CANCEL", reply_markup=kb)
        bot.register_next_step_handler(msg, withdraw_amount_step)
    except: pass

def withdraw_amount_step(m):
    uid=str(m.from_user.id); text=(m.text or "").strip()
    if text=="🔙 CANCEL":
        users.get(uid,{}).pop("withdraw_flow",None); users.get(uid,{}).pop("temp_addr",None); save_user(uid); back_to_main_menu(m); return
    try: local_amt=float(text)
    except:
        msg=bot.send_message(m.chat.id,"❌ Invalid number. Try again or press 🔙 CANCEL"); bot.register_next_step_handler(msg,withdraw_amount_step); return
    code=cur_code(uid); price=asset_usd_price(code)
    if price<=0: bot.send_message(m.chat.id,"❌ Current market rate unavailable.",reply_markup=localized_user_menu(uid)); return
    asset_amt=local_amt; usd_amt=asset_to_usd(code,asset_amt); available=available_asset_amount(uid)
    min_w=float(get_setting("min_withdrawal",1.0) or 1.0)
    if usd_amt<min_w: bot.send_message(m.chat.id,f"❌ Minimum withdrawal is {money_text(uid,min_w)}",reply_markup=localized_user_menu(uid)); return
    if asset_amt>available: bot.send_message(m.chat.id,f"❌ Insufficient available balance. Available: {format_asset(code,available)}",reply_markup=localized_user_menu(uid)); return
    fee_pct=float(get_setting("fee_percent",0.0) or 0.0); low_fee=float(get_setting("low_fee",0.0) or 0.0)
    calculated_fee=usd_amt*fee_pct/100.0; low_fee_pct=(low_fee/usd_amt*100.0) if usd_amt > 0 and low_fee > 0 else 0.0; total_fee=calculated_fee+low_fee; amount_sent=max(0.0,usd_amt-total_fee)
    wid=random.randint(10000,99999); users[uid]["balance"]=round(balance_amount(uid)-asset_amt,12); save_user(uid)
    withdrawal={"id":wid,"user":uid,"asset":code,"amount":asset_amt,"amount_usd":usd_amt,"fee":calculated_fee,"low_fee":low_fee,"amount_sent":amount_sent,"blocked":asset_amt,"blocked_usd":usd_amt,"address":users[uid].get("temp_addr","N/A"),"status":"pending","time":datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    users[uid].pop("withdraw_flow",None); users[uid].pop("temp_addr",None); save_user(uid)
    withdraws.append(withdrawal); save_withdraws(); log_activity(uid,"withdrawal_requested",{"asset":code,"amount":asset_amt,"amount_usd":usd_amt,"request_id":wid})
    receipt_text=(f"✅ <b>WITHDRAWAL REQUEST RECEIVED</b>\n"
                   f"━━━━━━━━━━━━━━━━━━\n"
                   f"🧾 <b>Request ID:</b> <code>{wid}</code>\n"
                   f"💰 <b>Amount:</b> {format_asset(code,asset_amt)}\n"
                   f"💵 <b>USD Value:</b> ${usd_amt:.2f}\n"
                   f"💲 <b>Fee:</b> {fee_pct:.4f}% (-${calculated_fee:.2f})\n"
                   f"📉 <b>Low W/D Fee:</b> ${low_fee:.8f} ({low_fee_pct:.4f}%)\n"
                   f"💸 <b>Total Fee:</b> ${total_fee:.8f}\n"
                   f"💵 <b>Amount Sent:</b> ${amount_sent:.2f}\n"
                   f"🏦 <b>Address:</b> {html.escape(str(withdrawal['address']))}\n"
                   f"⏳ <b>Status:</b> PENDING\n\n"
                   f"Your requested amount is now counted as <b>Pending Amount</b> until Admin makes a decision.")
    try: bot.send_message(int(uid),receipt_text)
    except: pass
    admin_text=(f"💳 <b>NEW WITHDRAWAL</b>\n\n"
                f"👤 User: <code>{uid}</code>\n"
                f"🤖 BOT ID: <code>{html.escape(str(users[uid].get('bot_id','N/A')))}</code>\n"
                f"💰 Amount: {format_asset(code,asset_amt)}\n"
                f"💵 USD value: ${usd_amt:.2f}\n"
                f"💲 Fee: {fee_pct:.4f}% (-${calculated_fee:.2f})\n"
                f"📉 Low W/D Fee: ${low_fee:.8f} ({low_fee_pct:.4f}%)\n"
                f"💸 Total Fee: ${total_fee:.8f}\n"
                f"💵 Amount Sent: ${amount_sent:.2f}\n"
                f"🧾 Request ID: <code>{wid}</code>\n"
                f"🏦 Address: {html.escape(str(withdrawal['address']))}\n"
                f"⏳ Status: <b>PENDING</b>\n\n"
                f"ℹ️ Pending is separate from Blocked Amount until Admin presses <b>BAN MONEY</b>.")
    markup=InlineKeyboardMarkup(row_width=2); markup.add(InlineKeyboardButton("✅ CONFIRM",callback_data=f"confirm_{wid}"),InlineKeyboardButton("❌ REJECT",callback_data=f"reject_{wid}"),InlineKeyboardButton("🚫 BAN USER",callback_data=f"ban_{uid}"),InlineKeyboardButton("💰 BAN MONEY",callback_data=f"block_{wid}"))
    for admin in ADMIN_IDS:
        try: bot.send_message(admin,admin_text,reply_markup=markup)
        except: pass

@bot.callback_query_handler(func=lambda call: call.data.startswith(("confirm_", "reject_", "ban_", "block_")))
def admin_callbacks(call):
    if not is_admin(call.from_user.id):
        try:
            bot.answer_callback_query(call.id, "❌ You are not admin")
        except: pass
        return

    data = call.data
    if data.startswith("confirm_"):
        wid = int(data.split("_")[1])
        w = next((x for x in withdraws if x["id"] == wid), None)
        if not w or w["status"] != "pending":
            return
        w["status"] = "paid"
        # Pending withdrawal was reserved by reducing balance. It becomes
        # completed now; it was never part of Blocked Amount.
        save_user(w["user"])
        save_withdraws()
        try:
            bot.answer_callback_query(call.id, "✅ Confirmed")
            bot.send_message(int(w["user"]), f"✅ Withdrawal #{wid} approved!")
        except: pass
    elif data.startswith("reject_"):
        wid = int(data.split("_")[1])
        w = next((x for x in withdraws if x["id"] == wid), None)
        if not w or w["status"] != "pending":
            return
        w["status"] = "rejected"
        users[w["user"]]["balance"] = round(balance_amount(w["user"])+float(w.get("amount",w.get("blocked",0))),12)
        save_user(w["user"])
        save_withdraws()
        try:
            bot.answer_callback_query(call.id, "❌ Rejected")
            bot.send_message(int(w["user"]), f"❌ Withdrawal #{wid} rejected")
        except: pass
    elif data.startswith("ban_"):
        uid = data.split("_")[1]
        if uid in users:
            users[uid]["banned"] = True
            save_user(uid)
            try:
                bot.answer_callback_query(call.id, "🚫 User banned")
                bot.send_message(int(uid), "🚫 You have been banned by admin.")
            except: pass
    elif data.startswith("block_"):
        wid = int(data.split("_")[1])
        w = next((x for x in withdraws if x["id"] == wid), None)
        if not w or w["status"] != "pending":
            return
        uid = w["user"]
        amt = float(w.get("amount",w.get("blocked",0)) or 0)
        w["status"] = "blocked"
        w["blocked"] = amt
        code = str(random.randint(1000, 9999))
        w["block_code"] = code
        # The withdrawal was pending; Admin explicitly moves it into the
        # Blocked Amount bucket here.
        users[uid]["blocked"] = round(blocked_amount(uid)+amt,12)
        save_user(uid)
        save_withdraws()
        try:
            bot.answer_callback_query(call.id, "💰 Money Blocked")
            bot.send_message(int(uid), f"🚫 Your withdrawal of ${amt:.2f} is BLOCKED.\n🔢 Block Code: {code}\nContact admin to unlock.")
        except: pass

@bot.message_handler(func=lambda m: m.text == "💰 UNBLOCK MONEY")
def unblock_money_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "🔢 Send 4-digit Block Code to UNBLOCK funds:")
        bot.register_next_step_handler(msg, unblock_money_process)
    except: pass

def unblock_money_process(m):
    if not is_admin(m.from_user.id):
        return
    code = (m.text or "").strip()
    w = next((x for x in withdraws if x.get("block_code") == code), None)
    if not w:
        try:
            bot.send_message(m.chat.id, "❌ Invalid Block Code")
        except: pass
        return

    uid = w["user"]
    amt = float(w.get("blocked",w.get("amount",0)) or 0)
    users[uid]["balance"] = round(balance_amount(uid)+amt,12)
    users[uid]["blocked"] = round(max(0.0,blocked_amount(uid)-amt),12)
    w["status"] = "unblocked"
    w.pop("block_code", None)
    w["blocked"] = 0.0
    save_user(uid)
    save_withdraws()
    try:
        bot.send_message(int(uid), f"✅ Your blocked ${amt:.2f} is now available in balance!")
        bot.send_message(m.chat.id, f"✅ Money unblocked for user {uid}")
    except: pass

@bot.message_handler(func=lambda m: m.text == "🔥 UN BAN-USER")
def unban_user_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send Telegram ID of user to UNBAN:")
        bot.register_next_step_handler(msg, unban_user_process)
    except: pass

def unban_user_process(m):
    if not is_admin(m.from_user.id):
        return
    uid = (m.text or "").strip()
    if uid not in users:
        try:
            bot.send_message(m.chat.id, "❌ User not found")
        except: pass
        return
    users[uid]["banned"] = False
    save_user(uid)
    try:
        bot.send_message(m.chat.id, f"✅ User {uid} unbanned")
        bot.send_message(int(uid), "✅ You have been unbanned by admin.")
    except: pass

@bot.message_handler(func=lambda m: m.text == "👑 ADMIN LIST")
def admin_list_handler(m):
    if not is_admin(m.from_user.id): return
    ids=get_admin_ids()
    lines=["👑 <b>ADMIN LIST</b>",""]
    for i,x in enumerate(ids,1):
        role="GENERAL ADMIN" if x==PRIMARY_ADMIN_ID else "ADMIN"
        lines.append(f"{i}. <code>{x}</code> — <b>{role}</b>")
    bot.send_message(m.chat.id,"\n".join(lines))

@bot.message_handler(func=lambda m: m.text == "💼 PORTFOLIO STATS")
def portfolio_stats_handler(m):
    if not is_admin(m.from_user.id): return
    refresh_market_rates(False)
    users_with_assets=0; total=0.0; crypto_total=0.0
    for uid,u in users.items():
        v=total_assets_usd(uid); total+=v
        if v>0: users_with_assets+=1
        for code,amt in (u.get("portfolio") or {}).items():
            if is_crypto(code): crypto_total += asset_to_usd(code,float(amt or 0))
        if is_crypto(cur_code(uid)): crypto_total += balance_usd_value(uid)
    fee,gas,count=get_crypto_fee_stats_today()
    bot.send_message(m.chat.id, f"💼 <b>PORTFOLIO STATISTICS</b>\n\n👥 Users with assets: <b>{users_with_assets}</b>\n💰 Total tracked value: <b>${total:,.2f}</b>\n🪙 Crypto value: <b>${crypto_total:,.2f}</b>\n\n📈 <b>TODAY</b>\n💸 Fees: <b>${fee:,.2f}</b>\n⛽ Gas: <b>${gas:,.2f}</b>\n🔄 Conversions: <b>{count}</b>")

@bot.message_handler(func=lambda m: m.text in ["🟢 OPEN HOLD","🔴 CLOSE HOLD","🟢 OPEN CRYPTO","🔴 CLOSE CRYPTO","💸 CRYPTO FEE","⛽ GAS FEE","💰 CRYPTO MIN DEPOSIT","📈 CRYPTO FEE STATS"])
def crypto_admin_controls(m):
    if not is_admin(m.from_user.id): return
    action=m.text
    if action=="🟢 OPEN HOLD": set_setting("crypto_hold_enabled",True); bot.send_message(m.chat.id,"🟢 <b>Crypto 1H Hold is OPEN.</b> New crypto conversions will be held for 1 hour."); return
    if action=="🔴 CLOSE HOLD": set_setting("crypto_hold_enabled",False); bot.send_message(m.chat.id,"🔴 <b>Crypto 1H Hold is CLOSED.</b> Existing holds keep their current status."); return
    if action=="🟢 OPEN CRYPTO": set_setting("crypto_enabled",True); bot.send_message(m.chat.id,"🟢 <b>Crypto is OPEN.</b> Users can use crypto currencies."); return
    if action=="🔴 CLOSE CRYPTO":
        # Disable new crypto operations first, then liquidate every crypto holding.
        set_setting("crypto_enabled",False)
        converted=0; fees=0.0; gross_total_all=0.0; net_total_all=0.0
        refresh_market_rates(True)
        for uid,u in list(users.items()):
            with CRYPTO_TX_LOCK:
                cur=cur_code(uid)
                current_amt=float(u.get("balance",0) or 0)
                current_blocked=float(u.get("blocked",0) or 0)
                gross_total=0.0; asset_rows=[]
                if is_crypto(cur) and current_amt>0:
                    gross=asset_to_usd(cur,current_amt)
                    if gross>0:
                        fee,gas,_=crypto_fee_usd(gross,cur); asset_rows.append((cur,current_amt,gross,fee,gas)); gross_total+=gross
                p=u.get("portfolio") if isinstance(u.get("portfolio"),dict) else {}
                for code,amt in list(p.items()):
                    amt=float(amt or 0)
                    if is_crypto(code) and amt>0:
                        gross=asset_to_usd(code,amt)
                        if gross>0:
                            fee,gas,_=crypto_fee_usd(gross,code); asset_rows.append((code,amt,gross,fee,gas)); gross_total+=gross
                if not asset_rows:
                    if is_crypto(cur):
                        u["balance"]=0.0; u["blocked"]=0.0; u["balance_asset"]="USD"; u["currency"]="USD"; u["portfolio"]={}
                        save_user(uid)
                    continue
                total_cost=sum(r[3]+r[4] for r in asset_rows); net_total=max(0.0,gross_total-total_cost)
                gross_total_all+=gross_total; net_total_all+=net_total; fees+=total_cost

                # Blocked amount is preserved as blocked USD when the source was
                # the current crypto balance. Active crypto conversion holds are
                # released because the admin explicitly closed the crypto market.
                blocked_usd=0.0
                if is_crypto(cur) and current_blocked>0:
                    blocked_usd=min(asset_to_usd(cur,current_blocked),gross_total)
                    if gross_total>0: blocked_usd=max(0.0,blocked_usd-total_cost*(blocked_usd/gross_total))
                blocked_usd=min(blocked_usd,net_total)

                # Preserve existing non-crypto cash. Crypto proceeds are always
                # added to USD cash; if the current balance itself is crypto, that
                # balance is replaced by the USD proceeds.
                if is_crypto(cur):
                    u["balance_asset"]="USD"; u["currency"]="USD"
                    u["balance"]=round(net_total,12)
                    u["blocked"]=round(blocked_usd,12)
                elif cur=="USD":
                    u["balance"]=round(current_amt+net_total,12)
                    # Existing USD blocked funds remain blocked; crypto portfolio
                    # proceeds do not create a new blocked amount.
                    blocked_usd=current_blocked
                    u["blocked"]=round(current_blocked,12)
                else:
                    # Legacy single-balance accounts using another fiat currency
                    # are converted to USD so the post-close account has one clean
                    # USD balance and the crypto proceeds are included.
                    current_usd=asset_to_usd(cur,current_amt)
                    current_blocked_usd=asset_to_usd(cur,current_blocked)
                    u["balance_asset"]="USD"; u["currency"]="USD"
                    u["balance"]=round(current_usd+net_total,12)
                    u["blocked"]=round(current_blocked_usd,12)
                    blocked_usd=current_blocked_usd
                u["portfolio"]={}
                now=datetime.now(timezone.utc)
                for code,amt,gross,fee,gas in asset_rows:
                    net=max(0.0,gross-fee-gas)
                    crypto_fee_ledger_col.insert_one({"user_id":uid,"type":"crypto_close_fee","from_asset":code,"to_asset":"USD","gross_usd":gross,"fee_usd":fee,"gas_fee_usd":gas,"net_usd":net,"time":now,"reason":"admin_close_crypto"})
                    balance_ledger_col.insert_one({"user_id":uid,"type":"crypto_close","from_asset":code,"to_asset":"USD","gross_usd":gross,"fee_usd":fee,"gas_fee_usd":gas,"net_usd":net,"time":now})
                conversion_holds_col.update_many({"user_id":uid,"status":"hold"},{"$set":{"status":"closed_crypto_returned","released_at":now,"released_by":"admin_close_crypto"}})
                save_user(uid); converted+=1
                available_usd=max(0.0,float(u.get("balance",0) or 0)-float(u.get("blocked",0) or 0)) if cur_code(uid)=="USD" else 0.0
                try:
                    bot.send_message(int(uid), "🔴 <b>CRYPTO SERVICE CLOSED</b>\n\nAll your crypto holdings have been converted to <b>USD</b> at the current live market price.\nYour crypto portfolio has been cleared.\n\n" f"💰 <b>Available Balance:</b> ${available_usd:,.2f} USD\n" f"🔒 <b>Blocked Amount:</b> ${float(u.get('blocked',0) or 0):,.2f} USD\n\n" f"💸 Fees + gas: ${total_cost:,.2f} USD\nYou can use the USD balance normally.")
                except Exception as e: print("Close crypto notify error:",uid,e)
        bot.send_message(m.chat.id, f"🔴 <b>CRYPTO CLOSED</b>\n\n👥 Users converted: <b>{converted}</b>\n💵 Gross crypto value: <b>${gross_total_all:,.2f}</b>\n💸 Fees + gas: <b>${fees:,.2f}</b>\n💰 Returned to USD: <b>${net_total_all:,.2f}</b>\n\n🗑 All crypto portfolio entries were removed.")
        return
    if action=="💰 CRYPTO MIN DEPOSIT":
        cur=crypto_min_deposit_usd(); msg=bot.send_message(m.chat.id,f"💰 <b>CRYPTO MINIMUM DEPOSIT</b>\n\nCurrent minimum: <b>${cur:,.2f}</b>\n\nSend the new minimum in USD. Example: <code>10</code>. Send <code>0</code> to allow everyone.")
        bot.register_next_step_handler(msg,crypto_min_deposit_process); return
    if action=="💸 CRYPTO FEE":
        cur=crypto_fee_percent(); msg=bot.send_message(m.chat.id,f"💸 <b>CRYPTO CONVERSION FEE</b>\nCurrent: <b>{cur:.4f}%</b>\n\nSend new percentage. Example: <code>1</code> or <code>0</code>.")
        bot.register_next_step_handler(msg,crypto_fee_process); return
    if action=="⛽ GAS FEE":
        cur=crypto_gas_fee_usd(); mode=str(get_setting("crypto_gas_mode","AUTO") or "AUTO")
        msg=bot.send_message(m.chat.id,f"⛽ <b>GAS FEE CONTROL</b>\nMode: <b>{html.escape(mode)}</b>\nCurrent reserve/fallback: <b>${cur:.4f} USD</b>\n\nSend <code>AUTO</code> to use live network estimates when supported (ETH/BNB/BTC), or send a USD fallback such as <code>0.10</code>.")
        bot.register_next_step_handler(msg,crypto_gas_process); return
    fee,gas,count=get_crypto_fee_stats_today()
    bot.send_message(m.chat.id,f"📈 <b>CRYPTO FEES TODAY</b>\n\n💸 Conversion fees: <b>${fee:,.2f}</b>\n⛽ Gas/network reserve: <b>${gas:,.2f}</b>\n💰 Total collected: <b>${fee+gas:,.2f}</b>\n🔄 Transactions: <b>{count}</b>")

def crypto_min_deposit_process(m):
    if not is_admin(m.from_user.id): return
    try:
        value=float((m.text or '').replace(',','').strip())
        if value<0: raise ValueError
        set_setting("crypto_min_deposit_usd",value)
        bot.send_message(m.chat.id,f"✅ Crypto minimum deposit is now <b>${value:,.2f}</b> USD." if value>0 else "✅ Crypto minimum deposit is now <b>OFF</b>. All users may access Crypto.")
    except Exception:
        bot.send_message(m.chat.id,"❌ Invalid amount. Send a number such as <code>10</code> or <code>0</code>.")

def crypto_fee_process(m):
    if not is_admin(m.from_user.id): return
    try:
        v=float((m.text or '').replace('%','').strip());
        if v<0 or v>100: raise ValueError
        set_setting("crypto_fee_percent",v); bot.send_message(m.chat.id,f"✅ Crypto conversion fee set to <b>{v:.4f}%</b>")
    except: bot.send_message(m.chat.id,"❌ Invalid fee. Send 0–100.")

def crypto_gas_process(m):
    if not is_admin(m.from_user.id): return
    raw=(m.text or '').strip()
    if raw.upper()=="AUTO":
        set_setting("crypto_gas_mode","AUTO"); bot.send_message(m.chat.id,"✅ Gas mode set to <b>AUTO</b>. Live network estimates will be used where supported; admin fallback remains available."); return
    try:
        v=float(raw.replace('$','').strip())
        if v<0 or v>10000: raise ValueError
        set_setting("crypto_gas_mode","ADMIN"); set_setting("crypto_gas_fee_usd",v); bot.send_message(m.chat.id,f"✅ Gas mode set to <b>ADMIN</b> with <b>${v:.4f}</b> USD reserve")
    except: bot.send_message(m.chat.id,"❌ Invalid. Send AUTO or a USD amount such as 0.10.")

@bot.message_handler(func=lambda m: m.text == "⏳ HOLD CHECK")
def hold_check_admin(m):
    if not is_admin(m.from_user.id): return
    hs=list(conversion_holds_col.find({"status":"hold"}).sort("created_at",-1).limit(50))
    if not hs: bot.send_message(m.chat.id,"⏳ No active holds."); return
    lines=["⏳ <b>ACTIVE HOLDS</b>",""]
    for h in hs:
        uid=str(h.get("user_id")); u=users.get(uid,{}); name=("@"+u.get("username")) if u.get("username") else uid; exp=parse_seen_time(h.get("expires_at")); left=max(0,int((exp-datetime.now(timezone.utc)).total_seconds())) if exp else 0
        source_docs=h.get("source_snapshot") or []
        src=[]
        for d in source_docs[:5]: src.append(str(d.get("source") or d.get("type") or "unknown"))
        source_text=", ".join(dict.fromkeys(src)) if src else "legacy/unknown"
        lines.append(f"👤 {name} ({uid})\n💵 ${float(h.get('usd_amount',0)):,.2f} USD\n🔄 {h.get('from_asset')} → USD\n⏱️ {left//60}m {left%60}s\n🆔 {h.get('_id')}\n📍 Source: {source_text}")
    bot.send_message(m.chat.id,"\n\n".join(lines))

@bot.message_handler(func=lambda m: m.text == "✅ RELEASE HOLD")
def release_hold_start(m):
    if not is_admin(m.from_user.id): return
    msg=bot.send_message(m.chat.id,"Send Hold ID or Telegram User ID to release active hold(s):"); bot.register_next_step_handler(msg,release_hold_process)

def release_hold_process(m):
    if not is_admin(m.from_user.id): return
    key=(m.text or "").strip(); q={"status":"hold"}
    if key.isdigit(): q["user_id"]=key
    else:
        try: from bson.objectid import ObjectId; q["_id"]=ObjectId(key)
        except: bot.send_message(m.chat.id,"❌ Invalid ID"); return
    hs=list(conversion_holds_col.find(q))
    if not hs: bot.send_message(m.chat.id,"❌ Hold not found"); return
    now=datetime.now(timezone.utc)
    for h in hs: conversion_holds_col.update_one({"_id":h["_id"],"status":"hold"},{"$set":{"status":"released_early","released_at":now,"released_by":str(m.from_user.id)}})
    uid=str(hs[0].get("user_id")); bot.send_message(m.chat.id,f"✅ Released {len(hs)} hold(s) for {uid}.")
    try: bot.send_message(int(uid),"✅ Your held amount has been released early by admin and is now available.")
    except: pass

@bot.message_handler(func=lambda m: m.text == "📜 HOLD HISTORY")
def hold_history_admin(m):
    if not is_admin(m.from_user.id): return
    hs=list(conversion_holds_col.find({}).sort("created_at",-1).limit(50))
    if not hs: bot.send_message(m.chat.id,"📜 No hold history yet."); return
    lines=["📜 <b>HOLD HISTORY</b>",""]
    for h in hs:
        uid=str(h.get("user_id")); u=users.get(uid,{}); name=("@"+u.get("username")) if u.get("username") else uid
        lines.append(f"👤 {name} | {h.get('from_asset')} → USD | ${float(h.get('usd_amount',0)):,.2f} | {h.get('status')} | {h.get('created_at')}")
    bot.send_message(m.chat.id,"\n".join(lines))

@bot.message_handler(func=lambda m: m.text == "💳 WITHDRAWAL CHECK")
def withdrawal_check_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Enter Withdrawal Request ID:")
        bot.register_next_step_handler(msg, withdrawal_check_process)
    except: pass

def withdrawal_check_process(m):
    if not is_admin(m.from_user.id):
        return
    try:
        wid = int(m.text.strip())
    except:
        try:
            bot.send_message(m.chat.id, "❌ Invalid Request ID")
        except: pass
        return

    w = next((x for x in withdraws if x["id"] == wid), None)
    if not w:
        try:
            bot.send_message(m.chat.id, "❌ Request not found")
        except: pass
        return
    uid = w["user"]
    bot_id = users.get(uid, {}).get("bot_id", "Unknown")
    invited = users.get(uid, {}).get("invited", 0)
    msg_text = f"💳 WITHDRAWAL DETAILS\n\n🧾 Request ID: {w['id']}\n👤 User ID: {uid}\n🤖 BOT ID: {bot_id}\n👥 Referrals: {invited}\n💰 Amount: {format_asset(w.get('asset','USD'),w['amount'])}\n💵 USD Value: ${float(w.get('amount_usd',w.get('amount',0))):.2f}\n🏦 Address: {w['address']}\n📊 Status: {w['status'].upper()}\n⏰ Time: {w['time']}"
    try:
        bot.send_message(m.chat.id, msg_text)
    except: pass

@bot.message_handler(func=lambda m: m.text == "📊 STATS")
def stats_handler(m):
    if not is_admin(m.from_user.id):
        return
    total_users = len(users)
    total_balance = sum(asset_to_usd((u.get("balance_asset") or u.get("currency") or "USD"),u.get("balance",0)) for u in users.values())
    total_blocked = sum(asset_to_usd((u.get("balance_asset") or u.get("currency") or "USD"),u.get("blocked",0)) for u in users.values())
    total_withdraws = len(withdraws)
    pending_withdraws = len([w for w in withdraws if w["status"] == "pending"])
    msg = f"📊 BOT STATS\n\n👥 Total Users: {total_users}\n💰 Total Balance: ${total_balance:.2f}\n⏳ Total Blocked: ${total_blocked:.2f}\n🧾 Total Withdrawals: {total_withdraws}\n⏳ Pending Withdrawals: {pending_withdraws}"
    try:
        bot.send_message(m.chat.id, msg)
    except: pass

@bot.message_handler(func=lambda m: m.text == "⏱️ FREE MAX MIN")
def free_max_minutes_start(m):
    if not is_admin(m.from_user.id): return
    current = int(get_setting("free_max_minutes", FREE_MAX_MINUTES_DEFAULT))
    msg = bot.send_message(m.chat.id, f"⏱️ Current FREE limit: {current} minutes\n\nSend new maximum minutes for FREE users (example: 10):")
    bot.register_next_step_handler(msg, free_max_minutes_process)


def free_max_minutes_process(m):
    if not is_admin(m.from_user.id): return
    try:
        minutes = int((m.text or "").strip())
        if minutes < 1 or minutes > 1440: raise ValueError
        set_setting("free_max_minutes", minutes)
        bot.send_message(m.chat.id, f"✅ FREE maximum download duration set to {minutes} minutes.")
    except Exception:
        bot.send_message(m.chat.id, "❌ Enter a whole number from 1 to 1440 minutes.")


@bot.message_handler(func=lambda m: m.text == "⏱️ PREMIUM MAX MIN")
def premium_max_minutes_start(m):
    if not is_admin(m.from_user.id): return
    current = int(get_setting("premium_max_minutes", PREMIUM_MAX_MINUTES_DEFAULT))
    msg = bot.send_message(m.chat.id, f"⏱️ Current PREMIUM limit: {current} minutes\n\nSend new maximum minutes for PREMIUM users (example: 120):")
    bot.register_next_step_handler(msg, premium_max_minutes_process)


def premium_max_minutes_process(m):
    if not is_admin(m.from_user.id): return
    try:
        minutes = int((m.text or "").strip())
        if minutes < 1 or minutes > 1440: raise ValueError
        set_setting("premium_max_minutes", minutes)
        bot.send_message(m.chat.id, f"✅ PREMIUM maximum download duration set to {minutes} minutes.")
    except Exception:
        bot.send_message(m.chat.id, "❌ Enter a whole number from 1 to 1440 minutes.")


@bot.message_handler(func=lambda m: m.text == "📦 FREE MAX MB")
def admin_free_max_mb(m):
    if not is_admin(m.from_user.id): return
    cur=int(get_setting("free_max_mb",49)); msg=bot.send_message(m.chat.id,f"📦 <b>FREE MAX MB</b>\n\nCurrent: <b>{cur} MB</b>\nSend new maximum file size for FREE users (1-2048 MB):")
    bot.register_next_step_handler(msg,admin_free_max_mb_step)

def admin_free_max_mb_step(m):
    if not is_admin(m.from_user.id): return
    try:
        v=int((m.text or '').strip());
        if v<1 or v>2048: raise ValueError
        set_setting("free_max_mb",v); bot.send_message(m.chat.id,f"✅ FREE max file size: <b>{v} MB</b>")
    except Exception: bot.send_message(m.chat.id,"❌ Enter 1-2048 MB.")

@bot.message_handler(func=lambda m: m.text == "📦 TRIAL MAX MB")
def admin_trial_max_mb(m):
    if not is_admin(m.from_user.id): return
    cur=int(get_setting("trial_max_mb",49)); msg=bot.send_message(m.chat.id,f"📦 <b>TRIAL MAX MB</b>\n\nCurrent: <b>{cur} MB</b>\nSend new maximum file size for Trial users (1-2048 MB):")
    bot.register_next_step_handler(msg,admin_trial_max_mb_step)

def admin_trial_max_mb_step(m):
    if not is_admin(m.from_user.id): return
    try:
        v=int((m.text or '').strip());
        if v<1 or v>2048: raise ValueError
        set_setting("trial_max_mb",v); bot.send_message(m.chat.id,f"✅ TRIAL max file size: <b>{v} MB</b>")
    except Exception: bot.send_message(m.chat.id,"❌ Enter 1-2048 MB.")

@bot.message_handler(func=lambda m: m.text == "📦 PREMIUM MAX MB")
def admin_premium_max_mb(m):
    if not is_admin(m.from_user.id): return
    cur=int(get_setting("premium_max_mb",49)); msg=bot.send_message(m.chat.id,f"📦 <b>PREMIUM MAX MB</b>\n\nCurrent: <b>{cur} MB</b>\nSend new maximum file size for Premium users (1-2048 MB):")
    bot.register_next_step_handler(msg,admin_premium_max_mb_step)

def admin_premium_max_mb_step(m):
    if not is_admin(m.from_user.id): return
    try:
        v=int((m.text or '').strip());
        if v<1 or v>2048: raise ValueError
        set_setting("premium_max_mb",v); bot.send_message(m.chat.id,f"✅ PREMIUM max file size: <b>{v} MB</b>")
    except Exception: bot.send_message(m.chat.id,"❌ Enter 1-2048 MB.")

@bot.message_handler(func=lambda m: m.text == "⚙️ DOWNLOAD LIMITS")
def admin_download_limits(m):
    if not is_admin(m.from_user.id): return
    fm=int(get_setting("free_max_minutes",FREE_MAX_MINUTES_DEFAULT)); pm=int(get_setting("premium_max_minutes",PREMIUM_MAX_MINUTES_DEFAULT))
    fmb=int(get_setting("free_max_mb",49)); tmb=int(get_setting("trial_max_mb",49)); pmb=int(get_setting("premium_max_mb",49))
    fyt=int(get_setting("free_youtube_max_mb",FREE_YOUTUBE_MAX_MB_DEFAULT) or FREE_YOUTUBE_MAX_MB_DEFAULT)
    pyt=int(get_setting("premium_youtube_max_mb",PREMIUM_YOUTUBE_MAX_MB_DEFAULT) or 0); tyt=int(get_setting("trial_youtube_max_mb",TRIAL_YOUTUBE_MAX_MB_DEFAULT) or 0)
    pu='Unlimited' if pyt==0 else f'{pyt} MB'; tu='Unlimited' if tyt==0 else f'{tyt} MB'
    bot.send_message(m.chat.id,f"⚙️ <b>DOWNLOAD LIMITS</b>\n\n🆓 FREE: {fm} min / {fmb} MB\n📺 FREE YouTube: {fyt} MB\n🎁 TRIAL: {tmb} MB / YouTube {tu}\n💎 PREMIUM: {pm} min / {pmb} MB / YouTube {pu}\n▶️ Full YouTube for Free: <b>{'OPEN' if youtube_full_free_enabled() else 'CLOSED'}</b>")

@bot.message_handler(func=lambda m: m.text == "▶️ YOUTUBE FREE ACCESS")
def admin_youtube_free_access(m):
    if not is_admin(m.from_user.id): return
    enabled=youtube_full_free_enabled()
    msg=bot.send_message(m.chat.id,
        f"▶️ <b>YOUTUBE FREE ACCESS</b>\n\nCurrent: <b>{'OPEN' if enabled else 'CLOSED'}</b>\n\n"
        "Send <code>ON</code> to allow Free users to download full YouTube videos.\n"
        "Send <code>OFF</code> to keep full YouTube Premium-only.\n"
        "YouTube Shorts remain Free either way.\n\n"
        "Reply with <code>ON</code> or <code>OFF</code>.")
    bot.register_next_step_handler(msg, admin_youtube_free_access_step)

def admin_youtube_free_access_step(m):
    if not is_admin(m.from_user.id): return
    v=(m.text or '').strip().lower()
    if v not in {'on','off'}:
        bot.send_message(m.chat.id,"❌ Send only ON or OFF."); return
    set_setting("youtube_full_free", v=='on')
    bot.send_message(m.chat.id, f"✅ Full YouTube for Free users: <b>{'OPEN' if v=='on' else 'CLOSED'}</b>\nYouTube Shorts remain Free.")

@bot.message_handler(func=lambda m: m.text == "📺 FREE YOUTUBE MB")
def admin_free_youtube_mb(m):
    if not is_admin(m.from_user.id): return
    cur=int(get_setting("free_youtube_max_mb",FREE_YOUTUBE_MAX_MB_DEFAULT) or FREE_YOUTUBE_MAX_MB_DEFAULT)
    msg=bot.send_message(m.chat.id,f"📺 <b>FREE YOUTUBE MAX MB</b>\n\nCurrent: <b>{cur} MB</b>\nSend a new limit from 1-2048 MB:")
    bot.register_next_step_handler(msg,admin_free_youtube_mb_step)

def admin_free_youtube_mb_step(m):
    if not is_admin(m.from_user.id): return
    try:
        v=int((m.text or '').strip())
        if v<1 or v>2048: raise ValueError
        set_setting("free_youtube_max_mb",v)
        bot.send_message(m.chat.id,f"✅ Free YouTube maximum: <b>{v} MB</b>")
    except Exception:
        bot.send_message(m.chat.id,"❌ Enter 1-2048 MB.")

@bot.message_handler(func=lambda m: m.text == "📺 PREMIUM YOUTUBE MB")
def admin_premium_youtube_mb(m):
    if not is_admin(m.from_user.id): return
    cur=int(get_setting("premium_youtube_max_mb",PREMIUM_YOUTUBE_MAX_MB_DEFAULT) or 0)
    current='Unlimited' if cur==0 else f'{cur} MB'
    msg=bot.send_message(m.chat.id,f"📺 <b>PREMIUM/TRIAL YOUTUBE LIMIT</b>\n\nCurrent: <b>{current}</b>\nSend <code>Unlimited</code> or a limit from 1-2048 MB:")
    bot.register_next_step_handler(msg,admin_premium_youtube_mb_step)

def admin_premium_youtube_mb_step(m):
    if not is_admin(m.from_user.id): return
    raw=(m.text or '').strip().lower()
    if raw in {'unlimited','unlimit','0'}:
        set_setting("premium_youtube_max_mb",0); set_setting("trial_youtube_max_mb",0)
        bot.send_message(m.chat.id,"✅ Premium/Trial YouTube file-size limit: <b>Unlimited</b>."); return
    try:
        v=int(raw)
        if v<1 or v>2048: raise ValueError
        set_setting("premium_youtube_max_mb",v); set_setting("trial_youtube_max_mb",v)
        bot.send_message(m.chat.id,f"✅ Premium/Trial YouTube maximum: <b>{v} MB</b>")
    except Exception:
        bot.send_message(m.chat.id,"❌ Enter Unlimited or 1-2048 MB.")

@bot.message_handler(func=lambda m: m.text == "📋 YOUTUBE LIMITS")
def admin_youtube_limits(m):
    if not is_admin(m.from_user.id): return
    free=int(get_setting("free_youtube_max_mb",FREE_YOUTUBE_MAX_MB_DEFAULT) or FREE_YOUTUBE_MAX_MB_DEFAULT)
    prem=int(get_setting("premium_youtube_max_mb",PREMIUM_YOUTUBE_MAX_MB_DEFAULT) or 0)
    trial=int(get_setting("trial_youtube_max_mb",TRIAL_YOUTUBE_MAX_MB_DEFAULT) or 0)
    p='Unlimited' if prem==0 else f'{prem} MB'; t='Unlimited' if trial==0 else f'{trial} MB'
    bot.send_message(m.chat.id,f"📋 <b>YOUTUBE LIMITS</b>\n\n🆓 Free YouTube: <b>{free} MB</b>\n🎁 Trial YouTube: <b>{t}</b>\n💎 Premium YouTube: <b>{p}</b>\n▶️ Full YouTube for Free: <b>{'OPEN' if youtube_full_free_enabled() else 'CLOSED'}</b>\n\nShorts are Free. Full videos require Premium when access is CLOSED.")

@bot.message_handler(func=lambda m: m.text == "📸 INSTAGRAM API")
def admin_instagram_api_setup(m):
    if not is_admin(m.from_user.id): return
    url,host,key=_instagram_api_config(); mask=("••••"+key[-4:] if len(key)>4 else ("set" if key else "not set"))
    msg=bot.send_message(m.chat.id,f"📸 <b>Instagram RapidAPI Setup</b>\n\nCurrent URL: <code>{html.escape(url or 'not set')}</code>\nHost: <code>{html.escape(host or 'not set')}</code>\nKey: <code>{mask}</code>\n\nSend in ONE message:\n<code>URL | HOST | API_KEY</code>\n\nExample: <code>https://example.p.rapidapi.com/download | example.p.rapidapi.com | YOUR_KEY</code>")
    bot.register_next_step_handler(msg,admin_instagram_api_setup_step)

def admin_instagram_api_setup_step(m):
    if not is_admin(m.from_user.id): return
    try:
        parts=[x.strip() for x in (m.text or '').split('|')]
        if len(parts)!=3 or not parts[0].startswith('http') or not parts[1] or not parts[2]: raise ValueError
        set_setting('instagram_api_url',parts[0]); set_setting('instagram_api_host',parts[1]); set_setting('instagram_api_key',parts[2])
        bot.send_message(m.chat.id,"✅ Instagram RapidAPI configuration saved in MongoDB. It is no longer required to put these settings in environment variables.")
    except Exception: bot.send_message(m.chat.id,"❌ Format: URL | HOST | API_KEY")

@bot.message_handler(func=lambda m: m.text == "📸 INSTAGRAM STATUS")
def admin_instagram_status(m):
    if not is_admin(m.from_user.id): return
    url,host,key=_instagram_api_config(); status='🟢 CONFIGURED' if url and host and key else '🔴 NOT CONFIGURED'
    bot.send_message(m.chat.id,f"📸 <b>INSTAGRAM API STATUS</b>\n\n{status}\nURL: <code>{html.escape(url or '—')}</code>\nHost: <code>{html.escape(host or '—')}</code>\nKey: {'set' if key else 'missing'}")

@bot.message_handler(func=lambda m: m.text == "🛰️ COBALT STATUS")
def cobalt_status_admin(m):
    if not is_admin(m.from_user.id): return
    ok, info = _cobalt_health()
    free_m = int(get_setting("free_max_minutes", FREE_MAX_MINUTES_DEFAULT))
    prem_m = int(get_setting("premium_max_minutes", PREMIUM_MAX_MINUTES_DEFAULT))
    status = "🟢 ONLINE" if ok else "🔴 OFFLINE / NOT CONFIGURED"
    bot.send_message(m.chat.id, f"🛰️ <b>COBALT STATUS</b>\n\n{status}\n{html.escape(str(info))}\n\n⏱️ FREE: {free_m} min\n💎 PREMIUM: {prem_m} min\n\nCOBALT_API_URL: {'configured' if COBALT_API_URL else 'not configured'}")


@bot.message_handler(func=lambda m: m.text == "📉 CHANGE MINIMUM")
def change_min_start(m):
    if not is_admin(m.from_user.id): return
    try:
        msg = bot.send_message(m.chat.id, "Send new minimum withdrawal amount (e.g., 0.001 or 1):")
        bot.register_next_step_handler(msg, change_min_process)
    except: pass

def change_min_process(m):
    if not is_admin(m.from_user.id): return
    try:
        new_min = float(m.text.strip())
        set_setting("min_withdrawal", new_min)
        bot.send_message(m.chat.id, f"✅ Minimum withdrawal updated to: ${new_min}")
    except:
        bot.send_message(m.chat.id, "❌ Invalid number.")

@bot.message_handler(func=lambda m: m.text == "➕ ADD FEE")
def add_fee_start(m):
    if not is_admin(m.from_user.id): return
    try:
        msg = bot.send_message(m.chat.id, "Send fee percentage (e.g., 1.5 for 1.5% or 0 for 0%):")
        bot.register_next_step_handler(msg, add_fee_process)
    except: pass

def add_fee_process(m):
    if not is_admin(m.from_user.id): return
    try:
        fee_pct = float(m.text.strip())
        set_setting("fee_percent", fee_pct)
        bot.send_message(m.chat.id, f"✅ Withdrawal fee percentage set to: {fee_pct}%")
    except:
        bot.send_message(m.chat.id, "❌ Invalid number.")

@bot.message_handler(func=lambda m: m.text == "➕ ADD LOW FEE")
def add_low_fee_start(m):
    if not is_admin(m.from_user.id): return
    try:
        msg = bot.send_message(m.chat.id, "Send low withdrawal fee amount (e.g., 0.05):")
        bot.register_next_step_handler(msg, add_low_fee_process)
    except: pass

def add_low_fee_process(m):
    if not is_admin(m.from_user.id): return
    try:
        low_fee = float(m.text.strip())
        set_setting("low_fee", low_fee)
        bot.send_message(m.chat.id, f"✅ Low W/D fee set to: ${low_fee}")
    except:
        bot.send_message(m.chat.id, "❌ Invalid number.")

@bot.message_handler(func=lambda m: m.text == "🎁 GIFT ALL")
def gift_all_start(m):
    if not is_admin(m.from_user.id): return
    try:
        msg = bot.send_message(m.chat.id, "Send amount to gift to ALL users (e.g. 1 or 0.5):")
        bot.register_next_step_handler(msg, gift_all_process)
    except: pass

def gift_all_process(m):
    if not is_admin(m.from_user.id): return
    try:
        amount = float(m.text.strip())
        if amount <= 0:
            bot.send_message(m.chat.id, "❌ Amount must be greater than 0")
            return
        
        for uid in users: ledger_credit(uid,amount,"admin_gift_all",{"admin_id":str(m.from_user.id)})
        bot.send_message(m.chat.id, f"🎁 Successfully added ${amount} USD worth of balance to all users!")
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Error: {e}")

@bot.message_handler(func=lambda m: m.text == "🗑️ REMOVE ALL")
def remove_all_start(m):
    if not is_admin(m.from_user.id): return
    try:
        msg = bot.send_message(m.chat.id, "Send amount and reason separated by pipe (|)\nExample:\n0.5 | Reason")
        bot.register_next_step_handler(msg, remove_all_process)
    except: pass

def remove_all_process(m):
    if not is_admin(m.from_user.id): return
    try:
        parts = m.text.split("|")
        if len(parts) < 2:
            bot.send_message(m.chat.id, "❌ Invalid format. Use: Amount | Reason")
            return
        remove_amt = float(parts[0].strip())
        reason = parts[1].strip()
        
        if remove_amt <= 0:
            bot.send_message(m.chat.id, "❌ Amount must be greater than 0")
            return
        for uid in users:
            asset_amt=usd_to_asset(cur_code(uid),remove_amt)
            asset_amt=min(asset_amt,available_asset_amount(uid))
            if asset_amt>0: ledger_debit(uid,asset_amt,"admin_remove_all",{"admin_id":str(m.from_user.id),"reason":reason})
            
        count = 0
        for uid in users:
            try:
                bot.send_message(int(uid), f"⚠️ Your Account Has Been Charged: ${remove_amt:.2f}\nReason: {reason}")
                count += 1
            except: pass
        bot.send_message(m.chat.id, f"✅ Successfully removed ${remove_amt} from all users and notified {count} users. Reason: {reason}")
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Error: {e}")

@bot.message_handler(func=lambda m: m.text == "🚫 BAN USER MANUAL")
def manual_ban_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send Telegram ID or BOT ID to BAN user:")
        bot.register_next_step_handler(msg, manual_ban_process)
    except: pass

def manual_ban_process(m):
    if not is_admin(m.from_user.id):
        return
    uid_input = (m.text or "").strip()
    uid = uid_input if uid_input in users else find_user_by_botid(uid_input)
    if not uid:
        try:
            bot.send_message(m.chat.id, "❌ User not found")
        except: pass
        return
    users[uid]["banned"] = True
    save_user(uid)
    try:
        bot.send_message(m.chat.id, f"🚫 User {uid} banned")
        bot.send_message(int(uid), "🚫 You have been banned by admin.")
    except: pass

@bot.message_handler(func=lambda m: m.text == "🔍 RAADI")
def raadi_stats(m):
    if not is_admin(m.from_user.id):
        return
    total_videos = videos_data.get("total", 0)
    platform_stats = videos_data.get("platforms", {})
    users_stats = videos_data.get("users", {})
    
    top_downloader = "None"
    sorted_users = []
    if users_stats:
        sorted_users = sorted(users_stats.items(), key=lambda x: x[1], reverse=True)
        top_uid, top_cnt = sorted_users[0]
        top_downloader = f'<a href="tg://user?id={top_uid}">{top_uid}</a> ({top_cnt} videos)'

    tt = platform_stats.get("tiktok", 0)
    yt = platform_stats.get("youtube", 0)
    fb = platform_stats.get("facebook", 0)
    pin = platform_stats.get("pinterest", 0)
    ig = platform_stats.get("instagram", 0)
    snap = platform_stats.get("snapchat", 0)
    tw = platform_stats.get("twitter", 0)

    msg_lines = [
        "🔍 DOWNLOAD ANALYTICS\n",
        f"🎬 Total Videos Downloaded: {total_videos}",
        f"🏆 Top Downloader: {top_downloader}\n",
        "📊 Downloads by Platform:",
        f"• TikTok: {tt}",
        f"• YouTube: {yt}",
        f"• Facebook: {fb}",
        f"• Instagram: {ig}",
        f"• Pinterest: {pin}",
        f"• Snapchat: {snap}",
        f"• X/Twitter: {tw}\n",
        "🥇 Top 40 Users:"
    ]
    for i, (uid, count) in enumerate(sorted_users[:40], start=1):
        bot_id = users.get(str(uid), {}).get("bot_id", "N/A")
        msg_lines.append(f'{i}. 👤 <a href="tg://user?id={uid}">{uid}</a> - 🎬 {count} videos | 🤖 BOT ID: {bot_id}')

    try:
        bot.send_message(m.chat.id, "\n".join(msg_lines), parse_mode="HTML")
    except Exception as e:
        print(f"RAADI error: {e}")

@bot.message_handler(func=lambda m: m.text == "📢 BROADCAST")
def broadcast_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "📝 Send the broadcast message to all users:")
        bot.register_next_step_handler(msg, broadcast_send)
    except: pass

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
    try:
        bot.send_message(m.chat.id, f"✅ Broadcast sent to {count} users")
    except: pass

@bot.message_handler(func=lambda m: m.text == "📢 BROADCAST MEDIA")
def broadcast_media_start(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "Send the Video or Photo with caption (or without):")
    bot.register_next_step_handler(msg, broadcast_media_process)

def broadcast_media_process(m):
    if not is_admin(m.from_user.id):
        return
    
    if not (m.video or m.photo):
        bot.send_message(m.chat.id, "❌ Please send a valid Video or Photo.")
        return
        
    count = 0
    file_id = m.video.file_id if m.video else m.photo[-1].file_id
    caption = m.caption or ""
    
    for uid in users:
        try:
            if m.video:
                bot.send_video(int(uid), file_id, caption=caption)
            else:
                bot.send_photo(int(uid), file_id, caption=caption)
            count += 1
        except:
            continue
    bot.send_message(m.chat.id, f"✅ Media broadcast sent to {count} users.")

@bot.message_handler(func=lambda m: m.text == "SEND PAY")
def send_pay_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send payment details in this format:\n\nTitle | Description | Price in Stars\n\nExample:\nVIP Access | 1 Month VIP Subscription | 50")
        bot.register_next_step_handler(msg, send_pay_process)
    except: pass

def send_pay_process(m):
    if not is_admin(m.from_user.id):
        return
    try:
        parts = m.text.split("|")
        if len(parts) != 3:
            bot.send_message(m.chat.id, "❌ Invalid format. Use: Title | Description | Price")
            return
            
        title = parts[0].strip()
        desc = parts[1].strip()
        price = int(parts[2].strip())
        prices = [LabeledPrice(label=title, amount=price)]
        
        count = 0
        for uid in users:
            try:
                bot.send_invoice(
                    int(uid),
                    title=title,
                    description=desc,
                    invoice_payload=f"stars_pay_{price}",
                    provider_token="",
                    currency="XTR",
                    prices=prices
                )
                count += 1
            except Exception as e:
                continue
        bot.send_message(m.chat.id, f"✅ Telegram Stars payment sent to {count} users.")
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Error processing payment: {e}")

@bot.message_handler(func=lambda m: m.text == "📌 POST CHANNEL")
def post_channel_start(m):
    global CHANNEL_WINDOW_OPEN
    if not is_admin(m.from_user.id):
        return
    CHANNEL_WINDOW_OPEN = True
    POST_CHANNELS.clear()
    try:
        msg = bot.send_message(m.chat.id, "Send channel usernames\nExample:\n@channel1\n\nMax 10 channels. Send DONE when finished.")
        bot.register_next_step_handler(msg, post_channel_add)
    except: pass

def post_channel_add(m):
    if m.text.lower() == "done":
        try:
            bot.send_message(m.chat.id, f"✅ {len(POST_CHANNELS)} channels added.")
        except: pass
        return
    if len(POST_CHANNELS) >= MAX_CHANNELS:
        try:
            bot.send_message(m.chat.id, "⚠️ Maximum 10 channels allowed.")
        except: pass
        return
    username = m.text.replace("@", "").strip()
    POST_CHANNELS.append(username)
    try:
        msg = bot.send_message(m.chat.id, f"Channel @{username} added\nTotal: {len(POST_CHANNELS)}\nSend another or DONE")
        bot.register_next_step_handler(msg, post_channel_add)
    except: pass

@bot.message_handler(func=lambda m: m.text == "CLOSE CHANNEL POST")
def close_channel_post(m):
    if not is_admin(m.from_user.id):
        return
    MANAGED_CHANNELS.clear()
    try:
        bot.send_message(m.chat.id, "❌ All channels removed.")
    except: pass

@bot.message_handler(func=lambda m: m.text == "👥 SEE LIST")
def see_users(m):
    if not is_admin(m.from_user.id):
        return
    total = len(users)
    count = 0
    for uid in users:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("💬 OPEN CHAT", url=f"tg://user?id={uid}"))
        qa_status = "⚡ Quick Access: YES" if users[str(uid)].get("quick_access") else "Quick Access: NO"
        try:
            bot.send_message(m.chat.id, f"👤 User ID: {uid} | {qa_status}", reply_markup=kb)
        except: pass
        count += 1
        if count >= 20:
            break
    try:
        bot.send_message(m.chat.id, f"📊 Total Users: {total}")
    except: pass

@bot.message_handler(func=lambda m: m.text == "🔒 LOCK BOT")
def lock_bot_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "✍️ Send the lock message users should receive.")
        bot.register_next_step_handler(msg, lock_bot_process)
    except: pass

def lock_bot_process(m):
    global BOT_LOCKED, LOCK_MESSAGE
    if not is_admin(m.from_user.id):
        return
    text = (m.text or "").strip()
    if text:
        LOCK_MESSAGE = text
        BOT_LOCKED = True
        try:
            bot.send_message(m.chat.id, "🔒 Bot locked successfully.")
        except: pass

@bot.message_handler(func=lambda m: m.text == "🔓 UNLOCK BOT")
def unlock_bot(m):
    global BOT_LOCKED
    if not is_admin(m.from_user.id):
        return
    BOT_LOCKED = False
    try:
        bot.send_message(m.chat.id, "🔓 Bot unlocked successfully.")
    except: pass

@bot.message_handler(func=lambda m: m.text == "📢 ADD ADS")
def add_ads_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "✍️ Format:\nButton Name | Link | Qoraal yar", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_add_ads)
    except: pass

def process_add_ads(m):
    global ADS_ENABLED, ADS_BTN_TEXT, ADS_URL, ADS_TEXT
    if not is_admin(m.from_user.id):
        return
    parts = [p.strip() for p in (m.text or "").split("|")]
    if len(parts) < 2:
        try:
            bot.send_message(m.chat.id, "❌ Format error.")
        except: pass
        return
    ADS_BTN_TEXT = parts[0]
    ADS_URL = parts[1]
    ADS_TEXT = parts[2] if len(parts) > 2 else "✨ Nagala soco baraha bulshada!"
    ADS_ENABLED = True
    try:
        bot.send_message(m.chat.id, "✅ Ads saved and enabled!")
    except: pass

@bot.message_handler(func=lambda m: m.text == "🗑 DELETE ADS")
def delete_ads(m):
    global ADS_ENABLED, ADS_BTN_TEXT, ADS_URL, ADS_TEXT
    if not is_admin(m.from_user.id):
        return
    ADS_ENABLED = False
    ADS_BTN_TEXT = ""
    ADS_URL = ""
    ADS_TEXT = ""
    try:
        bot.send_message(m.chat.id, "🗑 Ads deleted.")
    except: pass

@bot.message_handler(func=lambda m: m.text == "📥 IMPORT USERS")
def import_users_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send Telegram IDs separated by spaces or new lines.")
        bot.register_next_step_handler(msg, import_users_process)
    except: pass

def import_users_process(m):
    if not is_admin(m.from_user.id):
        return
    ids = (m.text or "").replace("\n", " ").split()
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
                "quick_access": False,
                "youtube_30m": False,
                "premium_until": None,
                "premium_warning_sent": False,
                "trial_used": False,
                "trial_pending": False,
                "trial_version_used": None,
                "trial_pending_version": None,
                "referral_50_rewarded": False,
                "referred_by": None,
                "last_seen_at": datetime.now(timezone.utc).isoformat(),
                "currency": "USD",
                "language": None,
                "gender": None,
                "city": None,
                "joined_date": datetime.now().strftime("%Y-%m-%d"),
                "month": now_month()
            }
            save_user(uid)
            added += 1
    try:
        bot.send_message(m.chat.id, f"✅ Imported {added} users successfully.")
    except: pass

@bot.message_handler(func=lambda m: m.text == "📢 REFERRAL BROADCAST")
def admin_referral_broadcast(m):
    if not is_admin(m.from_user.id):
        return
    reward = referral_reward_amount()
    sent = 0
    failed = 0
    for uid, u in list(users.items()):
        try:
            ref = str(u.get("ref") or "").strip()
            if not ref:
                ref = random_ref()
                users[uid]["ref"] = ref
                save_user(uid)
            username = bot.get_me().username
            link = f"https://t.me/{username}?start={ref}"
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("📤 Share", switch_inline_query=link))
            bot.send_message(
                int(uid),
                "🎁 <b>REFERRAL EARNING UPDATE</b>\n\n"
                f"💰 You can earn <b>${reward:.2f}</b> for every eligible person you refer.\n"
                f"🔗 Your Referral Link: <code>{html.escape(link)}</code>\n\n"
                "📤 Use the <b>Share</b> button below to share your referral link directly.\n"
                "👥 When someone joins through your link and qualifies, the referral reward is credited according to the bot's referral rules.",
                reply_markup=kb,
                parse_mode="HTML"
            )
            sent += 1
        except Exception:
            failed += 1
    bot.send_message(m.chat.id, f"✅ Referral broadcast completed.\n\n📨 Sent: <b>{sent}</b>\n❌ Failed: <b>{failed}</b>", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == "🔗 GET REFERRAL CODE")
def get_ref_code_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send user username (e.g. @username):")
        bot.register_next_step_handler(msg, get_ref_username)
    except: pass

def get_ref_username(m):
    if not is_admin(m.from_user.id):
        return
    username = m.text.replace("@", "").strip()
    try:
        msg = bot.send_message(m.chat.id, f"User: @{username}\nNow send referral code number:")
        bot.register_next_step_handler(msg, lambda x: save_custom_ref_code(x, username))
    except: pass

def save_custom_ref_code(m, username):
    if not is_admin(m.from_user.id):
        return
    code = m.text.strip()
    if not code.isdigit():
        try:
            bot.send_message(m.chat.id, "❌ Code must be a number")
        except: pass
        return
    user_id = next((uid for uid, data in users.items() if data.get("username", "").lower() == username.lower()), None)
    if not user_id:
        try:
            bot.send_message(m.chat.id, "❌ User not found")
        except: pass
        return
    users[user_id]["ref"] = code
    save_user(user_id)
    try:
        bot.send_message(m.chat.id, f"✅ Referral code updated for @{username}")
    except: pass

@bot.message_handler(func=lambda m: m.text == "🔎 SEARCH USER")
def search_user(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send User Telegram ID")
        bot.register_next_step_handler(msg, search_user_result)
    except: pass

def search_user_result(m):
    if not is_admin(m.from_user.id):
        return
    uid = m.text.strip()
    if uid in users:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("💬 OPEN CHAT", url=f"tg://user?id={uid}"))
        kb.add(InlineKeyboardButton("✉️ MESSAGE USER", callback_data=f"msguser|{uid}"))
        try:
            bot.send_message(m.chat.id, f"👤 User Found\nID: {uid}", reply_markup=kb)
        except: pass
    else:
        try:
            bot.send_message(m.chat.id, "❌ User not found")
        except: pass

# ================= NEW FEATURE: CUSTOM REFERRAL CODES & PAY =================

def is_ref_taken(code):
    for uid, data in users.items():
        if str(data.get("ref")) == str(code):
            return True
    return False

@bot.message_handler(func=lambda m: m.text == "💳 PAY")
@bot.callback_query_handler(func=lambda call: call.data == "buy_ref_menu")
def pay_custom_ref_handler(m):
    if bot_locked_guard(m if hasattr(m, "from_user") else m.message) or banned_guard(m if hasattr(m, "from_user") else m.message):
        return
        
    chat_id = m.chat.id if hasattr(m, "chat") else m.message.chat.id
    if not get_setting("pay_rev_enabled", False):
        try:
            bot.send_message(chat_id, "❌ Custom referral code purchase system is currently disabled by admin.")
        except: pass
        if hasattr(m, "id"):
            bot.answer_callback_query(m.id)
        return
    try:
        msg = bot.send_message(chat_id, "💳 **Buy Custom Referral Code**\n\nEnter your desired referral code (letters/numbers):")
        bot.register_next_step_handler(msg, pay_custom_ref_code_input)
        if hasattr(m, "id"):
            bot.answer_callback_query(m.id)
    except: pass

def pay_custom_ref_code_input(m):
    uid = str(m.from_user.id)
    code = (m.text or "").strip()
    if not code or len(code) > 30:
        try:
            msg = bot.send_message(m.chat.id, "❌ Invalid code. Please enter a valid referral code:")
            bot.register_next_step_handler(msg, pay_custom_ref_code_input)
        except: pass
        return

    if is_ref_taken(code):
        try:
            msg = bot.send_message(m.chat.id, "⚠️ This referral code already taken. Please choose another one:")
            bot.register_next_step_handler(msg, pay_custom_ref_code_input)
        except: pass
        return

    length = len(code)
    if length <= 5:
        price = get_setting("ref_price_short", 50)
    else:
        price = get_setting("ref_price_long", 20)

    prices = [LabeledPrice(label=f"Custom Ref: {code}", amount=price)]
    try:
        bot.send_invoice(
            m.chat.id,
            title="Custom Referral Code",
            description=f"Purchase custom referral code: {code}",
            invoice_payload=f"buy_ref_{code}",
            provider_token="",
            currency="XTR",
            prices=prices
        )
    except Exception as e:
        try:
            bot.send_message(m.chat.id, f"❌ Error creating invoice: {e}")
        except: pass

@bot.message_handler(content_types=['successful_payment'])
def successful_payment_handler(message):
    payment = message.successful_payment
    payload = payment.invoice_payload
    uid = str(message.from_user.id)
    stars = int(getattr(payment, "total_amount", 0) or 0)
    if payload.startswith("balance_topup:"):
        rate = float(get_setting("stars_per_usd", 100))
        usd = stars / rate if rate > 0 else 0.0
        credit_user_balance(uid, usd, "stars_topup", network_commission=True)
        log_activity(uid, "stars_topup", {"stars": stars, "usd": usd})
        bot.send_message(message.chat.id, f"✅ <b>Balance Added</b>\n\n⭐ Stars: {stars}\n💵 Added: ${usd:.2f}\n💰 New balance: {money_text(uid, users[uid]['balance'])}")
        return
    
    if payload.startswith("buy_ref_"):
        code = payload.replace("buy_ref_", "")
        if is_ref_taken(code) and users.get(uid, {}).get("ref") != code:
            try:
                bot.send_message(message.chat.id, "⚠️ This referral code has just been taken by someone else. Please contact admin or try another code.")
            except: pass
            return
        users[uid]["ref"] = code
        save_user(uid)
        bot_username = bot.get_me().username
        link = f"https://t.me/{bot_username}?start={code}"
        try:
            bot.send_message(
                message.chat.id,
                f"🎉 <b>Success!</b> Your custom referral code has been successfully activated.\n\n"
                f"🔑 Code: <code>{code}</code>\n"
                f"🔗 New Referral Link:\n{link}",
                parse_mode="HTML"
            )
        except: pass

@bot.message_handler(func=lambda m: m.text == "Reveral Prices")
def admin_referral_prices(m):
    if not is_admin(m.from_user.id): return
    short_p = get_setting("ref_price_short", 50)
    long_p = get_setting("ref_price_long", 20)
    msg = f"⚙️ Referral Code Prices (Telegram Stars)\n\n• 1-5 chars price: {short_p} Stars\n• 6+ chars price: {long_p} Stars\n\nSend new price for short codes (1-5 chars) or type CANCEL:"
    msg_sent = bot.send_message(m.chat.id, msg, parse_mode="Markdown")
    bot.register_next_step_handler(msg_sent, set_short_price)

def set_short_price(m):
    if not is_admin(m.from_user.id): return
    if m.text.strip().lower() == "cancel":
        bot.send_message(m.chat.id, "Cancelled.")
        return
    try:
        p = int(m.text.strip())
        set_setting("ref_price_short", p)
        msg = bot.send_message(m.chat.id, f"✅ Short code price set to {p} Stars.\n\nNow send price for 6+ characters codes:")
        bot.register_next_step_handler(msg, set_long_price)
    except:
        msg = bot.send_message(m.chat.id, "❌ Invalid number. Try again or type CANCEL:")
        bot.register_next_step_handler(msg, set_short_price)

def set_long_price(m):
    if not is_admin(m.from_user.id): return
    if m.text.strip().lower() == "cancel":
        bot.send_message(m.chat.id, "Cancelled.")
        return
    try:
        p = int(m.text.strip())
        set_setting("ref_price_long", p)
        bot.send_message(m.chat.id, f"✅ Long code price set to {p} Stars successfully!")
    except:
        msg = bot.send_message(m.chat.id, "❌ Invalid number. Try again or type CANCEL:")
        bot.register_next_step_handler(msg, set_long_price)

@bot.message_handler(func=lambda m: m.text == "Delete Pay")
def delete_pay_handler(m):
    if not is_admin(m.from_user.id): return
    set_setting("pay_rev_enabled", False)
    bot.send_message(m.chat.id, "🛑 Referral code purchase system is now CLOSED (Deleted Pay).")

@bot.message_handler(func=lambda m: m.text == "Open Pay rev")
def open_pay_handler(m):
    if not is_admin(m.from_user.id): return
    set_setting("pay_rev_enabled", True)
    bot.send_message(m.chat.id, "🟢 Referral code purchase system is now OPEN.")

# ================= NEW FEATURE: SEND VERIFY BROADCAST =================

@bot.message_handler(func=lambda m: m.text == "Send verify")
def send_verify_broadcast_start(m):
    if not is_admin(m.from_user.id): return
    msg = bot.send_message(m.chat.id, "✍️ Send the message you want to broadcast with the email verification button to unverified users:")
    bot.register_next_step_handler(msg, send_verify_broadcast_process)

def send_verify_broadcast_process(m):
    if not is_admin(m.from_user.id): return
    text = m.text
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔐 Verify Now", callback_data="start_verify_flow"))
    
    count = 0
    for uid, udata in users.items():
        if not udata.get("verified", False):
            try:
                bot.send_message(int(uid), text, reply_markup=kb)
                count += 1
            except:
                continue
    bot.send_message(m.chat.id, f"✅ Verification broadcast sent to {count} unverified users successfully.")

# ================= LINK HANDLER =================

def grant_premium_days(uid,days,reason="admin"):
    uid=str(uid); now=datetime.now(timezone.utc); old=users.get(uid,{}).get("premium_until")
    try: old_dt=datetime.fromisoformat(str(old).replace("Z","+00:00")) if old else now
    except Exception: old_dt=now
    if old_dt.tzinfo is None: old_dt=old_dt.replace(tzinfo=timezone.utc)
    until=max(now,old_dt)+timedelta(days=int(days)); users[uid]["premium_until"]=until.isoformat(); users[uid]["premium_warning_sent"]=False; users[uid]["premium_source"]=("trial" if "trial" in str(reason).lower() else "paid"); save_user(uid)
    premium_logs_col.insert_one({"user_id":uid,"days":int(days),"until":until.isoformat(),"time":now.isoformat(),"type":reason}); log_activity(uid,"premium_grant",{"days":days,"reason":reason})
    return until

# ================= PREMIUM SYSTEM =================
def get_premium_prices():
    return {k: float(get_setting(f"premium_price_{k}", v)) for k, v in PREMIUM_DEFAULT_PRICES.items()}

def premium_features_text():
    platforms=", ".join(premium_platform_names())
    return (
        "💎 <b>PREMIUM</b>\n\n"
        "🚀 Priority download queue + high concurrency\n"
        "⚡ Premium queue is faster than Free queue\n"
        "⚡ No artificial speed throttle from the bot\n"
        "🎥 Higher quality: 720p • 1080p • 1440p • 4K\n"
        "▶️ Full YouTube videos + Shorts\n"
        f"📥 <b>{len(premium_platform_names())} platforms</b>: {html.escape(platforms)}\n"
        "🎵 Better music metadata\n"
        "📦 Premium file-size limit is admin controlled\n\n"
        "🔐 Verification requirement can be controlled by Admin."
    )

def premium_plan_keyboard():
    prices = get_premium_prices()
    kb = InlineKeyboardMarkup(row_width=2)
    for months in ["1", "3", "9", "12"]:
        label = {"1":"1 Month", "3":"3 Months", "9":"9 Months", "12":"12 Months"}[months]
        kb.add(InlineKeyboardButton(f"{label} — ${prices[months]:.2f}", callback_data=f"premium_buy:{months}"))
    return kb

def send_quality_menu(chat_id, link):
    uid = str(chat_id)
    premium_quality_pending[uid] = {"link": link, "created": time.time()}
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("720p", callback_data="quality:720"), InlineKeyboardButton("1080p", callback_data="quality:1080"))
    kb.add(InlineKeyboardButton("1440p", callback_data="quality:1440"), InlineKeyboardButton("4K", callback_data="quality:2160"))
    bot.send_message(chat_id, "💎 <b>Premium Quality</b>\n\nChoose your download quality:", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "💎 PREMIUM")
def premium_button(m):
    touch_user(m.from_user.id)
    if bot_locked_guard(m) or banned_guard(m): return
    show_premium_menu(m.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "premium_menu")
def premium_menu_callback(call):
    bot.answer_callback_query(call.id)
    show_premium_menu(call.message.chat.id)

def show_premium_menu(chat_id):
    uid = str(chat_id)
    if is_premium(uid):
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🎥 Choose Quality", callback_data="premium_quality_info"))
        bot.send_message(chat_id, premium_features_text() + f"\n\n✅ <b>Active until:</b> {premium_until_text(uid)}", reply_markup=kb)
    else:
        if premium_verification_required() and not user_is_verified(uid):
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("🔐 VERIFY ACCOUNT", callback_data="start_verify_flow"))
            bot.send_message(chat_id, premium_features_text() + "\n\n⚠️ Verification is required before Premium. Choose any available verification method.", reply_markup=kb)
            return
        kb = premium_plan_keyboard()
        if trial_available(uid):
            kb.add(InlineKeyboardButton(f"🎁 {trial_days()} DAY FREE TRIAL", callback_data="premium_trial"))
        kb.add(InlineKeyboardButton("💳 ADD BALANCE", callback_data="topup_menu"))
        bot.send_message(chat_id, premium_features_text() + "\n\n💰 <b>Choose a plan:</b>", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("premium_buy:"))
def premium_buy_callback(call):
    uid = str(call.from_user.id)
    if premium_verification_required() and not user_is_verified(uid):
        bot.answer_callback_query(call.id, "❌ Verify your account first.", show_alert=True); return
    months = call.data.split(":",1)[1]
    if balance_is_locked(uid):
        bot.answer_callback_query(call.id,"❌ Your balance is temporarily closed.",show_alert=True); return
    if months not in PREMIUM_DEFAULT_PRICES:
        bot.answer_callback_query(call.id, "Invalid plan.", show_alert=True); return
    price = get_premium_prices()[months]
    bal = balance_amount(uid)
    price_asset = usd_to_asset(cur_code(uid), price)
    available = available_asset_amount(uid)
    if available < price_asset:
        bot.answer_callback_query(call.id, "❌ Insufficient balance.", show_alert=True)
        bot.send_message(call.message.chat.id, f"❌ You need <b>{format_asset(cur_code(uid),price_asset)}</b> (${price:.2f}). Your available balance is <b>{format_asset(cur_code(uid),available)}</b>.\n\n💰 Earn more through referrals or ask admin to add balance.")
        return
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(f"✅ Pay ${price:.2f} from balance", callback_data=f"premium_confirm:{months}"))
    kb.add(InlineKeyboardButton("❌ Cancel", callback_data="premium_cancel"))
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"💎 <b>{months} month Premium</b>\n\nPrice: <b>{money_text(uid, price)}</b> (USD ${price:.2f})\nYour balance: <b>{money_text(uid, bal)}</b>\n\nConfirm payment?", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("premium_confirm:"))
def premium_confirm_callback(call):
    uid = str(call.from_user.id)
    months = call.data.split(":",1)[1]
    price = get_premium_prices().get(months)
    if price is None or (premium_verification_required() and not user_is_verified(uid)):
        bot.answer_callback_query(call.id, "❌ Premium purchase unavailable.", show_alert=True); return
    bal = balance_amount(uid)
    price_asset = usd_to_asset(cur_code(uid), price)
    available = available_asset_amount(uid)
    if available < price_asset:
        bot.answer_callback_query(call.id, "❌ Insufficient balance.", show_alert=True); return
    now = datetime.now(timezone.utc)
    old = users[uid].get("premium_until")
    try:
        old_dt = datetime.fromisoformat(str(old).replace("Z", "+00:00")) if old else now
        if old_dt.tzinfo is None: old_dt = old_dt.replace(tzinfo=timezone.utc)
    except Exception: old_dt = now
    base = max(now, old_dt)
    until = base + timedelta(days=30*int(months))
    ledger_debit(uid,price_asset,"premium_purchase",{"price_usd":price,"months":months})
    users[uid]["premium_until"] = until.isoformat()
    users[uid]["premium_warning_sent"] = False
    users[uid]["premium_source"] = "paid"
    save_user(uid)
    premium_logs_col.insert_one({"user_id": uid, "months": int(months), "price": price, "until": until.isoformat(), "time": now.isoformat(), "type": "purchase"})
    bot.answer_callback_query(call.id, "✅ Premium activated!")
    bot.edit_message_text(f"🎉 <b>Premium Activated!</b>\n\n📅 Duration: {months} months\n💵 Paid: ${price:.2f}\n⏰ Expires: <b>{local_datetime_text(uid, until)}</b>\n\n🌐 <b>17 Premium/Trial Platforms:</b>\n{html.escape(', '.join(premium_platform_names()))}\n\n⚡ Priority downloads\n🎥 Higher quality\n▶️ Full YouTube is unlocked.", call.message.chat.id, call.message.message_id, parse_mode="HTML")
    send_premium_email(uid, "Premium Activated", months, price, until)

@bot.callback_query_handler(func=lambda call: call.data == "premium_cancel")
def premium_cancel(call):
    bot.answer_callback_query(call.id, "Cancelled")
    try: bot.edit_message_text("❌ Premium purchase cancelled.", call.message.chat.id, call.message.message_id)
    except Exception: pass

@bot.callback_query_handler(func=lambda call: call.data == "premium_quality_info")
def premium_quality_info(call):
    bot.answer_callback_query(call.id)
    current = users.get(str(call.from_user.id), {}).get("premium_quality", "Not selected")
    bot.send_message(call.message.chat.id, f"💎 <b>Premium quality</b> is saved per account.\n\nCurrent: <b>{current if current != '2160' else '4K'}</b>\n\nSend a new link and the saved quality will be used automatically.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_quality:"))
def set_quality_callback(call):
    uid = str(call.from_user.id)
    if not (is_quick_access(uid) or is_premium(uid) or _is_trial_active(uid)):
        bot.answer_callback_query(call.id, "❌ Premium/Trial required.", show_alert=True); return
    q = call.data.split(":",1)[1]
    if q not in PREMIUM_QUALITY_FORMATS:
        bot.answer_callback_query(call.id, "Invalid quality.", show_alert=True); return
    users[uid]["premium_quality"] = q
    save_user(uid)
    pending = premium_quality_pending.pop(uid, None)
    bot.answer_callback_query(call.id, "✅ Quality saved")
    bot.edit_message_text(f"✅ Premium quality saved: {q if q != '2160' else '4K'}\n\nFuture downloads will use this quality automatically.", call.message.chat.id, call.message.message_id)
    if pending and pending.get("link") and not pending.get("set_only"):
        msg = bot.send_message(call.message.chat.id, "✍️ Typing...\n⬇️ Downloading...")
        download_executor_for(call.from_user.id).submit(download_media, call.message.chat.id, pending["link"], msg.message_id, q)


@bot.callback_query_handler(func=lambda call: call.data.startswith("quality:"))
def quality_callback(call):
    uid = str(call.from_user.id)
    if not (is_quick_access(uid) or is_premium(uid) or _is_trial_active(uid)):
        bot.answer_callback_query(call.id, "❌ Premium/Trial required.", show_alert=True); return
    q = call.data.split(":",1)[1]
    data = premium_quality_pending.get(uid)
    if not data:
        bot.answer_callback_query(call.id, "❌ Quality session expired. Send the link again.", show_alert=True); return
    premium_quality_pending.pop(uid, None)
    users.setdefault(uid,{})["premium_quality"]=q; save_user(uid)
    bot.answer_callback_query(call.id, f"✅ {q if q != '2160' else '4K'} saved")
    send_action(call.message.chat.id, "typing")
    msg = bot.send_message(call.message.chat.id, f"✍️ Typing...\n⬇️ Downloading at {q if q != '2160' else '4K'} quality...")
    download_executor_for(call.from_user.id).submit(download_media, call.message.chat.id, data["link"], msg.message_id, q)

def send_premium_email(uid, subject, months, price, until):
    email=users.get(str(uid),{}).get("email")
    if not email: return False
    body=("<html><body style='margin:0;background:#f3f8f5;font-family:Arial;color:#10231d'>"
          "<div style='max-width:620px;margin:30px auto;background:white;border-radius:22px;overflow:hidden'>"
          "<div style='padding:28px;background:linear-gradient(135deg,#087f5b,#19b77d);color:white'><h1 style='margin:0'>💎 Downloader Bot</h1><p>Premium account notification</p></div>"
          f"<div style='padding:30px'><h2>{html.escape(subject)}</h2><p>Your Premium access is active.</p><div style='background:#f0faf6;padding:18px;border-radius:14px'><b>Duration:</b> {months if months else 'Trial / Reward'}<br><b>Paid:</b> ${price:.2f}<br><b>Expires:</b> {html.escape(local_datetime_text(uid, until))}<br><b>Platforms:</b> {len(premium_platform_names())}<br><b>YouTube:</b> Premium only<br><b>Speed:</b> No artificial bot throttle</div><p>Thank you for using our service.</p></div></div></body></html>")
    return send_html_email(email,subject,body)

def send_premium_expiry_email(uid,until,days_left=None,expired=False):
    email=users.get(str(uid),{}).get("email")
    if not email: return False
    subject="Your Downloader Bot Premium has expired" if expired else f"Your Downloader Bot Premium expires in {days_left} day(s)"
    title="⏰ Premium Expired" if expired else "⚠️ Premium Expiry Reminder"
    body=("<html><body style='margin:0;background:#f4f7f6;font-family:Arial'><div style='max-width:620px;margin:30px auto;background:#fff;border-radius:20px;padding:30px'>"
          f"<h1>{title}</h1><p>Your Premium {('has ended.' if expired else f'will expire in {days_left} day(s).')}</p><p><b>Expiry:</b> {until.strftime('%Y-%m-%d %H:%M UTC')}</p><p>Open <b>💎 PREMIUM</b> in Telegram to renew.</p></div></body></html>")
    return send_html_email(email,subject,body)

def conversion_hold_worker():
    while True:
        try:
            now=datetime.now(timezone.utc)
            for h in conversion_holds_col.find({"status":"hold","expires_at":{"$lte":now}}):
                conversion_holds_col.update_one({"_id":h["_id"],"status":"hold"},{"$set":{"status":"released_auto","released_at":now}})
                try: bot.send_message(int(h.get("user_id")),f"✅ Your ${float(h.get('usd_amount',0)):,.2f} USD hold has expired. The amount is now available.")
                except: pass
        except Exception as e: print("Hold worker error:",e)
        time.sleep(60)

def premium_expiry_worker():
    while True:
        try:
            now=datetime.now(timezone.utc)
            for uid,data in list(users.items()):
                until=data.get("premium_until")
                if not until: continue
                try: dt=until if isinstance(until,datetime) else datetime.fromisoformat(str(until).replace("Z","+00:00")); dt=dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
                except Exception: continue
                if dt<=now:
                    data["premium_until"]=None; data["premium_warning_sent"]=False; save_user(uid)
                    try: bot.send_message(int(uid),f"⏰ <b>Your Downloader Bot Premium has expired.</b>\n\n🕒 Expired at: <b>{local_datetime_text(uid, dt)}</b>\n\n💎 Open Premium to renew.")
                    except Exception: pass
                    send_premium_expiry_email(uid,dt,expired=True)
                elif dt-now<=timedelta(days=7) and not data.get("premium_warning_sent",False):
                    data["premium_warning_sent"]=True; save_user(uid); days=max(1,int((dt-now).total_seconds()//86400))
                    try: bot.send_message(int(uid),f"⚠️ <b>Premium expires in {days} day(s).</b>\n\nRenew now to keep Premium features.")
                    except Exception: pass
                    send_premium_expiry_email(uid,dt,days_left=days)
        except Exception as e: print("Premium worker error:",e)
        time.sleep(PREMIUM_CHECK_INTERVAL)

# ================= PREMIUM EXTRA PLATFORMS =================
PLATFORM_PATTERNS.update({
    "reddit": ("reddit.com", "redd.it"),
    "threads": ("threads.net",),
    "likee": ("likee.video", "like.video"),
    "vimeo": ("vimeo.com",),
    "dailymotion": ("dailymotion.com", "dai.ly"),
    "soundcloud": ("soundcloud.com",),
    "twitch": ("twitch.tv",),
    "tumblr": ("tumblr.com",),
    "streamable": ("streamable.com",),
    "odnoklassniki": ("ok.ru",),
})
PREMIUM_EXTRA_PLATFORMS = ["Reddit", "Threads", "Likee", "Vimeo", "Dailymotion", "SoundCloud", "Twitch", "Tumblr", "Streamable", "OK.ru"]

@bot.message_handler(func=lambda m: m.text and "http" in m.text)
def handle_links(message):
    touch_user(message.from_user.id)
    if bot_locked_guard(message) or banned_guard(message): return
    user_id = message.from_user.id
    uid = str(user_id)
    link = extract_url(message.text)
    if not link: return

    if CHANNEL_WINDOW_OPEN and POST_CHANNELS:
        for ch in POST_CHANNELS:
            try:
                member = bot.get_chat_member(f"@{ch}", user_id)
                if member.status not in ["member", "administrator", "creator"]:
                    pending_links[user_id] = link; send_multi_join(user_id); return
            except Exception:
                pending_links[user_id] = link; send_multi_join(user_id); return

    # Verification is required before Premium and before protected downloads.
    if VERIFY_ENABLED and not user_is_verified(uid):
        verify_pending[user_id] = {"link": link}
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📩 Verify via DM", callback_data="via_telegram"))
        kb.add(InlineKeyboardButton("🤖 Verify via Bot", url=f"https://t.me/Verifyd_bot?start=verify_{user_id}"))
        bot.send_message(message.chat.id, "🔐 Verification Required\n\nPlease verify your account before downloading.", reply_markup=kb); return

    platform = detect_platform(link)
    # Free access policy: 6 social platforms + YouTube Shorts.
    # Full YouTube and the 10 Premium-only extra platforms require Premium/Trial,
    # unless Admin has explicitly enabled full YouTube for Free users.
    if premium_required_for_platform(platform, uid, link) and not is_premium(uid):
        if platform == "youtube" and users.get(uid,{}).get("youtube_30m",False):
            pass
        else:
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("💎 OPEN PREMIUM", callback_data="premium_menu"))
            bot.send_message(message.chat.id, premium_gate_message(uid, platform), reply_markup=kb, parse_mode="HTML")
            return

    # Premium quality is selected once and stored on the user.
    # If no quality has been selected yet, ask once; future links use the saved quality.
    if is_quick_access(uid):
        quality = users.get(uid, {}).get("premium_quality") or "1080"
    elif is_premium(uid) or _is_trial_active(uid):
        saved_quality = users.get(uid, {}).get("premium_quality")
        if saved_quality not in PREMIUM_QUALITY_FORMATS:
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(InlineKeyboardButton("720p", callback_data="set_quality:720"), InlineKeyboardButton("1080p", callback_data="set_quality:1080"))
            kb.add(InlineKeyboardButton("1440p", callback_data="set_quality:1440"), InlineKeyboardButton("4K", callback_data="set_quality:2160"))
            bot.send_message(message.chat.id, "💎 <b>Choose your Premium quality once.</b>\nYour choice will be used automatically for future downloads.", reply_markup=kb)
            premium_quality_pending[uid] = {"link": link, "created": time.time(), "set_only": True}
            return
        quality = saved_quality

    try:
        send_action(message.chat.id, "typing")
        msg = bot.send_message(message.chat.id, "✍️ Typing...\n⬇️ Preparing your download...")
        download_executor_for(uid).submit(
            download_media, message.chat.id, link, msg.message_id,
            quality if (is_quick_access(uid) or is_premium(uid) or _is_trial_active(uid)) else None
        )
    except Exception: pass

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
        try:
            bot.answer_callback_query(call.id, "✅ Join verified")
        except: pass
        if user_id in pending_links:
            link = pending_links[user_id]
            del pending_links[user_id]
            try:
                msg = bot.send_message(user_id, "⬇️ Processing your video...")
                download_executor_for(user_id).submit(download_media, user_id, link, msg.message_id)
            except: pass
        else:
            # Multi-channel confirmation must also complete onboarding: show
            # the configurable welcome message and the user's real main menu.
            try:
                bot.send_message(
                    user_id,
                    render_start_message(str(user_id)),
                    reply_markup=welcome_destination_markup(),
                    parse_mode="HTML"
                )
                bot.send_message(user_id, "👇 <b>Main Menu</b>", reply_markup=localized_user_menu(str(user_id)), parse_mode="HTML")
            except Exception as e:
                print("MULTI WELCOME AFTER CONFIRM ERROR:", repr(e))
    else:
        try:
            bot.answer_callback_query(call.id, "❌ You must join all channels first!", show_alert=True)
        except: pass

@bot.message_handler(func=lambda m: m.text == "❌ CLOSE WINDOWS")
def close_channel_windows(m):
    global CHANNEL_WINDOW_OPEN
    if not is_admin(m.from_user.id):
        return
    CHANNEL_WINDOW_OPEN = False
    try:
        bot.send_message(m.chat.id, "✅ Channel join system disabled.")
    except: pass

@bot.message_handler(func=lambda m: m.text == "✅ VERIFY ON")
def verify_on(m):
    global VERIFY_ENABLED
    if not is_admin(m.from_user.id):
        return
    VERIFY_ENABLED = True
    try:
        bot.send_message(m.chat.id, "✅ Verify system enabled")
    except: pass

@bot.message_handler(func=lambda m: m.text == "❌ VERIFY OFF")
def verify_off(m):
    global VERIFY_ENABLED
    if not is_admin(m.from_user.id):
        return
    VERIFY_ENABLED = False
    try:
        bot.send_message(m.chat.id, "❌ Verify system disabled")
    except: pass

@bot.message_handler(func=lambda m: m.text == "CHANNEL POST")
def start_channel_post(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send the main text for the channel post.")
        bot.register_next_step_handler(msg, post_main_text)
    except: pass

def post_main_text(m):
    pending_post[m.from_user.id] = {"text": m.text, "buttons": []}
    try:
        msg = bot.send_message(m.chat.id, "Send button like:\n\nButton Name | Text when clicked\n\nSend DONE when finished.")
        bot.register_next_step_handler(msg, add_buttons)
    except: pass

def add_buttons(m):
    uid = m.from_user.id
    if m.text.lower() == "done":
        data = pending_post.get(uid)
        if not data:
            return
        kb = InlineKeyboardMarkup()
        for i, btn in enumerate(data["buttons"]):
            kb.add(InlineKeyboardButton(btn["name"], callback_data=f"postbtn_{i}"))
        for ch in MANAGED_CHANNELS:
            try:
                msg = bot.send_message(ch, data["text"], reply_markup=kb)
                channel_posts[msg.message_id] = data
            except: pass
        pending_post.pop(uid, None)
        try:
            bot.send_message(m.chat.id, "✅ Post sent")
        except: pass
        return

    try:
        name, content = m.text.split("|", 1)
        pending_post[uid]["buttons"].append({"name": name.strip(), "content": content.strip()})
        msg = bot.send_message(m.chat.id, "Button added. Send another or DONE")
        bot.register_next_step_handler(msg, add_buttons)
    except:
        try:
            msg = bot.send_message(m.chat.id, "❌ Format error\nButton Name | Text")
            bot.register_next_step_handler(msg, add_buttons)
        except: pass

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
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    except: pass

@bot.message_handler(func=lambda m: m.text == "➕ ADD BALANCE")
def add_balance_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send BOT ID or Telegram ID and amount:")
        bot.register_next_step_handler(msg, add_balance_process)
    except: pass

def add_balance_process(m):
    if not is_admin(m.from_user.id):
        return
    try:
        uid_str, amt_str = m.text.strip().split()
        amt = float(amt_str)
        uid = uid_str if uid_str in users else find_user_by_botid(uid_str)
        if not uid or amt <= 0:
            try:
                bot.send_message(m.chat.id, "❌ Invalid input")
            except: pass
            return
        asset_amt=ledger_credit(uid,amt,"admin_add_balance",{"admin_id":str(m.from_user.id)})
        try:
            bot.send_message(m.chat.id, f"✅ Added ${amt:.2f} USD = {format_asset(cur_code(uid),asset_amt)} to user {uid}")
            bot.send_message(int(uid), f"💰 Your balance increased by ${amt:.2f}")
        except: pass
    except:
        try:
            bot.send_message(m.chat.id, "❌ Format error.")
        except: pass

@bot.message_handler(func=lambda m: m.text == "➖ REMOVE MONEY")
def remove_balance_start(m):
    if not is_admin(m.from_user.id):
        return
    try:
        msg = bot.send_message(m.chat.id, "Send BOT ID or Telegram ID and amount:")
        bot.register_next_step_handler(msg, remove_balance_process)
    except: pass

def remove_balance_process(m):
    if not is_admin(m.from_user.id):
        return
    try:
        uid_str, amt_str = m.text.strip().split()
        amt = float(amt_str)
        uid = uid_str if uid_str in users else find_user_by_botid(uid_str)
        if not uid or amt <= 0:
            try:
                bot.send_message(m.chat.id, "❌ Invalid input")
            except: pass
            return
        if available_asset_amount(uid) < usd_to_asset(cur_code(uid),amt):
            try:
                bot.send_message(m.chat.id, "❌ Insufficient balance")
            except: pass
            return
        asset_amt=usd_to_asset(cur_code(uid),amt)
        ledger_debit(uid,asset_amt,"admin_remove_balance",{"admin_id":str(m.from_user.id)})
        try:
            bot.send_message(m.chat.id, f"✅ Removed ${amt:.2f} USD from user {uid}")
            bot.send_message(int(uid), f"💸 ${amt:.2f} removed from your balance")
        except: pass
    except:
        try:
            bot.send_message(m.chat.id, "❌ Format error.")
        except: pass

# ================= PREMIUM VERIFICATION CONTROL =================
@bot.message_handler(func=lambda m: m.text in ["🔐 PREMIUM VERIFY ON","🔓 PREMIUM VERIFY OFF"])
def premium_verify_control(m):
    if not is_admin(m.from_user.id): return
    enabled = m.text == "🔐 PREMIUM VERIFY ON"
    set_setting("premium_verify_required", enabled)
    bot.send_message(m.chat.id, f"{'🔐 Premium verification is now REQUIRED.' if enabled else '🔓 Premium verification is now OPTIONAL.'}\n\nUsers can still use any available Gmail/SMS/WhatsApp verification when required.")

# ================= ADMIN BALANCE LOCK / VIEW MANAGEMENT =================
def _balance_snapshot(uid):
    u=users.get(str(uid),{})
    return {
        "user_id":str(uid), "username":u.get("username",""), "bot_id":u.get("bot_id",""),
        "balance":float(u.get("balance",0) or 0), "blocked":float(u.get("blocked",0) or 0),
        "balance_asset":u.get("balance_asset") or u.get("currency") or "USD",
        "currency":u.get("currency") or "USD", "portfolio":dict(u.get("portfolio") or {}),
        "created_at":datetime.now(timezone.utc),
        "expires_at":datetime.now(timezone.utc)+timedelta(days=10),
    }

def _close_one_balance(uid, notify=True):
    uid=str(uid)
    if uid not in users: return None
    old=balance_freezes_col.find_one({"user_id":uid,"status":"closed"})
    if old and balance_lock_remaining(uid)>0: return old.get("activation_code")
    snap=_balance_snapshot(uid); code=generate_balance_activation_code(); snap.update({"status":"closed","activation_code":code})
    balance_freezes_col.delete_many({"user_id":uid,"status":"closed"}); balance_freezes_col.insert_one(snap)
    users[uid]["balance_locked"]=True; users[uid]["balance_activation_code"]=code; users[uid]["balance_lock_until"]=snap["expires_at"].isoformat(); save_user(uid)
    if notify:
        try: bot.send_message(int(uid),"🔒 <b>Your Balance has been temporarily closed by Admin.</b>\n\n" f"🗝 <b>Activation Code:</b> <code>{code}</code>\n" f"⏳ Open within <b>10 days</b> to keep your funds.\n" "If the deadline passes without activation, the saved balance is permanently removed.\n\n" "Contact Customer/Admin if you need your balance activated.")
        except Exception: pass
    return code

def _restore_one_balance(uid):
    uid=str(uid); snap=balance_freezes_col.find_one({"user_id":uid,"status":"closed"})
    if not snap: return False,"No closed balance record."
    exp=parse_seen_time(snap.get("expires_at"))
    if exp and exp<=datetime.now(timezone.utc):
        balance_freezes_col.delete_one({"_id":snap["_id"]}); users[uid]["balance_locked"]=False; users[uid]["balance_activation_code"]=None; users[uid]["balance_lock_until"]=None; users[uid]["balance"]=0.0; users[uid]["blocked"]=0.0; users[uid]["portfolio"]={}; save_user(uid)
        return False,"The 10-day activation period has expired; the balance was permanently removed."
    users[uid]["balance"]=float(snap.get("balance",0) or 0); users[uid]["blocked"]=float(snap.get("blocked",0) or 0); users[uid]["balance_asset"]=snap.get("balance_asset") or "USD"; users[uid]["currency"]=snap.get("currency") or users[uid]["balance_asset"]; users[uid]["portfolio"]=dict(snap.get("portfolio") or {}); users[uid]["balance_locked"]=False; users[uid]["balance_activation_code"]=None; users[uid]["balance_lock_until"]=None; save_user(uid)
    balance_freezes_col.update_one({"_id":snap["_id"]},{"$set":{"status":"opened","opened_at":datetime.now(timezone.utc)}})
    return True,"Balance restored successfully."

@bot.message_handler(func=lambda m: m.text == "💰 SEE BALANCE")
def admin_see_balance_broadcast(m):
    if not is_admin(m.from_user.id): return
    msg=bot.send_message(m.chat.id,"💰 <b>SEE BALANCE</b>\n\nSend the message you want users to receive together with their current balance.\nExample: <code>You have $100 balance. Come use your balance.</code>")
    bot.register_next_step_handler(msg,admin_see_balance_broadcast_step)

def admin_see_balance_broadcast_step(m):
    if not is_admin(m.from_user.id): return
    custom=(m.text or "").strip()
    if not custom: bot.send_message(m.chat.id,"❌ Message cannot be empty."); return
    sent=0
    for uid,u in list(users.items()):
        try:
            if balance_is_locked(uid):
                text=balance_locked_message(uid)
            else:
                av=available_asset_amount(uid); bl=blocked_amount(uid); pd=pending_withdrawal_amount(uid)
                text=(f"💰 <b>Available Balance:</b> {format_asset(cur_code(uid),av)}\n"
                      f"🔒 <b>Blocked Amount:</b> {format_asset(cur_code(uid),bl)}\n"
                      f"⏳ <b>Pending Amount:</b> {format_asset(cur_code(uid),pd)}\n\n{html.escape(custom)}")
            bot.send_message(int(uid),text); sent+=1
        except Exception: pass
    bot.send_message(m.chat.id,f"✅ Balance message sent to <b>{sent}</b> users.")

@bot.message_handler(func=lambda m: m.text == "📊 SEE ALL BALANCE")
def admin_see_all_balance(m):
    if not is_admin(m.from_user.id): return
    lines=["📊 <b>ALL USER BALANCES</b>",""]
    for i,(uid,u) in enumerate(users.items(),1):
        username=("@"+u.get("username")) if u.get("username") else "No username"
        locked="🔒 CLOSED" if balance_is_locked(uid) else "🟢 OPEN"
        av=available_asset_amount(uid); blocked=blocked_amount(uid); pending=pending_withdrawal_amount(uid)
        port=portfolio_usd_value(uid)
        lines.append(f"{i}. {username} | <code>{uid}</code> | 🤖 {u.get('bot_id','N/A')}\n   💰 {format_asset(cur_code(uid),av)} | 🔒 {format_asset(cur_code(uid),blocked)} | ⏳ {format_asset(cur_code(uid),pending)} | 💼 ${port:,.2f} | {locked}")
    if len(lines)==2: lines.append("No users found.")
    # Telegram message limit safety
    text="\n".join(lines)
    for i in range(0,len(text),3800): bot.send_message(m.chat.id,text[i:i+3800])

@bot.message_handler(func=lambda m: m.text == "🔒 CLOSE ALL BALANCE")
def close_all_balance_admin(m):
    if not is_admin(m.from_user.id): return
    count=0
    for uid in list(users.keys()):
        if float(users[uid].get("balance",0) or 0)>0 or float(users[uid].get("blocked",0) or 0)>0 or get_portfolio(uid):
            if _close_one_balance(uid,notify=True): count+=1
    bot.send_message(m.chat.id,f"🔒 <b>ALL BALANCES CLOSED</b>\n\nUsers frozen: <b>{count}</b>\nEach user received a unique 25-character activation code.\n⏳ Deadline: 10 days. After expiry, the saved balance is permanently removed.")

@bot.message_handler(func=lambda m: m.text == "🔓 OPEN ALL BALANCE")
def open_all_balance_admin(m):
    if not is_admin(m.from_user.id): return
    restored=expired=0
    for uid in list(users.keys()):
        if balance_is_locked(uid):
            ok,msg=_restore_one_balance(uid)
            if ok:
                restored+=1
                try: bot.send_message(int(uid),"🟢 <b>Your Balance has been reopened by Admin.</b>\n\n💰 Available and blocked funds are active again.")
                except Exception: pass
            elif "expired" in msg.lower(): expired+=1
    bot.send_message(m.chat.id,f"🔓 <b>OPEN ALL BALANCE</b>\n\n✅ Restored: <b>{restored}</b>\n🗑 Expired/deleted: <b>{expired}</b>")

@bot.message_handler(func=lambda m: m.text == "🔓 OPEN PERSON BALANCE")
def open_person_balance_start(m):
    if not is_admin(m.from_user.id): return
    msg=bot.send_message(m.chat.id,"🔓 <b>OPEN PERSON BALANCE</b>\n\nSend the user's 25-character activation code:")
    bot.register_next_step_handler(msg,open_person_balance_process)

def open_person_balance_process(m):
    if not is_admin(m.from_user.id): return
    code=(m.text or "").strip().upper()
    snap=balance_freezes_col.find_one({"activation_code":code,"status":"closed"})
    if not snap: bot.send_message(m.chat.id,"❌ Invalid or already used activation code."); return
    uid=str(snap.get("user_id"))
    ok,msg=_restore_one_balance(uid)
    if not ok: bot.send_message(m.chat.id,"❌ "+msg); return
    bot.send_message(m.chat.id,f"✅ Balance opened for user <code>{uid}</code>.")
    try: bot.send_message(int(uid),"🟢 <b>Your Balance has been reopened by Admin.</b>\n\nYour saved balance and crypto portfolio are active again.")
    except Exception: pass

@bot.message_handler(func=lambda m: m.text == "🗑 REMOVE ALL BALANCE")
def remove_all_balance_start(m):
    if not is_admin(m.from_user.id): return
    msg=bot.send_message(m.chat.id,"🗑 <b>REMOVE ALL BALANCE</b>\n\nSend Username, BOT ID or Telegram ID.\nExample: <code>@username</code> or <code>123456789</code>")
    bot.register_next_step_handler(msg,remove_all_balance_process)

def remove_all_balance_process(m):
    if not is_admin(m.from_user.id): return
    raw=(m.text or "").strip(); uid=raw.lstrip("@")
    if uid not in users:
        uid=next((x for x,u in users.items() if str(u.get("username","")).lstrip("@").lower()==raw.lstrip("@").lower()),None)
    if uid not in users:
        uid=find_user_by_botid(raw)
    if not uid: bot.send_message(m.chat.id,"❌ User not found."); return
    users[uid]["balance"]=0.0; users[uid]["blocked"]=0.0; users[uid]["portfolio"]={}; users[uid]["balance_locked"]=False; users[uid]["balance_activation_code"]=None; users[uid]["balance_lock_until"]=None; save_user(uid)
    balance_freezes_col.delete_many({"user_id":str(uid)})
    conversion_holds_col.update_many({"user_id":str(uid),"status":"hold"},{"$set":{"status":"admin_removed_balance","released_at":datetime.now(timezone.utc)}})
    balance_ledger_col.insert_one({"user_id":str(uid),"type":"admin_remove_all_balance","admin_id":str(m.from_user.id),"time":datetime.now(timezone.utc)})
    bot.send_message(m.chat.id,f"🗑 <b>ALL BALANCE REMOVED</b>\n\nUser: <code>{uid}</code>\n💰 Balance: $0.00\n🪙 Crypto portfolio: cleared.")
    try: bot.send_message(int(uid),"🗑 <b>Your balance and all crypto holdings were removed by Admin.</b>")
    except Exception: pass

def balance_lock_worker():
    while True:
        try:
            now=datetime.now(timezone.utc)
            for snap in balance_freezes_col.find({"status":"closed","expires_at":{"$lte":now}}):
                uid=str(snap.get("user_id"))
                if uid in users and balance_is_locked(uid):
                    users[uid]["balance"]=0.0; users[uid]["blocked"]=0.0; users[uid]["portfolio"]={}; users[uid]["balance_locked"]=False; users[uid]["balance_activation_code"]=None; users[uid]["balance_lock_until"]=None; save_user(uid)
                    try: bot.send_message(int(uid),"🗑 <b>Your closed balance expired after 10 days and was permanently removed.</b>")
                    except Exception: pass
                balance_freezes_col.update_one({"_id":snap["_id"]},{"$set":{"status":"expired","expired_at":now}})
        except Exception as e: print("Balance lock worker error:",e)
        time.sleep(3600)

# ================= ADMIN PREMIUM MANAGEMENT =================
@bot.message_handler(func=lambda m: m.text == "💎 PREMIUM PANEL")
def admin_premium_panel(m):
    if not is_admin(m.from_user.id): return
    prices=get_premium_prices()
    active=sum(1 for uid in users if is_premium(uid))
    bot.send_message(m.chat.id, f"💎 PREMIUM PANEL\n\n👑 Active Premium Users: {active}\n\n1 Month: ${prices['1']:.2f}\n3 Months: ${prices['3']:.2f}\n9 Months: ${prices['9']:.2f}\n12 Months: ${prices['12']:.2f}\n\nUse the Premium Prices button to edit prices.")

@bot.message_handler(func=lambda m: m.text == "💰 PREMIUM PRICES")
def premium_prices_admin(m):
    if not is_admin(m.from_user.id): return
    p=get_premium_prices()
    msg=bot.send_message(m.chat.id, f"💰 Premium prices\n\n1 Month: ${p['1']:.2f}\n3 Months: ${p['3']:.2f}\n9 Months: ${p['9']:.2f}\n12 Months: ${p['12']:.2f}\n\nSend four prices separated by spaces, e.g. 5 12 30 40")
    bot.register_next_step_handler(msg, set_premium_prices_admin)

def set_premium_prices_admin(m):
    if not is_admin(m.from_user.id): return
    try:
        vals=[float(x) for x in (m.text or '').split()]
        if len(vals)!=4 or any(x<0 for x in vals): raise ValueError
        for k,v in zip(["1","3","9","12"],vals): set_setting(f"premium_price_{k}",v)
        bot.send_message(m.chat.id, "✅ Premium prices updated successfully.")
    except Exception:
        bot.send_message(m.chat.id, "❌ Format error. Use: 1 month 3 month 9 month 12 month prices, e.g. 5 12 30 40")

def resolve_user_input(text):
    text=(text or '').strip()
    return text if text in users else find_user_by_botid(text)

def _parse_premium_duration(text):
    """Parse 1sec, 30s, 5min, 2h, 7d, 3mo, 1y into seconds."""
    raw=(text or '').strip().lower().replace('-', ' ')
    m=re.fullmatch(r'(\d+(?:\.\d+)?)\s*(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h|days?|d|weeks?|w|months?|mos?|mo|years?|yrs?|y)', raw)
    if not m: return None
    value=float(m.group(1)); unit=m.group(2)
    mult=1 if unit in {'s','sec','secs','second','seconds'} else 60 if unit in {'m','min','mins','minute','minutes'} else 3600 if unit in {'h','hr','hrs','hour','hours'} else 86400 if unit in {'d','day','days'} else 604800 if unit in {'w','week','weeks'} else 2592000 if unit in {'mo','mos','month','months'} else 31536000
    sec=value*mult
    return max(1,int(sec))

def _premium_duration_text(seconds):
    seconds=int(seconds)
    if seconds%31536000==0: return f"{seconds//31536000} year(s)"
    if seconds%2592000==0: return f"{seconds//2592000} month(s)"
    if seconds%86400==0: return f"{seconds//86400} day(s)"
    if seconds%3600==0: return f"{seconds//3600} hour(s)"
    if seconds%60==0: return f"{seconds//60} minute(s)"
    return f"{seconds} second(s)"

def _grant_premium_seconds(uid, seconds, reason="admin"):
    uid=str(uid); now=datetime.now(timezone.utc)
    old=users.get(uid,{}).get('premium_until')
    try: old_dt=datetime.fromisoformat(str(old).replace('Z','+00:00')) if old else now; old_dt=old_dt if old_dt.tzinfo else old_dt.replace(tzinfo=timezone.utc)
    except Exception: old_dt=now
    until=max(now,old_dt)+timedelta(seconds=int(seconds))
    users[uid]['premium_until']=until.isoformat(); users[uid]['premium_warning_sent']=False; users[uid]['premium_source']='admin'; save_user(uid)
    premium_logs_col.insert_one({'user_id':uid,'seconds':int(seconds),'until':until.isoformat(),'time':now.isoformat(),'type':reason})
    log_activity(uid,'premium_grant',{'seconds':int(seconds),'reason':reason})
    return until

def _notify_admin_premium_grant(uid, seconds, reason="Admin grant"):
    uid=str(uid); until=users[uid].get('premium_until')
    duration=_premium_duration_text(seconds)
    try:
        bot.send_message(int(uid),
            f"🎉 <b>Premium Activated by Admin</b>\n\n"
            f"⏱️ Granted: <b>{html.escape(duration)}</b>\n"
            f"⏰ Expires: <b>{html.escape(premium_until_text(uid))}</b>\n\n"
            f"🌐 <b>{len(premium_platform_names())} Premium/Trial platforms</b>\n"
            "⚡ Priority downloads\n🎥 Higher quality\n▶️ Full YouTube access")
    except Exception as e:
        print("Premium bot notification error:", uid, e)
    u=users.get(uid,{})
    if u.get('email') and u.get('email_verified'):
        try:
            until_dt=datetime.fromisoformat(str(until).replace('Z','+00:00'))
            send_premium_email(uid,'Premium Granted by Admin',duration,0,until_dt)
        except Exception as e:
            print("Premium email notification error:", uid, e)

@bot.message_handler(func=lambda m: m.text == "🔓 OPEN PREMIUM")
def open_premium_start(m):
    if not is_admin(m.from_user.id): return
    msg=bot.send_message(m.chat.id,
        "💎 <b>GIVE PREMIUM</b>\n\nSend <code>USER_ID DURATION</code>.\nExamples:\n<code>123456789 1sec</code>\n<code>123456789 30min</code>\n<code>123456789 5h</code>\n<code>123456789 7d</code>\n<code>123456789 3mo</code>\n<code>123456789 2y</code>")
    bot.register_next_step_handler(msg, open_premium_process)

def open_premium_process(m):
    if not is_admin(m.from_user.id): return
    try:
        parts=(m.text or '').split(maxsplit=1)
        if len(parts)!=2: raise ValueError
        uid=resolve_user_input(parts[0]); seconds=_parse_premium_duration(parts[1])
        if not uid or seconds is None: raise ValueError
        until=_grant_premium_seconds(uid,seconds,"admin_open")
        _notify_admin_premium_grant(uid,seconds,"Admin grant")
        bot.send_message(m.chat.id,f"✅ Premium granted to <code>{uid}</code> for <b>{html.escape(_premium_duration_text(seconds))}</b>.\n⏰ Expires: {html.escape(local_datetime_text(uid, until))}")
    except Exception:
        bot.send_message(m.chat.id,"❌ Format error. Example: <code>123456789 1sec</code> or <code>123456789 7d</code>")

@bot.message_handler(func=lambda m: m.text == "🎁 GIVE PREMIUM ALL")
def give_premium_all_start(m):
    if not is_admin(m.from_user.id): return
    msg=bot.send_message(m.chat.id,"💎 <b>GIVE PREMIUM TO ALL USERS</b>\n\nSend duration, e.g. <code>1sec</code>, <code>30min</code>, <code>1h</code>, <code>7d</code>, <code>1mo</code>, <code>1y</code>.")
    bot.register_next_step_handler(msg,give_premium_all_process)

def give_premium_all_process(m):
    if not is_admin(m.from_user.id): return
    seconds=_parse_premium_duration(m.text or '')
    if seconds is None:
        bot.send_message(m.chat.id,"❌ Invalid duration. Example: <code>30min</code> or <code>7d</code>"); return
    count=0; emails=0
    for uid in list(users.keys()):
        try:
            _grant_premium_seconds(uid,seconds,"admin_give_all")
            _notify_admin_premium_grant(uid,seconds,"Admin give all")
            count+=1
            if users.get(uid,{}).get('email') and users.get(uid,{}).get('email_verified'): emails+=1
        except Exception as e: print('Give premium all error:',uid,e)
    bot.send_message(m.chat.id,f"🎉 <b>PREMIUM GIVEN TO ALL</b>\n\n👥 Users: <b>{count}</b>\n⏱️ Duration: <b>{html.escape(_premium_duration_text(seconds))}</b>\n📧 Verified Gmail notifications: <b>{emails}</b>\n🌐 Platforms: <b>{len(premium_platform_names())}</b>")

@bot.message_handler(func=lambda m: m.text == "🔒 CLOSE PREMIUM")
def close_premium_start(m):
    if not is_admin(m.from_user.id): return
    msg=bot.send_message(m.chat.id,"Send User ID or BOT ID to close Premium.")
    bot.register_next_step_handler(msg, close_premium_process)

def close_premium_process(m):
    if not is_admin(m.from_user.id): return
    uid=resolve_user_input(m.text)
    if not uid: bot.send_message(m.chat.id,"❌ User not found."); return
    users[uid]['premium_until']=None; users[uid]['premium_warning_sent']=False; save_user(uid)
    bot.send_message(m.chat.id,f"🔒 Premium closed for {uid}.")
    try: bot.send_message(int(uid),"🔒 Your Premium has been closed by admin.")
    except Exception: pass

@bot.message_handler(func=lambda m: m.text == "👑 PREMIUM USERS")
def premium_users_admin(m):
    if not is_admin(m.from_user.id): return
    active=[(uid,premium_until_text(uid)) for uid in users if is_premium(uid)]
    if not active: bot.send_message(m.chat.id,"No active Premium users."); return
    text="👑 ACTIVE PREMIUM USERS\n\n"+"\n".join(f"• {uid} — {until}" for uid,until in active[:100])
    bot.send_message(m.chat.id,text)

@bot.message_handler(func=lambda m: m.text == "✏️ EDIT START MESSAGE")
def edit_start_message_admin(m):
    if not is_admin(m.from_user.id): return
    current=get_setting('start_message',START_MESSAGE_DEFAULT)
    msg=bot.send_message(m.chat.id,"✏️ Send the new /start message.\n\nCurrent:\n"+current)
    bot.register_next_step_handler(msg, save_start_message_admin)

def save_start_message_admin(m):
    if not is_admin(m.from_user.id): return
    text=(m.text or '').strip()
    if not text: bot.send_message(m.chat.id,"❌ Message cannot be empty."); return
    set_setting('start_message',text)
    bot.send_message(m.chat.id,"✅ /start message updated.")


# ================= NEW USER FEATURES =================
def activate_pending_trial(uid, chat_id=None):
    uid=str(uid); u=users.get(uid,{})
    if not u.get("trial_pending") or (premium_verification_required() and not user_is_verified(uid)) or not trial_enabled():
        return False
    version=current_trial_version()
    if u.get("trial_version_used") == version:
        u["trial_pending"]=False; save_user(uid); return False
    days=trial_days(); u["trial_pending"]=False; u["trial_pending_version"]=None
    until=grant_premium_days(uid,days,"trial_campaign")
    u["trial_used"]=True; u["trial_version_used"]=version; save_user(uid)
    if chat_id is not None:
        try: bot.send_message(chat_id,f"🎁 <b>{days} DAY PREMIUM TRIAL ACTIVATED!</b>\n\n⏰ Expires: <b>{local_datetime_text(uid, until)}</b>\n\n🌐 <b>17 Premium/Trial Platforms:</b>\n{html.escape(', '.join(premium_platform_names()))}\n\n⚡ Priority downloads\n🎥 Higher quality.",reply_markup=localized_user_menu(uid),parse_mode="HTML")
        except Exception: pass
    send_premium_email(uid,f"Your {days}-Day Premium Trial is Active",0,0,until)
    return True

@bot.callback_query_handler(func=lambda c: c.data == "premium_trial")
def premium_trial_callback(call):
    uid=str(call.from_user.id)
    if not trial_available(uid):
        bot.answer_callback_query(call.id,"❌ Trial is not available right now.",show_alert=True); return
    days=trial_days()
    if premium_verification_required() and not user_is_verified(uid):
        users[uid]["trial_pending"]=True; users[uid]["trial_pending_version"]=current_trial_version(); save_user(uid)
        kb=InlineKeyboardMarkup(); kb.add(InlineKeyboardButton("🔐 VERIFY ACCOUNT",callback_data="start_verify_flow"))
        bot.answer_callback_query(call.id,"Verify once and your trial will activate automatically.",show_alert=True)
        bot.send_message(call.message.chat.id,f"🔐 <b>Verification required</b>\n\nAfter verification, your {days}-Day Premium Trial will activate automatically. You will NOT need to press the trial button again.",reply_markup=kb); return
    users[uid]["trial_pending"]=True; users[uid]["trial_pending_version"]=current_trial_version(); save_user(uid)
    activated=activate_pending_trial(uid,call.message.chat.id)
    bot.answer_callback_query(call.id,"🎁 Trial activated!" if activated else "Please verify first.")

@bot.callback_query_handler(func=lambda c: c.data == "topup_menu")
def topup_menu(call):
    rate=int(get_setting("stars_per_usd",100)); kb=InlineKeyboardMarkup(row_width=2)
    for stars in (100,500,1000,5000): kb.add(InlineKeyboardButton(f"⭐ {stars} Stars = ${stars/rate:.2f}",callback_data=f"topup:{stars}"))
    kb.add(InlineKeyboardButton("✏️ Custom Stars",callback_data="topup_custom")); bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id,f"💳 <b>ADD BALANCE</b>\n\nCurrent rate: <b>{rate} Stars = $1</b>",reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("topup:"))
def topup_pay(call):
    stars=int(call.data.split(":",1)[1]); bot.answer_callback_query(call.id)
    bot.send_invoice(call.message.chat.id,"Add Balance",f"Add {stars} Telegram Stars to your balance.",f"balance_topup:{stars}","", "XTR",[LabeledPrice(label=f"Balance {stars} Stars",amount=stars)])

@bot.callback_query_handler(func=lambda c: c.data == "topup_custom")
def topup_custom(call):
    msg=bot.send_message(call.message.chat.id,"⭐ Send Stars amount:"); bot.register_next_step_handler(msg,topup_custom_step); bot.answer_callback_query(call.id)

def topup_custom_step(m):
    try:
        stars=int((m.text or "").strip());
        if stars<=0: raise ValueError
        bot.send_invoice(m.chat.id,"Add Balance",f"Add {stars} Telegram Stars to your balance.",f"balance_topup:{stars}","", "XTR",[LabeledPrice(label=f"Balance {stars} Stars",amount=stars)])
    except Exception: bot.send_message(m.chat.id,"❌ Invalid Stars amount.")

@bot.pre_checkout_query_handler(func=lambda q: True)
def pre_checkout_all(q):
    try: bot.answer_pre_checkout_query(q.id,ok=True)
    except Exception: pass

@bot.message_handler(func=lambda m: m.text == "🎁 TRIAL PREMIUM")
def admin_trial(m):
    if not is_admin(m.from_user.id): return
    msg=bot.send_message(m.chat.id,"Send User ID/BOT ID and days. Example: 123456789 7"); bot.register_next_step_handler(msg,admin_trial_step)

def admin_trial_step(m):
    if not is_admin(m.from_user.id): return
    try:
        target,days=m.text.split()[:2]; days=int(days); uid=resolve_user_input(target)
        if not uid or days<1 or days>365: raise ValueError
        until=grant_premium_days(uid,days,"admin_trial_renew")
        bot.send_message(m.chat.id,f"✅ {days} Premium day(s) granted to {uid}.")
        bot.send_message(int(uid),f"🎁 <b>Downloader Bot Premium renewed by admin</b>\n\n⏰ Expires: {until.strftime('%Y-%m-%d %H:%M UTC')}")
        send_premium_email(uid,"Downloader Bot Premium Trial Renewed",0,0,until)
    except Exception: bot.send_message(m.chat.id,"❌ Format error. Example: 123456789 7")

# ================= TRIAL / REFERRAL / RATING / USER ADMIN =================

@bot.message_handler(func=lambda m: m.text == "🎁 OPEN TRIAL DAYS")
def admin_open_trial_days(m):
    if not is_admin(m.from_user.id): return
    msg=bot.send_message(m.chat.id,f"🎁 <b>OPEN TRIAL DAYS</b>\n\nCurrent: <b>{trial_days()} day(s)</b>\nStatus: <b>{'OPEN' if trial_enabled() else 'CLOSED'}</b>\n\nSend number of days to open a NEW trial campaign. Example: <code>3</code>")
    bot.register_next_step_handler(msg,admin_open_trial_days_step)

def admin_open_trial_days_step(m):
    if not is_admin(m.from_user.id): return
    try:
        days=int((m.text or '').strip()); version,_=open_trial_campaign(days); notified=0
        for uid in list(users.keys()):
            try:
                bot.send_message(int(uid),f"🎁 <b>New Trial Available!</b>\n\nYou can now use the new <b>{days}-day Premium Trial</b> campaign.",reply_markup=localized_user_menu(uid)); notified+=1
            except Exception: pass
        bot.send_message(m.chat.id,f"✅ New trial campaign opened.\n\n🎁 Trial: <b>{days} day(s)</b>\n🔢 Campaign: <b>#{version}</b>\n🟢 Status: OPEN\n📨 Menu refreshed for <b>{notified}</b> users.")
    except Exception: bot.send_message(m.chat.id,"❌ Invalid days. Enter a whole number from 1 to 3650.")

@bot.message_handler(func=lambda m: m.text == "💵 REFERRAL REWARD")
def admin_referral_reward(m):
    if not is_admin(m.from_user.id): return
    msg=bot.send_message(m.chat.id,f"💵 <b>REFERRAL REWARD</b>\n\nCurrent: <b>${referral_reward_amount():.4f}</b> per direct referral.\n\nSend new USD amount. Example: <code>1</code>")
    bot.register_next_step_handler(msg,admin_referral_reward_step)

def admin_referral_reward_step(m):
    if not is_admin(m.from_user.id): return
    try:
        value=float((m.text or '').strip())
        if value<0 or value>100000: raise ValueError
        set_setting("referral_reward",round(value,8))
        bot.send_message(m.chat.id,f"✅ Referral reward updated to <b>${value:.4f}</b> per direct referral.\n\n📢 Use <b>REFERRAL BROADCAST</b> to notify all users with their own referral link, code and Share button.", parse_mode="HTML", reply_markup=admin_menu())
    except Exception: bot.send_message(m.chat.id,"❌ Invalid amount.")

@bot.message_handler(func=lambda m: m.text == "🔗 NETWORK REFERRAL %")
def admin_network_referral(m):
    if not is_admin(m.from_user.id): return
    msg=bot.send_message(m.chat.id,f"🔗 <b>NETWORK REFERRAL %</b>\n\nCurrent: <b>{referral_network_percent():.4f}%</b> per upstream level.\nExample: <code>0.01</code> = 0.01%.\nThis applies to user balance credits from Stars top-ups and pays the same percentage to each upstream referral level, up to 10 levels.\n\nSend new percentage:")
    bot.register_next_step_handler(msg,admin_network_referral_step)

def admin_network_referral_step(m):
    if not is_admin(m.from_user.id): return
    try:
        pct=float((m.text or '').strip())
        if pct<0 or pct>100: raise ValueError
        set_setting("referral_network_percent",round(pct,8)); bot.send_message(m.chat.id,f"✅ Network referral commission set to <b>{pct:.4f}%</b> per level.")
    except Exception: bot.send_message(m.chat.id,"❌ Invalid percentage. Example: 0.01")

@bot.message_handler(func=lambda m: m.text == "⭐ RATE BOT")
def admin_rate_bot_start(m):
    if not is_admin(m.from_user.id): return
    campaign_id=uuid.uuid4().hex[:10]
    rating_campaigns_col.insert_one({"_id":campaign_id,"created_at":datetime.now(timezone.utc),"created_by":str(m.from_user.id),"status":"sent"})
    kb=InlineKeyboardMarkup(row_width=1)
    for n,label in [(5,"5 Stars"),(4,"4 Stars"),(3,"3 Stars"),(2,"2 Stars"),(1,"1 Star")]:
        kb.add(InlineKeyboardButton(f"{'⭐'*n} {label}",callback_data=f"botrate:{campaign_id}:{n}"))
    text="⭐ <b>Rate Downloader Bot</b>\n\nHow would you rate our service?\n\nPlease choose one rating below. ❤️"
    count=0
    for uid in list(users.keys()):
        try: bot.send_message(int(uid),text,reply_markup=kb); count+=1
        except Exception: pass
    rating_campaigns_col.update_one({"_id":campaign_id},{"$set":{"sent_count":count}})
    bot.send_message(m.chat.id,f"✅ Rating request sent to <b>{count}</b> users.\n🆔 Campaign: <code>{campaign_id}</code>")

@bot.callback_query_handler(func=lambda c: c.data.startswith("botrate:"))
def user_bot_rating(call):
    try:
        _,campaign_id,rating=call.data.split(":",2); rating=int(rating); uid=str(call.from_user.id)
        if rating<1 or rating>5: raise ValueError
        now=datetime.now(timezone.utc); existed=ratings_col.find_one({"campaign_id":campaign_id,"user_id":uid})
        ratings_col.update_one({"campaign_id":campaign_id,"user_id":uid},{"$set":{"rating":rating,"username":call.from_user.username or "","updated_at":now},"$setOnInsert":{"campaign_id":campaign_id,"user_id":uid,"created_at":now}},upsert=True)
        if not existed: rating_campaigns_col.update_one({"_id":campaign_id},{"$inc":{"response_count":1},"$set":{"last_response_at":now}})
        bot.answer_callback_query(call.id,"Thank you For Rate ❤️")
        try: bot.edit_message_text("Thank you For Rate ❤️",call.message.chat.id,call.message.message_id)
        except Exception:
            try: bot.edit_message_reply_markup(call.message.chat.id,call.message.message_id,reply_markup=None)
            except Exception: pass
    except Exception as e:
        print("Rating error:",e)
        try: bot.answer_callback_query(call.id,"❌ Rating failed.",show_alert=True)
        except Exception: pass

@bot.message_handler(func=lambda m: m.text == "📊 RATE STATS")
def admin_rate_stats(m):
    if not is_admin(m.from_user.id): return
    total=ratings_col.count_documents({}); counts={i:ratings_col.count_documents({"rating":i}) for i in range(1,6)}
    avg_row=next(ratings_col.aggregate([{"$group":{"_id":None,"avg":{"$avg":"$rating"}}}]),None) if total else None
    avg=float(avg_row.get("avg",0)) if avg_row else 0.0
    lines=["⭐ <b>RATE BOT STATISTICS</b>","",f"📊 Total Ratings: <b>{total}</b>",f"⭐ Average: <b>{avg:.2f}/5</b>",""]
    for i in range(5,0,-1):
        pct=counts[i]/total*100 if total else 0; lines.append(f"{'⭐'*i} <b>{i} Star</b>: {counts[i]} ({pct:.1f}%)")
    lines.append("\n📨 <b>Recent Rating Campaigns</b>")
    campaigns=list(rating_campaigns_col.find().sort("created_at",-1).limit(10))
    if campaigns:
        for c in campaigns:
            cid=c.get("_id","N/A"); sent=c.get("sent_count",0); responses=ratings_col.count_documents({"campaign_id":cid}); created=c.get("created_at"); ts=created.strftime("%Y-%m-%d %H:%M UTC") if hasattr(created,"strftime") else str(created); lines.append(f"• <code>{cid}</code> — Sent {sent}, Rated {responses} — {ts}")
    else: lines.append("• No campaigns yet.")
    bot.send_message(m.chat.id,"\n".join(lines))

@bot.message_handler(func=lambda m: m.text == "🗑 DELETE DATABASE USER")
def admin_delete_database_user(m):
    if not is_admin(m.from_user.id): return
    msg=bot.send_message(m.chat.id,"🗑 <b>DELETE DATABASE USER</b>\n\nSend Telegram ID or BOT ID.\n\nThe user will be removed until they send /start again.")
    bot.register_next_step_handler(msg,admin_delete_database_user_step)

def admin_delete_database_user_step(m):
    if not is_admin(m.from_user.id): return
    target=(m.text or '').strip(); uid=resolve_user_input(target)
    if not uid: bot.send_message(m.chat.id,"❌ User not found."); return
    try:
        sid=str(uid); users_col.delete_one({"_id":sid}); activity_col.delete_many({"user_id":sid}); ratings_col.delete_many({"user_id":sid}); referral_commissions_col.delete_many({"$or":[{"source_user":sid},{"recipient_user":sid}]}); users.pop(sid,None)
        for d,k in [(verify_pending,int(uid)),(email_verify_pending,sid),(phone_verify_pending,sid),(whatsapp_verify_pending,sid),(premium_pending,sid),(premium_quality_pending,sid),(pending_links,int(uid))]: d.pop(k,None)
        bot.send_message(m.chat.id,f"✅ User <code>{sid}</code> deleted from database.\n\nThey are no longer in the system until they send /start again.")
    except Exception as e: bot.send_message(m.chat.id,f"❌ Delete failed: {e}")

@bot.message_handler(func=lambda m: m.text == "👥 AVAILABLE USERS")
def admin_available_users(m):
    if not is_admin(m.from_user.id): return
    cutoff=datetime.now(timezone.utc)-timedelta(days=2); rows=[]
    for uid,u in users.items():
        dt=parse_seen_time(u.get("last_seen_at"))
        if dt and dt>=cutoff: rows.append((dt,uid,u))
    rows.sort(reverse=True,key=lambda x:x[0])
    lines=["👥 <b>AVAILABLE USERS — LAST 2 DAYS</b>","",f"Total active/interacted: <b>{len(rows)}</b>",""]
    for i,(dt,uid,u) in enumerate(rows[:200],1):
        username=("@"+u.get("username")) if u.get("username") else "No username"; lines.append(f"{i}. 👤 <code>{uid}</code> | {username} | 🤖 {u.get('bot_id','N/A')} | 🕒 {dt.strftime('%Y-%m-%d %H:%M UTC')}")
    if not rows: lines.append("No user interaction recorded in the last 2 days.")
    bot.send_message(m.chat.id,"\n".join(lines))

@bot.message_handler(func=lambda m: m.text == "📨 SEND LANGUAGE")
def admin_send_language(m):
    if not is_admin(m.from_user.id): return
    n=0
    for uid in users:
        try: bot.send_message(int(uid),"🌍 <b>Select language</b>",reply_markup=language_kb("change_lang")); n+=1
        except Exception: pass
    bot.send_message(m.chat.id,f"✅ Language selector sent to {n} users.")

@bot.message_handler(func=lambda m: m.text == "🌍 LANGUAGE STATS")
def language_stats(m):
    if not is_admin(m.from_user.id): return
    total=len(users); lines=["🌍 <b>LANGUAGE STATISTICS</b>",f"Total: {total}"]
    for code,v in LANGUAGES.items():
        n=sum(1 for u in users.values() if u.get("language")==code); lines.append(f"{v['name']}: <b>{n}</b> ({(n/total*100 if total else 0):.1f}%)")
    bot.send_message(m.chat.id,"\n".join(lines))

@bot.message_handler(func=lambda m: m.text == "⚥ SEND GENDER")
def send_gender(m):
    if not is_admin(m.from_user.id): return
    kb=InlineKeyboardMarkup(); kb.row(InlineKeyboardButton("👨 Male",callback_data="gender:male"),InlineKeyboardButton("👩 Female",callback_data="gender:female")); n=0
    for uid,u in users.items():
        if u.get("gender"): continue
        try: bot.send_message(int(uid),"⚥ <b>Select Your Gender</b>",reply_markup=kb); n+=1
        except Exception: pass
    bot.send_message(m.chat.id,f"✅ Gender selector sent to {n} users.")

@bot.callback_query_handler(func=lambda c: c.data.startswith("gender:"))
def gender_select(call):
    uid=str(call.from_user.id); gender=call.data.split(":",1)[1]
    if gender not in ("male","female"): return
    users[uid]["gender"]=gender; save_user(uid); log_activity(uid,"gender_selected",{"gender":gender}); bot.answer_callback_query(call.id,"✅ Saved")
    try: bot.edit_message_text(f"✅ Gender saved: {gender.title()}",call.message.chat.id,call.message.message_id)
    except Exception: pass

@bot.message_handler(func=lambda m: m.text == "📊 GENDER STATS")
def gender_stats(m):
    if not is_admin(m.from_user.id): return
    male=sum(1 for u in users.values() if u.get("gender")=="male"); female=sum(1 for u in users.values() if u.get("gender")=="female"); total=male+female; unknown=len(users)-total
    bot.send_message(m.chat.id,f"⚥ <b>GENDER STATISTICS</b>\n\n👨 Male: <b>{male}</b> ({male/total*100 if total else 0:.1f}%)\n👩 Female: <b>{female}</b> ({female/total*100 if total else 0:.1f}%)\n❓ Not selected: <b>{unknown}</b>")

@bot.message_handler(func=lambda m: m.text == "🏙 SEND CITY")
def send_city_start(m):
    if not is_admin(m.from_user.id): return
    msg=bot.send_message(m.chat.id,"🏙 Send up to 50 cities/countries, one per line."); bot.register_next_step_handler(msg,save_city_list)

def save_city_list(m):
    if not is_admin(m.from_user.id): return
    opts=list(dict.fromkeys([x.strip() for x in (m.text or "").splitlines() if x.strip()]))[:50]
    if not opts: bot.send_message(m.chat.id,"❌ No cities received."); return
    set_setting("city_options",opts); bot.send_message(m.chat.id,f"✅ Saved {len(opts)} locations. Sending selector..."); send_city_selector()

def send_city_selector():
    opts=get_setting("city_options",[]); kb=InlineKeyboardMarkup(row_width=2)
    for i,name in enumerate(opts): kb.add(InlineKeyboardButton(name[:50],callback_data=f"city:{i}"))
    n=0
    for uid,u in users.items():
        if u.get("city"): continue
        try: bot.send_message(int(uid),"🏙 <b>Select your city / country</b>",reply_markup=kb); n+=1
        except Exception: pass
    return n

@bot.callback_query_handler(func=lambda c: c.data.startswith("city:"))
def city_select(call):
    uid=str(call.from_user.id); idx=int(call.data.split(":",1)[1]); opts=get_setting("city_options",[])
    if idx>=len(opts): return
    users[uid]["city"]=opts[idx]; save_user(uid); log_activity(uid,"city_selected",{"city":opts[idx]}); bot.answer_callback_query(call.id,"✅ Saved")
    try: bot.edit_message_text(f"✅ Location saved: <b>{html.escape(opts[idx])}</b>",call.message.chat.id,call.message.message_id)
    except Exception: pass

@bot.message_handler(func=lambda m: m.text == "📊 CITY STATS")
def city_stats(m):
    if not is_admin(m.from_user.id): return
    from collections import Counter
    c=Counter(u.get("city") for u in users.values() if u.get("city")); total=len(users); lines=["🏙 <b>CITY / COUNTRY STATISTICS</b>",""]
    for city,n in c.most_common(50): lines.append(f"• {html.escape(city)}: <b>{n}</b> ({n/total*100 if total else 0:.1f}%)")
    if not c: lines.append("No city data yet.")
    bot.send_message(m.chat.id,"\n".join(lines))

@bot.message_handler(func=lambda m: m.text == "💱 CHANGE MONEY")
def change_money(m):
    if not is_admin(m.from_user.id): return
    msg=bot.send_message(m.chat.id,"💱 <b>Exchange-rate override</b> — use this only when you want to pin a manual rate.\nExample: ETB=188 EUR=0.85 JPY=147 KRW=1380\n\nIf no manual override exists, the bot uses the live USD market rate."); bot.register_next_step_handler(msg,change_money_step)

def change_money_step(m):
    if not is_admin(m.from_user.id): return
    changed=0
    for part in (m.text or "").replace(","," ").split():
        if "=" not in part: continue
        code,val=part.split("=",1)
        try: val=float(val); set_setting("fx_"+code.upper(),val); changed+=1
        except Exception: pass
    bot.send_message(m.chat.id,f"✅ Updated {changed} exchange rate(s).")

@bot.message_handler(func=lambda m: m.text == "👥 CURRENCY USERS")
def admin_currency_users(m):
    if not is_admin(m.from_user.id): return
    rows=[]
    for uid,u in users.items():
        rows.append(f"• {uid}: {cur_code(uid)} — 1 USD = {fx_rate(uid):,.4f} {cur_code(uid)}")
    text="💱 <b>USER CURRENCIES</b>\n\n"+"\n".join(rows[:200])
    bot.send_message(m.chat.id,text if rows else "No users yet.")

@bot.message_handler(func=lambda m: m.text == "📊 MARKET STATUS")
def admin_market_status(m):
    if not is_admin(m.from_user.id): return
    refresh_market_rates(force=False)
    lines=["🌍 <b>GLOBAL MARKET RATE STATUS</b>",""]
    fiat=FX_CACHE.get("fiat",{}); crypto=FX_CACHE.get("crypto",{})
    lines.append(f"💵 Fiat source: <b>{FX_CACHE.get('sources',{}).get('fiat','N/A')}</b>")
    lines.append(f"🪙 Crypto source: <b>{FX_CACHE.get('sources',{}).get('crypto','N/A')}</b>")
    lines.append(f"🕒 Fiat updated: <b>{datetime.fromtimestamp(fiat.get('time',0),timezone.utc).strftime('%Y-%m-%d %H:%M UTC') if fiat.get('time') else 'N/A'}</b>")
    lines.append(f"🕒 Crypto updated: <b>{datetime.fromtimestamp(crypto.get('time',0),timezone.utc).strftime('%Y-%m-%d %H:%M UTC') if crypto.get('time') else 'N/A'}</b>")
    lines.append("")
    for code in ("ETB","SOS","EUR","BTC","ETH","USDT","BNB","SOL","XRP","USDC","ADA","DOGE","TRX"):
        lines.append(f"• <b>{code}</b>: 1 USD = {market_rate_text(code)} {code}")
    lines.append("\n⚙️ Admin manual override still has priority over live market data.")
    bot.send_message(m.chat.id,"\n".join(lines))

@bot.message_handler(func=lambda m: m.text == "📊 CURRENCY STATS")
def currency_stats(m):
    if not is_admin(m.from_user.id): return
    from collections import Counter
    c=Counter(cur_code(uid) for uid in users)
    lines=["💱 <b>CURRENCY STATISTICS</b>",""]
    for code,n in c.most_common(): lines.append(f"• {code}: <b>{n}</b>")
    bot.send_message(m.chat.id,"\n".join(lines))

@bot.message_handler(func=lambda m: m.text == "⭐ STARS SETTINGS")
def stars_settings(m):
    if not is_admin(m.from_user.id): return
    current=get_setting("stars_per_usd",100); msg=bot.send_message(m.chat.id,f"⭐ Current: {current} Telegram Stars = $1\nSend new rate:"); bot.register_next_step_handler(msg,stars_settings_step)

def stars_settings_step(m):
    if not is_admin(m.from_user.id): return
    try:
        rate=int(m.text.strip()); assert rate>0; set_setting("stars_per_usd",rate); bot.send_message(m.chat.id,f"✅ {rate} Stars = $1")
    except Exception: bot.send_message(m.chat.id,"❌ Invalid rate.")

@bot.message_handler(func=lambda m: m.text == "💱 CHANGE CURRENCY")
def change_currency_button(m):
    uid=str(m.from_user.id)
    if balance_is_locked(uid):
        bot.send_message(m.chat.id,balance_locked_message(uid),reply_markup=localized_user_menu(uid)); return
    if bot_locked_guard(m) or banned_guard(m): return
    if not crypto_system_open():
        bot.send_message(m.chat.id,"⚠️ <b>This Version is Not Available Now!</b>\n\nCrypto/Currency exchange is currently closed by admin.",reply_markup=localized_user_menu(uid)); return
    allowed,remaining,minimum=crypto_access_status(uid)
    if not allowed:
        kb=InlineKeyboardMarkup(); kb.add(InlineKeyboardButton("📜 HISTORY",callback_data="profile_history"))
        bot.send_message(m.chat.id,f"🪙 <b>Crypto is not available for your account yet.</b>\n\nYour total deposited/credited amount: <b>${total_account_deposits_usd(uid):,.2f}</b>\nMinimum required by admin: <b>${minimum:,.2f}</b>\nAmount remaining: <b>${remaining:,.2f}</b>\n\nPlease add more balance, then try Crypto again. Check your account history below.",reply_markup=kb); return
    refresh_market_rates(False)
    minimum=float(get_setting("currency_change_min_usd",5.0) or 0)
    assets=wallet_asset_options(uid)
    if len(assets)<1:
        bot.send_message(m.chat.id,"❌ You have no available funds to convert.",reply_markup=localized_user_menu(uid)); return
    lines=["💱 <b>CHANGE CURRENCY</b>","","Choose the currency you want to convert <b>FROM</b>:",f"Minimum conversion: <b>${minimum:,.2f} USD</b>","", "You choose both FROM and TO. Only the amount you enter is converted."]
    bot.send_message(m.chat.id,"\n".join(lines),reply_markup=currency_source_kb(uid))

@bot.callback_query_handler(func=lambda c:c.data=="currency_refresh")
def currency_refresh_callback(call):
    try:
        refresh_market_rates(True); bot.answer_callback_query(call.id,"✅ Market rates updated")
        uid=str(call.from_user.id)
        bot.send_message(call.message.chat.id,"📊 <b>Market updated.</b>\n\nChoose the currency you want to convert <b>FROM</b>:",reply_markup=currency_source_kb(uid))
    except Exception:
        bot.answer_callback_query(call.id,"❌ Market update failed.",show_alert=True)

def held_asset_amount(uid, code):
    """Amount of a specific asset currently locked by an active 1H crypto hold."""
    now=datetime.now(timezone.utc); total=0.0
    try:
        for h in conversion_holds_col.find({"user_id":str(uid),"status":"hold","to_asset":code}):
            exp=parse_seen_time(h.get("expires_at"))
            if exp and exp>now:
                total += float(h.get("to_amount",0) or 0)
    except Exception:
        pass
    return max(0.0,total)

def wallet_asset_options(uid):
    """Return (kind, code, amount) for every spendable wallet holding."""
    out=[]; u=users.get(str(uid),{}); cur=cur_code(uid); amt=available_asset_amount(uid)
    if amt>1e-12:
        spendable=max(0.0, amt-held_asset_amount(uid,cur))
        if spendable>1e-12: out.append(("current",cur,spendable))
    for code,a in get_portfolio(uid).items():
        a=float(a or 0)
        if a>1e-12 and code in AVAILABLE_CURRENCIES:
            spendable=max(0.0,a-held_asset_amount(uid,code))
            if spendable>1e-12: out.append(("portfolio",code,spendable))
    return out

def wallet_label(kind,code,amount):
    icon=(FIAT_CURRENCIES.get(code) or CRYPTO_CURRENCIES.get(code) or ("💰",code,""))[0]
    where="BALANCE" if kind=="current" else "PORTFOLIO"
    return f"{icon} {code} • {format_asset(code,amount)} ({where})"

def currency_source_kb(uid):
    kb=InlineKeyboardMarkup(row_width=1)
    for kind,code,amount in wallet_asset_options(uid):
        kb.add(InlineKeyboardButton(wallet_label(kind,code,amount),callback_data=f"currency_from:{kind}:{code}"))
    kb.add(InlineKeyboardButton("🔄 UPDATE MARKET",callback_data="currency_refresh"))
    return kb

def currency_target_kb(source_code):
    kb=InlineKeyboardMarkup(row_width=2); btn=[]
    for code,(flag,_,_) in FIAT_CURRENCIES.items():
        if code!=source_code: btn.append(InlineKeyboardButton(f"{flag} {code}",callback_data=f"currency_to:{code}"))
    if crypto_system_open():
        for code,(icon,_,_) in CRYPTO_CURRENCIES.items():
            if code!=source_code: btn.append(InlineKeyboardButton(f"{icon} {code}",callback_data=f"currency_to:{code}"))
    for i in range(0,len(btn),2): kb.row(*btn[i:i+2])
    kb.add(InlineKeyboardButton("🔙 CHOOSE FROM",callback_data="currency_back_sources"))
    return kb

@bot.callback_query_handler(func=lambda c:c.data=="currency_back_sources")
def currency_back_sources_callback(call):
    bot.answer_callback_query(call.id); bot.send_message(call.message.chat.id,"Choose the currency you want to convert <b>FROM</b>:",reply_markup=currency_source_kb(str(call.from_user.id)))

@bot.callback_query_handler(func=lambda c:c.data.startswith("currency_from:"))
def currency_source_callback(call):
    uid=str(call.from_user.id); parts=call.data.split(":")
    if len(parts)!=3: return
    kind,code=parts[1],parts[2]
    if not any(k==kind and c==code and a>1e-12 for k,c,a in wallet_asset_options(uid)):
        bot.answer_callback_query(call.id,"❌ This balance is no longer available.",show_alert=True); return
    users[uid]["pending_conversion_amount"]={"from_type":kind,"from":code}
    save_user(uid)
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id,f"📤 <b>FROM:</b> {format_asset(code,dict(((k,c),a) for k,c,a in wallet_asset_options(uid)).get((kind,code),0))}\n\nNow choose the currency you want to convert <b>TO</b>:",reply_markup=currency_target_kb(code))

@bot.callback_query_handler(func=lambda c:c.data.startswith("currency_to:"))
def currency_target_callback(call):
    uid=str(call.from_user.id); new=call.data.split(":",1)[1]; p=users.get(uid,{}).get("pending_conversion_amount") or {}
    old=p.get("from")
    if not old:
        bot.answer_callback_query(call.id,"Choose FROM currency first.",show_alert=True); return
    if new not in AVAILABLE_CURRENCIES or new==old:
        bot.answer_callback_query(call.id,"❌ Invalid target currency.",show_alert=True); return
    if new in CRYPTO_CURRENCIES:
        if not crypto_system_open():
            bot.answer_callback_query(call.id,"This Version is Not Available Now!",show_alert=True); return
        allowed,remaining,minimum=crypto_access_status(uid)
        if not allowed:
            bot.answer_callback_query(call.id,f"Crypto requires ${minimum:,.2f} total deposited. You need ${remaining:,.2f} more.",show_alert=True); return
    refresh_market_rates(False)
    if asset_usd_price(old)<=0 or asset_usd_price(new)<=0:
        bot.answer_callback_query(call.id,"❌ Live market price unavailable.",show_alert=True); return
    users[uid]["pending_conversion_amount"]["to"]=new; save_user(uid)
    msg=bot.send_message(call.message.chat.id,f"💱 <b>{old} → {new}</b>\n\n✍️ Enter the amount in <b>{old}</b> you want to convert.\n\nMinimum: <b>${float(get_setting('currency_change_min_usd',5.0) or 0):,.2f} USD</b>\nExample: <code>5</code>",reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("❌ CANCEL CONVERSION"))
    bot.answer_callback_query(call.id); bot.register_next_step_handler(msg,conversion_amount_step)

def conversion_amount_step(m):
    uid=str(m.from_user.id); p=users.get(uid,{}).get("pending_conversion_amount") or {}
    if not p: return
    if (m.text or '').strip()=="❌ CANCEL CONVERSION":
        users[uid].pop("pending_conversion_amount",None); save_user(uid); bot.send_message(m.chat.id,"❌ Conversion cancelled.",reply_markup=localized_user_menu(uid)); return
    try: amount=float((m.text or '').replace(',','').strip())
    except Exception: amount=-1
    if amount<=0:
        msg=bot.send_message(m.chat.id,"❌ Invalid amount. Send a positive number, e.g. <code>5</code>."); bot.register_next_step_handler(msg,conversion_amount_step); return
    old=p.get("from"); new=p.get("to"); kind=p.get("from_type")
    available=0.0
    if kind=="current":
        available=available_asset_amount(uid)
    else:
        available=max(0.0,float(get_portfolio(uid).get(old,0) or 0)-held_asset_amount(uid,old))
    if amount>available+1e-12:
        msg=bot.send_message(m.chat.id,f"❌ Insufficient {old} balance. Available: <b>{format_asset(old,available)}</b>. Send a smaller amount."); bot.register_next_step_handler(msg,conversion_amount_step); return
    gross=asset_to_usd(old,amount); minimum=float(get_setting("currency_change_min_usd",5.0) or 0)
    if minimum>0 and gross<minimum:
        msg=bot.send_message(m.chat.id,f"❌ Minimum is <b>${minimum:,.2f} USD</b>. Your amount is <b>${gross:,.2f}</b>."); bot.register_next_step_handler(msg,conversion_amount_step); return
    network_code=old if is_crypto(old) else new
    fee,gas,total=crypto_fee_usd(gross,network_code); net=max(0.0,gross-total); new_amt=usd_to_asset(new,net)
    if net<=0 or new_amt<=0:
        bot.send_message(m.chat.id,"❌ Amount is too small after fee/gas.",reply_markup=localized_user_menu(uid)); return
    nonce=uuid.uuid4().hex[:12]
    users[uid]["pending_conversion"]={"nonce":nonce,"from_type":kind,"from":old,"to":new,"amount":amount,"gross_usd":gross,"fee_usd":fee,"gas_usd":gas,"net_usd":net,"new_amount":new_amt,"created_at":datetime.now(timezone.utc).isoformat()}
    users[uid].pop("pending_conversion_amount",None); save_user(uid)
    kb=InlineKeyboardMarkup(row_width=2); kb.add(InlineKeyboardButton("✅ CONFIRM",callback_data=f"convert_confirm:{nonce}"),InlineKeyboardButton("❌ CANCEL",callback_data=f"convert_cancel:{nonce}"))
    bot.send_message(m.chat.id,f"🧾 <b>CONVERSION PREVIEW</b>\n\n📤 From: <b>{format_asset(old,amount)}</b>\n💵 Gross value: <b>${gross:,.2f}</b>\n📥 To: <b>{new}</b>\n📊 Live rate: <b>{market_rate_text(new)}</b>\n💰 You receive: <b>{format_asset(new,new_amt)}</b>\n\n💸 Fee ({crypto_fee_percent():.4f}%): <b>-${fee:,.2f}</b>\n⛽ Network/Gas fee: <b>-${gas:,.2f}</b>\n💰 Total fees: <b>-${total:,.2f}</b>\n\n⚠️ The rate is refreshed again at confirmation.\nPress <b>CONFIRM</b> to execute.",reply_markup=kb)

@bot.callback_query_handler(func=lambda c:c.data.startswith("convert_cancel:"))
def convert_cancel_callback(call):
    uid=str(call.from_user.id); nonce=call.data.split(":",1)[1]
    if users.get(uid,{}).get("pending_conversion",{}).get("nonce")!=nonce: bot.answer_callback_query(call.id,"Expired",show_alert=True); return
    users[uid].pop("pending_conversion",None); save_user(uid)
    try: bot.delete_message(call.message.chat.id,call.message.message_id)
    except: pass
    bot.answer_callback_query(call.id,"Cancelled"); bot.send_message(call.message.chat.id,"❌ Conversion cancelled.",reply_markup=localized_user_menu(uid))

@bot.callback_query_handler(func=lambda c:c.data.startswith("convert_confirm:"))
def convert_confirm_callback(call):
    uid=str(call.from_user.id); nonce=call.data.split(":",1)[1]; p=users.get(uid,{}).get("pending_conversion") or {}
    if p.get("nonce")!=nonce: bot.answer_callback_query(call.id,"Expired conversion",show_alert=True); return
    with CRYPTO_TX_LOCK:
        if not crypto_system_open():
            users[uid].pop("pending_conversion",None); save_user(uid); bot.answer_callback_query(call.id,"Currency exchange is currently closed.",show_alert=True); return
        old=p.get("from"); new=p.get("to"); kind=p.get("from_type"); amount=float(p.get("amount",0));
        available=available_asset_amount(uid) if kind=="current" else max(0.0,float(get_portfolio(uid).get(old,0) or 0)-held_asset_amount(uid,old))
        if not old or not new or amount<=0 or amount>available+1e-12:
            users[uid].pop("pending_conversion",None); save_user(uid); bot.answer_callback_query(call.id,"Balance changed. Start again.",show_alert=True); return
        refresh_market_rates(True); gross=asset_to_usd(old,amount); network_code=old if is_crypto(old) else new
        fee,gas,total=crypto_fee_usd(gross,network_code); net=gross-total; new_amt=usd_to_asset(new,net)
        minimum=float(get_setting("currency_change_min_usd",5.0) or 0)
        if (minimum>0 and gross<minimum) or net<=0 or new_amt<=0:
            bot.answer_callback_query(call.id,"Conversion is no longer valid at the current rate.",show_alert=True); return
        # Debit the exact selected source amount.
        if kind=="current":
            users[uid]["balance"]=round(max(0.0,balance_amount(uid)-amount),12)
        else:
            pfolio=get_portfolio(uid); pfolio[old]=round(max(0.0,float(pfolio.get(old,0))-amount),12); users[uid]["portfolio"]=pfolio
        # Credit the target without overwriting any other holding.
        if new==cur_code(uid):
            users[uid]["balance"]=round(balance_amount(uid)+new_amt,12)
        else:
            add_portfolio_asset(uid,new,new_amt)
        save_user(uid)
        now=datetime.now(timezone.utc)
        balance_ledger_col.insert_one({"user_id":uid,"type":"conversion","from_asset":old,"from_amount":amount,"to_asset":new,"to_amount":new_amt,"gross_usd":gross,"fee_usd":fee,"gas_fee_usd":gas,"net_usd":net,"source":"currency_conversion","time":now})
        if fee>0 or gas>0: record_crypto_fee(uid,old,new,gross,fee,gas,amount,net)
        hold_txt=""
        if crypto_hold_open() and (is_crypto(old) or is_crypto(new)):
            exp=now+timedelta(hours=1)
            conversion_holds_col.insert_one({"user_id":uid,"status":"hold","usd_amount":net,"from_asset":old,"from_amount":amount,"to_asset":new,"to_amount":new_amt,"created_at":now,"expires_at":exp,"source":"crypto_conversion"})
            hold_txt=f"\n🔒 <b>Amount on Hold:</b> ${net:,.2f} USD for 1 hour"
        users[uid].pop("pending_conversion",None); save_user(uid)
    try: bot.delete_message(call.message.chat.id,call.message.message_id)
    except: pass
    bot.answer_callback_query(call.id,"✅ Conversion completed")
    bot.send_message(call.message.chat.id,f"✅ <b>CONVERSION COMPLETE</b>\n\n📤 Used: <b>{format_asset(old,amount)}</b>\n📥 Received: <b>{format_asset(new,new_amt)}</b>\n💸 Fee: <b>${fee:,.2f}</b>\n⛽ Gas fee: <b>${gas:,.2f}</b>\n💵 Net value: <b>${net:,.2f} USD</b>{hold_txt}\n\nOnly the amount you selected was converted. All other holdings remain untouched.",reply_markup=localized_user_menu(uid))


@bot.message_handler(func=lambda m: m.text in ["📜 HISTORY"] + [v.get("history","") for v in MAIN_LABELS.values()])
def history_button(m):
    uid=str(m.from_user.id); rows=list(activity_col.find({"user_id":uid}).sort("time",-1).limit(20)); lines=["📜 <b>YOUR HISTORY</b>",""]
    for r in rows:
        t=r.get("time"); ts=t.strftime("%Y-%m-%d %H:%M") if hasattr(t,"strftime") else str(t); lines.append(f"• {str(r.get('action','event')).replace('_',' ').title()} — {ts}")
    if not rows: lines.append("No history yet.")
    bot.send_message(m.chat.id,"\n".join(lines))

@bot.message_handler(func=lambda m: m.text in [v.get("lang","") for v in MAIN_LABELS.values()])
def language_button(m):
    bot.send_message(m.chat.id,"🌍 <b>Select your language</b>",reply_markup=language_kb("change_lang"))

@bot.message_handler(func=lambda m: m.text in [v.get("topup","") for v in MAIN_LABELS.values()])
def localized_topup_button(m):
    # Reuse the callback UI directly for localized users.
    rate=int(get_setting("stars_per_usd",100)); kb=InlineKeyboardMarkup(row_width=2)
    for stars in (100,500,1000,5000): kb.add(InlineKeyboardButton(f"⭐ {stars} Stars = ${stars/rate:.2f}",callback_data=f"topup:{stars}"))
    kb.add(InlineKeyboardButton("✏️ Custom Stars",callback_data="topup_custom")); bot.send_message(m.chat.id,f"💳 <b>ADD BALANCE</b>\n\n{rate} Stars = $1",reply_markup=kb)

# Localized main actions.
_ACTIONS={}
for _lang,_d in MAIN_LABELS.items():
    for _key,_label in _d.items(): _ACTIONS[_label]=_key

@bot.message_handler(func=lambda m: bool(m.text and m.text in _ACTIONS))
def localized_action_dispatch(m):
    touch_user(m.from_user.id)
    action=_ACTIONS[m.text]; uid=str(m.from_user.id)
    if action in ("history","lang","topup"): return
    if action=="balance": return balance_handler(m)
    if action=="withdraw": return withdraw_menu(m)
    if action=="ref": return refer_cmd(m)
    if action=="id": return get_id_handler(m)
    if action=="premium": return premium_button(m)
    if action=="music": return music_menu_button(m)
    if action=="profile": return profile_handler(m)
    if action=="customer": return customer_handler(m)
    if action=="ai": return customer_ai_handler(m)
    if action=="promo": return promo_user_menu(m)
    if action=="trial":
        if not trial_available(uid):
            bot.send_message(m.chat.id,"❌ Trial is not available right now."); return
        days=trial_days()
        if premium_verification_required() and not user_is_verified(uid):
            users[uid]["trial_pending"]=True; users[uid]["trial_pending_version"]=current_trial_version(); save_user(uid)
            kb=InlineKeyboardMarkup(); kb.add(InlineKeyboardButton("🔐 VERIFY ACCOUNT",callback_data="start_verify_flow"))
            bot.send_message(m.chat.id,f"🔐 <b>Verification required</b>\n\nVerify once and your {days}-Day Premium Trial will activate automatically. You will NOT need to press the trial button again.",reply_markup=kb); return
        users[uid]["trial_pending"]=True; users[uid]["trial_pending_version"]=current_trial_version(); save_user(uid); activate_pending_trial(uid,m.chat.id)

# ================= MAIN RUN LOOP =================

if __name__ == "__main__":
    threading.Thread(target=premium_expiry_worker, daemon=True).start()
    threading.Thread(target=market_refresh_worker, daemon=True).start()
    threading.Thread(target=conversion_hold_worker, daemon=True).start()
    threading.Thread(target=balance_lock_worker, daemon=True).start()
    threading.Thread(target=streak_worker, daemon=True).start()
    try: refresh_market_rates(force=True)
    except Exception as e: print("Initial market refresh failed:", e)
    try: migrate_legacy_ledger_once()
    except Exception as e: print("Ledger migration warning:", e)
    print("🤖 Bot 1 and Bot 2 are starting...")
    print(f"🟢 WaForge WhatsApp configured: {bool(WAFORGE_API_KEY)} | D7 SMS configured: {bool(D7_TOKEN)}")
    print("📦 Telegram upload limits: Admin-controlled FREE/TRIAL/PREMIUM values stored in MongoDB")
    
    def run_bot2():
        try:
            bot2.infinity_polling(skip_pending=True)
        except Exception as e:
            print(f"Bot 2 Error: {e}")
            
    threading.Thread(target=run_bot2, daemon=True).start()

    if customer_ai_bot:
        def run_customer_ai_bot():
            try:
                print("🤖 Dedicated Customer AI bot is starting...")
                customer_ai_bot.infinity_polling(skip_pending=True)
            except Exception as e:
                print(f"Customer AI Bot Error: {e}")
        threading.Thread(target=run_customer_ai_bot, daemon=True).start()
    else:
        print("⚠️ CUSTOMER_AI_BOT_TOKEN is not configured; dedicated Customer AI bot is disabled.")
    
    try:
        bot.infinity_polling(skip_pending=True)
    except Exception as e:
        print(f"Bot 1 Error: {e}")
