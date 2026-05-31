"""
BOT TIN HIEU GIAO DICH + TRACKER V16 - PRO VERSION
- V16: 3 coin x 3 khung - ADX + S/R THUC TE + Entry ly tuong
- S/R thuc te tu bieu do (swing high/low + cluster)
- Entry = S/R gan nhat (ngay thuong) hoac MA20 (cuoi tuan)
- Weekend Mode: Tu dong giam R:R + Entry linh hoat
- Tracker: PENDING -> ACTIVE -> CLOSED (theo doi trang thai thuc)
- Bao cao 12h
"""
import requests
import pandas as pd
import numpy as np
import time
import json
import os
from datetime import datetime, timedelta

TOKEN = os.getenv("TELEGRAM_TOKEN", "8893995280:AAF9XwWAm9QgPkwmDrhZdY6UQ4zfySooWpk")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "518284897")

DANH_SACH_COIN = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
CAC_KHUNG = ["1h", "4h", "1d"]
CHU_KY = 300
NGUONG_DIEM_TREND = 5
NGUONG_DIEM_SIDEWAY = 4
ADX_SIDEWAY = 20
ADX_MIN = 20

tin_hieu_cu = {}
TRACKER_FILE = "data/trades.json"
_last_report = 0
os.makedirs("data", exist_ok=True)

def is_weekend():
    return datetime.now().weekday() >= 5

def get_rr_threshold():
    return 1.2 if is_weekend() else 1.5

