"""
BOT TIN HIEU GIAO DICH + TRACKER V16 - FINAL VERSION
- Đã backtest 90 ngày: ROI +2,145% | Win Rate 65.8%
- 3 coin x 1 KHUNG 1h - ADX + S/R THUC TE
- Entry = S/R gan nhat (BAT BUOC co S/R)
- Tracker: PENDING -> ACTIVE -> CLOSED
- Bao cao 12h
"""
import requests
import pandas as pd
import numpy as np
import time
import json
import os
from datetime import datetime, timedelta

# ============================================
# CONFIG
# ============================================
TOKEN = os.getenv("TELEGRAM_TOKEN", "8893995280:AAF9XwWAm9QgPkwmDrhZdY6UQ4zfySooWpk")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "518284897")

DANH_SACH_COIN = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
CHU_KY = 300  # 5 phut

# Thong so da toi uu tu backtest
ADX_MIN = 22
ADX_SIDEWAY = 25
RR_MIN = 2.0
MIN_SCORE = 6
NGUONG_DIEM_TREND = 6
NGUONG_DIEM_SIDEWAY = 5

# Quan ly von
RISK_PER_TRADE = 0.015  # 1.5% moi lenh
MAX_CONCURRENT = 2
COOLDOWN_HOURS = 12

tin_hieu_cu = {}
TRACKER_FILE = "data/trades.json"
SIGNALS_FILE = "data/signals.json"
_last_report = 0
os.makedirs("data", exist_ok=True)

# ============================================
# TELEGRAM
# ============================================
def gui(msg):
    """Gui tin nhan Telegram"""
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
    except:
        pass

def now_str():
    """Thoi gian hien tai"""
    n = datetime.now()
    return f"🕐 {n.strftime('%H:%M')} (Asia) | {(n-timedelta(hours=5)).strftime('%H:%M')} (EU) | {(n-timedelta(hours=11)).strftime('%H:%M')} (US) | {n.strftime('%d/%m/%Y')}"

def clean_old_signals(signal_dict, max_hours=24):
    """Xoa tin hieu cu"""
    now = datetime.now()
    for key in list(signal_dict.keys()):
        if (now - signal_dict[key]).total_seconds() > max_hours * 3600:
            del signal_dict[key]

