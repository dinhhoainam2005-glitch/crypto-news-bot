"""
BOT TIN TUC - LICH KINH TE + DIA CHINH TRI + MARKET
- FRED API (tu dong bat khi len Render Singapore)
- GDELT API (tu dong bat khi len Render Singapore)
- Lich kinh te: FOMC, CPI, NFP, GDP, PPI
- Du bao truoc 3 ngay + gui ket qua THAT sau su kien
- 100% du lieu tu API, khong thu cong, khong doan
"""
import requests
import time
import json
import os
from datetime import datetime, timedelta

# ============================================
# THAY BANG THONG TIN CUA BAN
# ============================================
import os

TOKEN = os.getenv("TELEGRAM_TOKEN", "8893995280:AAF9XwWAm9QgPkwmDrhZdY6UQ4zfySooWpk")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "518284897")
FRED_API_KEY = os.getenv("FRED_API_KEY", "ff3e122af2b2c0a433606476fc6dc5fb")

# ============================================
# CAU HINH
# ============================================
CHU_KY_TIN_TUC = 600   # 10 phut kiem tra tin dia chinh tri
CHU_KY_LICH = 3600     # 1 gio kiem tra lich kinh te
DATA_FILE = "data/tin_tuc_log.json"

# Trang thai API
fred_online = None
gdelt_online = None

# ============================================
# GHI LOG (tranh gui trung)
# ============================================
def load_log():
    os.makedirs("data", exist_ok=True)
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"events_sent": {}, "news_sent": [], "fg_last": 0}

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
# KIEM TRA API ONLINE
# ============================================
def check_fred():
    global fred_online
    if fred_online is not None:
        return fred_online
    try:
        r = requests.get(
            f"https://api.stlouisfed.org/fred/series/observations?series_id=DFF&api_key={FRED_API_KEY}&file_type=json&limit=1",
            timeout=5
        )
        fred_online = r.status_code == 200
    except:
        fred_online = False
    
    if fred_online:
        print("✅ FRED API: Online")
    else:
        print("⚠️ FRED API: Offline - se hoat dong khi len Render")
    return fred_online

def check_gdelt():
    global gdelt_online
    if gdelt_online is not None:
        return gdelt_online
    try:
        r = requests.get(
            "https://api.gdeltproject.org/api/v2/doc/doc?query=war&mode=artlist&format=json&maxrecords=1",
            timeout=5
        )
        gdelt_online = r.status_code == 200
    except:
        gdelt_online = False
    
    if gdelt_online:
        print("✅ GDELT API: Online")
    else:
        print("⚠️ GDELT API: Offline - se hoat dong khi len Render")
    return gdelt_online

# ============================================
# 1. FRED API - DU LIEU KINH TE THUC
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
    """Lay du lieu kinh te hien tai"""
    if not check_fred():
        return "📡 FRED offline - se hoat dong khi len Render Singapore"
    
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
    
    return "\n".join(lines) if len(lines) > 2 else "📡 Dang cho du lieu FRED..."

# ============================================
# 2. LICH KINH TE
# ============================================
KINH_TE_EVENTS = [
    {
        'id': 'nfp_2026-06-05',
        'name': '💼 Non-Farm Payrolls (T5)',
        'date': '2026-06-05', 'time': '19:30',
        'impact': '🔴 HIGH',
        'desc': 'Bao cao viec lam phi nong nghiep My.',
        'fred_series': 'UNRATE',
        'result_text': 'Ty le that nghiep thuc te: {value}% (ky truoc: {prev}%)'
    },
    {
        'id': 'cpi_2026-06-11',
        'name': '📊 CPI Report (T5)',
        'date': '2026-06-11', 'time': '19:30',
        'impact': '🔴 HIGH',
        'desc': 'Chi so gia tieu dung - thước do lam phat.',
        'fred_series': 'CPIAUCSL',
        'result_text': 'CPI thuc te: {value} (ky truoc: {prev})'
    },
    {
        'id': 'ppi_2026-06-12',
        'name': '🏭 PPI Report (T5)',
        'date': '2026-06-12', 'time': '19:30',
        'impact': '🟡 MEDIUM',
        'desc': 'Chi so gia san xuat.',
        'fred_series': 'PPIACO',
        'result_text': 'PPI thuc te: {value} (ky truoc: {prev})'
    },
    {
        'id': 'fomc_2026-06-18',
        'name': '🏦 FOMC Rate Decision (T6)',
        'date': '2026-06-18', 'time': '01:00',
        'impact': '🔴 HIGH',
        'desc': 'Quyet dinh lai suat Fed - SU KIEN QUAN TRONG NHAT.',
        'fred_series': 'DFF',
        'result_text': 'Lai suat Fed thuc te: {value}% (ky truoc: {prev}%) - Fed {action}'
    },
    {
        'id': 'gdp_2026-06-25',
        'name': '📊 GDP Q2 2026 (Final)',
        'date': '2026-06-25', 'time': '19:30',
        'impact': '🔴 HIGH',
        'desc': 'Tang truong kinh te My.',
        'fred_series': 'GDP',
        'result_text': 'GDP thuc te: ${value:,.0f}B (ky truoc: ${prev:,.0f}B)'
    },
    {
        'id': 'fomc_2026-07-30',
        'name': '🏦 FOMC Rate Decision (T7)',
        'date': '2026-07-30', 'time': '01:00',
        'impact': '🔴 HIGH',
        'desc': 'Quyet dinh lai suat giua nam 2026.',
        'fred_series': 'DFF',
        'result_text': 'Lai suat Fed thuc te: {value}% (ky truoc: {prev}%) - Fed {action}'
    },
]

