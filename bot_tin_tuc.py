"""
BOT TIN TUC V2 - RSS + FRED + EVENTS - FINAL
- 8 nguồn RSS: Reuters, CNBC, CoinDesk, Cointelegraph, MarketWatch, BBC, Financial Times
- Sự kiện kinh tế: FRED API (FOMC, CPI, NFP, GDP, PPI)
- Dịch tiếng Việt: Google Translate + từ điển tài chính
- Context analysis: hiểu ngữ cảnh thị trường
- FILTER HOT NEWS: chỉ tin nóng, không phân tích/opinion
- FIX TRIỆT ĐỂ: dùng memory lock chống trùng lặp
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

TOKEN = os.getenv("TELEGRAM_TOKEN", "8893995280:AAF9XwWAm9QgPkwmDrhZdY6UQ4zfySooWpk")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "518284897")
FRED_API_KEY = os.getenv("FRED_API_KEY", "ff3e122af2b2c0a433606476fc6dc5fb")

CHU_KY = 21600
MAX_NEWS = 10
DATA_DIR = "data"
STATE_FILE = f"{DATA_DIR}/state_news.json"
LOG_FILE = f"{DATA_DIR}/log_news.json"

RSS_FEEDS = [
    ("https://feeds.reuters.com/reuters/businessNews", "Reuters"),
    ("https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01", "CNBC"),
    ("https://feeds.marketwatch.com/marketwatch/topstories", "MarketWatch"),
    ("https://www.ft.com/world?format=rss", "Financial Times"),
    ("https://www.coindesk.com/arc/outboundfeeds/news/", "CoinDesk"),
    ("https://cointelegraph.com/rss", "Cointelegraph"),
    ("https://feeds.bbci.co.uk/news/world/rss.xml", "BBC World"),
    ("https://feeds.bbci.co.uk/news/business/rss.xml", "BBC Business"),
]

BLOCKED_SOURCES = [
    "naturalnews.com", "beforeitsnews.com", "infowars.com", "zerohedge.com",
    "foxnews.com", "newsmax.com", "oann.com", "breitbart.com"
]

TRUSTED_SOURCES = [
    "reuters.com", "bloomberg.com", "cnbc.com", "wsj.com", "ft.com",
    "coindesk.com", "cointelegraph.com", "marketwatch.com",
    "investing.com", "forexlive.com", "apnews.com", "bbc.com", "bbc.co.uk"
]

NON_MARKET_KW = [
    "generational war", "culture war", "boomer", "gen z",
    "tiktok", "influencer", "celebrity", "royal family",
    "sports", "gaming", "movie", "netflix", "disney",
    "grammy", "oscar", "emmy", "super bowl", "world cup", "nfl", "nba"
]

ANALYSIS_KW = [
    'analysis', 'opinion', 'essay', 'commentary', 'editorial',
    'what if', 'could', 'might', 'may lead to',
    'explainer', 'explained', 'guide to', 'how to',
    'review', 'retrospect', 'legacy', 'history of',
    'here is why', 'here are', 'everything you need to know',
    'what to expect', 'what we know', 'what happens next',
    'why the', 'how the', 'when the', 'where the',
    'is this the end', 'can it', 'will it', 'should you'
]

def is_hot_news(title, description=""):
    full_text = (title + " " + description).lower()
    if any(kw in full_text for kw in ANALYSIS_KW):
        return False
    return True

os.makedirs(DATA_DIR, exist_ok=True)

# ============================================
# TIỆN ÍCH
# ============================================
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

def save_log(data):
    with open(LOG_FILE, 'w') as f: json.dump(data, f, ensure_ascii=False, indent=2)

def gui(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
    except: pass

def now_str():
    n = datetime.now()
    return (
        f"🕐 {n.strftime('%H:%M')} (Asia) | "
        f"{(n - timedelta(hours=5)).strftime('%H:%M')} (EU) | "
        f"{(n - timedelta(hours=11)).strftime('%H:%M')} (US) | "
        f"{n.strftime('%d/%m/%Y')}"
    )

def clean_html(text):
    if not text: return ""
    text = re.sub(r'<[^>]+>', '', text)
    return unescape(text).strip()

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
# FRED API
# ============================================
def fred_get(series_id):
    try:
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {"series_id": series_id, "api_key": FRED_API_KEY, "file_type": "json", "limit": 2, "sort_order": "desc"}
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            observations = r.json().get('observations', [])
            result = []
            for obs in observations:
                if obs.get('value', '.') != '.':
                    result.append({'date': obs['date'], 'value': float(obs['value'])})
            return result
    except: pass
    return None

def econ_summary():
    indicators = [
        ('DFF','<b>Lãi suất Fed:</b> {}%'), ('CPIAUCSL','<b>CPI:</b> {}'),
        ('UNRATE','<b>Thất nghiệp:</b> {}%'), ('GDP','<b>GDP:</b> ${:,.0f}B'), ('PPIACO','<b>PPI:</b> {}')
    ]
    parts = []
    for sid, fmt in indicators:
        data = fred_get(sid)
        if data: parts.append(fmt.format(data[0]['value']))
    return " | ".join(parts) if parts else "Đang tải..."

# ============================================
# FEDWATCH
# ============================================
def get_fedwatch_prediction():
    fed_data = fred_get('DFF')
    if not fed_data: return None
    current_rate = fed_data[0]['value']
    if len(fed_data) >= 2:
        prev_rate = fed_data[1]['value']
        if current_rate > prev_rate: trend = f"📈 Lãi suất đang <b>TĂNG</b> (từ {prev_rate}% → {current_rate}%)"
        elif current_rate < prev_rate: trend = f"📉 Lãi suất đang <b>GIẢM</b> (từ {prev_rate}% → {current_rate}%)"
        else: trend = f"➡️ Lãi suất đang <b>ỔN ĐỊNH</b> ở mức {current_rate}%"
    else: trend = f"➡️ Lãi suất hiện tại: <b>{current_rate}%</b>"
    cpi_data = fred_get('CPIAUCSL')
    if cpi_data and len(cpi_data) >= 2:
        cpi_change = round((cpi_data[0]['value']-cpi_data[1]['value'])/cpi_data[1]['value']*100,1)
        if cpi_change > 0.3: prediction = f"⚠️ CPI tăng <b>{cpi_change}%</b> → Áp lực <b>TĂNG</b> lãi suất"
        elif cpi_change < -0.3: prediction = f"✅ CPI giảm <b>{abs(cpi_change)}%</b> → Có thể <b>GIẢM</b> lãi suất"
        else: prediction = f"➡️ CPI ổn định → Dự kiến <b>GIỮ NGUYÊN</b> lãi suất"
    else: prediction = "➡️ Chưa có dữ liệu CPI → Dự kiến <b>GIỮ NGUYÊN</b>"
    return {'current_rate':f"{current_rate}%",'trend':trend,'prediction':prediction}

# ============================================
# PHÂN TÍCH TIN TỨC
# ============================================
def is_market_news(title):
    for kw in NON_MARKET_KW:
        if kw in title.lower(): return False
    return True

CONTEXT_POSITIVE = [
    "ceasefire","truce","peace deal","peace talk","reopening","withdrawal",
    "rate cut","dovish","easing","stimulus","rebound","recover",
    "surge","soar","rally","record high","bull market",
    "etf approved","etf inflow","institutional","adoption",
    "oil prices drop","oil prices fall","oil prices decline",
    "stock surge","stock rally","market rally",
    "gold decline","gold drop","gold fall",
]

CONTEXT_NEGATIVE = [
    "war intensifies","missile strike","missile attack","airstrike","invasion",
    "oil prices surge","oil prices rise","oil prices spike",
    "rate hike","hawkish","tightening","recession","depression",
    "crash","collapse","plunge","tumble","slump",
    "etf outflow","sanction imposed","tariff imposed",
    "nuclear threat","military escalation",
    "stock plunge","stock crash","market crash","market turmoil",
    "gold surge","gold soar","gold spike",
]

POSITIVE_KW = [
    "rate cut","dovish","easing","ceasefire","peace deal","peace talk",
    "truce","withdrawal","bull market","rally","etf approved",
    "etf inflow","blackrock","institutional","adoption",
    "stimulus","rebound","recover","surge","soar"
]

NEGATIVE_KW = [
    "war","strike","missile","bomb","airstrike","attack","invasion",
    "nuclear","sanction","embargo","tariff","trade war",
    "rate hike","hawkish","tightening","recession","depression","crash",
    "collapse","etf outflow","hormuz",
    "escalation","conflict","tensions","plunge","tumble","slump"
]

def has_keyword(text, word): return bool(re.search(r'\b'+re.escape(word)+r'\b', text.lower()))

def analyze_sentiment(title, description=""):
    if not is_market_news(title): return None
    text = (title+" "+description).lower()
    pos_context = sum(1 for ctx in CONTEXT_POSITIVE if ctx in text)
    neg_context = sum(1 for ctx in CONTEXT_NEGATIVE if ctx in text)
    pos_kw = [kw for kw in POSITIVE_KW if has_keyword(text, kw)]
    neg_kw = [kw for kw in NEGATIVE_KW if has_keyword(text, kw)]
    pos_score = pos_context*3 + len(pos_kw); neg_score = neg_context*3 + len(neg_kw)
    if pos_score == 0 and neg_score == 0: return None
    display_kw = []
    for ctx in CONTEXT_POSITIVE:
        if ctx in text and len(display_kw)<3: display_kw.append(ctx)
    for ctx in CONTEXT_NEGATIVE:
        if ctx in text and len(display_kw)<3: display_kw.append(ctx)
    if not display_kw: display_kw = pos_kw[:3] if pos_kw else neg_kw[:3]
    display_kw = list(set(display_kw))[:3]
    if neg_score > pos_score:
        if neg_score >= 9: loai = "🔴🔴🔴 CỰC KỲ TIÊU CỰC"
        elif neg_score >= 6: loai = "🔴🔴 RẤT TIÊU CỰC"
        else: loai = "🔴 TIÊU CỰC"
        gold = "🥇 Vàng: 🟢 TĂNG (trú ẩn)"; crypto = "₿ Crypto: 🔴 GIẢM (risk-off)"; usd = "💵 USD: 🟢 TĂNG (trú ẩn)"; advice = "⚠️ ƯU TIÊN SHORT"
    else:
        if pos_score >= 9: loai = "🟢🟢🟢 CỰC KỲ TÍCH CỰC"
        elif pos_score >= 6: loai = "🟢🟢 TÍCH CỰC"
        else: loai = "🟢 TÍCH CỰC"
        gold = "🥇 Vàng: 🔴 GIẢM (risk-on)"; crypto = "₿ Crypto: 🟢 TĂNG (risk-on)"; usd = "💵 USD: 🔴 GIẢM (risk-on)"; advice = "✅ ƯU TIÊN LONG"
    return {'loai':loai,'gold':gold,'crypto':crypto,'usd':usd,'advice':advice,'keywords':display_kw}

# ============================================
# DỊCH TIẾNG VIỆT
# ============================================
FIX_DICH = {
    "tỷ lệ cắt":"hạ lãi suất","cắt giảm lãi suất":"hạ lãi suất","tỷ lệ tăng":"tăng lãi suất",
    "chợ bò":"thị trường tăng","chợ gấu":"thị trường giảm","tiền điện tử":"crypto","tiền mã hóa":"crypto",
    "chuỗi khối":"blockchain","dòng tiền chảy ra":"dòng vốn ETF ra","dòng tiền chảy vào":"dòng vốn ETF vào",
    "trú ẩn an toàn":"tài sản trú ẩn","eo biển hormuz":"eo biển Hormuz","cục dự trữ liên bang":"Fed",
    "quỹ giao dịch trao đổi":"ETF","bảng lương phi nông nghiệp":"bảng lương NFP",
    "chỉ số giá tiêu dùng":"CPI","chỉ số giá sản xuất":"PPI","tổng sản phẩm quốc nội":"GDP",
    "phố wall":"Phố Wall","nhà trắng":"Nhà Trắng","lầu năm góc":"Lầu Năm Góc","điện kremlin":"Điện Kremlin",
    "vốn hóa thị trường":"vốn hóa","thị trường chứng khoán":"chứng khoán","lợi suất trái phiếu":"lợi suất",
    "dầu thô":"dầu","giá dầu":"giá dầu",
}

def dich_tieng_viet(text):
    if not text: return ""
    try:
        r = requests.get("https://translate.googleapis.com/translate_a/single", params={'client':'gtx','sl':'en','tl':'vi','dt':'t','q':text}, timeout=5)
        if r.status_code == 200: translated = ''.join([s[0] for s in r.json()[0] if s[0]])
        else: return text
    except: return text
    for wrong, correct in FIX_DICH.items(): translated = re.sub(r'\b'+re.escape(wrong)+r'\b', correct, translated, flags=re.IGNORECASE)
    if translated and len(translated) > 1: translated = translated[0].upper() + translated[1:]
    return translated

# ============================================
# FETCH RSS - CHỐNG TRÙNG TUYỆT ĐỐI
# ============================================
def fetch_rss_news(log):
    all_news = []
    all_links = []
    
    for url, source_name in RSS_FEEDS:
        try:
            r = requests.get(url, timeout=10, headers={'User-Agent':'Mozilla/5.0'})
            if r.status_code != 200: continue
            root = ET.fromstring(r.content)
            items = root.findall('.//item')
            if not items: items = root.findall('.//{http://www.w3.org/2005/Atom}entry')
            
            for item in items[:5]:
                title_el = item.find('title')
                if title_el is None: title_el = item.find('{http://www.w3.org/2005/Atom}title')
                title = title_el.text if title_el is not None else ''
                
                desc_el = item.find('description')
                if desc_el is None: desc_el = item.find('{http://www.w3.org/2005/Atom}summary')
                description = clean_html(desc_el.text) if desc_el is not None and desc_el.text else ''
                
                link_el = item.find('link')
                if link_el is None: link_el = item.find('{http://www.w3.org/2005/Atom}link')
                link = ""
                if link_el is not None: link = link_el.get('href') or link_el.text or ''
                
                date_el = item.find('pubDate')
                if date_el is None:
                    date_el = item.find('{http://www.w3.org/2005/Atom}updated')
                    if date_el is None: date_el = item.find('{http://www.w3.org/2005/Atom}published')
                pubdate = date_el.text if date_el is not None else ''
                
                if not title: continue
                if link and link in log['news_sent']: continue
                if link and link in all_links: continue
                if not is_hot_news(title, description): continue
                
                result = analyze_sentiment(title, description)
                if result is None: continue
                
                is_dup = False
                for existing in all_news:
                    w1 = set(title.lower().split()); w2 = set(existing['title_en'].lower().split())
                    if not w1 or not w2: continue
                    if len(w1 & w2) / len(w1 | w2) > 0.5: is_dup = True; break
                if is_dup: continue
                
                log['news_sent'].append(link)
                all_links.append(link)
                all_news.append({
                    'title_vi':dich_tieng_viet(title),'title_en':title,'description':description,
                    'source':source_name,'date':format_date(pubdate) if pubdate else '',
                    'loai':result['loai'],'gold':result['gold'],'crypto':result['crypto'],
                    'usd':result['usd'],'advice':result['advice'],'keywords':result['keywords']
                })
        except: continue
    return all_news

def fetch_all_news():
    log = get_log(); log['news_sent'] = []
    all_news = fetch_rss_news(log)
    log['news_sent'] = log['news_sent'][-500:]; save_log(log)
    priority = {'CỰC KỲ TIÊU CỰC':0,'RẤT TIÊU CỰC':1,'TIÊU CỰC':2,'TÍCH CỰC':3,'CỰC KỲ TÍCH CỰC':4}
    def sk(n):
        lt = n['loai'].split()[-1] if 'CỰC' in n['loai'] else n['loai'].split()[-1]
        return (priority.get(lt,3), 0 if any(s in n['source'].lower() for s in TRUSTED_SOURCES) else 1)
    all_news.sort(key=sk)
    return all_news[:MAX_NEWS]

# ============================================
# SỰ KIỆN KINH TẾ
# ============================================
EVENTS = [
    {'id':'fomc_minutes_jun','name':'📋 Biên bản họp FOMC (T6)','date':'2026-06-04','time':'01:00','impact':'🟢 THẤP','desc':'Biên bản cuộc họp cũ - không có quyết định mới.','fred':'DFF','is_fomc':False},
    {'id':'nfp_may','name':'💼 Bảng lương NFP (T5)','date':'2026-06-05','time':'19:30','impact':'🔴 CAO','desc':'Báo cáo việc làm phi nông nghiệp - chỉ báo sức khỏe kinh tế Mỹ.','fred':'UNRATE','is_fomc':False,'advice':'NFP > dự đoán → Kinh tế mạnh → 🟢 LONG Crypto\nNFP < dự đoán → Kinh tế yếu → 🔴 SHORT Crypto','gold':'NFP cao → USD mạnh → Vàng GIẢM','crypto':'NFP cao → Kinh tế tốt → Crypto TĂNG','usd':'NFP cao → USD TĂNG'},
    {'id':'cpi_may','name':'📊 Chỉ số CPI (T5)','date':'2026-06-11','time':'19:30','impact':'🔴 CAO','desc':'Chỉ số giá tiêu dùng - thước đo lạm phát quan trọng nhất.','fred':'CPIAUCSL','is_fomc':False,'advice':'CPI thấp hơn dự đoán → Fed dovish → 🟢 LONG Crypto\nCPI cao hơn dự đoán → Fed hawkish → 🔴 SHORT Crypto','gold':'CPI cao → Vàng TĂNG (hedge lạm phát)','crypto':'CPI cao → lo tăng lãi suất → Crypto GIẢM','usd':'CPI cao → USD TĂNG (kỳ vọng hawkish)'},
    {'id':'ppi_may','name':'🏭 Chỉ số PPI (T5)','date':'2026-06-12','time':'19:30','impact':'🟡 TRUNG BÌNH','desc':'Chỉ số giá sản xuất - chỉ báo sớm của lạm phát.','fred':'PPIACO','is_fomc':False,'advice':'PPI tăng → áp lực lạm phát → thận trọng\nPPI giảm → tích cực cho Crypto','gold':'PPI cao → Vàng TĂNG nhẹ','crypto':'PPI cao → Crypto GIẢM nhẹ','usd':'PPI cao → USD TĂNG nhẹ'},
    {'id':'fomc_jun','name':'🏦 Quyết định lãi suất FOMC (T6)','date':'2026-06-18','time':'01:00','impact':'🔴 CAO - SỰ KIỆN QUAN TRỌNG NHẤT THÁNG','desc':'Fed công bố quyết định tăng/giảm/giữ nguyên lãi suất.','fred':'DFF','is_fomc':True,'advice':'Nếu GIỮ NGUYÊN → 🟢 LONG Crypto\nNếu TĂNG → 🔴 SHORT Crypto\nNếu GIẢM → 🟢 LONG mạnh Crypto\nĐóng bot 30p trước sự kiện!','gold':'Hawkish → Vàng GIẢM | Dovish → Vàng TĂNG','crypto':'Hawkish → Crypto GIẢM | Dovish → Crypto TĂNG','usd':'Hawkish → USD TĂNG | Dovish → USD GIẢM'},
    {'id':'gdp_q2','name':'📊 GDP Quý 2/2026','date':'2026-06-25','time':'19:30','impact':'🔴 CAO','desc':'Tăng trưởng kinh tế Mỹ quý 2/2026.','fred':'GDP','is_fomc':False,'advice':'GDP cao → Kinh tế mạnh → 🟢 LONG Crypto\nGDP thấp → Suy thoái → 🔴 SHORT Crypto','gold':'GDP cao → Vàng GIẢM (risk-on)','crypto':'GDP cao → Crypto TĂNG','usd':'GDP cao → USD TĂNG'},
    {'id':'fomc_jul','name':'🏦 Quyết định lãi suất FOMC (T7)','date':'2026-07-30','time':'01:00','impact':'🔴 CAO - SỰ KIỆN QUAN TRỌNG','desc':'Quyết định lãi suất Fed giữa năm 2026.','fred':'DFF','is_fomc':True,'advice':'Nếu GIỮ NGUYÊN → 🟢 LONG Crypto\nNếu TĂNG → 🔴 SHORT Crypto\nĐóng bot 30p trước sự kiện!','gold':'Hawkish → Vàng GIẢM | Dovish → Vàng TĂNG','crypto':'Hawkish → Crypto GIẢM | Dovish → Crypto TĂNG','usd':'Hawkish → USD TĂNG | Dovish → USD GIẢM'},
]

def check_events():
    log = get_log(); now = datetime.now(); today = now.date(); messages = []
    fedwatch = get_fedwatch_prediction()
    for ev in EVENTS:
        evd = datetime.strptime(ev['date'],'%Y-%m-%d').date()
        evdt = datetime.strptime(ev['date']+' '+ev['time'],'%Y-%m-%d %H:%M')
        days = (evd - today).days
        hours_since = (now - evdt).total_seconds()/3600 if evdt < now else -1
        if 0 <= days <= 5:
            key = f"pre_{ev['id']}"
            if time.time() - log['events'].get(key,0) >= 21600:
                log['events'][key] = time.time()
                cd = f"⚠️ <b>HÔM NAY</b> lúc {ev['time']} (giờ VN)" if days==0 else f"📅 <b>NGÀY MAI</b> lúc {ev['time']} (giờ VN)" if days==1 else f"📅 Còn <b>{days} ngày</b> - {ev['date']} lúc {ev['time']} (giờ VN)"
                fw_text = ""
                if ev.get('is_fomc') and fedwatch: fw_text = f"\n\n📊 <b>PHÂN TÍCH LÃI SUẤT (FRED):</b>\n{fedwatch['trend']}\n{fedwatch['prediction']}\n🏦 Hiện tại: {fedwatch['current_rate']}"
                tac_dong = ""
                if ev.get('gold') or ev.get('crypto') or ev.get('usd'):
                    tac_dong = "\n\n📊 <b>TÁC ĐỘNG DỰ KIẾN:</b>\n"
                    if ev.get('gold'): tac_dong += f"🥇 Vàng: {ev['gold']}\n"
                    if ev.get('crypto'): tac_dong += f"₿ Crypto: {ev['crypto']}\n"
                    if ev.get('usd'): tac_dong += f"💵 USD: {ev['usd']}\n"
                chien_luoc = ""
                if ev.get('advice'): chien_luoc = f"\n💡 <b>CHIẾN LƯỢC:</b>\n{ev['advice']}\n"
                messages.append(f"📅 <b>{ev['name']}</b>\n━━━━━━━━━━━━━━━━━━\n⏰ {cd}\n⚡ Mức độ: {ev['impact']}\n📝 {ev['desc']}{fw_text}{tac_dong}{chien_luoc}\n━━━━━━━━━━━━━━━━━━\n📊 <b>DỮ LIỆU KINH TẾ HIỆN TẠI:</b>\n{econ_summary()}\n\n{now_str()}")
        elif days < 0 and 1 <= hours_since <= 24:
            key = f"post_{ev['id']}"
            if key not in log['events']:
                data = fred_get(ev['fred'])
                if data and len(data) >= 2:
                    curr = data[0]['value']; prev = data[1]['value']
                    if 'fomc' in ev['id'] and 'minutes' not in ev['id']:
                        if curr > prev: ket_qua = f"📈 <b>Fed TĂNG lãi suất</b> từ {prev}% lên {curr}%"; tac_dong = "🦅 <b>HAWKISH</b>"; hanh_dong = "🔴 SHORT Crypto"
                        elif curr < prev: ket_qua = f"📉 <b>Fed GIẢM lãi suất</b> từ {prev}% xuống {curr}%"; tac_dong = "🕊️ <b>DOVISH</b>"; hanh_dong = "🟢 LONG Crypto"
                        else: ket_qua = f"➡️ <b>Fed GIỮ NGUYÊN lãi suất</b> ở mức {curr}%"; tac_dong = "➡️ <b>TRUNG LẬP</b>"; hanh_dong = "🟢 Tích cực nhẹ"
                    elif ev['id'] == 'nfp_may': ket_qua = f"📊 <b>Thất nghiệp: {curr}%</b> (trước: {prev}%)"; tac_dong = "⚠️ Yếu" if curr > prev else "✅ Mạnh"; hanh_dong = "🟢 LONG" if curr < prev else "🔴 SHORT"
                    elif ev['id'] == 'cpi_may':
                        pct = round((curr-prev)/prev*100,1); ket_qua = f"📊 <b>CPI: {curr}</b> ({'+' if pct>0 else ''}{pct}%)"
                        tac_dong = "⚠️ Nóng" if curr > prev else "✅ Hạ nhiệt"; hanh_dong = "🟢 LONG" if curr <= prev else "🔴 SHORT"
                    elif ev['id'] == 'ppi_may': pct = round((curr-prev)/prev*100,1); ket_qua = f"📊 <b>PPI: {curr}</b> ({'+' if pct>0 else ''}{pct}%)"; tac_dong = "⚠️ Áp lực" if curr > prev else "✅ Giảm"; hanh_dong = "Theo dõi"
                    elif ev['id'] == 'gdp_q2': pct = round((curr-prev)/prev*100,2); ket_qua = f"📊 <b>GDP: ${curr:,.0f}B</b> ({'+' if pct>0 else ''}{pct}%)"; tac_dong = "✅ Tăng" if curr > prev else "⚠️ Giảm"; hanh_dong = "🟢 LONG" if curr > prev else "🔴 SHORT"
                    else: ket_qua = f"📊 <b>{curr}</b> (trước: {prev})"; tac_dong = "Đã cập nhật"; hanh_dong = "Theo dõi"
                    log['events'][key] = time.time()
                    messages.append(f"✅ <b>{ev['name']} - KẾT QUẢ THỰC TẾ</b>\n━━━━━━━━━━━━━━━━━━\n⏰ Đã diễn ra: {ev['date']} lúc {ev['time']} (giờ VN)\n\n📊 <b>KẾT QUẢ:</b>\n{ket_qua}\n\n🎤 <b>ĐÁNH GIÁ:</b>\n{tac_dong}\n\n💡 <b>HÀNH ĐỘNG:</b>\n{hanh_dong}\n━━━━━━━━━━━━━━━━━━\n📊 <b>DỮ LIỆU KINH TẾ HIỆN TẠI:</b>\n{econ_summary()}\n\n{now_str()}")
    save_log(log)
    return messages

# ============================================
# MAIN - MEMORY LOCK CHỐNG TRÙNG
# ============================================
print("="*60)
print("BOT TIN TUC V2 - RSS + FRED + EVENTS")
print("="*60)

_last_fetch_time = 0

while True:
    try:
        state = get_state()
        now_ts = time.time()
        
        # MEMORY LOCK: Chỉ fetch nếu cách lần cuối > 5 phút
        if now_ts - _last_fetch_time < 300:
            time.sleep(10)
            continue
        
        if not state['started'] or (now_ts - state['last_update'] >= CHU_KY):
            _last_fetch_time = now_ts
            set_state(started=True, last_update=now_ts)
            if 'started_ever' not in state: set_state(started_ever=True)
            
            news = fetch_all_news()
            label = "đã khởi động" if state.get('started_ever') else "cập nhật 6h"
            rss_count = sum(1 for n in news if n['source'] in ['Reuters','CNBC','CoinDesk','Cointelegraph','MarketWatch','BBC World','BBC Business','Financial Times'])
            
            gui(f"📰 <b>BẢN TIN THỊ TRƯỜNG {label}!</b>\n━━━━━━━━━━━━━━━━━━\n📡 FRED: ✅ | RSS: ✅ {rss_count} tin từ 8 nguồn\n\n📊 <b>DỮ LIỆU KINH TẾ:</b>\n{econ_summary()}\n\n📋 Phát hiện <b>{len(news)} tin</b> quan trọng\n\n{now_str()}")
            
            if news:
                neg = sum(1 for n in news if 'TIÊU CỰC' in n['loai']); pos = sum(1 for n in news if 'TÍCH CỰC' in n['loai'])
                total = len(news); neg_ratio = neg/total if total > 0 else 0
                if neg_ratio >= 0.6: level = "CAO 🔴"; advice = "⚠️ <b>NGHIÊNG VỀ SHORT</b>"
                elif pos >= total*0.6: level = "THẤP (TÍCH CỰC) 🟢"; advice = "✅ <b>ƯU TIÊN LONG</b>"
                else: level = "TRUNG BÌNH 🟡"; advice = "➡️ <b>THEO DÕI THÊM</b>"
                all_kw = []
                for n in news: all_kw.extend(n['keywords'])
                gui(f"📰 <b>TỔNG QUAN THỊ TRƯỜNG</b>\n━━━━━━━━━━━━━━━━━━\n🚨 Mức độ: <b>{level}</b>\n📊 Tiêu cực: {neg}/{total} | Tích cực: {pos}/{total}\n💡 {advice}\n\n🔑 Từ khóa: {', '.join(list(set(all_kw))[:6])}\n\n{now_str()}")
                
                for n in news:
                    date_line = f"\n📅 {n['date']}" if n['date'] else ""
                    tom_tat_parts = []
                    if n['keywords']: tom_tat_parts.append(f"🔑 <b>Từ khóa:</b> {', '.join(n['keywords'])}")
                    if n.get('description'):
                        desc = clean_html(n['description']); first_sentence = desc.split('.')[0].strip()
                        if len(first_sentence) > 15: tom_tat_parts.append(f"📝 {first_sentence}.")
                    tom_tat = "\n".join(tom_tat_parts)
                    msg = f"📰 TIN TỨC {n['loai']}\n━━━━━━━━━━━━━━━━━━\n🇻🇳 <b>{n['title_vi']}</b>\n\n"
                    if tom_tat: msg += f"{tom_tat}\n\n"
                    msg += f"📡 Nguồn: {n['source']}{date_line}\n🇬🇧 {n['title_en']}\n\n🏦 <b>Dự báo:</b>\n{n['gold']}\n{n['crypto']}\n{n['usd']}\n\n💡 {n['advice']}\n\n{now_str()}"
                    gui(msg); time.sleep(1)
            
            for msg in check_events(): gui(msg)
        
        time.sleep(60)
    except KeyboardInterrupt: print("\n👋 Đã dừng Bot Tin Tức"); break
    except Exception as e: print(f"Lỗi: {e}"); time.sleep(30)