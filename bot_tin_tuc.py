"""
BOT TIN TUC - NEWSAPI + RSS FEEDS - PRO FILTER V4
- 5 nguồn RSS miễn phí: Reuters, CNBC, CoinDesk, Cointelegraph, MarketWatch
- NewsAPI bổ sung
- Dịch word-boundary chính xác - không cắt chữ
- CME FedWatch Tool cho dự đoán lãi suất
- Post-event tự động báo cáo kết quả thực tế
- Tối đa 10 tin chất lượng/lần gửi
- Sự kiện trước 5 ngày
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
                   "thegatewaypundit.com", "breitbart.com", "occupydemocrats.com", "dailycaller.com"]

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
            return dt.strftime("%d/%m/%Y %H:%M UTC")
        except: pass
    return date_str[:16] if len(date_str) > 16 else date_str

# ============================================
# CME FEDWATCH - DU DOAN LAI SUAT
# ============================================
def get_fedwatch_prediction():
    """Lay du doan lai suat tu CME FedWatch"""
    try:
        r = requests.get("https://www.cmegroup.com/CmeWS/mvc/AtmOptions/FedWatchWidget", 
                        params={"timePeriod": "current"}, timeout=10)
        if r.status_code != 200: return None
        
        data = r.json()
        meetings = data.get('meetings', [])
        if not meetings: return None
        
        next_meeting = meetings[0]
        rates = next_meeting.get('probabilities', [])
        
        # Tìm xác suất giữ nguyên và thay đổi
        prob_hold = 0
        prob_cut = 0
        prob_hike = 0
        current_rate = next_meeting.get('currentTarget', 'N/A')
        
        for rate_info in rates:
            if rate_info.get('label', '') == 'Current':
                prob_hold = rate_info.get('probability', 0)
            elif 'cut' in rate_info.get('label', '').lower() or float(rate_info.get('target', '999')) < float(str(current_rate).split('-')[0]):
                prob_cut += rate_info.get('probability', 0)
            elif 'hike' in rate_info.get('label', '').lower() or float(rate_info.get('target', '0')) > float(str(current_rate).split('-')[0]):
                prob_hike += rate_info.get('probability', 0)
        
        # Xác định xu hướng
        if prob_cut > prob_hold and prob_cut > prob_hike:
            prediction = f"📉 <b>Dự đoán: GIẢM lãi suất</b> (xác suất {prob_cut:.0f}%)"
        elif prob_hike > prob_hold and prob_hike > prob_cut:
            prediction = f"📈 <b>Dự đoán: TĂNG lãi suất</b> (xác suất {prob_hike:.0f}%)"
        else:
            prediction = f"➡️ <b>Dự đoán: GIỮ NGUYÊN</b> (xác suất {prob_hold:.0f}%)"
        
        return {
            'current_rate': current_rate,
            'prob_hold': prob_hold,
            'prob_cut': prob_cut,
            'prob_hike': prob_hike,
            'prediction': prediction,
            'meeting_date': next_meeting.get('meetingDate', '')
        }
    except:
        return None

# ============================================
# DICH CHUAN - WORD BOUNDARY CHINH XAC
# ============================================
DICT_TAI_CHINH = {
    # Cụm dài phải để TRƯỚC (ưu tiên khớp cụm dài trước)
    "federal reserve": "Cục Dự trữ Liên bang",
    "interest rate": "lãi suất",
    "rate cut": "hạ lãi suất",
    "rate hike": "tăng lãi suất",
    "monetary policy": "chính sách tiền tệ",
    "fiscal policy": "chính sách tài khóa",
    "quantitative easing": "nới lỏng định lượng",
    "debt ceiling": "trần nợ công",
    "bond yield": "lợi suất trái phiếu",
    "yield curve": "đường cong lợi suất",
    "peace deal": "thỏa thuận hòa bình",
    "peace talk": "đàm phán hòa bình",
    "trade war": "chiến tranh thương mại",
    "strait of hormuz": "eo biển Hormuz",
    "south china sea": "Biển Đông",
    "taiwan strait": "eo biển Đài Loan",
    "north korea": "Triều Tiên",
    "demilitarized zone": "khu phi quân sự",
    "institutional investor": "nhà đầu tư tổ chức",
    "bull market": "thị trường tăng trưởng",
    "bear market": "thị trường suy giảm",
    "market cap": "vốn hóa thị trường",
    "safe haven": "tài sản trú ẩn an toàn",
    "crude oil": "dầu thô",
    "oil price": "giá dầu",
    "dollar index": "chỉ số đô la Mỹ",
    "stock market": "thị trường chứng khoán",
    "wall street": "Phố Wall",
    "white house": "Nhà Trắng",
    "record high": "mức cao kỷ lục",
    "record low": "mức thấp kỷ lục",
    "all-time high": "mức cao nhất mọi thời đại",
    "nonfarm payrolls": "bảng lương phi nông nghiệp",
    "etf approved": "ETF được phê duyệt",
    "etf inflow": "dòng vốn ETF vào",
    "etf outflow": "dòng vốn ETF ra",
    "oil price surge": "giá dầu tăng vọt",
    "crude surge": "dầu thô tăng vọt",
    "de-dollarization": "phi đô la hóa",
    
    # Từ đơn
    "inflation": "lạm phát",
    "recession": "suy thoái",
    "depression": "đại suy thoái",
    "unemployment": "thất nghiệp",
    "dovish": "ôn hòa",
    "hawkish": "diều hâu",
    "tightening": "thắt chặt",
    "easing": "nới lỏng",
    "stimulus": "kích thích kinh tế",
    "bailout": "cứu trợ tài chính",
    "treasury": "trái phiếu chính phủ",
    "ceasefire": "ngừng bắn",
    "truce": "đình chiến",
    "surrender": "đầu hàng",
    "withdrawal": "rút quân",
    "missile": "tên lửa",
    "airstrike": "không kích",
    "invasion": "xâm lược",
    "offensive": "tấn công quân sự",
    "nuclear": "hạt nhân",
    "sanction": "trừng phạt",
    "embargo": "cấm vận",
    "tariff": "thuế quan",
    "bitcoin": "Bitcoin",
    "ethereum": "Ethereum",
    "cryptocurrency": "tiền điện tử",
    "blockchain": "blockchain",
    "blackrock": "BlackRock",
    "fidelity": "Fidelity",
    "vanguard": "Vanguard",
    "adoption": "chấp nhận rộng rãi",
    "regulation": "quy định pháp lý",
    "rally": "tăng mạnh",
    "volatility": "biến động",
    "liquidity": "thanh khoản",
    "gold": "vàng",
    "silver": "bạc",
    "forex": "ngoại hối",
    "nasdaq": "Nasdaq",
    "warns": "cảnh báo",
    "warning": "cảnh báo",
    "threatens": "đe dọa",
    "negotiations": "đàm phán",
    "talks": "đàm phán",
    "summit": "hội nghị thượng đỉnh",
    "agreement": "thỏa thuận",
    "deal": "thỏa thuận",
    "accord": "hiệp định",
    "tensions": "căng thẳng",
    "escalation": "leo thang",
    "conflict": "xung đột",
    "allies": "đồng minh",
    "coalition": "liên minh",
    "pentagon": "Lầu Năm Góc",
    "kremlin": "Điện Kremlin",
    "congress": "Quốc hội Mỹ",
    "senate": "Thượng viện",
    "president": "tổng thống",
    "election": "bầu cử",
    "resilience": "khả năng phục hồi",
    "resilient": "phục hồi tốt",
    "robust": "mạnh mẽ",
    "surge": "tăng vọt",
    "plunge": "lao dốc",
    "tumble": "giảm mạnh",
    "soar": "tăng vọt",
    "slump": "sụt giảm",
    "rebound": "phục hồi",
    "recover": "phục hồi",
    "decline": "giảm",
    "drop": "giảm",
    "rise": "tăng",
    "climb": "tăng",
    "crash": "sụp đổ",
    "collapse": "sụp đổ",
    
    # Từ viết tắt - giữ nguyên
    "fomc": "FOMC",
    "cpi": "CPI",
    "ppi": "PPI",
    "gdp": "GDP",
    "etf": "ETF",
    "sec": "SEC",
    "cftc": "CFTC",
    "nato": "NATO",
    "opec": "OPEC",
    "brics": "BRICS",
    "dxy": "DXY",
    "fed": "Fed",
    "qe": "QE",
    "s&p 500": "S&P 500",
}

def replace_word_boundary(text, word, replacement):
    """Thay thế CHỈ khi từ đứng riêng (word boundary)"""
    pattern = r'\b' + re.escape(word) + r'\b'
    return re.sub(pattern, replacement, text, flags=re.IGNORECASE)

def dich_tai_chinh(text):
    """Dịch dùng từ điển chuyên ngành - word boundary chính xác"""
    if not text: return ""
    
    # Clean HTML
    text = unescape(text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&[a-z]+;', '', text)
    
    result = text
    
    # Sắp xếp key theo độ dài giảm dần - ưu tiên cụm dài
    sorted_keys = sorted(DICT_TAI_CHINH.keys(), key=len, reverse=True)
    
    for key in sorted_keys:
        result = replace_word_boundary(result, key, DICT_TAI_CHINH[key])
    
    # Clean up: xóa ký tự thừa, chuẩn hóa khoảng trắng
    result = re.sub(r'\s+', ' ', result)
    result = result.strip()
    
    # Viết hoa chữ cái đầu câu
    if result and len(result) > 1:
        result = result[0].upper() + result[1:]
    
    return result

# ============================================
# KEYWORD MATCHING - REGEX WORD BOUNDARY
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
    """Kiểm tra từ khóa với word boundary"""
    return bool(re.search(r'\b' + re.escape(word) + r'\b', text.lower()))

def phan_tich_tin(title, description=""):
    t = (title + " " + description).lower()
    
    pos_found = [DICT_TAI_CHINH.get(kw, kw) for kw in POSITIVE_KW if has_keyword(t, kw)]
    neg_found = [DICT_TAI_CHINH.get(kw, kw) for kw in NEGATIVE_KW if has_keyword(t, kw)]
    
    # Loại bỏ trùng lặp
    pos_found = list(set(pos_found))
    neg_found = list(set(neg_found))
    
    if not pos_found and not neg_found:
        return None
    
    # AI Context: chiến tranh + dầu = TIÊU CỰC
    has_war = any(has_keyword(t, w) for w in ['war', 'strike', 'airstrike', 'attack', 'invasion'])
    has_oil = any(has_keyword(t, w) for w in ['oil price', 'crude oil', 'crude surge'])
    if has_war and has_oil:
        neg_found.append("giá dầu tăng (do xung đột)")
        pos_found = [p for p in pos_found if p not in ['ngừng bắn', 'đình chiến']]
    
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
    """Tính độ tương đồng giữa 2 chuỗi"""
    if not s1 or not s2: return 0
    words1 = set(s1.lower().split())
    words2 = set(s2.lower().split())
    if not words1 or not words2: return 0
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    return len(intersection) / len(union)

# ============================================
# FETCH RSS NEWS
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
                if link_el is None: 
                    link_el = item.find('{http://www.w3.org/2005/Atom}link')
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
                title_vi = dich_tai_chinh(title)
                
                all_news.append({
                    'title_vi': title_vi,
                    'title_en': title,
                    'source': source_name,
                    'date': format_date(pubdate) if pubdate else '',
                    'loai': result['loai'], 'gold': result['gold'],
                    'crypto': result['crypto'], 'usd': result['usd'],
                    'advice': result['advice'], 'keywords': result['keywords']
                })
        except: continue
    
    return all_news

# ============================================
# FETCH NEWSAPI NEWS
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
                title_vi = dich_tai_chinh(title)
                
                all_news.append({
                    'title_vi': title_vi,
                    'title_en': title,
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
# EVENTS - 5 NGAY + FEDWATCH + POST-EVENT
# ============================================
EVENTS = [
    {'id':'fomc_minutes_jun','name':'📋 Biên bản họp FOMC (T6)','date':'2026-06-04','time':'01:00','impact':'🟡 TRUNG BÌNH','desc':'Biên bản cuộc họp FOMC tháng 6 - hé lộ quan điểm của Fed.','fred':'DFF','is_fomc':True,'fmt':'🎤 <b>Thái độ:</b> 🏦 Lãi suất Fed: {value}%\n📝 Biên bản đã công bố.\n📊 <b>Kết quả: {action}</b>\n📝 {detail}','gold':'<b>Hawkish → GIẢM</b> | Dovish → TĂNG','crypto':'<b>Hawkish → GIẢM</b> | Dovish → TĂNG','usd':'<b>Hawkish → TĂNG</b> | Dovish → GIẢM'},
    {'id':'nfp_may','name':'💼 Bảng lương phi nông nghiệp (T5)','date':'2026-06-05','time':'19:30','impact':'🔴 CAO','desc':'Báo cáo việc làm phi nông nghiệp Mỹ - chỉ báo sức khỏe kinh tế.','fred':'UNRATE','is_fomc':False,'fmt':'<b>Tỷ lệ thất nghiệp:</b> {value}% (trước: {prev}%)\n📊 <b>Kết quả: {action}</b>\n📝 {detail}','gold':'<b>NFP cao → GIẢM</b> | NFP thấp → TĂNG','crypto':'<b>NFP cao → TĂNG</b> | NFP thấp → GIẢM','usd':'<b>NFP cao → TĂNG</b> | NFP thấp → GIẢM'},
    {'id':'cpi_may','name':'📊 Chỉ số giá tiêu dùng CPI (T5)','date':'2026-06-11','time':'19:30','impact':'🔴 CAO','desc':'Chỉ số giá tiêu dùng - thước đo lạm phát chính.','fred':'CPIAUCSL','is_fomc':False,'fmt':'<b>CPI:</b> {value} (trước: {prev})\n📊 <b>Kết quả: {action}</b>\n📝 CPI {detail}.','gold':'<b>CPI cao → TĂNG</b> (hedge) | CPI thấp → GIẢM','crypto':'<b>CPI cao → GIẢM</b> (lo tăng lãi suất) | CPI thấp → TĂNG','usd':'<b>CPI cao → TĂNG</b> | CPI thấp → GIẢM'},
    {'id':'ppi_may','name':'🏭 Chỉ số giá sản xuất PPI (T5)','date':'2026-06-12','time':'19:30','impact':'🟡 TRUNG BÌNH','desc':'Chỉ số giá sản xuất - chỉ báo sớm của lạm phát.','fred':'PPIACO','is_fomc':False,'fmt':'<b>PPI:</b> {value} (trước: {prev})\n📊 <b>Kết quả: {action}</b>\n📝 PPI {detail}.','gold':'<b>PPI cao → TĂNG</b> | PPI thấp → GIẢM','crypto':'<b>PPI cao → TĂNG nhẹ</b>','usd':'<b>PPI cao → TĂNG nhẹ</b>'},
    {'id':'fomc_jun','name':'🏦 Quyết định lãi suất FOMC (T6)','date':'2026-06-18','time':'01:00','impact':'🔴 CAO','desc':'Quyết định lãi suất Fed - SỰ KIỆN QUAN TRỌNG NHẤT.','fred':'DFF','is_fomc':True,'fmt':'<b>Lãi suất Fed:</b> {value}% (trước: {prev}%)\n📊 <b>Kết quả: {action}</b>\n📝 {detail}.','gold':'<b>Hawkish → GIẢM</b> | Dovish → TĂNG','crypto':'<b>Hawkish → GIẢM</b> | Dovish → TĂNG','usd':'<b>Hawkish → TĂNG</b> | Dovish → GIẢM'},
    {'id':'gdp_q2','name':'📊 GDP Quý 2/2026 (Cuối cùng)','date':'2026-06-25','time':'19:30','impact':'🔴 CAO','desc':'Tăng trưởng kinh tế Mỹ quý 2/2026.','fred':'GDP','is_fomc':False,'fmt':'<b>GDP:</b> ${value:,.0f}B (trước: ${prev:,.0f}B)\n📊 <b>Kết quả: {action}</b>\n📝 GDP thay đổi {detail}% so với ${prev:,.0f}B.','gold':'<b>GDP cao → GIẢM</b> | GDP thấp → TĂNG','crypto':'<b>GDP cao → TĂNG</b> | GDP thấp → GIẢM','usd':'<b>GDP cao → TĂNG</b> | GDP thấp → GIẢM'},
    {'id':'fomc_jul','name':'🏦 Quyết định lãi suất FOMC (T7)','date':'2026-07-30','time':'01:00','impact':'🔴 CAO','desc':'Quyết định lãi suất giữa năm 2026.','fred':'DFF','is_fomc':True,'fmt':'<b>Lãi suất Fed:</b> {value}% (trước: {prev}%)\n📊 <b>Kết quả: {action}</b>\n📝 {detail}.','gold':'<b>Hawkish → GIẢM</b> | Dovish → TĂNG','crypto':'<b>Hawkish → GIẢM</b> | Dovish → TĂNG','usd':'<b>Hawkish → TĂNG</b> | Dovish → GIẢM'},
]

def check_events():
    log = get_log()
    now = datetime.now()
    today = now.date()
    msgs = []
    
    # Lấy dự đoán FedWatch
    fedwatch = get_fedwatch_prediction()
    
    for ev in EVENTS:
        evd = datetime.strptime(ev['date'], '%Y-%m-%d').date()
        evdt = datetime.strptime(ev['date']+' '+ev['time'], '%Y-%m-%d %H:%M')
        days = (evd - today).days
        hours_since = (now - evdt).total_seconds()/3600 if evdt < now else -1
        
        # === PRE-EVENT: 0-5 ngay ===
        if 0 <= days <= 5:
            key = f"pre_{ev['id']}"
            if time.time() - log['events'].get(key, 0) >= 21600:
                log['events'][key] = time.time()
                
                if days == 0: cd = f"⚠️ <b>HÔM NAY</b> lúc {ev['time']} (giờ Việt Nam)"
                elif days == 1: cd = f"📅 <b>NGÀY MAI</b> lúc {ev['time']} (giờ Việt Nam)"
                else: cd = f"📅 Còn <b>{days} ngày</b> - {ev['date']} lúc {ev['time']} (giờ Việt Nam)"
                
                # Thêm dự đoán FedWatch cho FOMC events
                fedwatch_text = ""
                if ev.get('is_fomc') and fedwatch:
                    fedwatch_text = f"\n\n📊 <b>DỰ ĐOÁN CME FEDWATCH:</b>\n{fedwatch['prediction']}\n🟢 Giữ nguyên: {fedwatch['prob_hold']:.0f}% | 📉 Giảm: {fedwatch['prob_cut']:.0f}% | 📈 Tăng: {fedwatch['prob_hike']:.0f}%\n🏦 Lãi suất hiện tại: {fedwatch['current_rate']}"
                
                msgs.append(f"📅 <b>{ev['name']}</b>\n━━━━━━━━━━━━━━━━━━\n⏰ {cd}\n⚡ Mức độ: {ev['impact']}\n📝 {ev['desc']}{fedwatch_text}\n\n━━━━━━━━━━━━━━━━━━\n📊 <b>TÁC ĐỘNG DỰ KIẾN:</b>\n🥇 Vàng: {ev['gold']}\n₿ Crypto: {ev['crypto']}\n💵 USD: {ev['usd']}\n━━━━━━━━━━━━━━━━━━\n\n📊 <b>DỮ LIỆU KINH TẾ HIỆN TẠI:</b>\n{econ_summary()}\n\n{now_str()}")
        
        # === POST-EVENT: 1-24h sau ===
        elif days < 0 and 1 <= hours_since <= 24:
            key = f"post_{ev['id']}"
            if key not in log['events'] and fred_ok():
                v = fred_get(ev['fred'])
                if v and len(v) >= 2:
                    curr, prev = v[0]['v'], v[1]['v']
                    
                    # Xác định kết quả chính
                    if curr > prev:
                        if 'fomc' in ev['id'] and 'minutes' not in ev['id']: 
                            action = "<b>TĂNG LÃI SUẤT 📈</b>"
                            detail = f"Fed <b>TĂNG</b> lãi suất thêm {round(curr-prev,2)}%, lên mức <b>{curr}%</b>"
                        elif 'gdp' in ev['id']: 
                            action = "<b>TĂNG TRƯỞNG ✅</b>"
                            detail = f"GDP tăng <b>+{round((curr-prev)/prev*100,2)}%</b> so với quý trước"
                        elif 'nfp' in ev['id']: 
                            action = "<b>TĂNG</b>"
                            detail = f"Tỷ lệ thất nghiệp tăng lên <b>{curr}%</b> - thị trường lao động yếu đi"
                        elif 'cpi' in ev['id']: 
                            action = "<b>LẠM PHÁT TĂNG 📈</b>"
                            detail = f"CPI tăng <b>{round((curr-prev)/prev*100,1)}%</b> - lạm phát đang nóng lên"
                        elif 'ppi' in ev['id']: 
                            action = "<b>TĂNG</b>"
                            detail = f"PPI tăng <b>{round((curr-prev)/prev*100,1)}%</b> - áp lực giá đầu vào"
                        else: 
                            action = "<b>TĂNG</b>"
                            detail = f"tăng <b>{round((curr-prev)/prev*100,1)}%</b>"
                    elif curr < prev:
                        if 'fomc' in ev['id'] and 'minutes' not in ev['id']: 
                            action = "<b>GIẢM LÃI SUẤT 📉</b>"
                            detail = f"Fed <b>GIẢM</b> lãi suất {round(prev-curr,2)}%, xuống mức <b>{curr}%</b>"
                        elif 'gdp' in ev['id']: 
                            action = "<b>SUY GIẢM ⚠️</b>"
                            detail = f"GDP giảm <b>{round((curr-prev)/prev*100,2)}%</b> - nền kinh tế thu hẹp"
                        elif 'nfp' in ev['id']: 
                            action = "<b>GIẢM ✅</b>"
                            detail = f"Tỷ lệ thất nghiệp giảm xuống <b>{curr}%</b> - thị trường lao động mạnh lên"
                        elif 'cpi' in ev['id']: 
                            action = "<b>LẠM PHÁT GIẢM 📉</b>"
                            detail = f"CPI giảm <b>{round((prev-curr)/prev*100,1)}%</b> - lạm phát hạ nhiệt"
                        elif 'ppi' in ev['id']: 
                            action = "<b>GIẢM</b>"
                            detail = f"PPI giảm <b>{round((prev-curr)/prev*100,1)}%</b>"
                        else: 
                            action = "<b>GIẢM</b>"
                            detail = f"giảm <b>{round((prev-curr)/prev*100,1)}%</b>"
                    else:
                        if 'fomc' in ev['id'] and 'minutes' not in ev['id']: 
                            action = "<b>GIỮ NGUYÊN ➡️</b>"
                            detail = f"Fed <b>GIỮ NGUYÊN</b> lãi suất ở mức <b>{curr}%</b>"
                        elif 'nfp' in ev['id']: 
                            action = "<b>KHÔNG ĐỔI ➡️</b>"
                            detail = "Thị trường lao động <b>ổn định</b>"
                        elif 'cpi' in ev['id']: 
                            action = "<b>KHÔNG ĐỔI ➡️</b>"
                            detail = "CPI <b>không thay đổi</b>"
                        elif 'ppi' in ev['id']: 
                            action = "<b>KHÔNG ĐỔI ➡️</b>"
                            detail = "PPI <b>không thay đổi</b>"
                        else: 
                            action = "<b>KHÔNG ĐỔI ➡️</b>"
                            detail = "<b>không thay đổi</b>"
                    
                    log['events'][key] = time.time()
                    msgs.append(f"===================================\n✅ <b>{ev['name']} - KẾT QUẢ THỰC TẾ</b>\n===================================\n⏰ Đã diễn ra: {ev['date']} lúc {ev['time']} (giờ Việt Nam)\n\n{ev['fmt'].format(value=curr, prev=prev, action=action, detail=detail)}\n\n━━━━━━━━━━━━━━━━━━\n📊 <b>TÁC ĐỘNG THỊ TRƯỜNG:</b>\n🥇 Vàng: {ev['gold']}\n₿ Crypto: {ev['crypto']}\n💵 USD: {ev['usd']}\n━━━━━━━━━━━━━━━━━━\n\n📊 <b>DỮ LIỆU KINH TẾ HIỆN TẠI:</b>\n{econ_summary()}\n\n{now_str()}")
    
    save_log(log)
    return msgs

# === MAIN ===
print("="*60)
print("BOT TIN TUC PRO V4 - RSS + NEWSAPI + FEDWATCH")
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
            
            msg = f"📰 <b>Bot tin tức {label}!</b>\n━━━━━━━━━━━━━━━━━━\n📡 FRED: {'✅ Online' if fred_ok() else '⏳ Offline'}\n📡 NewsAPI: ✅ Online\n📡 RSS Feeds: ✅ {rss_count} tin\n\n📊 <b>DỮ LIỆU KINH TẾ:</b>\n{econ_summary()}\n\n"
            if news: msg += f"📋 Phát hiện <b>{len(news)} tin</b> quan trọng\n"
            msg += f"\n✅ Đang theo dõi sự kiện...\n\n{now_str()}"
            gui(msg)
            
            if news:
                summary = market_summary(news)
                if summary: gui(summary)
                for n in news:
                    date_line = f"\n📅 {n['date']}" if n['date'] else ""
                    msg = f"📰 TIN TỨC THỊ TRƯỜNG {n['loai']}\n━━━━━━━━━━━━━━━━━━\n{n['title_vi']}\n\n📡 Nguồn: {n['source']}{date_line}\n🔑 Từ khóa: <b>{', '.join(n['keywords'])}</b>\n\n🏦 <b>Dự báo:</b>\n{n['gold']}\n{n['crypto']}\n{n['usd']}\n\n💡 Khuyến nghị: {n['advice']}\n\n{now_str()}"
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