                if owner: kb.add("👑 ADMIN PANEL")
                return kb
            def _start(m):
                _ctx(); managed_bots_col.update_one({"bot_id":bid},{"$addToSet":{"users":int(m.from_user.id)}}); owner=str(doc.get("owner_id") or "")==str(m.from_user.id)
                if btype=="music":
                    text="🎵 <b>WELCOME TO MUSIC DOWNLOADER</b> 🎵\n\nSearch and download songs by title, part of title or artist.\n\n🎵 Full song download\n🎤 Artist + title metadata\n🖼 Cover artwork\n⚡ Fast search\n\n🚀 Send a song name now."
                else:
                    dstart=_managed_bot_doc(bid) or doc\n                    text=str(dstart.get("start_message") or "🎬 <b>WELCOME TO VIDEO DOWNLOADER</b> 🎬\\n\\nDownload supported videos and photos quickly.\\n\\n📥 Copy a supported link and send it here.\\n🌐 YouTube • TikTok • Instagram • Facebook • Pinterest • Snapchat • X/Twitter and other supported platforms.\\n⚡ The download starts immediately.\\n\\n🚀 Send your link now.")
                mb.send_message(m.chat.id,text,parse_mode="HTML",reply_markup=_menu(owner))
            def _help(m): _ctx(); _start(m)
            def _create(m):
                _ctx(); url=_creator_bot_url()
                if not _creation_open(): mb.send_message(m.chat.id,"🔒 <b>Bot creation is currently closed.</b>",parse_mode="HTML"); return
                if url: mb.send_message(m.chat.id,"🤖 <b>Create Your Own Bot</b>\n\nOpen the Creator Bot to choose Video Downloader or Music Downloader.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Open Creator Bot",url=url)]]),parse_mode="HTML")
            def _remove_ads_menu(m):