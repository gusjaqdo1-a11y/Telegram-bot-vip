from flask import Flask, request, send_file, session, redirect, url_for, render_template_string, Response
import yt_dlp
import os
import uuid
import html
import urllib.parse
import requests

app = Flask(__name__)
from datetime import timedelta
app.permanent_session_lifetime=timedelta(days=365)
app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SECURE=True,SESSION_COOKIE_SAMESITE="Lax",SESSION_COOKIE_NAME="quickdl_creator_session",SESSION_COOKIE_PATH="/")
os.makedirs("downloads", exist_ok=True)

@app.route("/download", methods=["GET"])
def download():

    url = request.args.get("url")
    filename = f"downloads/{uuid.uuid4()}.mp4"

    ydl_opts = {
        "outtmpl": filename,
        "format": "best",
        "merge_output_format": "mp4",
        "quiet": True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    return send_file(filename, as_attachment=True)


# ================= CREATOR DASHBOARD =================
# This dashboard is intentionally small and isolated from the existing
# downloader endpoint above. It does not change /download behavior.
import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from functools import wraps

from pymongo import MongoClient
from cryptography.fernet import Fernet

DASHBOARD_BASE_URL = os.getenv("DASHBOARD_BASE_URL", "https://go.quickdl.site").rstrip("/")
DASHBOARD_SESSION_SECRET = os.getenv(
    "DASHBOARD_SESSION_SECRET",
    hashlib.sha256((os.getenv("BOT_TOKEN", "") + ":creator-dashboard").encode()).hexdigest(),
)
app.secret_key = DASHBOARD_SESSION_SECRET

_dash_mongo = MongoClient(os.getenv("MONGO_URI_1", os.getenv("MONGO_URI", "mongodb://localhost:27017/user_db")))
try:
    _dash_db = _dash_mongo.get_default_database()
except Exception:
    _dash_db = _dash_mongo["user_db"]
_dash_bots = _dash_db["managed_bots"]
_dash_users = _dash_db["users"]

_CREATOR_BOT_TOKEN = os.getenv("CREATOR_BOT_TOKEN", "").strip()
_MANAGED_TOKEN_KEY = os.getenv("MANAGED_TOKEN_ENCRYPTION_KEY", "").strip()


def _dash_pin_hash(pin):
    return hashlib.sha256(str(pin).encode("utf-8")).hexdigest()


def _dash_make_pin():
    return str(secrets.randbelow(900000) + 100000)


def _dash_pin_ok(stored, supplied):
    try:
        return hmac.compare_digest(str(stored or ""), _dash_pin_hash(str(supplied or "")))
    except Exception:
        return False


def _dash_premium(doc):
    try:
        until=doc.get("premium_until")
        if not until:
            return False
        if isinstance(until, datetime):
            dt=until
        else:
            dt=datetime.fromisoformat(str(until).replace("Z","+00:00"))
        if dt.tzinfo is None:
            dt=dt.replace(tzinfo=timezone.utc)
        return dt > datetime.now(timezone.utc)
    except Exception:
        return False


def _dash_token(doc):
    enc=str(doc.get("token_enc") or "").strip()
    if not enc:
        return str(doc.get("token") or "").strip()
    if _MANAGED_TOKEN_KEY:
        try:
            return Fernet(_MANAGED_TOKEN_KEY.encode()).decrypt(enc.encode()).decode()
        except Exception:
            pass
    # Legacy installations may have stored an unencrypted token.
    return enc


def _dash_bot_api(token, method, payload=None, timeout=20):
    try:
        r=requests.post(f"https://api.telegram.org/bot{token}/{method}",json=payload or {},timeout=timeout)
        data=r.json()
        if data.get("ok"):
            return data.get("result"), None
        return None, str(data.get("description") or f"{method} failed")
    except Exception as e:
        return None, str(e)


def _dash_creator_api(method, payload=None, timeout=20):
    if not _CREATOR_BOT_TOKEN:
        return None, "CREATOR_BOT_TOKEN is not configured"
    try:
        r=requests.post(f"https://api.telegram.org/bot{_CREATOR_BOT_TOKEN}/{method}",json=payload or {},timeout=timeout)
        data=r.json()
        if data.get("ok"):
            return data.get("result"), None
        return None, str(data.get("description") or f"{method} failed")
    except Exception as e:
        return None, str(e)


def _dash_remember_value(bot_id, expires_at=None):
    bid=str(bot_id)
    exp=int(expires_at or (datetime.now(timezone.utc).timestamp()+31536000))
    raw=f"{bid}|{exp}"
    sig=hmac.new(DASHBOARD_SESSION_SECRET.encode(),raw.encode(),hashlib.sha256).hexdigest()
    return f"{raw}|{sig}"

def _dash_remember_valid(bot_id,value):
    try:
        parts=str(value or "").split("|")
        if len(parts)!=3 or parts[0]!=str(bot_id): return False
        exp=int(parts[1])
        if exp<int(datetime.now(timezone.utc).timestamp()): return False
        expected=_dash_remember_value(bot_id,exp)
        return hmac.compare_digest(str(value),expected)
    except Exception:
        return False

def _dash_resolve_doc(dashboard_id):
    """Resolve dashboard IDs stored by either legacy string or Telegram integer fields."""
    key=str(dashboard_id or "").strip()
    if not key:
        return None

    # Telegram IDs are commonly stored as integers in MongoDB, while some
    # older Creator records stored them as strings. Accept both forms so a
    # valid dashboard link never becomes a false 404 just because of BSON type.
    candidates=[key]
    try:
        candidates.append(int(key))
    except (TypeError, ValueError):
        pass

    doc=_dash_bots.find_one({"bot_id":{"$in":candidates}})
    if doc:
        return doc

    # Older Creator messages sometimes used the owner's Telegram ID in the
    # dashboard URL. Resolve that legacy form only when exactly one bot belongs
    # to the owner, avoiding an ambiguous dashboard selection.
    rows=list(_dash_bots.find({"owner_id":{"$in":candidates}}).sort("created_at",-1).limit(2))
    if len(rows)==1:
        return rows[0]
    return None

def _dash_unavailable_page(dashboard_id):
    key=html.escape(str(dashboard_id or ""),quote=True)
    creator_username=html.escape(str(os.getenv("CREATOR_BOT_USERNAME","")).strip().lstrip("@"),quote=True)
    creator_link=(f'<a class="btn" href="https://t.me/{creator_username}">🤖 Open Creator Bot</a>' if creator_username else "")
    page=_dash_page("Dashboard unavailable",f"""<div class="wrap unavailable-shell">
      <div class="glass unavailable">
        <div class="unavailable-icon">◈</div>
        <div class="eyebrow">QUICKDL • CREATOR</div>
        <h1>Dashboard link needs attention</h1>
        <p class="muted">The web service is online, but no active Creator Bot record matches <code>{key}</code>.</p>
        <div class="notice">If this is a newly created bot, open <b>My Bots</b> in Creator Bot and use the fresh Dashboard link. If the bot was deleted, its dashboard is intentionally disabled.</div>
        <div class="actions">{creator_link}<a class="btn secondary" href="/">↩ Back</a></div>
      </div>
    </div>""")
    response=Response(page,status=404,mimetype="text/html")
    response.headers["Cache-Control"]="no-store, no-cache, must-revalidate, max-age=0"
    return response

def _dash_auth_required(fn):
    @wraps(fn)
    def wrapped(bot_id, *args, **kwargs):
        requested=str(bot_id)
        doc=_dash_resolve_doc(requested)
        if not doc or not doc.get("active",True):
            session.pop("creator_dashboard_bot",None)
            return _dash_unavailable_page(requested),404
        bid=str(doc.get("bot_id") or requested)
        if requested != bid:
            return redirect(url_for("creator_dashboard_login",bot_id=bid),code=302)
        if str(session.get("creator_dashboard_bot") or "") != bid:
            remembered=_dash_remember_valid(bid,request.cookies.get("creator_dashboard_remember"))
            if remembered:
                session["creator_dashboard_bot"]=bid
                session.permanent=True
            else:
                return redirect(url_for("creator_dashboard_login", bot_id=bid))
        return fn(doc,*args,**kwargs)
    return wrapped


def _dash_photo_url(bot_id):
    return url_for("creator_dashboard_avatar",bot_id=str(bot_id),_external=True)

@app.route("/media/premium/<months>")
def premium_plan_media(months):
    months=str(months)
    if months not in {"1","3","9","12"}: return "",404
    raw=_dash_db["settings"].find_one({"key":f"premium_plan_media_{months}"}) or {}; value=raw.get("value") or {}; file_id=str(value.get("photo_file_id") or ""); token=os.getenv("BOT_TOKEN","").strip()
    if not file_id or not token: return "",404
    result,err=_dash_bot_api(token,"getFile",{"file_id":file_id},timeout=15)
    if err or not result or not result.get("file_path"): return "",404
    try:
        rr=requests.get(f"https://api.telegram.org/file/bot{token}/{result['file_path']}",timeout=20); rr.raise_for_status()
        return Response(rr.content,content_type=rr.headers.get("content-type","image/jpeg"),headers={"Cache-Control":"public,max-age=300"})
    except Exception: return "",404


def _dash_css():
    return """
    :root{color-scheme:dark;--bg:#07111f;--glass:rgba(20,32,52,.72);--line:rgba(255,255,255,.11);--text:#f7fbff;--muted:#9eacc1;--accent:#8b5cf6;--accent2:#22d3ee;--danger:#fb7185}
    *{box-sizing:border-box}body{margin:0;font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:var(--text);background:radial-gradient(circle at 10% 0%,#263a59 0,transparent 35%),radial-gradient(circle at 90% 10%,#3c245a 0,transparent 30%),linear-gradient(135deg,#050a12,#0a1424 55%,#080d17);min-height:100vh}
    body:before{content:"";position:fixed;inset:0;pointer-events:none;background:linear-gradient(120deg,rgba(255,255,255,.025),transparent 30%,rgba(255,255,255,.018));backdrop-filter:blur(2px)}
    .wrap{width:min(1160px,calc(100% - 28px));margin:0 auto;padding:30px 0 70px}.glass{background:linear-gradient(145deg,rgba(24,38,61,.78),rgba(11,20,35,.64));border:1px solid rgba(255,255,255,.12);box-shadow:0 30px 100px rgba(0,0,0,.38),inset 0 1px rgba(255,255,255,.09),0 0 0 1px rgba(139,92,246,.035);backdrop-filter:blur(28px) saturate(130%);border-radius:28px;position:relative;overflow:hidden}.glass:after{content:"";position:absolute;inset:0;pointer-events:none;background:linear-gradient(120deg,rgba(255,255,255,.055),transparent 28%,transparent 72%,rgba(34,211,238,.025))}
    .unavailable-shell{min-height:82vh;display:grid;place-items:center}.unavailable{width:min(680px,100% - 10px);padding:42px;text-align:center}.unavailable-icon{width:74px;height:74px;margin:0 auto 18px;display:grid;place-items:center;border-radius:24px;background:linear-gradient(135deg,rgba(139,92,246,.25),rgba(34,211,238,.14));border:1px solid rgba(255,255,255,.14);font-size:34px;box-shadow:0 18px 50px rgba(0,0,0,.28)}.eyebrow{font-size:11px;letter-spacing:.18em;color:#a8b7ca;margin-bottom:10px}.unavailable h1{font-size:30px;margin:0 0 10px}.unavailable .actions{justify-content:center}
    .top{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:18px 20px;margin-bottom:18px;position:sticky;top:12px;z-index:10}.brand{display:flex;align-items:center;gap:13px}.avatar{width:58px;height:58px;border-radius:19px;object-fit:cover;border:1px solid rgba(255,255,255,.16);background:#172235;box-shadow:0 10px 30px rgba(0,0,0,.25)}.title{font-size:21px;font-weight:850;letter-spacing:-.02em}.sub{color:var(--muted);font-size:13px;margin-top:3px}
    .pill{padding:8px 12px;border-radius:999px;background:rgba(255,255,255,.06);border:1px solid var(--line);font-size:12px}.pill.premium{background:rgba(139,92,246,.18);border-color:rgba(167,139,250,.32)}
    .grid{display:grid;grid-template-columns:1.35fr .9fr;gap:18px}.card{padding:22px;margin-bottom:18px}.card h2{margin:0 0 7px;font-size:17px}.muted{color:var(--muted);font-size:13px;line-height:1.55}
    label{display:block;font-size:12px;color:var(--muted);margin:14px 0 7px}input,textarea,select{width:100%;border:1px solid var(--line);background:rgba(0,0,0,.18);color:var(--text);border-radius:14px;padding:12px 13px;outline:none;font:inherit}textarea{min-height:110px;resize:vertical}input:focus,textarea:focus,select:focus{border-color:rgba(139,92,246,.7);box-shadow:0 0 0 3px rgba(139,92,246,.11)}
    .btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;border:1px solid rgba(255,255,255,.12);border-radius:13px;padding:11px 14px;background:linear-gradient(135deg,rgba(139,92,246,.92),rgba(34,211,238,.7));color:white;font-weight:750;text-decoration:none;cursor:pointer}.btn.secondary{background:rgba(255,255,255,.055)}.btn.danger{background:rgba(251,113,133,.12);border-color:rgba(251,113,133,.25)}.actions{display:flex;flex-wrap:wrap;gap:9px;margin-top:15px}
    .row2{display:grid;grid-template-columns:1fr 1fr;gap:12px}.stat{padding:15px;border-radius:18px;background:rgba(255,255,255,.045);border:1px solid var(--line)}.stat b{font-size:18px}.stat span{display:block;color:var(--muted);font-size:11px;margin-top:4px}
    .locked{opacity:.62}.lock{display:flex;align-items:center;justify-content:space-between;gap:12px}.notice{padding:12px 14px;border-radius:14px;background:rgba(34,211,238,.07);border:1px solid rgba(34,211,238,.14);font-size:12px;color:#c7f9ff;margin-top:12px}.err{background:rgba(251,113,133,.09);border-color:rgba(251,113,133,.2);color:#ffd2d9}.ok{background:rgba(34,197,94,.09);border-color:rgba(34,197,94,.2);color:#c8ffd7}
    .login{max-width:440px;margin:9vh auto;padding:30px}.login .logo{font-size:42px;margin-bottom:8px}.login h1{margin:0 0 6px}.small{font-size:11px;color:var(--muted)}.logout{color:#cbd5e1;text-decoration:none;font-size:12px}
    @media(max-width:820px){.grid{grid-template-columns:1fr}.row2{grid-template-columns:1fr}.top{align-items:flex-start}.wrap{width:min(100% - 18px,1100px);padding-top:10px}}
    """


def _dash_page(title, body, full=True):
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} • Creator Dashboard</title><style>{_dash_css()}</style></head><body>{body}</body></html>"""




@app.route("/__dashboard_health", methods=["GET"])
def creator_dashboard_health():
    response=Response("QUICKDL_DASHBOARD_OK",status=200,mimetype="text/plain")
    response.headers["Cache-Control"]="no-store, no-cache, must-revalidate, max-age=0"
    return response


@app.route("/dashboard/<bot_id>", methods=["GET","POST"])
def creator_dashboard_login(bot_id):
    requested=str(bot_id)
    doc=_dash_resolve_doc(requested)
    if not doc:
        return _dash_unavailable_page(requested),404
    bid=str(doc.get("bot_id") or requested)
    if not doc.get("active",True) or doc.get("suspended"):
        return _dash_page("Dashboard disabled",'<div class="wrap unavailable-shell"><div class="glass unavailable"><div class="unavailable-icon">⛔</div><div class="eyebrow">QUICKDL • CREATOR</div><h1>Dashboard disabled</h1><p class="muted">This Downloader Bot is no longer active. Its dashboard has been disabled with the bot record.</p></div></div>'),410
    if requested!=bid:
        return redirect(url_for("creator_dashboard_login",bot_id=bid))
    if str(session.get("creator_dashboard_bot") or "")==bid or _dash_remember_valid(bid,request.cookies.get("creator_dashboard_remember")):
        session["creator_dashboard_bot"]=bid
        session.permanent=True
        return redirect(url_for("creator_dashboard_home",bot_id=bid))
    error=""
    remember=False
    if request.method=="POST":
        username=str(request.form.get("username") or "").strip().lstrip("@")
        pin=str(request.form.get("pin") or "").strip()
        remember=bool(request.form.get("remember"))
        expected=str(doc.get("dashboard_username") or doc.get("username") or "").strip().lstrip("@")
        stored_hash=str(doc.get("dashboard_pin_hash") or "").strip()
        pin_ok=_dash_pin_ok(stored_hash,pin)
        # Legacy Creator records may still have the original PIN field.
        # Accept it once and migrate it to the current hash format.
        if not pin_ok:
            legacy_pin=str(doc.get("dashboard_pin") or "").strip()
            if legacy_pin and hmac.compare_digest(legacy_pin,pin):
                pin_ok=True
                try:
                    _dash_bots.update_one({"_id":doc.get("_id")},{"$set":{"dashboard_pin_hash":_dash_pin_hash(pin)}})
                except Exception as e:
                    print("Dashboard PIN migration skipped:",repr(e))
        username_ok=bool(username) and hmac.compare_digest(username.lower(),expected.lower())
        if username_ok and pin_ok:
        session.clear()
        session["creator_dashboard_bot"]=bid
        session.permanent=True
        session["creator_dashboard_saved_at"]=datetime.now(timezone.utc).isoformat()
        response=redirect(url_for("creator_dashboard_home",bot_id=bid),code=302)
        if remember:
            response.set_cookie("creator_dashboard_remember",_dash_remember_value(bid),max_age=31536000,httponly=True,secure=True,samesite="Lax",path="/")
        return response
        error="Invalid dashboard username or PIN."
    botname=str(doc.get("username") or "Downloader Bot").lstrip("@")
    body=f"""<div class="wrap unavailable-shell"><div class="glass login"><div class="logo">◈</div><div class="eyebrow">QUICKDL • CREATOR DASHBOARD</div><h1>Welcome back</h1><div class="muted">Secure owner access for <b>@{html.escape(botname)}</b>.</div>{'<div class="notice err">'+html.escape(error)+'</div>' if error else ''}<form method="post"><label>Dashboard Username</label><input name="username" autocomplete="username" placeholder="@botusername" required><label>6-digit PIN</label><input name="pin" type="password" inputmode="numeric" autocomplete="current-password" minlength="6" maxlength="6" placeholder="••••••" required><label class="lock"><span>💾 Save login on this device</span><input type="checkbox" name="remember" checked></label><div class="actions"><button class="btn" type="submit">⚡ Enter Dashboard</button></div></form><div class="small" style="margin-top:18px">Your PIN stays private. Saved login is signed and expires automatically.</div></div></div>"""
    return _dash_page("Login",body)


@app.route("/dashboard/<bot_id>/home",methods=["GET"])
@_dash_auth_required
def creator_dashboard_home(doc):
    bid=str(doc.get("bot_id"))
    premium=_dash_premium(doc)
    typ="Music Downloader" if str(doc.get("bot_type") or "video")=="music" else "Video Downloader"
    until=doc.get("premium_until") or "Not active"
    avatar=_dash_photo_url(bid)
    photo_html=f'<img class="avatar" src="{avatar}" alt="Telegram profile" onerror="this.style.display=\'none\'">'
    notice=request.args.get("notice","")
    locked="" if premium else '<div class="notice">💎 Premium-only controls are locked. Open Premium in Creator Bot to unlock profile editing, broadcast, speed, ads and YouTube controls.</div>'
    token_action=(f'<form method="post" action="{url_for("creator_dashboard_rotate_token",bot_id=bid)}"><button class="btn danger" type="submit">🔄 Revoke Bot Token</button></form>' if bool(doc.get("managed",True)) else "")
    body=f"""<div class="wrap">
    <div class="glass top"><div class="brand">{photo_html}<div><div class="title">@{html.escape(str(doc.get("username") or "unknown"))}</div><div class="sub">{typ} • Dashboard</div></div></div><div style="display:flex;align-items:center;gap:12px"><span class="pill {'premium' if premium else ''}">{'💎 Premium' if premium else '🆓 Standard'}</span><a class="logout" href="{url_for('creator_dashboard_logout',bot_id=bid)}">Log out</a></div></div>
    {f'<div class="notice ok">{html.escape(notice)}</div>' if notice else ''}
    {locked}
    <div class="grid">
      <main>
        <div class="glass card"><h2>Bot Profile</h2><div class="muted">These Telegram profile settings are available to Premium creators.</div>
          <form method="post" action="{url_for('creator_dashboard_profile',bot_id=bid)}">
            <label>Bot name</label><input name="name" maxlength="64" value="{html.escape(str(doc.get("name") or ""))}" {'disabled' if not premium else ''}>
            <label>Short description</label><input name="short_description" maxlength="120" value="{html.escape(str(doc.get("short_description") or ""))}" {'disabled' if not premium else ''}>
            <label>Full description</label><textarea name="description" maxlength="512" {'disabled' if not premium else ''}>{html.escape(str(doc.get("description") or ""))}</textarea>
            <label>/start message</label><textarea name="start_message" maxlength="3500" {'disabled' if not premium else ''}>{html.escape(str(doc.get("start_message") or ""))}</textarea>
            <div class="actions"><button class="btn" type="submit" {'disabled' if not premium else ''}>💾 Save Profile</button></div>
          </form>
        </div>
        <div class="glass card"><h2>Profile Photo</h2><div class="muted">Upload a JPG/PNG profile image for your bot.</div>
          <form method="post" enctype="multipart/form-data" action="{url_for('creator_dashboard_photo',bot_id=bid)}"><label>New photo</label><input type="file" name="photo" accept=".jpg,.jpeg,.png" {'disabled' if not premium else ''}><div class="actions"><button class="btn" type="submit" {'disabled' if not premium else ''}>📷 Set Profile Photo</button><button class="btn secondary" formaction="{url_for('creator_dashboard_photo_remove',bot_id=bid)}" formmethod="post" type="submit" {'disabled' if not premium else ''}>🗑 Remove Photo</button></div></form>
        </div>
        <div class="glass card"><h2>Broadcast</h2><div class="muted">Send one message to users recorded by this downloader bot.</div>
          <form method="post" action="{url_for('creator_dashboard_broadcast',bot_id=bid)}"><textarea name="message" maxlength="4096" placeholder="Write your broadcast..." {'disabled' if not premium else ''}></textarea><div class="actions"><button class="btn" type="submit" {'disabled' if not premium else ''}>📢 Send Broadcast</button></div></form>
        </div>
      </main>
      <aside>
        <div class="glass card"><h2>Bot Status</h2><div class="row2"><div class="stat"><b>{'🟢' if doc.get('active',True) else '🔴'}</b><span>Runtime</span></div><div class="stat"><b>{len(doc.get('users') or [])}</b><span>Users</span></div></div><div class="notice">Premium until: <b>{html.escape(str(until))}</b></div></div>
        <div class="glass card"><h2>Users</h2><div class="muted">Telegram users who have opened or interacted with this Downloader Bot.</div>
          <div class="user-list">{''.join(f'<div class="stat" style="margin-top:9px"><b>👤 {html.escape(str(x))}</b><span>Telegram user ID</span></div>' for x in list(doc.get('users') or [])[-100:][::-1]) or '<div class="notice">No users recorded yet.</div>'}</div>
          <div class="small" style="margin-top:10px">Showing the latest {min(100,len(doc.get('users') or []))} users.</div>
        </div>
        <div class="glass card"><h2>Premium Controls</h2>
          <form method="post" action="{url_for('creator_dashboard_controls',bot_id=bid)}">
            <div class="lock"><span>🚫 Disable Ads</span><input type="checkbox" name="ads_disabled" {'checked' if premium and doc.get('ads_enabled') is False else ''} {'disabled' if not premium else ''}></div>
            <div class="lock" style="margin-top:14px"><span>🏷 Disable Powered By</span><input type="checkbox" name="powered_disabled" {'checked' if premium and doc.get('powered_by_enabled') is False else ''} {'disabled' if not premium else ''}></div>
            <label>⚡ Bot speed</label><select name="speed" {'disabled' if not premium else ''}><option value="normal" {'selected' if doc.get('speed')=='normal' else ''}>Normal</option><option value="fast" {'selected' if doc.get('speed','fast')=='fast' else ''}>Fast</option><option value="turbo" {'selected' if doc.get('speed')=='turbo' else ''}>Turbo</option></select>
            <label>▶️ YouTube maximum minutes (0 = unlimited)</label><input type="number" min="0" max="1440" name="youtube_max_minutes" value="{int(doc.get('youtube_max_minutes') or 0)}" {'disabled' if not premium else ''}>
            <label>🎛 Menu buttons</label>
            <div class="lock"><span>🤖 Create My Bot</span><input type="checkbox" name="menu_create_enabled" {'checked' if doc.get('menu_create_enabled',True) else ''} {'disabled' if not premium else ''}></div>
            <div class="lock"><span>🚫 Remove Ads</span><input type="checkbox" name="menu_remove_ads_enabled" {'checked' if doc.get('menu_remove_ads_enabled',True) else ''} {'disabled' if not premium else ''}></div>
            <div class="lock"><span>💎 Premium</span><input type="checkbox" name="menu_premium_enabled" {'checked' if doc.get('menu_premium_enabled',True) else ''} {'disabled' if not premium else ''}></div>
            <label>🌐 Disable platforms</label>
            <div class="lock"><span>TikTok</span><input type="checkbox" name="disabled_platforms" value="tiktok" {'checked' if 'tiktok' in set(doc.get('disabled_platforms') or []) else ''} {'disabled' if not premium else ''}></div>
            <div class="lock"><span>Instagram</span><input type="checkbox" name="disabled_platforms" value="instagram" {'checked' if 'instagram' in set(doc.get('disabled_platforms') or []) else ''} {'disabled' if not premium else ''}></div>
            <div class="lock"><span>Facebook</span><input type="checkbox" name="disabled_platforms" value="facebook" {'checked' if 'facebook' in set(doc.get('disabled_platforms') or []) else ''} {'disabled' if not premium else ''}></div>
            <div class="lock"><span>YouTube</span><input type="checkbox" name="disabled_platforms" value="youtube" {'checked' if 'youtube' in set(doc.get('disabled_platforms') or []) else ''} {'disabled' if not premium else ''}></div>
            <div class="actions"><button class="btn" type="submit" {'disabled' if not premium else ''}>⚙️ Save Dashboard Controls</button></div>
          </form>
        </div>
        <div class="glass card"><h2>Security</h2><div class="muted">PIN and managed-token controls stay separate from profile customization.</div>
          <div class="actions"><form method="post" action="{url_for('creator_dashboard_rotate_pin',bot_id=bid)}"><button class="btn secondary" type="submit">🔐 Revoke PIN / Get New PIN</button></form>
          {token_action}
          </div>
        </div>
      </aside>
    </div></div>"""
    return _dash_page("Dashboard",body)


@app.route("/dashboard/<bot_id>/logout",methods=["GET"])
def creator_dashboard_logout(bot_id):
    session.pop("creator_dashboard_bot",None)
    response=redirect(url_for("creator_dashboard_login",bot_id=str(bot_id)))
    response.delete_cookie("creator_dashboard_remember")
    return response


@app.route("/dashboard/<bot_id>/profile",methods=["POST"])
@_dash_auth_required
def creator_dashboard_profile(doc):
    bid=str(doc.get("bot_id"))
    if not _dash_premium(doc):
        return redirect(url_for("creator_dashboard_home",bot_id=bid)+"?notice=Premium required for profile editing.")
    token=_dash_token(doc)
    name=str(request.form.get("name") or "").strip()
    short=str(request.form.get("short_description") or "").strip()
    description=str(request.form.get("description") or "").strip()
    start_message=str(request.form.get("start_message") or "").strip()
    if not name or len(name)>64 or len(short)>120 or len(description)>512 or len(start_message)>3500:
        return redirect(url_for("creator_dashboard_home",bot_id=bid)+"?notice=One of the fields is too long or empty.")
    errors=[]
    for method,payload in [
        ("setMyName",{"name":name}),
        ("setMyShortDescription",{"short_description":short}),
        ("setMyDescription",{"description":description}),
    ]:
        _,err=_dash_bot_api(token,method,payload)
        if err: errors.append(err)
    if not errors:
        _dash_bots.update_one({"bot_id":bid},{"$set":{"name":name,"short_description":short,"description":description,"start_message":start_message,"updated_at":datetime.now(timezone.utc)}})
        return redirect(url_for("creator_dashboard_home",bot_id=bid)+"?notice=Profile saved successfully.")
    return redirect(url_for("creator_dashboard_home",bot_id=bid)+"?notice="+urllib.parse.quote("Telegram rejected a profile change: "+errors[0]))


@app.route("/dashboard/<bot_id>/photo",methods=["POST"])
@_dash_auth_required
def creator_dashboard_photo(doc):
    bid=str(doc.get("bot_id"))
    if not _dash_premium(doc):
        return redirect(url_for("creator_dashboard_home",bot_id=bid)+"?notice=Premium required for profile photo.")
    token=_dash_token(doc)
    file=request.files.get("photo")
    if not file or not file.filename:
        return redirect(url_for("creator_dashboard_home",bot_id=bid)+"?notice=Choose a JPG or PNG image.")
    raw=file.read()
    if len(raw)>10*1024*1024:
        return redirect(url_for("creator_dashboard_home",bot_id=bid)+"?notice=Photo is too large.")
    mime=file.mimetype or "image/jpeg"
    if mime not in {"image/jpeg","image/png"}:
        return redirect(url_for("creator_dashboard_home",bot_id=bid)+"?notice=Only JPG or PNG is allowed.")
    try:
        rr=requests.post(
            f"https://api.telegram.org/bot{token}/setMyProfilePhoto",
            data={"photo":json.dumps({"type":"static","photo":"attach://photo"})},
            files={"photo":(file.filename,raw,mime)},
            timeout=30,
        )
        data=rr.json()
        if not data.get("ok"):
            raise RuntimeError(data.get("description") or "Telegram rejected the photo")
        return redirect(url_for("creator_dashboard_home",bot_id=bid)+"?notice=Profile photo updated.")
    except Exception as e:
        return redirect(url_for("creator_dashboard_home",bot_id=bid)+"?notice="+urllib.parse.quote(str(e)))


@app.route("/dashboard/<bot_id>/photo/remove",methods=["POST"])
@_dash_auth_required
def creator_dashboard_photo_remove(doc):
    bid=str(doc.get("bot_id"))
    if not _dash_premium(doc):
        return redirect(url_for("creator_dashboard_home",bot_id=bid)+"?notice=Premium required.")
    token=_dash_token(doc)
    _,err=_dash_bot_api(token,"removeMyProfilePhoto",{})
    return redirect(url_for("creator_dashboard_home",bot_id=bid)+"?notice="+urllib.parse.quote("Profile photo removed." if not err else err))


@app.route("/dashboard/<bot_id>/controls",methods=["POST"])
@_dash_auth_required
def creator_dashboard_controls(doc):
    bid=str(doc.get("bot_id"))
    if not _dash_premium(doc):
        return redirect(url_for("creator_dashboard_home",bot_id=bid)+"?notice=Premium required for these controls.")
    speed=str(request.form.get("speed") or "fast").lower()
    if speed not in {"normal","fast","turbo"}: speed="fast"
    try: yt=max(0,min(1440,int(request.form.get("youtube_max_minutes") or 0)))
    except Exception: yt=0
    ads_enabled=not bool(request.form.get("ads_disabled")); powered=not bool(request.form.get("powered_disabled"))
    disabled=[x for x in request.form.getlist("disabled_platforms") if x in {"tiktok","instagram","facebook","youtube","pinterest","snapchat","twitter"}]
    _dash_bots.update_one({"bot_id":bid},{"$set":{
        "ads_enabled":ads_enabled,"powered_by_enabled":powered,"speed":speed,"youtube_max_minutes":yt,"disabled_platforms":disabled,
        "menu_create_enabled":bool(request.form.get("menu_create_enabled")),"menu_remove_ads_enabled":bool(request.form.get("menu_remove_ads_enabled")),"menu_premium_enabled":bool(request.form.get("menu_premium_enabled")),"updated_at":datetime.now(timezone.utc)
    }})
    return redirect(url_for("creator_dashboard_home",bot_id=bid)+"?notice=Premium controls saved.")


@app.route("/dashboard/<bot_id>/rotate-pin",methods=["POST"])
@_dash_auth_required
def creator_dashboard_rotate_pin(doc):
    bid=str(doc.get("bot_id"))
    pin=_dash_make_pin()
    _dash_bots.update_one({"bot_id":bid},{"$set":{"dashboard_pin_hash":_dash_pin_hash(pin),"dashboard_pin_updated_at":datetime.now(timezone.utc)}})
    owner=str(doc.get("owner_id") or "")
    if owner:
        dash_url=html.escape(f"{DASHBOARD_BASE_URL}/dashboard/{bid}",quote=True)
        _dash_creator_api("sendMessage",{"chat_id":int(owner),"text":
            f"🔐 <b>Dashboard PIN Updated</b>\n\n"
            f"🤖 <b>@{html.escape(str(doc.get('username') or 'unknown'))}</b>\n"
            f'🌐 <a href="{dash_url}">Open Dashboard</a>\n'
            f"👤 Username: <code>{html.escape(str(doc.get('dashboard_username') or doc.get('username') or ''))}</code>\n"
            f"🔑 New PIN: <code>{pin}</code>\n\n"
            "The old PIN is now revoked."})
    return redirect(url_for("creator_dashboard_home",bot_id=bid)+"?notice=Old PIN revoked. Your new PIN was sent by Creator Bot.")


@app.route("/dashboard/<bot_id>/rotate-token",methods=["POST"])
@_dash_auth_required
def creator_dashboard_rotate_token(doc):
    bid=str(doc.get("bot_id"))
    if not bool(doc.get("managed",True)):
        return redirect(url_for("creator_dashboard_home",bot_id=bid)+"?notice=Automatic token rotation is available only for Telegram-managed bots.")
    result,err=_dash_creator_api("replaceManagedBotToken",{"user_id":int(bid)},timeout=25)
    if err or not result:
        return redirect(url_for("creator_dashboard_home",bot_id=bid)+"?notice="+urllib.parse.quote("Token revoke failed: "+str(err or "Telegram returned no token.")))
    # A token revoke also revokes the old dashboard PIN. The new PIN is sent
    # only through the Creator Bot, never displayed on the web page.
    pin=_dash_make_pin()
    _dash_bots.update_one({"bot_id":bid},{"$set":{"dashboard_pin_hash":_dash_pin_hash(pin),"dashboard_pin_updated_at":datetime.now(timezone.utc)}})
    owner=str(doc.get("owner_id") or "")
    if owner:
        dash_url=html.escape(f"{DASHBOARD_BASE_URL}/dashboard/{bid}",quote=True)
        _dash_creator_api("sendMessage",{"chat_id":int(owner),"text":
            f"🔐 <b>Dashboard PIN Rotated</b>\n\n"
            f"🤖 <b>@{html.escape(str(doc.get('username') or 'unknown'))}</b>\n"
            f'🌐 <a href="{dash_url}">Open Dashboard</a>\n'
            f"👤 Username: <code>{html.escape(str(doc.get('dashboard_username') or doc.get('username') or ''))}</code>\n"
            f"🔑 New PIN: <code>{pin}</code>\n\n"
            "The old Dashboard PIN was revoked because the bot token was revoked. "
            "Creator Bot will receive the new token and restart the bot automatically."})
    return redirect(url_for("creator_dashboard_home",bot_id=bid)+"?notice=Token revoke requested. Old Dashboard PIN revoked; the new PIN was sent by Creator Bot.")


@app.route("/dashboard/<bot_id>/broadcast",methods=["POST"])
@_dash_auth_required
def creator_dashboard_broadcast(doc):
    bid=str(doc.get("bot_id"))
    if not _dash_premium(doc):
        return redirect(url_for("creator_dashboard_home",bot_id=bid)+"?notice=Premium required for broadcast.")
    token=_dash_token(doc)
    message=str(request.form.get("message") or "").strip()
    if not message:
        return redirect(url_for("creator_dashboard_home",bot_id=bid)+"?notice=Broadcast message is empty.")
    targets=[int(x) for x in (doc.get("users") or [])[:10000]]
    sent=failed=0
    def send_one(uid):
        return _dash_bot_api(token,"sendMessage",{"chat_id":uid,"text":message,"parse_mode":"HTML"},timeout=12)
    with ThreadPoolExecutor(max_workers=24) as pool:
        for _,err in pool.map(send_one,targets):
            if err: failed+=1
            else: sent+=1
    return redirect(url_for("creator_dashboard_home",bot_id=bid)+f"?notice=Broadcast complete: {sent} sent, {failed} failed.")


@app.route("/dashboard/<bot_id>/avatar",methods=["GET"])
@_dash_auth_required
def creator_dashboard_avatar(doc):
    token=_dash_token(doc)
    photos,err=_dash_bot_api(token,"getUserProfilePhotos",{"user_id":int(doc.get("bot_id")),"limit":1})
    if err or not photos or not photos.get("photos"):
        return "",404
    sizes=photos["photos"][0]
    photo=sizes[-1] if sizes else None
    if not photo: return "",404
    file,err=_dash_bot_api(token,"getFile",{"file_id":photo.get("file_id")})
    if err or not file: return "",404
    try:
        rr=requests.get(f"https://api.telegram.org/file/bot{token}/{file['file_path']}",timeout=15)
        rr.raise_for_status()
        return Response(rr.content,content_type=rr.headers.get("content-type","image/jpeg"),headers={"Cache-Control":"private,max-age=300"})
    except Exception:
        return "",404


if __name__ == "__main__":
    app.run()
