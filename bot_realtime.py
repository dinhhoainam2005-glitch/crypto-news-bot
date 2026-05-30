"""
BOT REALTIME - WHALE + LIQUIDATION + ETF + BIEN DONG
- Whale Alert: Đọc từ kênh Telegram miễn phí
- Liquidation: Coinglass API free
- ETF Flow: Farside scrape
- Biến động giá: CoinGecko API free
- Cảnh báo realtime khi có sự kiện bất thường
"""
import requests
import time
import json
import os
import re
from datetime import datetime, timedelta

TOKEN = os.getenv("TELEGRAM_TOKEN", "8893995280:AAF9XwWAm9QgPkwmDrhZdY6UQ4zfySooWpk")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "518284897")
WHALE_CHANNEL = "@whale_alert_io"

CHU_KY_COINGLASS = 60
CHU_KY_ETF = 300
CHU_KY_COINGECKO = 60
DATA_DIR = "data"
STATE_FILE = f"{DATA_DIR}/state_realtime.json"

THRESHOLDS = {
    'whale_min_usd': 50_000_000,
    'liquidation_min_usd': 100_000_000,
    'etf_flow_min_usd': 300_000_000,
    'price_change_pct': 3.0,
}

os.makedirs(DATA_DIR, exist_ok=True)

def get_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f: return json.load(f)
    return {"last_whale_id": 0, "last_liq_time": 0, "last_etf_time": 0, "last_price_time": 0}

def set_state(**kv):
    s = get_state(); s.update(kv)
    with open(STATE_FILE, 'w') as f: json.dump(s, f)