def check_lich_kinh_te():
    """Kiem tra lich kinh te: du bao truoc 3 ngay, ket qua sau su kien"""
    log = load_log()
    now = datetime.now()
    today = now.date()
    messages = []
    
    for ev in KINH_TE_EVENTS:
        ev_date = datetime.strptime(ev['date'], '%Y-%m-%d').date()
        ev_dt = datetime.strptime(ev['date'] + ' ' + ev['time'], '%Y-%m-%d %H:%M')
        days_until = (ev_date - today).days
        hours_since = (now - ev_dt).total_seconds() / 3600 if ev_dt < now else -1
        
        # ===== TRUOC SU KIEN: Du bao (D-3 den D-0) =====
        if 0 <= days_until <= 3:
            key = f"pre_{ev['id']}"
            last = log['events_sent'].get(key, 0)
            
            # Gui moi 12 gio
            if time.time() - last >= 43200:
                log['events_sent'][key] = time.time()
                
                if days_until == 0:
                    countdown = f"⚠️ HOM NAY luc {ev['time']} (UTC+7)"
                elif days_until == 1:
                    countdown = f"📅 NGAY MAI luc {ev['time']} (UTC+7)"
                else:
                    countdown = f"📅 Con {days_until} ngay - {ev['date']} luc {ev['time']} (UTC+7)"
                
                msg = f"📅 {ev['name']}\n━" * 15 + f"\n"
                msg += f"⏰ {countdown}\n"
                msg += f"⚡ {ev['impact']}\n"
                msg += f"📝 {ev['desc']}\n\n"
                msg += get_econ_text()
                messages.append(msg)
        
        # ===== SAU SU KIEN: Ket qua THAT (1h-72h sau) =====
        elif days_until < 0 and 1 <= hours_since <= 72:
            key = f"post_{ev['id']}"
            
            if key not in log['events_sent']:
                # Lay ket qua THAT tu FRED
                if check_fred():
                    values = get_fred_value(ev['fred_series'])
                    if values and len(values) >= 2:
                        curr_val = values[0]['value']
                        prev_val = values[1]['value']
                        
                        # Tinh action cho FOMC
                        action = ""
                        if 'fomc' in ev['id']:
                            if curr_val > prev_val:
                                action = "TANG lai suat 🦅"
                            elif curr_val < prev_val:
                                action = "GIAM lai suat 🕊️"
                            else:
                                action = "GIU NGUYEN lai suat"
                        
                        result = ev['result_text'].format(
                            value=curr_val, prev=prev_val, action=action
                        )
                        
                        log['events_sent'][key] = time.time()
                        
                        msg = f"✅ KET QUA: {ev['name']}\n━" * 15 + f"\n"
                        msg += f"📊 {result}\n\n"
                        msg += get_econ_text()
                        messages.append(msg)
                    else:
                        # FRED chua co du lieu, thu lai sau
                        pass
                else:
                    # FRED offline, bao chờ Render
                    if key not in log['events_sent']:
                        log['events_sent'][key] = time.time()
                        messages.append(
                            f"✅ {ev['name']} da dien ra!\n"
                            f"📡 FRED offline - ket qua se co khi len Render Singapore"
                        )
    
    save_log(log)
    return messages

