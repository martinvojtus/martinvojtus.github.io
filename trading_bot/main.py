import time
import os
from dotenv import load_dotenv

# Načíta premenné zo súboru .env
load_dotenv()

from trading_bot.client import VBSXClient
from trading_bot.strategy import VBSXStrategy
from trading_bot.notifications import TelegramBot

def run_bot():
    print("VBSX Trading Bot Starting...")
    client = VBSXClient()
    strategies = {"BTC": VBSXStrategy()}
    bot = TelegramBot()
    
    bot.send_message("🤖 *VBSX Bot Active*\nMonitoring: BTC (1d, 4h, 2h, 1h)")

    while True:
        try:
            for asset in ["BTC"]:
                print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Checking scores for {asset}...")
                
                # 1. Fetch MTF Scores
                scores = client.get_mtf_scores(asset)
                
                # 2. Calculate Weighted Master Score
                strategy = strategies[asset]
                master_score = strategy.calculate_weighted_score(scores)
                
                # 3. Update EMA
                ema = strategy.update_ema(master_score)
                
                # 4. Check for Hook Signal
                signal = strategy.check_hook()
                
                print(f"{asset} Master Score: {master_score} | EMA: {ema}")
                print(f"Scores: {scores}")

                if signal:
                    bot.notify_hook(signal, ema, scores, asset=asset)
                    print(f"!!! {asset} SIGNAL: {signal} !!!")

                # 5. Periodic status update every 6 hours (if no signal)
                if time.localtime().tm_hour % 6 == 0 and time.localtime().tm_min < 5:
                    status_msg = f"📊 *Periodic Status Update ({asset})*\nMaster EMA: `{ema}%`\n1d: `{scores.get('1d')}%` | 1h: `{scores.get('1h')}%`"
                    bot.send_message(status_msg)

        except Exception as e:
            print(f"Bot Error: {e}")
            bot.send_message(f"❌ *Bot Error*: `{str(e)}`")

        # Sleep for 1 hour
        time.sleep(3600)

if __name__ == "__main__":
    run_bot()
