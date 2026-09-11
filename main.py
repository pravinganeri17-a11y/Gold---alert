import os
import time
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

TELEGRAM_TOKEN = "8163156265:AAGuUYBf6urAsJhkzScZDiJhzt1GysNXn58"
CHAT_ID = "6422746952"
API_KEY = "60badeda201b49d2a4cc00079279da49"

last_candle_time = ""

def send_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, json=payload, timeout=8)
    except Exception as e:
        print(f"Telegram error: {e}")

def check_inside_bar():
    global last_candle_time
    url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=15min&outputsize=5&apikey={API_KEY}"
    try:
        res = requests.get(url, timeout=10).json()
        if "values" not in res:
            return

        candles = res["values"]
        c1 = candles[1]  # Closed candle
        c2 = candles[2]  # Mother candle
        c_time = c1["datetime"]

        c1_h, c1_l = float(c1["high"]), float(c1["low"])
        c2_h, c2_l = float(c2["high"]), float(c2["low"])

        if (c1_h < c2_h) and (c1_l > c2_l):
            if c_time != last_candle_time:
                last_candle_time = c_time
                msg = f"🔔 XAUUSD 15M: Inside Bar Formed!\n\nTime: {c_time}\nHigh: {c1_h}\nLow: {c1_l}\nStatus: Confirmed Closed"
                send_alert(msg)
    except Exception as e:
        print(f"Fetch error: {e}")

def bot_loop():
    time.sleep(3)
    send_alert("✅ PG 1702 Bot Active ho gaya hai! XAU/USD 15M tracking chalu.")
    while True:
        check_inside_bar()
        time.sleep(30)

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active and running!")

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

if __name__ == "__main__":
    threading.Thread(target=bot_loop, daemon=True).start()
    run_server()
    
