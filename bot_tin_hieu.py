"""
BOT TIN HIEU GIAO DICH + TRACKER + SCALP - FULL
- V16: 3 coin x 3 khung (1h, 4h, 1d) - ADX + S/R + Entry ly tuong
- Scalp: 3 coin x 15m - RSI + BB + S/R + Entry ly tuong - 3 muc do
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
SCALP_MAX_DAILY = 15
SCALP_COOLDOWN = 1800

tin_hieu_cu = {}
scalp_cu = {}
scalp_daily_count = 0
scalp_daily_date = datetime.now().date()
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

def trong_gio_trade():
    hour = datetime.now().hour
    return 6 <= hour < 22

def reset_scalp_daily():
    global scalp_daily_count, scalp_daily_date
    today = datetime.now().date()
    if today > scalp_daily_date:
        scalp_daily_count = 0
        scalp_daily_date = today

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
# VOLUME PROFILE
# ============================================
def get_volume_profile(df, atr):
    recent = df.tail(20)
    zones = {}
    for i in range(len(recent)):
        level = round(recent['close'].iloc[i] / atr) * atr if atr > 0 else recent['close'].iloc[i]
        if level not in zones: zones[level] = 0
        zones[level] += recent['volume'].iloc[i]
    return max(zones, key=zones.get) if zones else df['close'].iloc[-1]

# ============================================
# SCALP 15M - PRICE ACTION + RSI HOI + VOL XAC NHAN + R:R >= 1:1.5
# ============================================
def scalp_analysis(symbol):
    global scalp_daily_count
    reset_scalp_daily()
    
    if not trong_gio_trade(): return None
    if scalp_daily_count >= SCALP_MAX_DAILY: return None
    
    try:
        df = lay_nen(symbol, "15m", 100)
        if df is None: return None
        df = tinh_chi_bao(df)
        supports, resistances = tim_support_resistance(df)
        
        gia = df['close'].iloc[-1]
        rsi_now = df['RSI'].iloc[-1]
        rsi_prev = df['RSI'].iloc[-2]
        rsi_prev2 = df['RSI'].iloc[-3]
        volr = df['Volume_Ratio'].iloc[-1]
        atr = df['ATR'].iloc[-1]
        adx = df['ADX'].iloc[-1]
        ema9 = df['close'].ewm(span=9, adjust=False).mean().iloc[-1]
        ema21 = df['close'].ewm(span=21, adjust=False).mean().iloc[-1]
        bb_mid = df['BB_mid'].iloc[-1]
        
        if pd.isna(rsi_now) or pd.isna(atr): return None
        
        trend = "🟢 WEAK_BULLISH" if ema9 > ema21 else "🔴 WEAK_BEARISH"
        is_bullish = ema9 > ema21
        is_bearish = ema9 < ema21
        
        # Price Action
        o, h, l, c = df['open'].iloc[-1], df['high'].iloc[-1], df['low'].iloc[-1], df['close'].iloc[-1]
        o1, h1, l1, c1 = df['open'].iloc[-2], df['high'].iloc[-2], df['low'].iloc[-2], df['close'].iloc[-2]
        body = abs(c - o)
        total_range = h - l
        lower_wick = min(o, c) - l
        upper_wick = h - max(o, c)
        
        is_hammer = body > 0 and total_range > 0 and lower_wick > body * 1.5 and (c - l) / total_range > 0.6
        is_engulfing = c > o and c1 < o1 and o <= c1 and c >= o1
        is_shooting_star = body > 0 and total_range > 0 and upper_wick > body * 1.5 and (h - c) / total_range > 0.6
        is_bear_engulfing = c < o and c1 > o1 and o >= c1 and c <= o1
        
        rsi_recovering = rsi_now > rsi_prev > rsi_prev2
        rsi_falling = rsi_now < rsi_prev < rsi_prev2
        
        vol_zone = get_volume_profile(df, atr)
        
        # === LONG SETUP ===
        if is_bullish and rsi_now < 50 and rsi_recovering and volr > 1.2:
            pa_signal = None
            if is_hammer: pa_signal = "HAMMER 🔨"
            elif is_engulfing: pa_signal = "BULLISH ENGULFING 🟢"
            
            if pa_signal:
                entry = round(c * 1.001, 2)
                sl = round(l - atr * 0.2, 2)
                tp1 = round(bb_mid, 2)
                tp2 = round(entry + atr * 1.5, 2)
                
                risk = abs(entry - sl) / entry * 100
                reward = abs(tp1 - entry) / entry * 100
                rr = round(reward / risk, 1) if risk > 0 else 0
                
                if rr < 1.5: return None
                
                scalp_daily_count += 1
                return {
                    'signal': 'LONG', 'entry': entry, 'sl': sl, 'tp1': tp1, 'tp2': tp2,
                    'rsi': rsi_now, 'adx': adx, 'volr': volr, 'atr': atr,
                    'trend': trend, 'pa_signal': pa_signal, 'rr': rr,
                    'vol_zone': vol_zone,
                    'supports': supports[:2], 'resistances': resistances[:2]
                }
        
        # === SHORT SETUP ===
        if is_bearish and rsi_now > 50 and rsi_falling and volr > 1.2:
            pa_signal = None
            if is_shooting_star: pa_signal = "SHOOTING STAR 🌠"
            elif is_bear_engulfing: pa_signal = "BEARISH ENGULFING 🔴"
            
            if pa_signal:
                entry = round(c * 0.999, 2)
                sl = round(h + atr * 0.2, 2)
                tp1 = round(bb_mid, 2)
                tp2 = round(entry - atr * 1.5, 2)
                
                risk = abs(sl - entry) / entry * 100
                reward = abs(entry - tp1) / entry * 100
                rr = round(reward / risk, 1) if risk > 0 else 0
                
                if rr < 1.5: return None
                
                scalp_daily_count += 1
                return {
                    'signal': 'SHORT', 'entry': entry, 'sl': sl, 'tp1': tp1, 'tp2': tp2,
                    'rsi': rsi_now, 'adx': adx, 'volr': volr, 'atr': atr,
                    'trend': trend, 'pa_signal': pa_signal, 'rr': rr,
                    'vol_zone': vol_zone,
                    'supports': supports[:2], 'resistances': resistances[:2]
                }
        
        return None
    except:
        return None

# ============================================
# V16 - PHAN TICH MOT KHUNG
# ============================================
def phan_tich_khung(df, ten_khung):
    if df is None or len(df) < 50: return 0,0,[],0,"UNKNOWN"
    rsi=df['RSI'].iloc[-1]; ma20=df['MA20'].iloc[-1]; ma50=df['MA50'].iloc[-1]
    macd=df['MACD'].iloc[-1]; macds=df['MACD_signal'].iloc[-1]
    macdp=df['MACD'].iloc[-2]; macdsp=df['MACD_signal'].iloc[-2]
    volr=df['Volume_Ratio'].iloc[-1]; adx=df['ADX'].iloc[-1]; gia=df['close'].iloc[-1]
    if pd.isna(rsi) or pd.isna(adx): return 0,0,[],0,"UNKNOWN"
    che_do = "SIDEWAY" if adx < ADX_SIDEWAY else "TREND"
    diemL=diemS=0; ly_do=[]
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
    ly_do.append(f"ADX={adx:.0f} ({che_do})")
    return diemL, diemS, ly_do, gia, che_do

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
print(f"🤖 BOT PRO - V16 + SCALP CHUAN")
print("="*60)
gui("🤖 <b>Bot PRO da khoi dong!</b>\n<b>V16:</b> 1h+4h+1d + ADX + S/R\n<b>Scalp:</b> 15m + PA + RSI hoi + R:R>=1:1.5\n⏰ Gio trade: 6h-22h | Max 15 lenh/ngay\n📊 Tracker + Bao cao 12h")

lan=0
while True:
    try:
        lan+=1
        now=datetime.now().strftime("%H:%M:%S")
        print(f"\n#{lan} | {now} | Scalp daily: {scalp_daily_count}/{SCALP_MAX_DAILY}")
        
        # ===== SCALP 15M =====
        for COIN in DANH_SACH_COIN:
            sig = scalp_analysis(COIN)
            if sig:
                key = f"scalp_{COIN}_{sig['signal']}"
                if key not in scalp_cu or (datetime.now() - scalp_cu[key]).seconds >= SCALP_COOLDOWN:
                    scalp_cu[key] = datetime.now()
                    
                    stars = "⭐⭐⭐"
                    action = "MUA" if sig['signal'] == "LONG" else "BÁN"
                    order_type = "BUY LIMIT" if sig['signal'] == "LONG" else "SELL LIMIT"
                    
                    msg = f"⚡ <b>{COIN.replace('USDT','')} - TÍN HIỆU SCALP {'🟢' if sig['signal']=='LONG' else '🔴'} {stars}</b>\n"
                    msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    msg += f"📌 <b>Coin:</b> {COIN}\n"
                    msg += f"💰 <b>Giá hiện tại:</b> ${sig['entry']:,.2f}\n"
                    msg += f"🎯 <b>ENTRY:</b> <b>${sig['entry']:,.2f}</b>\n"
                    msg += f"📊 <b>Price Action:</b> <b>{sig['pa_signal']}</b>\n"
                    msg += f"📊 <b>Vol Zone:</b> ${sig['vol_zone']:,.2f}\n"
                    msg += f"📈 <b>Trend:</b> {sig['trend']} | <b>RSI:</b> {sig['rsi']:.1f} (đang hồi) | <b>ADX:</b> {sig['adx']:.1f}\n"
                    msg += f"📊 <b>Vol:</b> {sig['volr']:.2f}x | <b>ATR:</b> ${sig['atr']:,.2f}\n"
                    msg += f"🛡️ <b>SR:</b> "
                    if sig.get('resistances'): msg += f"R1=${sig['resistances'][0]:,.2f}"
                    if len(sig.get('resistances', [])) > 1: msg += f", R2=${sig['resistances'][1]:,.2f}"
                    if sig.get('supports'): msg += f" | S1=${sig['supports'][0]:,.2f}"
                    if len(sig.get('supports', [])) > 1: msg += f", S2=${sig['supports'][1]:,.2f}"
                    msg += f"\n\n💡 <b>ĐẶT LỆNH CHỜ:</b>\n"
                    msg += f"{'🟢' if sig['signal']=='LONG' else '🔴'} <b>{order_type}</b> tại <b>${sig['entry']:,.2f}</b>\n"
                    msg += f"🎯 <b>TP1:</b> ${sig['tp1']:,.2f} | <b>TP2:</b> ${sig['tp2']:,.2f}\n"
                    msg += f"🛑 <b>SL:</b> ${sig['sl']:,.2f}\n"
                    msg += f"📐 <b>R:R = 1:{sig['rr']}</b>\n\n"
                    msg += f"⏳ <b>CHỜ GIÁ CHẠM ${sig['entry']:,.2f} ĐỂ VÀO LỆNH!</b>\n"
                    msg += now_str()
                    gui(msg)
                    tracker_them(COIN, sig['signal'], sig['entry'], sig['sl'], sig['tp1'], sig['tp2'], "Scalp")
                    print(f"   ⚡ Scalp {COIN}: {sig['signal']} | PA: {sig['pa_signal']} | R:R=1:{sig['rr']} | Daily: {scalp_daily_count}/{SCALP_MAX_DAILY}")
        
        # ===== V16 =====
        for COIN in DANH_SACH_COIN:
            ket_qua={}; df_1h=None; supports_1h=[]; resistances_1h=[]
            for khung in CAC_KHUNG:
                df=lay_nen(COIN,khung)
                if df is not None:
                    df=tinh_chi_bao(df)
                    if khung=="1h": df_1h=df; supports_1h,resistances_1h=tim_support_resistance(df)
                    diemL,diemS,ly_do,gia,che_do=phan_tich_khung(df,khung)
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
                
                msg = f"🔮 <b>{ten_coin} 🏦 1D TÍN HIỆU CHỜ {signal} {'🟢' if signal=='LONG' else '🔴'} {stars}</b>\n"
                msg += f"({'Rất mạnh' if 'CUC' in do_manh else 'Mạnh'})\n"
                msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                msg += f"📌 <b>Coin:</b> {COIN}\n"
                msg += f"💰 <b>Giá hiện tại:</b> ${gia_hien_tai:,.2f}\n"
                msg += f"🎯 <b>ENTRY LÝ TƯỞNG:</b> <b>${entry:,.2f}</b>\n"
                msg += f"   ({entry_direction} {entry_name})\n"
                msg += f"   Cách hiện tại: {entry_pct}%\n"
                msg += f"{'🟢' if signal=='LONG' else '🔴'} {action} <b>Tín hiệu:</b> {signal}\n"
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
                print(f"   ✅ V16 {ten_coin}: {signal} - {do_manh} | Entry: ${entry:.0f}")
        
        tracker_check()
        tracker_report()
        time.sleep(CHU_KY)
        
    except KeyboardInterrupt:
        print("\n👋 Dung"); gui("🛑 Bot da dung"); break
    except Exception as e:
        print(f"❌ {e}"); time.sleep(30)