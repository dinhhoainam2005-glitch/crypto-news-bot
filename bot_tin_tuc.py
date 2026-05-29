"""
BOT TIN TUC - LICH KINH TE + DIA CHINH TRI + MARKET
"""
import requests
import time
import json
import os
from datetime import datetime, timedelta

# ============================================
# ENVIRONMENT VARIABLES
# ============================================
TOKEN = os.getenv("TELEGRAM_TOKEN", "8893995280:AAF9XwWAm9QgPkwmDrhZdY6UQ4zfySooWpk")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "518284897")
FRED_API_KEY = os.getenv("FRED_API_KEY", "ff3e122af2b2c0a433606476fc6dc5fb")

# ============================================
# CAU HINH
# ============================================
CHU_KY_TIN_TUC = 600
CHU_KY_LICH = 3600
DATA_FILE = "data/tin_tuc_log.json"

fred_online = None
gdelt_online = None
da_khoi_dong = False  # <<< DUNG BIEN NAY

# ============================================
# GHI LOG
# ============================================
os.makedirs("data", exist_ok=True)

def load_log():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"events_sent": {}, "news_sent": []}

def save_log(log):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

# ============================================
# GỬI TELEGRAM
# ============================================
def gui_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
    except:
        pass

# ============================================
# KIEM TRA API
# ============================================
def check_fred():
    global fred_online
    if fred_online is not None:
        return fred_online
    try:
        r = requests.get(
            f"https://api.stlouisfed.org/fred/series/observations?series_id=DFF&api_key={FRED_API_KEY}&file_type=json&limit=1",
            timeout=10
        )
        fred_online = r.status_code == 200
    except:
        fred_online = False
    return fred_online

def check_gdelt():
    global gdelt_online
    if gdelt_online is not None:
        return gdelt_online
    try:
        r = requests.get(
            "https://api.gdeltproject.org/api/v2/doc/doc?query=war&mode=artlist&format=json&maxrecords=1",
            timeout=10
        )
        gdelt_online = r.status_code == 200
    except:
        gdelt_online = False
    return gdelt_online

# ============================================
# FRED API
# ============================================
def get_fred_value(series_id):
    if not check_fred():
        return None
    try:
        r = requests.get(
            f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={FRED_API_KEY}&file_type=json&limit=2&sort_order=desc",
            timeout=10
        )
        if r.status_code == 200:
            obs = r.json().get('observations', [])
            values = []
            for o in obs:
                if o.get('value', '.') != '.':
                    values.append({'date': o['date'], 'value': float(o['value'])})
            return values if values else None
    except:
        pass
    return None

def get_econ_text():
    if not check_fred():
        return "📡 FRED offline"
    lines = ["📊 DU LIEU KINH TE MY (FRED)", "━" * 20]
    fed = get_fred_value('DFF')
    if fed: lines.append(f"🏦 Fed Rate: {fed[0]['value']}% ({fed[0]['date']})")
    cpi = get_fred_value('CPIAUCSL')
    if cpi: lines.append(f"📈 CPI: {cpi[0]['value']:.1f} ({cpi[0]['date']})")
    ue = get_fred_value('UNRATE')
    if ue: lines.append(f"👥 That nghiep: {ue[0]['value']}% ({ue[0]['date']})")
    gdp = get_fred_value('GDP')
    if gdp: lines.append(f"📊 GDP: ${gdp[0]['value']:,.0f}B ({gdp[0]['date']})")
    ppi = get_fred_value('PPIACO')
    if ppi: lines.append(f"🏭 PPI: {ppi[0]['value']:.1f} ({ppi[0]['date']})")
    return "\n".join(lines) if len(lines) > 2 else "📡 Dang cho du lieu..."

