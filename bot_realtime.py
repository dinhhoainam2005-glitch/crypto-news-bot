"""
BOT REALTIME V2 - TICH HOP TAT CA TIN HIEU
- Thanh lý >$100M (Coinglass)
- ETF Flow >$300M (Farside)
- Biến động giá >3% (CoinGecko)
- Sự kiện kinh tế: FOMC, CPI, NFP, GDP, PPI (FRED)
- Địa chính trị khẩn cấp (NewsAPI)
- BTC.D, ETH.D, SOL.D Dominance
- FedWatch logic rõ ràng - không mâu thuẫn
- Cảnh báo trước 5 ngày + kết quả sau sự kiện
"""
import requests
import time
import json
import os
import re
from datetime import datetime, timedelta

TOKEN = os.getenv("TELEGRAM_TOKEN", "8893995280:AAF9XwWAm9QgPkwmDrhZdY6UQ4zfySooWpk")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "518284897")
FRED_API_KEY = os.getenv("FRED_API_KEY", "ff3e122af2b2c0a433606476fc6dc5fb")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "bcdf1d28d8bd401f9eb1978268efeb53")

DATA_DIR = "data"
LOG_FILE = f"{DATA_DIR}/log_realtime.json"
os.makedirs(DATA_DIR, exist_ok=True)

