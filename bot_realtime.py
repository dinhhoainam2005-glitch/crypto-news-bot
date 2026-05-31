"""
BOT REALTIME PRO - TIN HIEU THI TRUONG + DIA CHINH TRI KHAN CAP
- Thanh lý >$100M (Coinglass)
- ETF Flow >$300M (Farside)
- Biến động giá >3% (CoinGecko)
- Dominance + Fear & Greed (CMC)
- Top Gainers >20% (CMC)
- Volume Alert >200% (CMC)
- Trending Coins (CMC)
- Market Cap Change >3% (CMC)
- Địa chính trị KHẨN CẤP (Foreign Policy, ISW, CSIS, BBC, CNN)
- SKIP 5 phút đầu - không spam
- Hiển thị 3 múi giờ
"""
import requests
import time
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

TOKEN = os.getenv("TELEGRAM_TOKEN", "8893995280:AAF9XwWAm9QgPkwmDrhZdY6UQ4zfySooWpk")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "518284897")
CMC_API_KEY = "ba07282bfe644708a9f42be12a33acf6"

DATA_DIR = "data"
LOG_FILE = f"{DATA_DIR}/log_realtime.json"
SKIP_FIRST_MINUTES = 5
os.makedirs(DATA_DIR, exist_ok=True)

# ============================================
# NGUON DIA CHINH TRI PRO
# ============================================
GEO_RSS_FEEDS = [
    ("https://foreignpolicy.com/feed/", "Foreign Policy"),
    ("https://www.understandingwar.org/press-media/rss.xml", "ISW"),
    ("https://www.csis.org/rss.xml", "CSIS"),
    ("https://feeds.bbci.co.uk/news/world/rss.xml", "BBC World"),
    ("http://rss.cnn.com/rss/edition_world.rss", "CNN World"),
]

HOT_KW = [
    'strike', 'strikes', 'attack', 'attacks', 'missile', 'missiles',
    'bomb', 'bombing', 'bombed', 'invasion', 'invades', 'invading',
    'nuclear', 'launches', 'launched', 'fired', 'fires',
    'explosion', 'explosions', 'casualties', 'killed', 'dead', 'death toll',
    'troops', 'military action', 'offensive', 'counter-offensive',
    'retaliation', 'retaliatory', 'escalation', 'escalates',
    'declare war', 'declared war', 'state of war', 'war on',
    'mobilization', 'mobilize', 'deploy', 'deployed',
    'air strike', 'airstrike', 'drone strike', 'drone attack',
    'rocket', 'artillery', 'shelling', 'bombardment',
]

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
    return re.sub(r'<[^>]+>', '', t).strip()

def get_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f: return json.load(f)
    return {"gainers_sent":[],"volume_sent":[],"trending_sent":[],"mcap_sent":[],"geo_sent":[]}

def save_log(d):
    with open(LOG_FILE, 'w') as f: json.dump(d, f, ensure_ascii=False, indent=2)

# ============================================
# DOMINANCE + FEAR & GREED (CMC)
# ============================================
def get_dominance():
    try:
        headers = {'X-CMC_PRO_API_KEY': CMC_API_KEY}
        r = requests.get("https://pro-api.coinmarketcap.com/v1/global-metrics/quotes/latest", headers=headers, timeout=10)
        if r.status_code != 200: return None
        data = r.json()['data']
        btc_d = round(data['btc_dominance'], 1); eth_d = round(data['eth_dominance'], 1)
        total_mcap = data['quote']['USD']['total_market_cap']; total_vol = data['quote']['USD']['total_volume_24h']
        fng_value = data.get('fear_greed_value'); fng_text = data.get('fear_greed_classification','')
        r2 = requests.get("https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest", params={'symbol':'BTC,ETH,SOL'}, headers=headers, timeout=10)
        if r2.status_code != 200: return None
        coins = r2.json()['data']
        btc_ch = round(coins['BTC']['quote']['USD']['percent_change_24h'], 1)
        eth_ch = round(coins['ETH']['quote']['USD']['percent_change_24h'], 1)
        sol_ch = round(coins['SOL']['quote']['USD']['percent_change_24h'], 1)
        sol_mcap = coins['SOL']['quote']['USD']['market_cap']
        sol_d = round(sol_mcap / total_mcap * 100, 1) if total_mcap > 0 else 0
        return {'btc_d':btc_d,'eth_d':eth_d,'sol_d':sol_d,'btc_ch':btc_ch,'eth_ch':eth_ch,'sol_ch':sol_ch,'fng_value':fng_value,'fng_text':fng_text,'total_mcap':total_mcap,'total_vol':total_vol}
    except: return None

