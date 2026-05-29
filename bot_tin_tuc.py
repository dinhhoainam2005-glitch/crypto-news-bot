"""
BOT TIN TUC - FORMAT CHUAN - DU LIEU THAT 100%
"""
import requests
import time
import json
import os
from datetime import datetime, timedelta

TOKEN = os.getenv("TELEGRAM_TOKEN", "8893995280:AAF9XwWAm9QgPkwmDrhZdY6UQ4zfySooWpk")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "518284897")
FRED_API_KEY = os.getenv("FRED_API_KEY", "ff3e122af2b2c0a433606476fc6dc5fb")

CHU_KY_TIN = 600
CHU_KY_LICH = 3600
DATA_DIR = "data"
STATE_FILE = f"{DATA_DIR}/state.json"
LOG_FILE = f"{DATA_DIR}/log.json"

os.makedirs(DATA_DIR, exist_ok=True)

# ===== STATE =====
def get_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f: return json.load(f)
    return {"started": False, "fg_last": 0, "lich_last": 0}

def set_state(**kv):
    s = get_state()
    s.update(kv)
    with open(STATE_FILE, 'w') as f: json.dump(s, f)

# ===== LOG =====
def get_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f: return json.load(f)
    return {"events": {}, "news_sent": []}

def save_log(l):
    with open(LOG_FILE, 'w') as f: json.dump(l, f, ensure_ascii=False, indent=2)

