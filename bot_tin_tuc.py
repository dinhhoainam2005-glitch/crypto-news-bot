"""
BOT TIN TUC V2 - RSS + CMC + FRED
- 5 nguồn RSS: Reuters, CNBC, CoinDesk, Cointelegraph, MarketWatch
- Dominance + Fear & Greed: CoinMarketCap API
- Sự kiện kinh tế: FRED API (FOMC, CPI, NFP, GDP, PPI)
- Dịch tiếng Việt: Google Translate + từ điển tài chính
- Context analysis: hiểu ngữ cảnh thị trường
- Format sự kiện chuẩn: Tác động + Chiến lược + Hành động
- Cập nhật mỗi 6 giờ
"""
import requests
import time
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from html import unescape

# ============================================
# CONFIG
# ============================================
TOKEN = os.getenv("TELEGRAM_TOKEN", "8893995280:AAF9XwWAm9QgPkwmDrhZdY6UQ4zfySooWpk")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "518284897")
FRED_API_KEY = os.getenv("FRED_API_KEY", "ff3e122af2b2c0a433606476fc6dc5fb")
CMC_API_KEY = "ba07282bfe644708a9f42be12a33acf6"

CHU_KY = 21600  # 6 giờ
MAX_NEWS = 10
DATA_DIR = "data"
STATE_FILE = f"{DATA_DIR}/state_news.json"
LOG_FILE = f"{DATA_DIR}/log_news.json"

# Nguồn RSS đáng tin cậy
RSS_FEEDS = [
    ("https://feeds.reuters.com/reuters/businessNews", "Reuters"),
    ("https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01", "CNBC"),
    ("https://www.coindesk.com/arc/outboundfeeds/news/", "CoinDesk"),
    ("https://cointelegraph.com/rss", "Cointelegraph"),
    ("https://feeds.marketwatch.com/marketwatch/topstories", "MarketWatch"),
]

# Nguồn tin không uy tín - chặn
BLOCKED_SOURCES = [
    "naturalnews.com", "beforeitsnews.com", "infowars.com", "zerohedge.com",
    "foxnews.com", "newsmax.com", "oann.com"
]

# Nguồn tin uy tín - ưu tiên
TRUSTED_SOURCES = [
    "reuters.com", "bloomberg.com", "cnbc.com", "wsj.com", "ft.com",
    "coindesk.com", "cointelegraph.com", "marketwatch.com",
    "investing.com", "forexlive.com", "apnews.com", "bbc.com"
]

# Từ khóa không liên quan thị trường - bỏ qua
NON_MARKET_KW = [
    "generational war", "culture war", "boomer", "gen z",
    "tiktok", "influencer", "celebrity", "royal family",
    "sports", "gaming", "movie", "netflix", "disney",
    "grammy", "oscar", "emmy", "super bowl", "world cup", "nfl", "nba"
]

os.makedirs(DATA_DIR, exist_ok=True)

# ============================================
# TIỆN ÍCH
# ============================================
def get_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f: return json.load(f)
    return {"started": False, "last_update": 0}

def set_state(**kv):
    s = get_state()
    s.update(kv)
    with open(STATE_FILE, 'w') as f: json.dump(s, f)

def get_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f: return json.load(f)
    return {"events": {}, "news_sent": []}

def save_log(data):
    with open(LOG_FILE, 'w') as f: json.dump(data, f, ensure_ascii=False, indent=2)

