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
    """Tìm vùng giá có volume cao nhất"""
    recent = df.tail(20)
    zones = {}
    for i in range(len(recent)):
        level = round(recent['close'].iloc[i] / atr) * atr if atr > 0 else recent['close'].iloc[i]
        if level not in zones: zones[level] = 0
        zones[level] += recent['volume'].iloc[i]
    return max(zones, key=zones.get) if zones else df['close'].iloc[-1]

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
        bb_low = df['BB_low'].iloc[-1]
        bb_high = df['BB_high'].iloc[-1]
        bb_mid = df['BB_mid'].iloc[-1]
        atr = df['ATR'].iloc[-1]
        volr = df['Volume_Ratio'].iloc[-1]
        adx = df['ADX'].iloc[-1]
        ema9 = df['close'].ewm(span=9, adjust=False).mean().iloc[-1]
        ema21 = df['close'].ewm(span=21, adjust=False).mean().iloc[-1]
        
        if pd.isna(rsi) or pd.isna(atr): return None
        
        trend = "WEAK_BULLISH" if ema9 > ema21 else "WEAK_BEARISH"
        pa_signals = detect_price_action(df)
        vol_zone = get_volume_profile(df, atr)
        
        # === LONG ===
        if rsi < 40 and volr > 0.8:
            bullish_pa = [p for p in pa_signals if p[1] == "BULLISH"]
            if not bullish_pa: return None
            
            pa_name = bullish_pa[0][0]
            
            # Entry: giá đóng cửa nến đảo chiều
            entry = gia
            sl = round(df['low'].iloc[-1] - atr * 0.3, 2)
            tp1 = round(bb_mid, 2)
            tp2 = round(entry + atr * 2, 2)
            entry_pct = 0  # Entry tại giá hiện tại vì đã có xác nhận PA
            
            if rsi < 25 and volr > 1.2: score, level = 3, "MẠNH"
            elif rsi < 30 and volr > 1.0: score, level = 2, "VỪA"
            else: score, level = 1, "YẾU"
            
            return {
                'signal': 'LONG', 'entry': entry, 'entry_pct': entry_pct,
                'sl': sl, 'tp1': tp1, 'tp2': tp2,
                'rsi': rsi, 'adx': adx, 'volr': volr, 'atr': atr,
                'trend': trend, 'score': score, 'level': level,
                'pa_signal': pa_name, 'vol_zone': vol_zone
            }
        
        # === SHORT ===
        if rsi > 60 and volr > 0.8:
            bearish_pa = [p for p in pa_signals if p[1] == "BEARISH"]
            if not bearish_pa: return None
            
            pa_name = bearish_pa[0][0]
            
            entry = gia
            sl = round(df['high'].iloc[-1] + atr * 0.3, 2)
            tp1 = round(bb_mid, 2)
            tp2 = round(entry - atr * 2, 2)
            entry_pct = 0
            
            if rsi > 75 and volr > 1.2: score, level = 3, "MẠNH"
            elif rsi > 70 and volr > 1.0: score, level = 2, "VỪA"
            else: score, level = 1, "YẾU"
            
            return {
                'signal': 'SHORT', 'entry': entry, 'entry_pct': entry_pct,
                'sl': sl, 'tp1': tp1, 'tp2': tp2,
                'rsi': rsi, 'adx': adx, 'volr': volr, 'atr': atr,
                'trend': trend, 'score': score, 'level': level,
                'pa_signal': pa_name, 'vol_zone': vol_zone
            }
        
        return None
    except:
        return None

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
    return df

