"""
BOT TIN TUC - NEWSAPI + RSS FEEDS - PRO V5 SONG NGU
- 5 nguồn RSS miễn phí: Reuters, CNBC, CoinDesk, Cointelegraph, MarketWatch
- NewsAPI bổ sung
- Hiển thị SONG NGỮ: Tiêu đề gốc tiếng Anh + Tóm tắt tiếng Việt
- CME FedWatch cho dự đoán lãi suất FOMC
- Post-event tự động báo cáo kết quả thực tế
- Tối đa 10 tin chất lượng/lần gửi
- Sự kiện trước 5 ngày + báo cáo sau 1-24h
- 6h cập nhật 1 lần
"""
import requests
import time
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from html import unescape

TOKEN = os.getenv("TELEGRAM_TOKEN", "8893995280:AAF9XwWAm9QgPkwmDrhZdY6UQ4zfySooWpk")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "518284897")
FRED_API_KEY = os.getenv("FRED_API_KEY", "ff3e122af2b2c0a433606476fc6dc5fb")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "bcdf1d28d8bd401f9eb1978268efeb53")

CHU_KY = 21600
MAX_NEWS = 10
DATA_DIR = "data"
STATE_FILE = f"{DATA_DIR}/state_news.json"
LOG_FILE = f"{DATA_DIR}/log_news.json"

BLOCKED_SOURCES = ["naturalnews.com", "naturalnews", "beforeitsnews.com", "infowars.com", 
                   "zerohedge.com", "activistpost.com", "globalresearch.ca", "nakedcapitalism.com",
                   "thegatewaypundit.com", "breitbart.com", "occupydemocrats.com", "dailycaller.com",
                   "foxnews.com"]

TRUSTED_SOURCES = ["reuters.com", "bloomberg.com", "cnbc.com", "wsj.com", "ft.com",
                   "coindesk.com", "cointelegraph.com", "theblock.co", "marketwatch.com",
                   "investing.com", "forexlive.com", "apnews.com", "bbc.com", "aljazeera.com",
                   "economist.com", "barrons.com", "financialpost.com", "fxstreet.com"]

RSS_FEEDS = [
    ("https://feeds.reuters.com/reuters/businessNews", "Reuters"),
    ("https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01", "CNBC"),
    ("https://www.coindesk.com/arc/outboundfeeds/news/", "CoinDesk"),
    ("https://cointelegraph.com/rss", "Cointelegraph"),
    ("https://feeds.marketwatch.com/marketwatch/topstories", "MarketWatch"),
]

os.makedirs(DATA_DIR, exist_ok=True)

def get_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f: return json.load(f)
    return {"started": False, "last_update": 0}

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
    for sid, fmt in [('DFF','<b>Lãi suất Fed:</b> {}%'), ('CPIAUCSL','<b>CPI:</b> {}'), ('UNRATE','<b>Thất nghiệp:</b> {}%'), ('GDP','<b>GDP:</b> ${:,.0f}B'), ('PPIACO','<b>PPI:</b> {}')]:
        v = fred_get(sid)
        if v: parts.append(fmt.format(v[0]['v']))
    return " | ".join(parts) if parts else "Đang tải..."

def format_date(date_str):
    formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%d/%m/%Y %H:%M")
        except: pass
    return date_str[:16] if len(date_str) > 16 else date_str

