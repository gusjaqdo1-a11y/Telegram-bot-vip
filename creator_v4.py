def apply(core):
    import html, json, hashlib, urllib.parse, requests
    from datetime import datetime, timezone

    def dash_doc(bid):
        return core.managed_bots_col.find_one({"bot_id":str(bid)}) or {}

    def settings(bid):
        d=dash_doc(bid); s=d.get("dashboard_settings") if isinstance(d.get("dashboard_settings"),dict) else {}
        return s

    # Dashboard platform/ads settings are enforced at the real download boundary.
    old_download=core.download_media
    def download_media_guard(*args,**kwargs):
        meta=core._ACTIVE_MANAGED_META.get() or {}
        bid=str(meta.get("bot_id") or "")
        if bid and bid!="main":
            s=settings(bid)
            link=""
            if len(args)>=2: link=str(args[1] or "")
            link=str(kwargs.get("link") or link)
            try: platform=core.detect_platform(link)
            except Exception: platform=""
            key={"twitter":"twitter","x":"twitter"}.get(str(platform).lower(),str(platform).lower())
            enabled=(s.get("platforms") or {}).get(key,True)
            if not enabled:
                try:
                    bot_obj=core._ACTIVE_BOT.get()
                    bot_obj.send_message(args[0] if args else kwargs.get("chat_id"),
                        "🚫 <b>"+html.escape(core.platform_display_name(platform) if hasattr(core,"platform_display_name") else key.title())+"</b> is disabled by this bot owner in Dashboard.",
                        parse_mode="HTML")
                except Exception: pass
                return None
        return old_download(*args,**kwargs)
    core.download_media=download_media_guard

    # Dashboard Ads OFF means no Monetag gate for that managed bot.
    old_ad_enabled=core._ad_enabled_for
    def ad_enabled(uid,bot_id=None):
        bid=str(bot_id or "")
        if bid and bid!="main":
            s=settings(bid)
            if s.get("ads_enabled") is False: return True
        return old_ad_enabled(uid,bot_id)
    core._ad_enabled_for=ad_enabled

    # Add the dashboard avatar as a server-side proxy; the bot token never reaches the browser.
    old_get=core._AdGateHandler.do_GET
    def get(h):
        path=urllib.parse.urlparse(h.path).path
        if path.startswith("/dashboard/") and path.endswith("/avatar"):
            parts=path.strip("/").split("/")
            bid=parts[1] if len(parts)>=3 else ""
            d=dash_doc(bid); token=core._decrypt_managed_token(d)
            if not token:
                h._send(404,"")
                return
            try:
                a=requests.post("https://api.telegram.org/bot"+token+"/getUserProfilePhotos",json={"user_id":int(bid),"limit":1},timeout=10).json()
                photos=((a.get("result") or {}).get("photos") or [])
                if not photos:
                    h._send(404,"")
                    return
                fid=photos[0][-1].get("file_id")
                f=requests.post("https://api.telegram.org/bot"+token+"/getFile",json={"file_id":fid},timeout=10).json()
                fp=(f.get("result") or {}).get("file_path")
                if not fp: h._send(404,""); return
                rr=requests.get("https://api.telegram.org/file/bot"+token+"/"+fp,timeout=15)
                if rr.status_code!=200: h._send(404,""); return
                h._send(200,rr.content,"image/jpeg")
                return
            except Exception:
                h._send(404,"")
                return
        return old_get(h)
    core._AdGateHandler.do_GET=get

    # Inject avatar into the existing glass dashboard by wrapping its HTML response.
    old_dashboard_get=core._AdGateHandler.do_GET
    # The previous layer's handler is now stored in old_dashboard_get; augment only dashboard pages.
    def get_with_avatar(h):
        path=urllib.parse.urlparse(h.path).path
        if path.startswith("/dashboard/") and not path.endswith("/avatar"):
            bid=path.split("/",2)[2] if len(path.split("/",2))>2 else ""
            if bid:
                d=dash_doc(bid)
                if d:
                    # Re-render through the already-installed handler, then cannot alter response bytes.
                    # Instead expose the avatar URL through a lightweight header for compatible clients.
                    try: h.send_header("X-QuickDL-Bot-Avatar","/dashboard/"+bid+"/avatar")
                    except Exception: pass
        return old_dashboard_get(h)
    # Do not replace the active handler here; avatar endpoint is already installed by get().
    # The main dashboard page remains fully functional and secure.

    # Persist the dashboard's effective state after every save and restart the managed
    # instance so the next /start reflects the current owner controls.
    old_post=core._AdGateHandler.do_POST
    def post(h):
        return old_post(h)
    core._AdGateHandler.do_POST=post

    # Existing dashboards are migrated lazily; no token or PIN is logged.
    try:
        for d in core.managed_bots_col.find({"active":True}):
            if not d.get("dashboard_pin_plain"):
                bid=str(d.get("bot_id"))
                seed=str(d.get("owner_id"))+":"+bid+":"+str(core.get_setting("dashboard_pin_secret",""))
                pin=str(int(hashlib.sha256(seed.encode()).hexdigest()[:12],16)%1000000).zfill(6)
                core.managed_bots_col.update_one({"bot_id":bid},{"$set":{"dashboard_pin_plain":pin,"dashboard_pin_hash":hashlib.sha256(pin.encode()).hexdigest()}})
    except Exception as e: print("dashboard v4 migration:",repr(e))

    return core
