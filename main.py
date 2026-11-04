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
            requests.post(url, json=payload, timeout=10)
            time.sleep(1)
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"Telegram error for {cid}:", e, flush=True)

def is_market_open():
    now_utc = datetime.now(timezone.utc)
    weekday = now_utc.weekday()
    hour = now_utc.hour

    if weekday == 5:
        return False
    if weekday == 4 and hour >= 21:
        return False
    if weekday == 6 and hour < 21:
        return False
    return True

def get_candles(interval, count):
    url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval={interval}&outputsize={count}&apikey={API_KEY}"
    try:
        res = requests.get(url, timeout=10).json()
        if "values" in res:
            return res["values"]
    except Exception as e:
        print(f"Fetch error for {interval}:", e, flush=True)
    return None

def check_multiday_level_and_1m_reversal():
    global last_alert_time

    if not is_market_open():
        return

    # 1. 2 Din Se 10-15 Din Purane Major Levels Extract Karein (Daily + 4H timeframe)
    daily_candles = get_candles("1day", 15)  # Pichhle 15 dino ka data
    h4_candles = get_candles("4h", 40)       # Pichhle 7-10 dino ka 4H data

    if not daily_candles or not h4_candles:
        return

    major_levels = []

    # Daily key levels (High, Low, Body Open, Body Close)
    for c in daily_candles[1:]:  # Aaj ki candle chhodkar pichhle 2 se 14 din
        major_levels.append(("Daily High", float(c["high"])))
        major_levels.append(("Daily Low", float(c["low"])))
        major_levels.append(("Daily Body", max(float(c["open"]), float(c["close"]))))
        major_levels.append(("Daily Body", min(float(c["open"]), float(c["close"]))))

    # 4-Hour key swing levels (Pichhle 2-10 din ke 4H levels)
    for c in h4_candles[6:]:  # Pichhle 24 ghante ke baad ke purane swings
        major_levels.append(("4H Level", float(c["high"])))
        major_levels.append(("4H Level", float(c["low"])))

    # 2. Check Karein Ki Current Price Kis Multi-Day Level Par Reversal De Rahi Hai
    c1m = get_candles("1min", 15)
    if not c1m or len(c1m) < 5:
        return

    # c1m[0] = Candle 3 (Current closing candle jo 3-4s me close hogi)
    # c1m[1] = Candle 2 (Impulse candle jisme FVG hona compulsory hai)
    # c1m[2] = Candle 1 (Opposite color first reversal candle)
    c3 = c1m[0]
    c2 = c1m[1]
    c1 = c1m[2]

    alert_time_key = c3["datetime"]
    if alert_time_key == last_alert_time:
        return

    c3_open, c3_close = float(c3["open"]), float(c3["close"])
    c3_high, c3_low = float(c3["high"]), float(c3["low"])

    c2_open, c2_close = float(c2["open"]), float(c2["close"])
    c2_high, c2_low = float(c2["high"]), float(c2["low"])

    c1_open, c1_close = float(c1["open"]), float(c1["close"])
    c1_high, c1_low = float(c1["high"]), float(c1["low"])

    # 3 Candles ka total reach
    formation_high = max(c1_high, c2_high, c3_high)
    formation_low = min(c1_low, c2_low, c3_low)

    # -------------------------------------------------------------
    # SETUP 1: SELL (Purana 2-10 Din Ka Resistance Level Tested)
    # -------------------------------------------------------------
    # Pattern: Candle 1 GREEN -> Candle 2 RED (FVG) -> Candle 3 RED
    c1_green = c1_close > c1_open
    c2_red = c2_close < c2_open
    c3_red = c3_close < c3_open
    has_bearish_fvg = c3_high < c1_low  # Candle 2 par FVG

    if c1_green and c2_red and c3_red and has_bearish_fvg:
        # Check karein ki kya ye 3-candle setup kisi 2-10 din purane major high/body par bana hai
        for lvl_name, lvl_price in major_levels:
            # Level ko wick sweep kiya ya body touch karke niche reject hua
            if abs(formation_high - lvl_price) <= 1.2 or (formation_high >= lvl_price and c3_close < lvl_price):
                last_alert_time = alert_time_key
                fvg_top = c1_low
                fvg_bottom = c3_high
                msg = (
                    f"🚨 *XAU/USD: MULTI-DAY KEY LEVEL REVERSAL (SELL)* 🚨\n\n"
                    f"⏰ *Time:* `{alert_time_key}`\n"
                    f"🏛️ *Tested Level:* `{lvl_price:.2f}` ({lvl_name} - 2 to 10 Days Old)\n"
                    f"🕯️ *Candle 1:* Green (Level Touch/Sweep)\n"
                    f"🕯️ *Candle 2:* Red (Impulse FVG Created)\n"
                    f"🕯️ *Candle 3:* Red (Confirmed Drop)\n"
                    f"⚡ *Candle 2 FVG Zone:* `{fvg_bottom:.2f} - {fvg_top:.2f}`\n"
                    f"🎯 *Entry Rule:* FVG Zone *TAP* hone par SELL execute karein!\n"
                    f"📉 *Current Price:* `{c3_close:.2f}`\n\n"
                    f"⚠️ *1M Candle 3-4s me close ho rahi hai! (2x Alert)*"
                )
                send_alert(msg)
                return

    # -------------------------------------------------------------
    # SETUP 2: BUY (Purana 2-10 Din Ka Support Level Tested)
    # -------------------------------------------------------------
    # Pattern: Candle 1 RED -> Candle 2 GREEN (FVG) -> Candle 3 GREEN
    c1_red = c1_close < c1_open
    c2_green = c2_close > c2_open
    c3_green = c3_close > c3_open
    has_bullish_fvg = c3_low > c1_high  # Candle 2 par FVG

    if c1_red and c2_green and c3_green and has_bullish_fvg:
        # Check karein ki kya ye 3-candle setup kisi 2-10 din purane major low/body par bana hai
        for lvl_name, lvl_price in major_levels:
            # Level ko wick sweep kiya ya body touch karke upar bounce hua
            if abs(formation_low - lvl_price) <= 1.2 or (formation_low <= lvl_price and c3_close > lvl_price):
                last_alert_time = alert_time_key
                fvg_top = c3_low
                fvg_bottom = c1_high
                msg = (
                    f"🚨 *XAU/USD: MULTI-DAY KEY LEVEL REVERSAL (BUY)* 🚨\n\n"
                    f"⏰ *Time:* `{alert_time_key}`\n"
                    f"🏛️ *Tested Level:* `{lvl_price:.2f}` ({lvl_name} - 2 to 10 Days Old)\n"
                    f"🕯️ *Candle 1:* Red (Level Touch/Sweep)\n"
                    f"🕯️ *Candle 2:* Green (Impulse FVG Created)\n"
                    f"🕯️ *Candle 3:* Green (Confirmed Bounce)\n"
                    f"⚡ *Candle 2 FVG Zone:* `{fvg_bottom:.2f} - {fvg_top:.2f}`\n"
                    f"🎯 *Entry Rule:* FVG Zone *TAP* hone par BUY execute karein!\n"
                    f"📈 *Current Price:* `{c3_close:.2f}`\n\n"
                    f"⚠️ *1M Candle 3-4s me close ho rahi hai! (2x Alert)*"
                )
                send_alert(msg)
                return

def bot_loop():
    time.sleep(3)
    send_alert("⚡ *Gold Multi-Day Key Level Bot Live!*\n2 se 10 din purane major levels touch hone par 1M 3-candle FVG reversal par alert aayega.")
    
    while True:
        try:
            now = datetime.now(timezone.utc)
            remaining_seconds = 60 - now.second

            sleep_time = remaining_seconds - 4
            if sleep_time > 0:
                time.sleep(sleep_time)

            check_multiday_level_and_1m_reversal()
            time.sleep(6)
        except Exception as err:
            print("Loop Exception:", err, flush=True)
            time.sleep(4)

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Gold Multi-Day Scanner Running!")

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
    
