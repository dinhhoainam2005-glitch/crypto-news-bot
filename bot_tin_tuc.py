"""
BOT TIN TUC - NEWSAPI + FRED - PRO FILTER
- Từ khóa KINH TẾ + ĐỊA CHÍNH TRỊ quan trọng nhất
- Tối đa 8 tin/lần gửi
- Có ngày đăng + nguồn
- 6h cập nhật 1 lần
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

CHU_KY = 21600
MAX_NEWS = 8
DATA_DIR = "data"
STATE_FILE = f"{DATA_DIR}/state.json"
LOG_FILE = f"{DATA_DIR}/log.json"

BLOCKED_SOURCES = ["naturalnews.com", "naturalnews", "beforeitsnews.com", "infowars.com", "zerohedge.com", "activistpost.com", "globalresearch.ca", "nakedcapitalism.com"]

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
    for sid, fmt in [('DFF','<b>Fed Rate:</b> {}%'), ('CPIAUCSL','<b>CPI:</b> {}'), ('UNRATE','<b>UE:</b> {}%'), ('GDP','<b>GDP:</b> ${:,.0f}B'), ('PPIACO','<b>PPI:</b> {}')]:
        v = fred_get(sid)
        if v: parts.append(fmt.format(v[0]['v']))
    return " | ".join(parts) if parts else "Đang tải..."

def dich_tieng_viet(text):
    try:
        r = requests.get("https://translate.googleapis.com/translate_a/single",
                        params={'client':'gtx','sl':'en','tl':'vi','dt':'t','q':text}, timeout=5)
        if r.status_code == 200:
            return ''.join([s[0] for s in r.json()[0] if s[0]])
    except: pass
    return text

def format_date(date_str):
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
        return dt.strftime("%d/%m/%Y %H:%M UTC")
    except: return date_str

# ===== TỪ KHÓA QUAN TRỌNG NHẤT =====
POSITIVE_KW = [
    "rate cut", "dovish", "easing", "ceasefire", "peace deal", "peace talk",
    "truce", "surrender", "withdraw", "bull market", "rally", "etf approved",
    "etf inflow", "blackrock", "institutional", "adoption", "partnership"
]

NEGATIVE_KW = [
    "war", "strike", "missile", "bomb", "airstrike", "attack", "invasion",
    "offensive", "nuclear", "sanction", "embargo", "tariff", "trade war",
    "rate hike", "hawkish", "tighten", "recession", "depression", "crash",
    "collapse", "oil price surge", "crude surge", "etf outflow", "hormuz"
]

DICH_KW = {
    "rate cut":"hạ lãi suất","dovish":"ôn hòa","easing":"nới lỏng",
    "ceasefire":"ngừng bắn","peace deal":"thỏa thuận hòa bình","peace talk":"đàm phán hòa bình",
    "truce":"đình chiến","surrender":"đầu hàng","withdraw":"rút quân",
    "bull market":"thị trường tăng","rally":"tăng mạnh","etf approved":"ETF được duyệt",
    "etf inflow":"dòng tiền ETF vào","blackrock":"BlackRock","institutional":"tổ chức",
    "adoption":"chấp nhận","partnership":"hợp tác",
    "war":"chiến tranh","strike":"không kích","missile":"tên lửa","bomb":"ném bom",
    "airstrike":"không kích","attack":"tấn công","invasion":"xâm lược","offensive":"tấn công",
    "nuclear":"hạt nhân","sanction":"trừng phạt","embargo":"cấm vận","tariff":"thuế quan",
    "trade war":"chiến tranh thương mại","rate hike":"tăng lãi suất","hawkish":"diều hâu",
    "tighten":"thắt chặt","recession":"suy thoái","depression":"đại suy thoái",
    "crash":"sụp đổ","collapse":"sụp đổ","oil price surge":"giá dầu tăng vọt",
    "crude surge":"dầu thô tăng","etf outflow":"dòng tiền ETF ra","hormuz":"Hormuz"
}

def phan_tich_tin(title, description=""):
    t = (title + " " + description).lower()
    
    # Bỏ qua tin không có từ khóa quan trọng
    pos_found = [DICH_KW.get(kw, kw) for kw in POSITIVE_KW if kw in t]
    neg_found = [DICH_KW.get(kw, kw) for kw in NEGATIVE_KW if kw in t]
    
    if not pos_found and not neg_found:
        return None
    
    # AI Context: chiến tranh + dầu = TIÊU CỰC
    has_war = any(w in t for w in ['war', 'strike', 'airstrike', 'attack', 'invasion', 'chiến tranh', 'không kích', 'tấn công'])
    has_oil = any(w in t for w in ['oil price surge', 'crude surge', 'giá dầu', 'dầu thô'])
    if has_war and has_oil:
        neg_found.append("giá dầu tăng (do chiến tranh)")
        pos_found = [p for p in pos_found if p not in ['thỏa thuận', 'đồng thuận', 'ngừng bắn', 'đình chiến']]
    
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

QUERIES = [
    "iran israel war strike",
    "russia ukraine war nato",
    "fed interest rate inflation",
    "trade war tariff",
    "oil price crude hormuz",
    "stock market crash recession",
    "crypto bitcoin etf regulation",
    "gold price safe haven"
]

def fetch_news():
    all_news = []
    log = get_log()
    
    for query in QUERIES:
        try:
            r = requests.get("https://newsapi.org/v2/everything", params={
                'q': query, 'language': 'en', 'sortBy': 'publishedAt',
                'pageSize': 3, 'apiKey': NEWS_API_KEY
            }, timeout=10)
            if r.status_code != 200: continue
            
            for a in r.json().get('articles', []):
                url_news = a.get('url', '')
                if url_news in log['news_sent']: continue
                
                source_name = (a.get('source', {}) or {}).get('name', 'Unknown')
                if any(b in source_name.lower() for b in BLOCKED_SOURCES): continue
                
                title = a.get('title', '')
                description = a.get('description', '') or ''
                published = a.get('publishedAt', '')
                
                result = phan_tich_tin(title, description)
                if result is None: continue
                
                log['news_sent'].append(url_news)
                all_news.append({
                    'title_vi': dich_tieng_viet(title),
                    'source': source_name,
                    'date': format_date(published) if published else '',
                    'loai': result['loai'], 'gold': result['gold'],
                    'crypto': result['crypto'], 'usd': result['usd'],
                    'advice': result['advice'], 'keywords': result['keywords']
                })
            time.sleep(0.3)
        except: continue
    
    log['news_sent'] = log['news_sent'][-300:]
    save_log(log)
    
    # Sắp xếp tiêu cực trước, giới hạn MAX_NEWS
    priority = {'CỰC KỲ TIÊU CỰC':0,'RẤT TIÊU CỰC':1,'TIÊU CỰC':2,'TÍCH CỰC':3,'TÍCH CỰC':3,'CỰC KỲ TÍCH CỰC':5}
    all_news.sort(key=lambda x: priority.get(x['loai'].split()[-1] if 'CỰC' in x['loai'] else x['loai'].split()[-1], 3))
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

EVENTS = [
    {'id':'nfp_may','name':'💼 Non-Farm Payrolls (T5)','date':'2026-06-05','time':'19:30','impact':'🔴 HIGH','desc':'Báo cáo việc làm phi nông nghiệp Mỹ.','fred':'UNRATE','fmt':'<b>Tỷ lệ thất nghiệp:</b> {value}% (trước: {prev}%)\n🎤 <b>Thái độ:</b> {action}\n📝 {detail}','gold':'<b>NFP cao → GIẢM</b> | NFP thấp → TĂNG','crypto':'<b>NFP cao → TĂNG</b> | NFP thấp → GIẢM','usd':'<b>NFP cao → TĂNG</b> | NFP thấp → GIẢM'},
    {'id':'cpi_may','name':'📊 CPI Report (T5)','date':'2026-06-11','time':'19:30','impact':'🔴 HIGH','desc':'Chỉ số giá tiêu dùng - thước đo lạm phát chính.','fred':'CPIAUCSL','fmt':'<b>CPI:</b> {value} (trước: {prev})\n🎤 <b>Thái độ:</b> {action}\n📝 CPI {detail}.','gold':'<b>CPI cao → TĂNG</b> (hedge) | CPI thấp → GIẢM','crypto':'<b>CPI cao → GIẢM</b> (lo tăng lãi suất) | CPI thấp → TĂNG','usd':'<b>CPI cao → TĂNG</b> | CPI thấp → GIẢM'},
    {'id':'ppi_may','name':'🏭 PPI Report (T5)','date':'2026-06-12','time':'19:30','impact':'🟡 MEDIUM','desc':'Chỉ số giá sản xuất - chỉ báo sớm của lạm phát.','fred':'PPIACO','fmt':'<b>PPI:</b> {value} (trước: {prev})\n🎤 <b>Thái độ:</b> {action}\n📝 PPI {detail}.','gold':'<b>PPI cao → TĂNG</b> | PPI thấp → GIẢM','crypto':'<b>PPI cao → TĂNG nhẹ</b>','usd':'<b>PPI cao → TĂNG nhẹ</b>'},
    {'id':'fomc_minutes_jun','name':'📋 FOMC Meeting Minutes (T6)','date':'2026-06-04','time':'01:00','impact':'🟡 MEDIUM','desc':'Biên bản cuộc họp FOMC tháng 6.','fred':'DFF','fmt':'🎤 <b>Thái độ:</b> 🏦 Fed Rate: {value}%\n📝 Biên bản đã công bố.','gold':'<b>Hawkish → GIẢM</b> | Dovish → TĂNG','crypto':'<b>Hawkish → GIẢM</b> | Dovish → TĂNG','usd':'<b>Hawkish → TĂNG</b> | Dovish → GIẢM'},
    {'id':'fomc_jun','name':'🏦 FOMC Rate Decision (T6)','date':'2026-06-18','time':'01:00','impact':'🔴 HIGH','desc':'Quyết định lãi suất Fed - SỰ KIỆN QUAN TRỌNG NHẤT.','fred':'DFF','fmt':'<b>Lãi suất Fed:</b> {value}% (trước: {prev}%)\n🎤 <b>Thái độ:</b> Fed {action}\n📝 {detail}.','gold':'<b>Hawkish → GIẢM</b> | Dovish → TĂNG','crypto':'<b>Hawkish → GIẢM</b> | Dovish → TĂNG','usd':'<b>Hawkish → TĂNG</b> | Dovish → GIẢM'},
    {'id':'gdp_q2','name':'📊 GDP Q2 2026 (Final)','date':'2026-06-25','time':'19:30','impact':'🔴 HIGH','desc':'Tăng trưởng kinh tế Mỹ quý 2/2026.','fred':'GDP','fmt':'<b>GDP:</b> ${value:,.0f}B (trước: ${prev:,.0f}B)\n🎤 <b>Thái độ:</b> {action}\n📝 GDP thay đổi {detail}% so với ${prev:,.0f}B.','gold':'<b>GDP cao → GIẢM</b> | GDP thấp → TĂNG','crypto':'<b>GDP cao → TĂNG</b> | GDP thấp → GIẢM','usd':'<b>GDP cao → TĂNG</b> | GDP thấp → GIẢM'},
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
            if time.time() - log['events'].get(key, 0) >= 21600:
                log['events'][key] = time.time()
                cd = f"⚠️ <b>HÔM NAY</b> lúc {ev['time']} (UTC+7)" if days==0 else f"📅 <b>NGÀY MAI</b> lúc {ev['time']} (UTC+7)" if days==1 else f"📅 Còn <b>{days} ngày</b> - {ev['date']} lúc {ev['time']} (UTC+7)"
                msgs.append(f"📅 <b>{ev['name']}</b>\n━━━━━━━━━━━━━━━━━━\n⏰ {cd}\n⚡ Mức độ: {ev['impact']}\n📝 {ev['desc']}\n\n━━━━━━━━━━━━━━━━━━\n📊 <b>TÁC ĐỘNG DỰ KIẾN:</b>\n🥇 Vàng: {ev['gold']}\n₿ Crypto: {ev['crypto']}\n💵 USD: {ev['usd']}\n━━━━━━━━━━━━━━━━━━\n\n📊 <b>DỮ LIỆU HIỆN TẠI:</b>\n{econ_summary()}\n\n{now_str()}")
        
        elif days < 0 and 1 <= hours_since <= 24:
            key = f"post_{ev['id']}"
            if key not in log['events'] and fred_ok():
                v = fred_get(ev['fred'])
                if v and len(v) >= 2:
                    curr, prev = v[0]['v'], v[1]['v']
                    if curr > prev:
                        if 'fomc' in ev['id'] and 'minutes' not in ev['id']: action="<b>TĂNG 🦅</b>"; detail=f"Fed <b>TĂNG</b> lãi suất thêm {round(curr-prev,2)}%"
                        elif 'gdp' in ev['id']: action="<b>📈 TĂNG TRƯỞNG ✅</b>"; detail=f"<b>+{round((curr-prev)/prev*100,2)}%</b>"
                        elif 'nfp' in ev['id']: action="<b>📈 TĂNG</b>"; detail="Thị trường lao động <b>yếu đi</b>"
                        elif 'cpi' in ev['id']: action="<b>📈 LẠM PHÁT TĂNG</b>"; detail=f"tăng <b>{round((curr-prev)/prev*100,1)}%</b>"
                        elif 'ppi' in ev['id']: action="<b>📈 TĂNG</b>"; detail=f"tăng <b>{round((curr-prev)/prev*100,1)}%</b>"
                        else: action="<b>📈 TĂNG</b>"; detail=f"tăng <b>{round((curr-prev)/prev*100,1)}%</b>"
                    elif curr < prev:
                        if 'fomc' in ev['id'] and 'minutes' not in ev['id']: action="<b>GIẢM 🕊️</b>"; detail=f"Fed <b>GIẢM</b> lãi suất {round(prev-curr,2)}%"
                        elif 'gdp' in ev['id']: action="<b>📉 SUY GIẢM ⚠️</b>"; detail=f"<b>{round((curr-prev)/prev*100,2)}%</b>"
                        elif 'nfp' in ev['id']: action="<b>📉 GIẢM</b>"; detail="Thị trường lao động <b>mạnh lên</b>"
                        elif 'cpi' in ev['id']: action="<b>📉 LẠM PHÁT GIẢM</b>"; detail=f"giảm <b>{round((prev-curr)/prev*100,1)}%</b>"
                        elif 'ppi' in ev['id']: action="<b>📉 GIẢM</b>"; detail=f"giảm <b>{round((prev-curr)/prev*100,1)}%</b>"
                        else: action="<b>📉 GIẢM</b>"; detail=f"giảm <b>{round((prev-curr)/prev*100,1)}%</b>"
                    else:
                        if 'fomc' in ev['id'] and 'minutes' not in ev['id']: action="<b>GIỮ NGUYÊN ➡️</b>"; detail=f"Fed <b>GIỮ NGUYÊN</b> lãi suất ở mức {curr}%"
                        elif 'nfp' in ev['id']: action="<b>➡️ KHÔNG ĐỔI</b>"; detail="<b>Ổn định</b>"
                        elif 'cpi' in ev['id']: action="<b>➡️ KHÔNG ĐỔI</b>"; detail="<b>không đổi</b>"
                        elif 'ppi' in ev['id']: action="<b>➡️ KHÔNG ĐỔI</b>"; detail="<b>không đổi</b>"
                        else: action="<b>➡️ KHÔNG ĐỔI</b>"; detail="<b>không đổi</b>"
                    
                    log['events'][key] = time.time()
                    msgs.append(f"===================================\n✅ <b>{ev['name']} - KẾT QUẢ THỰC TẾ</b>\n===================================\n⏰ Đã diễn ra: {ev['date']} lúc {ev['time']} (UTC+7)\n\n{ev['fmt'].format(value=curr, prev=prev, action=action, detail=detail)}\n\n━━━━━━━━━━━━━━━━━━\n📊 <b>TÁC ĐỘNG THỊ TRƯỜNG:</b>\n🥇 Vàng: {ev['gold']}\n₿ Crypto: {ev['crypto']}\n💵 USD: {ev['usd']}\n━━━━━━━━━━━━━━━━━━\n\n📊 <b>DỮ LIỆU FRED:</b>\n{econ_summary()}\n\n{now_str()}")
    
    save_log(log)
    return msgs

# === MAIN ===
print("BOT TIN TUC PRO - 6H")

while True:
    try:
        s = get_state()
        now = time.time()
        
        if not s['started'] or (now - s['last_update'] >= CHU_KY):
            set_state(started=True, last_update=now)
            if 'started_ever' not in s: set_state(started_ever=True)
            
            log = get_log()
            log['news_sent'] = []
            save_log(log)
            
            news = fetch_news()
            
            label = "đã khởi động" if s.get('started_ever') else "cập nhật 6h"
            
            msg = f"📰 <b>Bot tin tức {label}!</b>\n━━━━━━━━━━━━━━━━━━\n📡 FRED: {'✅ Online' if fred_ok() else '⏳ Offline'}\n📡 NewsAPI: ✅ Online\n\n📊 <b>DỮ LIỆU KINH TẾ:</b>\n{econ_summary()}\n\n"
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
                gui(f"{i} <b>Fear & Greed Index:</b> {v}/100 ({c})")
            except: pass
        
        time.sleep(60)
    except KeyboardInterrupt: break
    except Exception as e:
        print(f"Loi: {e}")
        time.sleep(30)