def gui(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                     data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except: pass

def now_str():
    n = datetime.now()
    return f"⏰ {n.strftime('%H:%M:%S')} | {n.strftime('%d/%m/%Y')}"

def get_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f: return json.load(f)
    return {"events_sent": {}, "news_sent": []}

def save_log(l):
    with open(LOG_FILE, 'w') as f: json.dump(l, f, ensure_ascii=False, indent=2)

# ============================================
# FRED API
# ============================================
def fred_get(sid):
    try:
        r = requests.get(f"https://api.stlouisfed.org/fred/series/observations?series_id={sid}&api_key={FRED_API_KEY}&file_type=json&limit=3&sort_order=desc", timeout=10)
        if r.status_code == 200:
            obs = r.json().get('observations', [])
            return [{'d': o['date'], 'v': float(o['value'])} for o in obs if o.get('value', '.') != '.']
    except: pass
    return None

def econ_summary():
    parts = []
    for sid, fmt in [('DFF','LS Fed: {}%'), ('CPIAUCSL','CPI: {}'), ('UNRATE','TN: {}%'), ('GDP','GDP: ${:,.0f}B')]:
        v = fred_get(sid)
        if v: parts.append(fmt.format(v[0]['v']))
    return " | ".join(parts) if parts else "Đang tải..."

# ============================================
# DOMINANCE
# ============================================
def get_dominance():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global", timeout=10)
        if r.status_code == 200:
            data = r.json()
            btc_d = round(data['data']['market_cap_percentage']['btc'], 1)
            eth_d = round(data['data']['market_cap_percentage']['eth'], 1)
            sol_d = None
            r2 = requests.get("https://api.coingecko.com/api/v3/coins/markets",
                            params={'vs_currency':'usd','ids':'solana','order':'market_cap_desc','per_page':1,'page':1}, timeout=10)
            if r2.status_code == 200:
                sol_data = r2.json()
                if sol_data:
                    total_mcap = data['data']['total_market_cap']['usd']
                    sol_d = round(sol_data[0]['market_cap'] / total_mcap * 100, 1)
            return btc_d, eth_d, sol_d
    except: pass
    return None, None, None

def dominance_text():
    btc_d, eth_d, sol_d = get_dominance()
    if btc_d:
        text = f"\n📊 <b>Dominance:</b> BTC: {btc_d}%"
        if eth_d: text += f" | ETH: {eth_d}%"
        if sol_d: text += f" | SOL: {sol_d}%"
        if btc_d > 58:
            text += "\n⚠️ <b>BTC.D CAO</b> → Altcoin yếu, ưu tiên BTC"
        elif btc_d < 48:
            text += "\n✅ <b>BTC.D THẤP</b> → Altcoin season, ưu tiên ETH/SOL"
        return text
    return ""

# ============================================
# 1. THANH LY (COINGLASS)
# ============================================
def check_liquidation():
    try:
        r = requests.get("https://open-api-v3.coinglass.com/api/futures/liquidation/detail",
                        params={'symbol': 'BTC', 'limit': 5}, timeout=10,
                        headers={'accept': 'application/json'})
        if r.status_code != 200: return None
        data = r.json()
        if not data.get('data'): return None
        total = sum(item.get('amount', 0) for item in data['data'][:10])
        if total >= 100_000_000:
            return f"💰 <b>THANH LÝ LỚN: ${total:,.0f}</b>\n📊 {len(data['data'])} lệnh bị thanh lý\n⚠️ Biến động mạnh → cân nhắc vào lệnh!"
    except: pass
    return None

# ============================================
# 2. ETF FLOW (FARSIDE)
# ============================================
def check_etf_flow():
    try:
        r = requests.get("https://farside.co.uk/btc-flow/", timeout=10,
                        headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code != 200: return None
        html = r.text
        match = re.search(r'Total.*?\$?([\d,]+\.?\d*)\s*(m|M|b|B)?', html, re.DOTALL)
        if match:
            value = float(match.group(1).replace(',', ''))
            unit = match.group(2) if match.group(2) else ''
            if unit.lower() == 'b': value *= 1_000_000_000
            elif unit.lower() == 'm': value *= 1_000_000
            if abs(value) >= 300_000_000:
                direction = "🟢 VÀO" if value > 0 else "🔴 RA"
                action = "🟢 LONG" if value > 0 else "🔴 SHORT"
                return f"📊 <b>ETF FLOW: {direction} ${abs(value):,.0f}</b>\n💡 Dòng tiền {direction.lower()} mạnh → {action}"
    except: pass
    return None

# ============================================
# 3. BIEN DONG GIA (COINGECKO)
# ============================================
def check_price_change():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price",
                        params={'ids': 'bitcoin,ethereum,solana', 'vs_currencies': 'usd', 'include_24hr_change': 'true'},
                        timeout=10)
        if r.status_code != 200: return None
        data = r.json()
        alerts = []
        emoji = {'bitcoin': '₿', 'ethereum': 'Ξ', 'solana': '◎'}
        name = {'bitcoin': 'BTC', 'ethereum': 'ETH', 'solana': 'SOL'}
        for cid, info in data.items():
            ch = info.get('usd_24h_change', 0)
            if abs(ch) >= 3.0:
                d = "🟢 TĂNG" if ch > 0 else "🔴 GIẢM"
                alerts.append(f"📈 {emoji[cid]} <b>{name[cid]}: {d} {abs(ch):.1f}%</b> | 💵 ${info['usd']:,.2f}")
        return "\n".join(alerts) if alerts else None
    except: pass
    return None

# ============================================
# 4. FEDWATCH
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
# 5. SU KIEN KINH TE
# ============================================
EVENTS = [
    {'id':'nfp_may','name':'💼 Bảng lương NFP (T5)','date':'2026-06-05','time':'19:30','impact':'🔴 CAO','desc':'Báo cáo việc làm phi nông nghiệp Mỹ.','fred':'UNRATE','type':'nfp'},
    {'id':'cpi_may','name':'📊 CPI (T5)','date':'2026-06-11','time':'19:30','impact':'🔴 CAO','desc':'Chỉ số giá tiêu dùng - lạm phát.','fred':'CPIAUCSL','type':'cpi'},
    {'id':'ppi_may','name':'🏭 PPI (T5)','date':'2026-06-12','time':'19:30','impact':'🟡 TB','desc':'Chỉ số giá sản xuất.','fred':'PPIACO','type':'ppi'},
    {'id':'fomc_jun','name':'🏦 FOMC (T6)','date':'2026-06-18','time':'01:00','impact':'🔴 CAO','desc':'Quyết định lãi suất Fed.','fred':'DFF','type':'fomc'},
    {'id':'gdp_q2','name':'📊 GDP Q2/2026','date':'2026-06-25','time':'19:30','impact':'🔴 CAO','desc':'Tăng trưởng kinh tế Mỹ.','fred':'GDP','type':'gdp'},
    {'id':'fomc_jul','name':'🏦 FOMC (T7)','date':'2026-07-30','time':'01:00','impact':'🔴 CAO','desc':'Quyết định lãi suất Fed.','fred':'DFF','type':'fomc'},
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
            if time.time() - log['events_sent'].get(key, 0) >= 3600:
                log['events_sent'][key] = time.time()
                
                cd = f"⚠️ <b>HÔM NAY</b> {ev['time']}" if days==0 else \
                     f"📅 <b>NGÀY MAI</b> {ev['time']}" if days==1 else \
                     f"📅 Còn <b>{days} ngày</b> - {ev['date']}"
                
                prediction = ""
                v = fred_get(ev['fred'])
                if v:
                    curr = v[0]['v']
                    if ev['type'] == 'fomc':
                        if fedwatch:
                            prediction = f"\n📊 <b>PHÂN TÍCH LÃI SUẤT:</b>\n{fedwatch['trend']}\n{fedwatch['prediction']}\n🏦 Hiện tại: {fedwatch['current_rate']}"
                        else:
                            prediction = f"\n📊 <b>LÃI SUẤT:</b> {curr}%"
                    elif ev['type'] == 'cpi':
                        if len(v) >= 2:
                            ch = round((v[0]['v']-v[1]['v'])/v[1]['v']*100, 1)
                            prediction = f"\n📊 <b>CPI HIỆN TẠI:</b> {curr} ({'+' if ch>0 else ''}{ch}%)"
                    elif ev['type'] == 'nfp':
                        prediction = f"\n📊 <b>THẤT NGHIỆP:</b> {curr}%"
                    elif ev['type'] == 'gdp':
                        prediction = f"\n📊 <b>GDP:</b> ${curr:,.0f}B"
                
                dom_text = dominance_text()
                msgs.append(f"🚨 <b>TÍN HIỆU SỰ KIỆN!</b>\n━━━━━━━━━━━━━━━━━━\n"
                          f"{ev['name']} | {ev['impact']}\n⏰ {cd}\n📝 {ev['desc']}"
                          f"{prediction}{dom_text}\n━━━━━━━━━━━━━━━━━━\n📊 {econ_summary()}")
        
        elif days < 0 and 1 <= hours_since <= 24:
            key = f"post_{ev['id']}"
            if key not in log['events_sent']:
                v = fred_get(ev['fred'])
                if v and len(v) >= 2:
                    curr, prev = v[0]['v'], v[1]['v']
                    
                    if ev['type'] == 'fomc':
                        if curr > prev: kq = f"📈 <b>TĂNG</b> từ {prev}% lên {curr}%"
                        elif curr < prev: kq = f"📉 <b>GIẢM</b> từ {prev}% xuống {curr}%"
                        else: kq = f"➡️ <b>GIỮ NGUYÊN</b> ở {curr}%"
                    elif ev['type'] == 'nfp':
                        if curr > prev: kq = f"📈 <b>TĂNG</b> lên {curr}%"
                        elif curr < prev: kq = f"📉 <b>GIẢM</b> xuống {curr}%"
                        else: kq = f"➡️ <b>KHÔNG ĐỔI</b> ở {curr}%"
                    elif ev['type'] == 'cpi':
                        pct = round(abs(curr-prev)/prev*100, 1)
                        if curr > prev: kq = f"📈 <b>TĂNG {pct}%</b> (lạm phát nóng)"
                        elif curr < prev: kq = f"📉 <b>GIẢM {pct}%</b> (lạm phát hạ nhiệt)"
                        else: kq = f"➡️ <b>KHÔNG ĐỔI</b>"
                    else:
                        kq = f"<b>{curr}</b> (trước: {prev})"
                    
                    log['events_sent'][key] = time.time()
                    dom_text = dominance_text()
                    msgs.append(f"✅ <b>{ev['name']} - KẾT QUẢ!</b>\n━━━━━━━━━━━━━━━━━━\n"
                              f"⏰ Đã diễn ra: {ev['date']} {ev['time']}\n📊 {kq}{dom_text}\n━━━━━━━━━━━━━━━━━━\n📊 {econ_summary()}")
    
    save_log(log)
    return msgs

# ============================================
# 6. DIA CHINH TRI KHAN CAP
# ============================================
GEO_QUERIES = ["iran israel war", "russia ukraine attack", "north korea missile", "china taiwan war"]

def check_geo_emergency():
    log = get_log()
    for query in GEO_QUERIES:
        try:
            r = requests.get("https://newsapi.org/v2/everything", params={
                'q': query, 'language': 'en', 'sortBy': 'publishedAt',
                'pageSize': 1, 'apiKey': NEWS_API_KEY
            }, timeout=10)
            if r.status_code != 200: continue
            
            for a in r.json().get('articles', []):
                title = a.get('title', '')
                url = a.get('url', '')
                if url in log['news_sent']: continue
                
                emergency_kw = ['strike', 'attack', 'war', 'missile', 'invasion', 'nuclear', 'bomb']
                if any(re.search(r'\b' + kw + r'\b', title.lower()) for kw in emergency_kw):
                    log['news_sent'].append(url)
                    log['news_sent'] = log['news_sent'][-100:]
                    save_log(log)
                    dom_text = dominance_text()
                    return f"🌍 <b>ĐỊA CHÍNH TRỊ KHẨN!</b>\n━━━━━━━━━━━━━━━━━━\n🇬🇧 {title}\n📡 {(a.get('source',{}) or {}).get('name','Unknown')}\n⚠️ Xung đột leo thang → 🔴 SHORT{dom_text}\n━━━━━━━━━━━━━━━━━━\n📊 {econ_summary()}"
            time.sleep(0.3)
        except: continue
    return None

# ============================================
# MAIN
# ============================================
print("="*60)
print("BOT REALTIME V2 - FULL SIGNALS")
print("="*60)

dom_text = dominance_text()
gui(f"🚨 <b>BOT REALTIME V2 ĐÃ KHỞI ĐỘNG!</b>\n━━━━━━━━━━━━━━━━━━\n"
    f"💰 Thanh lý >$100M | 📊 ETF >$300M | 📈 Biến động >3%\n"
    f"🏦 FOMC/CPI/NFP/GDP | 🌍 Địa chính trị khẩn\n"
    f"⏰ Cảnh báo trước 5 ngày + Kết quả sau sự kiện{dom_text}\n━━━━━━━━━━━━━━━━━━\n{now_str()}")

last_liq = last_etf = last_price = last_events = last_geo = 0

while True:
    try:
        now = time.time()
        
        if now - last_liq >= 60:
            last_liq = now
            msg = check_liquidation()
            if msg: gui(f"🚨 TÍN HIỆU REALTIME!\n━━━━━━━━━━━━━━━━━━\n{msg}\n\n{now_str()}")
        
        if now - last_etf >= 300:
            last_etf = now
            msg = check_etf_flow()
            if msg: gui(f"🚨 TÍN HIỆU REALTIME!\n━━━━━━━━━━━━━━━━━━\n{msg}\n\n{now_str()}")
        
        if now - last_price >= 60:
            last_price = now
            msg = check_price_change()
            if msg: gui(f"🚨 TÍN HIỆU REALTIME!\n━━━━━━━━━━━━━━━━━━\n{msg}\n\n{now_str()}")
        
        if now - last_events >= 3600:
            last_events = now
            for msg in check_events():
                gui(f"{msg}\n\n{now_str()}")
        
        if now - last_geo >= 600:
            last_geo = now
            msg = check_geo_emergency()
            if msg: gui(f"{msg}\n\n{now_str()}")
        
        time.sleep(10)
        
    except KeyboardInterrupt:
        gui("🛑 Bot Realtime đã dừng")
        break
    except Exception as e:
        print(f"Lỗi: {e}")
        time.sleep(30)