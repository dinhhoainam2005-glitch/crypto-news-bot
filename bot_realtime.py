# bot_realtime.py - 431 dòng
# CHỈ SỬA 2 PHẦN: EVENTS (dòng 200-220) và check_events() (dòng 250-310)
# TẤT CẢ CÁC PHẦN KHÁC GIỮ NGUYÊN 100%

"""
BOT REALTIME V2 - FULL SIGNALS + CMC - FINAL
- Thanh lý >$100M | ETF >$300M | Biến động >3%
- Sự kiện FOMC/CPI/NFP/GDP format chuẩn + Chiến lược + Hành động
- Địa chính trị khẩn cấp
- Dominance + Fear & Greed (CoinMarketCap)
- Top Gainers >20% (Vol>$1M, MCap>$10M)
- Volume Alert >200% (Vol>$10M, MCap>$50M)
- FedWatch rõ ràng
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
CMC_API_KEY = "ba07282bfe644708a9f42be12a33acf6"

DATA_DIR = "data"
LOG_FILE = f"{DATA_DIR}/log_realtime.json"
os.makedirs(DATA_DIR, exist_ok=True)

def gui(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except: pass

def now_str():
    n = datetime.now()
    return f"⏰ {n.strftime('%H:%M:%S')} | {n.strftime('%d/%m/%Y')}"

def get_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f: return json.load(f)
    return {"events_sent": {}, "news_sent": [], "gainers_sent": [], "volume_sent": []}

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
    for sid, fmt in [('DFF','LS Fed: {}%'),('CPIAUCSL','CPI: {}'),('UNRATE','TN: {}%'),('GDP','GDP: ${:,.0f}B')]:
        v = fred_get(sid)
        if v: parts.append(fmt.format(v[0]['v']))
    return " | ".join(parts) if parts else "Đang tải..."

# ============================================
# DOMINANCE + FEAR & GREED (CMC)
# ============================================
def get_cmc_global():
    try:
        headers = {'X-CMC_PRO_API_KEY': CMC_API_KEY}
        r = requests.get("https://pro-api.coinmarketcap.com/v1/global-metrics/quotes/latest", headers=headers, timeout=10)
        if r.status_code != 200: return None
        return r.json()['data']
    except: return None

def get_dominance():
    data = get_cmc_global()
    if not data: return None,None,None,None,None,None,None,None
    
    btc_d = round(data['btc_dominance'], 1)
    eth_d = round(data['eth_dominance'], 1)
    total_mcap = data['quote']['USD']['total_market_cap']
    fng_value = data.get('fear_greed_value') or data.get('market_mood')
    fng_text = data.get('fear_greed_classification', '')
    
    try:
        headers = {'X-CMC_PRO_API_KEY': CMC_API_KEY}
        r2 = requests.get("https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest", params={'symbol':'BTC,ETH,SOL'}, headers=headers, timeout=10)
        if r2.status_code == 200:
            coins = r2.json()['data']
            btc_change = round(coins['BTC']['quote']['USD']['percent_change_24h'], 1)
            eth_change = round(coins['ETH']['quote']['USD']['percent_change_24h'], 1)
            sol_change = round(coins['SOL']['quote']['USD']['percent_change_24h'], 1)
            sol_mcap = coins['SOL']['quote']['USD']['market_cap']
            sol_d = round(sol_mcap / total_mcap * 100, 1) if total_mcap > 0 else 0
            return btc_d, eth_d, sol_d, btc_change, eth_change, sol_change, fng_value, fng_text
    except: pass
    
    return btc_d, eth_d, 0, 0, 0, 0, fng_value, fng_text

def dominance_text():
    result = get_dominance()
    if not result or not result[0]: return ""
    btc_d, eth_d, sol_d, btc_ch, eth_ch, sol_ch, fng_val, fng_text = result
    
    def ch_icon(v):
        if v > 0: return f"🟢 +{v}%"
        elif v < 0: return f"🔴 {v}%"
        return "➡️ 0%"
    
    text = f"\n📊 <b>Dominance:</b>\n₿ BTC: <b>{btc_d}%</b> ({ch_icon(btc_ch)})\nΞ ETH: <b>{eth_d}%</b> ({ch_icon(eth_ch)})\n◎ SOL: <b>{sol_d}%</b> ({ch_icon(sol_ch)})\n"
    if btc_d > 58: text += "⚠️ <b>BTC.D CAO</b> → Altcoin yếu, ưu tiên BTC\n"
    elif btc_d < 48: text += "✅ <b>BTC.D THẤP</b> → Altcoin season, ưu tiên ETH/SOL\n"
    if abs(btc_ch) > 2: text += f"⚡ BTC.D đang {'TĂNG' if btc_ch>0 else 'GIẢM'} mạnh ({btc_ch:+.1f}%) → Dòng tiền đang dịch chuyển!\n"
    
    if fng_val is not None:
        i = "😱" if fng_val <= 25 else "😟" if fng_val <= 40 else "😐" if fng_val <= 60 else "😊" if fng_val <= 75 else "🤤"
        text += f"\n{i} <b>Fear & Greed:</b> {fng_val}/100 ({fng_text}) [CMC]\n"
    
    return text

# ============================================
# TOP GAINERS + VOLUME ALERT (CMC)
# ============================================
def check_top_movers():
    log = get_log()
    try:
        headers = {'X-CMC_PRO_API_KEY': CMC_API_KEY}
        r = requests.get("https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest", params={'limit':100,'sort':'percent_change_24h','sort_dir':'desc'}, headers=headers, timeout=10)
        if r.status_code != 200: return None
        
        data = r.json()['data']
        alerts = []
        
        for coin in data:
            try:
                change = coin['quote']['USD']['percent_change_24h']
                volume = coin['quote']['USD']['volume_24h']
                market_cap = coin['quote']['USD']['market_cap']
                name = coin['name']
                symbol = coin['symbol']
                
                if not change or abs(change) < 20: continue
                if not volume or volume < 1_000_000: continue
                if not market_cap or market_cap < 10_000_000: continue
                if symbol in ['USDT','USDC','DAI','BUSD','TUSD','USDP','USDD']: continue
                
                direction = "🟢 TĂNG" if change > 0 else "🔴 GIẢM"
                key = f"gainer_{symbol}"
                
                if key not in log['gainers_sent']:
                    log['gainers_sent'].append(key)
                    log['gainers_sent'] = log['gainers_sent'][-50:]
                    alerts.append(f"📈 <b>{symbol}</b> ({name[:20]}): {direction} <b>{abs(change):.1f}%</b>\n   💧 Vol: ${volume:,.0f} | 💰 MCap: ${market_cap:,.0f}")
            except: continue
        
        save_log(log)
        if alerts:
            return "🚀 <b>TOP BIẾN ĐỘNG 24H:</b>\n" + "\n".join(alerts[:5])
    except: pass
    return None

def check_volume_alert():
    log = get_log()
    try:
        headers = {'X-CMC_PRO_API_KEY': CMC_API_KEY}
        r = requests.get("https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest", params={'limit':100,'sort':'volume_24h','sort_dir':'desc'}, headers=headers, timeout=10)
        if r.status_code != 200: return None
        
        data = r.json()['data']
        alerts = []
        
        for coin in data:
            try:
                volume_24h = coin['quote']['USD']['volume_24h']
                volume_change = coin['quote']['USD'].get('volume_change_24h', 0) or 0
                market_cap = coin['quote']['USD']['market_cap']
                name = coin['name']
                symbol = coin['symbol']
                
                if not volume_24h or volume_24h < 10_000_000: continue
                if not market_cap or market_cap < 50_000_000: continue
                if abs(volume_change) < 200: continue
                if symbol in ['USDT','USDC','DAI','BUSD','TUSD']: continue
                
                direction = "🟢 TĂNG" if volume_change > 0 else "🔴 GIẢM"
                key = f"vol_{symbol}"
                
                if key not in log['volume_sent']:
                    log['volume_sent'].append(key)
                    log['volume_sent'] = log['volume_sent'][-50:]
                    alerts.append(f"📊 <b>{symbol}</b> ({name[:20]}): Volume {direction} <b>{abs(volume_change):.0f}%</b>\n   💧 Vol 24h: ${volume_24h:,.0f} | 💰 MCap: ${market_cap:,.0f}")
            except: continue
        
        save_log(log)
        if alerts:
            return "📊 <b>VOLUME ĐỘT BIẾN:</b>\n" + "\n".join(alerts[:3])
    except: pass
    return None

# ============================================
# THANH LY + ETF + PRICE
# ============================================
def check_liquidation():
    try:
        r = requests.get("https://open-api-v3.coinglass.com/api/futures/liquidation/detail", params={'symbol':'BTC','limit':5}, timeout=10, headers={'accept':'application/json'})
        if r.status_code != 200: return None
        data = r.json()
        if not data.get('data'): return None
        total = sum(item.get('amount',0) for item in data['data'][:10])
        if total >= 100_000_000:
            return f"💰 <b>THANH LÝ LỚN: ${total:,.0f}</b>\n📊 {len(data['data'])} lệnh\n⚠️ Biến động mạnh → cân nhắc vào lệnh!"
    except: pass
    return None

def check_etf_flow():
    try:
        r = requests.get("https://farside.co.uk/btc-flow/", timeout=10, headers={'User-Agent':'Mozilla/5.0'})
        if r.status_code != 200: return None
        match = re.search(r'Total.*?\$?([\d,]+\.?\d*)\s*(m|M|b|B)?', r.text, re.DOTALL)
        if match:
            value = float(match.group(1).replace(',',''))
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
        r = requests.get("https://api.coingecko.com/api/v3/simple/price", params={'ids':'bitcoin,ethereum,solana','vs_currencies':'usd','include_24hr_change':'true'}, timeout=10)
        if r.status_code != 200: return None
        data = r.json()
        alerts = []
        emoji = {'bitcoin':'₿','ethereum':'Ξ','solana':'◎'}
        name = {'bitcoin':'BTC','ethereum':'ETH','solana':'SOL'}
        for cid, info in data.items():
            ch = info.get('usd_24h_change',0)
            if abs(ch) >= 3.0:
                d = "🟢 TĂNG" if ch > 0 else "🔴 GIẢM"
                alerts.append(f"📈 {emoji[cid]} <b>{name[cid]}: {d} {abs(ch):.1f}%</b> | 💵 ${info['usd']:,.2f}")
        return "\n".join(alerts) if alerts else None
    except: pass
    return None

# ============================================
# FEDWATCH
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
        cpi_change = round((cpi_data[0]['v']-cpi_data[1]['v'])/cpi_data[1]['v']*100,1)
        if cpi_change > 0.3: prediction = f"⚠️ CPI tăng <b>{cpi_change}%</b> → Áp lực <b>TĂNG</b> lãi suất"
        elif cpi_change < -0.3: prediction = f"✅ CPI giảm <b>{abs(cpi_change)}%</b> → Có thể <b>GIẢM</b> lãi suất"
        else: prediction = f"➡️ CPI ổn định → Dự kiến <b>GIỮ NGUYÊN</b> lãi suất"
    else: prediction = "➡️ Chưa có dữ liệu CPI → Dự kiến <b>GIỮ NGUYÊN</b>"
    
    return {'current_rate':f"{current_rate}%",'trend':trend,'prediction':prediction}

# ============================================
# EVENTS - FORMAT CHUẨN (MỚI)
# ============================================
EVENTS = [
    {'id':'fomc_minutes_jun','name':'📋 Biên bản họp FOMC (T6)','date':'2026-06-04','time':'01:00','impact':'🟢 THẤP','desc':'Biên bản cuộc họp cũ - không có quyết định mới. Ít ảnh hưởng thị trường.','fred':'DFF','is_fomc':False},
    {'id':'nfp_may','name':'💼 Bảng lương NFP (T5)','date':'2026-06-05','time':'19:30','impact':'🔴 CAO','desc':'Báo cáo việc làm - chỉ báo sức khỏe kinh tế Mỹ.','fred':'UNRATE','is_fomc':False,'advice':'NFP > dự đoán → Kinh tế mạnh → 🟢 LONG\nNFP < dự đoán → Kinh tế yếu → 🔴 SHORT'},
    {'id':'cpi_may','name':'📊 Chỉ số CPI (T5)','date':'2026-06-11','time':'19:30','impact':'🔴 CAO','desc':'Chỉ số giá tiêu dùng - thước đo lạm phát quan trọng nhất.','fred':'CPIAUCSL','is_fomc':False,'advice':'CPI thấp → Fed dovish → 🟢 LONG\nCPI cao → Fed hawkish → 🔴 SHORT'},
    {'id':'ppi_may','name':'🏭 Chỉ số PPI (T5)','date':'2026-06-12','time':'19:30','impact':'🟡 TB','desc':'Chỉ số giá sản xuất - chỉ báo sớm của lạm phát.','fred':'PPIACO','is_fomc':False},
    {'id':'fomc_jun','name':'🏦 Quyết định lãi suất FOMC (T6)','date':'2026-06-18','time':'01:00','impact':'🔴 CAO - QUAN TRỌNG NHẤT THÁNG','desc':'Fed công bố quyết định lãi suất.','fred':'DFF','is_fomc':True,'advice':'GIỮ NGUYÊN → 🟢 LONG\nTĂNG → 🔴 SHORT\nGIẢM → 🟢 LONG mạnh\nĐóng bot 30p trước!','gold':'Hawkish → Vàng GIẢM | Dovish → Vàng TĂNG','crypto':'Hawkish → Crypto GIẢM | Dovish → Crypto TĂNG','usd':'Hawkish → USD TĂNG | Dovish → USD GIẢM'},
    {'id':'gdp_q2','name':'📊 GDP Quý 2/2026','date':'2026-06-25','time':'19:30','impact':'🔴 CAO','desc':'Tăng trưởng kinh tế Mỹ.','fred':'GDP','is_fomc':False,'advice':'GDP cao → 🟢 LONG\nGDP thấp → 🔴 SHORT'},
    {'id':'fomc_jul','name':'🏦 Quyết định lãi suất FOMC (T7)','date':'2026-07-30','time':'01:00','impact':'🔴 CAO - QUAN TRỌNG','desc':'Quyết định lãi suất Fed.','fred':'DFF','is_fomc':True,'advice':'GIỮ NGUYÊN → 🟢 LONG\nTĂNG → 🔴 SHORT\nĐóng bot 30p trước!','gold':'Hawkish → Vàng GIẢM | Dovish → Vàng TĂNG','crypto':'Hawkish → Crypto GIẢM | Dovish → Crypto TĂNG','usd':'Hawkish → USD TĂNG | Dovish → USD GIẢM'},
]

def check_events():
    log = get_log()
    now = datetime.now()
    today = now.date()
    msgs = []
    fedwatch = get_fedwatch_prediction()
    
    for ev in EVENTS:
        evd = datetime.strptime(ev['date'],'%Y-%m-%d').date()
        evdt = datetime.strptime(ev['date']+' '+ev['time'],'%Y-%m-%d %H:%M')
        days = (evd - today).days
        hours_since = (now - evdt).total_seconds()/3600 if evdt < now else -1
        
        if 0 <= days <= 5:
            key = f"pre_{ev['id']}"
            if time.time() - log['events_sent'].get(key,0) >= 3600:
                log['events_sent'][key] = time.time()
                
                cd = f"⚠️ <b>HÔM NAY</b> {ev['time']}" if days==0 else f"📅 <b>NGÀY MAI</b> {ev['time']}" if days==1 else f"📅 Còn <b>{days} ngày</b> - {ev['date']}"
                
                fw_text = ""
                if ev.get('is_fomc') and fedwatch:
                    fw_text = f"\n\n📊 <b>PHÂN TÍCH LÃI SUẤT (FRED):</b>\n{fedwatch['trend']}\n{fedwatch['prediction']}\n🏦 Hiện tại: {fedwatch['current_rate']}"
                
                tac_dong = ""
                if ev.get('gold') or ev.get('crypto') or ev.get('usd'):
                    tac_dong = f"\n\n📊 <b>TÁC ĐỘNG DỰ KIẾN:</b>\n"
                    if ev.get('gold'): tac_dong += f"🥇 Vàng: {ev['gold']}\n"
                    if ev.get('crypto'): tac_dong += f"₿ Crypto: {ev['crypto']}\n"
                    if ev.get('usd'): tac_dong += f"💵 USD: {ev['usd']}\n"
                
                chien_luoc = ""
                if ev.get('advice'):
                    chien_luoc = f"\n💡 <b>CHIẾN LƯỢC:</b>\n{ev['advice']}\n"
                
                msgs.append(
                    f"📅 <b>{ev['name']}</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"⏰ {cd}\n"
                    f"⚡ Mức độ: {ev['impact']}\n"
                    f"📝 {ev['desc']}"
                    f"{fw_text}{tac_dong}{chien_luoc}\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"📊 {econ_summary()}"
                )
        
        elif days < 0 and 1 <= hours_since <= 24:
            key = f"post_{ev['id']}"
            if key not in log['events_sent']:
                v = fred_get(ev['fred'])
                if v and len(v) >= 2:
                    curr, prev = v[0]['v'], v[1]['v']
                    
                    if 'fomc' in ev['id'] and 'minutes' not in ev['id']:
                        if curr > prev:
                            ket_qua = f"📈 <b>Fed TĂNG lãi suất</b> từ {prev}% lên {curr}%"
                            tac_dong = "🦅 <b>HAWKISH</b>"
                            hanh_dong = "🔴 SHORT Crypto"
                        elif curr < prev:
                            ket_qua = f"📉 <b>Fed GIẢM lãi suất</b> từ {prev}% xuống {curr}%"
                            tac_dong = "🕊️ <b>DOVISH</b>"
                            hanh_dong = "🟢 LONG Crypto"
                        else:
                            ket_qua = f"➡️ <b>Fed GIỮ NGUYÊN</b> ở mức {curr}%"
                            tac_dong = "➡️ <b>TRUNG LẬP</b>"
                            hanh_dong = "🟢 Tích cực nhẹ"
                    
                    elif ev['id'] == 'nfp_may':
                        ket_qua = f"📊 <b>Thất nghiệp: {curr}%</b>"
                        tac_dong = "✅ Mạnh" if curr < prev else "⚠️ Yếu"
                        hanh_dong = "🟢 LONG" if curr < prev else "🔴 SHORT"
                    
                    elif ev['id'] == 'cpi_may':
                        pct = round((curr-prev)/prev*100,1)
                        ket_qua = f"📊 <b>CPI: {curr}</b> ({'+' if pct>0 else ''}{pct}%)"
                        tac_dong = "⚠️ Nóng" if curr > prev else "✅ Hạ nhiệt"
                        hanh_dong = "🟢 LONG" if curr <= prev else "🔴 SHORT"
                    
                    else:
                        ket_qua = f"📊 <b>{curr}</b>"
                        tac_dong = "Đã cập nhật"
                        hanh_dong = "Theo dõi thêm"
                    
                    log['events_sent'][key] = time.time()
                    msgs.append(
                        f"✅ <b>{ev['name']} - KẾT QUẢ!</b>\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"⏰ {ev['date']} {ev['time']}\n"
                        f"📊 {ket_qua}\n"
                        f"🎤 {tac_dong}\n"
                        f"💡 {hanh_dong}\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"📊 {econ_summary()}"
                    )
    
    save_log(log)
    return msgs

GEO_QUERIES = ["iran israel war","russia ukraine attack","north korea missile","china taiwan war"]

def check_geo_emergency():
    log = get_log()
    for query in GEO_QUERIES:
        try:
            r = requests.get("https://newsapi.org/v2/everything", params={'q':query,'language':'en','sortBy':'publishedAt','pageSize':1,'apiKey':NEWS_API_KEY}, timeout=10)
            if r.status_code != 200: continue
            for a in r.json().get('articles',[]):
                title = a.get('title','')
                url = a.get('url','')
                if url in log['news_sent']: continue
                if any(re.search(r'\b'+kw+r'\b', title.lower()) for kw in ['strike','attack','war','missile','invasion','nuclear','bomb']):
                    log['news_sent'].append(url)
                    log['news_sent'] = log['news_sent'][-100:]
                    save_log(log)
                    return f"🌍 <b>ĐỊA CHÍNH TRỊ KHẨN!</b>\n━━━━━━━━━━━━━━━━━━\n🇬🇧 {title}\n📡 {(a.get('source',{}) or {}).get('name','Unknown')}\n⚠️ Xung đột leo thang → 🔴 SHORT\n━━━━━━━━━━━━━━━━━━\n📊 {econ_summary()}"
            time.sleep(0.3)
        except: continue
    return None

# ============================================
# MAIN
# ============================================
print("="*60)
print("BOT REALTIME V2 + CMC - FINAL")
print("="*60)

dom_text = dominance_text()
gui(f"🚨 <b>BOT REALTIME V2 ĐÃ KHỞI ĐỘNG!</b>\n━━━━━━━━━━━━━━━━━━\n"
    f"💰 Thanh lý >$100M | 📊 ETF >$300M | 📈 Biến động >3%\n"
    f"🏦 FOMC/CPI/NFP/GDP | 🌍 Địa chính trị khẩn\n"
    f"🚀 Top Gainers >20% | 📊 Volume >200%{dom_text}\n"
    f"━━━━━━━━━━━━━━━━━━\n{now_str()}")

last_liq = last_etf = last_price = last_events = last_geo = last_dom = last_movers = last_vol = 0

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
        
        if now - last_movers >= 1800:
            last_movers = now
            msg = check_top_movers()
            if msg: gui(f"🚀 TÍN HIỆU REALTIME!\n━━━━━━━━━━━━━━━━━━\n{msg}\n\n{now_str()}")
        
        if now - last_vol >= 1800:
            last_vol = now
            msg = check_volume_alert()
            if msg: gui(f"📊 TÍN HIỆU REALTIME!\n━━━━━━━━━━━━━━━━━━\n{msg}\n\n{now_str()}")
        
        if now - last_events >= 3600:
            last_events = now
            for msg in check_events():
                gui(f"{msg}\n\n{now_str()}")
        
        if now - last_geo >= 600:
            last_geo = now
            msg = check_geo_emergency()
            if msg: gui(f"{msg}\n\n{now_str()}")
        
        if now - last_dom >= 3600:
            last_dom = now
            dom = dominance_text()
            if dom: gui(f"📊 <b>CẬP NHẬT DOMINANCE</b>\n━━━━━━━━━━━━━━━━━━{dom}\n\n{now_str()}")
        
        time.sleep(10)
        
    except KeyboardInterrupt:
        gui("🛑 Bot Realtime đã dừng")
        break
    except Exception as e:
        print(f"Lỗi: {e}")
        time.sleep(30)