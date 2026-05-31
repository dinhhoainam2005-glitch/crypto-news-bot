"""
BOT TIN TUC PRO - NGUON CHUAN NHA DAU TU CHUYEN NGHIEP
- Reuters, Financial Times, Foreign Policy, CSIS, ISW
- CoinDesk, Cointelegraph
- FRED (FED), BLS, IMF, World Bank API
- Filter: CHI TIN NONG, khong phan tich, khong opinion
- Format chuan: dich tieng Viet + sentiment + tac dong thi truong
- Su kien kinh te: FOMC, CPI, NFP, GDP, PPI
- Cap nhat moi 6 gio - KHONG TRUNG LAP
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
BLS_API_KEY = os.getenv("BLS_API_KEY", "")

CHU_KY = 21600
MAX_NEWS = 10
DATA_DIR = "data"
STATE_FILE = f"{DATA_DIR}/state_news_pro.json"
LOG_FILE = f"{DATA_DIR}/log_news_pro.json"

# ============================================
# NGUON CHUAN PRO - TIER 1
# ============================================
RSS_FEEDS = [
    ("https://feeds.reuters.com/reuters/businessNews", "Reuters"),
    ("https://www.ft.com/world?format=rss", "Financial Times"),
    ("https://foreignpolicy.com/feed/", "Foreign Policy"),
    ("https://www.csis.org/rss.xml", "CSIS"),
    ("https://www.understandingwar.org/press-media/rss.xml", "ISW"),
    ("https://www.coindesk.com/arc/outboundfeeds/news/", "CoinDesk"),
    ("https://cointelegraph.com/rss", "Cointelegraph"),
]

os.makedirs(DATA_DIR, exist_ok=True)

# ========== TIỆN ÍCH ==========
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

def save_log(d): 
    with open(LOG_FILE, 'w') as f: json.dump(d, f, ensure_ascii=False, indent=2)

def gui(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                     data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except: pass

def now_str():
    n = datetime.now()
    return f"🕐 {n.strftime('%H:%M')} (Asia) | {(n-timedelta(hours=5)).strftime('%H:%M')} (EU) | {(n-timedelta(hours=11)).strftime('%H:%M')} (US) | {n.strftime('%d/%m/%Y')}"

def clean_html(t):
    if not t: return ""
    return unescape(re.sub(r'<[^>]+>', '', t)).strip()

def format_date(d):
    for f in ["%Y-%m-%dT%H:%M:%SZ","%Y-%m-%dT%H:%M:%S%z","%a, %d %b %Y %H:%M:%S %z","%a, %d %b %Y %H:%M:%S %Z"]:
        try: return datetime.strptime(d, f).strftime("%d/%m/%Y %H:%M")
        except: pass
    return d[:16] if len(d)>16 else d

# ========== FRED + BLS + IMF + WORLD BANK ==========
def fred_get(sid):
    try:
        r = requests.get("https://api.stlouisfed.org/fred/series/observations",
                        params={"series_id":sid,"api_key":FRED_API_KEY,"file_type":"json","limit":2,"sort_order":"desc"}, timeout=10)
        if r.status_code==200:
            return [{'date':o['date'],'value':float(o['value'])} for o in r.json().get('observations',[]) if o.get('value','.')!='.']
    except: pass
    return None

def econ_summary():
    p = []
    for sid,f in [('DFF','<b>Lãi suất Fed:</b> {}%'),('CPIAUCSL','<b>CPI:</b> {}'),('UNRATE','<b>Thất nghiệp:</b> {}%'),('GDP','<b>GDP:</b> ${:,.0f}B'),('PPIACO','<b>PPI:</b> {}')]:
        d = fred_get(sid)
        if d: p.append(f.format(d[0]['value']))
    return " | ".join(p) if p else "Đang tải..."

# ========== FILTER TIN ==========
FINANCE_KW = [
    'crypto','bitcoin','ethereum','blockchain','defi',
    'stock','wall street','nasdaq','dow','s&p','sp500','index',
    'forex','dollar','euro','yen','yuan','pound','currency',
    'bond','treasury','yield','interest rate','fed','fomc','central bank',
    'inflation','cpi','ppi','gdp','recession','economy','economic',
    'oil','crude','gold','silver','commodity','energy',
    'etf','sec','cftc','regulation',
    'market','trade','tariff','sanction','embargo',
    'bank','imf','world bank','bis',
    'iran','israel','russia','ukraine','china','taiwan','north korea',
    'missile','war','conflict','military','nuclear','troops','strike','attack',
    'pentagon','nato','white house','kremlin','state department',
    'peace talk','ceasefire','truce','negotiation','summit',
    'supply chain','manufacturing','semiconductor','chip',
]

ANALYSIS_KW = [
    'analysis','opinion','essay','commentary','editorial','oped',
    'what if','could','might','may lead to','potentially',
    'explainer','explained','guide to','how to','why you should',
    'review','retrospect','legacy','history of','looking back',
    'here is why','here are','everything you need to know',
    'what to expect','what we know','what happens next',
    'why the','how the','when the','where the','who the',
    'is this the end','can it','will it','should you',
    'why ','how to ','when will ','where is ','what does ',
    '?','could ','might ','may ','perhaps','maybe',
    '5 things','3 reasons','top 10','top 5','weekly roundup',
]

NON_MARKET = [
    "generational war","culture war","boomer","gen z",
    "tiktok","influencer","celebrity","royal family",
    "sports","gaming","movie","netflix","disney",
    "grammy","oscar","emmy","super bowl","world cup","nfl","nba",
    "weather","hurricane","earthquake","tsunami","volcano",
    "cattle","beef","livestock","dairy","crop","harvest",
]

def is_finance_news(title, desc=""):
    t = (title+" "+desc).lower()
    return any(kw in t for kw in FINANCE_KW)

def is_hot_news(title, desc=""):
    t = (title+" "+desc).lower()
    if any(kw in t for kw in ANALYSIS_KW): return False
    if not is_finance_news(title, desc): return False
    for kw in NON_MARKET:
        if kw in t: return False
    return True

# ========== SENTIMENT ==========
POS_CTX = [
    "ceasefire","truce","peace deal","peace talk","reopening","withdrawal",
    "rate cut","dovish","easing","stimulus","rebound","recover",
    "surge","soar","rally","record high","bull market",
    "etf approved","etf inflow","institutional","adoption",
    "oil prices drop","stock surge","market rally","gold decline",
    "ending conflict","de-escalation","diplomatic solution",
]
NEG_CTX = [
    "war intensifies","missile strike","airstrike","invasion",
    "oil prices surge","rate hike","hawkish","tightening",
    "recession","depression","crash","collapse","plunge","tumble","slump",
    "etf outflow","sanction imposed","tariff imposed",
    "nuclear threat","military escalation",
    "stock crash","market crash","gold surge",
    "troops deploy","mobilization","declare war",
]
POS_KW = ["rate cut","dovish","easing","ceasefire","peace deal","peace talk","truce","withdrawal","bull market","rally","etf approved","etf inflow","blackrock","institutional","adoption","stimulus","rebound","recover","surge","soar"]
NEG_KW = ["war","strike","missile","bomb","airstrike","attack","invasion","nuclear","sanction","embargo","tariff","trade war","rate hike","hawkish","tightening","recession","depression","crash","collapse","etf outflow","hormuz","escalation","conflict","tensions","plunge","tumble","slump"]

def has_kw(t,w): return bool(re.search(r'\b'+re.escape(w)+r'\b', t.lower()))

def analyze(title, desc=""):
    t = (title+" "+desc).lower()
    pc = sum(1 for c in POS_CTX if c in t)
    nc = sum(1 for c in NEG_CTX if c in t)
    pk = [k for k in POS_KW if has_kw(t,k)]
    nk = [k for k in NEG_KW if has_kw(t,k)]
    ps = pc*3+len(pk); ns = nc*3+len(nk)
    if ps==0 and ns==0: return None
    dk = [c for c in POS_CTX if c in t][:3] + [c for c in NEG_CTX if c in t][:3]
    if not dk: dk = pk[:3] if pk else nk[:3]
    dk = list(set(dk))[:3]
    if ns>ps:
        l = "🔴🔴🔴 CỰC KỲ TIÊU CỰC" if ns>=9 else ("🔴🔴 RẤT TIÊU CỰC" if ns>=6 else "🔴 TIÊU CỰC")
        g="🥇 Vàng: 🟢 TĂNG (trú ẩn)"; c="₿ Crypto: 🔴 GIẢM (risk-off)"; u="💵 USD: 🟢 TĂNG (trú ẩn)"; a="⚠️ ƯU TIÊN SHORT"
    else:
        l = "🟢🟢🟢 CỰC KỲ TÍCH CỰC" if ps>=9 else ("🟢🟢 TÍCH CỰC" if ps>=6 else "🟢 TÍCH CỰC")
        g="🥇 Vàng: 🔴 GIẢM (risk-on)"; c="₿ Crypto: 🟢 TĂNG (risk-on)"; u="💵 USD: 🔴 GIẢM (risk-on)"; a="✅ ƯU TIÊN LONG"
    return {'loai':l,'gold':g,'crypto':c,'usd':u,'advice':a,'keywords':dk}

# ========== DỊCH ==========
FIX_D = {
    "tỷ lệ cắt":"hạ lãi suất","tỷ lệ tăng":"tăng lãi suất",
    "chợ bò":"thị trường tăng","chợ gấu":"thị trường giảm",
    "tiền điện tử":"crypto","chuỗi khối":"blockchain",
    "trú ẩn an toàn":"tài sản trú ẩn","eo biển hormuz":"eo biển Hormuz",
    "cục dự trữ liên bang":"Fed","quỹ giao dịch trao đổi":"ETF",
    "bảng lương phi nông nghiệp":"bảng lương NFP",
    "chỉ số giá tiêu dùng":"CPI","chỉ số giá sản xuất":"PPI",
    "tổng sản phẩm quốc nội":"GDP",
    "phố wall":"Phố Wall","nhà trắng":"Nhà Trắng",
    "lầu năm góc":"Lầu Năm Góc","điện kremlin":"Điện Kremlin",
    "dầu thô":"dầu","giá dầu":"giá dầu",
}

def dich(text):
    if not text: return ""
    try:
        r = requests.get("https://translate.googleapis.com/translate_a/single",
                        params={'client':'gtx','sl':'en','tl':'vi','dt':'t','q':text}, timeout=5)
        if r.status_code==200: t = ''.join([s[0] for s in r.json()[0] if s[0]])
        else: return text
    except: return text
    for w,c in FIX_D.items(): t = re.sub(r'\b'+re.escape(w)+r'\b', c, t, flags=re.IGNORECASE)
    return t[0].upper()+t[1:] if len(t)>1 else t

# ========== FETCH RSS ==========
def fetch_rss_news(log):
    all_news = []
    all_links = []
    for url, src in RSS_FEEDS:
        try:
            r = requests.get(url, timeout=15, headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
            if r.status_code!=200: continue
            root = ET.fromstring(r.content)
            items = root.findall('.//item') or root.findall('.//{http://www.w3.org/2005/Atom}entry')
            for item in items[:5]:
                title_el = item.find('title') or item.find('{http://www.w3.org/2005/Atom}title')
                title = title_el.text if title_el is not None else ''
                desc_el = item.find('description') or item.find('{http://www.w3.org/2005/Atom}summary')
                desc = clean_html(desc_el.text) if desc_el is not None and desc_el.text else ''
                link_el = item.find('link') or item.find('{http://www.w3.org/2005/Atom}link')
                link = (link_el.get('href') or link_el.text or '') if link_el is not None else ''
                date_el = item.find('pubDate') or item.find('{http://www.w3.org/2005/Atom}updated') or item.find('{http://www.w3.org/2005/Atom}published')
                pubdate = date_el.text if date_el is not None else ''
                if not title or link in log['news_sent'] or link in all_links: continue
                if not is_hot_news(title, desc): continue
                result = analyze(title, desc)
                if not result: continue
                dup = False
                for e in all_news:
                    w1=set(title.lower().split()); w2=set(e['title_en'].lower().split())
                    if w1 and w2 and len(w1&w2)/len(w1|w2)>0.5: dup=True; break
                if dup: continue
                log['news_sent'].append(link); all_links.append(link)
                all_news.append({
                    'title_vi':dich(title),'title_en':title,'description':desc,
                    'source':src,'date':format_date(pubdate) if pubdate else '',
                    'loai':result['loai'],'gold':result['gold'],'crypto':result['crypto'],
                    'usd':result['usd'],'advice':result['advice'],'keywords':result['keywords']
                })
        except: continue
    return all_news

def fetch_all_news():
    log = get_log(); log['news_sent'] = []
    news = fetch_rss_news(log)
    log['news_sent'] = log['news_sent'][-500:]; save_log(log)
    pr = {'CỰC KỲ TIÊU CỰC':0,'RẤT TIÊU CỰC':1,'TIÊU CỰC':2,'TÍCH CỰC':3,'CỰC KỲ TÍCH CỰC':4}
    TRUST = ["reuters.com","ft.com","foreignpolicy.com","csis.org","understandingwar.org","coindesk.com","cointelegraph.com"]
    news.sort(key=lambda n: (pr.get(n['loai'].split()[-1] if 'CỰC' in n['loai'] else n['loai'].split()[-1],3), 0 if any(s in n['source'].lower() for s in TRUST) else 1))
    return news[:MAX_NEWS]

# ========== EVENTS ==========
EVENTS = [
    {'id':'nfp_may','name':'💼 Bảng lương NFP (T5)','date':'2026-06-05','time':'19:30','impact':'🔴 CAO','desc':'Báo cáo việc làm phi nông nghiệp - chỉ báo sức khỏe kinh tế Mỹ.','fred':'UNRATE','is_fomc':False,'advice':'NFP > dự đoán → Kinh tế mạnh → 🟢 LONG\nNFP < dự đoán → Kinh tế yếu → 🔴 SHORT','gold':'NFP cao → USD mạnh → Vàng GIẢM','crypto':'NFP cao → Kinh tế tốt → Crypto TĂNG','usd':'NFP cao → USD TĂNG'},
    {'id':'cpi_may','name':'📊 Chỉ số CPI (T5)','date':'2026-06-11','time':'19:30','impact':'🔴 CAO','desc':'Chỉ số giá tiêu dùng - thước đo lạm phát quan trọng nhất.','fred':'CPIAUCSL','is_fomc':False,'advice':'CPI thấp → Fed dovish → 🟢 LONG\nCPI cao → Fed hawkish → 🔴 SHORT','gold':'CPI cao → Vàng TĂNG (hedge)','crypto':'CPI cao → lo tăng lãi suất → Crypto GIẢM','usd':'CPI cao → USD TĂNG'},
    {'id':'ppi_may','name':'🏭 Chỉ số PPI (T5)','date':'2026-06-12','time':'19:30','impact':'🟡 TRUNG BÌNH','desc':'Chỉ số giá sản xuất - chỉ báo sớm của lạm phát.','fred':'PPIACO','is_fomc':False},
    {'id':'fomc_jun','name':'🏦 Quyết định lãi suất FOMC (T6)','date':'2026-06-18','time':'01:00','impact':'🔴 CAO - SỰ KIỆN QUAN TRỌNG NHẤT THÁNG','desc':'Fed công bố quyết định lãi suất.','fred':'DFF','is_fomc':True,'advice':'GIỮ NGUYÊN → 🟢 LONG\nTĂNG → 🔴 SHORT\nGIẢM → 🟢 LONG mạnh\nĐóng bot 30p trước!','gold':'Hawkish → Vàng GIẢM | Dovish → Vàng TĂNG','crypto':'Hawkish → Crypto GIẢM | Dovish → Crypto TĂNG','usd':'Hawkish → USD TĂNG | Dovish → USD GIẢM'},
    {'id':'gdp_q2','name':'📊 GDP Quý 2/2026','date':'2026-06-25','time':'19:30','impact':'🔴 CAO','desc':'Tăng trưởng kinh tế Mỹ quý 2/2026.','fred':'GDP','is_fomc':False,'advice':'GDP cao → 🟢 LONG\nGDP thấp → 🔴 SHORT','gold':'GDP cao → Vàng GIẢM','crypto':'GDP cao → Crypto TĂNG','usd':'GDP cao → USD TĂNG'},
    {'id':'fomc_jul','name':'🏦 Quyết định lãi suất FOMC (T7)','date':'2026-07-30','time':'01:00','impact':'🔴 CAO - QUAN TRỌNG','desc':'Quyết định lãi suất Fed giữa năm 2026.','fred':'DFF','is_fomc':True,'advice':'GIỮ NGUYÊN → 🟢 LONG\nTĂNG → 🔴 SHORT\nĐóng bot 30p trước!','gold':'Hawkish → Vàng GIẢM | Dovish → Vàng TĂNG','crypto':'Hawkish → Crypto GIẢM | Dovish → Crypto TĂNG','usd':'Hawkish → USD TĂNG | Dovish → USD GIẢM'},
]

def get_fedwatch():
    d = fred_get('DFF')
    if not d: return None
    cr = d[0]['value']
    if len(d)>=2:
        pr = d[1]['value']
        if cr>pr: tr = f"📈 Lãi suất đang <b>TĂNG</b> (từ {pr}% → {cr}%)"
        elif cr<pr: tr = f"📉 Lãi suất đang <b>GIẢM</b> (từ {pr}% → {cr}%)"
        else: tr = f"➡️ Lãi suất đang <b>ỔN ĐỊNH</b> ở mức {cr}%"
    else: tr = f"➡️ Lãi suất hiện tại: <b>{cr}%</b>"
    cd = fred_get('CPIAUCSL')
    if cd and len(cd)>=2:
        ch = round((cd[0]['value']-cd[1]['value'])/cd[1]['value']*100,1)
        if ch>0.3: prd = f"⚠️ CPI tăng <b>{ch}%</b> → Áp lực <b>TĂNG</b> lãi suất"
        elif ch<-0.3: prd = f"✅ CPI giảm <b>{abs(ch)}%</b> → Có thể <b>GIẢM</b> lãi suất"
        else: prd = f"➡️ CPI ổn định → Dự kiến <b>GIỮ NGUYÊN</b>"
    else: prd = "➡️ Dự kiến <b>GIỮ NGUYÊN</b>"
    return {'current_rate':f"{cr}%",'trend':tr,'prediction':prd}

def check_events():
    log = get_log(); now = datetime.now(); today = now.date(); msgs = []
    fw = get_fedwatch()
    for ev in EVENTS:
        evd = datetime.strptime(ev['date'],'%Y-%m-%d').date()
        evdt = datetime.strptime(ev['date']+' '+ev['time'],'%Y-%m-%d %H:%M')
        days = (evd-today).days
        hs = (now-evdt).total_seconds()/3600 if evdt<now else -1
        if 0<=days<=5:
            key = f"pre_{ev['id']}"
            if time.time()-log['events'].get(key,0)>=21600:
                log['events'][key]=time.time()
                cd = f"⚠️ <b>HÔM NAY</b> lúc {ev['time']} (giờ VN)" if days==0 else f"📅 <b>NGÀY MAI</b> lúc {ev['time']} (giờ VN)" if days==1 else f"📅 Còn <b>{days} ngày</b> - {ev['date']} lúc {ev['time']} (giờ VN)"
                fwt = ""
                if ev.get('is_fomc') and fw: fwt = f"\n\n📊 <b>PHÂN TÍCH LÃI SUẤT (FRED):</b>\n{fw['trend']}\n{fw['prediction']}\n🏦 Hiện tại: {fw['current_rate']}"
                td = ""
                if ev.get('gold') or ev.get('crypto') or ev.get('usd'):
                    td = "\n\n📊 <b>TÁC ĐỘNG DỰ KIẾN:</b>\n"
                    if ev.get('gold'): td+=f"🥇 Vàng: {ev['gold']}\n"
                    if ev.get('crypto'): td+=f"₿ Crypto: {ev['crypto']}\n"
                    if ev.get('usd'): td+=f"💵 USD: {ev['usd']}\n"
                cl = ""
                if ev.get('advice'): cl = f"\n💡 <b>CHIẾN LƯỢC:</b>\n{ev['advice']}\n"
                msgs.append(f"📅 <b>{ev['name']}</b>\n━━━━━━━━━━━━━━━━━━\n⏰ {cd}\n⚡ Mức độ: {ev['impact']}\n📝 {ev['desc']}{fwt}{td}{cl}\n━━━━━━━━━━━━━━━━━━\n📊 <b>DỮ LIỆU KINH TẾ HIỆN TẠI:</b>\n{econ_summary()}\n\n{now_str()}")
        elif days<0 and 1<=hs<=24:
            key = f"post_{ev['id']}"
            if key not in log['events']:
                d = fred_get(ev['fred'])
                if d and len(d)>=2:
                    curr,prev = d[0]['value'],d[1]['value']
                    if 'fomc' in ev['id'] and 'minutes' not in ev['id']:
                        if curr>prev: kq="📈 <b>Fed TĂNG lãi suất</b>"; td="🦅 <b>HAWKISH</b>"; hd="🔴 SHORT Crypto"
                        elif curr<prev: kq="📉 <b>Fed GIẢM lãi suất</b>"; td="🕊️ <b>DOVISH</b>"; hd="🟢 LONG Crypto"
                        else: kq="➡️ <b>Fed GIỮ NGUYÊN</b>"; td="➡️ <b>TRUNG LẬP</b>"; hd="🟢 Tích cực nhẹ"
                    elif ev['id']=='nfp_may': kq=f"📊 <b>Thất nghiệp: {curr}%</b>"; td="✅ Mạnh" if curr<prev else "⚠️ Yếu"; hd="🟢 LONG" if curr<prev else "🔴 SHORT"
                    elif ev['id']=='cpi_may':
                        pct=round((curr-prev)/prev*100,1); kq=f"📊 <b>CPI: {curr}</b> ({'+' if pct>0 else ''}{pct}%)"
                        td="⚠️ Nóng" if curr>prev else "✅ Hạ nhiệt"; hd="🟢 LONG" if curr<=prev else "🔴 SHORT"
                    else: kq=f"📊 <b>{curr}</b>"; td="Đã cập nhật"; hd="Theo dõi"
                    log['events'][key]=time.time()
                    msgs.append(f"✅ <b>{ev['name']} - KẾT QUẢ</b>\n━━━━━━━━━━━━━━━━━━\n⏰ {ev['date']} lúc {ev['time']} (giờ VN)\n\n📊 <b>KẾT QUẢ:</b>\n{kq}\n\n🎤 <b>ĐÁNH GIÁ:</b>\n{td}\n\n💡 <b>HÀNH ĐỘNG:</b>\n{hd}\n━━━━━━━━━━━━━━━━━━\n📊 <b>DỮ LIỆU KINH TẾ HIỆN TẠI:</b>\n{econ_summary()}\n\n{now_str()}")
    save_log(log)
    return msgs

# ========== MAIN ==========
print("="*60)
print("BOT TIN TUC PRO - NGUON CHUAN NHA DAU TU")
print("="*60)
_last_fetch = 0

while True:
    try:
        state = get_state(); now_ts = time.time()
        if now_ts - _last_fetch < 300: time.sleep(10); continue
        if not state['started'] or (now_ts - state['last_update'] >= CHU_KY):
            _last_fetch = now_ts
            set_state(started=True, last_update=now_ts)
            if 'started_ever' not in state: set_state(started_ever=True)
            news = fetch_all_news()
            label = "đã khởi động" if state.get('started_ever') else "cập nhật 6h"
            srcs = ['Reuters','Financial Times','Foreign Policy','CSIS','ISW','CoinDesk','Cointelegraph']
            cnt = sum(1 for n in news if n['source'] in srcs)
            gui(f"📰 <b>BẢN TIN THỊ TRƯỜNG {label}!</b>\n━━━━━━━━━━━━━━━━━━\n📡 FRED: ✅ | RSS: ✅ {cnt} tin từ 7 nguồn PRO\n\n📊 <b>DỮ LIỆU KINH TẾ:</b>\n{econ_summary()}\n\n📋 Phát hiện <b>{len(news)} tin</b> quan trọng\n\n{now_str()}")
            if news:
                neg=sum(1 for n in news if 'TIÊU CỰC' in n['loai']); pos=sum(1 for n in news if 'TÍCH CỰC' in n['loai'])
                total=len(news); nr=neg/total if total>0 else 0
                if nr>=0.6: level="CAO 🔴"; adv="⚠️ <b>NGHIÊNG VỀ SHORT</b>"
                elif pos>=total*0.6: level="THẤP (TÍCH CỰC) 🟢"; adv="✅ <b>ƯU TIÊN LONG</b>"
                else: level="TRUNG BÌNH 🟡"; adv="➡️ <b>THEO DÕI THÊM</b>"
                akw=[]; 
                for n in news: akw.extend(n['keywords'])
                gui(f"📰 <b>TỔNG QUAN THỊ TRƯỜNG</b>\n━━━━━━━━━━━━━━━━━━\n🚨 Mức độ: <b>{level}</b>\n📊 Tiêu cực: {neg}/{total} | Tích cực: {pos}/{total}\n💡 {adv}\n\n🔑 Từ khóa: {', '.join(list(set(akw))[:6])}\n\n{now_str()}")
                for n in news:
                    dl = f"\n📅 {n['date']}" if n['date'] else ""
                    tp = []
                    if n['keywords']: tp.append(f"🔑 <b>Từ khóa:</b> {', '.join(n['keywords'])}")
                    if n.get('description'):
                        d = clean_html(n['description']); fs = d.split('.')[0].strip()
                        if len(fs)>15: tp.append(f"📝 {fs}.")
                    tt = "\n".join(tp)
                    msg = f"📰 TIN TỨC {n['loai']}\n━━━━━━━━━━━━━━━━━━\n🇻🇳 <b>{n['title_vi']}</b>\n\n"
                    if tt: msg += f"{tt}\n\n"
                    msg += f"📡 Nguồn: {n['source']}{dl}\n🇬🇧 {n['title_en']}\n\n🏦 <b>Dự báo:</b>\n{n['gold']}\n{n['crypto']}\n{n['usd']}\n\n💡 {n['advice']}\n\n{now_str()}"
                    gui(msg); time.sleep(1)
            for m in check_events(): gui(m)
        time.sleep(60)
    except KeyboardInterrupt: print("\n👋 Dừng"); break
    except Exception as e: print(f"Lỗi: {e}"); time.sleep(30)