def dominance_text():
    dom = get_dominance()
    if not dom: return ""
    def ch_icon(v):
        if v > 0: return f"🟢 +{v}%"
        elif v < 0: return f"🔴 {v}%"
        return "➡️ 0%"
    text = f"\n📊 <b>Dominance:</b>\n₿ BTC: <b>{dom['btc_d']}%</b> ({ch_icon(dom['btc_ch'])})\nΞ ETH: <b>{dom['eth_d']}%</b> ({ch_icon(dom['eth_ch'])})\n◎ SOL: <b>{dom['sol_d']}%</b> ({ch_icon(dom['sol_ch'])})\n"
    if dom['btc_d'] > 58: text += "⚠️ <b>BTC.D CAO</b> → Altcoin yếu, ưu tiên BTC\n"
    elif dom['btc_d'] < 48: text += "✅ <b>BTC.D THẤP</b> → Altcoin season, ưu tiên ETH/SOL\n"
    fng_val = dom['fng_value']; fng_text = dom['fng_text']
    if fng_val is None:
        try:
            r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
            if r.status_code == 200: d = r.json()['data'][0]; fng_val = int(d['value']); fng_text = d['value_classification']
        except: pass
    if fng_val is not None:
        icons = {25:"😱",40:"😟",60:"😐",75:"😊",100:"🤤"}; icon = "😐"
        for t,i in icons.items():
            if fng_val <= t: icon = i; break
        text += f"\n{icon} <b>Fear & Greed:</b> {fng_val}/100 ({fng_text})\n"
    text += f"\n💰 <b>Total MCap:</b> ${dom['total_mcap']:,.0f}\n📊 <b>Volume 24h:</b> ${dom['total_vol']:,.0f}\n"
    return text

# ============================================
# 1. THANH LÝ (COINGLASS)
# ============================================
def check_liquidation():
    try:
        r = requests.get("https://open-api-v3.coinglass.com/api/futures/liquidation/detail",
                        params={'symbol':'BTC','limit':5}, timeout=10, headers={'accept':'application/json'})
        if r.status_code != 200: return None
        data = r.json()
        if not data.get('data'): return None
        total = sum(item.get('amount',0) for item in data['data'][:10])
        if total >= 100_000_000:
            return f"💰 <b>THANH LÝ LỚN: ${total:,.0f}</b>\n📊 {len(data['data'])} lệnh\n⚠️ Biến động mạnh → cân nhắc vào lệnh!"
    except: pass
    return None

# ============================================
# 2. ETF FLOW (FARSIDE)
# ============================================
def check_etf_flow():
    try:
        r = requests.get("https://farside.co.uk/btc-flow/", timeout=10, headers={'User-Agent':'Mozilla/5.0'})
        if r.status_code != 200: return None
        match = re.search(r'Total.*?\$?([\d,]+\.?\d*)\s*(m|M|b|B)?', r.text, re.DOTALL)
        if match:
            value = float(match.group(1).replace(',','')); unit = match.group(2) if match.group(2) else ''
            if unit.lower() == 'b': value *= 1_000_000_000
            elif unit.lower() == 'm': value *= 1_000_000
            if abs(value) >= 300_000_000:
                direction = "🟢 VÀO" if value > 0 else "🔴 RA"
                action = "🟢 LONG" if value > 0 else "🔴 SHORT"
                return f"📊 <b>ETF FLOW: {direction} ${abs(value):,.0f}</b>\n💡 → {action}"
    except: pass
    return None