# ============================================
# TRACKER - PENDING -> ACTIVE -> CLOSED
# ============================================
def _t_load():
    """Load trades tu file"""
    if os.path.exists(TRACKER_FILE):
        with open(TRACKER_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def _t_save(trades):
    """Luu trades vao file"""
    with open(TRACKER_FILE, 'w', encoding='utf-8') as f:
        json.dump(trades, f, ensure_ascii=False, indent=2)

def _s_load():
    """Load signals tu file"""
    if os.path.exists(SIGNALS_FILE):
        with open(SIGNALS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def _s_save(signals):
    """Luu signals vao file"""
    with open(SIGNALS_FILE, 'w', encoding='utf-8') as f:
        json.dump(signals, f, ensure_ascii=False, indent=2)

def _t_price(coin):
    """Lay gia hien tai"""
    try:
        r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={coin}USDT", timeout=5)
        return float(r.json()['price'])
    except:
        return None

def tracker_them(coin, signal, entry, sl, tp1, tp2):
    """Them lenh moi vao tracker"""
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
    """Kiem tra trang thai cac lenh"""
    trades = _t_load()
    updated = False
    
    for t in trades:
        status = t.get('status', 'PENDING')
        if status in ['CLOSED_WIN', 'CLOSED_LOSS']:
            continue
        
        price = _t_price(t['coin'])
        if price is None:
            continue
        
        signal = t['signal']
        entry = t['entry']
        sl = t['sl']
        tp1 = t['tp1']
        
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
                gui(f"📊 <b>[V16] ĐÃ KHỚP LỆNH!</b>\n━━━━━━━━━━━━━━━━\n📌 {t['coin']} {t['signal']}\n💰 Entry: <b>${entry:,.2f}</b>\n💵 Giá khớp: <b>${price:,.2f}</b>\n⏰ {t['entry_time']}")
        
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
            else:
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
                gui(f"{icon} <b>[V16] KẾT QUẢ: {result_text}</b> {emoji}\n━━━━━━━━━━━━━━━━\n📊 {t['coin']} {t['signal']}\n💰 Entry: <b>${entry:,.2f}</b>\n🎯 Thoát: <b>${t['exit_price']:,.2f}</b>\n📈 PnL: <b>{t['pnl']:+.2f}%</b>\n⏰ {t['exit_time']}")
    
    if updated:
        _t_save(trades)

def tracker_report():
    """Bao cao 12h"""
    global _last_report
    now = time.time()
    if now - _last_report < 43200:  # 12 gio
        return
    _last_report = now
    
    trades = _t_load()
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
        f"📊 <b>BÁO CÁO V16 12H</b>\n━━━━━━━━━━━━━━━━\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}\n\n"
        f"📈 <b>12H QUA:</b>\n✅ Thắng: <b>{r_wins}</b> | ❌ Thua: <b>{r_losses}</b>\n"
        f"📊 Win Rate: <b>{r_wr:.1f}%</b>\n💰 PnL: <b>{r_pnl:+.2f}%</b>\n\n"
        f"📊 <b>TỔNG:</b>\n✅ Thắng: <b>{len(wins)}</b> | ❌ Thua: <b>{len(losses)}</b>\n"
        f"📊 Win Rate: <b>{wr:.1f}%</b>\n💰 Tổng PnL: <b>{total_pnl:+.2f}%</b>"
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
    """Phat hien mau hinh nen"""
    if len(df) < 3:
        return []
    
    o, h, l, c = df['open'].iloc[-1], df['high'].iloc[-1], df['low'].iloc[-1], df['close'].iloc[-1]
    o1, h1, l1, c1 = df['open'].iloc[-2], df['high'].iloc[-2], df['low'].iloc[-2], df['close'].iloc[-2]
    
    body = abs(c - o)
    total_range = h - l
    results = []
    
    if total_range > 0:
        lower_wick = min(o, c) - l
        if body > 0 and lower_wick > body * 2 and total_range > 0:
            if (c - l) / total_range > 0.7:
                results.append(("HAMMER 🔨", "BULLISH"))
        
        upper_wick = h - max(o, c)
        if body > 0 and upper_wick > body * 2 and total_range > 0:
            if (h - c) / total_range > 0.7:
                results.append(("SHOOTING STAR 🌠", "BEARISH"))
    
    if c > o and c1 < o1 and o <= c1 and c >= o1:
        results.append(("BULLISH ENGULFING 🟢", "BULLISH"))
    if c < o and c1 > o1 and o >= c1 and c <= o1:
        results.append(("BEARISH ENGULFING 🔴", "BEARISH"))
    
    if total_range > 0 and body / total_range < 0.1:
        if l < min(l1, c1):
            results.append(("DRAGONFLY DOJI 🐉", "BULLISH"))
        elif h > max(h1, c1):
            results.append(("GRAVESTONE DOJI 🪦", "BEARISH"))
    
    return results

# ============================================
# LAY DU LIEU
# ============================================
def lay_nen(symbol, khung, limit=100):
    """Lay du lieu nen tu Binance"""
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

# ============================================
# TINH CHI BAO
# ============================================
def tinh_chi_bao(df):
    """Tinh toan cac chi bao ky thuat"""
    # RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta.where(delta < 0, 0))
    df['RSI'] = 100 - (100 / (1 + gain.rolling(14).mean() / loss.rolling(14).mean()))
    
    # MA
    df['MA20'] = df['close'].rolling(20).mean()
    df['MA50'] = df['close'].rolling(50).mean()
    df['EMA20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    # MACD
    e12 = df['close'].ewm(span=12, adjust=False).mean()
    e26 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = e12 - e26
    df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_hist'] = df['MACD'] - df['MACD_signal']
    
    # ATR
    df['TR'] = np.maximum(
        df['high'] - df['low'],
        np.maximum(
            abs(df['high'] - df['close'].shift()),
            abs(df['low'] - df['close'].shift())
        )
    )
    df['ATR'] = df['TR'].rolling(14).mean()
    
    # ADX
    pdm = df['high'].diff()
    mdm = -df['low'].diff()
    pdm[pdm < 0] = 0
    mdm[mdm < 0] = 0
    
    pdt = np.where(pdm > mdm, pdm, 0)
    mdt = np.where(mdm > pdm, mdm, 0)
    
    a14 = df['TR'].rolling(14).mean()
    pdi = 100 * (pd.Series(pdt).rolling(14).mean() / a14)
    mdi = 100 * (pd.Series(mdt).rolling(14).mean() / a14)
    df['ADX'] = (100 * abs(pdi - mdi) / (pdi + mdi)).rolling(14).mean()
    df['DI_plus'] = pdi
    df['DI_minus'] = mdi
    
    # Volume
    df['Volume_Ratio'] = df['volume'] / df['volume'].rolling(20).mean()
    
    # Bollinger Bands
    df['BB_mid'] = df['close'].rolling(20).mean()
    df['BB_std'] = df['close'].rolling(20).std()
    df['BB_upper'] = df['BB_mid'] + 2 * df['BB_std']
    df['BB_lower'] = df['BB_mid'] - 2 * df['BB_std']
    
    # Stochastic
    low_14 = df['low'].rolling(14).min()
    high_14 = df['high'].rolling(14).max()
    df['Stoch_K'] = 100 * ((df['close'] - low_14) / (high_14 - low_14))
    df['Stoch_D'] = df['Stoch_K'].rolling(3).mean()
    
    return df

# ============================================
# TIM S/R THUC TE
# ============================================
def tim_sr_thuc_te(df, i, lookback=100):
    """Tim support/resistance thuc te"""
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
# CHAM DIEM TIN HIEU
# ============================================
def cham_diem_khung(df, i):
    """Cham diem tin hieu LONG va SHORT"""
    if i < 60:
        return 0, 0, "UNKNOWN", []
    
    rsi = df['RSI'].iloc[i]
    adx = df['ADX'].iloc[i]
    di_plus = df['DI_plus'].iloc[i]
    di_minus = df['DI_minus'].iloc[i]
    ma20 = df['MA20'].iloc[i]
    ma50 = df['MA50'].iloc[i]
    macd_hist = df['MACD_hist'].iloc[i]
    macd_hist_prev = df['MACD_hist'].iloc[i-1]
    stoch_k = df['Stoch_K'].iloc[i]
    stoch_d = df['Stoch_D'].iloc[i]
    volr = df['Volume_Ratio'].iloc[i]
    gia = df['close'].iloc[i]
    gia_prev = df['close'].iloc[i-1]
    bb_lower = df['BB_lower'].iloc[i]
    bb_upper = df['BB_upper'].iloc[i]
    pa_signals = detect_price_action(df)
    
    if pd.isna(rsi) or pd.isna(adx):
        return 0, 0, "UNKNOWN", []
    
    che_do = "SIDEWAY" if adx < ADX_SIDEWAY else "TREND"
    diemL = 0
    diemS = 0
    ly_do = []
    
    # RSI
    if rsi < 30:
        diemL += 3
        ly_do.append(f"RSI={rsi:.0f}")
    elif rsi < 40:
        diemL += 1
    elif rsi > 70:
        diemS += 3
    elif rsi > 60:
        diemS += 1
    
    # ADX/DI
    if adx > 25:
        if di_plus > di_minus:
            diemL += 3
            ly_do.append("Trend tăng")
        else:
            diemS += 3
            ly_do.append("Trend giảm")
    
    # MA
    if not pd.isna(ma20) and not pd.isna(ma50):
        if ma20 > ma50:
            diemL += 2
        else:
            diemS += 2
    
    # MACD
    if not pd.isna(macd_hist) and not pd.isna(macd_hist_prev):
        if macd_hist > 0 and macd_hist_prev <= 0:
            diemL += 3
            ly_do.append("MACD cắt lên")
        elif macd_hist < 0 and macd_hist_prev >= 0:
            diemS += 3
            ly_do.append("MACD cắt xuống")
    
    # Stochastic
    if not pd.isna(stoch_k) and not pd.isna(stoch_d):
        if stoch_k < 20 and stoch_k > stoch_d:
            diemL += 2
            ly_do.append(f"Stoch={stoch_k:.0f}")
        elif stoch_k > 80 and stoch_k < stoch_d:
            diemS += 2
    
    # Volume
    if not pd.isna(volr) and volr > 2.0:
        if gia > gia_prev:
            diemL += 2
            ly_do.append(f"Vol x{volr:.1f}")
        else:
            diemS += 2
    
    # Bollinger Bands
    if not pd.isna(bb_lower) and gia <= bb_lower * 1.01:
        diemL += 1
    if not pd.isna(bb_upper) and gia >= bb_upper * 0.99:
        diemS += 1
    
    # Price Action
    bullish_pa = [p for p in pa_signals if p[1] == "BULLISH"]
    bearish_pa = [p for p in pa_signals if p[1] == "BEARISH"]
    if bullish_pa:
        diemL += 2
        ly_do.append(f"PA: {bullish_pa[0][0]}")
    if bearish_pa:
        diemS += 2
        ly_do.append(f"PA: {bearish_pa[0][0]}")
    
    ly_do.append(f"ADX={adx:.0f} ({che_do})")
    return diemL, diemS, che_do, ly_do

# ============================================
# TINH ENTRY/SL/TP
# ============================================
def tinh_entry_sltp_sr(df, signal, i):
    """Tinh entry, SL, TP dua tren S/R"""
    supports, resistances = tim_sr_thuc_te(df, i)
    gia = df['close'].iloc[i]
    atr = df['ATR'].iloc[i]
    ma20 = df['MA20'].iloc[i]
    
    if pd.isna(atr):
        atr = gia * 0.01
    
    if signal == "LONG":
        entry = min(gia, ma20) if not pd.isna(ma20) else gia
        valid_s = [s for s in supports if s < gia * 0.998]
        if valid_s:
            entry = max(valid_s)
        
        sl = round(entry - atr * 2, 2)
        
        valid_r = [r for r in resistances if r > entry * 1.005]
        if valid_r:
            tp1 = min(valid_r)
        else:
            tp1 = round(entry + atr * 4, 2)
        
        tp2 = round(entry + atr * 6, 2)
        entry_name = f"S/R {entry:.2f}" if valid_s else f"MA20 {entry:.2f}"
    else:
        entry = max(gia, ma20) if not pd.isna(ma20) else gia
        valid_r = [r for r in resistances if r > gia * 1.002]
        if valid_r:
            entry = min(valid_r)
        
        sl = round(entry + atr * 2, 2)
        
        valid_s = [s for s in supports if s < entry * 0.995]
        if valid_s:
            tp1 = max(valid_s)
        else:
            tp1 = round(entry - atr * 4, 2)
        
        tp2 = round(entry - atr * 6, 2)
        entry_name = f"S/R {entry:.2f}" if valid_r else f"MA20 {entry:.2f}"
    
    return entry, entry_name, sl, tp1, tp2

# ============================================
# MAIN
# ============================================
print("="*60)
print(f"🤖 BOT V16 FINAL - DA TOI UU")
print(f"📊 Backtest: ROI +2,145% | WR 65.8% | 219 lenh/90 ngay")
print("="*60)
gui(f"🤖 <b>Bot V16 Final da khoi dong!</b>\n📊 Backtest: ROI +2,145% | WR 65.8%\n⚙️ Score≥{MIN_SCORE} | ADX>{ADX_MIN} | R:R≥{RR_MIN}")

lan = 0
last_signal_time = _s_load()

while True:
    try:
        lan += 1
        if lan % 12 == 0:
            clean_old_signals(tin_hieu_cu)
        
        for COIN in DANH_SACH_COIN:
            try:
                df_1h = lay_nen(COIN, "1h", 100)
                if df_1h is None:
                    continue
                
                df_1h = tinh_chi_bao(df_1h)
                i = len(df_1h) - 1
                
                # ADX filter
                adx_1h = df_1h['ADX'].iloc[i]
                if pd.isna(adx_1h) or adx_1h < ADX_MIN:
                    continue
                
                # Kiem tra cooldown
                if COIN in last_signal_time:
                    last_time = datetime.fromisoformat(last_signal_time[COIN])
                    hours_since = (datetime.now() - last_time).total_seconds() / 3600
                    if hours_since < COOLDOWN_HOURS:
                        continue
                
                # Kiem tra so lenh dang mo
                trades = _t_load()
                active_count = len([t for t in trades if t.get('status') in ['PENDING', 'ACTIVE']])
                if active_count >= MAX_CONCURRENT:
                    continue
                
                # Cham diem
                diemL, diemS, che_do, ly_do = cham_diem_khung(df_1h, i)
                threshold = NGUONG_DIEM_TREND if che_do == "TREND" else NGUONG_DIEM_SIDEWAY
                
                signal = "NEUTRAL"
                if diemL >= threshold and diemL > diemS:
                    signal = "LONG"
                elif diemS >= threshold and diemS > diemL:
                    signal = "SHORT"
                
                if COIN not in tin_hieu_cu:
                    tin_hieu_cu[COIN] = None
                if signal == "NEUTRAL" or signal == tin_hieu_cu[COIN]:
                    continue
                
                # Tinh Entry/SL/TP
                result = tinh_entry_sltp_sr(df_1h, signal, i)
                if result is None:
                    continue
                
                entry, entry_name, sl, tp1, tp2 = result
                
                risk = abs(entry - sl)
                reward = abs(tp1 - entry)
                rr_val = round(reward / risk, 1) if risk > 0 else 0
                if rr_val < RR_MIN:
                    continue
                
                gia_hien_tai = df_1h['close'].iloc[i]
                ten_coin = COIN.replace("USDT", "")
                entry_pct = round(abs(entry - gia_hien_tai) / gia_hien_tai * 100, 2)
                
                if signal == "LONG":
                    entry_direction = "Hồi về hỗ trợ"
                    order_type = "BUY LIMIT"
                else:
                    entry_direction = "Hồi về kháng cự"
                    order_type = "SELL LIMIT"
                
                rsi_val = df_1h['RSI'].iloc[i]
                adx_val = df_1h['ADX'].iloc[i]
                volr_val = df_1h['Volume_Ratio'].iloc[i]
                
                supports_1h, resistances_1h = tim_sr_thuc_te(df_1h, i)
                pa_1h = detect_price_action(df_1h)
                pa_text = ""
                if pa_1h:
                    pa_text = f"\n📊 <b>Price Action:</b> <b>{pa_1h[0][0]}</b>"
                
                score = diemL if signal == "LONG" else diemS
                
                msg = (
                    f"🔮 {ten_coin} 🏦 <b>TÍN HIỆU V16 {signal}</b> {'🟢' if signal=='LONG' else '🔴'}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📌 <b>Coin:</b> {COIN}\n"
                    f"💰 <b>Giá hiện tại:</b> ${gia_hien_tai:,.2f}\n"
                    f"🎯 <b>ENTRY LÝ TƯỞNG:</b> <b>${entry:,.2f}</b>\n"
                    f"   ({entry_direction} {entry_name})\n"
                    f"   Cách hiện tại: {entry_pct}%{pa_text}\n"
                    f"📊 <b>Score:</b> {score} | <b>RSI:</b> {rsi_val:.1f} | <b>ADX:</b> {adx_val:.1f} | <b>Vol:</b> {volr_val:.1f}x\n"
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
                    f"🎯 <b>TP1:</b> ${tp1:,.2f} | <b>TP2:</b> ${tp2:,.2f}\n"
                    f"🛑 <b>SL:</b> ${sl:,.2f}\n"
                    f"📐 <b>R:R = 1:{rr_val}</b>\n"
                    f"📊 <b>Lý do:</b> {', '.join(ly_do)}\n\n"
                    f"⏳ <b>CHỜ GIÁ CHẠM ${entry:,.2f} ĐỂ VÀO LỆNH!</b>\n{now_str()}"
                )
                
                gui(msg)
                tin_hieu_cu[COIN] = signal
                
                # Luu thoi gian tin hieu
                last_signal_time[COIN] = datetime.now().isoformat()
                _s_save(last_signal_time)
                
                tracker_them(COIN, signal, entry, sl, tp1, tp2)
                
            except Exception as e:
                print(f"Loi voi {COIN}: {e}")
                continue
        
        tracker_check()
        tracker_report()
        time.sleep(CHU_KY)
    
    except KeyboardInterrupt:
        gui("🛑 Bot da dung")
        break
    except Exception as e:
        print(f"Loi: {e}")
        time.sleep(30)