def gui(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
    except:
        pass

def now_str():
    n = datetime.now()
    return (
        f"🕐 {n.strftime('%H:%M')} (Asia) | "
        f"{(n - timedelta(hours=5)).strftime('%H:%M')} (EU) | "
        f"{(n - timedelta(hours=11)).strftime('%H:%M')} (US) | "
        f"{n.strftime('%d/%m/%Y')}"
    )

def clean_html(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    return unescape(text).strip()

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
        except:
            pass
    return date_str[:16] if len(date_str) > 16 else date_str

# ============================================
# FRED API - DỮ LIỆU KINH TẾ MỸ
# ============================================
def fred_get(series_id):
    try:
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": series_id,
            "api_key": FRED_API_KEY,
            "file_type": "json",
            "limit": 2,
            "sort_order": "desc"
        }
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            observations = r.json().get('observations', [])
            result = []
            for obs in observations:
                if obs.get('value', '.') != '.':
                    result.append({
                        'date': obs['date'],
                        'value': float(obs['value'])
                    })
            return result
    except:
        pass
    return None

def econ_summary():
    """Tóm tắt dữ liệu kinh tế Mỹ"""
    indicators = [
        ('DFF', '<b>Lãi suất Fed:</b> {}%'),
        ('CPIAUCSL', '<b>CPI:</b> {}'),
        ('UNRATE', '<b>Thất nghiệp:</b> {}%'),
        ('GDP', '<b>GDP:</b> ${:,.0f}B'),
        ('PPIACO', '<b>PPI:</b> {}'),
    ]
    parts = []
    for sid, fmt in indicators:
        data = fred_get(sid)
        if data:
            parts.append(fmt.format(data[0]['value']))
    return " | ".join(parts) if parts else "Đang tải..."

# ============================================
# COINMARKETCAP - DOMINANCE + FEAR & GREED
# ============================================
def get_dominance():
    """Lấy BTC.D, ETH.D, SOL.D và Fear & Greed từ CMC"""
    try:
        headers = {'X-CMC_PRO_API_KEY': CMC_API_KEY}
        
        # Global metrics
        r = requests.get(
            "https://pro-api.coinmarketcap.com/v1/global-metrics/quotes/latest",
            headers=headers,
            timeout=10
        )
        if r.status_code != 200:
            return None
        
        data = r.json()['data']
        btc_d = round(data['btc_dominance'], 1)
        eth_d = round(data['eth_dominance'], 1)
        total_mcap = data['quote']['USD']['total_market_cap']
        
        # Fear & Greed từ CMC
        fng_value = data.get('fear_greed_value')
        fng_text = data.get('fear_greed_classification', '')
        
        # Quote cho BTC, ETH, SOL
        r2 = requests.get(
            "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest",
            params={'symbol': 'BTC,ETH,SOL'},
            headers=headers,
            timeout=10
        )
        if r2.status_code != 200:
            return None
        
        coins = r2.json()['data']
        btc_change = round(coins['BTC']['quote']['USD']['percent_change_24h'], 1)
        eth_change = round(coins['ETH']['quote']['USD']['percent_change_24h'], 1)
        sol_change = round(coins['SOL']['quote']['USD']['percent_change_24h'], 1)
        sol_mcap = coins['SOL']['quote']['USD']['market_cap']
        sol_d = round(sol_mcap / total_mcap * 100, 1) if total_mcap > 0 else 0
        
        return {
            'btc_d': btc_d, 'eth_d': eth_d, 'sol_d': sol_d,
            'btc_ch': btc_change, 'eth_ch': eth_change, 'sol_ch': sol_change,
            'fng_value': fng_value, 'fng_text': fng_text
        }
    except:
        return None

def dominance_text():
    """Tạo text hiển thị Dominance + Fear & Greed"""
    dom = get_dominance()
    if not dom:
        return ""
    
    def ch_icon(v):
        if v > 0:
            return f"🟢 +{v}%"
        elif v < 0:
            return f"🔴 {v}%"
        return "➡️ 0%"
    
    text = (
        f"\n📊 <b>Dominance:</b>\n"
        f"₿ BTC: <b>{dom['btc_d']}%</b> ({ch_icon(dom['btc_ch'])})\n"
        f"Ξ ETH: <b>{dom['eth_d']}%</b> ({ch_icon(dom['eth_ch'])})\n"
        f"◎ SOL: <b>{dom['sol_d']}%</b> ({ch_icon(dom['sol_ch'])})\n"
    )
    
    if dom['btc_d'] > 58:
        text += "⚠️ <b>BTC.D CAO</b> → Altcoin yếu, ưu tiên BTC\n"
    elif dom['btc_d'] < 48:
        text += "✅ <b>BTC.D THẤP</b> → Altcoin season, ưu tiên ETH/SOL\n"
    
    if abs(dom['btc_ch']) > 2:
        direction = "TĂNG" if dom['btc_ch'] > 0 else "GIẢM"
        text += f"⚡ BTC.D đang {direction} mạnh ({dom['btc_ch']:+.1f}%) → Dòng tiền đang dịch chuyển!\n"
    
    # Fear & Greed
    fng_val = dom['fng_value']
    fng_text = dom['fng_text']
    
    if fng_val is None:
        # Fallback: Alternative.me
        try:
            r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
            if r.status_code == 200:
                d = r.json()['data'][0]
                fng_val = int(d['value'])
                fng_text = d['value_classification']
        except:
            pass
    
    if fng_val is not None:
        icons = {25: "😱", 40: "😟", 60: "😐", 75: "😊", 100: "🤤"}
        icon = "😐"
        for threshold, i in icons.items():
            if fng_val <= threshold:
                icon = i
                break
        text += f"\n{icon} <b>Fear & Greed:</b> {fng_val}/100 ({fng_text})\n"
    
    return text

# ============================================
# FEDWATCH - DỰ ĐOÁN LÃI SUẤT
# ============================================
def get_fedwatch_prediction():
    """Dự đoán xu hướng lãi suất Fed dựa trên FRED"""
    fed_data = fred_get('DFF')
    if not fed_data:
        return None
    
    current_rate = fed_data[0]['value']
    
    if len(fed_data) >= 2:
        prev_rate = fed_data[1]['value']
        if current_rate > prev_rate:
            trend = f"📈 Lãi suất đang <b>TĂNG</b> (từ {prev_rate}% → {current_rate}%)"
        elif current_rate < prev_rate:
            trend = f"📉 Lãi suất đang <b>GIẢM</b> (từ {prev_rate}% → {current_rate}%)"
        else:
            trend = f"➡️ Lãi suất đang <b>ỔN ĐỊNH</b> ở mức {current_rate}%"
    else:
        trend = f"➡️ Lãi suất hiện tại: <b>{current_rate}%</b>"
    
    cpi_data = fred_get('CPIAUCSL')
    if cpi_data and len(cpi_data) >= 2:
        cpi_change = round((cpi_data[0]['value'] - cpi_data[1]['value']) / cpi_data[1]['value'] * 100, 1)
        if cpi_change > 0.3:
            prediction = f"⚠️ CPI tăng <b>{cpi_change}%</b> → Áp lực <b>TĂNG</b> lãi suất"
        elif cpi_change < -0.3:
            prediction = f"✅ CPI giảm <b>{abs(cpi_change)}%</b> → Có thể <b>GIẢM</b> lãi suất"
        else:
            prediction = f"➡️ CPI ổn định → Dự kiến <b>GIỮ NGUYÊN</b> lãi suất"
    else:
        prediction = "➡️ Chưa có dữ liệu CPI → Dự kiến <b>GIỮ NGUYÊN</b>"
    
    return {
        'current_rate': f"{current_rate}%",
        'trend': trend,
        'prediction': prediction
    }

# ============================================
# PHÂN TÍCH TIN TỨC
# ============================================
def is_market_news(title):
    """Kiểm tra tin có liên quan thị trường không"""
    title_lower = title.lower()
    for kw in NON_MARKET_KW:
        if kw in title_lower:
            return False
    return True

# Context rules - hiểu ngữ cảnh
CONTEXT_POSITIVE = [
    "ceasefire", "truce", "peace deal", "peace talk", "reopening", "withdrawal",
    "rate cut", "dovish", "easing", "stimulus", "rebound", "recover",
    "surge", "soar", "rally", "record high", "bull market",
    "etf approved", "etf inflow", "institutional", "adoption",
    "oil prices drop", "oil prices fall", "oil prices decline",
    "stock surge", "stock rally", "market rally",
    "gold decline", "gold drop", "gold fall",
]

CONTEXT_NEGATIVE = [
    "war intensifies", "missile strike", "missile attack", "airstrike", "invasion",
    "oil prices surge", "oil prices rise", "oil prices spike",
    "rate hike", "hawkish", "tightening", "recession", "depression",
    "crash", "collapse", "plunge", "tumble", "slump",
    "etf outflow", "sanction imposed", "tariff imposed",
    "nuclear threat", "military escalation",
    "stock plunge", "stock crash", "market crash", "market turmoil",
    "gold surge", "gold soar", "gold spike",
]

POSITIVE_KW = [
    "rate cut", "dovish", "easing", "ceasefire", "peace deal", "peace talk",
    "truce", "withdrawal", "bull market", "rally", "etf approved",
    "etf inflow", "blackrock", "institutional", "adoption",
    "stimulus", "rebound", "recover", "surge", "soar"
]

NEGATIVE_KW = [
    "war", "strike", "missile", "bomb", "airstrike", "attack", "invasion",
    "nuclear", "sanction", "embargo", "tariff", "trade war",
    "rate hike", "hawkish", "tightening", "recession", "depression", "crash",
    "collapse", "etf outflow", "hormuz",
    "escalation", "conflict", "tensions", "plunge", "tumble", "slump"
]

def has_keyword(text, word):
    return bool(re.search(r'\b' + re.escape(word) + r'\b', text.lower()))

def analyze_sentiment(title, description=""):
    """Phân tích sentiment của tin tức"""
    if not is_market_news(title):
        return None
    
    text = (title + " " + description).lower()
    
    # Đếm context rules (trọng số 3)
    pos_context = sum(1 for ctx in CONTEXT_POSITIVE if ctx in text)
    neg_context = sum(1 for ctx in CONTEXT_NEGATIVE if ctx in text)
    
    # Đếm từ khóa đơn (trọng số 1)
    pos_kw = [kw for kw in POSITIVE_KW if has_keyword(text, kw)]
    neg_kw = [kw for kw in NEGATIVE_KW if has_keyword(text, kw)]
    
    pos_score = pos_context * 3 + len(pos_kw)
    neg_score = neg_context * 3 + len(neg_kw)
    
    if pos_score == 0 and neg_score == 0:
        return None
    
    # Keywords hiển thị
    display_kw = []
    for ctx in CONTEXT_POSITIVE:
        if ctx in text and len(display_kw) < 3:
            display_kw.append(ctx)
    for ctx in CONTEXT_NEGATIVE:
        if ctx in text and len(display_kw) < 3:
            display_kw.append(ctx)
    if not display_kw:
        display_kw = pos_kw[:3] if pos_kw else neg_kw[:3]
    display_kw = list(set(display_kw))[:3]
    
    if neg_score > pos_score:
        if neg_score >= 9:
            loai = "🔴🔴🔴 CỰC KỲ TIÊU CỰC"
        elif neg_score >= 6:
            loai = "🔴🔴 RẤT TIÊU CỰC"
        else:
            loai = "🔴 TIÊU CỰC"
        gold = "🥇 Vàng: 🟢 TĂNG (trú ẩn)"
        crypto = "₿ Crypto: 🔴 GIẢM (risk-off)"
        usd = "💵 USD: 🟢 TĂNG (trú ẩn)"
        advice = "⚠️ ƯU TIÊN SHORT"
    else:
        if pos_score >= 9:
            loai = "🟢🟢🟢 CỰC KỲ TÍCH CỰC"
        elif pos_score >= 6:
            loai = "🟢🟢 TÍCH CỰC"
        else:
            loai = "🟢 TÍCH CỰC"
        gold = "🥇 Vàng: 🔴 GIẢM (risk-on)"
        crypto = "₿ Crypto: 🟢 TĂNG (risk-on)"
        usd = "💵 USD: 🔴 GIẢM (risk-on)"
        advice = "✅ ƯU TIÊN LONG"
    
    return {
        'loai': loai,
        'gold': gold,
        'crypto': crypto,
        'usd': usd,
        'advice': advice,
        'keywords': display_kw
    }

# ============================================
# DỊCH TIẾNG VIỆT
# ============================================
FIX_DICH = {
    "tỷ lệ cắt": "hạ lãi suất",
    "cắt giảm lãi suất": "hạ lãi suất",
    "tỷ lệ tăng": "tăng lãi suất",
    "chợ bò": "thị trường tăng",
    "chợ gấu": "thị trường giảm",
    "tiền điện tử": "crypto",
    "tiền mã hóa": "crypto",
    "chuỗi khối": "blockchain",
    "dòng tiền chảy ra": "dòng vốn ETF ra",
    "dòng tiền chảy vào": "dòng vốn ETF vào",
    "trú ẩn an toàn": "tài sản trú ẩn",
    "eo biển hormuz": "eo biển Hormuz",
    "cục dự trữ liên bang": "Fed",
    "quỹ giao dịch trao đổi": "ETF",
    "bảng lương phi nông nghiệp": "bảng lương NFP",
    "chỉ số giá tiêu dùng": "CPI",
    "chỉ số giá sản xuất": "PPI",
    "tổng sản phẩm quốc nội": "GDP",
    "phố wall": "Phố Wall",
    "nhà trắng": "Nhà Trắng",
    "lầu năm góc": "Lầu Năm Góc",
    "điện kremlin": "Điện Kremlin",
    "vốn hóa thị trường": "vốn hóa",
    "thị trường chứng khoán": "chứng khoán",
    "lợi suất trái phiếu": "lợi suất",
    "dầu thô": "dầu",
    "giá dầu": "giá dầu",
}

def dich_tieng_viet(text):
    """Dịch tiếng Việt chuẩn"""
    if not text:
        return ""
    try:
        r = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={'client': 'gtx', 'sl': 'en', 'tl': 'vi', 'dt': 't', 'q': text},
            timeout=5
        )
        if r.status_code == 200:
            translated = ''.join([s[0] for s in r.json()[0] if s[0]])
        else:
            return text
    except:
        return text
    
    for wrong, correct in FIX_DICH.items():
        translated = re.sub(r'\b' + re.escape(wrong) + r'\b', correct, translated, flags=re.IGNORECASE)
    
    if translated and len(translated) > 1:
        translated = translated[0].upper() + translated[1:]
    
    return translated

