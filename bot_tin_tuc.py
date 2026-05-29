"""
BOT TIN TUC - LICH KINH TE + DIA CHINH TRI
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
DA_KHOI_DONG = False

fred_online = None
gdelt_online = None

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
    except:
        pass

def check_fred():
    global fred_online
    if fred_online is not None:
        return fred_online
    try:
        r = requests.get(f"https://api.stlouisfed.org/fred/series/observations?series_id=DFF&api_key={FRED_API_KEY}&file_type=json&limit=1", timeout=10)
        fred_online = r.status_code == 200
    except:
        fred_online = False
    return fred_online

def check_gdelt():
    global gdelt_online
    if gdelt_online is not None:
        return gdelt_online
    try:
        r = requests.get("https://api.gdeltproject.org/api/v2/doc/doc?query=war&mode=artlist&format=json&maxrecords=1", timeout=10)
        gdelt_online = r.status_code == 200
    except:
        gdelt_online = False
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
    for sid, label in [('DFF', '🏦 Fed Rate'), ('CPIAUCSL', '📈 CPI'), ('UNRATE', '👥 That nghiep'), ('GDP', '📊 GDP'), ('PPIACO', '🏭 PPI')]:
        v = get_fred_value(sid)
        if v: lines.append(f"{label}: {v[0]['value']} ({v[0]['date']})")
    return "\n".join(lines) if len(lines) > 2 else "📡 Dang cho..."

EVENTS = [
    {'id':'nfp','name':'💼 Non-Farm Payrolls','date':'2026-06-05','time':'19:30','impact':'🔴 HIGH','desc':'Bao cao viec lam.','fred':'UNRATE','fmt':'That nghiep: {value}% (truoc: {prev}%)'},
    {'id':'cpi','name':'📊 CPI Report','date':'2026-06-11','time':'19:30','impact':'🔴 HIGH','desc':'Lam phat tieu dung.','fred':'CPIAUCSL','fmt':'CPI: {value} (truoc: {prev})'},
    {'id':'fomc','name':'🏦 FOMC Rate Decision','date':'2026-06-18','time':'01:00','impact':'🔴 HIGH','desc':'Quyet dinh lai suat Fed.','fred':'DFF','fmt':'Fed Rate: {value}% (truoc: {prev}%) - {action}'},
    {'id':'gdp','name':'📊 GDP Q2','date':'2026-06-25','time':'19:30','impact':'🔴 HIGH','desc':'Tang truong kinh te.','fred':'GDP','fmt':'GDP: ${value:,.0f}B (truoc: ${prev:,.0f}B)'},
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
            if time.time() - log['events_sent'].get(k, 0) >= 43200:
                log['events_sent'][k] = time.time()
                cd = f"HOM NAY {ev['time']}" if d==0 else f"NGAY MAI {ev['time']}" if d==1 else f"Con {d} ngay - {ev['date']} {ev['time']}"
                msgs.append(f"📅 {ev['name']}\n⏰ {cd}\n⚡ {ev['impact']}\n📝 {ev['desc']}\n\n{get_econ_text()}")
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
        q = "war OR conflict OR ukraine OR russia OR israel OR iran OR nato OR missile OR tariff"
        r = requests.get(f"https://api.gdeltproject.org/api/v2/doc/doc?query={requests.utils.quote(q)}&mode=artlist&format=json&maxrecords=3&sort=datedesc", timeout=15)
        if r.status_code != 200: return []
        arts = r.json().get('articles', [])
        log = load_log()
        news = []
        for a in arts[:3]:
            t = a.get('title',''); u = a.get('url',''); s = a.get('domain','?'); tone = float(a.get('tone','0'))
            if u in log['news_sent']: continue
            log['news_sent'].append(u)
            imp = "🔴🔴🔴" if tone<-5 else "🔴🔴" if tone<-2 else "🟢🟢" if tone>2 else "⚪"
            g = "🟢 TANG" if tone<-3 else ("🔴 GIAM" if tone>3 else "⚪")
            cr = "🔴 GIAM" if tone<-3 else ("🟢 TANG" if tone>3 else "⚪")
            kn = "⚠️ SHORT" if tone<-3 else ("✅ LONG" if tone>3 else "⏳ CHO")
            news.append({'t':t,'s':s,'imp':imp,'sc':tone,'g':g,'cr':cr,'kn':kn})
        log['news_sent'] = log['news_sent'][-50:]
        save_log(log)
        return news
    except: return []

_fg_last = 0
def get_fg():
    global _fg_last
    if time.time() - _fg_last < 3600: return None
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        d = r.json()['data'][0]
        v = int(d['value']); c = d['value_classification']
        i = "😱" if v<=25 else "😟" if v<=40 else "😐" if v<=60 else "😊" if v<=75 else "🤤"
        _fg_last = time.time()
        return f"{i} Fear & Greed: {v}/100 - {c}"
    except: return None

# === MAIN ===
print("BOT TIN TUC STARTED")
last_lich = 0

while True:
    try:
        global DA_KHOI_DONG
        if not DA_KHOI_DONG:
            DA_KHOI_DONG = True
            gui(f"📰 Bot tin tuc da khoi dong!\n📡 FRED: {'✅' if check_fred() else '⏳'}\n📡 GDELT: {'✅' if check_gdelt() else '⏳'}")

        for n in get_news():
            gui(f"📰 {n['imp']}\n{n['t']}\n📡 {n['s']} (Score:{n['sc']:.0f})\n🥇 Vang:{n['g']} | ₿ Crypto:{n['cr']}\n💡 {n['kn']}")
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