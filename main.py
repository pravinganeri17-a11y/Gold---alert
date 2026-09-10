import os
import time
import logging
from datetime import datetime, timezone
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Load sensitive variables from environment
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_NEW_REVOKED_TOKEN")
CHAT_ID = os.getenv("CHAT_ID", "6422746952")
API_KEY = os.getenv("TWELVE_DATA_API_KEY", "DEMO_KEY")

last_candle_time = ""

def send_alert(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        response = requests.post(url, json=payload, timeout=8)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Telegram dispatch failed: {e}")

def check_inside_bar():
    global last_candle_time
    url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=15min&outputsize=5&apikey={API_KEY}"
    
    try:
        res = requests.get(url, timeout=10).json()
        if "values" not in res:
            logging.warning(f"TwelveData Error: {res.get('message', 'No candle values returned')}")
            return

        candles = res["values"]
        # index 0 = current live bar, index 1 = last closed bar, index 2 = mother bar
        c1, c2 = candles[1], candles[2]
        c_time = c1["datetime"]

        c1_h, c1_l = float(c1["high"]), float(c1["low"])
        c2_h, c2_l = float(c2["high"]), float(c2["low"])

        # Check inside bar condition: c1 fully contained within c2
        if (c1_h < c2_h) and (c1_l > c2_l):
            if c_time != last_candle_time:
                last_candle_time = c_time
                msg = (
                    f"🔔 XAUUSD 15M: Inside Bar Formed!\n\n"
                    f"Time: {c_time}\n"
                    f"Inside Bar: H={c1_h} | L={c1_l}\n"
                    f"Mother Bar: H={c2_h} | L={c2_l}\n"
                    f"Status: Confirmed Closed"
                )
                logging.info("Inside bar detected. Sending alert.")
                send_alert(msg)
    except Exception as e:
        logging.error(f"Error checking candle data: {e}")

def bot_loop():
    while True:
        # Calculate seconds until next 15-minute mark (:00, :15, :30, :45) + 10s buffer for API sync
        now = datetime.now(timezone.utc)
        minutes_to_next = 15 - (now.minute % 15)
        seconds_to_wait = (minutes_to_next * 60) - now.second + 10
        
        logging.info(f"Next check in {seconds_to_wait} seconds.")
        time.sleep(seconds_to_wait)
        check_inside_bar()

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is running!")

    def log_message(self, format, *args):
        pass  # Suppress HTTP access noise in logs

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    logging.info(f"Keep-alive webserver listening on port {port}")
    server.serve_forever()

if __name__ == "__main__":
    threading.Thread(target=bot_loop, daemon=True).start()
    run_server()
    
