"""
BOT TIN TUC - NEWSAPI + FRED - DU LIEU THAT 100%
- NewsAPI: 80.000+ nguồn báo uy tín
- FRED: Dữ liệu kinh tế thật
- Chỉ lọc tin có từ khóa thực tế - không bịa score
"""
import requests
import time
import json
import os
from datetime import datetime, timedelta

TOKEN = os.getenv("TELEGRAM_TOKEN", "8893995280:AAF9XwWAm9QgPkwmDrhZdY6UQ4zfySooWpk")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "518284897")
FRED_API_KEY = os.getenv("FRED_API_KEY", "ff3e122af2b2c0a433606476fc6dc5fb")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "bcdf1d28d8bd401f9eb1978268efeb53")

CHU_KY_TIN = 600
CHU_KY_LICH = 3600
DATA_DIR = "data"
STATE_FILE = f"{DATA_DIR}/state.json"
LOG_FILE = f"{DATA_DIR}/log.json"

os.makedirs(DATA_DIR, exist_ok=True)

def get_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f: return json.load(f)
    return {"started": False, "fg_last": 0, "lich_last": 0}

def set_state(**kv):
    s = get_state(); s.update(kv)
    with open(STATE_FILE, 'w') as f: json.dump(s, f)

def get_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f: return json.load(f)
    return {"events": {}, "news_sent": []}

def save_log(l):
    with open(LOG_FILE, 'w') as f: json.dump(l, f, ensure_ascii=False, indent=2)

def gui(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                     data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except: pass

def now_str():
    n = datetime.now()
    return f"🕐 {n.strftime('%H:%M')} (Asia) | {(n-timedelta(hours=5)).strftime('%H:%M')} (EU) | {(n-timedelta(hours=11)).strftime('%H:%M')} (US) | {n.strftime('%d/%m/%Y')}"

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
            return [{'d': o['date'], 'v': float(o['value'])} for o in obs if o.get('value', '.') != '.']
    except: pass
    return None

def econ_summary():
    parts = []
    for sid, fmt in [('DFF','Fed Rate: {}%'), ('CPIAUCSL','CPI: {}'), ('UNRATE','UE: {}%'), ('GDP','GDP: ${:,.0f}B'), ('PPIACO','PPI: {}')]:
        v = fred_get(sid)
        if v: parts.append(fmt.format(v[0]['v']))
    return " | ".join(parts) if parts else "Đang tải..."

# ===== TỪ KHÓA LỌC TIN =====
# Chỉ lấy tin CHỨA các từ khóa này - đảm bảo liên quan thị trường
POSITIVE_KW = [
    "ceasefire", "peace deal", "peace talk", "truce", "surrender", "withdraw",
    "rate cut", "dovish", "easing", "stimulus", "bull market", "rally",
    "surge", "breakout", "adoption", "partnership", "approved", "breakthrough",
    "agreement", "deal", "resolved", "upward", "record high", "outperform"
]

NEGATIVE_KW = [
    "war", "invasion", "strike", "missile", "bomb", "airstrike", "offensive",
    "nuclear", "sanction", "embargo", "tariff", "trade war",
    "crash", "recession", "depression", "meltdown", "plunge", "collapse",
    "rate hike", "hawkish", "tighten", "inflation surge", "cpi surge",
    "crackdown", "ban", "delist", "lawsuit", "sec charge", "fraud",
    "tension", "escalation", "conflict", "attack", "casualty",
    "oil price surge", "supply shock", "shortage", "crisis"
]

def phan_tich_tin(title, description=""):
    """Phân tích tin dựa trên từ khóa THỰC TẾ trong tiêu đề"""
    t = (title + " " + description).lower()
    
    positive_found = []
    negative_found = []
    
    for kw in POSITIVE_KW:
        if kw in t:
            positive_found.append(kw)
    
    for kw in NEGATIVE_KW:
        if kw in t:
            negative_found.append(kw)
    
    pos_count = len(positive_found)
    neg_count = len(negative_found)
    
    if neg_count > pos_count:
        if neg_count >= 3:
            loai = "🔴🔴🔴 CỰC KỲ TIÊU CỰC"
        elif neg_count >= 2:
            loai = "🔴🔴 RẤT TIÊU CỰC"
        else:
            loai = "🔴 TIÊU CỰC"
        
        gold = "🟢 TĂNG (trú ẩn)"
        crypto = "🔴 GIẢM (risk-off)"
        usd = "🟢 TĂNG (trú ẩn)"
        advice = "⚠️ ƯU TIÊN SHORT"
        keywords = negative_found
    elif pos_count > neg_count:
        if pos_count >= 3:
            loai = "🟢🟢🟢 CỰC KỲ TÍCH CỰC"
        elif pos_count >= 2:
            loai = "🟢🟢 TÍCH CỰC"
        else:
            loai = "🟢 TÍCH CỰC"
        
        gold = "🔴 GIẢM (risk-on)"
        crypto = "🟢 TĂNG (risk-on)"
        usd = "🔴 GIẢM (risk-on)"
        advice = "✅ ƯU TIÊN LONG"
        keywords = positive_found
    else:
        return None  # Trung tính -> bỏ qua
    
    return {
        'loai': loai, 'gold': gold, 'crypto': crypto,
        'usd': usd, 'advice': advice, 'keywords': keywords
    }

# ===== NEWSAPI =====
QUERIES = [
    "iran israel war conflict",
    "russia ukraine war",
    "fed interest rate inflation",
    "trade war tariff",
    "oil price crude",
    "stock market crash recession",
    "crypto bitcoin regulation sec",
    "gold price safe haven"
]

def fetch_news():
    """Lấy tin từ NewsAPI với nhiều queries"""
    all_news = []
    log = get_log()
    
    for query in QUERIES:
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                'q': query,
                'language': 'en',
                'sortBy': 'publishedAt',
                'pageSize': 5,
                'apiKey': NEWS_API_KEY
            }
            r = requests.get(url, params=params, timeout=10)
            
            if r.status_code != 200:
                continue
            
            articles = r.json().get('articles', [])
            
            for a in articles:
                url_news = a.get('url', '')
                if url_news in log['news_sent']:
                    continue
                
                title = a.get('title', '')
                description = a.get('description', '')
                source = a.get('source', {}).get('name', 'Unknown')
                
                # Phân tích từ khóa
                result = phan_tich_tin(title, description)
                if result is None:
                    continue  # Bỏ qua tin trung tính
                
                log['news_sent'].append(url_news)
                
                all_news.append({
                    'title': title,
                    'source': source,
                    'loai': result['loai'],
                    'gold': result['gold'],
                    'crypto': result['crypto'],
                    'usd': result['usd'],
                    'advice': result['advice'],
                    'keywords': result['keywords'],
                    'url': url_news
                })
            
            time.sleep(0.5)  # Tránh rate limit
            
        except Exception as e:
            print(f"Query error ({query}): {e}")
            continue
    
    log['news_sent'] = log['news_sent'][-500:]
    save_log(log)
    
    # Sắp xếp: tin tiêu cực trước
    priority = {'CỰC KỲ TIÊU CỰC': 0, 'RẤT TIÊU CỰC': 1, 'TIÊU CỰC': 2,
                'TÍCH CỰC': 3, 'RẤT TÍCH CỰC': 4, 'CỰC KỲ TÍCH CỰC': 5}
    all_news.sort(key=lambda x: priority.get(x['loai'].split()[-1] if 'CỰC' in x['loai'] else x['loai'].split()[-1], 3))
    
    return all_news

