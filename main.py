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

def is_us_dst(dt_utc):
    year = dt_utc.year
    mar_first = datetime(year, 3, 1, tzinfo=timezone.utc)
    mar_second_sun = 14 - (mar_first.weekday() + 1) % 7
    dst_start = datetime(year, 3, mar_second_sun, 2, tzinfo=timezone.utc)

    nov_first = datetime(year, 11, 1, tzinfo=timezone.utc)
    nov_first_sun = 7 - (nov_first.weekday() + 1) % 7
    if nov_first_sun == 0:
        nov_first_sun = 7
    dst_end = datetime(year, 11, nov_first_sun, 2, tzinfo=timezone.utc)

    return dst_start <= dt_utc < dst_end

def check_institutional_setup():
    global last_alert_time

    if not is_market_open():
        return

    now_utc = datetime.now(timezone.utc)
    dst_active = is_us_dst(now_utc)

    # 1. 1-Hour Trend Direction (Anti-Trend Breakout Protection)
    c1h = get_candles("1h", 10)
    if not c1h or len(c1h) < 5:
        return

    h1_close = float(c1h[0]["close"])
    h1_sma = sum([float(x["close"]) for x in c1h[:5]]) / 5.0
    h1_bullish = h1_close > h1_sma
    h1_bearish = h1_close < h1_sma

    # 2. Previous Day High & Low (PDH / PDL)
    daily = get_candles("1day", 5)
    if not daily or len(daily) < 2:
        return
    pdh = float(daily[1]["high"])
    pdl = float(daily[1]["low"])

    # 3. Dynamic Asian Range (Auto Sardi/Garmi DST)
    c15m = get_candles("15min", 50)
    if not c15m or len(c15m) < 10:
        return

    asia_candles = []
    asia_start = 0 if dst_active else 1
    asia_end = 6 if dst_active else 7

    for c in c15m:
        try:
            dt = datetime.strptime(c["datetime"], "%Y-%m-%d %H:%M:%S")
            if asia_start <= dt.hour < asia_end:
                asia_candles.append(c)
        except:
            pass

    asia_high = max([float(x["high"]) for x in asia_candles]) if asia_candles else pdh
    asia_low = min([float(x["low"]) for x in asia_candles]) if asia_candles else pdl

    # 4. 15-Minute Level Check: Wick-Only Sweep Validation (No body close outside)
    recent_15m = c15m[0]
    m15_high = float(recent_15m["high"])
    m15_low = float(recent_15m["low"])
    m15_close = float(recent_15m["close"])
    m15_open = float(recent_15m["open"])
    m15_body_top = max(m15_open, m15_close)
    m15_body_bottom = min(m15_open, m15_close)

    valid_bearish_sweep = False
    valid_bullish_sweep = False
    swept_level = 0.0
    level_type = ""

    # Bearish Sweep: Wick upar gayi par body level ke niche close hui
    for ref_level, name in [(pdh, "Previous Day High (PDH)"), (asia_high, "Asian Session High")]:
        if m15_high >= ref_level and m15_body_top < ref_level:
            valid_bearish_sweep = True
            swept_level = ref_level
            level_type = name
            break

    # Bullish Sweep: Wick niche gayi par body level ke upar close hui
    for ref_level, name in [(pdl, "Previous Day Low (PDL)"), (asia_low, "Asian Session Low")]:
        if m15_low <= ref_level and m15_body_bottom > ref_level:
            valid_bullish_sweep = True
            swept_level = ref_level
            level_type = name
            break

    # 5. 1-Minute MSS & Clean Unmitigated FVG Check
    c1m = get_candles("1min", 25)
    if not c1m or len(c1m) < 12:
        return

    c3 = c1m[0]  # Candle 3 (Current closing candle)
    c2 = c1m[1]  # Candle 2 (Displacement Impulse candle)
    c1 = c1m[2]  # Candle 1 (Reversal leg start)

    alert_time_key = c3["datetime"]
    if alert_time_key == last_alert_time:
        return

    c3_open, c3_close = float(c3["open"]), float(c3["close"])
    c3_high, c3_low = float(c3["high"]), float(c3["low"])

    c2_open, c2_close = float(c2["open"]), float(c2["close"])
    c2_high, c2_low = float(c2["high"]), float(c2["low"])

    c1_open, c1_close = float(c1["open"]), float(c1["close"])
    c1_high, c1_low = float(c1["high"]), float(c1["low"])

    recent_swing_high = max([float(x["high"]) for x in c1m[3:12]])
    recent_swing_low = min([float(x["low"]) for x in c1m[3:12]])

    # -------------------------------------------------------------
    # SETUP 1: SELL (Unmitigated Bearish FVG Check)
    # -------------------------------------------------------------
    if valid_bearish_sweep and not h1_bullish:
        c1_green = c1_close > c1_open
        c2_red = c2_close < c2_open
        c3_red = c3_close < c3_open

        # FVG Zone: c3_high se lekar c1_low tak
        fvg_gap = c1_low - c3_high
        mss_done = (c2_close < recent_swing_low) or (c3_close < recent_swing_low)

        # UNMITIGATED CHECK:
        # Candle 3 ki upper wick ne FVG box ko pehle hi touch nahi kiya hona chahiye
        unmitigated = c3_high < c1_low

        if c1_green and c2_red and c3_red and (fvg_gap >= 1.00) and mss_done and unmitigated:
            last_alert_time = alert_time_key
            highest_sweep = max(c1_high, c2_high, c3_high, m15_high)
            fvg_entry = c3_high  # Entry jab next candle yahan tap kare
            sl = round(highest_sweep + 1.60, 2)
            risk = sl - fvg_entry
            tp1 = round(fvg_entry - (risk * 2.0), 2)
            tp2 = round(fvg_entry - (risk * 3.5), 2)

            msg = (
                f"🔴 *XAU/USD: INSTITUTIONAL SELL SETUP* 🔴\n\n"
                f"⏰ *Time:* `{alert_time_key}`\n"
                f"🏛️ *Sweep:* `{swept_level:.2f}` ({level_type}) - *Wick Only*\n"
                f"🔄 *MSS:* 1M Micro Swing Low Body Broken\n"
                f"📊 *Fresh FVG Gap:* `${fvg_gap:.2f}` (Unmitigated)\n\n"
                f"⚡ *1M FVG ZONE:* `{c3_high:.2f} - {c1_low:.2f}`\n"
                f"🎯 *ACTION:* Ye FVG bilkul fresh hai! Next candle is box me *TAP* kare tab SELL execute karein.\n\n"
                f"📌 *ORDER PARAMETERS:*\n"
                f"• *Entry:* `{fvg_entry:.2f}` (FVG Tap)\n"
                f"• *Stop Loss (SL):* `{sl:.2f}`\n"
                f"• *Target 1 (1:2 RR):* `{tp1:.2f}`\n"
                f"• *Target 2 (1:3.5 RR):* `{tp2:.2f}`\n\n"
                f"⚠️ *1M Candle 3-4s me close ho rahi hai! (2x Alert)*"
            )
            send_alert(msg)
            return

    # -------------------------------------------------------------
    # SETUP 2: BUY (Unmitigated Bullish FVG Check)
    # -------------------------------------------------------------
    if valid_bullish_sweep and not h1_bearish:
        c1_red = c1_close < c1_open
        c2_green = c2_close > c2_open
        c3_green = c3_close > c3_open

        # FVG Zone: c1_high se lekar c3_low tak
        fvg_gap = c3_low - c1_high
        mss_done = (c2_close > recent_swing_high) or (c3_close > recent_swing_high)

        # UNMITIGATED CHECK:
        # Candle 3 ki lower wick ne FVG box ko pehle hi touch nahi kiya hona chahiye
        unmitigated = c3_low > c1_high

        if c1_red and c2_green and c3_green and (fvg_gap >= 1.00) and mss_done and unmitigated:
            last_alert_time = alert_time_key
            lowest_sweep = min(c1_low, c2_low, c3_low, m15_low)
            fvg_entry = c3_low  # Entry jab next candle yahan tap kare
            sl = round(lowest_sweep - 1.60, 2)
            risk = fvg_entry - sl
            tp1 = round(fvg_entry + (risk * 2.0), 2)
            tp2 = round(fvg_entry + (risk * 3.5), 2)

            msg = (
                f"🟢 *XAU/USD: INSTITUTIONAL BUY SETUP* 🟢\n\n"
                f"⏰ *Time:* `{alert_time_key}`\n"
                f"🏛️ *Sweep:* `{swept_level:.2f}` ({level_type}) - *Wick Only*\n"
                f"🔄 *MSS:* 1M Micro Swing High Body Broken\n"
                f"📊 *Fresh FVG Gap:* `${fvg_gap:.2f}` (Unmitigated)\n\n"
                f"⚡ *1M FVG ZONE:* `{c1_high:.2f} - {c3_low:.2f}`\n"
                f"🎯 *ACTION:* Ye FVG bilkul fresh hai! Next candle is box me *TAP* kare tab BUY execute karein.\n\n"
                f"📌 *ORDER PARAMETERS:*\n"
                f"• *Entry:* `{fvg_entry:.2f}` (FVG Tap)\n"
                f"• *Stop Loss (SL):* `{sl:.2f}`\n"
                f"• *Target 1 (1:2 RR):* `{tp1:.2f}`\n"
                f"• *Target 2 (1:3.5 RR):* `{tp2:.2f}`\n\n"
                f"⚠️ *1M Candle 3-4s me close ho rahi hai! (2x Alert)*"
            )
            send_alert(msg)
            return

def bot_loop():
    time.sleep(3)
    send_alert("⚡ *Gold Strict Unmitigated SMC Scanner Live!*\nCandle 3 agar FVG ko touch karke jaayegi toh alert reject ho jaayega. Sirf 100% fresh aur open FVG par alert aayega.")
    
    while True:
        try:
            now = datetime.now(timezone.utc)
            remaining_seconds = 60 - now.second

            sleep_time = remaining_seconds - 4
            if sleep_time > 0:
                time.sleep(sleep_time)

            check_institutional_setup()
            time.sleep(6)
        except Exception as err:
            print("Loop Exception:", err, flush=True)
            time.sleep(4)

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Gold Unmitigated SMC Bot Running!")

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
    
