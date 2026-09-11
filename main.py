import os
import time
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# Direct Credentials
TELEGRAM_TOKEN = "8163156265:AAGuUYBf6urAsJhkzScZDiJhzt1GysNXn58"
CHAT_ID = "6422746952"
API_KEY = "60badeda201b49d2a4cc00079279da49"

last_candle_time = ""

def send_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        r = requests.post(url, json=payload, timeout=10)
        print("Telegram Response:", r.status_code, r.text)
    except Exception as e:
        print("Telegram Send Error:", e)

def check_inside_bar():
    global last_candle_time
    # TwelveData endpoint
    url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=15min&outputsize=5&apikey={API_KEY}"
    try:
        res = requests.get(url, timeout=12).json()
        
        if "values" not in res:
            print("API Warning/Error:", res.get("message", res))
            return

        candles = res["values"]
        # c1 is completed candle, c2 is previous mother candle
        c1 = candles[1]
        c2 = candles[2]
        c_time = c1["datetime"]

        c1_h, c1_l = float(c1["high"]), float(c1["low"])
        c2_h, c2_l = float(c2["high"]), float(c2["low"])

        print(f"Checking {c_time} | C1 High:{c1_h} Low:{c1_l} vs C2 High:{c2_h} Low:{c2_l}")

        # Inside Bar condition: C1 completely inside C2
        if (c1_h < c2_h) and (c1_l > c2_l):
            if c_time != last_candle_time:
                last_candle_time = c_time
                msg = (
                    f"🔔 XAU/USD 15M: Inside Bar Formed!\n\n"
                    f"⏰ Candle Time: {c_time}\n"
                    f"📈 High: {c1_h}\n"
                    f"📉 Low: {c1_l}\n"
                    f"Status: Confirmed Closed"
                )
                send_alert(msg)
    except Exception as e:
        print("Data Fetch Exception:", e)

def bot_loop():
    # Service start hone ke 5 sec baad confirmation message
    time.sleep(5)
    send_alert("🚀 PG 1702 Alert Bot Online!\nXAU/USD 15-Min Live Scan Chalu Ho Chuka Hai.")
    
    while True:
        check_inside_bar()
        time.sleep(30)

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is 100% active and scanning!")

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

if __name__ == "__main__":
    t = threading.Thread(target=bot_loop, daemon=True)
    t.start()
    run_server()
    
