"""
BOT TIN TUC - LICH KINH TE + DIA CHINH TRI + MARKET
"""
import requests
import time
import json
import os
from datetime import datetime, timedelta

TOKEN = os.getenv("TELEGRAM_TOKEN", "8893995280:AAF9XwWAm9QgPkwmDrhZdY6UQ4zfySooWpk")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "518284897")
FRED_API_KEY = os.getenv("FRED_API_KEY", "ff3e122af2b2c0a433606476fc6dc5fb")

CHU_KY_TIN_TUC = 600
CHU_KY_LICH = 3600
DATA_FILE = "data/tin_tuc_log.json"

fred_online = None
gdelt_online = None
da_khoi_dong = False
last_lich = 0
fg_last = 0

os.makedirs("data", exist_ok=True)

def load_log():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"events_sent": {}, "news_sent": []}

def save_log(log):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

def gui(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                     data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except: pass

def check_fred():
    global fred_online
    if fred_online is not None: return fred_online
    try:
        r = requests.get(f"https://api.stlouisfed.org/fred/series/observations?series_id=DFF&api_key={FRED_API_KEY}&file_type=json&limit=1", timeout=10)
        fred_online = r.status_code == 200
    except: fred_online = False
    return fred_online

def check_gdelt():
    global gdelt_online
    if gdelt_online is not None: return gdelt_online
    try:
        r = requests.get("https://api.gdeltproject.org/api/v2/doc/doc?query=war&mode=artlist&format=json&maxrecords=1", timeout=10)
        gdelt_online = r.status_code == 200
    except: gdelt_online = False
    return gdelt_online

def get_fred_value(series_id):
    if not check_fred(): return None
    try:
        r = requests.get(f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={FRED_API_KEY}&file_type=json&limit=2&sort_order=desc", timeout=10)
        if r.status_code == 200:
            obs = r.json().get('observations', [])
            vals = [{'date': o['date'], 'value': float(o['value'])} for o in obs if o.get('value', '.') != '.']
            return vals if vals else None
    except: pass
    return None

def get_econ_text():
    if not check_fred(): return "📡 FRED offline"
    lines = ["📊 DU LIEU KINH TE MY (FRED)", "━" * 20]
    for sid, label in [('DFF','🏦 Fed Rate'),('CPIAUCSL','📈 CPI'),('UNRATE','👥 That nghiep'),('GDP','📊 GDP'),('PPIACO','🏭 PPI')]:
        v = get_fred_value(sid)
        if v: lines.append(f"{label}: {v[0]['value']} ({v[0]['date']})")
    return "\n".join(lines) if len(lines) > 2 else "📡 Dang cho..."

EVENTS = [
    {'id':'nfp','name':'💼 Non-Farm Payrolls','date':'2026-06-05','time':'19:30','impact':'🔴 HIGH','desc':'Bao cao viec lam phi nong nghiep My.','fred':'UNRATE','fmt':'That nghiep: {value}% (truoc: {prev}%)'},
    {'id':'cpi','name':'📊 CPI Report','date':'2026-06-11','time':'19:30','impact':'🔴 HIGH','desc':'Chi so gia tieu dung - thước do lam phat.','fred':'CPIAUCSL','fmt':'CPI: {value} (truoc: {prev})'},
    {'id':'ppi','name':'🏭 PPI Report','date':'2026-06-12','time':'19:30','impact':'🟡 MEDIUM','desc':'Chi so gia san xuat.','fred':'PPIACO','fmt':'PPI: {value} (truoc: {prev})'},
    {'id':'fomc','name':'🏦 FOMC Rate Decision','date':'2026-06-18','time':'01:00','impact':'🔴 HIGH','desc':'Quyet dinh lai suat Fed - SU KIEN QUAN TRONG NHAT.','fred':'DFF','fmt':'Fed Rate: {value}% (truoc: {prev}%) - Fed {action}'},
    {'id':'gdp','name':'📊 GDP Q2 2026','date':'2026-06-25','time':'19:30','impact':'🔴 HIGH','desc':'Tang truong kinh te My.','fred':'GDP','fmt':'GDP: ${value:,.0f}B (truoc: ${prev:,.0f}B)'},
    {'id':'fomc7','name':'🏦 FOMC Rate Decision (T7)','date':'2026-07-30','time':'01:00','impact':'🔴 HIGH','desc':'Quyet dinh lai suat giua nam 2026.','fred':'DFF','fmt':'Fed Rate: {value}% (truoc: {prev}%) - Fed {action}'},
]

def check_events():
    log = load_log()
    now = datetime.now()
    today = now.date()
    msgs = []
    for ev in EVENTS:
        evd = datetime.strptime(ev['date'], '%Y-%m-%d').date()
        evdt = datetime.strptime(ev['date']+' '+ev['time'], '%Y-%m-%d %H:%M')
        d = (evd - today).days
        h = (now - evdt).total_seconds()/3600 if evdt < now else -1
        if 0 <= d <= 3:
            k = f"pre_{ev['id']}"
            if time.time() - log['events_sent'].get(k,0) >= 43200:
                log['events_sent'][k] = time.time()
                cd = f"⚠️ HOM NAY {ev['time']}" if d==0 else f"📅 NGAY MAI {ev['time']}" if d==1 else f"📅 Con {d} ngay - {ev['date']} {ev['time']}"
                msgs.append(f"📅 {ev['name']}\n⏰ {cd} (UTC+7)\n⚡ {ev['impact']}\n📝 {ev['desc']}\n\n{get_econ_text()}")
        elif d < 0 and 1 <= h <= 72:
            k = f"post_{ev['id']}"
            if k not in log['events_sent'] and check_fred():
                v = get_fred_value(ev['fred'])
                if v and len(v) >= 2:
                    c, p = v[0]['value'], v[1]['value']
                    a = "TANG 🦅" if c>p else ("GIAM 🕊️" if c<p else "GIU NGUYEN")
                    log['events_sent'][k] = time.time()
                    msgs.append(f"✅ KET QUA: {ev['name']}\n📊 {ev['fmt'].format(value=c, prev=p, action=a)}\n\n{get_econ_text()}")
    save_log(log)
    return msgs

def get_news():
    if not check_gdelt(): return []
    try:
        q = "war OR conflict OR ukraine OR russia OR israel OR iran OR nato OR missile OR tariff OR strike OR putin OR zelensky OR netanyahu OR north korea"
        r = requests.get(f"https://api.gdeltproject.org/api/v2/doc/doc?query={requests.utils.quote(q)}&mode=artlist&format=json&maxrecords=5&sort=datedesc", timeout=15)
        if r.status_code != 200: return []
        arts = r.json().get('articles', [])
        log = load_log()
        news = []
        for a in arts[:5]:
            t = a.get('title',''); u = a.get('url',''); s = a.get('domain','?'); tone = float(a.get('tone','0'))
            if u in log['news_sent']: continue
            log['news_sent'].append(u)
            if tone < -5: imp = "🔴🔴🔴 CUC KY TIEU CUC"
            elif tone < -2: imp = "🔴🔴 TIEU CUC"
            elif tone > 5: imp = "🟢🟢🟢 CUC KY TICH CUC"
            elif tone > 2: imp = "🟢🟢 TICH CUC"
            else: imp = "⚪ TRUNG TINH"
            g = "🟢 TANG" if tone<-3 else ("🔴 GIAM" if tone>3 else "⚪ IT BIEN DONG")
            cr = "🔴 GIAM" if tone<-3 else ("🟢 TANG" if tone>3 else "⚪ IT BIEN DONG")
            kn = "⚠️ UU TIEN SHORT" if tone<-3 else ("✅ UU TIEN LONG" if tone>3 else "⏳ CHO DOI")
            news.append({'t':t,'s':s,'imp':imp,'sc':tone,'g':g,'cr':cr,'kn':kn})
        log['news_sent'] = log['news_sent'][-50:]
        save_log(log)
        return news
    except: return []

def get_fg():
    global fg_last
    if time.time() - fg_last < 3600: return None
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        d = r.json()['data'][0]
        v = int(d['value']); c = d['value_classification']
        i = "😱" if v<=25 else "😟" if v<=40 else "😐" if v<=60 else "😊" if v<=75 else "🤤"
        fg_last = time.time()
        return f"{i} Fear & Greed: {v}/100 - {c}"
    except: return None

# === MAIN ===
print("=" * 40)
print("📰 BOT TIN TUC")
print(f"FRED: {check_fred()} | GDELT: {check_gdelt()}")
print("=" * 40)

while True:
    try:
        if not da_khoi_dong:
            da_khoi_dong = True
            gui(f"📰 Bot tin tuc da khoi dong!\n━" * 15 + f"\n📡 FRED: {'✅ Online' if check_fred() else '⏳ Offline'}\n📡 GDELT: {'✅ Online' if check_gdelt() else '⏳ Offline'}\n\n✅ Dang theo doi su kien...")

        for n in get_news():
            gui(f"📰 TIN TUC THI TRUONG {n['imp']}\n━" * 20 + f"\n{n['t']}\n\n📡 Nguon: {n['s']}\n⚡ Score: {n['sc']:.0f}\n\n🥇 Vang: {n['g']}\n₿ Crypto: {n['cr']}\n💡 Khuyen nghi: {n['kn']}\n🕐 {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}")
            time.sleep(1)

        if time.time() - last_lich >= CHU_KY_LICH:
            last_lich = time.time()
            for m in check_events():
                gui(m)

        fg = get_fg()
        if fg: gui(fg)

        time.sleep(CHU_KY_TIN_TUC)
    except KeyboardInterrupt: break
    except Exception as e:
        print(f"Loi: {e}")
        time.sleep(30)