# ============================================
# 3. BIẾN ĐỘNG GIÁ (COINGECKO)
# ============================================
def check_price_change():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price",
                        params={'ids':'bitcoin,ethereum,solana','vs_currencies':'usd','include_24hr_change':'true'}, timeout=10)
        if r.status_code != 200: return None
        data = r.json(); alerts = []
        emoji = {'bitcoin':'₿','ethereum':'Ξ','solana':'◎'}; name = {'bitcoin':'BTC','ethereum':'ETH','solana':'SOL'}
        for cid, info in data.items():
            ch = info.get('usd_24h_change',0)
            if abs(ch) >= 3.0:
                d = "🟢 TĂNG" if ch > 0 else "🔴 GIẢM"
                alerts.append(f"📈 {emoji[cid]} <b>{name[cid]}: {d} {abs(ch):.1f}%</b> | 💵 ${info['usd']:,.2f}")
        return "\n".join(alerts) if alerts else None
    except: pass
    return None

# ============================================
# 4. TOP GAINERS (CMC)
# ============================================
def check_top_movers():
    log = get_log()
    try:
        headers = {'X-CMC_PRO_API_KEY': CMC_API_KEY}
        r = requests.get("https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest",
                        params={'limit':100,'sort':'percent_change_24h','sort_dir':'desc'}, headers=headers, timeout=10)
        if r.status_code != 200: return None
        data = r.json()['data']; alerts = []
        for coin in data:
            try:
                change = coin['quote']['USD']['percent_change_24h']; vol = coin['quote']['USD']['volume_24h']
                mcap = coin['quote']['USD']['market_cap']; name = coin['name']; symbol = coin['symbol']
                if not change or abs(change) < 20: continue
                if not vol or vol < 1_000_000: continue
                if not mcap or mcap < 10_000_000: continue
                if symbol in ['USDT','USDC','DAI','BUSD']: continue
                direction = "🟢 TĂNG" if change > 0 else "🔴 GIẢM"; key = f"gainer_{symbol}"
                if key not in log['gainers_sent']:
                    log['gainers_sent'].append(key); log['gainers_sent'] = log['gainers_sent'][-50:]
                    alerts.append(f"📈 <b>{symbol}</b> ({name[:20]}): {direction} <b>{abs(change):.1f}%</b>\n   💧 Vol: ${vol:,.0f} | 💰 MCap: ${mcap:,.0f}")
            except: continue
        save_log(log)
        if alerts: return "🚀 <b>TOP BIẾN ĐỘNG 24H:</b>\n" + "\n".join(alerts[:5])
    except: pass
    return None

# ============================================
# 5. VOLUME ALERT (CMC)
# ============================================
def check_volume_alert():
    log = get_log()
    try:
        headers = {'X-CMC_PRO_API_KEY': CMC_API_KEY}
        r = requests.get("https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest",
                        params={'limit':100,'sort':'volume_24h','sort_dir':'desc'}, headers=headers, timeout=10)
        if r.status_code != 200: return None
        data = r.json()['data']; alerts = []
        for coin in data:
            try:
                vol24 = coin['quote']['USD']['volume_24h']; vol_ch = coin['quote']['USD'].get('volume_change_24h',0) or 0
                mcap = coin['quote']['USD']['market_cap']; name = coin['name']; symbol = coin['symbol']
                if not vol24 or vol24 < 10_000_000: continue
                if not mcap or mcap < 50_000_000: continue
                if abs(vol_ch) < 200: continue
                if symbol in ['USDT','USDC']: continue
                direction = "🟢 TĂNG" if vol_ch > 0 else "🔴 GIẢM"; key = f"vol_{symbol}"
                if key not in log['volume_sent']:
                    log['volume_sent'].append(key); log['volume_sent'] = log['volume_sent'][-50:]
                    alerts.append(f"📊 <b>{symbol}</b> ({name[:20]}): Volume {direction} <b>{abs(vol_ch):.0f}%</b>\n   💧 Vol 24h: ${vol24:,.0f} | 💰 MCap: ${mcap:,.0f}")
            except: continue
        save_log(log)
        if alerts: return "📊 <b>VOLUME ĐỘT BIẾN:</b>\n" + "\n".join(alerts[:3])
    except: pass
    return None

