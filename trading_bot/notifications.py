import requests
import os

class TelegramBot:
    def __init__(self, token=None, chat_id=None):
        self.token = token or os.environ.get("TELEGRAM_TOKEN")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def send_message(self, text):
        if not self.token or not self.chat_id:
            print("Telegram credentials missing.")
            return
        
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"}
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print(f"Telegram error: {e}")

    def notify_hook(self, signal, score_ema, interval_scores, asset="BTC"):
        emoji = "🚀 LONG" if signal == "BUY" else "🔻 SHORT"
        msg = f"*{emoji} {asset} SIGNAL CONFIRMED!*\n\n"
        msg += f"MTF Master EMA: `{score_ema}%`\n"
        msg += f"1d: `{interval_scores.get('1d')}%` | 4h: `{interval_scores.get('4h')}%`\n"
        msg += f"2h: `{interval_scores.get('2h')}%` | 1h: `{interval_scores.get('1h')}%`"
        self.send_message(msg)