# ============================================
# TIM SUPPORT & RESISTANCE
# ============================================
def tim_support_resistance(df):
    supports, resistances = [], []
    for i in range(2, len(df)-2):
        if df['high'].iloc[i] > df['high'].iloc[i-1] and df['high'].iloc[i] > df['high'].iloc[i-2] and df['high'].iloc[i] > df['high'].iloc[i+1] and df['high'].iloc[i] > df['high'].iloc[i+2]:
            resistances.append(df['high'].iloc[i])
        if df['low'].iloc[i] < df['low'].iloc[i-1] and df['low'].iloc[i] < df['low'].iloc[i-2] and df['low'].iloc[i] < df['low'].iloc[i+1] and df['low'].iloc[i] < df['low'].iloc[i+2]:
            supports.append(df['low'].iloc[i])
    def gom(levels, t=0.01):
        if not levels: return []
        levels = sorted(set(levels)); nhom = []; cur = [levels[0]]
        for l in levels[1:]:
            if (l-cur[-1])/cur[-1] < t: cur.append(l)
            else: nhom.append(round(sum(cur)/len(cur),2)); cur = [l]
        nhom.append(round(sum(cur)/len(cur),2)); return nhom
    return sorted(gom(supports), reverse=True), sorted(gom(resistances))

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
# V16 - TIM ENTRY + SL/TP
# ============================================
def tinh_entry_sltp(df, signal_type, supports, resistances):
    gia=df['close'].iloc[-1]; atr=df['ATR'].iloc[-1]
    ma20=df['MA20'].iloc[-1]; ma50=df['MA50'].iloc[-1]
    ema20=df['EMA20'].iloc[-1]; ema50=df['EMA50'].iloc[-1]
    bb_low=df['BB_low'].iloc[-1]; bb_high=df['BB_high'].iloc[-1]
    if pd.isna(atr): atr=gia*0.01
    
    vol_zone = get_volume_profile(df, atr)
    
    if signal_type=="LONG":
        cac_muc=[]
        for s in supports[:3]:
            if s<gia: cac_muc.append((f"S1",s)); break
        if ma20<gia: cac_muc.append(("MA20",ma20))
        if ma50<gia: cac_muc.append(("MA50",ma50))
        if ema20<gia: cac_muc.append(("EMA20",ema20))
        if bb_low<gia: cac_muc.append(("BB Low",bb_low))
        if vol_zone<gia: cac_muc.append(("Vol Zone",vol_zone))
        if cac_muc: entry_name,entry=max(cac_muc,key=lambda x:x[1])
        else: entry_name,entry="Gia -1%",gia*0.99
        
        sl_atr=entry-atr*1.5; sl_support=None
        for s in supports:
            if s<entry*0.98: sl_support=s*0.995; break
        sl=max(sl_atr,sl_support) if sl_support else sl_atr; sl=round(sl,2)
        tp_atr=entry+atr*2; tp_resistance=None
        for r in resistances:
            if r>entry: tp_resistance=r*0.995; break
        tp1=min(tp_atr,tp_resistance) if tp_resistance else tp_atr; tp1=round(tp1,2)
        tp2=round(entry+atr*3,2); tp3=round(entry+atr*4,2)
    else:
        cac_muc=[]
        for r in resistances[:3]:
            if r>gia: cac_muc.append((f"R1",r)); break
        if ma20>gia: cac_muc.append(("MA20",ma20))
        if ma50>gia: cac_muc.append(("MA50",ma50))
        if ema20>gia: cac_muc.append(("EMA20",ema20))
        if bb_high>gia: cac_muc.append(("BB High",bb_high))
        if vol_zone>gia: cac_muc.append(("Vol Zone",vol_zone))
        if cac_muc: entry_name,entry=min(cac_muc,key=lambda x:x[1])
        else: entry_name,entry="Gia +1%",gia*1.01
        
        sl_atr=entry+atr*1.5; sl_resistance=None
        for r in resistances:
            if r>entry*1.02: sl_resistance=r*1.005; break
        sl=min(sl_atr,sl_resistance) if sl_resistance else sl_atr; sl=round(sl,2)
        tp_atr=entry-atr*2; tp_support=None
        for s in supports:
            if s<entry: tp_support=s*1.005; break
        tp1=max(tp_atr,tp_support) if tp_support else tp_atr; tp1=round(tp1,2)
        tp2=round(entry-atr*3,2); tp3=round(entry-atr*4,2)
    return entry, entry_name, sl, tp1, tp2, tp3

# ============================================
# MAIN
# ============================================
print("="*60)
print(f"🤖 BOT PRO - V16 + SCALP + PRICE ACTION")
print("="*60)
gui("🤖 Bot PRO da khoi dong!\nV16: 1h+4h+1d + Price Action\nScalp: 15m + Price Action + Volume Profile\n📊 Tracker + Bao cao 12h")