# ============================================
# 3. GDELT - TIN DIA CHINH TRI
# ============================================
def get_geopolitical_news():
    """Lay tin dia chinh tri tu GDELT"""
    if not check_gdelt():
        return []
    
    try:
        # Query cac tu khoa chinh tri
        query = "war OR conflict OR strike OR missile OR tension OR ceasefire OR peace OR nato OR putin OR zelensky OR netanyahu OR iran OR israel OR ukraine OR russia OR north korea OR trade war OR tariff"
        
        url = f"https://api.gdeltproject.org/api/v2/doc/doc?query={requests.utils.quote(query)}&mode=artlist&format=json&maxrecords=5&sort=datedesc"
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
            
            # Tranh gui trung
            if url_news in log['news_sent']:
                continue
            
            log['news_sent'].append(url_news)
            
            # Phan tich tac dong
            if tone < -5:
                impact = "🔴🔴🔴 CUC KY TIEU CUC"
                score = tone
            elif tone < -2:
                impact = "🔴🔴 TIEU CUC"
                score = tone
            elif tone > 5:
                impact = "🟢🟢🟢 CUC KY TICH CUC"
                score = tone
            elif tone > 2:
                impact = "🟢🟢 TICH CUC"
                score = tone
            else:
                impact = "⚪ TRUNG TINH"
                score = tone
            
            # Du bao tac dong thi truong
            if tone < -3:
                gold_impact = "🟢 TANG (tru an)"
                crypto_impact = "🔴 GIAM (risk-off)"
                usd_impact = "🟢 TANG (tru an)"
                khuyen_nghi = "⚠️ UU TIEN SHORT"
            elif tone > 3:
                gold_impact = "🔴 GIAM (risk-on)"
                crypto_impact = "🟢 TANG (risk-on)"
                usd_impact = "🔴 GIAM (risk-on)"
                khuyen_nghi = "✅ UU TIEN LONG"
            else:
                gold_impact = "⚪ IT BIEN DONG"
                crypto_impact = "⚪ IT BIEN DONG"
                usd_impact = "⚪ IT BIEN DONG"
                khuyen_nghi = "⏳ CHO DOI"
            
            news_list.append({
                'title': title,
                'url': url_news,
                'source': source,
                'impact': impact,
                'score': score,
                'gold': gold_impact,
                'crypto': crypto_impact,
                'usd': usd_impact,
                'khuyen_nghi': khuyen_nghi
            })
        
        # Giữ 50 tin gan nhat
        log['news_sent'] = log['news_sent'][-50:]
        save_log(log)
        
        return news_list
    
    except Exception as e:
        print(f"⚠️ GDELT error: {e}")
        return []

def format_news(news_list):
    """Format tin tuc thanh Telegram message"""
    messages = []
    
    for n in news_list:
        msg = f"📰 TIN TUC THI TRUONG {n['impact']}\n━" * 20 + f"\n"
        msg += f"{n['title']}\n\n"
        msg += f"📡 Nguon: {n['source']}\n"
        msg += f"⚡ Tac dong: {n['impact']} (Score: {n['score']:.0f})\n\n"
        msg += f"🏦 Du bao:\n"
        msg += f"🥇 Vang: {n['gold']}\n"
        msg += f"₿ Crypto: {n['crypto']}\n"
        msg += f"💵 USD: {n['usd']}\n\n"
        msg += f"💡 Khuyen nghi: {n['khuyen_nghi']}\n"
        msg += f"🕐 {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}"
        
        messages.append(msg)
    
    return messages

# ============================================
# 4. FEAR & GREED
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
        
        return f"{icon} Fear & Greed Index: {v}/100 - {c}\n🕐 {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}"
    except:
        return None

# ============================================
# MAIN
# ============================================
print("=" * 60)
print("📰 BOT TIN TUC - LICH KINH TE + DIA CHINH TRI")
print("=" * 60)
print(f"📡 FRED API: {'✅ Online' if check_fred() else '⏳ Se hoat dong khi len Render'}")
print(f"📡 GDELT API: {'✅ Online' if check_gdelt() else '⏳ Se hoat dong khi len Render'}")
print(f"⏱️ Tin tuc: {CHU_KY_TIN_TUC}s | Lich kinh te: {CHU_KY_LICH}s")
print("=" * 60)

# Khoi dong
startup = "📰 Bot tin tuc da khoi dong!\n━" * 15 + f"\n"
startup += f"📡 FRED: {'✅ Online' if check_fred() else '⏳ Cho Render'}\n"
startup += f"📡 GDELT: {'✅ Online' if check_gdelt() else '⏳ Cho Render'}\n"
startup += f"\n✅ Dang theo doi su kien..."
# Chi gui khoi dong 1 lan
if not os.path.exists("data/started.txt"):
    os.makedirs("data", exist_ok=True)
    with open("data/started.txt", "w") as f:
        f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    gui_telegram(startup)

last_lich_check = 0
lan = 0

while True:
    try:
        lan += 1
        now = time.time()
        now_str = datetime.now().strftime("%H:%M:%S")
        count = 0
        
        # ===== TIN DIA CHINH TRI (moi 10 phut) =====
        news = get_geopolitical_news()
        for msg in format_news(news):
            gui_telegram(msg)
            count += 1
            print(f"   ✅ Tin dia chinh tri")
            time.sleep(1)  # Delay giua cac tin
        
        # ===== LICH KINH TE (moi 1 gio) =====
        if now - last_lich_check >= CHU_KY_LICH:
            last_lich_check = now
            for msg in check_lich_kinh_te():
                gui_telegram(msg)
                count += 1
                print(f"   ✅ Lich kinh te")
        
        # ===== FEAR & GREED =====
        fg = get_fear_greed()
        if fg:
            gui_telegram(fg)
            count += 1
            print(f"   ✅ Fear & Greed")
        
        if count == 0:
            print(f"#{lan} | {now_str} | Khong co gi moi")
        else:
            print(f"#{lan} | {now_str} | Da gui {count} tin")
        
        time.sleep(CHU_KY_TIN_TUC)
        
    except KeyboardInterrupt:
        print("\n👋 Bot da dung!")
        gui_telegram("🛑 Bot tin tuc da dung")
        break
    except Exception as e:
        print(f"❌ Loi: {e}")
        time.sleep(30)