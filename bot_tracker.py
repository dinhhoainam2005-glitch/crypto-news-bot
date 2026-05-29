"""
BOT TRACKER - GHI CHEP & THONG KE HIEU SUAT TIN HIEU
- Tu dong ghi nhan tin hieu LONG/SHORT
- Cho phep danh dau DUNG/SAI qua Telegram
- Thong ke win rate theo coin, theo thoi gian
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

# ===== XU LY LENH =====
def process_command(text):
    text = text.strip().lower()
    
    # /dung 5 -> danh dau tin hieu #5 la DUNG
    if text.startswith('/dung'):
        try:
            idx = int(text.replace('/dung', '').strip()) - 1
            trades = load_trades()
            if 0 <= idx < len(trades):
                trades[idx]['result'] = 'DUNG'
                save_trades(trades)
                t = trades[idx]
                return f"✅ <b>#{idx+1} ĐÃ ĐÁNH DẤU ĐÚNG</b>\n{t['coin']} {t['signal']} | Entry: ${t['entry']:,.0f}"
            return "❌ Số thứ tự không hợp lệ"
        except:
            return "❌ Dùng: /dung [số]"
    
    # /sai 5 -> danh dau tin hieu #5 la SAI
    if text.startswith('/sai'):
        try:
            idx = int(text.replace('/sai', '').strip()) - 1
            trades = load_trades()
            if 0 <= idx < len(trades):
                trades[idx]['result'] = 'SAI'
                save_trades(trades)
                t = trades[idx]
                return f"❌ <b>#{idx+1} ĐÃ ĐÁNH DẤU SAI</b>\n{t['coin']} {t['signal']} | Entry: ${t['entry']:,.0f}"
            return "❌ Số thứ tự không hợp lệ"
        except:
            return "❌ Dùng: /sai [số]"
    
    # /ds -> xem danh sach tin hieu chua danh gia
    if text == '/ds':
        trades = load_trades()
        pending = [(i, t) for i, t in enumerate(trades) if t.get('result') == 'CHO']
        if not pending:
            return "📋 Không có tín hiệu nào chờ đánh giá"
        
        msg = f"📋 <b>{len(pending)} TÍN HIỆU CHỜ ĐÁNH GIÁ</b>\n━━━━━━━━━━━━━━━━━━\n"
        for i, t in pending[:10]:
            msg += f"#{i+1} | {t['time'][:16]} | {t['coin']} {t['signal']} | Entry: ${t['entry']:,.0f}\n"
        if len(pending) > 10:
            msg += f"\n... còn {len(pending)-10} tín hiệu"
        msg += f"\n\n💡 /dung [số] hoặc /sai [số] để đánh giá"
        return msg
    
    # /tk -> thong ke
    if text == '/tk':
        trades = load_trades()
        done = [t for t in trades if t.get('result') != 'CHO']
        if not done:
            return "📊 Chưa có tín hiệu nào được đánh giá"
        
        dung = sum(1 for t in done if t['result'] == 'DUNG')
        sai = sum(1 for t in done if t['result'] == 'SAI')
        total = len(done)
        win_rate = dung / total * 100 if total > 0 else 0
        
        # Thong ke theo coin
        coins = {}
        for t in done:
            coin = t['coin']
            if coin not in coins:
                coins[coin] = {'dung': 0, 'sai': 0}
            if t['result'] == 'DUNG':
                coins[coin]['dung'] += 1
            else:
                coins[coin]['sai'] += 1
        
        msg = f"📊 <b>THỐNG KÊ HIỆU SUẤT</b>\n━━━━━━━━━━━━━━━━━━\n"
        msg += f"✅ Đúng: <b>{dung}</b> | ❌ Sai: <b>{sai}</b>\n"
        msg += f"📈 Win Rate: <b>{win_rate:.1f}%</b>\n"
        msg += f"📋 Tổng: <b>{total}</b> tín hiệu đã đánh giá\n\n"
        msg += f"📊 <b>Theo Coin:</b>\n"
        for coin, stats in coins.items():
            total_c = stats['dung'] + stats['sai']
            wr_c = stats['dung'] / total_c * 100 if total_c > 0 else 0
            msg += f"• {coin}: {stats['dung']}/{total_c} ({wr_c:.0f}%)\n"
        
        return msg
    
    # /help
    if text == '/help':
        return (
            "📋 <b>BOT TRACKER - HƯỚNG DẪN</b>\n━━━━━━━━━━━━━━━━━━\n"
            "/ds - Xem tín hiệu chờ đánh giá\n"
            "/dung [số] - Đánh dấu ĐÚNG\n"
            "/sai [số] - Đánh dấu SAI\n"
            "/tk - Xem thống kê\n"
            "/help - Hướng dẫn"
        )
    
    return None

# ===== DOC TIN HIEU TU BOT TIN HIEU =====
def check_new_signals():
    """Đọc tín hiệu từ file log của bot tín hiệu"""
    signal_file = "data/tin_hieu_log.json"
    if not os.path.exists(signal_file):
        return
    
    with open(signal_file, 'r', encoding='utf-8') as f:
        signals = json.load(f)
    
    trades = load_trades()
    existing_times = [t['time'] for t in trades]
    
    new_count = 0
    for sig in signals:
        if sig['time'] not in existing_times:
            trades.append({
                'time': sig['time'],
                'coin': sig['coin'],
                'signal': sig['signal'],
                'gia': sig['gia'],
                'entry': sig['entry'],
                'sl': sig['sl'],
                'tp1': sig['tp1'],
                'tp2': sig['tp2'],
                'rr': sig['rr'],
                'do_manh': sig.get('do_manh', ''),
                'result': 'CHO'
            })
            new_count += 1
    
    if new_count > 0:
        save_trades(trades)
        print(f"📊 Thêm {new_count} tín hiệu mới")

# ===== DOC LENH TELEGRAM =====
def get_updates(offset=None):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
        params = {'timeout': 30, 'allowed_updates': ['message']}
        if offset:
            params['offset'] = offset
        r = requests.get(url, params=params, timeout=35)
        if r.status_code == 200:
            return r.json().get('result', [])
    except:
        pass
    return []

# === MAIN ===
print("=" * 50)
print("📊 BOT TRACKER")
print("=" * 50)

gui("📊 <b>Bot Tracker đã khởi động!</b>\n━━━━━━━━━━━━━━━━━━\n/ds - Xem tín hiệu chờ\n/tk - Thống kê\n/help - Hướng dẫn")

last_update_id = 0
last_signal_check = 0

while True:
    try:
        # Kiểm tra tín hiệu mới mỗi 5 phút
        if time.time() - last_signal_check >= 300:
            last_signal_check = time.time()
            check_new_signals()
        
        # Đọc lệnh Telegram
        updates = get_updates(last_update_id + 1)
        for u in updates:
            last_update_id = u['update_id']
            msg = u.get('message', {})
            text = msg.get('text', '')
            chat_id = str(msg.get('chat', {}).get('id', ''))
            
            # Chỉ phản hồi chat của bạn
            if chat_id == CHAT_ID:
                reply = process_command(text)
                if reply:
                    gui(reply)
        
        time.sleep(2)
    except KeyboardInterrupt:
        print("👋 Dừng")
        break
    except Exception as e:
        print(f"Lỗi: {e}")
        time.sleep(10)