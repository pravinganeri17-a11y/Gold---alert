import os
import time
import requests
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# Configuration
TELEGRAM_TOKEN = "8163156265:AAHGfJHD9Qu0yxDQFfwqXKCHFNHTgAApH_4"
CHAT_IDS = ["6422746952"]
API_KEY = "60badeda201b49d2a4cc00079279da49"

last_alert_time = ""

def send_alert(message):
    for cid in CHAT_IDS:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": cid, "text": message, "parse_mode": "Markdown"}
        try:
            # Pehla Alert
            requests.post(url, json=payload, timeout=10)
            time.sleep(1)
            # Dusra Alert (2 Baar notification confirm karne ke liye)
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"Telegram error for {cid}:", e, flush=True)

def is_market_open():
    now_utc = datetime.now(timezone.utc)
    weekday = now_utc.weekday()
    hour = now_utc.hour

    if weekday == 5:  # Saturday full day closed
        return False
    if weekday == 4 and hour >= 21:  # Friday post 21:00 UTC closed
        return False
    if weekday == 6 and hour < 21:  # Sunday pre 21:00 UTC closed
        return False
    return True

def check_sweep_and_fvg():
    global last_alert_time

    if not is_market_open():
        return

    url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=5min&outputsize=100&apikey={API_KEY}"
    try:
        res = requests.get(url, timeout=10).json()
        if "values" not in res:
            return

        candles = res["values"]
        if len(candles) < 50:
            return

        c3 = candles[0]
        c2 = candles[1]
        c1 = candles[2]
        
        alert_candle_time = c3["datetime"]
        if alert_candle_time == last_alert_time:
            return

        c3_open, c3_close = float(c3["open"]), float(c3["close"])
        c3_high, c3_low = float(c3["high"]), float(c3["low"])

        c2_open, c2_close = float(c2["open"]), float(c2["close"])
        c2_high, c2_low = float(c2["high"]), float(c2["low"])

        c1_open, c1_close = float(c1["open"]), float(c1["close"])
        c1_high, c1_low = float(c1["high"]), float(c1["low"])

        is_c1_green = c1_close > c1_open
        is_c2_red = c2_close < c2_open
        is_c3_red = c3_close < c3_open

        is_c1_red = c1_close < c1_open
        is_c2_green = c2_close > c2_open
        is_c3_green = c3_close > c3_open

        # 1. Bearish Setup
        if is_c1_green and is_c2_red and is_c3_red:
            c4 = candles[3]
            c4_high = float(c4["high"])
            has_fvg = (c2_low > c4_high) or ((c1_close - c1_open) > 1.2)

            current_sweep_high = max(c1_high, c2_high, c3_high)

            touch_found = False
            target_level = 0.0
            touch_candle_index = -1

            for i in range(3, 12):
                c_prev_high = float(candles[i]["high"])
                if abs(current_sweep_high - c_prev_high) <= 1.5:
                    touch_found = True
                    target_level = c_prev_high
                    touch_candle_index = i - 2
                    break

            if touch_found and c3_close < target_level and has_fvg:
                last_alert_time = alert_candle_time
                msg = (
                    f"🚨 *XAU/USD 5M: 8-9 CANDLE SWEEP REVERSAL (SELL)* 🚨\n\n"
                    f"⏰ *Time:* `{alert_candle_time}`\n"
                    f"📍 *Level Tested:* `{target_level:.2f}`\n"
                    f"🕯️ *First Touch:* `{touch_candle_index} candles pehle`\n"
                    f"🔺 *Sweep Wick:* `{current_sweep_high:.2f}`\n"
                    f"🎯 *Formation:* 1 Green + 2 Red Confirmed\n"
                    f"⚡ *FVG Status:* Confirmed Imbalance\n"
                    f"📉 *Current Price:* `{c3_close:.2f}`\n\n"
                    f"⚠️ *Candle agle 3-4s mein close ho rahi hai! (2x Alert)*"
                )
                send_alert(msg)
                return

        # 2. Bullish Setup
        if is_c1_red and is_c2_green and is_c3_green:
            c4 = candles[3]
            c4_low = float(c4["low"])
            has_fvg = (c2_high < c4_low) or ((c1_open - c1_close) > 1.2)

            current_sweep_low = min(c1_low, c2_low, c3_low)

            touch_found = False
            target_level = 0.0
            touch_candle_index = -1

            for i in range(3, 12):
                c_prev_low = float(candles[i]["low"])
                if abs(current_sweep_low - c_prev_low) <= 1.5:
                    touch_found = True
                    target_level = c_prev_low
                    touch_candle_index = i - 2
                    break

            if touch_found and c3_close > target_level and has_fvg:
                last_alert_time = alert_candle_time
                msg = (
                    f"🚨 *XAU/USD 5M: 8-9 CANDLE SWEEP REVERSAL (BUY)* 🚨\n\n"
                    f"⏰ *Time:* `{alert_candle_time}`\n"
                    f"📍 *Level Tested:* `{target_level:.2f}`\n"
                    f"🕯️ *First Touch:* `{touch_candle_index} candles pehle`\n"
                    f"🔻 *Sweep Wick:* `{current_sweep_low:.2f}`\n"
                    f"🎯 *Formation:* 1 Red + 2 Green Confirmed\n"
                    f"⚡ *FVG Status:* Confirmed Imbalance\n"
                    f"📈 *Current Price:* `{c3_close:.2f}`\n\n"
                    f"⚠️ *Candle agle 3-4s mein close ho rahi hai! (2x Alert)*"
                )
                send_alert(msg)

    except Exception as e:
        print("Analysis Error:", e, flush=True)

def bot_loop():
    time.sleep(3)
    send_alert("⚡ *Gold 5M: 8-9 Candle Sweep Scanner Live!*\nFirst touch ke baad 8-9 candles ke andar sweep hone par 4s pehle alert aayega.")
    
    while True:
        try:
            now = datetime.now(timezone.utc)
            elapsed_seconds = (now.minute % 5) * 60 + now.second
            remaining_seconds = 300 - elapsed_seconds

            sleep_time = remaining_seconds - 4
            if sleep_time > 0:
                time.sleep(sleep_time)

            check_sweep_and_fvg()
            time.sleep(8)
        except Exception as err:
            print("Loop Exception:", err, flush=True)
            time.sleep(5)

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Gold 5M Scanner Running!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        return

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    t = threading.Thread(target=bot_loop, daemon=True)
    t.start()
    server.serve_forever()

if __name__ == "__main__":
    run_server()
          