# ============================================
# FETCH RSS
# ============================================
def fetch_rss_news(log):
    """Lấy tin từ tất cả nguồn RSS"""
    all_news = []
    
    for url, source_name in RSS_FEEDS:
        try:
            r = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            if r.status_code != 200:
                continue
            
            root = ET.fromstring(r.content)
            items = root.findall('.//item')
            if not items:
                items = root.findall('.//{http://www.w3.org/2005/Atom}entry')
            
            for item in items[:5]:
                # Lấy title
                title_el = item.find('title')
                if title_el is None:
                    title_el = item.find('{http://www.w3.org/2005/Atom}title')
                title = title_el.text if title_el is not None else ''
                
                # Lấy description
                desc_el = item.find('description')
                if desc_el is None:
                    desc_el = item.find('{http://www.w3.org/2005/Atom}summary')
                description = clean_html(desc_el.text) if desc_el is not None and desc_el.text else ''
                
                # Lấy link
                link_el = item.find('link')
                if link_el is None:
                    link_el = item.find('{http://www.w3.org/2005/Atom}link')
                link = ""
                if link_el is not None:
                    link = link_el.get('href') or link_el.text or ''
                
                # Lấy ngày
                date_el = item.find('pubDate')
                if date_el is None:
                    date_el = item.find('{http://www.w3.org/2005/Atom}updated')
                    if date_el is None:
                        date_el = item.find('{http://www.w3.org/2005/Atom}published')
                pubdate = date_el.text if date_el is not None else ''
                
                if not title or link in log['news_sent']:
                    continue
                
                # Phân tích sentiment
                result = analyze_sentiment(title, description)
                if result is None:
                    continue
                
                # Kiểm tra trùng lặp
                is_dup = False
                for existing in all_news:
                    words1 = set(title.lower().split())
                    words2 = set(existing['title_en'].lower().split())
                    if not words1 or not words2:
                        continue
                    similarity = len(words1 & words2) / len(words1 | words2)
                    if similarity > 0.5:
                        is_dup = True
                        break
                
                if is_dup:
                    continue
                
                log['news_sent'].append(link)
                all_news.append({
                    'title_vi': dich_tieng_viet(title),
                    'title_en': title,
                    'description': description,
                    'source': source_name,
                    'date': format_date(pubdate) if pubdate else '',
                    'loai': result['loai'],
                    'gold': result['gold'],
                    'crypto': result['crypto'],
                    'usd': result['usd'],
                    'advice': result['advice'],
                    'keywords': result['keywords']
                })
        except:
            continue
    
    return all_news