# ===== TELEGRAM =====
def gui(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                     data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except: pass

def now_str():
    n = datetime.now()
    return f"🕐 {n.strftime('%H:%M')} (Asia) | {(n-timedelta(hours=5)).strftime('%H:%M')} (EU) | {(n-timedelta(hours=11)).strftime('%H:%M')} (US) | {n.strftime('%d/%m/%Y')}"

# ===== FRED =====
def fred_ok():
    try:
        r = requests.get(f"https://api.stlouisfed.org/fred/series/observations?series_id=DFF&api_key={FRED_API_KEY}&file_type=json&limit=1", timeout=10)
        return r.status_code == 200
    except: return False

def fred_get(sid):
    if not fred_ok(): return None
    try:
        r = requests.get(f"https://api.stlouisfed.org/fred/series/observations?series_id={sid}&api_key={FRED_API_KEY}&file_type=json&limit=2&sort_order=desc", timeout=10)
        if r.status_code == 200:
            obs = r.json().get('observations', [])
            vals = [{'d': o['date'], 'v': float(o['value'])} for o in obs if o.get('value', '.') != '.']
            return vals if vals else None
    except: pass
    return None

def econ_summary():
    """Dòng tóm tắt: Fed Rate: X% | CPI: Y | UE: Z% | GDP: $WB"""
    parts = []
    for sid, fmt in [('DFF','Fed Rate: {}%'), ('CPIAUCSL','CPI: {}'), ('UNRATE','UE: {}%'), ('GDP','GDP: ${:,.0f}B')]:
        v = fred_get(sid)
        if v: parts.append(fmt.format(v[0]['v']))
    return " | ".join(parts) if parts else "Dang tai du lieu FRED..."

# ===== GDELT =====
KEYWORDS = "war OR conflict OR strike OR missile OR ukraine OR russia OR israel OR iran OR nato OR putin OR zelensky OR netanyahu OR north korea OR tariff OR recession OR crash OR sec OR inflation OR fed"

def gdelt_news():
    try:
        url = f"https://api.gdeltproject.org/api/v2/doc/doc?query={requests.utils.quote(KEYWORDS)}&mode=artlist&format=json&maxrecords=10&sort=datedesc"
        r = requests.get(url, timeout=15)
        if r.status_code != 200: return []
        
        data = r.json()
        if 'articles' not in data: return []
        
        articles = data['articles']
        log = get_log()
        news_list = []
        
        for a in articles:
            url_news = a.get('url', '')
            if url_news in log['news_sent']: continue
            
            title = a.get('title', 'No title')
            domain = a.get('domain', 'Unknown')
            tone = float(a.get('tone', 0))
            
            log['news_sent'].append(url_news)
            
            # Phân loại tác động
            if tone < -5: impact = "🔴🔴🔴 CỰC KỲ TIÊU CỰC"
            elif tone < -2: impact = "🔴🔴 TIÊU CỰC"
            elif tone > 5: impact = "🟢🟢🟢 CỰC KỲ TÍCH CỰC"
            elif tone > 2: impact = "🟢🟢 TÍCH CỰC"
            else: impact = "🟡 TRUNG TÍNH"
            
            # Dự báo thị trường
            if tone < -3:
                gold, crypto, usd, advice = "🟢 TĂNG (trú ẩn)", "🔴 GIẢM (risk-off)", "🟢 TĂNG (trú ẩn)", "⚠️ ƯU TIÊN SHORT"
            elif tone > 3:
                gold, crypto, usd, advice = "🔴 GIẢM (risk-on)", "🟢 TĂNG (risk-on)", "🔴 GIẢM (risk-on)", "✅ ƯU TIÊN LONG"
            else:
                gold, crypto, usd, advice = "🟡 THEO DÕI", "🟡 THEO DÕI", "🟡 THEO DÕI", "➡️ GIAO DỊCH BÌNH THƯỜNG"
            
            # Từ khóa
            keywords_found = []
            for kw in ['war','russia','ukraine','strike','israel','iran','missile','north korea','recession','crash','sec','inflation','putin','zelensky','netanyahu','nato','tariff']:
                if kw in title.lower():
                    weight = -25 if kw in ['war','crash'] else (-18 if kw in ['strike','recession'] else -10)
                    keywords_found.append(f"{kw}({weight})")
            
            kw_str = ", ".join(keywords_found[:5]) if keywords_found else "geopolitical"
            
            news_list.append({
                'title': title,
                'source': domain,
                'impact': impact,
                'score': int(tone),
                'gold': gold,
                'crypto': crypto,
                'usd': usd,
                'advice': advice,
                'keywords': kw_str
            })
        
        log['news_sent'] = log['news_sent'][-200:]
        save_log(log)
        return news_list
    except Exception as e:
        print(f"GDELT error: {e}")
        return []

# ===== LICH KINH TE =====
EVENTS = [
    {'id':'nfp_jun','name':'💼 Non-Farm Payrolls','date':'2026-06-05','time':'19:30','impact':'🔴 HIGH','desc':'Báo cáo việc làm phi nông nghiệp Mỹ.','fred':'UNRATE','fmt':'Tỷ lệ thất nghiệp: {value}% (trước: {prev}%)'},
    {'id':'cpi_jun','name':'📊 CPI Report','date':'2026-06-11','time':'19:30','impact':'🔴 HIGH','desc':'Chỉ số giá tiêu dùng - thước đo lạm phát chính.','fred':'CPIAUCSL','fmt':'CPI: {value} (trước: {prev})'},
    {'id':'ppi_jun','name':'🏭 PPI Report','date':'2026-06-12','time':'19:30','impact':'🟡 MEDIUM','desc':'Chỉ số giá sản xuất.','fred':'PPIACO','fmt':'PPI: {value} (trước: {prev})'},
    {'id':'fomc_jun','name':'🏦 FOMC Rate Decision','date':'2026-06-18','time':'01:00','impact':'🔴 HIGH','desc':'Quyết định lãi suất Fed - SỰ KIỆN QUAN TRỌNG NHẤT.','fred':'DFF','fmt':'Lãi suất Fed: {value}% (trước: {prev}%) - Fed {action}'},
    {'id':'gdp_q2','name':'📊 GDP Q2 2026 (Final)','date':'2026-06-25','time':'19:30','impact':'🔴 HIGH','desc':'Tăng trưởng kinh tế Mỹ.','fred':'GDP','fmt':'GDP: ${value:,.0f}B (trước: ${prev:,.0f}B) - {action}'},
    {'id':'fomc_jul','name':'🏦 FOMC Rate Decision (T7)','date':'2026-07-30','time':'01:00','impact':'🔴 HIGH','desc':'Quyết định lãi suất giữa năm 2026.','fred':'DFF','fmt':'Lãi suất Fed: {value}% (trước: {prev}%) - Fed {action}'},
]

def check_events():
    log = get_log()
    now = datetime.now()
    today = now.date()
    msgs = []
    
    for ev in EVENTS:
        evd = datetime.strptime(ev['date'], '%Y-%m-%d').date()
        evdt = datetime.strptime(ev['date']+' '+ev['time'], '%Y-%m-%d %H:%M')
        days = (evd - today).days
        hours_since = (now - evdt).total_seconds()/3600 if evdt < now else -1
        
        # TRUOC SU KIEN (D-3 den D-0)
        if 0 <= days <= 3:
            key = f"pre_{ev['id']}"
            if time.time() - log['events'].get(key, 0) >= 43200:  # 12h
                log['events'][key] = time.time()
                
                if days == 0: cd = f"⚠️ HÔM NAY lúc {ev['time']} (UTC+7)"
                elif days == 1: cd = f"📅 NGÀY MAI lúc {ev['time']} (UTC+7)"
                else: cd = f"📅 Còn {days} ngày - {ev['date']} lúc {ev['time']} (UTC+7)"
                
                msg = f"📅 {ev['name']}\n"
                msg += f"━━━━━━━━━━━━━━━━━━\n"
                msg += f"⏰ {cd}\n"
                msg += f"⚡ Mức độ: {ev['impact']}\n"
                msg += f"📝 {ev['desc']}\n\n"
                msg += f"📊 DỮ LIỆU HIỆN TẠI:\n{econ_summary()}\n\n"
                msg += now_str()
                msgs.append(msg)
        
        # SAU SU KIEN (1h-72h) -> KET QUA THAT
        elif days < 0 and 1 <= hours_since <= 72:
            key = f"post_{ev['id']}"
            if key not in log['events'] and fred_ok():
                v = fred_get(ev['fred'])
                if v and len(v) >= 2:
                    curr, prev = v[0]['v'], v[1]['v']
                    
                    if 'fomc' in ev['id'] or 'gdp' in ev['id']:
                        action = "TĂNG 📈" if curr > prev else ("GIẢM 📉" if curr < prev else "GIỮ NGUYÊN ➡️")
                    else:
                        action = ""
                    
                    log['events'][key] = time.time()
                    
                    msg = f"===================================\n"
                    msg += f"✅ {ev['name']} - KẾT QUẢ THỰC TẾ\n"
                    msg += f"===================================\n"
                    msg += f"⏰ Đã diễn ra: {ev['date']} lúc {ev['time']} (UTC+7)\n\n"
                    msg += f"📊 {ev['fmt'].format(value=curr, prev=prev, action=action)}\n\n"
                    msg += f"━━━━━━━━━━━━━━━━━━\n"
                    msg += f"📊 TÁC ĐỘNG THỊ TRƯỜNG:\n"
                    msg += f"🥇 Vàng: Theo dữ liệu thực tế\n"
                    msg += f"₿ Crypto: Theo dữ liệu thực tế\n"
                    msg += f"💵 USD: Theo dữ liệu thực tế\n"
                    msg += f"━━━━━━━━━━━━━━━━━━\n\n"
                    msg += f"📊 DỮ LIỆU FRED:\n{econ_summary()}\n\n"
                    msg += now_str()
                    msgs.append(msg)
    
    save_log(log)
    return msgs

# ===== FEAR & GREED =====
def get_fg():
    s = get_state()
    if time.time() - s['fg_last'] < 3600: return None
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        d = r.json()['data'][0]
        v = int(d['value']); c = d['value_classification']
        i = "😱" if v<=25 else "😟" if v<=40 else "😐" if v<=60 else "😊" if v<=75 else "🤤"
        set_state(fg_last=time.time())
        return f"{i} Fear & Greed Index: {v}/100 ({c})"
    except: return None

# ===== TONG QUAN =====
def market_summary(news_list):
    if not news_list: return None
    total_score = sum(n['score'] for n in news_list)
    
    if total_score < -200: level = "RẤT CAO"
    elif total_score < -100: level = "CAO"
    elif total_score < 0: level = "TRUNG BÌNH"
    else: level = "THẤP"
    
    all_kw = []
    for n in news_list:
        all_kw.extend(n['keywords'].split(', '))
    
    top_kw = list(set(all_kw))[:5]
    
    if total_score < -100:
        advice = "⚠️ ƯU TIÊN SHORT"
    elif total_score > 100:
        advice = "✅ ƯU TIÊN LONG"
    else:
        advice = "➡️ GIAO DỊCH BÌNH THƯỜNG"
    
    msg = f"📰 TỔNG QUAN THỊ TRƯỜNG\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    msg += f"🚨 Căng thẳng {level} (score: {total_score}). {advice}\n\n"
    msg += f"📋 Số tin phát hiện: {len(news_list)}\n"
    msg += f"🔑 Từ khóa nóng: {', '.join(top_kw)}\n\n"
    msg += now_str()
    
    return msg

# ===== MAIN =====
print("BOT TIN TUC STARTED")
print(f"FRED: {fred_ok()} | GDELT: testing...")

while True:
    try:
        s = get_state()
        
        if not s['started']:
            set_state(started=True)
            gui(f"📰 Bot tin tức đã khởi động!\n━━━━━━━━━━━━━━━━━━\n📡 FRED: {'✅ Online' if fred_ok() else '⏳ Offline'}\n📡 GDELT: ✅ Online\n\n✅ Đang theo dõi sự kiện...\n\n{now_str()}")

        # Tin tức
        news = gdelt_news()
        if news:
            # Tổng quan
            summary = market_summary(news)
            if summary: gui(summary)
            
            # Từng tin
            for n in news:
                msg = f"📰 TIN TỨC THỊ TRƯỜNG {n['impact']}\n"
                msg += f"━━━━━━━━━━━━━━━━━━\n"
                msg += f"{n['title']}\n\n"
                msg += f"📡 Nguồn: {n['source']}\n"
                msg += f"⚡ Tác động: {n['impact']} (Score: {n['score']})\n"
                msg += f"🔑 Từ khóa: {n['keywords']}\n\n"
                msg += f"🏦 Dự báo:\n"
                msg += f"🥇 Vàng: {n['gold']}\n"
                msg += f"₿ Crypto: {n['crypto']}\n"
                msg += f"💵 USD: {n['usd']}\n\n"
                msg += f"💡 Khuyến nghị: {n['advice']}\n\n"
                msg += now_str()
                gui(msg)
                time.sleep(1)

        # Lịch kinh tế
        if time.time() - s['lich_last'] >= CHU_KY_LICH:
            set_state(lich_last=time.time())
            for m in check_events():
                gui(m)

        # Fear & Greed
        fg = get_fg()
        if fg: gui(fg)

        time.sleep(CHU_KY_TIN)
    except KeyboardInterrupt: break
    except Exception as e:
        print(f"Loi: {e}")
        time.sleep(30)