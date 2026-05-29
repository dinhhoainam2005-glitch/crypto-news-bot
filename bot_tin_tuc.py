import requests
import os
import time
from datetime import datetime

TOKEN = os.getenv("TELEGRAM_TOKEN", "8893995280:AAF9XwWAm9QgPkwmDrhZdY6UQ4zfySooWpk")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "518284897")

def gui(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                     data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except:
        pass

# Chi gui 1 lan
gui(f"✅ Bot hoat dong! {datetime.now().strftime('%H:%M:%S')}")

# Test FRED
try:
    r = requests.get("https://api.stlouisfed.org/fred/series/observations?series_id=DFF&api_key=ff3e122af2b2c0a433606476fc6dc5fb&file_type=json&limit=1", timeout=10)
    if r.status_code == 200:
        gui("✅ FRED API: ONLINE")
    else:
        gui(f"FRED: {r.status_code}")
except Exception as e:
    gui(f"FRED loi: {str(e)[:50]}")

# Test GDELT
try:
    r = requests.get("https://api.gdeltproject.org/api/v2/doc/doc?query=war&mode=artlist&format=json&maxrecords=1", timeout=10)
    if r.status_code == 200:
        gui("✅ GDELT API: ONLINE")
    else:
        gui(f"GDELT: {r.status_code}")
except Exception as e:
    gui(f"GDELT loi: {str(e)[:50]}")

gui("⏳ Bot se chay tiep...")
time.sleep(30)
gui("✅ Van hoat dong!")