# ============================================
# CME FEDWATCH
# ============================================
def get_fedwatch_prediction():
    try:
        r = requests.get("https://www.cmegroup.com/CmeWS/mvc/AtmOptions/FedWatchWidget", 
                        params={"timePeriod": "current"}, timeout=10,
                        headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code != 200: return None
        
        data = r.json()
        meetings = data.get('meetings', [])
        if not meetings: return None
        
        next_meeting = meetings[0]
        rates = next_meeting.get('probabilities', [])
        
        prob_hold = 0
        prob_cut = 0
        prob_hike = 0
        current_rate = next_meeting.get('currentTarget', 'N/A')
        
        for rate_info in rates:
            label = rate_info.get('label', '')
            prob = rate_info.get('probability', 0)
            if 'current' in label.lower():
                prob_hold = prob
            elif 'cut' in label.lower():
                prob_cut += prob
            elif 'hike' in label.lower():
                prob_hike += prob
        
        if prob_cut > prob_hold and prob_cut > prob_hike:
            prediction = f"📉 <b>GIẢM lãi suất</b> ({prob_cut:.0f}%)"
        elif prob_hike > prob_hold and prob_hike > prob_cut:
            prediction = f"📈 <b>TĂNG lãi suất</b> ({prob_hike:.0f}%)"
        else:
            prediction = f"➡️ <b>GIỮ NGUYÊN</b> ({prob_hold:.0f}%)"
        
        return {
            'current_rate': current_rate,
            'prob_hold': prob_hold,
            'prob_cut': prob_cut,
            'prob_hike': prob_hike,
            'prediction': prediction,
        }
    except:
        return None

# ============================================
# TOM TAT TIENG VIET
# ============================================
def tom_tat_tieng_viet(title, description, keywords):
    """Tạo tóm tắt tiếng Việt từ keywords và description"""
    parts = []
    
    # Dịch keywords
    if keywords:
        parts.append(f"🔑 {', '.join(keywords)}")
    
    # Lấy câu đầu tiên của description làm tóm tắt
    if description:
        desc_clean = re.sub(r'<[^>]+>', '', description)
        desc_clean = unescape(desc_clean)
        first_sentence = desc_clean.split('.')[0]
        if len(first_sentence) > 15:
            parts.append(f"📝 {first_sentence.strip()}.")
    
    return "\n".join(parts) if parts else "Đang cập nhật..."

# ============================================
# KEYWORD MATCHING
# ============================================
POSITIVE_KW = [
    "rate cut", "dovish", "easing", "ceasefire", "peace deal", "peace talk",
    "truce", "surrender", "withdrawal", "bull market", "rally", "etf approved",
    "etf inflow", "blackrock", "institutional", "adoption", "partnership",
    "stimulus", "rebound", "recover", "surge", "soar"
]

NEGATIVE_KW = [
    "war", "strike", "missile", "bomb", "airstrike", "attack", "invasion",
    "offensive", "nuclear", "sanction", "embargo", "tariff", "trade war",
    "rate hike", "hawkish", "tightening", "recession", "depression", "crash",
    "collapse", "oil price surge", "crude surge", "etf outflow", "hormuz",
    "escalation", "conflict", "tensions", "plunge", "tumble", "slump"
]

def has_keyword(text, word):
    return bool(re.search(r'\b' + re.escape(word) + r'\b', text.lower()))

def phan_tich_tin(title, description=""):
    t = (title + " " + description).lower()
    
    pos_found = [kw for kw in POSITIVE_KW if has_keyword(t, kw)]
    neg_found = [kw for kw in NEGATIVE_KW if has_keyword(t, kw)]
    
    pos_found = list(set(pos_found))
    neg_found = list(set(neg_found))
    
    if not pos_found and not neg_found:
        return None
    
    # AI Context
    has_war = any(has_keyword(t, w) for w in ['war', 'strike', 'airstrike', 'attack', 'invasion'])
    has_oil = any(has_keyword(t, w) for w in ['oil price', 'crude oil', 'crude surge'])
    if has_war and has_oil:
        neg_found.append("oil war")
        pos_found = [p for p in pos_found if p not in ['ceasefire', 'truce']]
    
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

# ============================================
# QUERIES
# ============================================
QUERIES = [
    "iran israel war strike ceasefire",
    "russia ukraine war nato peace talk",
    "fed interest rate inflation fomc",
    "trade war tariff sanction",
    "oil price crude hormuz opec",
    "stock market crash recession",
    "crypto bitcoin etf regulation sec",
    "gold price safe haven",
    "south china sea taiwan philippines",
    "north korea missile nuclear",
    "de-dollarization brics currency",
    "opec oil production cut",
]

def similarity(s1, s2):
    if not s1 or not s2: return 0
    words1 = set(s1.lower().split())
    words2 = set(s2.lower().split())
    if not words1 or not words2: return 0
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    return len(intersection) / len(union)

# ============================================
# FETCH RSS
# ============================================
def fetch_rss_news(log):
    all_news = []
    
    for url, source_name in RSS_FEEDS:
        try:
            r = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            if r.status_code != 200: continue
            
            root = ET.fromstring(r.content)
            items = root.findall('.//item')
            if not items:
                items = root.findall('.//{http://www.w3.org/2005/Atom}entry')
            
            for item in items[:5]:
                title_el = item.find('title')
                desc_el = item.find('description')
                link_el = item.find('link')
                date_el = item.find('pubDate')
                
                if title_el is None: title_el = item.find('{http://www.w3.org/2005/Atom}title')
                if desc_el is None: desc_el = item.find('{http://www.w3.org/2005/Atom}summary')
                if link_el is None: link_el = item.find('{http://www.w3.org/2005/Atom}link')
                if date_el is None: 
                    date_el = item.find('{http://www.w3.org/2005/Atom}updated') or item.find('{http://www.w3.org/2005/Atom}published')
                
                title = title_el.text if title_el is not None else ''
                description = desc_el.text if desc_el is not None and desc_el.text else ''
                link = link_el.get('href') if link_el is not None and link_el.get('href') else (link_el.text if link_el is not None else '')
                pubdate = date_el.text if date_el is not None else ''
                
                if not title: continue
                if link in log['news_sent']: continue
                
                result = phan_tich_tin(title, description)
                if result is None: continue
                
                is_duplicate = False
                for existing in all_news:
                    if similarity(title, existing.get('title_en', '')) > 0.5:
                        is_duplicate = True
                        break
                
                if is_duplicate: continue
                
                log['news_sent'].append(link)
                
                all_news.append({
                    'title_en': title,
                    'description': description,
                    'source': source_name,
                    'date': format_date(pubdate) if pubdate else '',
                    'loai': result['loai'], 'gold': result['gold'],
                    'crypto': result['crypto'], 'usd': result['usd'],
                    'advice': result['advice'], 'keywords': result['keywords']
                })
        except: continue
    
    return all_news

# ============================================
# FETCH NEWSAPI
# ============================================
def fetch_newsapi_news(log):
    all_news = []
    
    for query in QUERIES:
        try:
            r = requests.get("https://newsapi.org/v2/everything", params={
                'q': query, 'language': 'en', 'sortBy': 'publishedAt',
                'pageSize': 2, 'apiKey': NEWS_API_KEY
            }, timeout=10)
            if r.status_code != 200: continue
            
            for a in r.json().get('articles', []):
                url_news = a.get('url', '')
                if url_news in log['news_sent']: continue
                
                source_name = (a.get('source', {}) or {}).get('name', 'Unknown')
                source_domain = source_name.lower().replace(' ', '')
                
                if any(b in source_domain for b in BLOCKED_SOURCES): continue
                
                title = a.get('title', '')
                description = a.get('description', '') or ''
                published = a.get('publishedAt', '')
                
                result = phan_tich_tin(title, description)
                if result is None: continue
                
                is_duplicate = False
                for existing in all_news:
                    if similarity(title, existing.get('title_en', '')) > 0.5:
                        is_duplicate = True
                        break
                
                if is_duplicate: continue
                
                log['news_sent'].append(url_news)
                
                all_news.append({
                    'title_en': title,
                    'description': description,
                    'source': source_name,
                    'date': format_date(published) if published else '',
                    'loai': result['loai'], 'gold': result['gold'],
                    'crypto': result['crypto'], 'usd': result['usd'],
                    'advice': result['advice'], 'keywords': result['keywords']
                })
            time.sleep(0.3)
        except: continue
    
    return all_news

def fetch_all_news():
    log = get_log()
    log['news_sent'] = []
    
    rss_news = fetch_rss_news(log)
    api_news = fetch_newsapi_news(log)
    
    all_news = rss_news.copy()
    for api_item in api_news:
        is_dup = False
        for existing in all_news:
            if similarity(api_item.get('title_en', ''), existing.get('title_en', '')) > 0.5:
                if any(t in api_item['source'].lower() for t in TRUSTED_SOURCES) and \
                   not any(t in existing['source'].lower() for t in TRUSTED_SOURCES):
                    all_news.remove(existing)
                    all_news.append(api_item)
                is_dup = True
                break
        if not is_dup:
            all_news.append(api_item)
    
    log['news_sent'] = log['news_sent'][-500:]
    save_log(log)
    
    priority = {'CỰC KỲ TIÊU CỰC':0, 'RẤT TIÊU CỰC':1, 'TIÊU CỰC':2, 
                'TÍCH CỰC':3, 'CỰC KỲ TÍCH CỰC':4}
    
    def sort_key(n):
        loai_text = n['loai'].split()[-1] if 'CỰC' in n['loai'] else n['loai'].split()[-1]
        p = priority.get(loai_text, 3)
        trusted = 0 if any(t in n['source'].lower() for t in TRUSTED_SOURCES) else 1
        return (p, trusted)
    
    all_news.sort(key=sort_key)
    return all_news[:MAX_NEWS]

def market_summary(news_list):
    if not news_list: return None
    neg = sum(1 for n in news_list if 'TIÊU CỰC' in n['loai'])
    pos = sum(1 for n in news_list if 'TÍCH CỰC' in n['loai'])
    
    if neg >= 5: level = "<b>RẤT CAO</b>"; advice = "⚠️ <b>ƯU TIÊN SHORT</b>"
    elif neg >= 3: level = "<b>CAO</b>"; advice = "⚠️ <b>NGHIÊNG VỀ SHORT</b>"
    elif pos >= 5: level = "<b>THẤP (TÍCH CỰC)</b>"; advice = "✅ <b>ƯU TIÊN LONG</b>"
    else: level = "<b>TRUNG BÌNH</b>"; advice = "➡️ <b>THEO DÕI THÊM</b>"
    
    all_kw = []
    for n in news_list: all_kw.extend(n['keywords'])
    top_kw = list(set(all_kw))[:6]
    
    return f"📰 <b>TỔNG QUAN THỊ TRƯỜNG</b>\n━━━━━━━━━━━━━━━━━━\n🚨 Căng thẳng {level}\n📊 Tiêu cực: {neg} | Tích cực: {pos}\n💡 {advice}\n\n📋 Số tin: {len(news_list)}\n🔑 Từ khóa: {', '.join(top_kw)}\n\n{now_str()}"

# ============================================
# EVENTS - PRE 5 NGAY + POST 1-24H + FEDWATCH
# ============================================
EVENTS = [
    {'id':'fomc_minutes_jun','name':'📋 Biên bản họp FOMC (T6)','date':'2026-06-04','time':'01:00','impact':'🟡 TRUNG BÌNH','desc':'Biên bản cuộc họp FOMC tháng 6 - hé lộ quan điểm của Fed về lãi suất.','fred':'DFF','is_fomc':True},
    {'id':'nfp_may','name':'💼 Bảng lương phi nông nghiệp (T5)','date':'2026-06-05','time':'19:30','impact':'🔴 CAO','desc':'Báo cáo việc làm - chỉ báo sức khỏe kinh tế Mỹ.','fred':'UNRATE','is_fomc':False},
    {'id':'cpi_may','name':'📊 Chỉ số CPI (T5)','date':'2026-06-11','time':'19:30','impact':'🔴 CAO','desc':'Chỉ số giá tiêu dùng - thước đo lạm phát chính.','fred':'CPIAUCSL','is_fomc':False},
    {'id':'ppi_may','name':'🏭 Chỉ số PPI (T5)','date':'2026-06-12','time':'19:30','impact':'🟡 TRUNG BÌNH','desc':'Chỉ số giá sản xuất - chỉ báo sớm của lạm phát.','fred':'PPIACO','is_fomc':False},
    {'id':'fomc_jun','name':'🏦 Quyết định lãi suất FOMC (T6)','date':'2026-06-18','time':'01:00','impact':'🔴 CAO','desc':'Quyết định lãi suất Fed - SỰ KIỆN QUAN TRỌNG NHẤT.','fred':'DFF','is_fomc':True},
    {'id':'gdp_q2','name':'📊 GDP Quý 2/2026','date':'2026-06-25','time':'19:30','impact':'🔴 CAO','desc':'Tăng trưởng kinh tế Mỹ quý 2/2026.','fred':'GDP','is_fomc':False},
    {'id':'fomc_jul','name':'🏦 Quyết định lãi suất FOMC (T7)','date':'2026-07-30','time':'01:00','impact':'🔴 CAO','desc':'Quyết định lãi suất giữa năm 2026.','fred':'DFF','is_fomc':True},
]

def check_events():
    log = get_log()
    now = datetime.now()
    today = now.date()
    msgs = []
    
    fedwatch = get_fedwatch_prediction()
    
    for ev in EVENTS:
        evd = datetime.strptime(ev['date'], '%Y-%m-%d').date()
        evdt = datetime.strptime(ev['date']+' '+ev['time'], '%Y-%m-%d %H:%M')
        days = (evd - today).days
        hours_since = (now - evdt).total_seconds()/3600 if evdt < now else -1
        
        # PRE-EVENT: 0-5 ngay
        if 0 <= days <= 5:
            key = f"pre_{ev['id']}"
            if time.time() - log['events'].get(key, 0) >= 21600:
                log['events'][key] = time.time()
                
                if days == 0: cd = f"⚠️ <b>HÔM NAY</b> lúc {ev['time']} (giờ VN)"
                elif days == 1: cd = f"📅 <b>NGÀY MAI</b> lúc {ev['time']} (giờ VN)"
                else: cd = f"📅 Còn <b>{days} ngày</b> - {ev['date']} lúc {ev['time']} (giờ VN)"
                
                fedwatch_text = ""
                if ev.get('is_fomc') and fedwatch:
                    fedwatch_text = f"\n\n📊 <b>DỰ ĐOÁN CME FEDWATCH:</b>\n{fedwatch['prediction']}\n🟢 Giữ nguyên: {fedwatch['prob_hold']:.0f}% | 📉 Giảm: {fedwatch['prob_cut']:.0f}% | 📈 Tăng: {fedwatch['prob_hike']:.0f}%\n🏦 Lãi suất hiện tại: {fedwatch['current_rate']}"
                
                msgs.append(f"📅 <b>{ev['name']}</b>\n━━━━━━━━━━━━━━━━━━\n⏰ {cd}\n⚡ Mức độ: {ev['impact']}\n📝 {ev['desc']}{fedwatch_text}\n\n📊 <b>DỮ LIỆU KINH TẾ HIỆN TẠI:</b>\n{econ_summary()}\n\n{now_str()}")
        
        # POST-EVENT: 1-24h sau
        elif days < 0 and 1 <= hours_since <= 24:
            key = f"post_{ev['id']}"
            if key not in log['events'] and fred_ok():
                v = fred_get(ev['fred'])
                if v and len(v) >= 2:
                    curr, prev = v[0]['v'], v[1]['v']
                    
                    # Xác định kết quả
                    if 'fomc' in ev['id'] and 'minutes' not in ev['id']:
                        if curr > prev:
                            ket_qua = f"📈 <b>Fed TĂNG lãi suất</b> từ {prev}% lên <b>{curr}%</b>"
                            tac_dong = "🦅 <b>HAWKISH</b> - Thắt chặt tiền tệ"
                        elif curr < prev:
                            ket_qua = f"📉 <b>Fed GIẢM lãi suất</b> từ {prev}% xuống <b>{curr}%</b>"
                            tac_dong = "🕊️ <b>DOVISH</b> - Nới lỏng tiền tệ"
                        else:
                            ket_qua = f"➡️ <b>Fed GIỮ NGUYÊN lãi suất</b> ở mức <b>{curr}%</b>"
                            tac_dong = "➡️ <b>TRUNG LẬP</b> - Chờ đợi thêm dữ liệu"
                    elif 'gdp' in ev['id']:
                        pct = round((curr-prev)/prev*100, 2)
                        if curr > prev:
                            ket_qua = f"📈 <b>GDP TĂNG {pct}%</b> lên ${curr:,.0f}B"
                            tac_dong = "✅ Tích cực - Kinh tế tăng trưởng"
                        else:
                            ket_qua = f"📉 <b>GDP GIẢM {pct}%</b> xuống ${curr:,.0f}B"
                            tac_dong = "⚠️ Tiêu cực - Kinh tế suy giảm"
                    elif 'nfp' in ev['id']:
                        if curr > prev:
                            ket_qua = f"📈 <b>Thất nghiệp TĂNG</b> lên <b>{curr}%</b>"
                            tac_dong = "⚠️ Tiêu cực - Thị trường lao động yếu đi"
                        elif curr < prev:
                            ket_qua = f"📉 <b>Thất nghiệp GIẢM</b> xuống <b>{curr}%</b>"
                            tac_dong = "✅ Tích cực - Thị trường lao động mạnh lên"
                        else:
                            ket_qua = f"➡️ <b>Thất nghiệp KHÔNG ĐỔI</b> ở mức <b>{curr}%</b>"
                            tac_dong = "➡️ Ổn định"
                    elif 'cpi' in ev['id']:
                        pct = round((curr-prev)/prev*100, 1)
                        if curr > prev:
                            ket_qua = f"📈 <b>LẠM PHÁT TĂNG {pct}%</b> - CPI: <b>{curr}</b>"
                            tac_dong = "⚠️ Tiêu cực - Lạm phát nóng lên, có thể Fed sẽ hawkish"
                        elif curr < prev:
                            ket_qua = f"📉 <b>LẠM PHÁT GIẢM {abs(pct)}%</b> - CPI: <b>{curr}</b>"
                            tac_dong = "✅ Tích cực - Lạm phát hạ nhiệt, có thể Fed sẽ dovish"
                        else:
                            ket_qua = f"➡️ <b>CPI KHÔNG ĐỔI</b> ở mức <b>{curr}</b>"
                            tac_dong = "➡️ Ổn định"
                    elif 'ppi' in ev['id']:
                        pct = round((curr-prev)/prev*100, 1)
                        if curr > prev:
                            ket_qua = f"📈 <b>PPI TĂNG {pct}%</b> - PPI: <b>{curr}</b>"
                            tac_dong = "⚠️ Áp lực giá đầu vào tăng"
                        elif curr < prev:
                            ket_qua = f"📉 <b>PPI GIẢM {abs(pct)}%</b> - PPI: <b>{curr}</b>"
                            tac_dong = "✅ Áp lực giá đầu vào giảm"
                        else:
                            ket_qua = f"➡️ <b>PPI KHÔNG ĐỔI</b> ở mức <b>{curr}</b>"
                            tac_dong = "➡️ Ổn định"
                    else:
                        ket_qua = f"<b>{curr}</b> (trước: {prev})"
                        tac_dong = "Đã cập nhật"
                    
                    log['events'][key] = time.time()
                    msgs.append(f"✅ <b>{ev['name']} - KẾT QUẢ THỰC TẾ</b>\n━━━━━━━━━━━━━━━━━━\n⏰ Đã diễn ra: {ev['date']} lúc {ev['time']} (giờ VN)\n\n📊 <b>KẾT QUẢ:</b>\n{ket_qua}\n\n🎤 <b>Đánh giá:</b>\n{tac_dong}\n\n📊 <b>DỮ LIỆU KINH TẾ HIỆN TẠI:</b>\n{econ_summary()}\n\n{now_str()}")
    
    save_log(log)
    return msgs

# === MAIN ===
print("="*60)
print("BOT TIN TUC PRO V5 - SONG NGU ANH-VIET")
print("="*60)

while True:
    try:
        s = get_state()
        now = time.time()
        
        if not s['started'] or (now - s['last_update'] >= CHU_KY):
            set_state(started=True, last_update=now)
            if 'started_ever' not in s: set_state(started_ever=True)
            
            news = fetch_all_news()
            
            label = "đã khởi động" if s.get('started_ever') else "cập nhật 6h"
            rss_count = sum(1 for n in news if n['source'] in ['Reuters', 'CNBC', 'CoinDesk', 'Cointelegraph', 'MarketWatch'])
            
            msg = f"📰 <b>Bot tin tức {label}!</b>\n━━━━━━━━━━━━━━━━━━\n📡 FRED: {'✅' if fred_ok() else '⏳'}\n📡 NewsAPI + RSS: ✅ {rss_count} tin RSS\n\n📊 <b>DỮ LIỆU KINH TẾ:</b>\n{econ_summary()}\n\n📋 Phát hiện <b>{len(news)} tin</b> quan trọng\n\n{now_str()}"
            gui(msg)
            
            if news:
                summary = market_summary(news)
                if summary: gui(summary)
                
                for n in news:
                    # Tạo tóm tắt tiếng Việt
                    tom_tat = tom_tat_tieng_viet(n.get('title_en', ''), n.get('description', ''), n['keywords'])
                    
                    date_line = f"\n📅 {n['date']}" if n['date'] else ""
                    
                    msg = f"📰 TIN TỨC {n['loai']}\n━━━━━━━━━━━━━━━━━━\n"
                    msg += f"🇬🇧 <b>{n['title_en']}</b>\n\n"
                    msg += f"🇻🇳 {tom_tat}\n\n"
                    msg += f"📡 Nguồn: {n['source']}{date_line}\n"
                    msg += f"🔑 Từ khóa: <b>{', '.join(n['keywords'])}</b>\n\n"
                    msg += f"🏦 <b>Dự báo thị trường:</b>\n{n['gold']}\n{n['crypto']}\n{n['usd']}\n\n"
                    msg += f"💡 Khuyến nghị: {n['advice']}\n\n{now_str()}"
                    gui(msg)
                    time.sleep(1)
            
            for m in check_events():
                gui(m)
            
            try:
                r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
                d = r.json()['data'][0]
                v = int(d['value']); c = d['value_classification']
                i = "😱" if v<=25 else "😟" if v<=40 else "😐" if v<=60 else "😊" if v<=75 else "🤤"
                gui(f"{i} <b>Chỉ số Sợ hãi & Tham lam:</b> {v}/100 ({c})")
            except: pass
        
        time.sleep(60)
    except KeyboardInterrupt: break
    except Exception as e:
        print(f"Lỗi: {e}")
        time.sleep(30)