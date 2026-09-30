def apply(core):
    import html

    old_start=core._managed_bot_start_instance
    def start(doc):
        mb=old_start(doc)
        if not mb: return mb
        if getattr(mb,"_quickdl_v2prem",False): return mb
        @mb.callback_query_handler(func=lambda c: str(c.data or "").startswith("v2prem:"))
        def managed_v2prem(c):
            p=str(c.data).split(":"); token=p[1] if len(p)>1 else ""; months=p[2] if len(p)>2 else ""
            row=core.ad_gates_col.find_one({"token":token})
            if not row or str(row.get("user_id"))!=str(c.from_user.id):
                mb.answer_callback_query(c.id,"Invalid payment session.",show_alert=True); return
            try:
                link,stars=core._create_ad_premium_invoice(token,str(c.from_user.id),str(row.get("bot_id") or "main"),months)
                # Premium media belongs to the main downloader bot. Telegram file_id values
                # are bot-specific, so send the configured media through the main bot.
                try:
                    media=core.db1["premium_plan_media"].find_one({"_id":str(months)}) or {}
                    fid=str(media.get("file_id") or "")
                    if fid:
                        if media.get("type")=="video": core.bot.send_video(c.message.chat.id,fid,caption=media.get("caption") or "",parse_mode="HTML")
                        else: core.bot.send_photo(c.message.chat.id,fid,caption=media.get("caption") or "",parse_mode="HTML")
                except Exception as e: print("managed premium media:",repr(e))
                mb.answer_callback_query(c.id,"Invoice ready")
                mb.send_message(c.message.chat.id,"💎 <b>Premium — "+html.escape(months)+" month(s)</b>\n\n⭐ Price: <b>"+str(stars)+" Stars</b>\n\nPayment is processed securely by @Downloadvedioytibot.",parse_mode="HTML",
                    reply_markup=core.InlineKeyboardMarkup([[core.InlineKeyboardButton("⭐ PAY NOW",url=link)]]))
            except Exception as e:
                print("managed v2 premium invoice:",repr(e)); mb.answer_callback_query(c.id,"Could not create invoice.",show_alert=True)
        mb._quickdl_v2prem=True
        return mb
    core._managed_bot_start_instance=start
    return core
