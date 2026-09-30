import os,json,time,secrets,hashlib,html,base64,io,urllib.parse
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor

def apply(core):
    # v10 is additive: creator_v2 remains the source of the managed-bot flow,
    # while this layer adds manual-token entry, premium dashboard controls,
    # owner customization, dashboard broadcast/security, and runtime enforcement.
    now=lambda: datetime.now(timezone.utc)
    sessions=core.db1["dashboard_sessions"]

    def defaults(d):
        s=d.get("dashboard_settings") if isinstance(d.get("dashboard_settings"),dict) else {}
        s=dict(s)
        s.setdefault("ads_enabled",True)
        s.setdefault("premium_enabled",True)
        s.setdefault("default_quality","best")
        s.setdefault("welcome_text","")
        s.setdefault("speed_mode","normal")
        s.setdefault("youtube_max_minutes",0)
        s.setdefault("profile_name",str(d.get("name") or "Downloader Bot"))
        s.setdefault("short_description","")
        s.setdefault("description","")
        plats={"youtube","tiktok","instagram","facebook","pinterest","snapchat","twitter","reddit","threads","likee","vimeo","dailymotion","soundcloud","twitch","tumblr","streamable","odnoklassniki"}
        p=dict(s.get("platforms") or {})
        for x in plats:p.setdefault(x,True)
        s["platforms"]=p
        b=dict(s.get("buttons") or {})
        for x in ("create","remove_ads","admin","powered_by","premium","music"):b.setdefault(x,True)
        s["buttons"]=b
        s.setdefault("locked_fields",list(core.get_setting("dashboard_locked_fields",[]) or []))
        return s

    def dash(bid):
        d=core.managed_bots_col.find_one({"bot_id":str(bid)}) or {}
        if not d:return None
        s=defaults(d)
        core.managed_bots_col.update_one({"bot_id":str(bid)},{"$set":{"dashboard_settings":s}})
        d["dashboard_settings"]=s
        return d

    def premium(d):
        try:return bool(core._managed_premium_active_doc(d))
        except Exception:return False

    def locks(d):
        s=defaults(d); return set(s.get("locked_fields") or []) | set(core.get_setting("dashboard_locked_fields",[]) or [])

    def locked(d,k):
        l=locks(d)
        return k in l or (k in {"platforms","buttons"} and ("dashboard_settings" in l or "all_settings" in l))

    def require_premium(d,k=None):
        return premium(d) or (k is not None and locked(d,k))

    def owner_session(h,bid):
        tok=str(h.headers.get("X-Dashboard-Token","") or "")
        if not tok:return None,None
        sd=sessions.find_one({"token_hash":hashlib.sha256(tok.encode()).hexdigest(),"bot_id":str(bid)})
        d=dash(bid)
        if not sd or not d or str(sd.get("owner_id"))!=str(d.get("owner_id")):return None,d
        sessions.update_one({"_id":sd["_id"]},{"$set":{"last_seen_at":now()}})
        return sd,d

    def jout(h,code,obj):
        raw=json.dumps(obj,ensure_ascii=False).encode()
        h.send_response(code);h.send_header("Content-Type","application/json");h.send_header("Cache-Control","no-store");h.send_header("Content-Length",str(len(raw)));h.end_headers();h.wfile.write(raw)

    def avatar(h,bid):
        d=dash(bid); token=core._decrypt_managed_token(d or {})
        if not token:h._send(404,"")
        else:
            try:
                a=core.requests.post("https://api.telegram.org/bot"+token+"/getUserProfilePhotos",json={"user_id":int(bid),"limit":1},timeout=10).json()
                photos=((a.get("result") or {}).get("photos") or [])
                if not photos:h._send(404,"");return
                fid=photos[0][-1].get("file_id"); f=core.requests.post("https://api.telegram.org/bot"+token+"/getFile",json={"file_id":fid},timeout=10).json()
                fp=(f.get("result") or {}).get("file_path")
                if not fp:h._send(404,"");return
                rr=core.requests.get("https://api.telegram.org/file/bot"+token+"/"+fp,timeout=15)
                if rr.status_code!=200:h._send(404,"");return
                h._send(200,rr.content,"image/jpeg")
            except Exception:h._send(404,"")

    def invoice(bid,months):
        d=dash(bid); plans=core.get_premium_prices(); m=str(months)
        if not d or m not in plans:return None
        rate=max(1,int(core.get_setting("stars_per_usd",100) or 100)); stars=max(1,int(round(float(plans[m])*rate)))
        payload="managed_creator_premium_stars:"+str(bid)+":"+m+":"+str(stars)
        body={"title":"Downloader Premium — "+m+" month(s)","description":"Premium controls for @"+str(d.get("username") or "DownloaderBot")+" for "+m+" month(s).","payload":payload,"provider_token":"","currency":"XTR","prices":[{"label":"Premium "+m+" month(s)","amount":stars}]}
        rr=core.requests.post("https://api.telegram.org/bot"+str(core.TOKEN)+"/createInvoiceLink",json=body,timeout=20)
        j=rr.json() if rr.content else {}
        return {"url":str(j.get("result") or ""), "stars":stars, "usd":float(plans[m])} if j.get("ok") and j.get("result") else None

    def page(d):
        s=defaults(d); prem=premium(d); lk=locks(d); bid=str(d.get("bot_id")); uname=str(d.get("username") or "bot")
        plans=core.get_premium_prices(); rate=max(1,int(core.get_setting("stars_per_usd",100) or 100))
        plan_buttons=[]
        for m in ("1","3","9","12"):
            if m in plans:
                iv=invoice(bid,m)
                if iv:plan_buttons.append("<a class='plan' href='"+html.escape(iv["url"],quote=True)+"'>💎 "+m+" Month · "+str(iv["stars"])+" ⭐</a>")
        pchecks="".join("<label><span>"+html.escape(k.title())+"</span><input data-p='"+html.escape(k)+"' type='checkbox' "+("checked" if s["platforms"].get(k,True) else "")+(" disabled" if (not prem or locked(d,"platforms")) else "")+"></label>" for k in sorted(s["platforms"]))
        bchecks="".join("<label><span>"+html.escape(k.replace("_"," ").title())+"</span><input data-b='"+html.escape(k)+"' type='checkbox' "+("checked" if s["buttons"].get(k,True) else "")+(" disabled" if (not prem or locked(d,"buttons")) else "")+"></label>" for k in s["buttons"])
        disabled="" if prem else "disabled"
        return """<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>QuickDL Dashboard</title>
<style>
:root{--bg:#06101d;--card:rgba(18,35,54,.72);--line:#ffffff1d;--txt:#f5f9ff;--muted:#91a4ba;--accent:#5ea8ff;--good:#66e6a0;--danger:#ff7777}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 10% 0,#173e67 0,#071322 42%,#03070d 100%);color:var(--txt);font:15px Inter,system-ui,sans-serif;min-height:100vh}
.wrap{max-width:1180px;margin:auto;padding:20px}.glass{background:var(--card);border:1px solid var(--line);backdrop-filter:blur(22px);border-radius:26px;padding:20px;box-shadow:0 22px 80px #0008}.top{display:flex;align-items:center;gap:15px}.avatar{width:72px;height:72px;border-radius:22px;object-fit:cover;background:#122235;border:1px solid var(--line)}h1,h2{margin:0 0 8px}.muted{color:var(--muted)}.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}.tabs button,.btn{border:0;border-radius:14px;padding:11px 15px;background:#1b3552;color:white;font-weight:800;cursor:pointer}.tabs button.active,.btn.primary{background:linear-gradient(135deg,#4d9fff,#7c6cff)}.tab{display:none}.tab.active{display:block}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}.row{display:flex;gap:10px;flex-wrap:wrap}.field{margin:10px 0}.field label{display:block;margin-bottom:6px;color:#cbd8e8}input[type=text],input[type=number],textarea,select{width:100%;padding:12px;border:1px solid var(--line);border-radius:13px;background:#06111e;color:white}input[type=checkbox]{width:auto}.checks label{display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid #ffffff10}.notice{padding:13px;border-radius:15px;background:#ffffff09;border:1px solid var(--line);margin:10px 0}.premium{border-color:#7f6cff66;background:linear-gradient(135deg,#38235d88,#10274488)}.plan{display:block;text-decoration:none;color:white;background:#ffffff10;border:1px solid var(--line);border-radius:14px;padding:13px;margin:8px 0}.locked{opacity:.58}.status{font-weight:800}.good{color:var(--good)}.bad{color:var(--danger)}video{width:100%;max-height:300px;border-radius:18px;background:#02060b}.small{font-size:12px;color:var(--muted)}#login{max-width:460px;margin:8vh auto}.hidden{display:none}.danger{background:#7c2029}.section{margin-top:14px}
</style></head><body><div class='wrap'>
<div id='login' class='glass'><h1>🔐 Bot Dashboard</h1><p class='muted'>Login with the username and private 6-digit PIN sent by Creator Bot.</p><div class='field'><input id='u' placeholder='@botusername'></div><div class='field'><input id='pin' maxlength='6' inputmode='numeric' placeholder='Dashboard PIN'></div><button class='btn primary' onclick='login()'>Open Dashboard</button><p id='lm'></p></div>
<div id='app' class='hidden'>
<div class='glass top'><img class='avatar' src='/dashboard/""" + html.escape(bid) + """/avatar' onerror="this.style.display='none'"><div><h1>🤖 @""" + html.escape(uname) + """</h1><div class='muted'>""" + html.escape(str(d.get("name") or "Downloader Bot")) + """</div><div class='status good'>● Connected</div></div><div style='margin-left:auto' class='small'>""" + ("💎 Premium active" if prem else "🆓 Free dashboard") + """</div></div>
<div class='tabs'><button class='active' onclick="tab('home',this)">Overview</button><button onclick="tab('custom',this)">Customize</button><button onclick="tab('premium',this)">💎 Premium</button><button onclick="tab('broadcast',this)">📢 Broadcast</button><button onclick="tab('security',this)">🔐 Security</button></div>
<section id='home' class='tab active'><div class='grid'>
<div class='glass'><h2>⚡ Bot control</h2><p>Manage your Downloader Bot without touching the source code.</p><div class='notice'>Username: <b>@""" + html.escape(uname) + """</b><br>Dashboard: <span class='small'>/dashboard/""" + html.escape(bid) + """</span></div><video controls muted playsinline preload='metadata'><source src='/dashboard-demo.mp4' type='video/mp4'></video><p class='small'>5-second dashboard preview.</p></div>
<div class='glass'><h2>✨ Premium benefits</h2><p>Premium unlocks the controls below.</p><div>✅ Remove mandatory ads<br>✅ Hide Powered by<br>✅ Choose bot speed<br>✅ Choose YouTube minute limit / unlimited<br>✅ Customize profile, Bio and /start<br>✅ Platform and button controls</div></div>
</div></section>
<section id='custom' class='tab'><div class='grid'>
<div class='glass """ + ("" if prem else "locked") + """'><h2>🎨 Profile & /start</h2><div class='field'><label>Bot name</label><input id='name' value='""" + html.escape(str(s.get("profile_name") or d.get("name") or ""),quote=True) + """' """+disabled+"""></div><div class='field'><label>Short Bio / About (120 chars)</label><input id='short' maxlength='120' value='""" + html.escape(str(s.get("short_description") or ""),quote=True) + """' """+disabled+"""></div><div class='field'><label>Bot Description (512 chars)</label><textarea id='desc' maxlength='512' rows='5' """+disabled+""">""" + html.escape(str(s.get("description") or "")) + """</textarea></div><div class='field'><label>/start message</label><textarea id='welcome' rows='6' """+disabled+""">""" + html.escape(str(s.get("welcome_text") or "")) + """</textarea></div><div class='row'><button class='btn' onclick='saveProfile()' """+disabled+""">💾 Save profile</button><label class='btn'>🖼 Change photo<input id='photo' type='file' accept='image/jpeg,image/png' style='display:none' onchange='uploadPhoto()' """+disabled+"""></label><button class='btn danger' onclick='removePhoto()' """+disabled+""">Remove photo</button></div><p class='small'>Telegram supports bot name, about/short description, description and profile-photo management. Admin locks always win.</p></div>
<div class='glass """ + ("" if prem else "locked") + """'><h2>🌐 Platforms</h2><div class='checks'>""" + pchecks + """</div></div>
<div class='glass """ + ("" if prem else "locked") + """'><h2>🎛 Buttons</h2><div class='checks'>""" + bchecks + """</div></div>
<div class='glass """ + ("" if prem else "locked") + """'><h2>⚡ Download controls</h2><div class='field'><label>Quality</label><select id='q' """+disabled+"""><option value='best'>Best available</option><option value='720'>720p</option><option value='1080'>1080p</option><option value='1440'>1440p</option><option value='2160'>2160p</option></select></div><label class='checks'><span>Ads enabled</span><input id='ads' type='checkbox' """ + ("checked" if s.get("ads_enabled",True) else "") + """ """+disabled+"""></label><div class='field'><label>Bot speed</label><select id='speed' """+disabled+"""><option value='normal' """+("selected" if s.get("speed_mode")=="normal" else "")+""">Normal</option><option value='fast' """+("selected" if s.get("speed_mode")=="fast" else "")+""">Fast</option><option value='turbo' """+("selected" if s.get("speed_mode")=="turbo" else "")+""">Turbo</option></select></div><div class='field'><label>YouTube maximum minutes (0 = unlimited)</label><input id='ytm' type='number' min='0' max='1440' value='""" + str(int(s.get("youtube_max_minutes") or 0)) + """' """+disabled+"""></div><label class='checks'><span>Premium feature switch</span><input id='pre' type='checkbox' """+("checked" if s.get("premium_enabled",True) else "")+""" """+disabled+"""></label><p class='small'>Free users can view these controls but cannot change them.</p><button class='btn primary' onclick='saveSettings()' """+disabled+""">💾 Save settings</button><p id='sm'></p></div>
</div></section>
<section id='premium' class='tab'><div class='grid'><div class='glass premium'><h2>💎 Premium Center</h2>""" + (("<div class='notice good'>Premium is active until <b>"+html.escape(str(d.get("premium_until") or ""))+"</b>.</div><p>All premium dashboard controls are unlocked unless the main admin locked them.</p>") if prem else "<div class='notice'>Premium is not active. Dashboard customization is locked.</div><p>Choose a plan. Payment opens directly in Telegram through a Telegram Stars invoice link.</p>") + "".join(plan_buttons) + """</div><div class='glass'><h2>🔒 Main Admin rules</h2><p>Admin-defined locks cannot be bypassed from this dashboard.</p><div class='small'>Locked: """ + html.escape(", ".join(sorted(lk)) or "None") + """</div></div></div></section>
<section id='broadcast' class='tab'><div class='glass'><h2>📢 Broadcast</h2><p class='muted'>Send a text broadcast to users of this Downloader Bot.</p><textarea id='bcast' rows='8' placeholder='Write your message...'></textarea><button class='btn primary' onclick='broadcast()'>Send Broadcast</button><p id='bm'></p></div></section>
<section id='security' class='tab'><div class='grid'><div class='glass'><h2>🔐 Dashboard security</h2><p>Your dashboard username is <b>@""" + html.escape(uname) + """</b>.</p><button class='btn' onclick='rotatePin()'>♻️ Generate New PIN</button><p id='pm'></p></div><div class='glass danger'><h2>♻️ Managed Bot Token</h2><p>Revoking replaces the managed bot token. Telegram sends the manager a managed_bot update so the Creator Bot can fetch the new token and restart the bot.</p><button class='btn danger' onclick='revokeToken()'>♻️ Revoke & Generate New Token</button><p id='rm'></p></div></div></section>
</div></div>
<script>
const BID=""" + json.dumps(bid) + """;let tok=localStorage.getItem('quickdl_dash_'+BID)||'';const $=x=>document.getElementById(x);
function tab(id,b){document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));$(id).classList.add('active');document.querySelectorAll('.tabs button').forEach(x=>x.classList.remove('active'));if(b)b.classList.add('active')}
function show(){ $('login').classList.toggle('hidden',!!tok); $('app').classList.toggle('hidden',!tok)}
async function api(path,data){let r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Dashboard-Token':tok},body:JSON.stringify(data||{})});let j=await r.json();if(!r.ok)throw Error(j.error||'Request failed');return j}
async function login(){try{let j=await api('/api/dashboard/login',{bot_id:BID,username:$('u').value.replace(/^@/,'').trim(),pin:$('pin').value.trim()});tok=j.token;localStorage.setItem('quickdl_dash_'+BID,tok);show()}catch(e){$('lm').textContent=e.message}}
async function saveProfile(){try{await api('/api/dashboard/profile',{bot_id:BID,name:$('name').value,short_description:$('short').value,description:$('desc').value,welcome_text:$('welcome').value});$('sm').textContent='✅ Profile saved'}catch(e){$('sm').textContent=e.message}}
async function saveSettings(){try{let platforms={},buttons={};document.querySelectorAll('[data-p]').forEach(x=>platforms[x.dataset.p]=x.checked);document.querySelectorAll('[data-b]').forEach(x=>buttons[x.dataset.b]=x.checked);await api('/api/dashboard/save',{bot_id:BID,settings:{platforms:platforms,buttons:buttons,ads_enabled:$('ads').checked,default_quality:$('q').value,speed_mode:$('speed').value,youtube_max_minutes:parseInt($('ytm').value||0),premium_enabled:$('pre').checked,welcome_text:$('welcome').value}});$('sm').textContent='✅ Settings saved'}catch(e){$('sm').textContent=e.message}}
async function uploadPhoto(){let f=$('photo').files[0];if(!f)return;let rd=new FileReader();rd.onload=async()=>{try{await api('/api/dashboard/profile-photo',{bot_id:BID,data:rd.result});location.reload()}catch(e){alert(e.message)}};rd.readAsDataURL(f)}
async function removePhoto(){try{await api('/api/dashboard/remove-photo',{bot_id:BID});location.reload()}catch(e){alert(e.message)}}
async function broadcast(){try{let j=await api('/api/dashboard/broadcast',{bot_id:BID,text:$('bcast').value});$('bm').textContent='✅ Sent '+j.sent+' · Failed '+j.failed}catch(e){$('bm').textContent=e.message}}
async function rotatePin(){try{let j=await api('/api/dashboard/rotate-pin',{bot_id:BID});$('pm').innerHTML='✅ New PIN: <b>'+j.pin+'</b>';localStorage.removeItem('quickdl_dash_'+BID);tok='';show()}catch(e){$('pm').textContent=e.message}}
async function revokeToken(){if(!confirm('Revoke the current managed-bot token and generate a new one?'))return;try{await api('/api/dashboard/revoke-token',{bot_id:BID});$('rm').textContent='✅ Revoke requested. Creator Bot will receive the new token and restart the bot.'}catch(e){$('rm').textContent=e.message}}
show();
</script></body></html>"""

    old_get=core._AdGateHandler.do_GET
    def do_get(h):
        path=urllib.parse.urlparse(h.path).path
        if path=="/dashboard-demo.mp4":
            # The actual demo file can be supplied later by the deployment image.
            # Keep a clean fallback response instead of breaking the dashboard.
            return old_get(h)
        if path.startswith("/dashboard/") and path.endswith("/avatar"):
            bid=path.strip("/").split("/")[1] if len(path.strip("/").split("/"))>=2 else ""; return avatar(h,bid)
        if path.startswith("/dashboard/"):
            bid=path.strip("/").split("/")[1] if len(path.strip("/").split("/"))>=2 else ""; d=dash(bid)
            if not d:h._send(404,"Dashboard not found.");return
            h._send(200,page(d));return
        return old_get(h)
    core._AdGateHandler.do_GET=do_get

    old_post=core._AdGateHandler.do_POST
    def do_post(h):
        path=urllib.parse.urlparse(h.path).path
        if not path.startswith("/api/dashboard/"):return old_post(h)
        try:
            n=int(h.headers.get("Content-Length","0")); body=h.rfile.read(n); data=json.loads(body or b"{}")
        except Exception:jout(h,400,{"error":"Invalid JSON"});return
        bid=str(data.get("bot_id") or ""); sd,d=owner_session(h,bid)
        if path=="/api/dashboard/login":
            d=dash(bid)
            if not d:jout(h,404,{"error":"Dashboard not found"});return
            u=str(data.get("username") or "").lstrip("@").lower();pin=str(data.get("pin") or "")
            if u!=str(d.get("username") or "").lstrip("@").lower() or pin!=str(d.get("dashboard_pin_plain") or ""):jout(h,401,{"error":"Invalid username or PIN"});return
            tok=secrets.token_urlsafe(32);sessions.insert_one({"token_hash":hashlib.sha256(tok.encode()).hexdigest(),"owner_id":str(d.get("owner_id")),"bot_id":bid,"created_at":now(),"last_seen_at":now()});jout(h,200,{"ok":True,"token":tok});return
        if not sd or not d:jout(h,401,{"error":"Session expired"});return
        if path=="/api/dashboard/save":
            inc=data.get("settings") if isinstance(data.get("settings"),dict) else {}
            if not premium(d):jout(h,402,{"error":"💎 Premium is required to change dashboard settings."});return
            cur=defaults(d);out=dict(cur); 
            for k in ("ads_enabled","premium_enabled","default_quality","speed_mode","youtube_max_minutes","welcome_text"):
                if k in inc and not locked(d,k):out[k]=inc[k]
            if isinstance(inc.get("platforms"),dict) and not locked(d,"platforms"):
                z=dict(out["platforms"]);z.update({str(a):bool(v) for a,v in inc["platforms"].items()});out["platforms"]=z
            if isinstance(inc.get("buttons"),dict) and not locked(d,"buttons"):
                z=dict(out["buttons"]);z.update({str(a):bool(v) for a,v in inc["buttons"].items()});out["buttons"]=z
            out["youtube_max_minutes"]=max(0,min(1440,int(out.get("youtube_max_minutes") or 0)))
            core.managed_bots_col.update_one({"bot_id":bid},{"$set":{"dashboard_settings":out,"updated_at":now()}})
            jout(h,200,{"ok":True});return
        if path=="/api/dashboard/profile":
            if not premium(d):jout(h,402,{"error":"💎 Premium is required for profile customization."});return
            if not locked(d,"bio"):
                name=str(data.get("name") or "").strip()[:64]; short=str(data.get("short_description") or "").strip()[:120]; desc=str(data.get("description") or "").strip()[:512]
                token=core._decrypt_managed_token(d)
                if token:
                    for method,payload in (("setMyName",{"name":name}),("setMyShortDescription",{"short_description":short}),("setMyDescription",{"description":desc})):
                        rr=core.requests.post("https://api.telegram.org/bot"+token+"/"+method,json=payload,timeout=15).json()
                        if not rr.get("ok"):jout(h,400,{"error":rr.get("description") or method+" failed"});return
                core.managed_bots_col.update_one({"bot_id":bid},{"$set":{"name":name,"dashboard_settings.profile_name":name,"dashboard_settings.short_description":short,"dashboard_settings.description":desc,"dashboard_settings.welcome_text":str(data.get("welcome_text") or "")[:4096],"updated_at":now()}})
                jout(h,200,{"ok":True});return
            jout(h,403,{"error":"🔒 Profile fields are locked by the main admin."});return
        if path=="/api/dashboard/profile-photo":
            if not premium(d):jout(h,402,{"error":"💎 Premium is required for profile photo changes."});return
            if locked(d,"profile_photo"):jout(h,403,{"error":"🔒 Profile photo is locked by the main admin."});return
            raw=str(data.get("data") or "")
            if "," in raw:raw=raw.split(",",1)[1]
            try:blob=base64.b64decode(raw,validate=True)
            except Exception:jout(h,400,{"error":"Invalid image"});return
            if len(blob)>5*1024*1024:jout(h,413,{"error":"Image is too large (max 5MB)."});return
            try:
                from PIL import Image
                im=Image.open(io.BytesIO(blob)).convert("RGB"); buf=io.BytesIO();im.save(buf,"JPEG",quality=90,optimize=True);blob=buf.getvalue()
            except Exception:jout(h,400,{"error":"Please upload a valid JPG/PNG image."});return
            token=core._decrypt_managed_token(d)
            rr=core.requests.post("https://api.telegram.org/bot"+token+"/setMyProfilePhoto",data={"photo":json.dumps({"type":"static","photo":"attach://profile_photo"})},files={"profile_photo":("profile.jpg",blob,"image/jpeg")},timeout=30)
            j=rr.json() if rr.content else {}
            if not j.get("ok"):jout(h,400,{"error":j.get("description") or "Telegram rejected the profile photo."});return
            jout(h,200,{"ok":True});return
        if path=="/api/dashboard/remove-photo":
            if not premium(d):jout(h,402,{"error":"💎 Premium is required for profile photo changes."});return
            if locked(d,"profile_photo"):jout(h,403,{"error":"🔒 Profile photo is locked by the main admin."});return
            token=core._decrypt_managed_token(d);j=core.requests.post("https://api.telegram.org/bot"+token+"/removeMyProfilePhoto",json={},timeout=15).json()
            if not j.get("ok"):jout(h,400,{"error":j.get("description") or "Telegram rejected the request."});return
            jout(h,200,{"ok":True});return
        if path=="/api/dashboard/broadcast":
            text=str(data.get("text") or "").strip()
            if not text:jout(h,400,{"error":"Write a broadcast message first."});return
            mb=core.managed_bot_objects.get(bid) or core._managed_bot_start_instance(d)
            if not mb:jout(h,503,{"error":"Bot is not running."});return
            targets=list(d.get("users") or []);sent=failed=0
            for uid in targets:
                try:mb.send_message(int(uid),text,parse_mode="HTML");sent+=1
                except Exception:failed+=1
            jout(h,200,{"ok":True,"sent":sent,"failed":failed});return
        if path=="/api/dashboard/rotate-pin":
            pin=str(secrets.randbelow(1000000)).zfill(6);sessions.delete_many({"bot_id":bid});core.managed_bots_col.update_one({"bot_id":bid},{"$set":{"dashboard_pin_plain":pin,"dashboard_pin_hash":hashlib.sha256(pin.encode()).hexdigest()}});jout(h,200,{"ok":True,"pin":pin});return
        if path=="/api/dashboard/revoke-token":
            try:
                fresh,err=core._creator_api("replaceManagedBotToken",{"user_id":int(bid)},timeout=20)
                if err:raise RuntimeError(err)
                jout(h,200,{"ok":True});return
            except Exception as e:jout(h,400,{"error":"Could not revoke token: "+str(e)});return
        jout(h,404,{"error":"Not found"})
    core._AdGateHandler.do_POST=do_post

    # Fix the v9 inversion: ads_enabled=False means ads are OFF and therefore no ad gate.
    old_ad=core._ad_enabled_for
    def ad_enabled(uid,bid=None):
        meta=core._ACTIVE_MANAGED_META.get() or {}; mbid=str(meta.get("bot_id") or bid or "")
        if mbid and mbid!="main":
            d=dash(mbid); s=defaults(d or {})
            if s.get("ads_enabled",True) is False:return True
        return old_ad(uid,bid)
    core._ad_enabled_for=ad_enabled

    # Premium dashboard controls: YouTube duration and downloader concurrency/speed.
    old_limit=core._download_limit_seconds
    def limit(uid):
        meta=core._ACTIVE_MANAGED_META.get() or {};bid=str(meta.get("bot_id") or "")
        if bid:
            d=dash(bid);s=defaults(d or {})
            if premium(d) and not locked(d,"youtube_max_minutes"):
                m=int(s.get("youtube_max_minutes") or 0)
                if m<=0:return 3650*24*60*60
                return max(1,min(1440,m))*60
        return old_limit(uid)
    core._download_limit_seconds=limit

    old_exec=core.download_executor_for
    speed_exec={}
    def executor(uid):
        meta=core._ACTIVE_MANAGED_META.get() or {};bid=str(meta.get("bot_id") or "")
        if bid:
            d=dash(bid);s=defaults(d or {})
            if premium(d):
                mode=str(s.get("speed_mode") or "normal")
                workers={"normal":8,"fast":20,"turbo":40}.get(mode,8)
                ex=speed_exec.get(bid)
                if ex is None or getattr(ex,"_quickdl_workers",0)!=workers:
                    ex=ThreadPoolExecutor(max_workers=workers);ex._quickdl_workers=workers;speed_exec[bid]=ex
                return ex
        return old_exec(uid)
    core.download_executor_for=executor

    # Owner can revoke from inside the managed bot; the Creator Bot receives the
    # official managed_bot update and refreshes the stored token.
    old_start=core._managed_bot_start_instance
    def start(doc):
        mb=old_start(doc)
        if not mb:return mb
        if getattr(mb,"_quickdl_v10_security",False):return mb
        bid=str(doc.get("bot_id") or "")
        owner=str(doc.get("owner_id") or "")
        @mb.callback_query_handler(func=lambda c:str(c.data or "").startswith("mrevokec:"))
        def confirm(c):
            if str(c.from_user.id)!=owner:mb.answer_callback_query(c.id,"Owner only.",show_alert=True);return
            parts=str(c.data).split(":");action=parts[1] if len(parts)>1 else ""
            if action=="ask":
                mb.answer_callback_query(c.id)
                mb.edit_message_text(c.message.chat.id,c.message.message_id,"⚠️ <b>REVOKE BOT TOKEN?</b>\n\nTelegram will generate a new managed token. Creator Bot will save it and restart this Downloader Bot.",parse_mode="HTML",reply_markup=core.InlineKeyboardMarkup([[core.InlineKeyboardButton("✅ Confirm Revoke",callback_data=f"mrevokec:yes:{bid}")],[core.InlineKeyboardButton("⬅️ Cancel",callback_data=f"mrevokec:no:{bid}")]]));return
            if action=="no":mb.answer_callback_query(c.id,"Cancelled");return
            fresh,err=core._creator_api("replaceManagedBotToken",{"user_id":int(bid)},timeout=20)
            if err:mb.answer_callback_query(c.id,"Telegram rejected the revoke.",show_alert=True);return
            mb.answer_callback_query(c.id,"✅ New token requested")
            try:mb.send_message(c.message.chat.id,"🔄 <b>Token rotation requested.</b>\n\nTelegram is sending the new token to Creator Bot now.")
            except Exception:pass
        @mb.message_handler(func=lambda m:m.text=="♻️ Revoke Bot Token")
        def revoke_cmd(m):
            if str(m.from_user.id)!=owner:return
            mb.send_message(m.chat.id,"⚠️ <b>Rotate your managed bot token?</b>\n\nThis changes the token without deleting your bot or dashboard.",parse_mode="HTML",reply_markup=core.InlineKeyboardMarkup([[core.InlineKeyboardButton("♻️ Continue",callback_data=f"mrevokec:ask:{bid}")]]))
        mb._quickdl_v10_security=True
        return mb
    core._managed_bot_start_instance=start

    # Add the owner controls to the managed-bot admin panel after all existing layers.
    old_start2=core._managed_bot_start_instance
    def start2(doc):
        mb=old_start2(doc)
        if not mb:return mb
        if getattr(mb,"_quickdl_v10_owner_controls",False):return mb
        bid=str(doc.get("bot_id") or "")
        owner=str(doc.get("owner_id") or "")
        @mb.message_handler(func=lambda m:m.text=="👑 ADMIN PANEL")
        def owner_panel(m):
            if str(m.from_user.id)!=owner:return
            d2=dash(bid) or {};s=defaults(d2);pm=premium(d2)
            kb=core.InlineKeyboardMarkup(row_width=2)
            kb.add(core.InlineKeyboardButton("📊 Stats",callback_data=f"mstats:{bid}"),core.InlineKeyboardButton("📢 Broadcast",callback_data=f"mbroadcast:{bid}"))
            kb.add(core.InlineKeyboardButton("🌐 Dashboard",url=str(core.AD_PUBLIC_BASE_URL).rstrip("/")+"/dashboard/"+bid))
            kb.add(core.InlineKeyboardButton("♻️ Revoke Token",callback_data=f"mrevokec:ask:{bid}"))
            if pm:kb.add(core.InlineKeyboardButton("💎 Premium Active",callback_data=f"mbotinfo:{bid}"))
            else:kb.add(core.InlineKeyboardButton("💎 Open Premium",url=core._creator_bot_url() or "https://t.me/Downloadvedioytibot"))
            mb.send_message(m.chat.id,"👑 <b>BOT CONTROL CENTER</b>\n\n🤖 @"+html.escape(str(d2.get("username") or "unknown"))+"\n\n"+
                ("💎 Premium dashboard controls are unlocked." if pm else "🆓 Free: dashboard settings are locked. Open Premium to unlock customization.")+
                "\n\n🌐 Dashboard: <b>"+html.escape(str(core.AD_PUBLIC_BASE_URL).rstrip("/")+"/dashboard/"+bid)+"</b>",parse_mode="HTML",reply_markup=kb)
        mb._quickdl_v10_owner_controls=True
        return mb
    core._managed_bot_start_instance=start2

    # Creator manual-token flow. creator_v2's callback currently replaces the older
    # v1 callback, so wire the existing-token state here without changing Telegram's
    # native managed-bot flow.
    old_cb=core._creator_callback
    def creator_cb(call):
        data=str((call or {}).get("data") or "");uid=str(((call or {}).get("from") or {}).get("id") or "")
        msg=(call or {}).get("message") or {};cid=(msg.get("chat") or {}).get("id")
        if data=="cuse_existing_token":
            core._creator_set_session(uid,{"state":"existing_token","updated_at":now()})
            core._creator_answer(call.get("id"),"Send your bot token")
            core._creator_send(cid,"🔑 <b>USE EXISTING BOT TOKEN</b>\n\nSend the BotFather token in one message. Telegram will validate it, read the bot name and username, save it securely and start the Downloader Bot.\n\n🔒 The token is never shown back.",reply_markup={"inline_keyboard":[[{"text":"❌ Cancel","callback_data":"ccancel_create"}]]})
            return
        if data=="ccancel_create":
            core._creator_answer(call.get("id"),"Cancelled");core._creator_clear_session(uid)
            core._creator_send(cid,"↩️ <b>Creation cancelled.</b>",reply_markup=core._creator_keyboard(uid));return
        return old_cb(call)
    core._creator_callback=creator_cb

    old_text=core._creator_handle_text
    def creator_text(uid,chat_id,text):
        if str(core._creator_session(uid).get("state") or "")=="existing_token":
            # Reuse creator_patch's validation logic if it was exposed; otherwise perform it here.
            token=str(text or "").strip()
            info,err=core._creator_api_with_token(token,"getMe",{},timeout=15)
            if err or not info or not info.get("id"):
                core._creator_send(chat_id,"❌ <b>Telegram rejected this token.</b>\n\nCheck the token and send it again.");return
            bid=str(info.get("id"));username=str(info.get("username") or "").lstrip("@");name=str(info.get("first_name") or "Downloader Bot")
            if not username:core._creator_send(chat_id,"❌ Telegram did not return a bot username.");return
            old=core.managed_bots_col.find_one({"bot_id":bid})
            if old and str(old.get("owner_id"))!=uid:core._creator_send(chat_id,"❌ This bot is already connected to another Creator account.");return
            pin=str((old or {}).get("dashboard_pin_plain") or ""); 
            if len(pin)!=6 or not pin.isdigit():pin=str(secrets.randbelow(1000000)).zfill(6)
            s=defaults(old or {})
            doc={"bot_id":bid,"owner_id":uid,"token_enc":core._encrypt_managed_token(token),"username":username,"name":name,"bot_type":str((core._creator_session(uid).get("bot_type") or "video")),"active":True,"suspended":False,"premium_until":(old or {}).get("premium_until"),"created_at":(old or {}).get("created_at",now()),"updated_at":now(),"users":list((old or {}).get("users") or []),"managed_by_telegram":False,"token_source":"existing_token","dashboard_pin_plain":pin,"dashboard_pin_hash":hashlib.sha256(pin.encode()).hexdigest(),"dashboard_settings":s}
            core.managed_bots_col.update_one({"bot_id":bid},{"$set":doc},upsert=True);core._creator_clear_session(uid);d=dash(bid);core._managed_bot_start_instance(d)
            link=str(core.AD_PUBLIC_BASE_URL).rstrip("/")+"/dashboard/"+bid
            core._creator_send(chat_id,"🎉 <b>Bot Connected Successfully!</b>\n\n🤖 <b>"+html.escape(name)+"</b>\n🔗 @"+html.escape(username)+"\n\n🌐 Dashboard: <a href='"+html.escape(link,quote=True)+"'>Open Dashboard</a>\n👤 Login username: <b>@"+html.escape(username)+"</b>\n🔐 Dashboard PIN: <code>"+pin+"</code>",reply_markup=core._creator_keyboard(uid));return
        return old_text(uid,chat_id,text)
    core._creator_handle_text=creator_text
    return core