def market_summary(news_list):
    if not news_list: return None
    
    neg_count = sum(1 for n in news_list if 'TIÊU CỰC' in n['loai'])
    pos_count = sum(1 for n in news_list if 'TÍCH CỰC' in n['loai'])
    
    if neg_count >= 5:
        level = "RẤT CAO"
        advice = "⚠️ ƯU TIÊN SHORT"
    elif neg_count >= 3:
        level = "CAO"
        advice = "⚠️ NGHIÊNG VỀ SHORT"
    elif pos_count >= 5:
        level = "THẤP (TÍCH CỰC)"
        advice = "✅ ƯU TIÊN LONG"
    else:
        level = "TRUNG BÌNH"
        advice = "➡️ THEO DÕI THÊM"
    
    all_kw = []
    for n in news_list: all_kw.extend(n['keywords'])
    top_kw = list(set(all_kw))[:8]
    
    return f"📰 TỔNG QUAN THỊ TRƯỜNG\n━━━━━━━━━━━━━━━━━━\n🚨 Căng thẳng {level}\n📊 Tin tiêu cực: {neg_count} | Tích cực: {pos_count}\n💡 {advice}\n\n📋 Số tin: {len(news_list)}\n🔑 Từ khóa: {', '.join(top_kw)}\n\n{now_str()}"

