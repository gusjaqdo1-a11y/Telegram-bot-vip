# creator_v2.py
import os, json, time, secrets, hashlib, html, urllib.parse, re
from datetime import datetime, timezone

def apply(core):
    def now(): return datetime.now(timezone.utc)
    def is_admin(uid):
        try: return bool(core.is_admin(uid))
        except Exception: return str(uid) in {str(x) for x in getattr(core,"ADMIN_IDS",[])}

    # ---------- Dashboard persistence ----------
    def defaults():
        return {
            "ads_enabled": True, "premium_enabled": True, "default_quality": "best",
            "welcome_text": "",
            "platforms": {x: True for x in (
                "youtube","tiktok","instagram","facebook","pinterest","snapchat","twitter",
                "reddit","threads","likee","vimeo","dailymotion","soundcloud","twitch",
                "tumblr","streamable","odnoklassniki")},
            "buttons": {"create":True,"remove_ads":True,"admin":True,"powered_by":True,"premium":True,"music":True},
            "locked_fields": []
        }

    def ensure_dashboard(d):
        if not d: return d
        bid=str(d.get("bot_id"))
        pin=str(d.get("dashboard_pin_plain") or "")
        if not (pin.isdigit() and len(pin)==6):
            seed=f"{d.get('owner_id')}:{bid}:{os.getenv('DASHBOARD_PIN_SECRET','quickdl-dashboard')}"
            pin=str(int(hashlib.sha256(seed.encode()).hexdigest()[:12],16)%1000000).zfill(6)
        s=d.get("dashboard_settings") if isinstance(d.get("dashboard_settings"),dict) else {}
        b=defaults()
        for k in ("ads_enabled","premium_enabled","default_quality","welcome_text"):
            if k in s: b[k]=s[k]
        for k in ("platforms","buttons"):
            if isinstance(s.get(k),dict): b[k].update(s[k])
        locks=core.get_setting("dashboard_locked_fields",[])
        b["locked_fields"]=list(locks or s.get("locked_fields") or [])
        upd={"dashboard_pin_plain":pin,
             "dashboard_pin_hash":hashlib.sha256(pin.encode()).hexdigest(),
             "dashboard_settings":b,
             "dashboard_url":str(core.AD_PUBLIC_BASE_URL).rstrip("/")+"/dashboard/"+bid}
        core.managed_bots_col.update_one({"bot_id":bid},{"$set":upd},upsert=True)
        d.update(upd)
        return d

    def get_dash(bid):
        return ensure_dashboard(core.managed_bots_col.find_one({"bot_id":str(bid)}) or {})

    def dash_link(d):
        return str(core.AD_PUBLIC_BASE_URL).rstrip("/")+"/dashboard/"+str(d.get("bot_id"))

    def notify_owner(d,text):
        try:
            if d.get("owner_id"): core._creator_send(int(d["owner_id"]),text,parse_mode="HTML")
        except Exception as e: print("dashboard owner notify:",repr(e))

    def notify_admin(text):
        for aid in getattr(core,"ADMIN_IDS",[]):
            try: core.bot.send_message(int(aid),text,parse_mode="HTML")
            except Exception: pass

    # ---------- Creator: three visual choices + native Telegram managed-bot UI ----------
    card_defaults={
        "video":{"title":"🎬 VIDEO DOWNLOADER","text":"Videos & photos from supported platforms. Fast and simple.","image":""},
        "music":{"title":"🎵 MUSIC DOWNLOADER","text":"Search songs, download full audio, metadata and artwork.","image":""},
        "all":{"title":"💎 ALL-IN-ONE DOWNLOADER","text":"Video + music features in one managed Downloader Bot.","image":""}
    }
    def card(kind):
        x=core.get_setting("creator_card_"+kind,card_defaults[kind])
        return x if isinstance(x,dict) else card_defaults[kind]

    def safe_username(v):
        v=str(v or "").lstrip("@")
        return v if re.fullmatch(r"[A-Za-z0-9_]{5,32}bot",v,re.I) else "QuickDLDownloaderBot"

    def create_screen(uid,chat_id,kind="video",edit=None):
        sess=core._creator_session(uid)
        rid=int(sess.get("request_id") or secrets.randbelow(2000000000)+1)
        name=str(sess.get("suggested_name") or "QuickDL Downloader")[:64]
        username=safe_username(sess.get("suggested_username") or "QuickDLDownloaderBot")
        core._creator_set_session(uid,{**sess,"state":"waiting_managed_bot","bot_type":kind,
            "request_id":rid,"suggested_name":name,"suggested_username":username,"updated_at":now()})
        c=card(kind)
        caption="<b>"+html.escape(str(c.get("title") or ""))+"</b>\n\n"+html.escape(str(c.get("text") or ""))+"\n\nChoose a type. Then tap <b>🚀 Create with Telegram</b>. Telegram opens the official creation screen where the name and username can be edited."
        rows=[
            [{"text":"🎬 Video Downloader","callback_data":"v2type:video"},{"text":"🎵 Music Downloader","callback_data":"v2type:music"}],
            [{"text":"💎 All-in-One Downloader","callback_data":"v2type:all"}],
            [{"text":"🚀 Create with Telegram","callback_data":"v2managed:"+str(rid)}],
            [{"text":"❌ Cancel","callback_data":"v2cancel"}]]
        markup={"inline_keyboard":rows}
        image=str(c.get("image") or "").strip()
        if edit:
            cid=edit["chat_id"]; mid=edit["message_id"]
            if image:
                rr=core._creator_api("editMessageMedia",{"chat_id":cid,"message_id":mid,
                    "media":{"type":"photo","media":image,"caption":caption,"parse_mode":"HTML"},"reply_markup":markup})
                if rr[1]: core._creator_edit(cid,mid,caption,reply_markup=markup)
            else: core._creator_edit(cid,mid,caption,reply_markup=markup)
        elif image:
            core._creator_api("sendPhoto",{"chat_id":chat_id,"photo":image,"caption":caption,
                "parse_mode":"HTML","reply_markup":markup})
        else:
            core._creator_send(chat_id,caption,reply_markup=markup)

    def start_create(uid,chat_id):
        if not core._creation_open():
            core._creator_send(chat_id,"🔒 <b>Bot Creation is Closed</b>\n\nExisting bots continue working normally.",reply_markup=core._creator_keyboard(uid)); return
        if not core._creator_verify_gate(uid,chat_id): return
        core._creator_set_session(uid,{"state":"type","updated_at":now()})
        create_screen(uid,chat_id,"video")

    old_text=core._creator_handle_text
    def text_handler(uid,chat_id,text):
        st=str(core._creator_session(uid).get("state") or "")
        if st=="type":
            core._creator_send(chat_id,"Choose one of the three bot types using the buttons above."); return
        if st=="waiting_managed_bot":
            core._creator_send(chat_id,"⏳ Tap <b>🚀 Create with Telegram</b>. Telegram will collect the bot name and username directly."); return
        return old_text(uid,chat_id,text)
    core._creator_start_create=start_create
    core._creator_handle_text=text_handler

    old_cb=core._creator_callback
    def callback(call):
        data=str((call or {}).get("data") or "")
        uid=str(((call or {}).get("from") or {}).get("id") or "")
        msg=((call or {}).get("message") or {}); cid=(msg.get("chat") or {}).get("id"); mid=msg.get("message_id")
        if data=="v2cancel":
            core._creator_answer(call.get("id"),"Cancelled"); core._creator_clear_session(uid)
            try: core._creator_edit(cid,mid,"↩️ <b>Creation cancelled.</b>",reply_markup=core._creator_keyboard(uid))
            except Exception: pass
            return
        if data.startswith("v2type:"):
            kind=data.split(":",1)[1]
            if kind not in {"video","music","all"}:
                core._creator_answer(call.get("id"),"Invalid type",True); return
            if core._creator_session(uid).get("state") not in {"type","waiting_managed_bot"}:
                core._creator_answer(call.get("id"),"Creation session expired.",True); return
            core._creator_answer(call.get("id"),"Selected")
            create_screen(uid,cid,kind,{"chat_id":cid,"message_id":mid}); return
        if data.startswith("v2managed:"):
            rid=int(data.split(":",1)[1]); s=core._creator_session(uid)
            if int(s.get("request_id") or 0)!=rid:
                core._creator_answer(call.get("id"),"Session expired.",True); return
            name=str(s.get("suggested_name") or "QuickDL Downloader")[:64]
            username=safe_username(s.get("suggested_username"))
            kb={"keyboard":[[{"text":"🚀 Create with Telegram","request_managed_bot":{
                "request_id":rid,"suggested_name":name,"suggested_username":username}}],
                [{"text":"❌ Cancel"}]],"resize_keyboard":True,"one_time_keyboard":True}
            core._creator_answer(call.get("id"),"Open Telegram")
            core._creator_send(cid,"🚀 <b>CREATE WITH TELEGRAM</b>\n\nSuggested name: <b>"+html.escape(name)+"</b>\nSuggested username: <b>@"+html.escape(username)+"</b>\n\nTap the button. Telegram will open the native creation flow.",reply_markup=kb)
            return
        return old_cb(call)
    core._creator_callback=callback

    # ---------- Managed token rotation ----------
    def stop_instance(bid):
        bid=str(bid); mb=core.managed_bot_objects.pop(bid,None)
        if mb:
            try: mb.stop_polling()
            except Exception: pass
        core.managed_bot_threads.pop(bid,None)

    def restart(d):
        stop_instance(d.get("bot_id"))
        time.sleep(.15)
        try: return core._managed_bot_start_instance(d)
        except Exception as e: print("managed restart:",repr(e)); return None

    def managed_update(update):
        obj=(update or {}).get("managed_bot") or {}; info=obj.get("bot") or {}; owner=obj.get("user") or {}
        bid=str(info.get("id") or "")
        if not bid: return
        old=core.managed_bots_col.find_one({"bot_id":bid}) or {}
        fresh,err=core._creator_api("getManagedBotToken",{"user_id":int(bid)},timeout=15)
        if err or not fresh:
            if old: core._creator_notify_managed_bot_removed(old,"deleted_or_revoked")
            return
        username=str(info.get("username") or old.get("username") or "").lstrip("@")
        name=str(info.get("first_name") or old.get("name") or "Downloader Bot")
        old_token=core._decrypt_managed_token(old) if old else ""
        if old and old_token and str(fresh)!=str(old_token):
            d=dict(old); d.update({"token_enc":core._encrypt_managed_token(fresh),"username":username or d.get("username"),
                "name":name,"active":True,"suspended":False,"updated_at":now(),
                "token_rotated_at":now(),"token_rotation_count":int(d.get("token_rotation_count",0) or 0)+1})
            core.managed_bots_col.update_one({"bot_id":bid},{"$set":d}); d=core.managed_bots_col.find_one({"bot_id":bid}) or d
            ensure_dashboard(d); restart(d)
            u=username or d.get("username") or "unknown"
            notify_owner(d,"🔄 <b>Bot Token Updated</b>\n\n🤖 @"+html.escape(str(u).lstrip("@"))+"\n\nTelegram changed this managed bot's token. Creator Bot automatically received the new token, saved it securely and restarted the bot.\n\n✅ Your bot remains in My Bots and continues using the same settings.")
            notify_admin("🔄 <b>Managed Bot Token Updated</b>\n\n🤖 @"+html.escape(str(u).lstrip("@"))+"\nOwner: <code>"+html.escape(str(d.get("owner_id")))+"</code>")
            return
        if old:
            d=dict(old); d.update({"username":username or d.get("username"),"name":name,"updated_at":now()})
            core.managed_bots_col.update_one({"bot_id":bid},{"$set":d}); ensure_dashboard(d); return
        uid=str(owner.get("id") or ""); s=core._creator_session(uid); btype=str(s.get("bot_type") or "video")
        if btype not in {"video","music","all"}: btype="video"
        d={"bot_id":bid,"owner_id":uid,"token_enc":core._encrypt_managed_token(fresh),"username":username,
           "name":name,"bot_type":btype,"active":True,"suspended":False,"premium_until":None,
           "wallet_linked":False,"created_at":now(),"updated_at":now(),"users":[]}
        ensure_dashboard(d); core.managed_bots_col.update_one({"bot_id":bid},{"$set":d},upsert=True); restart(d)

    core._creator_on_managed_update=managed_update

    def health():
        for d in list(core.managed_bots_col.find({"active":True,"suspended":{"$ne":True}})):
            bid=str(d.get("bot_id") or ""); token=core._decrypt_managed_token(d)
            if not bid or not token: continue
            try:
                _,err=core._creator_api_with_token(token,"getMe",{},timeout=8)
                if not err: continue
                fresh,ferr=core._creator_api("getManagedBotToken",{"user_id":int(bid)},timeout=10)
                if not ferr and fresh:
                    if str(fresh)!=str(token):
                        managed_update({"managed_bot":{"bot":{"id":int(bid),"username":d.get("username"),"first_name":d.get("name")},"user":{"id":int(d.get("owner_id") or 0)}}})
                    continue
                core._creator_notify_managed_bot_removed(d,"deleted_or_revoked")
            except Exception as e: print("managed health:",repr(e))
    core._creator_check_managed_bots=health

    old_created=core._creator_on_managed_bot_created
    def created(msg):
        old_created(msg)
        info=((msg or {}).get("managed_bot_created") or {}).get("bot") or {}; bid=str(info.get("id") or "")
        if bid:
            d=get_dash(bid)
            if d:
                notify_owner(d,"🌐 <b>Dashboard Ready</b>\n\n🤖 @"+html.escape(str(d.get("username") or "unknown"))+
                    "\n🔗 <a href=\""+html.escape(dash_link(d),quote=True)+"\">Open Dashboard</a>"+
                    "\n👤 Login username: <b>@"+html.escape(str(d.get("username") or "unknown"))+"</b>"+
                    "\n🔐 Dashboard PIN: <code>"+html.escape(str(d.get("dashboard_pin_plain")))+"</code>\n\nUse <b>Save</b> so this device remembers the dashboard.")
    core._creator_on_managed_bot_created=created

    # ---------- Dashboard HTTP server ----------
    sessions=core.db1["dashboard_sessions"]

    def page(d):
        s=d.get("dashboard_settings") or defaults(); p=s.get("platforms") or {}; b=s.get("buttons") or {}
        prow="".join("<label><span>"+html.escape(k.title())+"</span><input type=\"checkbox\" data-p=\""+html.escape(k)+"\" "+("checked" if p.get(k,True) else "")+"></label>" for k in p)
        brow="".join("<label><span>"+html.escape(k.replace("_"," ").title())+"</span><input type=\"checkbox\" data-b=\""+html.escape(k)+"\" "+("checked" if b.get(k,True) else "")+"></label>" for k in b)
        bid=str(d.get("bot_id")); uname=str(d.get("username") or "bot")
        return """<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>QuickDL Dashboard</title><style>
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top,#1a3654,#07111f 60%,#03070d);color:#f7fbff;font:15px system-ui,Segoe UI,sans-serif}
.wrap{max-width:1100px;margin:auto;padding:22px}.glass{background:rgba(255,255,255,.09);border:1px solid rgba(255,255,255,.16);backdrop-filter:blur(20px);border-radius:24px;padding:20px;box-shadow:0 20px 70px #0007}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}label{display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid #ffffff18}
input,textarea,select{width:100%;padding:12px;border-radius:12px;border:1px solid #ffffff22;background:#07111f;color:white}input[type=checkbox]{width:auto}
button{border:0;border-radius:13px;padding:12px 16px;font-weight:800;background:#2387ff;color:white}.muted{opacity:.65}.ok{color:#80f2a0}.err{color:#ff9a9a}
#app{display:none}.row{display:flex;gap:10px;flex-wrap:wrap}</style></head><body><div class="wrap">
<div id="login" class="glass"><h1>🔐 Bot Dashboard</h1><p class="muted">Use the username and 6-digit PIN supplied by Creator Bot.</p>
<input id="u" placeholder="@botusername"><br><br><input id="pin" maxlength="6" inputmode="numeric" placeholder="Dashboard PIN"><br><br><button onclick="login()">Login</button><p id="m"></p></div>
<div id="app"><div class="glass"><h1>🤖 @""" + html.escape(uname) + """</h1><p class="muted">""" + html.escape(str(d.get("name") or "Downloader Bot")) + """</p><p>🟢 Connected</p></div><br>
<div class="grid"><div class="glass"><h2>🌐 Platforms</h2>""" + prow + """</div>
<div class="glass"><h2>🎛️ Buttons</h2>""" + brow + """</div>
<div class="glass"><h2>⚡ Download</h2><select id="q"><option value="best">Best available</option><option value="720">720p</option><option value="1080">1080p</option><option value="1440">1440p</option><option value="2160">2160p</option></select>
<label><span>Ads enabled</span><input id="ads" type="checkbox" """ + ("checked" if s.get("ads_enabled",True) else "") + """></label>
<label><span>Premium enabled</span><input id="pre" type="checkbox" """ + ("checked" if s.get("premium_enabled",True) else "") + """></label></div>
<div class="glass"><h2>✍️ Welcome message</h2><textarea id="w" rows="8">""" + html.escape(str(s.get("welcome_text") or "")) + """</textarea><p class="muted">Admin-locked fields cannot be changed here.</p>
<div class="row"><button onclick="save()">💾 Save</button><button onclick="logout()">Logout</button></div><p id="sm"></p></div></div></div></div>
<script>
const BID=""" + json.dumps(bid) + """;let tok=localStorage.getItem("quickdl_dash_"+BID)||"";
function show(){loginBox.style.display=tok?"none":"block";app.style.display=tok?"block":"none"}
async function api(path,data){let r=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json","X-Dashboard-Token":tok},body:JSON.stringify(data||{})});let j=await r.json();if(!r.ok)throw Error(j.error||"Request failed");return j}
async function login(){try{let u=document.getElementById("u").value.replace(/^@/,"").trim(),p=document.getElementById("pin").value.trim();let j=await api("/api/dashboard/login",{bot_id:BID,username:u,pin:p});tok=j.token;localStorage.setItem("quickdl_dash_"+BID,tok);show()}catch(e){m.innerHTML='<span class="err">'+e.message+"</span>"}}
async function save(){try{let platforms={},buttons={};document.querySelectorAll("[data-p]").forEach(x=>platforms[x.dataset.p]=x.checked);document.querySelectorAll("[data-b]").forEach(x=>buttons[x.dataset.b]=x.checked);await api("/api/dashboard/save",{bot_id:BID,settings:{platforms:platforms,buttons:buttons,ads_enabled:ads.checked,premium_enabled:pre.checked,default_quality:q.value,welcome_text:w.value}});sm.innerHTML='<span class="ok">✅ Saved</span>'}catch(e){sm.innerHTML='<span class="err">'+e.message+"</span>"}}
function logout(){localStorage.removeItem("quickdl_dash_"+BID);tok="";show()}const loginBox=document.getElementById("login"),app=document.getElementById("app");show();
</script></body></html>"""

    def json_out(h,code,obj):
        raw=json.dumps(obj,ensure_ascii=False).encode()
        h.send_response(code); h.send_header("Content-Type","application/json"); h.send_header("Cache-Control","no-store")
        h.send_header("Content-Length",str(len(raw))); h.end_headers(); h.wfile.write(raw)

    old_get=core._AdGateHandler.do_GET
    def do_get(h):
        path=urllib.parse.urlparse(h.path).path
        if path.startswith("/dashboard/"):
            bid=path.split("/",2)[2] if len(path.split("/",2))>2 else ""; d=get_dash(bid)
            if not d: h._send(404,"Dashboard not found."); return
            h._send(200,page(d)); return
        return old_get(h)
    core._AdGateHandler.do_GET=do_get

    def do_post(h):
        path=urllib.parse.urlparse(h.path).path
        try: n=int(h.headers.get("Content-Length","0")); data=json.loads(h.rfile.read(n) or b"{}")
        except Exception: json_out(h,400,{"error":"Invalid JSON"}); return
        if path=="/api/dashboard/login":
            d=get_dash(str(data.get("bot_id") or ""))
            if not d: json_out(h,404,{"error":"Dashboard not found"}); return
            u=str(data.get("username") or "").lstrip("@").lower(); pin=str(data.get("pin") or "")
            if u!=str(d.get("username") or "").lstrip("@").lower() or pin!=str(d.get("dashboard_pin_plain") or ""):
                json_out(h,401,{"error":"Invalid username or PIN"}); return
            tok=secrets.token_urlsafe(32); sessions.insert_one({"token_hash":hashlib.sha256(tok.encode()).hexdigest(),"owner_id":str(d.get("owner_id")),"bot_id":str(d.get("bot_id")),"created_at":now(),"last_seen_at":now()})
            json_out(h,200,{"ok":True,"token":tok}); return
        if path=="/api/dashboard/save":
            bid=str(data.get("bot_id") or ""); tok=h.headers.get("X-Dashboard-Token","")
            sd=sessions.find_one({"token_hash":hashlib.sha256(tok.encode()).hexdigest(),"bot_id":bid}); d=get_dash(bid)
            if not sd or not d or str(sd.get("owner_id"))!=str(d.get("owner_id")): json_out(h,401,{"error":"Session expired"}); return
            inc=data.get("settings") if isinstance(data.get("settings"),dict) else {}; cur=d.get("dashboard_settings") or defaults()
            locks=set(cur.get("locked_fields") or [])
            out=dict(cur)
            for k in ("ads_enabled","premium_enabled","default_quality","welcome_text"):
                if k in inc and k not in locks: out[k]=inc[k]
            for k in ("platforms","buttons"):
                if k not in locks and isinstance(inc.get(k),dict):
                    z=dict(out.get(k) or {}); z.update({str(a):bool(v) for a,v in inc[k].items()}); out[k]=z
            core.managed_bots_col.update_one({"bot_id":bid},{"$set":{"dashboard_settings":out,"updated_at":now()}})
            json_out(h,200,{"ok":True}); return
        json_out(h,404,{"error":"Not found"})
    core._AdGateHandler.do_POST=do_post

    # ---------- Premium media for each price ----------
    media_col=core.db1["premium_plan_media"]
    def media(months): return media_col.find_one({"_id":str(months)}) or {}
    def send_media(obj,chat_id,months):
        d=media(months); fid=str(d.get("file_id") or "")
        if not fid: return
        try:
            if d.get("type")=="video": obj.send_video(chat_id,fid,caption=d.get("caption") or "",parse_mode="HTML")
            else: obj.send_photo(chat_id,fid,caption=d.get("caption") or "",parse_mode="HTML")
        except Exception as e: print("premium media:",repr(e))

    # Main admin can upload one photo/video per plan.
    @core.bot.message_handler(func=lambda m: bool(m.text) and m.text=="💎 PREMIUM MEDIA")
    def premium_media_menu(m):
        if not is_admin(m.from_user.id): return
        kb=core.InlineKeyboardMarkup(row_width=2)
        for x in ("1","3","9","12"):
            d=media(x); kb.add(core.InlineKeyboardButton("💎 "+x+"M"+(" 📷" if d else ""),callback_data="v2media:"+x))
        core.bot.send_message(m.chat.id,"💎 <b>PREMIUM PLAN MEDIA</b>\n\nChoose a plan, then send its photo or video.",parse_mode="HTML",reply_markup=kb)

    @core.bot.callback_query_handler(func=lambda c: str(c.data or "").startswith("v2media:"))
    def premium_media_pick(c):
        if not is_admin(c.from_user.id): core.bot.answer_callback_query(c.id,"Admin only",show_alert=True); return
        x=str(c.data).split(":",1)[1]; core._creator_set_session(str(c.from_user.id),{"state":"admin_premium_media","months":x})
        core.bot.answer_callback_query(c.id); core.bot.send_message(c.message.chat.id,"📷 <b>Premium "+html.escape(x)+" month(s)</b>\n\nSend a photo or video now.",parse_mode="HTML")

    @core.bot.message_handler(content_types=["photo","video"])
    def premium_media_receive(m):
        uid=str(m.from_user.id); st=core._creator_session(uid)
        if not is_admin(uid) or st.get("state")!="admin_premium_media": return
        x=str(st.get("months") or ""); fid=m.photo[-1].file_id if getattr(m,"photo",None) else m.video.file_id
        typ="photo" if getattr(m,"photo",None) else "video"
        media_col.update_one({"_id":x},{"$set":{"file_id":fid,"type":typ,"caption":"💎 Premium — "+x+" month(s)","updated_at":now()}},upsert=True)
        core._creator_clear_session(uid); core.bot.send_message(m.chat.id,"✅ <b>Premium "+x+"-month media saved.</b>",reply_markup=core.admin_menu())

    def premium_plans(obj,c,token):
        row=core.ad_gates_col.find_one({"token":str(token)})
        if not row or str(row.get("user_id"))!=str(c.from_user.id):
            obj.answer_callback_query(c.id,"Invalid ad session.",show_alert=True); return
        plans=core.get_premium_prices(); rows=[]
        for x in ("1","3","9","12"):
            if x in plans: rows.append([core.InlineKeyboardButton("💎 "+x+" Month — $"+format(float(plans[x]),".2f"),callback_data="v2prem:"+token+":"+x)])
        rows.append([core.InlineKeyboardButton("⬅️ Back",callback_data="adpremium:"+token)])
        obj.answer_callback_query(c.id)
        obj.edit_message_text(c.message.chat.id,c.message.message_id,"💎 <b>PREMIUM</b>\n\nChoose a Premium period.\n\n"+
            "\n".join("• <b>"+x+" month(s)</b> — $"+format(float(plans[x]),".2f") for x in ("1","3","9","12") if x in plans)+
            "\n\nPayment is handled by <b>@Downloadvedioytibot</b> with Telegram Stars.",parse_mode="HTML",reply_markup=core.InlineKeyboardMarkup(rows))
    core._show_ad_premium_plans=premium_plans

    @core.bot.callback_query_handler(func=lambda c: str(c.data or "").startswith("v2prem:"))
    def v2prem(c):
        p=str(c.data).split(":"); token=p[1] if len(p)>1 else ""; months=p[2] if len(p)>2 else ""
        row=core.ad_gates_col.find_one({"token":token})
        if not row or str(row.get("user_id"))!=str(c.from_user.id): core.bot.answer_callback_query(c.id,"Invalid session.",show_alert=True); return
        try:
            link,stars=core._create_ad_premium_invoice(token,str(c.from_user.id),str(row.get("bot_id") or "main"),months)
            send_media(core.bot,c.message.chat.id,months)
            core.bot.answer_callback_query(c.id,"Invoice ready")
            core.bot.send_message(c.message.chat.id,"💎 <b>Premium — "+html.escape(months)+" month(s)</b>\n\n⭐ Price: <b>"+str(stars)+" Stars</b>\n\nPremium activates automatically after successful payment.",parse_mode="HTML",reply_markup=core.InlineKeyboardMarkup([[core.InlineKeyboardButton("⭐ PAY NOW",url=link)]]))
        except Exception as e: print("premium invoice v2:",repr(e)); core.bot.answer_callback_query(c.id,"Could not create invoice.",show_alert=True)

    # ---------- Main admin menu additions ----------
    old_admin_menu=core.admin_menu
    def admin_menu_v2():
        kb=old_admin_menu()
        try: kb.add("💎 PREMIUM MEDIA","🌐 DASHBOARD CONTROL")
        except Exception: pass
        try: kb.add("🗑 Delete Last Broadcast","🗑 Delete 2 Last Broadcast")
        except Exception: pass
        return kb
    core.admin_menu=admin_menu_v2

    @core.bot.message_handler(func=lambda m: bool(m.text) and m.text=="🌐 DASHBOARD CONTROL")
    def dashboard_control(m):
        if not is_admin(m.from_user.id): return
        locks=core.get_setting("dashboard_locked_fields",[])
        core.bot.send_message(m.chat.id,"🌐 <b>DASHBOARD CONTROL</b>\n\nCurrent locks: <code>"+html.escape(json.dumps(locks,ensure_ascii=False))+"</code>\n\nSend a JSON array to replace them, e.g. <code>[\"ads_enabled\",\"premium_enabled\"]</code>.",parse_mode="HTML")
        core._creator_set_session(str(m.from_user.id),{"state":"admin_dashboard_locks"})

    @core.bot.message_handler(func=lambda m: bool(m.text) and is_admin(m.from_user.id) and core._creator_session(str(m.from_user.id)).get("state")=="admin_dashboard_locks")
    def dashboard_lock_receive(m):
        try:
            x=json.loads((m.text or "").strip())
            if not isinstance(x,list): raise ValueError
            core.set_setting("dashboard_locked_fields",[str(v) for v in x]); core._creator_clear_session(str(m.from_user.id))
            core.bot.send_message(m.chat.id,"✅ <b>Dashboard locks updated.</b>",reply_markup=core.admin_menu())
        except Exception: core.bot.send_message(m.chat.id,"❌ Invalid JSON array.")

    # Broadcast deletion store. New broadcast implementations can call core._record_broadcast_message.
    bcol=core.db1["broadcast_history"]
    def record_broadcast(admin_id,chat_id,message_id):
        if is_admin(admin_id):
            bcol.insert_one({"admin_id":str(admin_id),"chat_id":int(chat_id),"message_id":int(message_id),"created_at":now()})
    core._record_broadcast_message=record_broadcast

    def delete_broadcasts(n,m):
        if not is_admin(m.from_user.id): return
        rows=list(bcol.find({"admin_id":str(m.from_user.id)}).sort("created_at",-1).limit(n)); deleted=0
        for r in rows:
            try: core.bot.delete_message(int(r["chat_id"]),int(r["message_id"])); deleted+=1
            except Exception: pass
        if rows: bcol.delete_many({"_id":{"$in":[r["_id"] for r in rows]}})
        core.bot.send_message(m.chat.id,"🗑 <b>Broadcast deletion</b>\n\nDeleted: <b>"+str(deleted)+"</b> message(s).")
    @core.bot.message_handler(func=lambda m: bool(m.text) and m.text=="🗑 Delete Last Broadcast")
    def delete_last(m): delete_broadcasts(1,m)
    @core.bot.message_handler(func=lambda m: bool(m.text) and m.text=="🗑 Delete 2 Last Broadcast")
    def delete_two(m): delete_broadcasts(2,m)

    # Persist dashboard credentials for all current bots.
    try:
        for d in core.managed_bots_col.find({}): ensure_dashboard(d)
    except Exception as e: print("dashboard migration:",repr(e))

    return core