def fetch_all_news():
    """Lấy tất cả tin tức"""
    log = get_log()
    log['news_sent'] = []
    
    all_news = fetch_rss_news(log)
    
    log['news_sent'] = log['news_sent'][-500:]
    save_log(log)
    
    # Sắp xếp: tiêu cực trước, nguồn uy tín ưu tiên
    priority = {
        'CỰC KỲ TIÊU CỰC': 0,
        'RẤT TIÊU CỰC': 1,
        'TIÊU CỰC': 2,
        'TÍCH CỰC': 3,
        'CỰC KỲ TÍCH CỰC': 4
    }
    
    def sort_key(news):
        loai_text = news['loai'].split()[-1] if 'CỰC' in news['loai'] else news['loai'].split()[-1]
        p = priority.get(loai_text, 3)
        t = 0 if any(s in news['source'].lower() for s in TRUSTED_SOURCES) else 1
        return (p, t)
    
    all_news.sort(key=sort_key)
    return all_news[:MAX_NEWS]

# ============================================
# SỰ KIỆN KINH TẾ
# ============================================
EVENTS = [
    {
        'id': 'fomc_minutes_jun',
        'name': '📋 Biên bản họp FOMC (T6)',
        'date': '2026-06-04',
        'time': '01:00',
        'impact': '🟢 THẤP',
        'desc': 'Biên bản cuộc họp cũ - không có quyết định mới. Ít ảnh hưởng thị trường.',
        'fred': 'DFF',
        'is_fomc': False
    },
    {
        'id': 'nfp_may',
        'name': '💼 Bảng lương NFP (T5)',
        'date': '2026-06-05',
        'time': '19:30',
        'impact': '🔴 CAO',
        'desc': 'Báo cáo việc làm phi nông nghiệp - chỉ báo sức khỏe kinh tế Mỹ.',
        'fred': 'UNRATE',
        'is_fomc': False,
        'advice': 'NFP > dự đoán → Kinh tế mạnh → 🟢 LONG Crypto\nNFP < dự đoán → Kinh tế yếu → 🔴 SHORT Crypto',
        'gold': 'NFP cao → USD mạnh → Vàng GIẢM',
        'crypto': 'NFP cao → Kinh tế tốt → Crypto TĂNG',
        'usd': 'NFP cao → USD TĂNG'
    },
    {
        'id': 'cpi_may',
        'name': '📊 Chỉ số CPI (T5)',
        'date': '2026-06-11',
        'time': '19:30',
        'impact': '🔴 CAO',
        'desc': 'Chỉ số giá tiêu dùng - thước đo lạm phát quan trọng nhất.',
        'fred': 'CPIAUCSL',
        'is_fomc': False,
        'advice': 'CPI thấp hơn dự đoán → Fed dovish → 🟢 LONG Crypto\nCPI cao hơn dự đoán → Fed hawkish → 🔴 SHORT Crypto',
        'gold': 'CPI cao → Vàng TĂNG (hedge lạm phát)',
        'crypto': 'CPI cao → lo tăng lãi suất → Crypto GIẢM',
        'usd': 'CPI cao → USD TĂNG (kỳ vọng hawkish)'
    },
    {
        'id': 'ppi_may',
        'name': '🏭 Chỉ số PPI (T5)',
        'date': '2026-06-12',
        'time': '19:30',
        'impact': '🟡 TRUNG BÌNH',
        'desc': 'Chỉ số giá sản xuất - chỉ báo sớm của lạm phát.',
        'fred': 'PPIACO',
        'is_fomc': False,
        'advice': 'PPI tăng → áp lực lạm phát → thận trọng\nPPI giảm → tích cực cho Crypto',
        'gold': 'PPI cao → Vàng TĂNG nhẹ',
        'crypto': 'PPI cao → Crypto GIẢM nhẹ',
        'usd': 'PPI cao → USD TĂNG nhẹ'
    },
    {
        'id': 'fomc_jun',
        'name': '🏦 Quyết định lãi suất FOMC (T6)',
        'date': '2026-06-18',
        'time': '01:00',
        'impact': '🔴 CAO - SỰ KIỆN QUAN TRỌNG NHẤT THÁNG',
        'desc': 'Fed công bố quyết định tăng/giảm/giữ nguyên lãi suất.',
        'fred': 'DFF',
        'is_fomc': True,
        'advice': 'Nếu GIỮ NGUYÊN → 🟢 LONG Crypto\nNếu TĂNG → 🔴 SHORT Crypto\nNếu GIẢM → 🟢 LONG mạnh Crypto\nĐóng bot 30p trước sự kiện!',
        'gold': 'Hawkish → Vàng GIẢM | Dovish → Vàng TĂNG',
        'crypto': 'Hawkish → Crypto GIẢM | Dovish → Crypto TĂNG',
        'usd': 'Hawkish → USD TĂNG | Dovish → USD GIẢM'
    },
    {
        'id': 'gdp_q2',
        'name': '📊 GDP Quý 2/2026',
        'date': '2026-06-25',
        'time': '19:30',
        'impact': '🔴 CAO',
        'desc': 'Tăng trưởng kinh tế Mỹ quý 2/2026.',
        'fred': 'GDP',
        'is_fomc': False,
        'advice': 'GDP cao → Kinh tế mạnh → 🟢 LONG Crypto\nGDP thấp → Suy thoái → 🔴 SHORT Crypto',
        'gold': 'GDP cao → Vàng GIẢM (risk-on)',
        'crypto': 'GDP cao → Crypto TĂNG',
        'usd': 'GDP cao → USD TĂNG'
    },
    {
        'id': 'fomc_jul',
        'name': '🏦 Quyết định lãi suất FOMC (T7)',
        'date': '2026-07-30',
        'time': '01:00',
        'impact': '🔴 CAO - SỰ KIỆN QUAN TRỌNG',
        'desc': 'Quyết định lãi suất Fed giữa năm 2026.',
        'fred': 'DFF',
        'is_fomc': True,
        'advice': 'Nếu GIỮ NGUYÊN → 🟢 LONG Crypto\nNếu TĂNG → 🔴 SHORT Crypto\nĐóng bot 30p trước sự kiện!',
        'gold': 'Hawkish → Vàng GIẢM | Dovish → Vàng TĂNG',
        'crypto': 'Hawkish → Crypto GIẢM | Dovish → Crypto TĂNG',
        'usd': 'Hawkish → USD TĂNG | Dovish → USD GIẢM'
    },
]