# ============================================
# 6. TRENDING (CMC)
# ============================================
def check_trending():
    log = get_log()
    try:
        headers = {'X-CMC_PRO_API_KEY': CMC_API_KEY}
        r = requests.get("https://pro-api.coinmarketcap.com/v1/cryptocurrency/trending/latest", headers=headers, timeout=10)
        if r.status_code != 200: return None
        data = r.json()['data']; alerts = []
        for coin in data[:5]:
            name = coin.get('name','?'); symbol = coin.get('symbol','?'); rank = coin.get('cmc_rank',0)
            key = f"trend_{symbol}"
            if key not in log['trending_sent']:
                log['trending_sent'].append(key); log['trending_sent'] = log['trending_sent'][-30:]
                alerts.append(f"🔥 <b>{symbol}</b> ({name[:20]}) - Rank #{rank}")
        save_log(log)
        if alerts: return "🔥 <b>TRENDING COINS (CMC):</b>\n" + "\n".join(alerts[:5])
    except: pass
    return None

# ============================================
# 7. MCAP CHANGE (CMC)
# ============================================
def check_mcap_change():
    log = get_log()
    try:
        headers = {'X-CMC_PRO_API_KEY': CMC_API_KEY}
        r = requests.get("https://pro-api.coinmarketcap.com/v1/global-metrics/quotes/latest", headers=headers, timeout=10)
        if r.status_code != 200: return None
        data = r.json()['data']
        total_mcap = data['quote']['USD']['total_market_cap']
        yesterday = data['quote']['USD'].get('total_market_cap_yesterday', total_mcap)
        change_pct = round((total_mcap - yesterday) / yesterday * 100, 1) if yesterday > 0 else 0
        key = f"mcap_{datetime.now().strftime('%Y%m%d_%H')}"
        if abs(change_pct) >= 3 and key not in log['mcap_sent']:
            log['mcap_sent'].append(key); log['mcap_sent'] = log['mcap_sent'][-50:]; save_log(log)
            direction = "🟢 TĂNG" if change_pct > 0 else "🔴 GIẢM"
            return f"💰 <b>TOTAL MCAP:</b> {direction} <b>{abs(change_pct):.1f}%</b>\n💵 ${total_mcap:,.0f}\n{'🟢 Dòng tiền vào → LONG' if change_pct > 0 else '🔴 Dòng tiền ra → SHORT'}"
    except: pass
    return None

# ============================================
# 8. ĐỊA CHÍNH TRỊ KHẨN CẤP (PRO SOURCES)
# ============================================
def check_geo_emergency():
    log = get_log()
    
    for url, src_name in GEO_RSS_FEEDS:
        try:
            r = requests.get(url, timeout=15, headers={'User-Agent':'Mozilla/5.0'})
            if r.status_code != 200: continue
            
            root = ET.fromstring(r.content)
            items = root.findall('.//item') or root.findall('.//{http://www.w3.org/2005/Atom}entry')
            
            for item in items[:3]:
                title_el = item.find('title') or item.find('{http://www.w3.org/2005/Atom}title')
                title = title_el.text if title_el is not None else ''
                
                desc_el = item.find('description') or item.find('{http://www.w3.org/2005/Atom}summary')
                desc = clean_html(desc_el.text) if desc_el is not None and desc_el.text else ''
                
                link_el = item.find('link') or item.find('{http://www.w3.org/2005/Atom}link')
                link = (link_el.get('href') or link_el.text or '') if link_el is not None else ''
                
                date_el = item.find('pubDate') or item.find('{http://www.w3.org/2005/Atom}updated') or item.find('{http://www.w3.org/2005/Atom}published')
                pubdate = date_el.text if date_el is not None else ''
                
                if not title or link in log['geo_sent']: continue
                
                full_text = (title + " " + desc).lower()
                
                # Phải có từ khóa KHẨN CẤP
                if not any(re.search(r'\b' + kw + r'\b', full_text) for kw in HOT_KW):
                    continue
                
                # Bỏ qua bài phân tích
                analysis_words = ['analysis','opinion','essay','what if','could','might','why ','how to']
                if any(kw in full_text for kw in analysis_words):
                    continue
                
                log['geo_sent'].append(link)
                log['geo_sent'] = log['geo_sent'][-200:]
                save_log(log)
                
                # Phân loại mức độ
                if any(kw in full_text for kw in ['nuclear','invasion','troops deploy','mobilization','declare war']):
                    level = "🔴🔴🔴 CỰC KỲ NGHIÊM TRỌNG"
                    action = "⚠️ Đóng tất cả lệnh, chờ thị trường ổn định"
                elif any(kw in full_text for kw in ['strike','attack','bombing','casualties','killed','missile']):
                    level = "🔴🔴 NGHIÊM TRỌNG"
                    action = "⚠️ Cân nhắc SHORT, giảm risk"
                else:
                    level = "🔴 CĂNG THẲNG"
                    action = "⚠️ Theo dõi, ưu tiên SHORT"
                
                return (
                    f"🌍 <b>ĐỊA CHÍNH TRỊ KHẨN CẤP!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🚨 Mức độ: {level}\n"
                    f"📡 Nguồn: {src_name}\n"
                    f"🇬🇧 {title}\n"
                    f"💡 {action}\n"
                    f"━━━━━━━━━━━━━━━━━━\n{now_str()}"
                )
        except: continue
    
    return None

