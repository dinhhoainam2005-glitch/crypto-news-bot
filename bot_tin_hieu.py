"""
BOT TIN HIEU GIAO DICH + TRACKER + SCALP - PRO VERSION
- Price Action: Hammer, Engulfing, Shooting Star, Doji
- Volume Profile: Vung volume cao nhat
- V16: 3 coin x 3 khung - ADX + S/R + Entry ly tuong
- Scalp: 3 coin x 15m - RSI + BB + Price Action + Entry ly tuong
- Tracker tu dong theo doi + Bao cao 12h
- Format chuan: so lieu THAT 100%
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
NGUONG_DIEM_TREND = 6
NGUONG_DIEM_SIDEWAY = 5
ADX_SIDEWAY = 20
RR_TOI_THIEU_V16 = 1.5
RR_TOI_THIEU_SCALP = 1.2

tin_hieu_cu = {}
scalp_cu = {}
TRACKER_FILE = "data/trades.json"
SCALP_FILE = "data/scalp_trades.json"
_last_report = 0
os.makedirs("data", exist_ok=True)

# ============================================
# TELEGRAM
# ============================================
def gui(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                     data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except: pass

def now_str():
    n = datetime.now()
    return f"🕐 {n.strftime('%H:%M')} (Asia) | {(n-timedelta(hours=5)).strftime('%H:%M')} (EU) | {(n-timedelta(hours=11)).strftime('%H:%M')} (US) | {n.strftime('%d/%m/%Y')}"

# ============================================
# CLEAN OLD SIGNALS - Fix memory leak
# ============================================
def clean_old_signals(signal_dict, max_hours=24):
    """Xóa tín hiệu cũ hơn max_hours giờ"""
    now = datetime.now()
    for key in list(signal_dict.keys()):
        if (now - signal_dict[key]).total_seconds() > max_hours * 3600:
            del signal_dict[key]

# ============================================
# TRACKER
# ============================================
def _t_load(file=TRACKER_FILE):
    if os.path.exists(file):
        with open(file, 'r', encoding='utf-8') as f: return json.load(f)
    return []

def _t_save(trades, file=TRACKER_FILE):
    with open(file, 'w', encoding='utf-8') as f: json.dump(trades, f, ensure_ascii=False, indent=2)

def _t_price(coin):
    try:
        r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={coin}USDT", timeout=5)
        return float(r.json()['price'])
    except: return None

def tracker_them(coin, signal, entry, sl, tp1, tp2, strategy="V16"):
    file = TRACKER_FILE if strategy == "V16" else SCALP_FILE
    trades = _t_load(file)
    trades.append({
        'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'coin': coin.replace('USDT', ''), 'signal': signal,
        'entry': entry, 'sl': sl, 'tp1': tp1, 'tp2': tp2,
        'strategy': strategy, 'result': 'CHO',
        'exit_price': 0, 'exit_time': '', 'pnl': 0
    })
    _t_save(trades, file)

def tracker_check():
    for file, label in [(TRACKER_FILE, "V16"), (SCALP_FILE, "Scalp")]:
        trades = _t_load(file)
        updated = False
        for t in trades:
            if t.get('result') != 'CHO': continue
            price = _t_price(t['coin'])
            if price is None: continue
            hit = False
            if t['signal'] == 'LONG':
                if price >= t['tp1']:
                    t['result'] = 'DUNG'; t['exit_price'] = t['tp1']
                    t['pnl'] = round((t['tp1'] - t['entry']) / t['entry'] * 100, 2)
                    hit = True
                elif price <= t['sl']:
                    t['result'] = 'SAI'; t['exit_price'] = t['sl']
                    t['pnl'] = round((t['sl'] - t['entry']) / t['entry'] * 100, 2)
                    hit = True
            else:
                if price <= t['tp1']:
                    t['result'] = 'DUNG'; t['exit_price'] = t['tp1']
                    t['pnl'] = round((t['entry'] - t['tp1']) / t['entry'] * 100, 2)
                    hit = True
                elif price >= t['sl']:
                    t['result'] = 'SAI'; t['exit_price'] = t['sl']
                    t['pnl'] = round((t['entry'] - t['sl']) / t['entry'] * 100, 2)
                    hit = True
            if hit:
                t['exit_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                updated = True
                icon = "✅" if t['result'] == 'DUNG' else "❌"
                e = "🎉" if t['result'] == 'DUNG' else "😞"
                gui(f"{icon} <b>[{label}] KET QUA: {t['result']}</b> {e}\n━━━━━━━━━━━━━━━━\n📊 {t['coin']} {t['signal']}\n💰 Entry: <b>${t['entry']:,.2f}</b>\n🎯 Thoat: <b>${t['exit_price']:,.2f}</b>\n📈 PnL: <b>{t['pnl']:+.2f}%</b>\n⏰ {t['exit_time']}")
        if updated: _t_save(trades, file)

def tracker_report():
    global _last_report
    now = time.time()
    if now - _last_report < 43200: return
    _last_report = now
    
    for file, label in [(TRACKER_FILE, "V16"), (SCALP_FILE, "Scalp")]:
        trades = _t_load(file)
        done = [t for t in trades if t.get('result') != 'CHO']
        if not done: continue
        dung = sum(1 for t in done if t['result'] == 'DUNG')
        sai = sum(1 for t in done if t['result'] == 'SAI')
        total = len(done)
        wr = dung / total * 100 if total > 0 else 0
        total_pnl = sum(t.get('pnl', 0) for t in done)
        
        cutoff = (datetime.now() - timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")
        recent = [t for t in done if t.get('exit_time', '') >= cutoff]
        r_dung = sum(1 for t in recent if t['result'] == 'DUNG')
        r_sai = sum(1 for t in recent if t['result'] == 'SAI')
        r_total = len(recent)
        r_wr = r_dung / r_total * 100 if r_total > 0 else 0
        r_pnl = sum(t.get('pnl', 0) for t in recent)
        
        pending = [t for t in trades if t.get('result') == 'CHO']
        
        msg = f"📊 <b>BAO CAO [{label}] 12H</b>\n━━━━━━━━━━━━━━━━\n⏰ {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}\n\n📈 <b>12H QUA:</b>\n✅ Đúng: <b>{r_dung}</b> | ❌ Sai: <b>{r_sai}</b>\n📊 Win Rate: <b>{r_wr:.1f}%</b>\n💰 PnL: <b>{r_pnl:+.2f}%</b>\n\n📊 <b>TONG:</b>\n✅ Đúng: <b>{dung}</b> | ❌ Sai: <b>{sai}</b>\n📊 Win Rate: <b>{wr:.1f}%</b>\n💰 Tong PnL: <b>{total_pnl:+.2f}%</b>"
        if pending: msg += f"\n\n⏳ <b>DANG THEO DOI:</b> {len(pending)} tin hieu"
        gui(msg)

# ============================================
# PRICE ACTION DETECTION
# ============================================
def detect_price_action(df):
    """Phát hiện các mẫu nến đảo chiều"""
    o, h, l, c = df['open'].iloc[-1], df['high'].iloc[-1], df['low'].iloc[-1], df['close'].iloc[-1]
    o1, h1, l1, c1 = df['open'].iloc[-2], df['high'].iloc[-2], df['low'].iloc[-2], df['close'].iloc[-2]
    o2, h2, l2, c2 = df['open'].iloc[-3], df['high'].iloc[-3], df['low'].iloc[-3], df['close'].iloc[-3]
    
    body = abs(c - o)
    total_range = h - l
    
    results = []
    
    # Hammer: bóng dưới dài > 2x thân, đóng cửa gần đỉnh
    lower_wick = min(o, c) - l
    if body > 0 and lower_wick > body * 2 and total_range > 0:
        if (c - l) / total_range > 0.7:
            results.append(("HAMMER 🔨", "BULLISH"))
    
    # Bullish Engulfing
    if c > o and c1 < o1 and o <= c1 and c >= o1:
        results.append(("BULLISH ENGULFING 🟢", "BULLISH"))
    
    # Morning Star: đỏ → doji nhỏ → xanh
    if c2 < o2 and body > 0 and abs(c1-o1) < body*0.5 and c > o and c > (o2+c2)/2:
        results.append(("MORNING STAR ⭐", "BULLISH"))
    
    # Inverted Hammer
    upper_wick_bull = h - max(o, c)
    if c > o and upper_wick_bull > body * 2 and body > 0:
        results.append(("INVERTED HAMMER 🔨", "BULLISH"))
    
    # Shooting Star: bóng trên dài > 2x thân
    upper_wick = h - max(o, c)
    if body > 0 and upper_wick > body * 2 and total_range > 0:
        if (h - c) / total_range > 0.7:
            results.append(("SHOOTING STAR 🌠", "BEARISH"))
    
    # Bearish Engulfing
    if c < o and c1 > o1 and o >= c1 and c <= o1:
        results.append(("BEARISH ENGULFING 🔴", "BEARISH"))
    
    # Evening Star: xanh → doji nhỏ → đỏ
    if c2 > o2 and body > 0 and abs(c1-o1) < body*0.5 and c < o and c < (o2+c2)/2:
        results.append(("EVENING STAR ⭐", "BEARISH"))
    
    # Doji: thân nến rất nhỏ
    if total_range > 0 and body / total_range < 0.1:
        if l < min(l1, l2):
            results.append(("DRAGONFLY DOJI 🐉", "BULLISH"))
        elif h > max(h1, h2):
            results.append(("GRAVESTONE DOJI 🪦", "BEARISH"))
    
    return results

def get_volume_profile(df, atr):
    """Tìm vùng giá có volume cao nhất (POC)"""
    recent = df.tail(20)
    zones = {}
    for i in range(len(recent)):
        level = round(recent['close'].iloc[i] / atr) * atr if atr > 0 else recent['close'].iloc[i]
        if level not in zones: zones[level] = 0
        zones[level] += recent['volume'].iloc[i]
    return max(zones, key=zones.get) if zones else df['close'].iloc[-1]

# ============================================
# KIEM TRA XU HUONG 1H - Filter cho Scalp
# ============================================
def get_1h_trend(symbol):
    """Lay EMA50 khung 1h de loc xu huong"""
    try:
        df = lay_nen(symbol, "1h", 60)
        if df is None: return None, None
        ema50 = df['close'].ewm(span=50, adjust=False).mean().iloc[-1]
        gia_1h = df['close'].iloc[-1]
        if pd.isna(ema50): return None, None
        return gia_1h, ema50
    except:
        return None, None

# ============================================
# LAY DU LIEU NEN
# ============================================
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
        df['close'] = df['close'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['open'] = df['open'].astype(float)
        df['volume'] = df['volume'].astype(float)
        return df
    except:
        return None

# ============================================
# TINH CHI BAO
# ============================================
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
    df['TR'] = np.maximum(df['high']-df['low'], np.maximum(abs(df['high']-df['close'].shift()), abs(df['low']-df['close'].shift())))
    df['ATR'] = df['TR'].rolling(14).mean()
    pdm = df['high'].diff(); mdm = -df['low'].diff(); pdm[pdm<0]=0; mdm[mdm<0]=0
    pdt = np.where(pdm>mdm, pdm, 0); mdt = np.where(mdm>pdm, mdm, 0)
    a14 = df['TR'].rolling(14).mean()
    pdi = 100*(pd.Series(pdt).rolling(14).mean()/a14)
    mdi = 100*(pd.Series(mdt).rolling(14).mean()/a14)
    df['ADX'] = (100*abs(pdi-mdi)/(pdi+mdi)).rolling(14).mean()
    df['BB_mid'] = df['close'].rolling(20).mean()
    std = df['close'].rolling(20).std()
    df['BB_low'] = df['BB_mid'] - 2*std
    df['BB_high'] = df['BB_mid'] + 2*std
    df['Volume_Ratio'] = df['volume'] / df['volume'].rolling(20).mean()
    
    # Fibonacci Levels
    high_50 = df['high'].rolling(50).max()
    low_50 = df['low'].rolling(50).min()
    diff = high_50 - low_50
    df['Fib_0'] = high_50
    df['Fib_0.236'] = high_50 - 0.236 * diff
    df['Fib_0.382'] = high_50 - 0.382 * diff
    df['Fib_0.5'] = high_50 - 0.5 * diff
    df['Fib_0.618'] = high_50 - 0.618 * diff
    df['Fib_0.786'] = high_50 - 0.786 * diff
    df['Fib_1'] = low_50
    df['Fib_1.272'] = high_50 + 0.272 * diff
    df['Fib_1.618'] = high_50 + 0.618 * diff
    
    return df

# ============================================
# TIM SUPPORT & RESISTANCE - MULTI-TOUCH + CLUSTERING
# ============================================
def tim_support_resistance(df, min_touches=2):
    """
    Tim S/R thuc te voi xac nhan multi-touch + clustering.
    S luon < gia hien tai < R.
    """
    supports_raw, resistances_raw = [], []
    
    # B1: Tim swing highs/lows (fractal 3 nến)
    for i in range(3, len(df)-3):
        # Swing high: đỉnh cao hơn 3 nến trái và 3 nến phải
        if (df['high'].iloc[i] > df['high'].iloc[i-1] and 
            df['high'].iloc[i] > df['high'].iloc[i-2] and 
            df['high'].iloc[i] > df['high'].iloc[i-3] and
            df['high'].iloc[i] > df['high'].iloc[i+1] and 
            df['high'].iloc[i] > df['high'].iloc[i+2] and 
            df['high'].iloc[i] > df['high'].iloc[i+3]):
            resistances_raw.append(df['high'].iloc[i])
        
        # Swing low: đáy thấp hơn 3 nến trái và 3 nến phải
        if (df['low'].iloc[i] < df['low'].iloc[i-1] and 
            df['low'].iloc[i] < df['low'].iloc[i-2] and 
            df['low'].iloc[i] < df['low'].iloc[i-3] and
            df['low'].iloc[i] < df['low'].iloc[i+1] and 
            df['low'].iloc[i] < df['low'].iloc[i+2] and 
            df['low'].iloc[i] < df['low'].iloc[i+3]):
            supports_raw.append(df['low'].iloc[i])
    
    # B2: Gom cụm (clustering) các mức gần nhau trong phạm vi 0.5%
    def cluster_levels(levels, threshold=0.005):
        if not levels: return []
        levels = sorted(levels)
        clusters = []
        current_cluster = [levels[0]]
        
        for lvl in levels[1:]:
            if (lvl - current_cluster[-1]) / current_cluster[-1] < threshold:
                current_cluster.append(lvl)
            else:
                clusters.append(sum(current_cluster) / len(current_cluster))
                current_cluster = [lvl]
        clusters.append(sum(current_cluster) / len(current_cluster))
        return [round(c, 2) for c in clusters]
    
    supports = cluster_levels(supports_raw)
    resistances = cluster_levels(resistances_raw)
    
    gia = df['close'].iloc[-1]
    
    # B3: Lọc multi-touch: giữ cụm có ít nhất 2 swing chạm
    def filter_multi_touch(levels, raw_levels, threshold=0.005):
        result = []
        for lvl in levels:
            count = sum(1 for r in raw_levels if abs(r - lvl) / lvl < threshold)
            if count >= min_touches:
                result.append(lvl)
        return result
    
    supports = filter_multi_touch(supports, supports_raw)
    resistances = filter_multi_touch(resistances, resistances_raw)
    
    # B4: S < giá < R - ĐẢM BẢO ĐÚNG THỨ TỰ
    supports_below = [s for s in supports if s < gia * 0.995]
    resistances_above = [r for r in resistances if r > gia * 1.005]
    
    # Nếu không đủ S/R multi-touch, thêm MA20/MA50/EMA20/EMA50 làm S/R dự phòng
    if len(supports_below) < 1:
        ma20 = df['MA20'].iloc[-1]
        ma50 = df['MA50'].iloc[-1]
        ema20 = df['EMA20'].iloc[-1]
        ema50 = df['EMA50'].iloc[-1]
        fib_0382 = df['Fib_0.382'].iloc[-1]
        fib_05 = df['Fib_0.5'].iloc[-1]
        fib_0618 = df['Fib_0.618'].iloc[-1]
        
        backup = [x for x in [ma20, ma50, ema20, ema50, fib_0382, fib_05, fib_0618] 
                  if not pd.isna(x) and x < gia * 0.995]
        supports_below = sorted(backup, reverse=True)[:2]
    
    if len(resistances_above) < 1:
        ma20 = df['MA20'].iloc[-1]
        ma50 = df['MA50'].iloc[-1]
        ema20 = df['EMA20'].iloc[-1]
        ema50 = df['EMA50'].iloc[-1]
        fib_1 = df['Fib_1'].iloc[-1]
        fib_1_272 = df['Fib_1.272'].iloc[-1]
        fib_1_618 = df['Fib_1.618'].iloc[-1]
        
        backup = [x for x in [ma20, ma50, ema20, ema50, fib_1, fib_1_272, fib_1_618] 
                  if not pd.isna(x) and x > gia * 1.005]
        resistances_above = sorted(backup)[:2]
    
    return sorted(supports_below, reverse=True), sorted(resistances_above)

# ============================================
# V16 - PHAN TICH MOT KHUNG + PRICE ACTION
# ============================================
def phan_tich_khung(df, ten_khung):
    if df is None or len(df) < 50: return 0,0,[],0,"UNKNOWN",[]
    rsi=df['RSI'].iloc[-1]; ma20=df['MA20'].iloc[-1]; ma50=df['MA50'].iloc[-1]
    macd=df['MACD'].iloc[-1]; macds=df['MACD_signal'].iloc[-1]
    macdp=df['MACD'].iloc[-2]; macdsp=df['MACD_signal'].iloc[-2]
    volr=df['Volume_Ratio'].iloc[-1]; adx=df['ADX'].iloc[-1]; gia=df['close'].iloc[-1]
    if pd.isna(rsi) or pd.isna(adx): return 0,0,[],0,"UNKNOWN",[]
    che_do = "SIDEWAY" if adx < ADX_SIDEWAY else "TREND"
    pa_signals = detect_price_action(df)
    diemL=diemS=0; ly_do=[]
    
    # RSI + Price Action
    bullish_pa = [p for p in pa_signals if p[1] == "BULLISH"]
    bearish_pa = [p for p in pa_signals if p[1] == "BEARISH"]
    
    if rsi<30: diemL+=3; ly_do.append(f"RSI={rsi:.0f} qua ban")
    elif rsi<40: diemL+=1
    elif rsi>70: diemS+=3; ly_do.append(f"RSI={rsi:.0f} qua mua")
    elif rsi>60: diemS+=1
    
    if ma20>ma50: diemL+=2
    else: diemS+=2
    
    if macdp<macdsp and macd>macds: diemL+=3; ly_do.append("MACD cat len")
    elif macdp>macdsp and macd<macds: diemS+=3; ly_do.append("MACD cat xuong")
    elif macd>macds: diemL+=1
    else: diemS+=1
    
    if volr>1.5:
        if df['close'].iloc[-1]>df['close'].iloc[-2]: diemL+=2; ly_do.append(f"Vol x{volr:.1f}")
        else: diemS+=2; ly_do.append(f"Vol x{volr:.1f}")
    
    # Price Action bonus
    if bullish_pa: diemL+=2; ly_do.append(f"PA: {bullish_pa[0][0]}")
    if bearish_pa: diemS+=2; ly_do.append(f"PA: {bearish_pa[0][0]}")
    
    ly_do.append(f"ADX={adx:.0f} ({che_do})")
    return diemL, diemS, ly_do, gia, che_do, pa_signals

# ============================================
# V16 - TIM ENTRY + SL/TP - R:R DAM BAO >= 1.5
# ============================================
def tinh_entry_sltp(df, signal_type, supports, resistances):
    gia = df['close'].iloc[-1]
    atr = df['ATR'].iloc[-1]
    if pd.isna(atr): atr = gia * 0.01
    
    ma20 = df['MA20'].iloc[-1]
    ma50 = df['MA50'].iloc[-1]
    ema20 = df['EMA20'].iloc[-1]
    ema50 = df['EMA50'].iloc[-1]
    fib_0382 = df['Fib_0.382'].iloc[-1]
    fib_0618 = df['Fib_0.618'].iloc[-1]
    fib_1_272 = df['Fib_1.272'].iloc[-1]
    fib_1_618 = df['Fib_1.618'].iloc[-1]
    
    vol_zone = get_volume_profile(df, atr)
    
    if signal_type == "LONG":
        # ENTRY: Hồi về vùng hỗ trợ GẦN NHẤT (ưu tiên multi-touch S/R)
        entry_options = []
        
        # Ưu tiên 1: Support từ multi-touch
        for s in supports[:2]:
            if s < gia * 0.995:
                entry_options.append((f"S {s:.2f}", s))
        
        # Ưu tiên 2: MA/EMA
        for name, val in [("MA20", ma20), ("EMA20", ema20), ("MA50", ma50), ("EMA50", ema50)]:
            if not pd.isna(val) and val < gia * 0.995:
                entry_options.append((name, val))
        
        # Ưu tiên 3: Fibonacci retracement
        for name, val in [("Fib 0.382", fib_0382), ("Fib 0.618", fib_0618)]:
            if not pd.isna(val) and val < gia * 0.995:
                entry_options.append((name, val))
        
        # Ưu tiên 4: Volume POC
        if vol_zone < gia * 0.995:
            entry_options.append(("Vol POC", vol_zone))
        
        if entry_options:
            entry_name, entry = max(entry_options, key=lambda x: x[1])
        else:
            entry_name, entry = "MA20", round(ma20, 2) if not pd.isna(ma20) else round(gia * 0.98, 2)
        
        # SL: Dưới đáy gần nhất - 0.5 ATR (1D)
        sl_support = min(supports) if supports else entry * 0.97
        sl = round(min(sl_support, entry - atr * 1.5) - atr * 0.3, 2)
        
        # TP1: Vùng kháng cự THỰC SỰ gần nhất (xa nhất có thể)
        tp1_options = []
        for r in resistances[:3]:
            if r > entry * 1.005:
                tp1_options.append(r)
        
        if tp1_options:
            tp1 = round(min(tp1_options), 2)
        else:
            # Dùng Fibonacci Extension nếu không có R
            fib_targets = [x for x in [fib_1_272, fib_1_618] if not pd.isna(x) and x > entry * 1.005]
            tp1 = round(min(fib_targets), 2) if fib_targets else round(entry + atr * 3, 2)
        
        # TP2: Fibonacci Extension 1.272
        if not pd.isna(fib_1_272) and fib_1_272 > tp1:
            tp2 = round(fib_1_272, 2)
        else:
            tp2 = round(entry + atr * 4, 2)
        
        # TP3: Fibonacci Extension 1.618
        if not pd.isna(fib_1_618) and fib_1_618 > tp2:
            tp3 = round(fib_1_618, 2)
        else:
            tp3 = round(entry + atr * 5, 2)
    
    else:  # SHORT
        # ENTRY: Hồi về vùng kháng cự GẦN NHẤT
        entry_options = []
        
        for r in resistances[:2]:
            if r > gia * 1.005:
                entry_options.append((f"R {r:.2f}", r))
        
        for name, val in [("MA20", ma20), ("EMA20", ema20), ("MA50", ma50), ("EMA50", ema50)]:
            if not pd.isna(val) and val > gia * 1.005:
                entry_options.append((name, val))
        
        for name, val in [("Fib 0.382", fib_0382), ("Fib 0.618", fib_0618)]:
            if not pd.isna(val) and val > gia * 1.005:
                entry_options.append((name, val))
        
        if vol_zone > gia * 1.005:
            entry_options.append(("Vol POC", vol_zone))
        
        if entry_options:
            entry_name, entry = min(entry_options, key=lambda x: x[1])
        else:
            entry_name, entry = "MA20", round(ma20, 2) if not pd.isna(ma20) else round(gia * 1.02, 2)
        
        # SL: Trên đỉnh gần nhất + 0.5 ATR
        sl_resistance = max(resistances) if resistances else entry * 1.03
        sl = round(max(sl_resistance, entry + atr * 1.5) + atr * 0.3, 2)
        
        # TP1: Vùng hỗ trợ THỰC SỰ gần nhất
        tp1_options = []
        for s in supports[:3]:
            if s < entry * 0.995:
                tp1_options.append(s)
        
        if tp1_options:
            tp1 = round(max(tp1_options), 2)
        else:
            fib_targets = [x for x in [fib_0382, fib_0618] if not pd.isna(x) and x < entry * 0.995]
            tp1 = round(max(fib_targets), 2) if fib_targets else round(entry - atr * 3, 2)
        
        # TP2
        if not pd.isna(fib_0382) and fib_0382 < tp1:
            tp2 = round(fib_0382, 2)
        else:
            tp2 = round(entry - atr * 4, 2)
        
        # TP3
        if not pd.isna(fib_0618) and fib_0618 < tp2:
            tp3 = round(fib_0618, 2)
        else:
            tp3 = round(entry - atr * 5, 2)
    
    # KIỂM TRA R:R - Nếu không đạt, điều chỉnh SL
    risk = abs(entry - sl)
    reward = abs(tp1 - entry)
    rr = round(reward / risk, 1) if risk > 0 else 0
    
    if rr < RR_TOI_THIEU_V16:
        # Điều chỉnh SL để đạt R:R tối thiểu
        target_risk = reward / RR_TOI_THIEU_V16
        if signal_type == "LONG":
            sl = round(entry - target_risk, 2)
        else:
            sl = round(entry + target_risk, 2)
        rr = RR_TOI_THIEU_V16
    
    return entry, entry_name, sl, tp1, tp2, tp3

# ============================================
# TINH ENTRY THONG MINH CHO SCALP
# ============================================
def tinh_entry_thong_minh(df, signal_type):
    """
    Tinh entry cho Scalp dua tren:
    - Cau truc nen (đáy/đỉnh nến trước)
    - MA20/EMA20
    - Volume Profile POC
    - KHÔNG fallback về "Giá +0.3%"
    """
    gia = df['close'].iloc[-1]
    atr = df['ATR'].iloc[-1]
    if pd.isna(atr): atr = gia * 0.002
    
    ma20 = df['MA20'].iloc[-1]
    ema20 = df['EMA20'].iloc[-1]
    vol_poc = get_volume_profile(df, atr)
    
    o1, h1, l1, c1 = df['open'].iloc[-2], df['high'].iloc[-2], df['low'].iloc[-2], df['close'].iloc[-2]
    o2, h2, l2, c2 = df['open'].iloc[-3], df['high'].iloc[-3], df['low'].iloc[-3], df['close'].iloc[-3]
    
    if signal_type == "LONG":
        entry_options = []
        
        # 1. Đáy nến trước (vùng giá đã test)
        day_truoc = min(l1, l2)
        if day_truoc < gia * 0.995:
            entry_options.append(("Đáy nến trước", round(day_truoc, 2)))
        
        # 2. MA20 nếu dưới giá
        if not pd.isna(ma20) and ma20 < gia * 0.995:
            entry_options.append(("MA20", round(ma20, 2)))
        
        # 3. EMA20
        if not pd.isna(ema20) and ema20 < gia * 0.995:
            entry_options.append(("EMA20", round(ema20, 2)))
        
        # 4. Volume POC
        if vol_poc < gia * 0.995:
            entry_options.append(("Vol POC", round(vol_poc, 2)))
        
        # 5. 50% thân nến hiện tại
        mid_body = (gia + df['open'].iloc[-1]) / 2
        if mid_body < gia * 0.995:
            entry_options.append(("50% thân nến", round(mid_body, 2)))
        
        if entry_options:
            entry_name, entry = max(entry_options, key=lambda x: x[1])
        else:
            # Nếu không có mức nào dưới giá, dùng MA20 làm entry mặc định
            entry_name = "MA20"
            entry = round(ma20, 2) if not pd.isna(ma20) else round(gia * 0.997, 2)
    
    else:  # SHORT
        entry_options = []
        
        # 1. Đỉnh nến trước
        dinh_truoc = max(h1, h2)
        if dinh_truoc > gia * 1.005:
            entry_options.append(("Đỉnh nến trước", round(dinh_truoc, 2)))
        
        # 2. MA20 nếu trên giá
        if not pd.isna(ma20) and ma20 > gia * 1.005:
            entry_options.append(("MA20", round(ma20, 2)))
        
        # 3. EMA20
        if not pd.isna(ema20) and ema20 > gia * 1.005:
            entry_options.append(("EMA20", round(ema20, 2)))
        
        # 4. Volume POC
        if vol_poc > gia * 1.005:
            entry_options.append(("Vol POC", round(vol_poc, 2)))
        
        # 5. 50% thân nến hiện tại
        mid_body = (gia + df['open'].iloc[-1]) / 2
        if mid_body > gia * 1.005:
            entry_options.append(("50% thân nến", round(mid_body, 2)))
        
        if entry_options:
            entry_name, entry = min(entry_options, key=lambda x: x[1])
        else:
            entry_name = "MA20"
            entry = round(ma20, 2) if not pd.isna(ma20) else round(gia * 1.003, 2)
    
    return entry, entry_name

# ============================================
# SCALP 15M - PRICE ACTION + VOLUME PROFILE
# ============================================
def scalp_analysis(symbol):
    try:
        df = lay_nen(symbol, "15m", 100)
        if df is None: return None
        df = tinh_chi_bao(df)
        
        gia = df['close'].iloc[-1]
        rsi = df['RSI'].iloc[-1]
        bb_mid = df['BB_mid'].iloc[-1]
        bb_high = df['BB_high'].iloc[-1]
        bb_low = df['BB_low'].iloc[-1]
        atr = df['ATR'].iloc[-1]
        volr = df['Volume_Ratio'].iloc[-1]
        adx = df['ADX'].iloc[-1]
        ema9 = df['close'].ewm(span=9, adjust=False).mean().iloc[-1]
        ema21 = df['close'].ewm(span=21, adjust=False).mean().iloc[-1]
        
        if pd.isna(rsi) or pd.isna(atr): return None
        
        trend_15m = "WEAK_BULLISH" if ema9 > ema21 else "WEAK_BEARISH"
        pa_signals = detect_price_action(df)
        vol_zone = get_volume_profile(df, atr)
        supports, resistances = tim_support_resistance(df)
        
        # === FILTER XU HUONG 1H ===
        gia_1h, ema50_1h = get_1h_trend(symbol)
        if gia_1h is None:
            trend_1h = "KHONG_XAC_DINH"
            allow_long = True
            allow_short = True
        else:
            if gia_1h > ema50_1h:
                trend_1h = "UPTREND"
                allow_long = True
                allow_short = False
            else:
                trend_1h = "DOWNTREND"
                allow_long = False
                allow_short = True
        
        # === FILTER XU HUONG 15M ===
        if trend_15m == "WEAK_BEARISH":
            allow_long = False
        if trend_15m == "WEAK_BULLISH":
            allow_short = False
        
        def check_rr(entry, sl, tp):
            risk = abs(entry - sl)
            reward = abs(tp - entry)
            return (round(reward / risk, 1) if risk > 0 else 0) >= RR_TOI_THIEU_SCALP
        
        # === LONG ===
        long_signal = None
        if allow_long and volr > 0.8:
            if rsi < 40:
                bullish_pa = [p for p in pa_signals if p[1] == "BULLISH"]
                if bullish_pa:
                    pa_name = bullish_pa[0][0]
                    entry, entry_name = tinh_entry_thong_minh(df, "LONG")
                    
                    # SL: Dưới đáy nến tín hiệu - 0.3 ATR
                    sl = round(df['low'].iloc[-1] - atr * 0.3, 2)
                    
                    # TP1: Vùng kháng cự gần nhất hoặc BB_mid (cái nào XA hơn)
                    r_near = min(resistances) if resistances else entry + atr * 2
                    tp1 = round(max(r_near, bb_mid, entry + atr * 1.5), 2)
                    
                    # TP2: ATR * 2.5 từ entry
                    tp2 = round(entry + atr * 2.5, 2)
                    
                    # Kiểm tra R:R
                    if not check_rr(entry, sl, tp1):
                        sl = round(entry - abs(tp1 - entry) / RR_TOI_THIEU_SCALP, 2)
                    
                    entry_pct = round(abs(entry - gia) / gia * 100, 2)
                    
                    if rsi < 25 and volr > 1.2: score, level = 3, "MẠNH"
                    elif rsi < 30 and volr > 1.0: score, level = 2, "VỪA"
                    else: score, level = 1, "YẾU"
                    
                    long_signal = {
                        'signal': 'LONG', 'entry': entry, 'entry_pct': entry_pct,
                        'entry_name': entry_name,
                        'sl': sl, 'tp1': tp1, 'tp2': tp2,
                        'rsi': rsi, 'adx': adx, 'volr': volr, 'atr': atr,
                        'trend': trend_15m, 'score': score, 'level': level,
                        'pa_signal': pa_name, 'vol_zone': vol_zone,
                        'filter_type': 'RSI', 'trend_1h': trend_1h
                    }
            
            if long_signal is None and volr > 1.5:
                strong_bullish = [p for p in pa_signals if p[1] == "BULLISH" and ("HAMMER" in p[0] or "ENGULFING" in p[0] or "MORNING" in p[0])]
                if strong_bullish and 35 <= rsi <= 65:
                    pa_name = strong_bullish[0][0]
                    entry, entry_name = tinh_entry_thong_minh(df, "LONG")
                    
                    sl = round(df['low'].iloc[-1] - atr * 0.3, 2)
                    r_near = min(resistances) if resistances else entry + atr * 2
                    tp1 = round(max(r_near, bb_mid, entry + atr * 1.5), 2)
                    tp2 = round(entry + atr * 2.5, 2)
                    
                    if not check_rr(entry, sl, tp1):
                        sl = round(entry - abs(tp1 - entry) / RR_TOI_THIEU_SCALP, 2)
                    
                    entry_pct = round(abs(entry - gia) / gia * 100, 2)
                    
                    score, level = 2, "PA MẠNH"
                    long_signal = {
                        'signal': 'LONG', 'entry': entry, 'entry_pct': entry_pct,
                        'entry_name': entry_name,
                        'sl': sl, 'tp1': tp1, 'tp2': tp2,
                        'rsi': rsi, 'adx': adx, 'volr': volr, 'atr': atr,
                        'trend': trend_15m, 'score': score, 'level': level,
                        'pa_signal': pa_name, 'vol_zone': vol_zone,
                        'filter_type': 'PA_STRONG', 'trend_1h': trend_1h
                    }
        
        if long_signal: return long_signal
        
        # === SHORT ===
        short_signal = None
        if allow_short and volr > 0.8:
            if rsi > 60:
                bearish_pa = [p for p in pa_signals if p[1] == "BEARISH"]
                if bearish_pa:
                    pa_name = bearish_pa[0][0]
                    entry, entry_name = tinh_entry_thong_minh(df, "SHORT")
                    
                    sl = round(df['high'].iloc[-1] + atr * 0.3, 2)
                    s_near = max(supports) if supports else entry - atr * 2
                    tp1 = round(min(s_near, bb_mid, entry - atr * 1.5), 2)
                    tp2 = round(entry - atr * 2.5, 2)
                    
                    if not check_rr(entry, sl, tp1):
                        sl = round(entry + abs(tp1 - entry) / RR_TOI_THIEU_SCALP, 2)
                    
                    entry_pct = round(abs(entry - gia) / gia * 100, 2)
                    
                    if rsi > 75 and volr > 1.2: score, level = 3, "MẠNH"
                    elif rsi > 70 and volr > 1.0: score, level = 2, "VỪA"
                    else: score, level = 1, "YẾU"
                    
                    short_signal = {
                        'signal': 'SHORT', 'entry': entry, 'entry_pct': entry_pct,
                        'entry_name': entry_name,
                        'sl': sl, 'tp1': tp1, 'tp2': tp2,
                        'rsi': rsi, 'adx': adx, 'volr': volr, 'atr': atr,
                        'trend': trend_15m, 'score': score, 'level': level,
                        'pa_signal': pa_name, 'vol_zone': vol_zone,
                        'filter_type': 'RSI', 'trend_1h': trend_1h
                    }
            
            if short_signal is None and volr > 1.5:
                strong_bearish = [p for p in pa_signals if p[1] == "BEARISH" and ("SHOOTING" in p[0] or "ENGULFING" in p[0] or "EVENING" in p[0] or "GRAVESTONE" in p[0])]
                if strong_bearish and 35 <= rsi <= 65:
                    pa_name = strong_bearish[0][0]
                    entry, entry_name = tinh_entry_thong_minh(df, "SHORT")
                    
                    sl = round(df['high'].iloc[-1] + atr * 0.3, 2)
                    s_near = max(supports) if supports else entry - atr * 2
                    tp1 = round(min(s_near, bb_mid, entry - atr * 1.5), 2)
                    tp2 = round(entry - atr * 2.5, 2)
                    
                    if not check_rr(entry, sl, tp1):
                        sl = round(entry + abs(tp1 - entry) / RR_TOI_THIEU_SCALP, 2)
                    
                    entry_pct = round(abs(entry - gia) / gia * 100, 2)
                    
                    score, level = 2, "PA MẠNH"
                    short_signal = {
                        'signal': 'SHORT', 'entry': entry, 'entry_pct': entry_pct,
                        'entry_name': entry_name,
                        'sl': sl, 'tp1': tp1, 'tp2': tp2,
                        'rsi': rsi, 'adx': adx, 'volr': volr, 'atr': atr,
                        'trend': trend_15m, 'score': score, 'level': level,
                        'pa_signal': pa_name, 'vol_zone': vol_zone,
                        'filter_type': 'PA_STRONG', 'trend_1h': trend_1h
                    }
        
        if short_signal: return short_signal
        
        return None
    except:
        return None

# ============================================
# MAIN
# ============================================
print("="*60)
print(f"🤖 BOT PRO - V16 + SCALP + PRICE ACTION")
print("="*60)
gui("🤖 Bot PRO da khoi dong!\nV16: 1h+4h+1d + S/R Multi-Touch + Fib\nScalp: 15m + Entry thong minh + R:R filter\n📊 Tracker + Bao cao 12h")

lan=0
while True:
    try:
        lan+=1
        now=datetime.now().strftime("%H:%M:%S")
        
        if lan % 12 == 0:
            clean_old_signals(tin_hieu_cu)
            clean_old_signals(scalp_cu)
        
        # ===== SCALP =====
        for COIN in DANH_SACH_COIN:
            sig = scalp_analysis(COIN)
            if sig:
                key = f"scalp_{COIN}_{sig['signal']}_{sig['score']}"
                if key not in scalp_cu or (datetime.now() - scalp_cu[key]).total_seconds() > 900:
                    scalp_cu[key] = datetime.now()
                    
                    stars = "⭐⭐⭐" if sig['score'] == 3 else ("⭐⭐" if sig['score'] == 2 else "⭐")
                    action = "MUA" if sig['signal'] == "LONG" else "BÁN"
                    order_type = "BUY LIMIT" if sig['signal'] == "LONG" else "SELL LIMIT"
                    trend_15m_text = "🟢 WEAK_BULLISH" if sig['trend'] == "WEAK_BULLISH" else "🔴 WEAK_BEARISH"
                    trend_1h_text = "🟢 UPTREND" if sig.get('trend_1h') == "UPTREND" else ("🔴 DOWNTREND" if sig.get('trend_1h') == "DOWNTREND" else "⚪ KHONG XAC DINH")
                    risk_val = abs(sig['entry'] - sig['sl']) / sig['entry'] * 100
                    reward_val = abs(sig['tp1'] - sig['entry']) / sig['entry'] * 100
                    rr = round(reward_val / risk_val, 1) if risk_val > 0 else 0
                    
                    filter_info = ""
                    if sig.get('filter_type') == 'PA_STRONG':
                        filter_info = f"\n🔰 <b>LOAI:</b> PA MẠNH + VOL CAO (RSI={sig['rsi']:.0f})"
                    
                    msg = f"⚡ {COIN.replace('USDT','')} - TÍN HIỆU SCALP {'🟢' if sig['signal']=='LONG' else '🔴'} {stars}\n"
                    msg += f"📈 SCALP ({sig['level']})\n"
                    msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    msg += f"📌 <b>Coin:</b> {COIN}\n"
                    msg += f"💰 <b>Giá hiện tại:</b> ${sig['entry']:,.2f}\n"
                    msg += f"🎯 <b>ENTRY:</b> <b>${sig['entry']:,.2f}</b> ({sig['entry_name']})\n"
                    msg += f"   Cách giá hiện tại: <b>{sig['entry_pct']}%</b>\n"
                    msg += f"📊 <b>Price Action:</b> <b>{sig['pa_signal']}</b>\n"
                    msg += f"📊 <b>Vol Zone:</b> ${sig['vol_zone']:,.2f}{filter_info}\n"
                    msg += f"{'🟢' if sig['signal']=='LONG' else '🔴'} {action} <b>Tín hiệu:</b> {sig['signal']}\n"
                    msg += f"📈 <b>Trend 15m:</b> {trend_15m_text}\n"
                    msg += f"📈 <b>Trend 1h:</b> {trend_1h_text} | <b>RSI:</b> {sig['rsi']:.1f} | <b>ADX:</b> {sig['adx']:.1f}\n"
                    msg += f"📊 <b>Vol:</b> {sig['volr']:.2f}x | <b>ATR:</b> ${sig['atr']:,.2f}\n\n"
                    msg += f"💡 <b>ĐẶT LỆNH CHỜ:</b>\n"
                    msg += f"{'🟢' if sig['signal']=='LONG' else '🔴'} <b>{order_type}</b> tại <b>${sig['entry']:,.2f}</b>\n"
                    msg += f"🎯 <b>TP1:</b> ${sig['tp1']:,.2f} | <b>TP2:</b> ${sig['tp2']:,.2f}\n"
                    msg += f"🛑 <b>SL:</b> ${sig['sl']:,.2f}\n"
                    msg += f"📐 <b>R:R = 1:{rr}</b> | Risk 2% = $200\n\n"
                    msg += f"⏳ <b>CHỜ GIÁ CHẠM ${sig['entry']:,.2f} ĐỂ VÀO LỆNH!</b>\n"
                    msg += now_str()
                    gui(msg)
                    tracker_them(COIN, sig['signal'], sig['entry'], sig['sl'], sig['tp1'], sig['tp2'], "Scalp")
        
        # ===== V16 =====
        for COIN in DANH_SACH_COIN:
            ket_qua={}; df_1h=None; supports_1h=[]; resistances_1h=[]; pa_1h=[]
            for khung in CAC_KHUNG:
                df=lay_nen(COIN,khung)
                if df is not None:
                    df=tinh_chi_bao(df)
                    if khung=="1h": 
                        df_1h=df
                        supports_1h,resistances_1h=tim_support_resistance(df)
                    diemL,diemS,ly_do,gia,che_do,pa=phan_tich_khung(df,khung)
                    if khung=="1h": pa_1h=pa
                    ket_qua[khung]={"L":diemL,"S":diemS,"che_do":che_do}
            if not ket_qua: continue
            
            gia_hien_tai=df['close'].iloc[-1]
            so_khung_L=sum(1 for v in ket_qua.values() if v['L']>=(NGUONG_DIEM_TREND if v['che_do']=="TREND" else NGUONG_DIEM_SIDEWAY))
            so_khung_S=sum(1 for v in ket_qua.values() if v['S']>=(NGUONG_DIEM_TREND if v['che_do']=="TREND" else NGUONG_DIEM_SIDEWAY))
            
            signal="NEUTRAL"
            if so_khung_L>=2: signal="LONG"; do_manh="CUC MANH (3/3)" if so_khung_L==3 else "MANH (2/3)"
            elif so_khung_S>=2: signal="SHORT"; do_manh="CUC MANH (3/3)" if so_khung_S==3 else "MANH (2/3)"
            
            if COIN not in tin_hieu_cu: tin_hieu_cu[COIN]=None
            
            if signal!="NEUTRAL" and signal!=tin_hieu_cu[COIN] and df_1h is not None:
                entry,entry_name,sl,tp1,tp2,tp3=tinh_entry_sltp(df_1h,signal,supports_1h,resistances_1h)
                risk=abs(entry-sl); reward=abs(tp1-entry); rr=round(reward/risk,1) if risk>0 else 0
                ten_coin=COIN.replace("USDT","")
                entry_pct = round(abs(entry - gia_hien_tai) / gia_hien_tai * 100, 2)
                entry_direction = "Hồi về hỗ trợ" if signal == "LONG" else "Hồi về kháng cự"
                action = "MUA" if signal == "LONG" else "BÁN"
                order_type = "BUY LIMIT" if signal == "LONG" else "SELL LIMIT"
                trend_text = "🟢 UPTREND" if signal == "LONG" else "🔴 DOWNTREND"
                stars = "⭐⭐⭐⭐⭐" if so_khung_L==3 or so_khung_S==3 else "⭐⭐⭐⭐"
                rsi_val = df_1h['RSI'].iloc[-1]
                adx_val = df_1h['ADX'].iloc[-1]
                volr_val = df_1h['Volume_Ratio'].iloc[-1]
                atr_val = df_1h['ATR'].iloc[-1]
                
                pa_text = ""
                if pa_1h:
                    pa_text = f"\n📊 <b>Price Action:</b> <b>{pa_1h[0][0]}</b>"
                
                msg = f"🔮 {ten_coin} 🏦 1D TÍN HIỆU CHỜ {signal} {'🟢' if signal=='LONG' else '🔴'} {stars}\n"
                msg += f"({'Rất mạnh' if 'CUC' in do_manh else 'Mạnh'})\n"
                msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                msg += f"📌 <b>Coin:</b> {COIN}\n"
                msg += f"💰 <b>Giá hiện tại:</b> ${gia_hien_tai:,.2f}\n"
                msg += f"🎯 <b>ENTRY LÝ TƯỞNG:</b> <b>${entry:,.2f}</b>\n"
                msg += f"   ({entry_direction} {entry_name})\n"
                msg += f"   Cách hiện tại: {entry_pct}%{pa_text}\n"
                msg += f"{'🟢' if signal=='LONG' else '🔴'} {action} <b>Tín hiệu:</b> {signal} {'🟢' if signal=='LONG' else '🔴'}\n"
                msg += f"📈 <b>Trend:</b> {trend_text} | <b>RSI:</b> {rsi_val:.1f} | <b>ADX:</b> {adx_val:.1f}\n"
                msg += f"📊 <b>Vol:</b> {volr_val:.1f}x | <b>ATR:</b> ${atr_val:,.2f}\n"
                msg += f"🛡️ <b>SR:</b> "
                if resistances_1h: msg += f"R1=${resistances_1h[0]:,.2f}"
                if len(resistances_1h) > 1: msg += f", R2=${resistances_1h[1]:,.2f}"
                if supports_1h: msg += f" | S1=${supports_1h[0]:,.2f}"
                if len(supports_1h) > 1: msg += f", S2=${supports_1h[1]:,.2f}"
                msg += f"\n\n\n💡 <b>ĐẶT LỆNH CHỜ:</b>\n"
                msg += f"{'🟢' if signal=='LONG' else '🔴'} <b>{order_type}</b> tại <b>${entry:,.2f}</b>\n"
                msg += f"🎯 <b>TP1:</b> ${tp1:,.2f} | <b>TP2:</b> ${tp2:,.2f} | <b>TP3:</b> ${tp3:,.2f}\n"
                msg += f"🛑 <b>SL:</b> ${sl:,.2f}\n"
                msg += f"📐 <b>R:R = 1:{rr}</b> | Risk 2% = $200\n\n"
                msg += f"⏳ <b>CHỜ GIÁ CHẠM ${entry:,.2f} ĐỂ VÀO LỆNH!</b>\n"
                msg += now_str()
                
                gui(msg)
                tin_hieu_cu[COIN]=signal
                tracker_them(COIN, signal, entry, sl, tp1, tp2, "V16")
        
        tracker_check()
        tracker_report()
        time.sleep(CHU_KY)
        
    except KeyboardInterrupt:
        gui("🛑 Bot da dung")
        break
    except Exception as e:
        time.sleep(30)