def check_events():
    """Kiểm tra và gửi thông báo sự kiện"""
    log = get_log()
    now = datetime.now()
    today = now.date()
    messages = []
    fedwatch = get_fedwatch_prediction()
    
    for ev in EVENTS:
        evd = datetime.strptime(ev['date'], '%Y-%m-%d').date()
        evdt = datetime.strptime(ev['date'] + ' ' + ev['time'], '%Y-%m-%d %H:%M')
        days = (evd - today).days
        hours_since = (now - evdt).total_seconds() / 3600 if evdt < now else -1
        
        # PRE-EVENT: 0-5 ngày trước
        if 0 <= days <= 5:
            key = f"pre_{ev['id']}"
            if time.time() - log['events'].get(key, 0) >= 21600:
                log['events'][key] = time.time()
                
                if days == 0:
                    cd = f"⚠️ <b>HÔM NAY</b> lúc {ev['time']} (giờ VN)"
                elif days == 1:
                    cd = f"📅 <b>NGÀY MAI</b> lúc {ev['time']} (giờ VN)"
                else:
                    cd = f"📅 Còn <b>{days} ngày</b> - {ev['date']} lúc {ev['time']} (giờ VN)"
                
                # Phân tích lãi suất cho FOMC
                fw_text = ""
                if ev.get('is_fomc') and fedwatch:
                    fw_text = (
                        f"\n\n📊 <b>PHÂN TÍCH LÃI SUẤT (FRED):</b>\n"
                        f"{fedwatch['trend']}\n"
                        f"{fedwatch['prediction']}\n"
                        f"🏦 Hiện tại: {fedwatch['current_rate']}"
                    )
                
                # Tác động dự kiến
                tac_dong = ""
                if ev.get('gold') or ev.get('crypto') or ev.get('usd'):
                    tac_dong = "\n\n📊 <b>TÁC ĐỘNG DỰ KIẾN:</b>\n"
                    if ev.get('gold'):
                        tac_dong += f"🥇 Vàng: {ev['gold']}\n"
                    if ev.get('crypto'):
                        tac_dong += f"₿ Crypto: {ev['crypto']}\n"
                    if ev.get('usd'):
                        tac_dong += f"💵 USD: {ev['usd']}\n"
                
                # Chiến lược
                chien_luoc = ""
                if ev.get('advice'):
                    chien_luoc = f"\n💡 <b>CHIẾN LƯỢC:</b>\n{ev['advice']}\n"
                
                messages.append(
                    f"📅 <b>{ev['name']}</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"⏰ {cd}\n"
                    f"⚡ Mức độ: {ev['impact']}\n"
                    f"📝 {ev['desc']}"
                    f"{fw_text}{tac_dong}{chien_luoc}\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"📊 <b>DỮ LIỆU KINH TẾ HIỆN TẠI:</b>\n{econ_summary()}\n\n{now_str()}"
                )
        
        # POST-EVENT: 1-24h sau
        elif days < 0 and 1 <= hours_since <= 24:
            key = f"post_{ev['id']}"
            if key not in log['events']:
                data = fred_get(ev['fred'])
                if data and len(data) >= 2:
                    curr = data[0]['value']
                    prev = data[1]['value']
                    
                    # FOMC Decision
                    if 'fomc' in ev['id'] and 'minutes' not in ev['id']:
                        if curr > prev:
                            ket_qua = f"📈 <b>Fed TĂNG lãi suất</b> từ {prev}% lên {curr}%"
                            tac_dong = "🦅 <b>HAWKISH</b> - Thắt chặt tiền tệ"
                            hanh_dong = "🔴 Tiêu cực cho Crypto → Cân nhắc SHORT"
                        elif curr < prev:
                            ket_qua = f"📉 <b>Fed GIẢM lãi suất</b> từ {prev}% xuống {curr}%"
                            tac_dong = "🕊️ <b>DOVISH</b> - Nới lỏng tiền tệ"
                            hanh_dong = "🟢 Tích cực cho Crypto → Cân nhắc LONG"
                        else:
                            ket_qua = f"➡️ <b>Fed GIỮ NGUYÊN lãi suất</b> ở mức {curr}%"
                            tac_dong = "➡️ <b>TRUNG LẬP</b> - Chờ thêm dữ liệu"
                            hanh_dong = "🟢 Tích cực nhẹ → Tiếp tục theo dõi"
                    
                    # NFP
                    elif ev['id'] == 'nfp_may':
                        ket_qua = f"📊 <b>Thất nghiệp: {curr}%</b> (trước: {prev}%)"
                        if curr > prev:
                            tac_dong = "⚠️ Lao động yếu đi"
                        elif curr < prev:
                            tac_dong = "✅ Lao động mạnh lên"
                        else:
                            tac_dong = "➡️ Không đổi"
                        hanh_dong = "🟢 LONG Crypto" if curr < prev else "🔴 SHORT Crypto"
                    
                    # CPI
                    elif ev['id'] == 'cpi_may':
                        pct = round((curr - prev) / prev * 100, 1)
                        ket_qua = f"📊 <b>CPI: {curr}</b> ({'+' if pct > 0 else ''}{pct}%)"
                        if curr > prev:
                            tac_dong = "⚠️ Lạm phát nóng"
                        elif curr < prev:
                            tac_dong = "✅ Lạm phát hạ nhiệt"
                        else:
                            tac_dong = "➡️ Không đổi"
                        hanh_dong = "🟢 LONG Crypto (CPI thấp)" if curr <= prev else "🔴 SHORT Crypto (CPI cao)"
                    
                    # PPI
                    elif ev['id'] == 'ppi_may':
                        pct = round((curr - prev) / prev * 100, 1)
                        ket_qua = f"📊 <b>PPI: {curr}</b> ({'+' if pct > 0 else ''}{pct}%)"
                        if curr > prev:
                            tac_dong = "⚠️ Áp lực giá tăng"
                        elif curr < prev:
                            tac_dong = "✅ Áp lực giá giảm"
                        else:
                            tac_dong = "➡️ Không đổi"
                        hanh_dong = "Theo dõi thêm"
                    
                    # GDP
                    elif ev['id'] == 'gdp_q2':
                        pct = round((curr - prev) / prev * 100, 2)
                        ket_qua = f"📊 <b>GDP: ${curr:,.0f}B</b> ({'+' if pct > 0 else ''}{pct}%)"
                        if curr > prev:
                            tac_dong = "✅ Kinh tế tăng trưởng"
                        else:
                            tac_dong = "⚠️ Kinh tế suy giảm"
                        hanh_dong = "🟢 LONG Crypto" if curr > prev else "🔴 SHORT Crypto"
                    
                    else:
                        ket_qua = f"📊 <b>{curr}</b> (trước: {prev})"
                        tac_dong = "Đã cập nhật"
                        hanh_dong = "Theo dõi thêm"
                    
                    log['events'][key] = time.time()
                    messages.append(
                        f"✅ <b>{ev['name']} - KẾT QUẢ THỰC TẾ</b>\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"⏰ Đã diễn ra: {ev['date']} lúc {ev['time']} (giờ VN)\n\n"
                        f"📊 <b>KẾT QUẢ:</b>\n{ket_qua}\n\n"
                        f"🎤 <b>ĐÁNH GIÁ:</b>\n{tac_dong}\n\n"
                        f"💡 <b>HÀNH ĐỘNG:</b>\n{hanh_dong}\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"📊 <b>DỮ LIỆU KINH TẾ HIỆN TẠI:</b>\n{econ_summary()}\n\n{now_str()}"
                    )
    
    save_log(log)
    return messages