def gui(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                     data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except: pass

def now_str():
    n = datetime.now()
    return f"🕐 {n.strftime('%H:%M')} (Asia) | {(n-timedelta(hours=5)).strftime('%H:%M')} (EU) | {(n-timedelta(hours=11)).strftime('%H:%M')} (US) | {n.strftime('%d/%m/%Y')}"

def clean_old_signals(signal_dict, max_hours=24):
    now = datetime.now()
    for key in list(signal_dict.keys()):
        if (now - signal_dict[key]).total_seconds() > max_hours * 3600:
            del signal_dict[key]

# ============================================
# TRACKER - PENDING -> ACTIVE -> CLOSED
# ============================================
def _t_load():
    if os.path.exists(TRACKER_FILE):
        with open(TRACKER_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def _t_save(trades):
    with open(TRACKER_FILE, 'w', encoding='utf-8') as f:
        json.dump(trades, f, ensure_ascii=False, indent=2)

def _t_price(coin):
    try:
        r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={coin}USDT", timeout=5)
        return float(r.json()['price'])
    except:
        return None

def tracker_them(coin, signal, entry, sl, tp1, tp2):
    """Thêm lệnh mới với trạng thái PENDING"""
    trades = _t_load()
    trades.append({
        'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'coin': coin.replace('USDT', ''),
        'signal': signal,
        'entry': entry,
        'sl': sl,
        'tp1': tp1,
        'tp2': tp2,
        'status': 'PENDING',
        'entry_price': 0,
        'entry_time': '',
        'exit_price': 0,
        'exit_time': '',
        'pnl': 0
    })
    _t_save(trades)

def tracker_check():
    """Kiểm tra trạng thái lệnh: PENDING -> ACTIVE -> CLOSED"""
    trades = _t_load()
    updated = False
    
    for t in trades:
        status = t.get('status', 'PENDING')
        
        # Bỏ qua lệnh đã đóng
        if status in ['CLOSED_WIN', 'CLOSED_LOSS']:
            continue
        
        price = _t_price(t['coin'])
        if price is None:
            continue
        
        signal = t['signal']
        entry = t['entry']
        sl = t['sl']
        tp1 = t['tp1']
        
        # === PENDING: Kiểm tra giá chạm Entry chưa ===
        if status == 'PENDING':
            hit_entry = False
            
            if signal == 'LONG' and price <= entry:
                hit_entry = True
            elif signal == 'SHORT' and price >= entry:
                hit_entry = True
            
            if hit_entry:
                t['status'] = 'ACTIVE'
                t['entry_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                t['entry_price'] = price
                updated = True
                gui(
                    f"📊 <b>[V16] ĐÃ KHỚP LỆNH!</b>\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"📌 {t['coin']} {t['signal']}\n"
                    f"💰 Entry: <b>${entry:,.2f}</b>\n"
                    f"💵 Giá khớp: <b>${price:,.2f}</b>\n"
                    f"⏰ {t['entry_time']}"
                )
        
        # === ACTIVE: Kiểm tra TP/SL ===
        elif status == 'ACTIVE':
            hit = False
            
            if signal == 'LONG':
                if price >= tp1:
                    t['status'] = 'CLOSED_WIN'
                    t['exit_price'] = tp1
                    t['pnl'] = round((tp1 - entry) / entry * 100, 2)
                    hit = True
                elif price <= sl:
                    t['status'] = 'CLOSED_LOSS'
                    t['exit_price'] = sl
                    t['pnl'] = round((sl - entry) / entry * 100, 2)
                    hit = True
            
            else:  # SHORT
                if price <= tp1:
                    t['status'] = 'CLOSED_WIN'
                    t['exit_price'] = tp1
                    t['pnl'] = round((entry - tp1) / entry * 100, 2)
                    hit = True
                elif price >= sl:
                    t['status'] = 'CLOSED_LOSS'
                    t['exit_price'] = sl
                    t['pnl'] = round((entry - sl) / entry * 100, 2)
                    hit = True
            
            if hit:
                t['exit_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                updated = True
                icon = "✅" if t['status'] == 'CLOSED_WIN' else "❌"
                emoji = "🎉" if t['status'] == 'CLOSED_WIN' else "😞"
                result_text = "THẮNG" if t['status'] == 'CLOSED_WIN' else "THUA"
                gui(
                    f"{icon} <b>[V16] KẾT QUẢ: {result_text}</b> {emoji}\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"📊 {t['coin']} {t['signal']}\n"
                    f"💰 Entry: <b>${entry:,.2f}</b>\n"
                    f"🎯 Thoát: <b>${t['exit_price']:,.2f}</b>\n"
                    f"📈 PnL: <b>{t['pnl']:+.2f}%</b>\n"
                    f"⏰ {t['exit_time']}"
                )
    
    if updated:
        _t_save(trades)

def tracker_report():
    """Báo cáo 12h"""
    global _last_report
    now = time.time()
    if now - _last_report < 43200:
        return
    _last_report = now
    
    trades = _t_load()
    
    # Lệnh đã đóng
    closed = [t for t in trades if t.get('status') in ['CLOSED_WIN', 'CLOSED_LOSS']]
    if not closed:
        return
    
    wins = [t for t in closed if t['status'] == 'CLOSED_WIN']
    losses = [t for t in closed if t['status'] == 'CLOSED_LOSS']
    
    total = len(closed)
    wr = len(wins) / total * 100 if total > 0 else 0
    total_pnl = sum(t.get('pnl', 0) for t in closed)
    
    cutoff = (datetime.now() - timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")
    recent = [t for t in closed if t.get('exit_time', '') >= cutoff]
    r_wins = sum(1 for t in recent if t['status'] == 'CLOSED_WIN')
    r_losses = sum(1 for t in recent if t['status'] == 'CLOSED_LOSS')
    r_total = len(recent)
    r_wr = r_wins / r_total * 100 if r_total > 0 else 0
    r_pnl = sum(t.get('pnl', 0) for t in recent)
    
    pending = [t for t in trades if t.get('status') == 'PENDING']
    active = [t for t in trades if t.get('status') == 'ACTIVE']
    
    msg = (
        f"📊 <b>BÁO CÁO V16 12H</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}\n\n"
        f"📈 <b>12H QUA:</b>\n"
        f"✅ Thắng: <b>{r_wins}</b> | ❌ Thua: <b>{r_losses}</b>\n"
        f"📊 Win Rate: <b>{r_wr:.1f}%</b>\n"
        f"💰 PnL: <b>{r_pnl:+.2f}%</b>\n\n"
        f"📊 <b>TỔNG:</b>\n"
        f"✅ Thắng: <b>{len(wins)}</b> | ❌ Thua: <b>{len(losses)}</b>\n"
        f"📊 Win Rate: <b>{wr:.1f}%</b>\n"
        f"💰 Tổng PnL: <b>{total_pnl:+.2f}%</b>"
    )
    
    if pending:
        msg += f"\n\n⏳ <b>CHỜ KHỚP:</b> {len(pending)} lệnh"
    if active:
        msg += f"\n📊 <b>ĐANG CHẠY:</b> {len(active)} lệnh"
    
    gui(msg)

# ============================================
# PRICE ACTION DETECTION
# ============================================
def detect_price_action(df):
    o, h, l, c = df['open'].iloc[-1], df['high'].iloc[-1], df['low'].iloc[-1], df['close'].iloc[-1]
    o1, h1, l1, c1 = df['open'].iloc[-2], df['high'].iloc[-2], df['low'].iloc[-2], df['close'].iloc[-2]
    o2, h2, l2, c2 = df['open'].iloc[-3], df['high'].iloc[-3], df['low'].iloc[-3], df['close'].iloc[-3]
    body = abs(c - o)
    total_range = h - l
    results = []
    
    lower_wick = min(o, c) - l
    if body > 0 and lower_wick > body * 2 and total_range > 0:
        if (c - l) / total_range > 0.7:
            results.append(("HAMMER 🔨", "BULLISH"))
    
    if c > o and c1 < o1 and o <= c1 and c >= o1:
        results.append(("BULLISH ENGULFING 🟢", "BULLISH"))
    
    if c2 < o2 and body > 0 and abs(c1-o1) < body*0.5 and c > o and c > (o2+c2)/2:
        results.append(("MORNING STAR ⭐", "BULLISH"))
    
    upper_wick = h - max(o, c)
    if body > 0 and upper_wick > body * 2 and total_range > 0:
        if (h - c) / total_range > 0.7:
            results.append(("SHOOTING STAR 🌠", "BEARISH"))
    
    if c < o and c1 > o1 and o >= c1 and c <= o1:
        results.append(("BEARISH ENGULFING 🔴", "BEARISH"))
    
    if c2 > o2 and body > 0 and abs(c1-o1) < body*0.5 and c < o and c < (o2+c2)/2:
        results.append(("EVENING STAR ⭐", "BEARISH"))
    
    if total_range > 0 and body / total_range < 0.1:
        if l < min(l1, l2):
            results.append(("DRAGONFLY DOJI 🐉", "BULLISH"))
        elif h > max(h1, h2):
            results.append(("GRAVESTONE DOJI 🪦", "BEARISH"))
    
    return results

def lay_nen(symbol, khung, limit=100):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": khung, "limit": limit}
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        df = pd.DataFrame(data, columns=[
            'time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades',
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])
        for col in ['close', 'high', 'low', 'open', 'volume']:
            df[col] = df[col].astype(float)
        return df
    except:
        return None

def tinh_chi_bao(df):
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta.where(delta < 0, 0))
    df['RSI'] = 100 - (100 / (1 + gain.rolling(14).mean() / loss.rolling(14).mean()))
    df['MA20'] = df['close'].rolling(20).mean()
    df['MA50'] = df['close'].rolling(50).mean()
    df['EMA20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['close'].ewm(span=50, adjust=False).mean()
    e12 = df['close'].ewm(span=12, adjust=False).mean()
    e26 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = e12 - e26
    df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_hist'] = df['MACD'] - df['MACD_signal']
    df['TR'] = np.maximum(df['high']-df['low'], np.maximum(abs(df['high']-df['close'].shift()), abs(df['low']-df['close'].shift())))
    df['ATR'] = df['TR'].rolling(14).mean()
    pdm = df['high'].diff(); mdm = -df['low'].diff()
    pdm[pdm<0] = 0; mdm[mdm<0] = 0
    pdt = np.where(pdm>mdm, pdm, 0); mdt = np.where(mdm>pdm, mdm, 0)
    a14 = df['TR'].rolling(14).mean()
    pdi = 100*(pd.Series(pdt).rolling(14).mean()/a14)
    mdi = 100*(pd.Series(mdt).rolling(14).mean()/a14)
    df['ADX'] = (100*abs(pdi-mdi)/(pdi+mdi)).rolling(14).mean()
    df['Volume_Ratio'] = df['volume'] / df['volume'].rolling(20).mean()
    return df

# ============================================
# TIM S/R THUC TE
# ============================================
def tim_sr_thuc_te(df, i, lookback=100):
    supports = []
    resistances = []
    start = max(0, i - lookback)
    
    for j in range(start + 3, i - 3):
        if j >= len(df) - 3:
            break
        if (df['low'].iloc[j] < df['low'].iloc[j-1] and 
            df['low'].iloc[j] < df['low'].iloc[j-2] and
            df['low'].iloc[j] < df['low'].iloc[j+1] and 
            df['low'].iloc[j] < df['low'].iloc[j+2]):
            supports.append(df['low'].iloc[j])
    
    for j in range(start + 3, i - 3):
        if j >= len(df) - 3:
            break
        if (df['high'].iloc[j] > df['high'].iloc[j-1] and 
            df['high'].iloc[j] > df['high'].iloc[j-2] and
            df['high'].iloc[j] > df['high'].iloc[j+1] and 
            df['high'].iloc[j] > df['high'].iloc[j+2]):
            resistances.append(df['high'].iloc[j])
    
    def cluster(levels, threshold=0.005):
        if not levels:
            return []
        levels = sorted(levels)
        clusters = [[levels[0]]]
        for l in levels[1:]:
            if (l - clusters[-1][-1]) / clusters[-1][-1] < threshold:
                clusters[-1].append(l)
            else:
                clusters.append([l])
        return [round(sum(c)/len(c), 2) for c in clusters if len(c) >= 2]
    
    return sorted(cluster(supports), reverse=True), sorted(cluster(resistances))

# ============================================
# CHAM DIEM V16
# ============================================
def cham_diem_khung(df, i):
    rsi = df['RSI'].iloc[i]
    adx = df['ADX'].iloc[i]
    ma20 = df['MA20'].iloc[i]
    ma50 = df['MA50'].iloc[i]
    macd_hist = df['MACD_hist'].iloc[i]
    macd_hist_prev = df['MACD_hist'].iloc[i-1]
    volr = df['Volume_Ratio'].iloc[i]
    gia = df['close'].iloc[i]
    gia_prev = df['close'].iloc[i-1]
    pa_signals = detect_price_action(df)
    
    if pd.isna(rsi) or pd.isna(adx):
        return 0, 0, "UNKNOWN", []
    
    che_do = "SIDEWAY" if adx < ADX_SIDEWAY else "TREND"
    diemL = diemS = 0
    ly_do = []
    
    if rsi < 30:
        diemL += 3; ly_do.append(f"RSI={rsi:.0f} cực quá bán")
    elif rsi < 40:
        diemL += 2; ly_do.append(f"RSI={rsi:.0f} quá bán")
    elif rsi > 70:
        diemS += 3; ly_do.append(f"RSI={rsi:.0f} cực quá mua")
    elif rsi > 60:
        diemS += 2; ly_do.append(f"RSI={rsi:.0f} quá mua")
    
    if not pd.isna(ma20) and not pd.isna(ma50) and ma50 > 0:
        if abs(ma20 - ma50) / ma50 > 0.01:
            if ma20 > ma50:
                diemL += 2; ly_do.append("MA20>MA50")
            else:
                diemS += 2; ly_do.append("MA50>MA20")
    
    if not pd.isna(macd_hist) and not pd.isna(macd_hist_prev):
        if macd_hist > 0 and macd_hist_prev <= 0:
            diemL += 3; ly_do.append("MACD cắt lên")
        elif macd_hist > 0 and macd_hist > macd_hist_prev:
            diemL += 2
        if macd_hist < 0 and macd_hist_prev >= 0:
            diemS += 3; ly_do.append("MACD cắt xuống")
        elif macd_hist < 0 and macd_hist < macd_hist_prev:
            diemS += 2
    
    if not pd.isna(volr) and volr > 1.5:
        if gia > gia_prev:
            diemL += 2; ly_do.append(f"Vol x{volr:.1f}")
        else:
            diemS += 2; ly_do.append(f"Vol x{volr:.1f}")
    
    bullish_pa = [p for p in pa_signals if p[1] == "BULLISH"]
    bearish_pa = [p for p in pa_signals if p[1] == "BEARISH"]
    if bullish_pa:
        diemL += 2; ly_do.append(f"PA: {bullish_pa[0][0]}")
    if bearish_pa:
        diemS += 2; ly_do.append(f"PA: {bearish_pa[0][0]}")
    
    ly_do.append(f"ADX={adx:.0f} ({che_do})")
    return diemL, diemS, che_do, ly_do

# ============================================
# ENTRY/SL/TP - LINH HOAT CUOI TUAN
# ============================================
def tinh_entry_sltp_sr(df, signal, i):
    supports, resistances = tim_sr_thuc_te(df, i)
    gia = df['close'].iloc[i]
    atr = df['ATR'].iloc[i]
    if pd.isna(atr):
        atr = gia * 0.01
    
    weekend = is_weekend()
    
    if signal == "LONG":
        # Entry: S/R thuc te (ngay thuong) hoac MA20 (cuoi tuan)
        if weekend:
            ma20 = df['MA20'].iloc[i]
            ema20 = df['EMA20'].iloc[i]
            entry = round(min(ma20, ema20), 2) if not pd.isna(ma20) and not pd.isna(ema20) else round(ma20, 2)
            entry_name = "MA20 (weekend)"
        else:
            valid_s = [s for s in supports if s < gia * 0.998]
            if not valid_s:
                ma20 = df['MA20'].iloc[i]
                entry = round(min(gia * 0.995, ma20), 2) if not pd.isna(ma20) else round(gia * 0.99, 2)
                entry_name = "MA20 (fallback)"
            else:
                entry = max(valid_s)
                entry_name = f"S/R {entry:.2f}"
        
        sl = round(entry * 0.997, 2)
        
        valid_r = [r for r in resistances if r > entry * 1.005]
        tp1 = min(valid_r) if valid_r else round(entry + atr * 2.5, 2)
        tp2 = round(entry + atr * 4, 2)
        tp3 = round(entry + atr * 6, 2)
    
    else:  # SHORT
        if weekend:
            ma20 = df['MA20'].iloc[i]
            ema20 = df['EMA20'].iloc[i]
            entry = round(max(ma20, ema20), 2) if not pd.isna(ma20) and not pd.isna(ema20) else round(ma20, 2)
            entry_name = "MA20 (weekend)"
        else:
            valid_r = [r for r in resistances if r > gia * 1.002]
            if not valid_r:
                ma20 = df['MA20'].iloc[i]
                entry = round(max(gia * 1.005, ma20), 2) if not pd.isna(ma20) else round(gia * 1.01, 2)
                entry_name = "MA20 (fallback)"
            else:
                entry = min(valid_r)
                entry_name = f"S/R {entry:.2f}"
        
        sl = round(entry * 1.003, 2)
        
        valid_s = [s for s in supports if s < entry * 0.995]
        tp1 = max(valid_s) if valid_s else round(entry - atr * 2.5, 2)
        tp2 = round(entry - atr * 4, 2)
        tp3 = round(entry - atr * 6, 2)
    
    return entry, entry_name, sl, tp1, tp2, tp3

# ============================================
# MAIN
# ============================================
print("="*60)
mode = "WEEKEND" if is_weekend() else "WEEKDAY"
rr = get_rr_threshold()
print(f"🤖 BOT V16 S/R - MODE: {mode} | R:R ≥{rr}")
print("="*60)
gui(f"🤖 Bot V16 S/R da khoi dong!\n📅 Mode: <b>{mode}</b>\n📊 V16: Entry {'MA20' if is_weekend() else 'S/R thực tế'}\n📊 R:R ≥{rr} | ADX>{ADX_MIN} | Tracker PENDING→ACTIVE→CLOSED")

lan = 0
while True:
    try:
        lan += 1
        
        if lan % 12 == 0:
            clean_old_signals(tin_hieu_cu)
        
        for COIN in DANH_SACH_COIN:
            ket_qua = {}
            df_1h = None
            supports_1h = []
            resistances_1h = []
            pa_1h = []
            
            for khung in CAC_KHUNG:
                df = lay_nen(COIN, khung)
                if df is not None:
                    df = tinh_chi_bao(df)
                    i = len(df) - 1
                    
                    if khung == "1h":
                        df_1h = df
                        supports_1h, resistances_1h = tim_sr_thuc_te(df, i)
                        pa_1h = detect_price_action(df)
                    
                    diemL, diemS, che_do, ly_do = cham_diem_khung(df, i)
                    ket_qua[khung] = {"L": diemL, "S": diemS, "che_do": che_do}
            
            if not ket_qua:
                continue
            
            gia_hien_tai = df['close'].iloc[-1]
            so_khung_L = sum(1 for v in ket_qua.values() if v['L'] >= (NGUONG_DIEM_TREND if v['che_do'] == "TREND" else NGUONG_DIEM_SIDEWAY))
            so_khung_S = sum(1 for v in ket_qua.values() if v['S'] >= (NGUONG_DIEM_TREND if v['che_do'] == "TREND" else NGUONG_DIEM_SIDEWAY))
            
            signal = "NEUTRAL"
            if so_khung_L >= 2:
                signal = "LONG"
                do_manh = "CỰC MẠNH (3/3)" if so_khung_L == 3 else "MẠNH (2/3)"
            elif so_khung_S >= 2:
                signal = "SHORT"
                do_manh = "CỰC MẠNH (3/3)" if so_khung_S == 3 else "MẠNH (2/3)"
            
            if COIN not in tin_hieu_cu:
                tin_hieu_cu[COIN] = None
            
            if signal != "NEUTRAL" and signal != tin_hieu_cu[COIN] and df_1h is not None:
                i_1h = len(df_1h) - 1
                adx_1h = df_1h['ADX'].iloc[i_1h]
                if pd.isna(adx_1h) or adx_1h < ADX_MIN:
                    continue
                
                entry, entry_name, sl, tp1, tp2, tp3 = tinh_entry_sltp_sr(df_1h, signal, i_1h)
                
                risk = abs(entry - sl)
                reward = abs(tp1 - entry)
                rr_val = round(reward / risk, 1) if risk > 0 else 0
                
                RR_MIN = get_rr_threshold()
                if rr_val < RR_MIN:
                    continue
                
                ten_coin = COIN.replace("USDT", "")
                entry_pct = round(abs(entry - gia_hien_tai) / gia_hien_tai * 100, 2)
                entry_direction = "Hồi về hỗ trợ" if signal == "LONG" else "Hồi về kháng cự"
                order_type = "BUY LIMIT" if signal == "LONG" else "SELL LIMIT"
                stars = "⭐⭐⭐⭐⭐" if so_khung_L == 3 or so_khung_S == 3 else "⭐⭐⭐⭐"
                rsi_val = df_1h['RSI'].iloc[i_1h]
                adx_val = df_1h['ADX'].iloc[i_1h]
                volr_val = df_1h['Volume_Ratio'].iloc[i_1h]
                atr_val = df_1h['ATR'].iloc[i_1h]
                
                pa_text = ""
                if pa_1h:
                    pa_text = f"\n📊 <b>Price Action:</b> <b>{pa_1h[0][0]}</b>"
                
                msg = (
                    f"🔮 {ten_coin} 🏦 TÍN HIỆU V16 {signal} {'🟢' if signal=='LONG' else '🔴'} {stars}\n"
                    f"({do_manh})\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📌 <b>Coin:</b> {COIN}\n"
                    f"💰 <b>Giá hiện tại:</b> ${gia_hien_tai:,.2f}\n"
                    f"🎯 <b>ENTRY LÝ TƯỞNG:</b> <b>${entry:,.2f}</b>\n"
                    f"   ({entry_direction} {entry_name})\n"
                    f"   Cách hiện tại: {entry_pct}%{pa_text}\n"
                    f"📈 <b>RSI:</b> {rsi_val:.1f} | <b>ADX:</b> {adx_val:.1f} | <b>Vol:</b> {volr_val:.1f}x\n"
                    f"🛡️ <b>S/R 1h:</b> "
                )
                
                if resistances_1h:
                    msg += f"R1=${resistances_1h[0]:,.2f}"
                if len(resistances_1h) > 1:
                    msg += f", R2=${resistances_1h[1]:,.2f}"
                if supports_1h:
                    msg += f" | S1=${supports_1h[0]:,.2f}"
                if len(supports_1h) > 1:
                    msg += f", S2=${supports_1h[1]:,.2f}"
                
                msg += (
                    f"\n\n💡 <b>ĐẶT LỆNH CHỜ:</b>\n"
                    f"{'🟢' if signal=='LONG' else '🔴'} <b>{order_type}</b> tại <b>${entry:,.2f}</b>\n"
                    f"🎯 <b>TP1:</b> ${tp1:,.2f} | <b>TP2:</b> ${tp2:,.2f} | <b>TP3:</b> ${tp3:,.2f}\n"
                    f"🛑 <b>SL:</b> ${sl:,.2f}\n"
                    f"📐 <b>R:R = 1:{rr_val}</b>\n\n"
                    f"⏳ <b>CHỜ GIÁ CHẠM ${entry:,.2f} ĐỂ VÀO LỆNH!</b>\n{now_str()}"
                )
                
                gui(msg)
                tin_hieu_cu[COIN] = signal
                tracker_them(COIN, signal, entry, sl, tp1, tp2)
        
        tracker_check()
        tracker_report()
        time.sleep(CHU_KY)
    
    except KeyboardInterrupt:
        gui("🛑 Bot da dung")
        break
    except Exception as e:
        time.sleep(30)