lan=0
while True:
    try:
        lan+=1
        now=datetime.now().strftime("%H:%M:%S")
        print(f"\n#{lan} | {now}")
        
        # ===== SCALP =====
        for COIN in DANH_SACH_COIN:
            sig = scalp_analysis(COIN)
            if sig:
                key = f"scalp_{COIN}_{sig['signal']}_{sig['score']}"
                if key not in scalp_cu or (datetime.now() - scalp_cu[key]).seconds > 900:
                    scalp_cu[key] = datetime.now()
                    
                    stars = "⭐⭐⭐" if sig['score'] == 3 else ("⭐⭐" if sig['score'] == 2 else "⭐")
                    action = "MUA" if sig['signal'] == "LONG" else "BÁN"
                    order_type = "BUY LIMIT" if sig['signal'] == "LONG" else "SELL LIMIT"
                    trend_text = "🟢 WEAK_BULLISH" if sig['trend'] == "WEAK_BULLISH" else "🔴 WEAK_BEARISH"
                    risk_val = abs(sig['entry'] - sig['sl']) / sig['entry'] * 100
                    reward_val = abs(sig['tp1'] - sig['entry']) / sig['entry'] * 100
                    rr = round(reward_val / risk_val, 1) if risk_val > 0 else 0
                    
                    msg = f"⚡ {COIN.replace('USDT','')} - TÍN HIỆU SCALP {'🟢' if sig['signal']=='LONG' else '🔴'} {stars}\n"
                    msg += f"📈 SCALP ({sig['level']})\n"
                    msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    msg += f"📌 Coin: {COIN}\n"
                    msg += f"💰 Giá hiện tại: ${sig['entry']:,.2f}\n"
                    msg += f"🎯 ĐIỂM ENTRY: ${sig['entry']:,.2f}\n"
                    msg += f"📊 Price Action: <b>{sig['pa_signal']}</b>\n"
                    msg += f"📊 Vol Zone: ${sig['vol_zone']:,.2f}\n"
                    msg += f"{'🟢' if sig['signal']=='LONG' else '🔴'} {action} Tín hiệu: {sig['signal']}\n"
                    msg += f"📈 Trend: {trend_text} | RSI: {sig['rsi']:.1f} | ADX: {sig['adx']:.1f}\n"
                    msg += f"📊 Vol: {sig['volr']:.2f}x | ATR: ${sig['atr']:,.2f}\n\n"
                    msg += f"💡 ĐẶT LỆNH CHỜ:\n"
                    msg += f"{'🟢' if sig['signal']=='LONG' else '🔴'} {order_type} tại ${sig['entry']:,.2f}\n"
                    msg += f"🎯 TP1: ${sig['tp1']:,.2f} | TP2: ${sig['tp2']:,.2f}\n"
                    msg += f"🛑 SL: ${sig['sl']:,.2f}\n"
                    msg += f"📐 R:R = 1:{rr} | Risk 2% = $200\n\n"
                    msg += f"⏳ CHỜ GIÁ CHẠM ${sig['entry']:,.2f} ĐỂ VÀO LỆNH!\n"
                    msg += now_str()
                    gui(msg)
                    tracker_them(COIN, sig['signal'], sig['entry'], sig['sl'], sig['tp1'], sig['tp2'], "Scalp")
                    print(f"   ⚡ Scalp {COIN}: {sig['signal']} {sig['level']} | PA: {sig['pa_signal']}")
        
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
            
            che_do_khung = [f"{k}:{v['che_do'][:1]}" for k,v in ket_qua.items()]
            sr_info = ""
            if supports_1h: sr_info += f" S:{supports_1h[0]:.0f}"
            if resistances_1h: sr_info += f" R:{resistances_1h[0]:.0f}"
            print(f"{COIN}: ${gia_hien_tai:,.0f} | L={so_khung_L}/3 S={so_khung_S}/3 | {' '.join(che_do_khung)}{sr_info}")
            
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
                    pa_text = f"\n📊 Price Action: <b>{pa_1h[0][0]}</b>"
                
                msg = f"🔮 {ten_coin} 🏦 1D TÍN HIỆU CHỜ {signal} {'🟢' if signal=='LONG' else '🔴'} {stars}\n"
                msg += f"({'Rất mạnh' if 'CUC' in do_manh else 'Mạnh'})\n"
                msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                msg += f"📌 Coin: {COIN}\n"
                msg += f"💰 Giá hiện tại: ${gia_hien_tai:,.2f}\n"
                msg += f"🎯 ĐIỂM ENTRY LÝ TƯỞNG: ${entry:,.2f}\n"
                msg += f"   ({entry_direction} {entry_name})\n"
                msg += f"   Cách hiện tại: {entry_pct}%{pa_text}\n"
                msg += f"{'🟢' if signal=='LONG' else '🔴'} {action} Tín hiệu: {signal} {'🟢' if signal=='LONG' else '🔴'}\n"
                msg += f"📈 Trend: {trend_text} | RSI: {rsi_val:.1f} | ADX: {adx_val:.1f}\n"
                msg += f"📊 Vol: {volr_val:.1f}x | ATR: ${atr_val:,.2f}\n"
                msg += f"🛡️ SR: "
                if resistances_1h: msg += f"R1=${resistances_1h[0]:,.2f}"
                if len(resistances_1h) > 1: msg += f", R2=${resistances_1h[1]:,.2f}"
                if supports_1h: msg += f" | S1=${supports_1h[0]:,.2f}"
                if len(supports_1h) > 1: msg += f", S2=${supports_1h[1]:,.2f}"
                msg += f"\n\n\n💡 ĐẶT LỆNH CHỜ:\n"
                msg += f"{'🟢' if signal=='LONG' else '🔴'} {order_type} tại ${entry:,.2f}\n"
                msg += f"🎯 TP1: ${tp1:,.2f} | TP2: ${tp2:,.2f} | TP3: ${tp3:,.2f}\n"
                msg += f"🛑 SL: ${sl:,.2f}\n"
                msg += f"📐 R:R = 1:{rr} | Risk 2% = $200\n\n"
                msg += f"⏳ CHỜ GIÁ CHẠM ${entry:,.2f} ĐỂ VÀO LỆNH!\n"
                msg += now_str()
                
                gui(msg)
                tin_hieu_cu[COIN]=signal
                tracker_them(COIN, signal, entry, sl, tp1, tp2, "V16")
                print(f"   ✅ V16 {ten_coin}: {signal} - {do_manh} | Entry: ${entry:.0f}")
        
        tracker_check()
        tracker_report()
        time.sleep(CHU_KY)
        
    except KeyboardInterrupt:
        print("\n👋 Dung"); gui("🛑 Bot da dung"); break
    except Exception as e:
        print(f"❌ {e}"); time.sleep(30)