# ============================================
# LICH KINH TE
# ============================================
KINH_TE_EVENTS = [
    {'id': 'nfp_2026-06-05', 'name': '💼 Non-Farm Payrolls (T5)', 'date': '2026-06-05', 'time': '19:30', 'impact': '🔴 HIGH', 'desc': 'Bao cao viec lam phi nong nghiep My.', 'fred_series': 'UNRATE', 'result_text': 'Ty le that nghiep: {value}% (truoc: {prev}%)'},
    {'id': 'cpi_2026-06-11', 'name': '📊 CPI Report (T5)', 'date': '2026-06-11', 'time': '19:30', 'impact': '🔴 HIGH', 'desc': 'Chi so gia tieu dung.', 'fred_series': 'CPIAUCSL', 'result_text': 'CPI: {value} (truoc: {prev})'},
    {'id': 'ppi_2026-06-12', 'name': '🏭 PPI Report (T5)', 'date': '2026-06-12', 'time': '19:30', 'impact': '🟡 MEDIUM', 'desc': 'Chi so gia san xuat.', 'fred_series': 'PPIACO', 'result_text': 'PPI: {value} (truoc: {prev})'},
    {'id': 'fomc_2026-06-18', 'name': '🏦 FOMC Rate Decision (T6)', 'date': '2026-06-18', 'time': '01:00', 'impact': '🔴 HIGH', 'desc': 'Quyet dinh lai suat Fed.', 'fred_series': 'DFF', 'result_text': 'Lai suat Fed: {value}% (truoc: {prev}%) - Fed {action}'},
    {'id': 'gdp_2026-06-25', 'name': '📊 GDP Q2 2026', 'date': '2026-06-25', 'time': '19:30', 'impact': '🔴 HIGH', 'desc': 'Tang truong kinh te My.', 'fred_series': 'GDP', 'result_text': 'GDP: ${value:,.0f}B (truoc: ${prev:,.0f}B)'},
    {'id': 'fomc_2026-07-30', 'name': '🏦 FOMC Rate Decision (T7)', 'date': '2026-07-30', 'time': '01:00', 'impact': '🔴 HIGH', 'desc': 'Quyet dinh lai suat Fed.', 'fred_series': 'DFF', 'result_text': 'Lai suat Fed: {value}% (truoc: {prev}%) - Fed {action}'},
]

def check_lich_kinh_te():
    log = load_log()
    now = datetime.now()
    today = now.date()
    messages = []
    
    for ev in KINH_TE_EVENTS:
        ev_date = datetime.strptime(ev['date'], '%Y-%m-%d').date()
        ev_dt = datetime.strptime(ev['date'] + ' ' + ev['time'], '%Y-%m-%d %H:%M')
        days_until = (ev_date - today).days
        hours_since = (now - ev_dt).total_seconds() / 3600 if ev_dt < now else -1
        
        if 0 <= days_until <= 3:
            key = f"pre_{ev['id']}"
            last = log['events_sent'].get(key, 0)
            if time.time() - last >= 43200:
                log['events_sent'][key] = time.time()
                if days_until == 0:
                    cd = f"⚠️ HOM NAY luc {ev['time']} (UTC+7)"
                elif days_until == 1:
                    cd = f"📅 NGAY MAI luc {ev['time']} (UTC+7)"
                else:
                    cd = f"📅 Con {days_until} ngay - {ev['date']} luc {ev['time']} (UTC+7)"
                msg = f"📅 {ev['name']}\n━" * 15 + f"\n⏰ {cd}\n⚡ {ev['impact']}\n📝 {ev['desc']}\n\n{get_econ_text()}"
                messages.append(msg)
        
        elif days_until < 0 and 1 <= hours_since <= 72:
            key = f"post_{ev['id']}"
            if key not in log['events_sent']:
                if check_fred():
                    values = get_fred_value(ev['fred_series'])
                    if values and len(values) >= 2:
                        c, p = values[0]['value'], values[1]['value']
                        action = ""
                        if 'fomc' in ev['id']:
                            action = "TANG 🦅" if c > p else ("GIAM 🕊️" if c < p else "GIU NGUYEN")
                        result = ev['result_text'].format(value=c, prev=p, action=action)
                        log['events_sent'][key] = time.time()
                        msg = f"✅ KET QUA: {ev['name']}\n━" * 15 + f"\n📊 {result}\n\n{get_econ_text()}"
                        messages.append(msg)
    
    save_log(log)
    return messages