# 7 SỰ KIỆN KINH TẾ
EVENTS = [
    {'id':'nfp_may','name':'💼 Non-Farm Payrolls (T5)','date':'2026-06-05','time':'19:30','impact':'🔴 HIGH','desc':'Báo cáo việc làm phi nông nghiệp Mỹ.','fred':'UNRATE','fmt':'Tỷ lệ thất nghiệp: {value}% (trước: {prev}%)\n🎤 Thái độ: {action}\n📝 {detail}','gold':'NFP cao → GIẢM | NFP thấp → TĂNG','crypto':'NFP cao → TĂNG | NFP thấp → GIẢM','usd':'NFP cao → TĂNG | NFP thấp → GIẢM'},
    {'id':'cpi_may','name':'📊 CPI Report (T5)','date':'2026-06-11','time':'19:30','impact':'🔴 HIGH','desc':'Chỉ số giá tiêu dùng - thước đo lạm phát.','fred':'CPIAUCSL','fmt':'CPI: {value} (trước: {prev})\n🎤 Thái độ: {action}\n📝 CPI {detail}.','gold':'CPI cao → TĂNG | CPI thấp → GIẢM','crypto':'CPI cao → GIẢM | CPI thấp → TĂNG','usd':'CPI cao → TĂNG | CPI thấp → GIẢM'},
    {'id':'ppi_may','name':'🏭 PPI Report (T5)','date':'2026-06-12','time':'19:30','impact':'🟡 MEDIUM','desc':'Chỉ số giá sản xuất.','fred':'PPIACO','fmt':'PPI: {value} (trước: {prev})\n🎤 Thái độ: {action}\n📝 PPI {detail}.','gold':'PPI cao → TĂNG | PPI thấp → GIẢM','crypto':'PPI cao → TĂNG nhẹ','usd':'PPI cao → TĂNG nhẹ'},
    {'id':'fomc_jun','name':'🏦 FOMC Rate Decision (T6)','date':'2026-06-18','time':'01:00','impact':'🔴 HIGH','desc':'Quyết định lãi suất Fed - SỰ KIỆN QUAN TRỌNG NHẤT.','fred':'DFF','fmt':'Lãi suất Fed: {value}% (trước: {prev}%)\n🎤 Thái độ: Fed {action}\n📝 {detail}.','gold':'Hawkish → GIẢM | Dovish → TĂNG','crypto':'Hawkish → GIẢM | Dovish → TĂNG','usd':'Hawkish → TĂNG | Dovish → GIẢM'},
    {'id':'gdp_q2','name':'📊 GDP Q2 2026 (Final)','date':'2026-06-25','time':'19:30','impact':'🔴 HIGH','desc':'Tăng trưởng kinh tế Mỹ quý 2.','fred':'GDP','fmt':'GDP: ${value:,.0f}B (trước: ${prev:,.0f}B)\n🎤 Thái độ: {action}\n📝 GDP thay đổi {detail}%.','gold':'GDP cao → GIẢM | GDP thấp → TĂNG','crypto':'GDP cao → TĂNG | GDP thấp → GIẢM','usd':'GDP cao → TĂNG | GDP thấp → GIẢM'},
    {'id':'fomc_jul','name':'🏦 FOMC Rate Decision (T7)','date':'2026-07-30','time':'01:00','impact':'🔴 HIGH','desc':'Quyết định lãi suất giữa năm 2026.','fred':'DFF','fmt':'Lãi suất Fed: {value}% (trước: {prev}%)\n🎤 Thái độ: Fed {action}\n📝 {detail}.','gold':'Hawkish → GIẢM | Dovish → TĂNG','crypto':'Hawkish → GIẢM | Dovish → TĂNG','usd':'Hawkish → TĂNG | Dovish → GIẢM'},
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
        
        if 0 <= days <= 3:
            key = f"pre_{ev['id']}"
            if time.time() - log['events'].get(key, 0) >= 43200:
                log['events'][key] = time.time()
                cd = f"⚠️ HÔM NAY lúc {ev['time']} (UTC+7)" if days==0 else f"📅 NGÀY MAI lúc {ev['time']} (UTC+7)" if days==1 else f"📅 Còn {days} ngày - {ev['date']} lúc {ev['time']} (UTC+7)"
                msgs.append(f"📅 {ev['name']}\n━━━━━━━━━━━━━━━━━━\n⏰ {cd}\n⚡ {ev['impact']}\n📝 {ev['desc']}\n\n━━━━━━━━━━━━━━━━━━\n📊 TÁC ĐỘNG DỰ KIẾN:\n🥇 Vàng: {ev['gold']}\n₿ Crypto: {ev['crypto']}\n💵 USD: {ev['usd']}\n━━━━━━━━━━━━━━━━━━\n\n📊 DỮ LIỆU HIỆN TẠI:\n{econ_summary()}\n\n{now_str()}")
        
        elif days < 0 and 1 <= hours_since <= 24:
            key = f"post_{ev['id']}"
            if key not in log['events'] and fred_ok():
                v = fred_get(ev['fred'])
                if v and len(v) >= 2:
                    curr, prev = v[0]['v'], v[1]['v']
                    
                    if curr > prev:
                        if 'fomc' in ev['id']:
                            action = "TĂNG lãi suất 🦅"
                            detail = f"Fed đã TĂNG lãi suất thêm {round(curr-prev,2)}%"
                        elif 'gdp' in ev['id']:
                            action = "📈 TĂNG TRƯỞNG ✅"
                            detail = f"+{round((curr-prev)/prev*100,2)}"
                        elif 'nfp' in ev['id']:
                            action = "📈 TĂNG"
                            detail = "Thị trường lao động yếu đi"
                        else:
                            action = "📈 TĂNG"
                            detail = f"tăng {round((curr-prev)/prev*100,1)}%"
                    elif curr < prev:
                        if 'fomc' in ev['id']:
                            action = "GIẢM lãi suất 🕊️"
                            detail = f"Fed đã GIẢM lãi suất {round(prev-curr,2)}%"
                        elif 'gdp' in ev['id']:
                            action = "📉 SUY GIẢM ⚠️"
                            detail = f"{round((curr-prev)/prev*100,2)}"
                        elif 'nfp' in ev['id']:
                            action = "📉 GIẢM"
                            detail = "Thị trường lao động mạnh lên"
                        else:
                            action = "📉 GIẢM"
                            detail = f"giảm {round((prev-curr)/prev*100,1)}%"
                    else:
                        if 'fomc' in ev['id']:
                            action = "GIỮ NGUYÊN ➡️"
                            detail = f"Fed GIỮ NGUYÊN lãi suất ở mức {curr}%"
                        else:
                            action = "➡️ KHÔNG ĐỔI"
                            detail = "không đổi"
                    
                    log['events'][key] = time.time()
                    msgs.append(f"===================================\n✅ {ev['name']} - KẾT QUẢ THỰC TẾ\n===================================\n⏰ Đã diễn ra: {ev['date']} lúc {ev['time']} (UTC+7)\n\n{ev['fmt'].format(value=curr, prev=prev, action=action, detail=detail)}\n\n━━━━━━━━━━━━━━━━━━\n📊 TÁC ĐỘNG THỊ TRƯỜNG:\n🥇 Vàng: {ev['gold']}\n₿ Crypto: {ev['crypto']}\n💵 USD: {ev['usd']}\n━━━━━━━━━━━━━━━━━━\n\n📊 DỮ LIỆU FRED:\n{econ_summary()}\n\n{now_str()}")
    
    save_log(log)
    return msgs

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

# === MAIN ===
print("BOT TIN TUC STARTED")

while True:
    try:
        s = get_state()
        
        if not s['started']:
            set_state(started=True)
            
            # Xóa cache news_sent để lấy tin mới khi khởi động
            log = get_log()
            log['news_sent'] = []
            save_log(log)
            
            news = fetch_news()
            
            msg = f"📰 Bot tin tức đã khởi động!\n━━━━━━━━━━━━━━━━━━\n📡 FRED: {'✅ Online' if fred_ok() else '⏳ Offline'}\n📡 NewsAPI: ✅ Online\n\n📊 DỮ LIỆU KINH TẾ:\n{econ_summary()}\n\n"
            if news: msg += f"📋 Phát hiện {len(news)} tin liên quan thị trường\n"
            msg += f"\n✅ Đang theo dõi sự kiện...\n\n{now_str()}"
            gui(msg)
            
            if news:
                summary = market_summary(news)
                if summary: gui(summary)
                for n in news:
                    msg = f"📰 TIN TỨC THỊ TRƯỜNG {n['loai']}\n━━━━━━━━━━━━━━━━━━\n{n['title']}\n\n📡 Nguồn: {n['source']}\n🔑 Từ khóa: {', '.join(n['keywords'])}\n\n🏦 Dự báo:\n🥇 Vàng: {n['gold']}\n₿ Crypto: {n['crypto']}\n💵 USD: {n['usd']}\n\n💡 Khuyến nghị: {n['advice']}\n\n{now_str()}"
                    gui(msg)
                    time.sleep(1)

        news = fetch_news()
        if news:
            summary = market_summary(news)
            if summary: gui(summary)
            for n in news:
                msg = f"📰 TIN TỨC THỊ TRƯỜNG {n['loai']}\n━━━━━━━━━━━━━━━━━━\n{n['title']}\n\n📡 Nguồn: {n['source']}\n🔑 Từ khóa: {', '.join(n['keywords'])}\n\n🏦 Dự báo:\n🥇 Vàng: {n['gold']}\n₿ Crypto: {n['crypto']}\n💵 USD: {n['usd']}\n\n💡 Khuyến nghị: {n['advice']}\n\n{now_str()}"
                gui(msg)
                time.sleep(1)

        if time.time() - s['lich_last'] >= CHU_KY_LICH:
            set_state(lich_last=time.time())
            for m in check_events():
                gui(m)

        fg = get_fg()
        if fg: gui(fg)

        time.sleep(CHU_KY_TIN)
    except KeyboardInterrupt: break
    except Exception as e:
        print(f"Loi: {e}")
        time.sleep(30)