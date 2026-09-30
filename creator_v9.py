def apply(core):
    # Wire per-bot dashboard settings into the already-existing managed-bot runtime.
    old_start=core._managed_bot_start_instance
    def start(doc):
        mb=old_start(doc)
        if not mb:return mb
        bid=str(doc.get("bot_id") or "")
        marker=getattr(mb,"_quickdl_v9_dashboard",None)
        if marker==bid:return mb
        def cfg():
            d=core.managed_bots_col.find_one({"bot_id":bid}) or {}
            s=d.get("dashboard_settings") if isinstance(d.get("dashboard_settings"),dict) else {}
            return d,s
        def blocked_button(s,name):
            b=s.get("buttons") or {}
            return b.get(name,True) is False
        def blocked_platform(s,platform):
            p=s.get("platforms") or {}
            return p.get(platform,True) is False
        def menu_for(m):
            d,s=cfg(); owner=str(d.get("owner_id") or "")==str(m.from_user.id)
            kb=core.ReplyKeyboardMarkup(resize_keyboard=True)
            if (core._creation_open() and not blocked_button(s,"create")): kb.add("🤖 Create Your Own Bot")
            if not blocked_button(s,"remove_ads"): kb.add("🚫 Remove Ads")
            if owner and not blocked_button(s,"admin"): kb.add("👑 ADMIN PANEL")
            return kb
        def guard_message(m):
            d,s=cfg(); text=str(m.text or "").strip()
            if text in {"/start","/help"}:
                custom=str(s.get("welcome_text") or "").strip()
                if custom:
                    mb.send_message(m.chat.id,custom,parse_mode="HTML",reply_markup=menu_for(m))
                else:
                    mb.send_message(m.chat.id,"🤖 <b>"+core.html.escape(str(d.get("name") or "Downloader Bot"))+"</b>\n\nSend a supported video link to start downloading.",parse_mode="HTML",reply_markup=menu_for(m))
                return
            if text=="🤖 Create Your Own Bot" and blocked_button(s,"create"):
                mb.send_message(m.chat.id,"🔒 <b>Create Bot</b> is disabled by this bot's owner.",parse_mode="HTML"); return
            if text=="🚫 Remove Ads" and blocked_button(s,"remove_ads"):
                mb.send_message(m.chat.id,"🔒 <b>Remove Ads</b> is disabled by this bot's owner.",parse_mode="HTML"); return
            if text=="👑 ADMIN PANEL" and blocked_button(s,"admin"):
                mb.send_message(m.chat.id,"🔒 Admin controls are disabled in this dashboard.",parse_mode="HTML"); return
            try:
                link=core.extract_url(text)
                if link:
                    platform=core.detect_platform(link)
                    if blocked_platform(s,platform):
                        mb.send_message(m.chat.id,"🔒 <b>"+core.html.escape(str(platform or "This platform"))+"</b> is disabled by this bot's owner.",parse_mode="HTML")
                        return
            except Exception: pass
            return
        def guard_filter(m):
            d,s=cfg(); text=str(m.text or "").strip()
            if text in {"/start","/help"}: return True
            if text=="🤖 Create Your Own Bot" and blocked_button(s,"create"): return True
            if text=="🚫 Remove Ads" and blocked_button(s,"remove_ads"): return True
            if text=="👑 ADMIN PANEL" and blocked_button(s,"admin"): return True
            try:
                link=core.extract_url(text)
                if link and blocked_platform(s,core.detect_platform(link)): return True
            except Exception: pass
            return False
        mb.message_handlers.insert(0,{"function":guard_message,"pass_bot":False,"filters":{"func":guard_filter,"content_types":["text"]}})
        def guard_callback(c):
            d,s=cfg(); data=str(c.data or "")
            deny=None
            if (data.startswith("music:") or data.startswith("msong:") or data.startswith("mspage:") or data.startswith("msongcancel:")) and blocked_button(s,"music"): deny="Music is disabled by this bot owner."
            elif (data.startswith("adplan:") or data.startswith("adremove:")) and blocked_button(s,"remove_ads"): deny="Remove Ads is disabled by this bot owner."
            elif (data.startswith("mytprem:") or data.startswith("v7premium:") or data.startswith("premium_") or data.startswith("adpremium:") or data.startswith("adpremplan:")) and blocked_button(s,"premium"): deny="Premium is disabled by this bot owner."
            elif (data.startswith("mbroadcast:") or data.startswith("mstats:") or data.startswith("mbotinfo:")) and blocked_button(s,"admin"): deny="Admin controls are disabled by this bot owner."
            if deny:
                mb.answer_callback_query(c.id,"🔒 "+deny,show_alert=True)
        def guard_cb_filter(c):
            d,s=cfg(); data=str(c.data or "")
            return ((data.startswith("music:") or data.startswith("msong:") or data.startswith("mspage:") or data.startswith("msongcancel:")) and blocked_button(s,"music")) or ((data.startswith("adplan:") or data.startswith("adremove:")) and blocked_button(s,"remove_ads")) or ((data.startswith("mytprem:") or data.startswith("v7premium:") or data.startswith("premium_") or data.startswith("adpremium:") or data.startswith("adpremplan:")) and blocked_button(s,"premium")) or ((data.startswith("mbroadcast:") or data.startswith("mstats:") or data.startswith("mbotinfo:")) and blocked_button(s,"admin"))
        mb.callback_query_handlers.insert(0,{"function":guard_callback,"pass_bot":False,"filters":{"func":guard_cb_filter}})
        mb._quickdl_v9_dashboard=bid
        return mb
    core._managed_bot_start_instance=start

    old_ads=core._ad_enabled_for
    def ad_enabled(uid,bid=None):
        meta=core._ACTIVE_MANAGED_META.get() or {}
        mbid=str(meta.get("bot_id") or "")
        if mbid:
            d=core.managed_bots_col.find_one({"bot_id":mbid}) or {}
            s=d.get("dashboard_settings") if isinstance(d.get("dashboard_settings"),dict) else {}
            if s.get("ads_enabled",True) is False:return False
        return old_ads(uid,bid)
    core._ad_enabled_for=ad_enabled

    old_powered=core._active_powered_text
    def powered():
        meta=core._ACTIVE_MANAGED_META.get() or {}; bid=str(meta.get("bot_id") or "")
        if bid:
            d=core.managed_bots_col.find_one({"bot_id":bid}) or {}; s=d.get("dashboard_settings") if isinstance(d.get("dashboard_settings"),dict) else {}
            if (s.get("buttons") or {}).get("powered_by",True) is False:return ""
        return old_powered()
    core._active_powered_text=powered

    old_quality=core._quality_format
    def quality(uid,quality_value=None):
        if quality_value is None:
            meta=core._ACTIVE_MANAGED_META.get() or {}; bid=str(meta.get("bot_id") or "")
            if bid:
                d=core.managed_bots_col.find_one({"bot_id":bid}) or {}; s=d.get("dashboard_settings") if isinstance(d.get("dashboard_settings"),dict) else {}
                quality_value=s.get("default_quality") or "best"
        return old_quality(uid,quality_value)
    core._quality_format=quality
    return core