def gui(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                     data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except: pass

def now_str():
    n = datetime.now()
    return f"⏰ {n.strftime('%H:%M:%S')} | {n.strftime('%d/%m/%Y')}"

# ============================================
# 1. WHALE ALERT - DOC TU KENH TELEGRAM
# ============================================
def check_whale_alerts():
    """Đọc tin nhắn từ kênh Whale Alert Telegram"""
    try:
        # Dùng Telegram Bot API để đọc lịch sử kênh công khai
        url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
        r = requests.get(url, params={'offset': -10, 'limit': 10, 'timeout': 5}, timeout=10)
        
        if r.status_code != 200: return []
        
        updates = r.json().get('result', [])
        alerts = []
        
        for update in updates:
            # Kiểm tra nếu là tin nhắn từ kênh
            channel_post = update.get('channel_post')
            if not channel_post: continue
            
            text = channel_post.get('text', '')
            message_id = channel_post.get('message_id', 0)
            
            state = get_state()
            if message_id <= state.get('last_whale_id', 0): continue
            
            # Parse giao dịch: "X BTC (Y USD) transferred from A to B"
            match = re.search(r'([\d,]+)\s*(\w+)\s*\(?[\$\s]*([\d,]+)\)?\s*(?:USD)?\s*transferred', text, re.IGNORECASE)
            if not match:
                match = re.search(r'([\d,]+)\s*(\w+)\s*\(?[\$\s]*([\d,]+)', text, re.IGNORECASE)
            
            if match:
                amount = float(match.group(1).replace(',', ''))
                symbol = match.group(2).upper()
                value_usd = float(match.group(3).replace(',', ''))
                
                if value_usd >= THRESHOLDS['whale_min_usd'] and symbol in ['BTC', 'ETH', 'SOL', 'USDT', 'USDC']:
                    alerts.append({
                        'text': text,
                        'amount': amount,
                        'symbol': symbol,
                        'value_usd': value_usd,
                        'message_id': message_id
                    })
                    set_state(last_whale_id=message_id)
        
        return alerts
    except:
        return []

# ============================================
# 2. LIQUIDATION - COINGLASS API
# ============================================
def check_liquidation():
    """Kiểm tra thanh lý lớn từ Coinglass"""
    try:
        r = requests.get(
            "https://open-api-v3.coinglass.com/api/futures/liquidation/detail",
            params={'symbol': 'BTC', 'limit': 5},
            timeout=10,
            headers={'accept': 'application/json'}
        )
        if r.status_code != 200: return None
        
        data = r.json()
        if not data.get('data'): return None
        
        total_liq = 0
        for item in data['data'][:10]:
            total_liq += item.get('amount', 0)
        
        if total_liq >= THRESHOLDS['liquidation_min_usd']:
            return {
                'total_usd': total_liq,
                'count': len(data['data']),
                'data': data['data'][:3]
            }
        return None
    except:
        return None

# ============================================
# 3. ETF FLOW - SCRAPE FARSIDE
# ============================================
def check_etf_flow():
    """Kiểm tra dòng tiền ETF từ Farside"""
    try:
        r = requests.get("https://farside.co.uk/btc-flow/", timeout=10,
                        headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code != 200: return None
        
        html = r.text
        
        # Tìm dòng tổng "Total" và giá trị
        match = re.search(r'Total.*?\$?([\d,]+\.?\d*)\s*(m|M|b|B)?', html, re.DOTALL)
        if match:
            value = float(match.group(1).replace(',', ''))
            unit = match.group(2) if match.group(2) else ''
            if unit.lower() == 'b':
                value *= 1_000_000_000
            elif unit.lower() == 'm':
                value *= 1_000_000
            
            if abs(value) >= THRESHOLDS['etf_flow_min_usd']:
                direction = "🟢 VÀO" if value > 0 else "🔴 RA"
                return {
                    'value_usd': abs(value),
                    'direction': direction,
                    'raw_value': value
                }
        
        # Fallback: parse bảng HTML
        matches = re.findall(r'\$([\d,]+\.?\d*)\s*(m|M|b|B)?', html)
        if matches:
            values = []
            for m in matches[-5:]:
                v = float(m[0].replace(',', ''))
                u = m[1] if m[1] else ''
                if u.lower() == 'b': v *= 1_000_000_000
                elif u.lower() == 'm': v *= 1_000_000
                values.append(v)
            
            total = sum(values)
            if abs(total) >= THRESHOLDS['etf_flow_min_usd']:
                direction = "🟢 VÀO" if total > 0 else "🔴 RA"
                return {'value_usd': abs(total), 'direction': direction, 'raw_value': total}
        
        return None
    except:
        return None

# ============================================
# 4. BIEN DONG GIA - COINGECKO
# ============================================
def check_price_change():
    """Kiểm tra biến động giá bất thường"""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={
                'ids': 'bitcoin,ethereum,solana',
                'vs_currencies': 'usd',
                'include_24hr_change': 'true'
            },
            timeout=10
        )
        if r.status_code != 200: return None
        
        data = r.json()
        alerts = []
        
        coin_map = {'bitcoin': 'BTC', 'ethereum': 'ETH', 'solana': 'SOL'}
        emoji_map = {'bitcoin': '₿', 'ethereum': 'Ξ', 'solana': '◎'}
        
        for coin_id, info in data.items():
            change = info.get('usd_24h_change', 0)
            price = info.get('usd', 0)
            
            if abs(change) >= THRESHOLDS['price_change_pct']:
                direction = "🟢 TĂNG" if change > 0 else "🔴 GIẢM"
                alerts.append({
                    'coin': coin_map.get(coin_id, coin_id.upper()),
                    'emoji': emoji_map.get(coin_id, ''),
                    'price': price,
                    'change': change,
                    'direction': direction
                })
        
        return alerts if alerts else None
    except:
        return None

# ============================================
# MAIN
# ============================================
print("="*60)
print("BOT REALTIME - WHALE + LIQ + ETF + PRICE")
print("="*60)

gui(f"🚨 <b>Bot Realtime đã khởi động!</b>\n━━━━━━━━━━━━━━━━━━\n🐋 Whale Alert: >$50M\n💰 Liquidation: >$100M\n📊 ETF Flow: >$300M\n📈 Biến động: >3%\n\n{now_str()}")

last_whale_check = 0
last_liq_check = 0
last_etf_check = 0
last_price_check = 0

while True:
    try:
        now = time.time()
        
        # 1. Whale Alert - mỗi 15 giây
        if now - last_whale_check >= 15:
            last_whale_check = now
            whales = check_whale_alerts()
            for w in whales:
                gui(f"🐋 <b>WHALE ALERT!</b>\n━━━━━━━━━━━━━━━━━━\n"
                    f"💰 {w['text']}\n"
                    f"💵 Giá trị: <b>${w['value_usd']:,.0f}</b>\n"
                    f"🪙 {w['amount']:,.0f} {w['symbol']}\n\n"
                    f"💡 Cá voi chuyển {w['symbol']} → theo dõi biến động giá!\n\n{now_str()}")
        
        # 2. Liquidation - mỗi 60 giây
        if now - last_liq_check >= CHU_KY_COINGLASS:
            last_liq_check = now
            liq = check_liquidation()
            if liq:
                gui(f"💰 <b>THANH LÝ LỚN!</b>\n━━━━━━━━━━━━━━━━━━\n"
                    f"🔥 Tổng thanh lý: <b>${liq['total_usd']:,.0f}</b>\n"
                    f"📊 Số lệnh: {liq['count']}\n\n"
                    f"⚠️ Biến động mạnh → cân nhắc vào lệnh!\n\n{now_str()}")
        
        # 3. ETF Flow - mỗi 5 phút
        if now - last_etf_check >= CHU_KY_ETF:
            last_etf_check = now
            etf = check_etf_flow()
            if etf:
                gui(f"📊 <b>ETF FLOW BẤT THƯỜNG!</b>\n━━━━━━━━━━━━━━━━━━\n"
                    f"{etf['direction']}: <b>${etf['value_usd']:,.0f}</b>\n\n"
                    f"💡 Dòng tiền {etf['direction'].lower()} mạnh → {'🟢 LONG' if 'VÀO' in etf['direction'] else '🔴 SHORT'}\n\n{now_str()}")
        
        # 4. Biến động giá - mỗi 60 giây
        if now - last_price_check >= CHU_KY_COINGECKO:
            last_price_check = now
            changes = check_price_change()
            if changes:
                for c in changes:
                    gui(f"📈 <b>BIẾN ĐỘNG GIÁ!</b>\n━━━━━━━━━━━━━━━━━━\n"
                        f"{c['emoji']} {c['coin']}: {c['direction']} <b>{abs(c['change']):.1f}%</b>\n"
                        f"💵 Giá: <b>${c['price']:,.2f}</b>\n\n"
                        f"⚠️ Biến động {abs(c['change']):.1f}% → cơ hội trade!\n\n{now_str()}")
        
        time.sleep(5)
        
    except KeyboardInterrupt:
        gui("🛑 Bot Realtime đã dừng")
        break
    except Exception as e:
        print(f"Lỗi: {e}")
        time.sleep(10)