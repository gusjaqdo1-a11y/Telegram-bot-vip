import os,uuid,contextvars,html
def apply(core):
    # Replace the already-registered main broadcast handlers in-place.
    def replace_handler(name,fn):
        for h in getattr(core.bot,"message_handlers",[]):
            f=h.get("function")
            if getattr(f,"__name__","")==name:
                h["function"]=fn
                return True
        return False
    def text_broadcast(m):
        if not core.is_admin(m.from_user.id): return
        batch=uuid.uuid4().hex
        sent=failed=0
        for uid in list(core.users.keys()):
            try:
                x=core.bot.copy_message(int(uid),m.chat.id,m.message_id)
                mid=getattr(x,"message_id",None)
                if mid and hasattr(core,"_record_broadcast_batch"):
                    core._record_broadcast_batch(m.from_user.id,batch,uid,mid)
                sent+=1
            except Exception: failed+=1
        try: core.bot.send_message(m.chat.id,"✅ Broadcast sent to <b>"+str(sent)+"</b> users\n❌ Failed: <b>"+str(failed)+"</b>",parse_mode="HTML")
        except Exception: pass
    def media_broadcast(m):
        if not core.is_admin(m.from_user.id): return
        if not (m.video or m.photo):
            core.bot.send_message(m.chat.id,"❌ Please send a valid Video or Photo."); return
        batch=uuid.uuid4().hex; sent=failed=0
        for uid in list(core.users.keys()):
            try:
                x=core.bot.copy_message(int(uid),m.chat.id,m.message_id)
                mid=getattr(x,"message_id",None)
                if mid and hasattr(core,"_record_broadcast_batch"):
                    core._record_broadcast_batch(m.from_user.id,batch,uid,mid)
                sent+=1
            except Exception: failed+=1
        core.bot.send_message(m.chat.id,"✅ Media broadcast sent to <b>"+str(sent)+"</b> users.\n❌ Failed: <b>"+str(failed)+"</b>",parse_mode="HTML")
    replace_handler("broadcast_send",text_broadcast)
    replace_handler("broadcast_media_process",media_broadcast)

    # Size-aware YouTube gate. The existing download error path remains intact:
    # we mark a size gate as a duration-limit error, while premium_gate_message
    # renders the exact required/allowed MB values.
    try:
        import contextvars
        size_state=contextvars.ContextVar("v8_size_gate",default=None)
        old_safe=core._safe_send_file
        old_gate=core.premium_gate_message
        def safe(chat_id,path,caption="",reply_markup=None,platform=None,link=None):
            if platform=="youtube":
                try:
                    uid=str(core._current_user_id() if hasattr(core,"_current_user_id") else "")
                    if not uid:
                        meta=core._ACTIVE_MANAGED_META.get() or {}
                        uid=str(meta.get("owner_id") or "")
                    max_mb=int(core._download_max_mb(uid,platform="youtube",link=link) or 0)
                    mb=os.path.getsize(path)/(1024*1024)
                    if max_mb>0 and mb>max_mb and not core.is_premium(uid):
                        size_state.set((mb,max_mb))
                        raise RuntimeError("duration limit")
                except RuntimeError: raise
                except Exception: pass
            return old_safe(chat_id,path,caption,reply_markup=reply_markup,platform=platform,link=link)
        def gate(uid,platform,duration=None):
            z=size_state.get()
            if z:
                size_state.set(None)
                mb,mx=z
                p=core.get_premium_prices()
                kb=core.InlineKeyboardMarkup(row_width=2)
                for m in ("1","3","9","12"):
                    if m in p:
                        kb.add(core.InlineKeyboardButton("💎 "+m+" Month — $"+format(float(p[m]),".2f"),callback_data="premium_buy:"+m))
                kb.row(core.InlineKeyboardButton("💎 OPEN PREMIUM",callback_data="premium_menu"))
                return ("📦 <b>YouTube file is larger than your current limit.</b>\n\n"
                        "📊 Required file size: <b>"+format(mb,".1f")+" MB</b>\n"
                        "📌 Your allowed limit: <b>"+str(mx)+" MB</b>\n\n"
                        "Upgrade to Premium to unlock a higher/unlimited YouTube limit.")
            return old_gate(uid,platform,duration)
        core._safe_send_file=safe
        core.premium_gate_message=gate
    except Exception as e:
        print("v8 size gate patch:",repr(e))
    return core
