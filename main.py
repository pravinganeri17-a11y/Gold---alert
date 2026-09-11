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
        r = requests.post(url, json=payload, timeout=10)
        print("Telegram Status:", r.status_code, r.text, flush=True)
    except Exception as e:
        print("Telegram Send Error:", e, flush=True)

def check_inside_bar():
    global last_candle_time
    url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=15min&outputsize=5&apikey={API_KEY}"
    try:
        res = requests.get(url, timeout=12).json()
        if "values" not in res:
            print("API Warning:", res, flush=True)
            return

        candles = res["values"]
        c1 = candles[1]  # Closed candle
        c2 = candles[2]  # Mother candle
        c_time = c1["datetime"]

        c1_h, c1_l = float(c1["high"]), float(c1["low"])
        c2_h, c2_l = float(c2["high"]), float(c2["low"])

        print(f"Candle: {c_time} | C1[{c1_l}-{c1_h}] vs C2[{c2_l}-{c2_h}]", flush=True)

        if (c1_h < c2_h) and (c1_l > c2_l):
            if c_time != last_candle_time:
                last_candle_time = c_time
                msg = (
                    f"🔔 XAU/USD 15M: Inside Bar Formed!\n\n"
                    f"⏰ Candle: {c_time}\n"
                    f"📈 High: {c1_h}\n"
                    f"📉 Low: {c1_l}\n"
                    f"Status: Confirmed Closed"
                )
                send_alert(msg)
    except Exception as e:
        print("Data Fetch Exception:", e, flush=True)

def bot_loop():
    time.sleep(2)
    # Turant Telegram send test
    send_alert("🚀 PG 1702 Bot Started Successfully!\nXAU/USD 15M Scan Active.")
    while True:
        check_inside_bar()
        time.sleep(45)

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive and running!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

if __name__ == "__main__":
    t = threading.Thread(target=bot_loop, daemon=True)
    t.start()
    run_server()
    
