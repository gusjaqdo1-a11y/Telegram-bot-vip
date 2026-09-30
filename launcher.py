import threading
import bot as core
from creator_patch import apply
from creator_v2 import apply as apply_v2
from creator_v3 import apply as apply_v3
from creator_v4 import apply as apply_v4
from creator_v5 import apply as apply_v5
from creator_v6 import apply as apply_v6
from creator_v7 import apply as apply_v7
from creator_v8 import apply as apply_v8
from creator_v9 import apply as apply_v9
from creator_v10 import apply as apply_v10

apply(core)
apply_v2(core)
apply_v3(core)
apply_v4(core)
apply_v5(core)
apply_v6(core)
apply_v7(core)
apply_v8(core)
apply_v9(core)
apply_v10(core)

def main():
    try: core._start_ad_http_server()
    except Exception as e: print("Ad server startup warning:",repr(e))
    try: core._creation_commands_refresh()
    except Exception as e: print("Creation command refresh warning:",repr(e))
    threading.Thread(target=core._managed_bots_startup,daemon=True,name="managed-bot-startup").start()
    threading.Thread(target=core._creator_poll_loop,daemon=True,name="creator-bot-poller").start()
    threading.Thread(target=core.premium_expiry_worker,daemon=True).start()
    threading.Thread(target=core.market_refresh_worker,daemon=True).start()
    threading.Thread(target=core.conversion_hold_worker,daemon=True).start()
    threading.Thread(target=core.balance_lock_worker,daemon=True).start()
    threading.Thread(target=core.streak_worker,daemon=True).start()
    try: core.refresh_market_rates(force=True)
    except Exception as e: print("Initial market refresh failed:",e)
    try: core.migrate_legacy_ledger_once()
    except Exception as e: print("Ledger migration warning:",e)
    print("🤖 Bot 1 and Bot 2 are starting...")
    print(f"🟢 WaForge WhatsApp configured: {bool(core.WAFORGE_API_KEY)} | D7 SMS configured: {bool(core.D7_TOKEN)}")
    print("📦 Telegram upload limits: Admin-controlled FREE/TRIAL/PREMIUM values stored in MongoDB")
    def run_bot2():
        try: core.bot2.infinity_polling(skip_pending=True)
        except Exception as e: print(f"Bot 2 Error: {e}")
    threading.Thread(target=run_bot2,daemon=True).start()
    if core.customer_ai_bot:
        def run_customer_ai_bot():
            try:
                print("🤖 Dedicated Customer AI bot is starting...")
                core.customer_ai_bot.infinity_polling(skip_pending=True)
            except Exception as e: print(f"Customer AI Bot Error: {e}")
        threading.Thread(target=run_customer_ai_bot,daemon=True).start()
    else:
        print("⚠️ CUSTOMER_AI_BOT_TOKEN is not configured; dedicated Customer AI bot is disabled.")
    try: core.bot.infinity_polling(skip_pending=True)
    except Exception as e: print(f"Bot 1 Error: {e}")

if __name__=="__main__":
    main()
