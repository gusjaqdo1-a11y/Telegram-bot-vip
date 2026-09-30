from flask import Flask, request, send_file, session, redirect, url_for, render_template_string, Response
import yt_dlp
import os
import uuid
import html
import urllib.parse
import requests

app = Flask(__name__)
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


def _dash_auth_required(fn):
    @wraps(fn)
    def wrapped(bot_id, *args, **kwargs):
        bid=str(bot_id)
        if str(session.get("creator_dashboard_bot") or "") != bid:
            return redirect(url_for("creator_dashboard_login", bot_id=bid))
        doc=_dash_bots.find_one({"bot_id":bid})
        if not doc or not doc.get("active",True):
            session.pop("creator_dashboard_bot",None)
            return render_template_string(_dash_page("Dashboard unavailable","This bot is no longer active in Creator Bot.",False))
        return fn(doc,*args,**kwargs)
    return wrapped


def _dash_photo_url(bot_id):
    return url_for("creator_dashboard_avatar",bot_id=str(bot_id),_external=True)


def _dash_css():
    return """
    :root{color-scheme:dark;--bg:#07111f;--glass:rgba(20,32,52,.72);--line:rgba(255,255,255,.11);--text:#f7fbff;--muted:#9eacc1;--accent:#8b5cf6;--accent2:#22d3ee;--danger:#fb7185}
    *{box-sizing:border-box}body{margin:0;font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:var(--text);background:radial-gradient(circle at 10% 0%,#263a59 0,transparent 35%),radial-gradient(circle at 90% 10%,#3c245a 0,transparent 30%),linear-gradient(135deg,#050a12,#0a1424 55%,#080d17);min-height:100vh}
    body:before{content:"";position:fixed;inset:0;pointer-events:none;background:linear-gradient(120deg,rgba(255,255,255,.025),transparent 30%,rgba(255,255,255,.018));backdrop-filter:blur(2px)}
    .wrap{width:min(1100px,calc(100% - 28px));margin:0 auto;padding:30px 0 60px}.glass{background:var(--glass);border:1px solid var(--line);box-shadow:0 24px 80px rgba(0,0,0,.34),inset 0 1px rgba(255,255,255,.07);backdrop-filter:blur(22px);border-radius:26px}
    .top{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:18px 20px;margin-bottom:18px}.brand{display:flex;align-items:center;gap:13px}.avatar{width:56px;height:56px;border-radius:18px;object-fit:cover;border:1px solid rgba(255,255,255,.14);background:#172235}.title{font-size:21px;font-weight:800}.sub{color:var(--muted);font-size:13px;margin-top:3px}
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


@app.route("/dashboard/<bot_id>", methods=["GET","POST"])
def creator_dashboard_login(bot_id):
    bid=str(bot_id)
    doc=_dash_bots.find_one({"bot_id":bid})
    if not doc:
        return _dash_page("Not found",'<div class="wrap"><div class="glass card"><h2>Dashboard not found</h2><div class="muted">This bot is not registered in Creator Bot.</div></div></div>'),404
    if str(session.get("creator_dashboard_bot") or "")==bid:
        return redirect(url_for("creator_dashboard_home",bot_id=bid))
    error=""
    if request.method=="POST":
        username=str(request.form.get("username") or "").strip().lstrip("@")
        pin=str(request.form.get("pin") or "").strip()
        expected=str(doc.get("dashboard_username") or doc.get("username") or "").strip().lstrip("@")
        if hmac.compare_digest(username.lower(),expected.lower()) and _dash_pin_ok(doc.get("dashboard_pin_hash"),pin):
            session["creator_dashboard_bot"]=bid
            session.permanent=True
            return redirect(url_for("creator_dashboard_home",bot_id=bid))
        error="Invalid dashboard username or PIN."
    botname=str(doc.get("username") or "Downloader Bot").lstrip("@")
    body=f"""<div class="wrap"><div class="glass login"><div class="logo">🤖</div><h1>Creator Dashboard</h1><div class="muted">Secure access for <b>@{botname}</b>.</div>{'<div class="notice err">'+error+'</div>' if error else ''}<form method="post"><label>Dashboard Username</label><input name="username" autocomplete="username" required><label>PIN</label><input name="pin" inputmode="numeric" autocomplete="current-password" minlength="6" maxlength="6" required><div class="actions"><button class="btn" type="submit">🔐 Open Dashboard</button></div></form><div class="small" style="margin-top:16px">Your PIN is private. Creator Bot can issue a new PIN at any time.</div></div></div>"""
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
        <div class="glass card"><h2>Premium Controls</h2>
          <form method="post" action="{url_for('creator_dashboard_controls',bot_id=bid)}">
            <div class="lock"><span>🚫 Disable Ads</span><input type="checkbox" name="ads_disabled" {'checked' if premium and doc.get('ads_enabled') is False else ''} {'disabled' if not premium else ''}></div>
            <div class="lock" style="margin-top:14px"><span>🏷 Disable Powered By</span><input type="checkbox" name="powered_disabled" {'checked' if premium and doc.get('powered_by_enabled') is False else ''} {'disabled' if not premium else ''}></div>
            <label>⚡ Bot speed</label><select name="speed" {'disabled' if not premium else ''}><option value="normal" {'selected' if doc.get('speed')=='normal' else ''}>Normal</option><option value="fast" {'selected' if doc.get('speed','fast')=='fast' else ''}>Fast</option><option value="turbo" {'selected' if doc.get('speed')=='turbo' else ''}>Turbo</option></select>
            <label>▶️ YouTube maximum minutes (0 = unlimited)</label><input type="number" min="0" max="1440" name="youtube_max_minutes" value="{int(doc.get('youtube_max_minutes') or 0)}" {'disabled' if not premium else ''}>
            <div class="actions"><button class="btn" type="submit" {'disabled' if not premium else ''}>⚙️ Save Premium Controls</button></div>
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
    return redirect(url_for("creator_dashboard_login",bot_id=str(bot_id)))


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
    ads_enabled=not bool(request.form.get("ads_disabled"))
    powered=not bool(request.form.get("powered_disabled"))
    _dash_bots.update_one({"bot_id":bid},{"$set":{
        "ads_enabled":ads_enabled,"powered_by_enabled":powered,"speed":speed,
        "youtube_max_minutes":yt,"updated_at":datetime.now(timezone.utc)
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
