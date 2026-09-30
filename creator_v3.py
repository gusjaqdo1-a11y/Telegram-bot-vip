def apply(core):
    import html
    from datetime import datetime, timezone

    def admin(uid):
        try: return bool(core.is_admin(uid))
        except Exception: return str(uid) in {str(x) for x in getattr(core,"ADMIN_IDS",[])}

    def now(): return datetime.now(timezone.utc)

    # Creator card media: one admin-managed image/video per bot type.
    @core.bot.message_handler(func=lambda m: bool(m.text) and m.text=="🎨 CREATOR CARD MEDIA")
    def creator_card_menu(m):
        if not admin(m.from_user.id): return
        kb=core.InlineKeyboardMarkup(row_width=3)
        kb.add(core.InlineKeyboardButton("🎬 Video",callback_data="v3card:video"),
               core.InlineKeyboardButton("🎵 Music",callback_data="v3card:music"),
               core.InlineKeyboardButton("💎 All",callback_data="v3card:all"))
        core.bot.send_message(m.chat.id,"🎨 <b>CREATOR CARD MEDIA</b>\n\nChoose a card, then send a photo or video. The selected media is shown when users open Create My Bot.",parse_mode="HTML",reply_markup=kb)

    @core.bot.callback_query_handler(func=lambda c: str(c.data or "").startswith("v3card:"))
    def creator_card_pick(c):
        if not admin(c.from_user.id):
            core.bot.answer_callback_query(c.id,"Admin only",show_alert=True); return
        kind=str(c.data).split(":",1)[1]
        if kind not in {"video","music","all"}: return
        core._creator_set_session(str(c.from_user.id),{"state":"admin_creator_card","kind":kind})
        core.bot.answer_callback_query(c.id)
        core.bot.send_message(c.message.chat.id,"📷 <b>"+html.escape(kind.title())+" Creator Card</b>\n\nSend the photo or video now.",parse_mode="HTML")

    @core.bot.message_handler(content_types=["photo","video"])
    def creator_card_receive(m):
        uid=str(m.from_user.id); st=core._creator_session(uid)
        if not admin(uid) or st.get("state")!="admin_creator_card": return
        kind=str(st.get("kind") or "video")
        if getattr(m,"photo",None):
            fid=m.photo[-1].file_id; typ="photo"
        elif getattr(m,"video",None):
            fid=m.video.file_id; typ="video"
        else: return
        core.set_setting("creator_card_"+kind,{"title":{"video":"🎬 VIDEO DOWNLOADER","music":"🎵 MUSIC DOWNLOADER","all":"💎 ALL-IN-ONE DOWNLOADER"}[kind],
            "text":{"video":"Videos & photos from supported platforms. Fast and simple.","music":"Search songs, download full audio, metadata and artwork.","all":"Video + music features in one managed Downloader Bot."}[kind],
            "image":fid,"media_type":typ,"updated_at":now().isoformat()})
        core._creator_clear_session(uid)
        core.bot.send_message(m.chat.id,"✅ <b>"+html.escape(kind.title())+" Creator Card media saved.</b>",reply_markup=core.admin_menu())

    # Add the card control without removing existing admin buttons.
    old_menu=core.admin_menu
    def menu():
        kb=old_menu()
        try: kb.add("🎨 CREATOR CARD MEDIA")
        except Exception: pass
        return kb
    core.admin_menu=menu

    # Keep the managed-bot creation prompt clean: delete the previous inline
    # selection message before Telegram's native request keyboard is sent.
    old_creator_cb=core._creator_callback
    def creator_cb(call):
        data=str((call or {}).get("data") or "")
        if data.startswith("v2managed:"):
            msg=(call or {}).get("message") or {}; cid=(msg.get("chat") or {}).get("id"); mid=msg.get("message_id")
            try:
                core._creator_api("deleteMessage",{"chat_id":cid,"message_id":mid})
            except Exception: pass
        return old_creator_cb(call)
    core._creator_callback=creator_cb

    # Apply global dashboard locks to all managed bots whenever this layer loads.
    try:
        locks=list(core.get_setting("dashboard_locked_fields",[]) or [])
        if locks:
            for d in core.managed_bots_col.find({}):
                s=d.get("dashboard_settings") if isinstance(d.get("dashboard_settings"),dict) else {}
                s["locked_fields"]=locks
                core.managed_bots_col.update_one({"bot_id":str(d.get("bot_id"))},{"$set":{"dashboard_settings":s}})
    except Exception as e:
        print("creator v3 migration:",repr(e))

    return core
