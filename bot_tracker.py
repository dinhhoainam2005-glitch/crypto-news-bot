"""
BOT TRACKER - TU DONG THEO DOI TIN HIEU + BAO CAO 12H
- Theo doi gia real-time sau khi co tin hieu
- Tu dong danh dau DUNG/SAI khi cham TP/SL
- Gui Telegram ngay khi co ket qua
- Bao cao hieu suat moi 12h
"""
import requests
import time
import json
import os
from datetime import datetime, timedelta

TOKEN = os.getenv("TELEGRAM_TOKEN", "8893995280:AAF9XwWAm9QgPkwmDrhZdY6UQ4zfySooWpk")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "518284897")

DATA_DIR = "data"
TRADE_FILE = f"{DATA_DIR}/trades.json"
SIGNAL_FILE = f"{DATA_DIR}/tin_hieu_log.json"

os.makedirs(DATA_DIR, exist_ok=True)

def load_trades():
    if os.path.exists(TRADE_FILE):
        with open(TRADE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_trades(trades):
    with open(TRADE_FILE, 'w', encoding='utf-8') as f:
        json.dump(trades, f, ensure_ascii=False, indent=2)

def gui(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                     data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except: pass

# ===== LAY GIA HIEN TAI =====
def get_price(coin):
    try:
        r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={coin}USDT", timeout=5)
        return float(r.json()['price'])
    except:
        return None

# ===== DOC TIN HIEU MOI =====
def load_signals():
    if os.path.exists(SIGNAL_FILE):
        with open(SIGNAL_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

# ===== THEO DOI TIN HIEU =====
def theo_doi_tin_hieu():
    signals = load_signals()
    trades = load_trades()
    existing_times = [t['time'] for t in trades]
    updated = False
    
    # Them tin hieu moi vao theo doi
    for sig in signals:
        if sig['time'] not in existing_times:
            trades.append({
                'time': sig['time'],
                'coin': sig['coin'],
                'signal': sig['signal'],
                'entry': sig['entry'],
                'sl': sig['sl'],
                'tp1': sig['tp1'],
                'tp2': sig.get('tp2', 0),
                'gia_hien_tai': sig['gia'],
                'result': 'CHO',
                'exit_price': 0,
                'exit_time': '',
                'pnl': 0
            })
            updated = True
    
    # Kiem tra cac tin hieu CHO
    for t in trades:
        if t['result'] != 'CHO':
            continue
        
        price = get_price(t['coin'])
        if price is None:
            continue
        
        signal = t['signal']
        tp = t['tp1']
        sl = t['sl']
        entry = t['entry']
        
        hit = False
        
        if signal == 'LONG':
            if price >= tp:
                t['result'] = 'DUNG'
                t['exit_price'] = tp
                t['pnl'] = round((tp - entry) / entry * 100, 2)
                hit = True
            elif price <= sl:
                t['result'] = 'SAI'
                t['exit_price'] = sl
                t['pnl'] = round((sl - entry) / entry * 100, 2)
                hit = True
        else:  # SHORT
            if price <= tp:
                t['result'] = 'DUNG'
                t['exit_price'] = tp
                t['pnl'] = round((entry - tp) / entry * 100, 2)
                hit = True
            elif price >= sl:
                t['result'] = 'SAI'
                t['exit_price'] = sl
                t['pnl'] = round((entry - sl) / entry * 100, 2)
                hit = True
        
        if hit:
            t['exit_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            updated = True
            
            # Gui Telegram ngay
            icon = "✅" if t['result'] == 'DUNG' else "❌"
            emoji = "🎉" if t['result'] == 'DUNG' else "😞"
            
            msg = f"{icon} <b>TIN HIEU {t['result']}</b> {emoji}\n"
            msg += f"━━━━━━━━━━━━━━━━\n"
            msg += f"📊 {t['coin']} {t['signal']}\n"
            msg += f"💰 Entry: <b>${t['entry']:,.2f}</b>\n"
            msg += f"🎯 Thoat: <b>${t['exit_price']:,.2f}</b>\n"
            msg += f"📈 PnL: <b>{t['pnl']:+.2f}%</b>\n"
            msg += f"⏰ {t['exit_time']}"
            gui(msg)
    
    if updated:
        save_trades(trades)

# ===== BAO CAO 12H =====
_last_report = 0

def bao_cao_12h():
    global _last_report
    now = time.time()
    
    if now - _last_report < 43200:  # 12h = 43200s
        return
    
    _last_report = now
    trades = load_trades()
    done = [t for t in trades if t['result'] != 'CHO']
    
    if not done:
        return
    
    dung = sum(1 for t in done if t['result'] == 'DUNG')
    sai = sum(1 for t in done if t['result'] == 'SAI')
    total = len(done)
    win_rate = dung / total * 100 if total > 0 else 0
    total_pnl = sum(t['pnl'] for t in done)
    
    # Theo coin
    coins = {}
    for t in done:
        c = t['coin']
        if c not in coins:
            coins[c] = {'dung': 0, 'sai': 0, 'pnl': 0}
        if t['result'] == 'DUNG':
            coins[c]['dung'] += 1
        else:
            coins[c]['sai'] += 1
        coins[c]['pnl'] += t['pnl']
    
    # 12h gan nhat
    cutoff = (datetime.now() - timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")
    recent = [t for t in done if t.get('exit_time', '') >= cutoff]
    recent_dung = sum(1 for t in recent if t['result'] == 'DUNG')
    recent_sai = sum(1 for t in recent if t['result'] == 'SAI')
    recent_total = len(recent)
    recent_wr = recent_dung / recent_total * 100 if recent_total > 0 else 0
    recent_pnl = sum(t['pnl'] for t in recent)
    
    msg = f"📊 <b>BAO CAO HIEU SUAT 12H</b>\n"
    msg += f"━━━━━━━━━━━━━━━━\n"
    msg += f"⏰ {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}\n\n"
    
    msg += f"📈 <b>12H QUA:</b>\n"
    msg += f"✅ Đúng: <b>{recent_dung}</b> | ❌ Sai: <b>{recent_sai}</b>\n"
    msg += f"📊 Win Rate: <b>{recent_wr:.1f}%</b>\n"
    msg += f"💰 PnL: <b>{recent_pnl:+.2f}%</b>\n\n"
    
    msg += f"📊 <b>TONG KET:</b>\n"
    msg += f"✅ Đúng: <b>{dung}</b> | ❌ Sai: <b>{sai}</b>\n"
    msg += f"📊 Win Rate: <b>{win_rate:.1f}%</b>\n"
    msg += f"💰 Tong PnL: <b>{total_pnl:+.2f}%</b>\n\n"
    
    msg += f"📊 <b>THEO COIN:</b>\n"
    for c, s in coins.items():
        t = s['dung'] + s['sai']
        wr = s['dung'] / t * 100 if t > 0 else 0
        msg += f"• {c}: {s['dung']}/{t} ({wr:.0f}%) | PnL: {s['pnl']:+.2f}%\n"
    
    # Dang theo doi
    pending = [t for t in trades if t['result'] == 'CHO']
    if pending:
        msg += f"\n⏳ <b>DANG THEO DOI:</b> {len(pending)} tin hieu"
    
    gui(msg)

# ===== MAIN =====
print("=" * 50)
print("📊 BOT TRACKER - TU DONG THEO DOI")
print("=" * 50)

gui("📊 <b>Bot Tracker da khoi dong!</b>\n✅ Tu dong theo doi tin hieu\n📊 Bao cao moi 12h")

while True:
    try:
        theo_doi_tin_hieu()
        bao_cao_12h()
        time.sleep(30)  # Kiem tra moi 30 giay
    except KeyboardInterrupt:
        print("👋 Dung")
        break
    except Exception as e:
        print(f"Loi: {e}")
        time.sleep(30)