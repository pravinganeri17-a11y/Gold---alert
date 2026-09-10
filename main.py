import time
import requests

TELEGRAM_TOKEN = "8163156265:AAGuUYBf6urAsJhkzScZDiJhzt1GysNXn58"
CHAT_ID = "6422746952"
API_KEY = "DEMO_KEY"

last_candle_time = ""

def send_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, json=payload, timeout=5)
    except:
        pass

def check_inside_bar():
    global last_candle_time
    url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=15min&outputsize=5&apikey={API_KEY}"
    try:
        res = requests.get(url, timeout=10).json()
        if "values" not in res:
            return

        candles = res["values"]
        c1 = candles[1]
        c2 = candles[2]
        c_time = c1["datetime"]

        c1_h, c1_l = float(c1["high"]), float(c1["low"])
        c2_h, c2_l = float(c2["high"]), float(c2["low"])

        if (c1_h < c2_h) and (c1_l > c2_l):
            if c_time != last_candle_time:
                last_candle_time = c_time
                msg = f"🔔 XAUUSD 15M: Inside Bar Formed!\n\nTime: {c_time}\nHigh: {c1_h}\nLow: {c1_l}\nStatus: Confirmed Closed"
                send_alert(msg)
    except:
        pass

while True:
    check_inside_bar()
    time.sleep(15)
