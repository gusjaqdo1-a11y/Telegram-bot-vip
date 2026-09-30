import hashlib
from datetime import datetime, timezone

def apply(core):
    def start_create(uid, chat_id):
        uid=str(uid)
        if not core._creation_open():
            core._creator_send(chat_id,"🔒 <b>Bot Creation is Closed</b>\n\nExisting bots continue working normally.",reply_markup=core._creator_keyboard(uid)); return
        if not core._creator_verify_gate(uid,chat_id): return
        core._creator_set_session(uid,{"state":"create_method","updated_at":datetime.now(timezone.utc)})
        core._creator_api("sendPhoto",{"chat_id":chat_id,"photo":core._creator_card_url("all"),
            "caption":"🤖 <b>CREATE YOUR OWN BOT</b>\n\nChoose how you want to add your Downloader Bot.\n\n🚀 <b>Create with Telegram</b> — Telegram opens the official managed-bot screen; enter the bot name and username there.\n\n🔑 <b>Use Existing Token</b> — connect an existing bot using its token.",
            "parse_mode":"HTML","reply_markup":{"inline_keyboard":[
                [{"text":"🚀 Create with Telegram","callback_data":"ccreate_managed"}],
                [{"text":"🔑 Use Existing Token","callback_data":"cuse_existing_token"}],
                [{"text":"❌ Cancel","callback_data":"ccancel_create"}],
            ]}})
    def existing_prompt(uid,chat_id):
        sess=core._creator_session(uid)
        core._creator_set_session(uid,{**sess,"state":"existing_token","updated_at":datetime.now(timezone.utc)})
        core._creator_send(chat_id,"🔑 <b>USE EXISTING BOT TOKEN</b>\n\nSend your bot token in one message. Telegram will validate it, read the bot name/username and start it automatically.\n\n🔒 The token is stored encrypted and is never shown back.",
            reply_markup={"inline_keyboard":[[{"text":"❌ Cancel","callback_data":"ccancel_create"}]]})
    def register_existing(uid,chat_id,token):
        uid=str(uid); token=str(token or "").strip()
        if not token:
            core._creator_send(chat_id,"❌ Send the bot token in one message."); return
        try:
            info,err=core._creator_api_with_token(token,"getMe",{},timeout=15)
            if err or not info or not info.get("id"):
                core._creator_send(chat_id,"❌ <b>Telegram rejected this token.</b>\n\nCheck it and send again."); return
            bid=str(info["id"]); username=str(info.get("username") or "").lstrip("@"); name=str(info.get("first_name") or "Downloader Bot")
            if not username:
                core._creator_send(chat_id,"❌ Telegram did not return a bot username for this token."); return
            old=core.managed_bots_col.find_one({"bot_id":bid})
            if old and str(old.get("owner_id"))!=uid:
                core._creator_send(chat_id,"❌ This bot is already connected to another Creator account."); return
            sess=core._creator_session(uid); btype=str(sess.get("bot_type") or "video").lower()
            if btype not in {"video","music","all"}: btype="video"
            now=datetime.now(timezone.utc); pin=str((old or {}).get("dashboard_pin_plain") or "")
            if len(pin)!=6 or not pin.isdigit(): pin=str(abs(hash((uid,bid)))%1000000).zfill(6)
            dashboard=(old or {}).get("dashboard_settings") or {"platforms":{},"ads_enabled":True,"premium_enabled":True,
                "buttons":{"create":True,"remove_ads":True,"admin":True,"powered_by":True},"locked_fields":[]}
            doc={"bot_id":bid,"owner_id":uid,"token_enc":core._encrypt_managed_token(token),"username":username,"name":name,
                "bot_type":btype,"active":True,"suspended":False,"premium_until":(old or {}).get("premium_until"),
                "wallet_linked":bool((old or {}).get("wallet_linked",False)),"created_at":(old or {}).get("created_at",now),
                "updated_at":now,"users":list((old or {}).get("users") or []),"managed_by_telegram":False,
                "token_source":"existing_token","dashboard_pin_plain":pin,"dashboard_pin_hash":hashlib.sha256(pin.encode()).hexdigest(),
                "dashboard_settings":dashboard}
            core.managed_bots_col.update_one({"bot_id":bid},{"$set":doc},upsert=True)
            core._creator_clear_session(uid); d=core.managed_bots_col.find_one({"bot_id":bid}) or doc; core._managed_bot_start_instance(d)
            dash=f"{str(core.AD_PUBLIC_BASE_URL).rstrip('/')}/dashboard/{bid}"
            core._creator_send(chat_id,f"🎉 <b>Bot Connected Successfully!</b>\n\n🤖 <b>{core.html.escape(name)}</b>\n🔗 @{core.html.escape(username)}\n🆔 <code>{bid}</code>\n\nYour existing bot is now running as a Downloader Bot.\n\n🌐 Dashboard: <code>{core.html.escape(dash)}</code>\n👤 Login username: <b>@{core.html.escape(username)}</b>\n🔐 Dashboard PIN: <code>{pin}</code>",reply_markup=core._creator_keyboard(uid))
        except Exception as e:
            print("Existing bot connection failed:",repr(e)); core._creator_send(chat_id,"❌ <b>Could not connect this bot.</b>\n\nCheck the token and try again.")
    old_text=core._creator_handle_text
    def handle_text(uid,chat_id,text):
        if str(core._creator_session(uid).get("state") or "")=="existing_token":
            register_existing(uid,chat_id,text); return
        return old_text(uid,chat_id,text)
    old_callback=core._creator_callback
    def callback(call):
        data=str((call or {}).get("data") or ""); uid=str(((call or {}).get("from") or {}).get("id") or "")
        chat_id=(((call or {}).get("message") or {}).get("chat") or {}).get("id")
        if data=="ccancel_create":
            core._creator_answer(call.get("id"),"Cancelled"); core._creator_clear_session(uid)
            core._creator_send(chat_id,"↩️ <b>Creation cancelled.</b>",reply_markup=core._creator_keyboard(uid)); return
        if data=="ccreate_managed":
            core._creator_answer(call.get("id"),"Choose the bot type"); core._creator_request_bot_type(uid,chat_id); return
        if data=="ccreate_back": start_create(uid,chat_id); return
        if data=="cuse_existing_token":
            core._creator_answer(call.get("id"),"Send your bot token"); existing_prompt(uid,chat_id); return
        return old_callback(call)
    core._creator_start_create=start_create
    core._creator_handle_text=handle_text
    core._creator_callback=callback
    return core