# ============================================
# GDELT
# ============================================
def get_geopolitical_news():
    if not check_gdelt():
        return []
    try:
        q = "war OR conflict OR strike OR missile OR ukraine OR russia OR israel OR iran OR nato OR putin OR zelensky OR netanyahu OR north korea OR trade war OR tariff"
        url = f"https://api.gdeltproject.org/api/v2/doc/doc?query={requests.utils.quote(q)}&mode=artlist&format=json&maxrecords=5&sort=datedesc"
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return []
        articles = r.json().get('articles', [])
        log = load_log()
        news_list = []
        for a in articles[:5]:
            title = a.get('title', '')
            url_news = a.get('url', '')
            source = a.get('domain', 'Unknown')
            tone = float(a.get('tone', '0'))
            if url_news in log['news_sent']:
                continue
            log['news_sent'].append(url_news)
            if tone < -5: impact = "🔴🔴🔴 CUC KY TIEU CUC"
            elif tone < -2: impact = "🔴🔴 TIEU CUC"
            elif tone > 5: impact = "🟢🟢🟢 CUC KY TICH CUC"
            elif tone > 2: impact = "🟢🟢 TICH CUC"
            else: impact = "⚪ TRUNG TINH"
            if tone < -3:
                g, cr, kn = "🟢 TANG", "🔴 GIAM", "⚠️ SHORT"
            elif tone > 3:
                g, cr, kn = "🔴 GIAM", "🟢 TANG", "✅ LONG"
            else:
                g, cr, kn = "⚪ IT BIEN DONG", "⚪ IT BIEN DONG", "⏳ CHO"
            news_list.append({'title': title, 'source': source, 'impact': impact, 'score': tone, 'gold': g, 'crypto': cr, 'khuyen_nghi': kn})
        log['news_sent'] = log['news_sent'][-50:]
        save_log(log)
        return news_list
    except:
        return []

def format_news(news_list):
    msgs = []
    for n in news_list:
        m = f"📰 TIN TUC {n['impact']}\n━" * 20 + f"\n{n['title']}\n\n📡 {n['source']}\n⚡ Score: {n['score']:.0f}\n\n🥇 Vang: {n['gold']}\n₿ Crypto: {n['crypto']}\n💡 {n['khuyen_nghi']}\n🕐 {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}"
        msgs.append(m)
    return msgs

# ============================================
# FEAR & GREED
# ============================================
_fg_last = 0
def get_fear_greed():
    global _fg_last
    now = time.time()
    if now - _fg_last < 3600:
        return None
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        d = r.json()['data'][0]
        v = int(d['value'])
        c = d['value_classification']
        icon = "😱" if v <= 25 else "😟" if v <= 40 else "😐" if v <= 60 else "😊" if v <= 75 else "🤤"
        _fg_last = now
        return f"{icon} Fear & Greed: {v}/100 - {c}"
    except:
        return None

# ============================================
# MAIN
# ============================================
print("=" * 40)
print("📰 BOT TIN TUC")
print(f"FRED: {check_fred()} | GDELT: {check_gdelt()}")
print("=" * 40)

last_lich = 0
lan = 0

while True:
    try:
        lan += 1
        now = time.time()
        count = 0
        
        # Khoi dong 1 lan duy nhat
        global da_khoi_dong
        if not da_khoi_dong:
            da_khoi_dong = True
            msg = f"📰 Bot tin tuc da khoi dong!\n━" * 15 + f"\n📡 FRED: {'✅ Online' if check_fred() else '⏳ Offline'}\n📡 GDELT: {'✅ Online' if check_gdelt() else '⏳ Offline'}\n\n✅ Dang theo doi..."
            gui_telegram(msg)
        
        # Tin dia chinh tri
        for msg in format_news(get_geopolitical_news()):
            gui_telegram(msg)
            count += 1
            time.sleep(1)
        
        # Lich kinh te
        if now - last_lich >= CHU_KY_LICH:
            last_lich = now
            for msg in check_lich_kinh_te():
                gui_telegram(msg)
                count += 1
        
        # Fear & Greed
        fg = get_fear_greed()
        if fg:
            gui_telegram(fg)
            count += 1
        
        if count == 0:
            print(f"#{lan} | OK")
        else:
            print(f"#{lan} | Gui {count} tin")
        
        time.sleep(CHU_KY_TIN_TUC)
        
    except KeyboardInterrupt:
        print("👋 Dung")
        break
    except Exception as e:
        print(f"Loi: {e}")
        time.sleep(30)