# ============================================
# MAIN
# ============================================
print("=" * 60)
print("BOT TIN TUC V2 - RSS + CMC + FRED")
print("=" * 60)

while True:
    try:
        state = get_state()
        now_ts = time.time()
        
        if not state['started'] or (now_ts - state['last_update'] >= CHU_KY):
            set_state(started=True, last_update=now_ts)
            
            if 'started_ever' not in state:
                set_state(started_ever=True)
            
            # Lấy tin tức
            news = fetch_all_news()
            
            label = "đã khởi động" if state.get('started_ever') else "cập nhật 6h"
            rss_count = sum(1 for n in news if n['source'] in [
                'Reuters', 'CNBC', 'CoinDesk', 'Cointelegraph', 'MarketWatch'
            ])
            dom_text = dominance_text()
            
            # Gửi bản tin
            gui(
                f"📰 <b>BẢN TIN THỊ TRƯỜNG {label}!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📡 FRED: ✅ | RSS: ✅ {rss_count} tin\n\n"
                f"📊 <b>DỮ LIỆU KINH TẾ:</b>\n{econ_summary()}{dom_text}\n\n"
                f"📋 Phát hiện <b>{len(news)} tin</b> quan trọng\n\n{now_str()}"
            )
            
            # Gửi từng tin
            if news:
                # Tổng quan thị trường
                neg = sum(1 for n in news if 'TIÊU CỰC' in n['loai'])
                pos = sum(1 for n in news if 'TÍCH CỰC' in n['loai'])
                total = len(news)
                neg_ratio = neg / total if total > 0 else 0
                
                if neg_ratio >= 0.6:
                    level = "CAO 🔴"
                    advice = "⚠️ <b>NGHIÊNG VỀ SHORT</b>"
                elif pos >= total * 0.6:
                    level = "THẤP (TÍCH CỰC) 🟢"
                    advice = "✅ <b>ƯU TIÊN LONG</b>"
                else:
                    level = "TRUNG BÌNH 🟡"
                    advice = "➡️ <b>THEO DÕI THÊM</b>"
                
                all_kw = []
                for n in news:
                    all_kw.extend(n['keywords'])
                top_kw = list(set(all_kw))[:6]
                
                gui(
                    f"📰 <b>TỔNG QUAN THỊ TRƯỜNG</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🚨 Mức độ: <b>{level}</b>\n"
                    f"📊 Tiêu cực: {neg}/{total} | Tích cực: {pos}/{total}\n"
                    f"💡 {advice}\n\n"
                    f"🔑 Từ khóa: {', '.join(top_kw)}\n\n{now_str()}"
                )
                
                # Từng tin chi tiết
                for n in news:
                    date_line = f"\n📅 {n['date']}" if n['date'] else ""
                    
                    tom_tat_parts = []
                    if n['keywords']:
                        tom_tat_parts.append(f"🔑 <b>Từ khóa:</b> {', '.join(n['keywords'])}")
                    if n.get('description'):
                        desc = clean_html(n['description'])
                        first_sentence = desc.split('.')[0].strip()
                        if len(first_sentence) > 15:
                            tom_tat_parts.append(f"📝 {first_sentence}.")
                    tom_tat = "\n".join(tom_tat_parts)
                    
                    msg = (
                        f"📰 TIN TỨC {n['loai']}\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"🇻🇳 <b>{n['title_vi']}</b>\n\n"
                    )
                    if tom_tat:
                        msg += f"{tom_tat}\n\n"
                    msg += (
                        f"📡 Nguồn: {n['source']}{date_line}\n"
                        f"🇬🇧 {n['title_en']}\n\n"
                        f"🏦 <b>Dự báo:</b>\n{n['gold']}\n{n['crypto']}\n{n['usd']}\n\n"
                        f"💡 {n['advice']}\n\n{now_str()}"
                    )
                    gui(msg)
                    time.sleep(1)
            
            # Gửi sự kiện
            for msg in check_events():
                gui(msg)
        
        time.sleep(60)
    
    except KeyboardInterrupt:
        print("\n👋 Đã dừng Bot Tin Tức")
        break
    except Exception as e:
        print(f"Lỗi: {e}")
        time.sleep(30)