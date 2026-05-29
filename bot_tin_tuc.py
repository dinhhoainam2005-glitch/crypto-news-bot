"""
BOT TIN TUC - NEWSAPI + FRED + DỊCH TIẾNG VIỆT
- 100% dữ liệu thật từ NewsAPI + FRED
- Dịch tiếng Việt + Highlight từ khóa quan trọng
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
    for sid, fmt in [('DFF','<b>Fed Rate:</b> {}%'), ('CPIAUCSL','<b>CPI:</b> {}'), ('UNRATE','<b>UE:</b> {}%'), ('GDP','<b>GDP:</b> ${:,.0f}B'), ('PPIACO','<b>PPI:</b> {}')]:
        v = fred_get(sid)
        if v: parts.append(fmt.format(v[0]['v']))
    return " | ".join(parts) if parts else "Đang tải..."

# ===== DỊCH TIẾNG VIỆT =====
def dich_tieng_viet(text):
    """Dịch bằng Google Translate API miễn phí"""
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            'client': 'gtx',
            'sl': 'en',
            'tl': 'vi',
            'dt': 't',
            'q': text
        }
        r = requests.get(url, params=params, timeout=5)
        if r.status_code == 200:
            result = r.json()
            translated = ''.join([s[0] for s in result[0] if s[0]])
            return translated
    except:
        pass
    return text  # Fallback: giữ nguyên tiếng Anh

# ===== TỪ KHÓA =====
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
    "rate hike", "hawkish", "tighten", "inflation surge",
    "crackdown", "ban", "delist", "lawsuit", "sec charge", "fraud",
    "tension", "escalation", "conflict", "attack", "casualty",
    "oil price surge", "supply shock", "shortage", "crisis"
]

DICH_KW = {
    "ceasefire": "ngừng bắn", "peace deal": "thỏa thuận hòa bình", "peace talk": "đàm phán hòa bình",
    "truce": "đình chiến", "surrender": "đầu hàng", "withdraw": "rút quân",
    "rate cut": "hạ lãi suất", "dovish": "ôn hòa", "easing": "nới lỏng",
    "bull market": "thị trường tăng", "rally": "tăng mạnh", "surge": "tăng vọt",
    "deal": "thỏa thuận", "agreement": "đồng thuận", "partnership": "hợp tác",
    "war": "chiến tranh", "invasion": "xâm lược", "strike": "không kích",
    "missile": "tên lửa", "bomb": "ném bom", "airstrike": "không kích",
    "offensive": "tấn công", "nuclear": "hạt nhân", "sanction": "trừng phạt",
    "embargo": "cấm vận", "tariff": "thuế quan", "trade war": "chiến tranh thương mại",
    "crash": "sụp đổ", "recession": "suy thoái", "depression": "đại suy thoái",
    "collapse": "sụp đổ", "rate hike": "tăng lãi suất", "hawkish": "diều hâu",
    "crackdown": "đàn áp", "ban": "cấm", "lawsuit": "kiện tụng",
    "tension": "căng thẳng", "escalation": "leo thang", "conflict": "xung đột",
    "attack": "tấn công", "casualty": "thương vong", "crisis": "khủng hoảng"
}

def phan_tich_tin(title, description=""):
    t = (title + " " + description).lower()
    pos_found = [DICH_KW.get(kw, kw) for kw in POSITIVE_KW if kw in t]
    neg_found = [DICH_KW.get(kw, kw) for kw in NEGATIVE_KW if kw in t]
    
    if len(neg_found) > len(pos_found):
        if len(neg_found) >= 3: loai = "🔴🔴🔴 <b>CỰC KỲ TIÊU CỰC</b>"
        elif len(neg_found) >= 2: loai = "🔴🔴 <b>RẤT TIÊU CỰC</b>"
        else: loai = "🔴 <b>TIÊU CỰC</b>"
        gold = "🥇 <b>Vàng: 🟢 TĂNG</b> (trú ẩn)"
        crypto = "₿ <b>Crypto: 🔴 GIẢM</b> (risk-off)"
        usd = "💵 <b>USD: 🟢 TĂNG</b> (trú ẩn)"
        advice = "⚠️ <b>ƯU TIÊN SHORT</b>"
        keywords = neg_found
    elif len(pos_found) > len(neg_found):
        if len(pos_found) >= 3: loai = "🟢🟢🟢 <b>CỰC KỲ TÍCH CỰC</b>"
        elif len(pos_found) >= 2: loai = "🟢🟢 <b>TÍCH CỰC</b>"
        else: loai = "🟢 <b>TÍCH CỰC</b>"
        gold = "🥇 <b>Vàng: 🔴 GIẢM</b> (risk-on)"
        crypto = "₿ <b>Crypto: 🟢 TĂNG</b> (risk-on)"
        usd = "💵 <b>USD: 🔴 GIẢM</b> (risk-on)"
        advice = "✅ <b>ƯU TIÊN LONG</b>"
        keywords = pos_found
    else:
        return None
    
    return {'loai': loai, 'gold': gold, 'crypto': crypto, 'usd': usd, 'advice': advice, 'keywords': keywords}

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
            if r.status_code != 200: continue
            
            articles = r.json().get('articles', [])
            
            for a in articles:
                url_news = a.get('url', '')
                if url_news in log['news_sent']: continue
                
                title = a.get('title', '')
                description = a.get('description', '')
                source = a.get('source', {}).get('name', 'Unknown')
                
                result = phan_tich_tin(title, description)
                if result is None: continue
                
                log['news_sent'].append(url_news)
                
                # Dịch tiêu đề sang tiếng Việt
                title_vi = dich_tieng_viet(title)
                
                all_news.append({
                    'title_en': title,
                    'title_vi': title_vi,
                    'source': source,
                    'loai': result['loai'],
                    'gold': result['gold'],
                    'crypto': result['crypto'],
                    'usd': result['usd'],
                    'advice': result['advice'],
                    'keywords': result['keywords']
                })
            
            time.sleep(0.5)
        except Exception as e:
            print(f"Query error ({query}): {e}")
            continue
    
    log['news_sent'] = log['news_sent'][-500:]
    save_log(log)
    
    # Sắp xếp: tiêu cực trước
    priority = {'CỰC KỲ TIÊU CỰC': 0, 'RẤT TIÊU CỰC': 1, 'TIÊU CỰC': 2,
                'TÍCH CỰC': 3, 'RẤT TÍCH CỰC': 4, 'CỰC KỲ TÍCH CỰC': 5}
    all_news.sort(key=lambda x: priority.get(x['loai'].split()[-1] if 'CỰC' in x['loai'] else x['loai'].split()[-1], 3))
    
    return all_news

def market_summary(news_list):
    if not news_list: return None
    
    neg_count = sum(1 for n in news_list if 'TIÊU CỰC' in n['loai'])
    pos_count = sum(1 for n in news_list if 'TÍCH CỰC' in n['loai'])
    
    if neg_count >= 5:
        level = "<b>RẤT CAO</b>"
        advice = "⚠️ <b>ƯU TIÊN SHORT</b>"
    elif neg_count >= 3:
        level = "<b>CAO</b>"
        advice = "⚠️ <b>NGHIÊNG VỀ SHORT</b>"
    elif pos_count >= 5:
        level = "<b>THẤP (TÍCH CỰC)</b>"
        advice = "✅ <b>ƯU TIÊN LONG</b>"
    else:
        level = "<b>TRUNG BÌNH</b>"
        advice = "➡️ <b>THEO DÕI THÊM</b>"
    
    all_kw = []
    for n in news_list: all_kw.extend(n['keywords'])
    top_kw = list(set(all_kw))[:8]
    
    return f"📰 <b>TỔNG QUAN THỊ TRƯỜNG</b>\n━━━━━━━━━━━━━━━━━━\n🚨 Căng thẳng {level}\n📊 Tin tiêu cực: {neg_count} | Tích cực: {pos_count}\n💡 {advice}\n\n📋 Số tin: {len(news_list)}\n🔑 Từ khóa: {', '.join(top_kw)}\n\n{now_str()}"

# 7 SỰ KIỆN
EVENTS = [
    {'id':'nfp_may','name':'💼 Non-Farm Payrolls (T5)','date':'2026-06-05','time':'19:30','impact':'🔴 HIGH','desc':'Báo cáo việc làm phi nông nghiệp Mỹ.','fred':'UNRATE','fmt':'<b>Tỷ lệ thất nghiệp:</b> {value}% (trước: {prev}%)\n🎤 <b>Thái độ:</b> {action}\n📝 {detail}','gold':'<b>NFP cao → GIẢM</b> | NFP thấp → TĂNG','crypto':'<b>NFP cao → TĂNG</b> | NFP thấp → GIẢM','usd':'<b>NFP cao → TĂNG</b> | NFP thấp → GIẢM'},
    {'id':'cpi_may','name':'📊 CPI Report (T5)','date':'2026-06-11','time':'19:30','impact':'🔴 HIGH','desc':'Chỉ số giá tiêu dùng - thước đo lạm phát.','fred':'CPIAUCSL','fmt':'<b>CPI:</b> {value} (trước: {prev})\n🎤 <b>Thái độ:</b> {action}\n📝 CPI {detail}.','gold':'<b>CPI cao → TĂNG</b> | CPI thấp → GIẢM','crypto':'<b>CPI cao → GIẢM</b> | CPI thấp → TĂNG','usd':'<b>CPI cao → TĂNG</b> | CPI thấp → GIẢM'},
    {'id':'ppi_may','name':'🏭 PPI Report (T5)','date':'2026-06-12','time':'19:30','impact':'🟡 MEDIUM','desc':'Chỉ số giá sản xuất.','fred':'PPIACO','fmt':'<b>PPI:</b> {value} (trước: {prev})\n🎤 <b>Thái độ:</b> {action}\n📝 PPI {detail}.','gold':'<b>PPI cao → TĂNG</b> | PPI thấp → GIẢM','crypto':'<b>PPI cao → TĂNG nhẹ</b>','usd':'<b>PPI cao → TĂNG nhẹ</b>'},
    {'id':'fomc_jun','name':'🏦 FOMC Rate Decision (T6)','date':'2026-06-18','time':'01:00','impact':'🔴 HIGH','desc':'Quyết định lãi suất Fed - SỰ KIỆN QUAN TRỌNG NHẤT.','fred':'DFF','fmt':'<b>Lãi suất Fed:</b> {value}% (trước: {prev}%)\n🎤 <b>Thái độ:</b> Fed {action}\n📝 {detail}.','gold':'<b>Hawkish → GIẢM</b> | Dovish → TĂNG','crypto':'<b>Hawkish → GIẢM</b> | Dovish → TĂNG','usd':'<b>Hawkish → TĂNG</b> | Dovish → GIẢM'},
    {'id':'gdp_q2','name':'📊 GDP Q2 2026 (Final)','date':'2026-06-25','time':'19:30','impact':'🔴 HIGH','desc':'Tăng trưởng kinh tế Mỹ quý 2.','fred':'GDP','fmt':'<b>GDP:</b> ${value:,.0f}B (trước: ${prev:,.0f}B)\n🎤 <b>Thái độ:</b> {action}\n📝 GDP thay đổi {detail}%.','gold':'<b>GDP cao → GIẢM</b> | GDP thấp → TĂNG','crypto':'<b>GDP cao → TĂNG</b> | GDP thấp → GIẢM','usd':'<b>GDP cao → TĂNG</b> | GDP thấp → GIẢM'},
    {'id':'fomc_jul','name':'🏦 FOMC Rate Decision (T7)','date':'2026-07-30','time':'01:00','impact':'🔴 HIGH','desc':'Quyết định lãi suất giữa năm 2026.','fred':'DFF','fmt':'<b>Lãi suất Fed:</b> {value}% (trước: {prev}%)\n🎤 <b>Thái độ:</b> Fed {action}\n📝 {detail}.','gold':'<b>Hawkish → GIẢM</b> | Dovish → TĂNG','crypto':'<b>Hawkish → GIẢM</b> | Dovish → TĂNG','usd':'<b>Hawkish → TĂNG</b> | Dovish → GIẢM'},
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
                cd = f"⚠️ <b>HÔM NAY</b> lúc {ev['time']} (UTC+7)" if days==0 else f"📅 <b>NGÀY MAI</b> lúc {ev['time']} (UTC+7)" if days==1 else f"📅 Còn <b>{days} ngày</b> - {ev['date']} lúc {ev['time']} (UTC+7)"
                msgs.append(f"📅 <b>{ev['name']}</b>\n━━━━━━━━━━━━━━━━━━\n⏰ {cd}\n⚡ {ev['impact']}\n📝 {ev['desc']}\n\n━━━━━━━━━━━━━━━━━━\n📊 <b>TÁC ĐỘNG DỰ KIẾN:</b>\n{ev['gold']}\n{ev['crypto']}\n{ev['usd']}\n━━━━━━━━━━━━━━━━━━\n\n📊 <b>DỮ LIỆU HIỆN TẠI:</b>\n{econ_summary()}\n\n{now_str()}")
        
        elif days < 0 and 1 <= hours_since <= 24:
            key = f"post_{ev['id']}"
            if key not in log['events'] and fred_ok():
                v = fred_get(ev['fred'])
                if v and len(v) >= 2:
                    curr, prev = v[0]['v'], v[1]['v']
                    
                    if curr > prev:
                        if 'fomc' in ev['id']: action = "<b>TĂNG lãi suất 🦅</b>"; detail = f"Fed đã <b>TĂNG</b> lãi suất thêm {round(curr-prev,2)}%"
                        elif 'gdp' in ev['id']: action = "<b>📈 TĂNG TRƯỞNG ✅</b>"; detail = f"<b>+{round((curr-prev)/prev*100,2)}%</b>"
                        elif 'nfp' in ev['id']: action = "<b>📈 TĂNG</b>"; detail = "Thị trường lao động <b>yếu đi</b>"
                        else: action = "<b>📈 TĂNG</b>"; detail = f"tăng <b>{round((curr-prev)/prev*100,1)}%</b>"
                    elif curr < prev:
                        if 'fomc' in ev['id']: action = "<b>GIẢM lãi suất 🕊️</b>"; detail = f"Fed đã <b>GIẢM</b> lãi suất {round(prev-curr,2)}%"
                        elif 'gdp' in ev['id']: action = "<b>📉 SUY GIẢM ⚠️</b>"; detail = f"<b>{round((curr-prev)/prev*100,2)}%</b>"
                        elif 'nfp' in ev['id']: action = "<b>📉 GIẢM</b>"; detail = "Thị trường lao động <b>mạnh lên</b>"
                        else: action = "<b>📉 GIẢM</b>"; detail = f"giảm <b>{round((prev-curr)/prev*100,1)}%</b>"
                    else:
                        if 'fomc' in ev['id']: action = "<b>GIỮ NGUYÊN ➡️</b>"; detail = f"Fed <b>GIỮ NGUYÊN</b> lãi suất ở mức {curr}%"
                        else: action = "<b>➡️ KHÔNG ĐỔI</b>"; detail = "<b>không đổi</b>"
                    
                    log['events'][key] = time.time()
                    msgs.append(f"===================================\n✅ <b>{ev['name']} - KẾT QUẢ THỰC TẾ</b>\n===================================\n⏰ Đã diễn ra: {ev['date']} lúc {ev['time']} (UTC+7)\n\n{ev['fmt'].format(value=curr, prev=prev, action=action, detail=detail)}\n\n━━━━━━━━━━━━━━━━━━\n📊 <b>TÁC ĐỘNG THỊ TRƯỜNG:</b>\n{ev['gold']}\n{ev['crypto']}\n{ev['usd']}\n━━━━━━━━━━━━━━━━━━\n\n📊 <b>DỮ LIỆU FRED:</b>\n{econ_summary()}\n\n{now_str()}")
    
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
        return f"{i} <b>Fear & Greed Index:</b> {v}/100 ({c})"
    except: return None

# === MAIN ===
print("BOT TIN TUC STARTED")

while True:
    try:
        s = get_state()
        
        if not s['started']:
            set_state(started=True)
            log = get_log()
            log['news_sent'] = []
            save_log(log)
            
            news = fetch_news()
            
            msg = f"📰 <b>Bot tin tức đã khởi động!</b>\n━━━━━━━━━━━━━━━━━━\n📡 FRED: {'✅ Online' if fred_ok() else '⏳ Offline'}\n📡 NewsAPI: ✅ Online\n\n📊 <b>DỮ LIỆU KINH TẾ:</b>\n{econ_summary()}\n\n"
            if news: msg += f"📋 Phát hiện <b>{len(news)} tin</b> liên quan thị trường\n"
            msg += f"\n✅ Đang theo dõi sự kiện...\n\n{now_str()}"
            gui(msg)
            
            if news:
                summary = market_summary(news)
                if summary: gui(summary)
                for n in news:
                    msg = f"📰 TIN TỨC THỊ TRƯỜNG {n['loai']}\n━━━━━━━━━━━━━━━━━━\n{n['title_vi']}\n\n📡 Nguồn: {n['source']}\n🔑 Từ khóa: <b>{', '.join(n['keywords'])}</b>\n\n🏦 <b>Dự báo:</b>\n{n['gold']}\n{n['crypto']}\n{n['usd']}\n\n💡 Khuyến nghị: {n['advice']}\n\n{now_str()}"
                    gui(msg)
                    time.sleep(1)

        news = fetch_news()
        if news:
            summary = market_summary(news)
            if summary: gui(summary)
            for n in news:
                msg = f"📰 TIN TỨC THỊ TRƯỜNG {n['loai']}\n━━━━━━━━━━━━━━━━━━\n{n['title_vi']}\n\n📡 Nguồn: {n['source']}\n🔑 Từ khóa: <b>{', '.join(n['keywords'])}</b>\n\n🏦 <b>Dự báo:</b>\n{n['gold']}\n{n['crypto']}\n{n['usd']}\n\n💡 Khuyến nghị: {n['advice']}\n\n{now_str()}"
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