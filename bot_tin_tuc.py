"""
BOT TIN TUC - NEWSAPI + RSS FEEDS - PRO FINAL
- 5 nguồn RSS miễn phí: Reuters, CNBC, CoinDesk, Cointelegraph, MarketWatch
- NewsAPI bổ sung
- Dịch tiếng Việt chuẩn Google Translate + sửa từ khóa tài chính
- Context analysis: hiểu ngữ cảnh, không chỉ đếm từ khóa
- FedWatch từ FRED - logic rõ ràng, không mâu thuẫn
- BTC.D, ETH.D, SOL.D Dominance (không stablecoin) + 24h change
- Lọc tin không liên quan thị trường
- Post-event tự động báo cáo kết quả
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

BLOCKED_SOURCES = [
    "naturalnews.com", "beforeitsnews.com", "infowars.com", "zerohedge.com",
    "activistpost.com", "globalresearch.ca", "nakedcapitalism.com",
    "thegatewaypundit.com", "breitbart.com", "occupydemocrats.com",
    "dailycaller.com", "foxnews.com", "newsmax.com", "oann.com"
]

TRUSTED_SOURCES = [
    "reuters.com", "bloomberg.com", "cnbc.com", "wsj.com", "ft.com",
    "coindesk.com", "cointelegraph.com", "theblock.co", "marketwatch.com",
    "investing.com", "forexlive.com", "apnews.com", "bbc.com", "aljazeera.com",
    "economist.com", "barrons.com", "financialpost.com", "fxstreet.com",
    "decrypt.co", "cryptobriefing.com", "blockworks.co"
]

NON_MARKET_KW = [
    "generational war", "culture war", "boomer", "gen z", "gen alpha",
    "millennial", "tiktok", "influencer", "celebrity", "royal family",
    "sports", "gaming", "streaming war", "movie", "netflix", "disney",
    "grammy", "oscar", "emmy", "super bowl", "world cup", "nfl", "nba"
]

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
        "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z",
        "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%d/%m/%Y %H:%M")
        except: pass
    return date_str[:16] if len(date_str) > 16 else date_str

# ============================================
# DOMINANCE - FIX CONG THUC + 24H CHANGE
# ============================================
def get_dominance():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global", timeout=10)
        if r.status_code != 200: return None, None, None, None, None, None
        data = r.json()
        total_mcap = data['data']['total_market_cap']['usd']
        
        r_stable = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={'ids': 'tether,usd-coin,dai,binance-usd', 'vs_currencies': 'usd', 'include_market_cap': 'true'},
            timeout=10
        )
        stable_mcap = 0
        if r_stable.status_code == 200:
            stable_data = r_stable.json()
            for coin_id in ['tether', 'usd-coin', 'dai', 'binance-usd']:
                stable_mcap += stable_data.get(coin_id, {}).get('usd_market_cap', 0)
        
        real_mcap = total_mcap - stable_mcap
        
        r_coins = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={'vs_currency':'usd','ids':'bitcoin,ethereum,solana','order':'market_cap_desc','per_page':3,'page':1,'sparkline':'false'},
            timeout=10
        )
        if r_coins.status_code != 200: return None, None, None, None, None, None
        
        coins_data = r_coins.json()
        btc_mcap = eth_mcap = sol_mcap = 0
        btc_change = eth_change = sol_change = 0
        
        for coin in coins_data:
            if coin['id'] == 'bitcoin':
                btc_mcap = coin['market_cap']; btc_change = coin.get('market_cap_change_percentage_24h', 0)
            elif coin['id'] == 'ethereum':
                eth_mcap = coin['market_cap']; eth_change = coin.get('market_cap_change_percentage_24h', 0)
            elif coin['id'] == 'solana':
                sol_mcap = coin['market_cap']; sol_change = coin.get('market_cap_change_percentage_24h', 0)
        
        btc_d = round(btc_mcap / real_mcap * 100, 1) if real_mcap > 0 else 0
        eth_d = round(eth_mcap / real_mcap * 100, 1) if real_mcap > 0 else 0
        sol_d = round(sol_mcap / real_mcap * 100, 1) if real_mcap > 0 else 0
        
        return btc_d, eth_d, sol_d, round(btc_change, 1), round(eth_change, 1), round(sol_change, 1)
    except:
        return None, None, None, None, None, None

def dominance_text():
    btc_d, eth_d, sol_d, btc_ch, eth_ch, sol_ch = get_dominance()
    if not btc_d: return ""
    
    def ch_icon(v):
        if v > 0: return f"🟢 +{v}%"
        elif v < 0: return f"🔴 {v}%"
        return "➡️ 0%"
    
    text = f"\n📊 <b>Dominance (không stablecoin):</b>\n"
    text += f"₿ BTC: <b>{btc_d}%</b> ({ch_icon(btc_ch)})\n"
    text += f"Ξ ETH: <b>{eth_d}%</b> ({ch_icon(eth_ch)})\n"
    text += f"◎ SOL: <b>{sol_d}%</b> ({ch_icon(sol_ch)})\n"
    
    if btc_d > 58:
        text += "⚠️ <b>BTC.D CAO</b> → Altcoin yếu, ưu tiên BTC\n"
    elif btc_d < 48:
        text += "✅ <b>BTC.D THẤP</b> → Altcoin season, ưu tiên ETH/SOL\n"
    
    if abs(btc_ch) > 2:
        direction = "TĂNG" if btc_ch > 0 else "GIẢM"
        text += f"⚡ BTC.D đang {direction} mạnh ({btc_ch:+.1f}%) → Dòng tiền đang dịch chuyển!\n"
    
    return text

# ============================================
# DICH TIENG VIET
# ============================================
FIX_DICH = {
    "tỷ lệ cắt": "hạ lãi suất", "cắt giảm lãi suất": "hạ lãi suất",
    "tỷ lệ tăng": "tăng lãi suất",
    "chợ bò": "thị trường tăng", "chợ gấu": "thị trường giảm",
    "tiền điện tử": "crypto", "tiền mã hóa": "crypto",
    "chuỗi khối": "blockchain",
    "dòng tiền chảy ra": "dòng vốn ETF ra", "dòng tiền chảy vào": "dòng vốn ETF vào",
    "trú ẩn an toàn": "tài sản trú ẩn",
    "eo biển hormuz": "eo biển Hormuz",
    "cục dự trữ liên bang": "Fed", "ngân hàng trung ương mỹ": "Fed",
    "quỹ giao dịch trao đổi": "ETF",
    "bảng lương phi nông nghiệp": "bảng lương NFP",
    "chỉ số giá tiêu dùng": "CPI", "chỉ số giá sản xuất": "PPI",
    "tổng sản phẩm quốc nội": "GDP",
    "phố wall": "Phố Wall", "nhà trắng": "Nhà Trắng",
    "lầu năm góc": "Lầu Năm Góc", "điện kremlin": "Điện Kremlin",
    "vốn hóa thị trường": "vốn hóa",
    "thị trường chứng khoán": "chứng khoán",
    "lợi suất trái phiếu": "lợi suất",
    "dầu thô": "dầu", "giá dầu": "giá dầu",
}

def dich_tieng_viet_chuan(text):
    if not text: return ""
    try:
        r = requests.get("https://translate.googleapis.com/translate_a/single",
                        params={'client':'gtx','sl':'en','tl':'vi','dt':'t','q':text}, timeout=5)
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
# FEDWATCH
# ============================================
def get_fedwatch_prediction():
    fed_data = fred_get('DFF')
    if not fed_data: return None
    
    current_rate = fed_data[0]['v']
    
    if len(fed_data) >= 2:
        prev_rate = fed_data[1]['v']
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
        cpi_change = round((cpi_data[0]['v'] - cpi_data[1]['v']) / cpi_data[1]['v'] * 100, 1)
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
        'prediction': prediction,
        'source': 'FRED (dữ liệu thực tế)'
    }

# ============================================
# LOC TIN + CONTEXT + FETCH (giữ nguyên)
# ============================================
def is_market_news(title):
    title_lower = title.lower()
    for kw in NON_MARKET_KW:
        if kw in title_lower: return False
    return True

CONTEXT_POSITIVE = [
    "ceasefire", "truce", "peace deal", "peace talk", "reopening", "withdrawal",
    "rate cut", "dovish", "easing", "stimulus", "rebound", "recover",
    "surge", "soar", "rally", "record high", "bull market",
    "etf approved", "etf inflow", "institutional", "adoption",
    "oil prices drop", "oil prices fall", "oil prices decline",
    "price drop", "price fall", "price decline",
    "stock surge", "stock rally", "market rally", "market surge",
    "gold decline", "gold drop", "gold fall",
    "stronger nato", "nato stronger"
]

CONTEXT_NEGATIVE = [
    "war intensifies", "missile strike", "missile attack", "airstrike", "invasion",
    "oil prices surge", "oil prices rise", "oil prices spike", "oil prices soar",
    "rate hike", "hawkish", "tightening", "recession", "depression",
    "crash", "collapse", "plunge", "tumble", "slump",
    "etf outflow", "sanction imposed", "tariff imposed",
    "nuclear threat", "nuclear weapon", "military escalation",
    "stock plunge", "stock crash", "market crash", "market turmoil",
    "gold surge", "gold soar", "gold spike", "gold rally"
]

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
    if not is_market_news(title): return None
    
    t = (title + " " + description).lower()
    pos_context = sum(1 for ctx in CONTEXT_POSITIVE if ctx in t)
    neg_context = sum(1 for ctx in CONTEXT_NEGATIVE if ctx in t)
    pos_kw = [kw for kw in POSITIVE_KW if has_keyword(t, kw)]
    neg_kw = [kw for kw in NEGATIVE_KW if has_keyword(t, kw)]
    
    pos_score = pos_context * 3 + len(pos_kw)
    neg_score = neg_context * 3 + len(neg_kw)
    if pos_score == 0 and neg_score == 0: return None
    
    display_kw = []
    for ctx in CONTEXT_POSITIVE:
        if ctx in t and len(display_kw) < 3: display_kw.append(ctx)
    for ctx in CONTEXT_NEGATIVE:
        if ctx in t and len(display_kw) < 3: display_kw.append(ctx)
    if not display_kw: display_kw = pos_kw[:3] if pos_kw else neg_kw[:3]
    display_kw = list(set(display_kw))[:3]
    
    if neg_score > pos_score:
        if neg_score >= 9: loai = "🔴🔴🔴 CỰC KỲ TIÊU CỰC"
        elif neg_score >= 6: loai = "🔴🔴 RẤT TIÊU CỰC"
        else: loai = "🔴 TIÊU CỰC"
        gold = "🥇 Vàng: 🟢 TĂNG (trú ẩn)"
        crypto = "₿ Crypto: 🔴 GIẢM (risk-off)"
        usd = "💵 USD: 🟢 TĂNG (trú ẩn)"
        advice = "⚠️ ƯU TIÊN SHORT"
    else:
        if pos_score >= 9: loai = "🟢🟢🟢 CỰC KỲ TÍCH CỰC"
        elif pos_score >= 6: loai = "🟢🟢 TÍCH CỰC"
        else: loai = "🟢 TÍCH CỰC"
        gold = "🥇 Vàng: 🔴 GIẢM (risk-on)"
        crypto = "₿ Crypto: 🟢 TĂNG (risk-on)"
        usd = "💵 USD: 🔴 GIẢM (risk-on)"
        advice = "✅ ƯU TIÊN LONG"
    
    return {'loai': loai, 'gold': gold, 'crypto': crypto, 'usd': usd, 'advice': advice, 'keywords': display_kw}

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
    w1, w2 = set(s1.lower().split()), set(s2.lower().split())
    if not w1 or not w2: return 0
    return len(w1 & w2) / len(w1 | w2)

def clean_html(text):
    if not text: return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = unescape(text)
    return text.strip()

def fetch_rss_news(log):
    all_news = []
    for url, source_name in RSS_FEEDS:
        try:
            r = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            if r.status_code != 200: continue
            root = ET.fromstring(r.content)
            items = root.findall('.//item')
            if not items: items = root.findall('.//{http://www.w3.org/2005/Atom}entry')
            for item in items[:5]:
                title_el = item.find('title'); desc_el = item.find('description')
                link_el = item.find('link'); date_el = item.find('pubDate')
                if title_el is None: title_el = item.find('{http://www.w3.org/2005/Atom}title')
                if desc_el is None: desc_el = item.find('{http://www.w3.org/2005/Atom}summary')
                if link_el is None: link_el = item.find('{http://www.w3.org/2005/Atom}link')
                if date_el is None: date_el = item.find('{http://www.w3.org/2005/Atom}updated') or item.find('{http://www.w3.org/2005/Atom}published')
                
                title = title_el.text if title_el is not None else ''
                description = clean_html(desc_el.text) if desc_el is not None and desc_el.text else ''
                link = link_el.get('href') if link_el is not None and link_el.get('href') else (link_el.text if link_el is not None else '')
                pubdate = date_el.text if date_el is not None else ''
                
                if not title or link in log['news_sent']: continue
                result = phan_tich_tin(title, description)
                if result is None: continue
                if any(similarity(title, e.get('title_en', '')) > 0.5 for e in all_news): continue
                
                log['news_sent'].append(link)
                all_news.append({
                    'title_vi': dich_tieng_viet_chuan(title), 'title_en': title,
                    'description': description, 'source': source_name,
                    'date': format_date(pubdate) if pubdate else '',
                    'loai': result['loai'], 'gold': result['gold'],
                    'crypto': result['crypto'], 'usd': result['usd'],
                    'advice': result['advice'], 'keywords': result['keywords']
                })
        except: continue
    return all_news

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
                if any(b in source_name.lower().replace(' ', '') for b in BLOCKED_SOURCES): continue
                
                title = a.get('title', '')
                description = a.get('description', '') or ''
                published = a.get('publishedAt', '')
                
                result = phan_tich_tin(title, description)
                if result is None: continue
                if any(similarity(title, e.get('title_en', '')) > 0.5 for e in all_news): continue
                
                log['news_sent'].append(url_news)
                all_news.append({
                    'title_vi': dich_tieng_viet_chuan(title), 'title_en': title,
                    'description': description, 'source': source_name,
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
        dup = False
        for existing in all_news:
            if similarity(api_item.get('title_en', ''), existing.get('title_en', '')) > 0.5:
                if any(t in api_item['source'].lower() for t in TRUSTED_SOURCES) and \
                   not any(t in existing['source'].lower() for t in TRUSTED_SOURCES):
                    all_news.remove(existing); all_news.append(api_item)
                dup = True; break
        if not dup: all_news.append(api_item)
    
    log['news_sent'] = log['news_sent'][-500:]; save_log(log)
    
    priority = {'CỰC KỲ TIÊU CỰC':0, 'RẤT TIÊU CỰC':1, 'TIÊU CỰC':2, 'TÍCH CỰC':3, 'CỰC KỲ TÍCH CỰC':4}
    def sk(n):
        lt = n['loai'].split()[-1] if 'CỰC' in n['loai'] else n['loai'].split()[-1]
        p = priority.get(lt, 3)
        t = 0 if any(x in n['source'].lower() for x in TRUSTED_SOURCES) else 1
        return (p, t)
    all_news.sort(key=sk)
    return all_news[:MAX_NEWS]

def tom_tat_tieng_viet(description, keywords):
    parts = []
    if keywords: parts.append(f"🔑 <b>Từ khóa:</b> {', '.join(keywords)}")
    if description:
        desc = clean_html(description)
        first = desc.split('.')[0].strip()
        if len(first) > 15: parts.append(f"📝 {first}.")
    return "\n".join(parts) if parts else ""

def market_summary(news_list):
    if not news_list: return None
    neg = sum(1 for n in news_list if 'TIÊU CỰC' in n['loai'])
    pos = sum(1 for n in news_list if 'TÍCH CỰC' in n['loai'])
    total = len(news_list)
    neg_ratio = neg / total if total > 0 else 0
    
    if neg_ratio >= 0.8: level = "RẤT CAO 🔴"; advice = "⚠️ <b>ƯU TIÊN SHORT</b>"
    elif neg_ratio >= 0.6: level = "CAO 🟠"; advice = "⚠️ <b>NGHIÊNG VỀ SHORT</b>"
    elif neg_ratio >= 0.4: level = "TRUNG BÌNH 🟡"; advice = "➡️ <b>THEO DÕI THÊM</b>"
    elif pos >= total * 0.6: level = "THẤP (TÍCH CỰC) 🟢"; advice = "✅ <b>ƯU TIÊN LONG</b>"
    else: level = "TRUNG BÌNH 🟡"; advice = "➡️ <b>THEO DÕI THÊM</b>"
    
    all_kw = []
    for n in news_list: all_kw.extend(n['keywords'])
    top_kw = list(set(all_kw))[:6]
    
    return f"📰 <b>TỔNG QUAN THỊ TRƯỜNG</b>\n━━━━━━━━━━━━━━━━━━\n🚨 Mức độ: <b>{level}</b>\n📊 Tiêu cực: {neg}/{total} | Tích cực: {pos}/{total}\n💡 {advice}\n\n🔑 Từ khóa: {', '.join(top_kw)}\n\n{now_str()}"

# ============================================
# EVENTS (giữ nguyên)
# ============================================
EVENTS = [
    {'id':'fomc_minutes_jun','name':'📋 Biên bản họp FOMC (T6)','date':'2026-06-04','time':'01:00','impact':'🟡 TRUNG BÌNH','desc':'Biên bản cuộc họp FOMC tháng 6.','fred':'DFF','is_fomc':True},
    {'id':'nfp_may','name':'💼 Bảng lương NFP (T5)','date':'2026-06-05','time':'19:30','impact':'🔴 CAO','desc':'Báo cáo việc làm phi nông nghiệp Mỹ.','fred':'UNRATE','is_fomc':False},
    {'id':'cpi_may','name':'📊 Chỉ số CPI (T5)','date':'2026-06-11','time':'19:30','impact':'🔴 CAO','desc':'Chỉ số giá tiêu dùng - thước đo lạm phát.','fred':'CPIAUCSL','is_fomc':False},
    {'id':'ppi_may','name':'🏭 Chỉ số PPI (T5)','date':'2026-06-12','time':'19:30','impact':'🟡 TRUNG BÌNH','desc':'Chỉ số giá sản xuất.','fred':'PPIACO','is_fomc':False},
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
        
        if 0 <= days <= 5:
            key = f"pre_{ev['id']}"
            if time.time() - log['events'].get(key, 0) >= 21600:
                log['events'][key] = time.time()
                cd = f"⚠️ <b>HÔM NAY</b> lúc {ev['time']} (giờ VN)" if days==0 else \
                     f"📅 <b>NGÀY MAI</b> lúc {ev['time']} (giờ VN)" if days==1 else \
                     f"📅 Còn <b>{days} ngày</b> - {ev['date']} lúc {ev['time']} (giờ VN)"
                
                fw_text = ""
                if ev.get('is_fomc') and fedwatch:
                    fw_text = f"\n\n📊 <b>PHÂN TÍCH LÃI SUẤT ({fedwatch['source']}):</b>\n{fedwatch['trend']}\n{fedwatch['prediction']}\n🏦 Hiện tại: {fedwatch['current_rate']}"
                
                msgs.append(f"📅 <b>{ev['name']}</b>\n━━━━━━━━━━━━━━━━━━\n⏰ {cd}\n⚡ Mức độ: {ev['impact']}\n📝 {ev['desc']}{fw_text}\n\n📊 <b>DỮ LIỆU KINH TẾ:</b>\n{econ_summary()}\n\n{now_str()}")
        
        elif days < 0 and 1 <= hours_since <= 24:
            key = f"post_{ev['id']}"
            if key not in log['events'] and fred_ok():
                v = fred_get(ev['fred'])
                if v and len(v) >= 2:
                    curr, prev = v[0]['v'], v[1]['v']
                    
                    if 'fomc' in ev['id'] and 'minutes' not in ev['id']:
                        ket_qua = f"📈 <b>TĂNG</b> từ {prev}% lên {curr}%" if curr > prev else \
                                  f"📉 <b>GIẢM</b> từ {prev}% xuống {curr}%" if curr < prev else \
                                  f"➡️ <b>GIỮ NGUYÊN</b> ở mức {curr}%"
                        tac_dong = "🦅 Hawkish" if curr > prev else "🕊️ Dovish" if curr < prev else "➡️ Trung lập"
                    elif 'gdp' in ev['id']:
                        pct = round((curr-prev)/prev*100, 2)
                        ket_qua = f"📈 <b>TĂNG {pct}%</b>" if curr > prev else f"📉 <b>GIẢM {abs(pct)}%</b>"
                        tac_dong = "✅ Tích cực" if curr > prev else "⚠️ Tiêu cực"
                    elif 'nfp' in ev['id']:
                        ket_qua = f"📈 <b>{curr}%</b>" if curr > prev else f"📉 <b>{curr}%</b>" if curr < prev else f"➡️ <b>{curr}%</b>"
                        tac_dong = "⚠️ Lao động yếu" if curr > prev else "✅ Lao động mạnh" if curr < prev else "➡️ Ổn định"
                    elif 'cpi' in ev['id']:
                        pct = round(abs(curr-prev)/prev*100, 1)
                        ket_qua = f"📈 <b>TĂNG {pct}%</b>: {curr}" if curr > prev else f"📉 <b>GIẢM {pct}%</b>: {curr}" if curr < prev else f"➡️ <b>{curr}</b>"
                        tac_dong = "⚠️ Lạm phát nóng" if curr > prev else "✅ Lạm phát hạ nhiệt" if curr < prev else "➡️ Ổn định"
                    elif 'ppi' in ev['id']:
                        pct = round(abs(curr-prev)/prev*100, 1)
                        ket_qua = f"📈 <b>TĂNG {pct}%</b>: {curr}" if curr > prev else f"📉 <b>GIẢM {pct}%</b>: {curr}" if curr < prev else f"➡️ <b>{curr}</b>"
                        tac_dong = "⚠️ Áp lực giá" if curr > prev else "✅ Giảm áp lực" if curr < prev else "➡️ Ổn định"
                    else:
                        ket_qua = f"<b>{curr}</b>"
                        tac_dong = "Đã cập nhật"
                    
                    log['events'][key] = time.time()
                    msgs.append(f"✅ <b>{ev['name']} - KẾT QUẢ</b>\n━━━━━━━━━━━━━━━━━━\n⏰ {ev['date']} lúc {ev['time']}\n\n📊 <b>KẾT QUẢ:</b>\n{ket_qua}\n🎤 {tac_dong}\n\n📊 <b>DỮ LIỆU KINH TẾ:</b>\n{econ_summary()}\n\n{now_str()}")
    
    save_log(log)
    return msgs

# ============================================
# MAIN
# ============================================
print("="*60)
print("BOT TIN TUC PRO - FINAL")
print("="*60)

# Gui khoi dong
gui(f"📰 <b>Bot Tin Tức đã khởi động!</b>\n━━━━━━━━━━━━━━━━━━\n📡 FRED + NewsAPI + RSS\n📊 Theo dõi sự kiện kinh tế & địa chính trị\n⏰ Cập nhật mỗi 6h\n{dominance_text()}\n\n{now_str()}")

while True:
    try:
        s = get_state()
        now_ts = time.time()
        
        if not s['started'] or (now_ts - s['last_update'] >= CHU_KY):
            set_state(started=True, last_update=now_ts)
            if 'started_ever' not in s: set_state(started_ever=True)
            
            news = fetch_all_news()
            label = "đã khởi động" if s.get('started_ever') else "cập nhật 6h"
            rss_count = sum(1 for n in news if n['source'] in ['Reuters', 'CNBC', 'CoinDesk', 'Cointelegraph', 'MarketWatch'])
            dom_text = dominance_text()
            
            gui(f"📰 <b>BẢN TIN THỊ TRƯỜNG {label}!</b>\n━━━━━━━━━━━━━━━━━━\n📡 FRED: {'✅' if fred_ok() else '⏳'} | RSS: ✅ {rss_count} tin | NewsAPI: ✅\n\n📊 <b>DỮ LIỆU KINH TẾ:</b>\n{econ_summary()}{dom_text}\n\n📋 Phát hiện <b>{len(news)} tin</b>\n\n{now_str()}")
            
            if news:
                summary = market_summary(news)
                if summary: gui(summary)
                
                for n in news:
                    tom_tat = tom_tat_tieng_viet(n.get('description', ''), n['keywords'])
                    date_line = f"\n📅 {n['date']}" if n['date'] else ""
                    
                    msg = f"📰 TIN TỨC {n['loai']}\n━━━━━━━━━━━━━━━━━━\n"
                    msg += f"🇻🇳 <b>{n['title_vi']}</b>\n\n"
                    if tom_tat: msg += f"{tom_tat}\n\n"
                    msg += f"📡 Nguồn: {n['source']}{date_line}\n"
                    msg += f"🇬🇧 {n['title_en']}\n\n"
                    msg += f"🏦 <b>Dự báo:</b>\n{n['gold']}\n{n['crypto']}\n{n['usd']}\n\n"
                    msg += f"💡 {n['advice']}\n\n{now_str()}"
                    gui(msg)
                    time.sleep(1)
            
            for m in check_events():
                gui(m)
            
            try:
                r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
                d = r.json()['data'][0]
                v, c = int(d['value']), d['value_classification']
                i = "😱" if v<=25 else "😟" if v<=40 else "😐" if v<=60 else "😊" if v<=75 else "🤤"
                gui(f"{i} <b>Sợ hãi & Tham lam:</b> {v}/100 ({c})\n\n{now_str()}")
            except: pass
        
        time.sleep(60)
    except KeyboardInterrupt: break
    except Exception as e:
        print(f"Lỗi: {e}")
        time.sleep(30)