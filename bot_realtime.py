"""
BOT REALTIME V2 - TICH HOP TAT CA TIN HIEU
- Thanh lý >$100M (Coinglass) | ETF Flow >$300M (Farside) | Biến động >3% (CoinGecko)
- Sự kiện kinh tế: FOMC, CPI, NFP, GDP, PPI (FRED)
- Địa chính trị khẩn cấp (NewsAPI)
- BTC.D, ETH.D, SOL.D Dominance (CoinGecko trực tiếp) + cập nhật mỗi giờ
- FedWatch logic rõ ràng
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
# DOMINANCE - COINGECKO TRUC TIEP
# ============================================
def get_dominance():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global", timeout=10)
        if r.status_code != 200: return None, None, None, None, None, None
        data = r.json()
        btc_d = round(data['data']['market_cap_percentage']['btc'], 1)
        eth_d = round(data['data']['market_cap_percentage']['eth'], 1)
        sol_d = round(data['data']['market_cap_percentage'].get('solana', 0), 1)
        
        r_coins = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={'vs_currency':'usd','ids':'bitcoin,ethereum,solana','order':'market_cap_desc','per_page':3,'page':1},
            timeout=10
        )
        btc_change = eth_change = sol_change = 0
        if r_coins.status_code == 200:
            for coin in r_coins.json():
                ch = coin.get('market_cap_change_percentage_24h', 0) or 0
                if coin['id'] == 'bitcoin': btc_change = ch
                elif coin['id'] == 'ethereum': eth_change = ch
                elif coin['id'] == 'solana': sol_change = ch
        
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
    text = f"\n📊 <b>Dominance:</b>\n₿ BTC: <b>{btc_d}%</b> ({ch_icon(btc_ch)})\nΞ ETH: <b>{eth_d}%</b> ({ch_icon(eth_ch)})\n◎ SOL: <b>{sol_d}%</b> ({ch_icon(sol_ch)})\n"
    if btc_d > 58: text += "⚠️ <b>BTC.D CAO</b> → Altcoin yếu, ưu tiên BTC\n"
    elif btc_d < 48: text += "✅ <b>BTC.D THẤP</b> → Altcoin season, ưu tiên ETH/SOL\n"
    if abs(btc_ch) > 2: text += f"⚡ BTC.D đang {'TĂNG' if btc_ch>0 else 'GIẢM'} mạnh ({btc_ch:+.1f}%) → Dòng tiền đang dịch chuyển!\n"
    return text

# ============================================
# 1-3. THANH LY + ETF + PRICE
# ============================================
def check_liquidation():
    try:
        r = requests.get("https://open-api-v3.coinglass.com/api/futures/liquidation/detail",
                        params={'symbol': 'BTC', 'limit': 5}, timeout=10, headers={'accept': 'application/json'})
        if r.status_code != 200: return None
        data = r.json()
        if not data.get('data'): return None
        total = sum(item.get('amount', 0) for item in data['data'][:10])
        if total >= 100_000_000:
            return f"💰 <b>THANH LÝ LỚN: ${total:,.0f}</b>\n📊 {len(data['data'])} lệnh\n⚠️ Biến động mạnh → cân nhắc vào lệnh!"
    except: pass
    return None

def check_etf_flow():
    try:
        r = requests.get("https://farside.co.uk/btc-flow/", timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code != 200: return None
        match = re.search(r'Total.*?\$?([\d,]+\.?\d*)\s*(m|M|b|B)?', r.text, re.DOTALL)
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

def check_price_change():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price",
                        params={'ids': 'bitcoin,ethereum,solana', 'vs_currencies': 'usd', 'include_24hr_change': 'true'}, timeout=10)
        if r.status_code != 200: return None
        data = r.json()
        alerts = []; emoji = {'bitcoin': '₿', 'ethereum': 'Ξ', 'solana': '◎'}; name = {'bitcoin': 'BTC', 'ethereum': 'ETH', 'solana': 'SOL'}
        for cid, info in data.items():
            ch = info.get('usd_24h_change', 0)
            if abs(ch) >= 3.0:
                d = "🟢 TĂNG" if ch > 0 else "🔴 GIẢM"
                alerts.append(f"📈 {emoji[cid]} <b>{name[cid]}: {d} {abs(ch):.1f}%</b> | 💵 ${info['usd']:,.2f}")
        return "\n".join(alerts) if alerts else None
    except: pass
    return None

# ============================================
# 4-5. FEDWATCH + EVENTS + GEO
# ============================================
def get_fedwatch_prediction():
    fed_data = fred_get('DFF')
    if not fed_data: return None
    current_rate = fed_data[0]['v']
    if len(fed_data) >= 2:
        prev_rate = fed_data[1]['v']
        if current_rate > prev_rate: trend = f"📈 Lãi suất đang <b>TĂNG</b> (từ {prev_rate}% → {current_rate}%)"
        elif current_rate < prev_rate: trend = f"📉 Lãi suất đang <b>GIẢM</b> (từ {prev_rate}% → {current_rate}%)"
        else: trend = f"➡️ Lãi suất đang <b>ỔN ĐỊNH</b> ở mức {current_rate}%"
    else: trend = f"➡️ Lãi suất hiện tại: <b>{current_rate}%</b>"
    cpi_data = fred_get('CPIAUCSL')
    if cpi_data and len(cpi_data) >= 2:
        cpi_change = round((cpi_data[0]['v'] - cpi_data[1]['v']) / cpi_data[1]['v'] * 100, 1)
        if cpi_change > 0.3: prediction = f"⚠️ CPI tăng <b>{cpi_change}%</b> → Áp lực <b>TĂNG</b> lãi suất"
        elif cpi_change < -0.3: prediction = f"✅ CPI giảm <b>{abs(cpi_change)}%</b> → Có thể <b>GIẢM</b> lãi suất"
        else: prediction = f"➡️ CPI ổn định → Dự kiến <b>GIỮ NGUYÊN</b> lãi suất"
    else: prediction = "➡️ Chưa có dữ liệu CPI → Dự kiến <b>GIỮ NGUYÊN</b>"
    return {'current_rate': f"{current_rate}%", 'trend': trend, 'prediction': prediction}

EVENTS = [
    {'id':'nfp_may','name':'💼 Bảng lương NFP (T5)','date':'2026-06-05','time':'19:30','impact':'🔴 CAO','desc':'Báo cáo việc làm.','fred':'UNRATE','type':'nfp'},
    {'id':'cpi_may','name':'📊 CPI (T5)','date':'2026-06-11','time':'19:30','impact':'🔴 CAO','desc':'Chỉ số giá tiêu dùng.','fred':'CPIAUCSL','type':'cpi'},
    {'id':'ppi_may','name':'🏭 PPI (T5)','date':'2026-06-12','time':'19:30','impact':'🟡 TB','desc':'Chỉ số giá sản xuất.','fred':'PPIACO','type':'ppi'},
    {'id':'fomc_jun','name':'🏦 FOMC (T6)','date':'2026-06-18','time':'01:00','impact':'🔴 CAO','desc':'Quyết định lãi suất Fed.','fred':'DFF','type':'fomc'},
    {'id':'gdp_q2','name':'📊 GDP Q2/2026','date':'2026-06-25','time':'19:30','impact':'🔴 CAO','desc':'Tăng trưởng kinh tế.','fred':'GDP','type':'gdp'},
    {'id':'fomc_jul','name':'🏦 FOMC (T7)','date':'2026-07-30','time':'01:00','impact':'🔴 CAO','desc':'Quyết định lãi suất Fed.','fred':'DFF','type':'fomc'},
]

def check_events():
    log = get_log(); now = datetime.now(); today = now.date(); msgs = []
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
                cd = f"⚠️ <b>HÔM NAY</b> {ev['time']}" if days==0 else f"📅 <b>NGÀY MAI</b> {ev['time']}" if days==1 else f"📅 Còn <b>{days} ngày</b> - {ev['date']}"
                prediction = ""
                v = fred_get(ev['fred'])
                if v and ev['type'] == 'fomc' and fedwatch:
                    prediction = f"\n📊 <b>PHÂN TÍCH:</b>\n{fedwatch['trend']}\n{fedwatch['prediction']}\n🏦 Hiện tại: {fedwatch['current_rate']}"
                msgs.append(f"🚨 <b>TÍN HIỆU SỰ KIỆN!</b>\n━━━━━━━━━━━━━━━━━━\n{ev['name']} | {ev['impact']}\n⏰ {cd}\n📝 {ev['desc']}{prediction}\n━━━━━━━━━━━━━━━━━━\n📊 {econ_summary()}")
        elif days < 0 and 1 <= hours_since <= 24:
            key = f"post_{ev['id']}"
            if key not in log['events_sent']:
                v = fred_get(ev['fred'])
                if v and len(v) >= 2:
                    curr, prev = v[0]['v'], v[1]['v']
                    if ev['type'] == 'fomc': kq = f"📈 <b>TĂNG</b> từ {prev}% lên {curr}%" if curr > prev else f"📉 <b>GIẢM</b> từ {prev}% xuống {curr}%" if curr < prev else f"➡️ <b>GIỮ NGUYÊN</b> ở {curr}%"
                    elif ev['type'] == 'nfp': kq = f"📈 <b>{curr}%</b>" if curr > prev else f"📉 <b>{curr}%</b>" if curr < prev else f"➡️ <b>{curr}%</b>"
                    elif ev['type'] == 'cpi':
                        pct = round(abs(curr-prev)/prev*100, 1)
                        kq = f"📈 <b>TĂNG {pct}%</b>" if curr > prev else f"📉 <b>GIẢM {pct}%</b>" if curr < prev else "➡️ <b>KHÔNG ĐỔI</b>"
                    else: kq = f"<b>{curr}</b> (trước: {prev})"
                    log['events_sent'][key] = time.time()
                    msgs.append(f"✅ <b>{ev['name']} - KẾT QUẢ!</b>\n━━━━━━━━━━━━━━━━━━\n⏰ {ev['date']} {ev['time']}\n📊 {kq}\n━━━━━━━━━━━━━━━━━━\n📊 {econ_summary()}")
    save_log(log)
    return msgs

GEO_QUERIES = ["iran israel war", "russia ukraine attack", "north korea missile", "china taiwan war"]

def check_geo_emergency():
    log = get_log()
    for query in GEO_QUERIES:
        try:
            r = requests.get("https://newsapi.org/v2/everything", params={'q': query, 'language': 'en', 'sortBy': 'publishedAt', 'pageSize': 1, 'apiKey': NEWS_API_KEY}, timeout=10)
            if r.status_code != 200: continue
            for a in r.json().get('articles', []):
                title = a.get('title', ''); url = a.get('url', '')
                if url in log['news_sent']: continue
                if any(re.search(r'\b' + kw + r'\b', title.lower()) for kw in ['strike','attack','war','missile','invasion','nuclear','bomb']):
                    log['news_sent'].append(url); log['news_sent'] = log['news_sent'][-100:]; save_log(log)
                    return f"🌍 <b>ĐỊA CHÍNH TRỊ KHẨN!</b>\n━━━━━━━━━━━━━━━━━━\n🇬🇧 {title}\n📡 {(a.get('source',{}) or {}).get('name','Unknown')}\n⚠️ Xung đột leo thang → 🔴 SHORT\n━━━━━━━━━━━━━━━━━━\n📊 {econ_summary()}"
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
gui(f"🚨 <b>BOT REALTIME V2 ĐÃ KHỞI ĐỘNG!</b>\n━━━━━━━━━━━━━━━━━━\n💰 Thanh lý >$100M | 📊 ETF >$300M | 📈 Biến động >3%\n🏦 FOMC/CPI/NFP/GDP | 🌍 Địa chính trị khẩn\n⏰ Cảnh báo trước 5 ngày + Kết quả sau sự kiện{dom_text}\n━━━━━━━━━━━━━━━━━━\n{now_str()}")

last_liq = last_etf = last_price = last_events = last_geo = last_dom = 0

while True:
    try:
        now = time.time()
        if now - last_liq >= 60:
            last_liq = now; msg = check_liquidation()
            if msg: gui(f"🚨 TÍN HIỆU REALTIME!\n━━━━━━━━━━━━━━━━━━\n{msg}\n\n{now_str()}")
        if now - last_etf >= 300:
            last_etf = now; msg = check_etf_flow()
            if msg: gui(f"🚨 TÍN HIỆU REALTIME!\n━━━━━━━━━━━━━━━━━━\n{msg}\n\n{now_str()}")
        if now - last_price >= 60:
            last_price = now; msg = check_price_change()
            if msg: gui(f"🚨 TÍN HIỆU REALTIME!\n━━━━━━━━━━━━━━━━━━\n{msg}\n\n{now_str()}")
        if now - last_events >= 3600:
            last_events = now
            for msg in check_events(): gui(f"{msg}\n\n{now_str()}")
        if now - last_geo >= 600:
            last_geo = now; msg = check_geo_emergency()
            if msg: gui(f"{msg}\n\n{now_str()}")
        if now - last_dom >= 3600:
            last_dom = now; dom = dominance_text()
            if dom: gui(f"📊 <b>CẬP NHẬT DOMINANCE</b>\n━━━━━━━━━━━━━━━━━━{dom}\n\n{now_str()}")
        time.sleep(10)
    except KeyboardInterrupt: gui("🛑 Bot Realtime đã dừng"); break
    except Exception as e: print(f"Lỗi: {e}"); time.sleep(30)