# ============================================
# MAIN
# ============================================
print("="*60)
print("BOT REALTIME PRO - TIN HIEU THI TRUONG + DIA CHINH TRI")
print("="*60)

dom_text = dominance_text()
gui(f"🚨 <b>BOT REALTIME PRO ĐÃ KHỞI ĐỘNG!</b>\n"
    f"━━━━━━━━━━━━━━━━━━\n"
    f"💰 Thanh lý >$100M | 📊 ETF >$300M | 📈 Biến động >3%\n"
    f"🚀 Top Gainers >20% | 📊 Volume >200%\n"
    f"🔥 Trending | 💰 MCap Change >3%\n"
    f"🌍 Địa chính trị: Foreign Policy, ISW, CSIS, BBC, CNN{dom_text}\n"
    f"━━━━━━━━━━━━━━━━━━\n{now_str()}")

last_liq=last_etf=last_price=last_movers=last_vol=last_trending=last_mcap=last_geo=last_dom=0
startup_time = time.time()

while True:
    try:
        now = time.time()
        
        # SKIP 5 phút đầu
        if time.time() - startup_time < SKIP_FIRST_MINUTES * 60:
            time.sleep(10)
            continue
        
        if now - last_liq >= 60:
            last_liq = now; msg = check_liquidation()
            if msg: gui(f"🚨 TÍN HIỆU REALTIME!\n━━━━━━━━━━━━━━━━━━\n{msg}\n\n{now_str()}")
        
        if now - last_etf >= 300:
            last_etf = now; msg = check_etf_flow()
            if msg: gui(f"🚨 TÍN HIỆU REALTIME!\n━━━━━━━━━━━━━━━━━━\n{msg}\n\n{now_str()}")
        
        if now - last_price >= 60:
            last_price = now; msg = check_price_change()
            if msg: gui(f"🚨 TÍN HIỆU REALTIME!\n━━━━━━━━━━━━━━━━━━\n{msg}\n\n{now_str()}")
        
        if now - last_movers >= 1800:
            last_movers = now; msg = check_top_movers()
            if msg: gui(f"🚀 TÍN HIỆU REALTIME!\n━━━━━━━━━━━━━━━━━━\n{msg}\n\n{now_str()}")
        
        if now - last_vol >= 1800:
            last_vol = now; msg = check_volume_alert()
            if msg: gui(f"📊 TÍN HIỆU REALTIME!\n━━━━━━━━━━━━━━━━━━\n{msg}\n\n{now_str()}")
        
        if now - last_trending >= 1800:
            last_trending = now; msg = check_trending()
            if msg: gui(f"🔥 TÍN HIỆU REALTIME!\n━━━━━━━━━━━━━━━━━━\n{msg}\n\n{now_str()}")
        
        if now - last_mcap >= 1800:
            last_mcap = now; msg = check_mcap_change()
            if msg: gui(f"💰 TÍN HIỆU REALTIME!\n━━━━━━━━━━━━━━━━━━\n{msg}\n\n{now_str()}")
        
        if now - last_geo >= 180:
            last_geo = now; msg = check_geo_emergency()
            if msg: gui(f"{msg}")
        
        if now - last_dom >= 3600:
            last_dom = now; dom = dominance_text()
            if dom: gui(f"📊 <b>CẬP NHẬT DOMINANCE</b>\n━━━━━━━━━━━━━━━━━━{dom}\n\n{now_str()}")
        
        time.sleep(10)
    
    except KeyboardInterrupt: gui("🛑 Bot Realtime đã dừng"); break
    except Exception as e: print(f"Lỗi: {e}"); time.sleep(30)