"""
BOT TIN HIEU GIAO DICH - DA KHUNG + ADX + S/R + ENTRY + SL/TP
- 3 coin: BTC, ETH, SOL
- 3 khung: 1h, 4h, 1d
- ADX phan biet Trend/Sideway
- Support/Resistance cho Entry chinh xac
- Ghi log cho Tracker
"""
import requests
import pandas as pd
import numpy as np
import time
import json
import os
from datetime import datetime

# ============================================
# THAY BANG THONG TIN CUA BAN
# ============================================
TOKEN = os.getenv("TELEGRAM_TOKEN", "8893995280:AAF9XwWAm9QgPkwmDrhZdY6UQ4zfySooWpk")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "518284897")

# ============================================
# CAU HINH
# ============================================
DANH_SACH_COIN = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
CAC_KHUNG = ["1h", "4h", "1d"]
CHU_KY = 300
NGUONG_DIEM_TREND = 6
NGUONG_DIEM_SIDEWAY = 5
ADX_SIDEWAY = 20

tin_hieu_cu = {}

# ============================================
# GHI LOG CHO TRACKER
# ============================================
def ghi_log_tracker(coin, signal, do_manh, gia, entry, sl, tp1, tp2, rr):
    log_file = "data/tin_hieu_log.json"
    os.makedirs("data", exist_ok=True)
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            logs = json.load(f)
    else:
        logs = []
    logs.append({
        'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'coin': coin.replace('USDT', ''),
        'signal': signal,
        'do_manh': do_manh,
        'gia': gia,
        'entry': entry,
        'sl': sl,
        'tp1': tp1,
        'tp2': tp2,
        'rr': rr
    })
    logs = logs[-100:]
    with open(log_file, 'w') as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

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
        df['volume'] = df['volume'].astype(float)
        return df
    except:
        return None

# ============================================
# TINH CHI BAO
# ============================================
def tinh_chi_bao(df):
    # RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta.where(delta < 0, 0))
    df['RSI'] = 100 - (100 / (1 + gain.rolling(14).mean() / loss.rolling(14).mean()))
    
    # MA & EMA
    df['MA20'] = df['close'].rolling(20).mean()
    df['MA50'] = df['close'].rolling(50).mean()
    df['EMA20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    # MACD
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    # ATR
    df['TR'] = np.maximum(
        df['high'] - df['low'],
        np.maximum(abs(df['high'] - df['close'].shift()), abs(df['low'] - df['close'].shift()))
    )
    df['ATR'] = df['TR'].rolling(14).mean()
    
    # ADX
    plus_dm = df['high'].diff()
    minus_dm = -df['low'].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    plus_dm_true = np.where(plus_dm > minus_dm, plus_dm, 0)
    minus_dm_true = np.where(minus_dm > plus_dm, minus_dm, 0)
    atr_14 = df['TR'].rolling(14).mean()
    plus_di = 100 * (pd.Series(plus_dm_true).rolling(14).mean() / atr_14)
    minus_di = 100 * (pd.Series(minus_dm_true).rolling(14).mean() / atr_14)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    df['ADX'] = dx.rolling(14).mean()
    
    # Bollinger Bands
    df['BB_mid'] = df['close'].rolling(20).mean()
    df['BB_std'] = df['close'].rolling(20).std()
    df['BB_low'] = df['BB_mid'] - 2 * df['BB_std']
    df['BB_high'] = df['BB_mid'] + 2 * df['BB_std']
    
    # Volume
    df['Volume_Ratio'] = df['volume'] / df['volume'].rolling(20).mean()
    
    return df

# ============================================
# TIM SUPPORT & RESISTANCE
# ============================================
def tim_support_resistance(df):
    supports = []
    resistances = []
    
    for i in range(2, len(df) - 2):
        if (df['high'].iloc[i] > df['high'].iloc[i-1] and 
            df['high'].iloc[i] > df['high'].iloc[i-2] and
            df['high'].iloc[i] > df['high'].iloc[i+1] and 
            df['high'].iloc[i] > df['high'].iloc[i+2]):
            resistances.append(df['high'].iloc[i])
        
        if (df['low'].iloc[i] < df['low'].iloc[i-1] and 
            df['low'].iloc[i] < df['low'].iloc[i-2] and
            df['low'].iloc[i] < df['low'].iloc[i+1] and 
            df['low'].iloc[i] < df['low'].iloc[i+2]):
            supports.append(df['low'].iloc[i])
    
    def gom_nhom(levels, threshold=0.01):
        if not levels: return []
        levels = sorted(set(levels))
        nhom = []
        nhom_hien_tai = [levels[0]]
        for level in levels[1:]:
            if (level - nhom_hien_tai[-1]) / nhom_hien_tai[-1] < threshold:
                nhom_hien_tai.append(level)
            else:
                nhom.append(round(sum(nhom_hien_tai) / len(nhom_hien_tai), 2))
                nhom_hien_tai = [level]
        nhom.append(round(sum(nhom_hien_tai) / len(nhom_hien_tai), 2))
        return nhom
    
    supports = sorted(gom_nhom(supports), reverse=True)
    resistances = sorted(gom_nhom(resistances))
    return supports, resistances

# ============================================
# PHAN TICH MOT KHUNG
# ============================================
def phan_tich_khung(df, ten_khung):
    if df is None or len(df) < 50:
        return 0, 0, [], 0, "UNKNOWN"
    
    rsi = df['RSI'].iloc[-1]
    ma20 = df['MA20'].iloc[-1]
    ma50 = df['MA50'].iloc[-1]
    macd = df['MACD'].iloc[-1]
    macd_signal = df['MACD_signal'].iloc[-1]
    macd_prev = df['MACD'].iloc[-2]
    macd_signal_prev = df['MACD_signal'].iloc[-2]
    vol_ratio = df['Volume_Ratio'].iloc[-1]
    adx = df['ADX'].iloc[-1]
    gia = df['close'].iloc[-1]
    
    if pd.isna(rsi) or pd.isna(adx):
        return 0, 0, [], 0, "UNKNOWN"
    
    che_do = "SIDEWAY" if adx < ADX_SIDEWAY else "TREND"
    
    diemL = 0
    diemS = 0
    ly_do = []
    
    if rsi < 30:
        diemL += 3; ly_do.append(f"RSI={rsi:.0f} qua ban")
    elif rsi < 40:
        diemL += 1
    elif rsi > 70:
        diemS += 3; ly_do.append(f"RSI={rsi:.0f} qua mua")
    elif rsi > 60:
        diemS += 1
    
    if ma20 > ma50:
        diemL += 2
    else:
        diemS += 2
    
    if macd_prev < macd_signal_prev and macd > macd_signal:
        diemL += 3; ly_do.append("MACD cat len")
    elif macd_prev > macd_signal_prev and macd < macd_signal:
        diemS += 3; ly_do.append("MACD cat xuong")
    elif macd > macd_signal:
        diemL += 1
    else:
        diemS += 1
    
    if vol_ratio > 1.5:
        if df['close'].iloc[-1] > df['close'].iloc[-2]:
            diemL += 2; ly_do.append(f"Vol x{vol_ratio:.1f}")
        else:
            diemS += 2; ly_do.append(f"Vol x{vol_ratio:.1f}")
    
    ly_do.append(f"ADX={adx:.0f} ({che_do})")
    
    return diemL, diemS, ly_do, gia, che_do

# ============================================
# TIM ENTRY + SL/TP
# ============================================
def tinh_entry_sltp(df, signal_type, supports, resistances):
    gia = df['close'].iloc[-1]
    atr = df['ATR'].iloc[-1]
    ma20 = df['MA20'].iloc[-1]
    ma50 = df['MA50'].iloc[-1]
    ema20 = df['EMA20'].iloc[-1]
    ema50 = df['EMA50'].iloc[-1]
    bb_low = df['BB_low'].iloc[-1]
    bb_high = df['BB_high'].iloc[-1]
    
    if pd.isna(atr):
        atr = gia * 0.01
    
    if signal_type == "LONG":
        cac_muc = []
        for s in supports[:3]:
            if s < gia:
                cac_muc.append((f"Support ${s:.0f}", s))
                break
        if ma20 < gia: cac_muc.append(("MA20", ma20))
        if ma50 < gia: cac_muc.append(("MA50", ma50))
        if ema20 < gia: cac_muc.append(("EMA20", ema20))
        if bb_low < gia: cac_muc.append(("BB Low", bb_low))
        
        if cac_muc:
            entry_name, entry = max(cac_muc, key=lambda x: x[1])
        else:
            entry_name, entry = "Gia -1%", gia * 0.99
        
        sl_atr = entry - atr * 1.5
        sl_support = None
        for s in supports:
            if s < entry * 0.98:
                sl_support = s * 0.995
                break
        sl = max(sl_atr, sl_support) if sl_support else sl_atr
        sl = round(sl, 2)
        
        tp_atr = entry + atr * 2
        tp_resistance = None
        for r in resistances:
            if r > entry:
                tp_resistance = r * 0.995
                break
        tp1 = min(tp_atr, tp_resistance) if tp_resistance else tp_atr
        tp1 = round(tp1, 2)
        tp2 = round(entry + atr * 3, 2)
        
    else:
        cac_muc = []
        for r in resistances[:3]:
            if r > gia:
                cac_muc.append((f"Resistance ${r:.0f}", r))
                break
        if ma20 > gia: cac_muc.append(("MA20", ma20))
        if ma50 > gia: cac_muc.append(("MA50", ma50))
        if ema20 > gia: cac_muc.append(("EMA20", ema20))
        if bb_high > gia: cac_muc.append(("BB High", bb_high))
        
        if cac_muc:
            entry_name, entry = min(cac_muc, key=lambda x: x[1])
        else:
            entry_name, entry = "Gia +1%", gia * 1.01
        
        sl_atr = entry + atr * 1.5
        sl_resistance = None
        for r in resistances:
            if r > entry * 1.02:
                sl_resistance = r * 1.005
                break
        sl = min(sl_atr, sl_resistance) if sl_resistance else sl_atr
        sl = round(sl, 2)
        
        tp_atr = entry - atr * 2
        tp_support = None
        for s in supports:
            if s < entry:
                tp_support = s * 1.005
                break
        tp1 = max(tp_atr, tp_support) if tp_support else tp_atr
        tp1 = round(tp1, 2)
        tp2 = round(entry - atr * 3, 2)
    
    return entry, entry_name, sl, tp1, tp2

# ============================================
# GUI TELEGRAM
# ============================================
def gui_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except:
        pass

# ============================================
# CHAY BOT
# ============================================
print("=" * 60)
print(f"🤖 BOT TIN HIEU - {', '.join(DANH_SACH_COIN)}")
print("=" * 60)
print(f"📊 Khung: {', '.join(CAC_KHUNG)}")
print(f"🎯 ADX < {ADX_SIDEWAY}: Sideway | ADX >= {ADX_SIDEWAY}: Trend")
print(f"🎯 Trend >= {NGUONG_DIEM_TREND}d | Sideway >= {NGUONG_DIEM_SIDEWAY}d")
print(f"🎯 Entry: S/R + MA + EMA + BB")
print(f"⏱️  Chu ky: {CHU_KY}s")
print("=" * 60)

gui_telegram(f"🤖 Bot tin hieu da khoi dong!\nTheo doi: {', '.join(DANH_SACH_COIN)}\nKhung: 1h+4h+1d\nADX + S/R + Entry ly tuong")

lan = 0

while True:
    try:
        lan += 1
        now = datetime.now().strftime("%H:%M:%S")
        
        print(f"\n{'='*60}")
        print(f"#{lan} | {now}")
        print(f"{'='*60}")
        
        for COIN in DANH_SACH_COIN:
            ket_qua = {}
            df_1h = None
            supports_1h = []
            resistances_1h = []
            
            for khung in CAC_KHUNG:
                df = lay_nen(COIN, khung)
                if df is not None:
                    df = tinh_chi_bao(df)
                    if khung == "1h":
                        df_1h = df
                        supports_1h, resistances_1h = tim_support_resistance(df)
                    diemL, diemS, ly_do, gia, che_do = phan_tich_khung(df, khung)
                    ket_qua[khung] = {"L": diemL, "S": diemS, "che_do": che_do}
            
            if not ket_qua:
                continue
            
            gia_hien_tai = df['close'].iloc[-1]
            
            so_khung_L = 0
            so_khung_S = 0
            for k, v in ket_qua.items():
                nguong = NGUONG_DIEM_TREND if v['che_do'] == "TREND" else NGUONG_DIEM_SIDEWAY
                if v['L'] >= nguong: so_khung_L += 1
                if v['S'] >= nguong: so_khung_S += 1
            
            che_do_khung = [f"{k}:{v['che_do'][:1]}" for k, v in ket_qua.items()]
            sr_info = ""
            if supports_1h: sr_info += f" S:{supports_1h[0]:.0f}"
            if resistances_1h: sr_info += f" R:{resistances_1h[0]:.0f}"
            
            print(f"{COIN}: ${gia_hien_tai:,.0f} | L={so_khung_L}/3 S={so_khung_S}/3 | {' '.join(che_do_khung)}{sr_info}")
            
            if so_khung_L >= 2:
                signal = "LONG"
                do_manh = "CUC MANH (3/3)" if so_khung_L == 3 else "MANH (2/3)"
            elif so_khung_S >= 2:
                signal = "SHORT"
                do_manh = "CUC MANH (3/3)" if so_khung_S == 3 else "MANH (2/3)"
            else:
                signal = "NEUTRAL"
            
            if COIN not in tin_hieu_cu:
                tin_hieu_cu[COIN] = None
            
            if signal != "NEUTRAL" and signal != tin_hieu_cu[COIN] and df_1h is not None:
                entry, entry_name, sl, tp1, tp2 = tinh_entry_sltp(df_1h, signal, supports_1h, resistances_1h)
                
                risk = abs(entry - sl)
                reward = abs(tp1 - entry)
                rr = round(reward / risk, 1) if risk > 0 else 0
                
                icon = "🟢" if signal == "LONG" else "🔴"
                ten_coin = COIN.replace("USDT", "")
                trend_count = sum(1 for v in ket_qua.values() if v['che_do'] == "TREND")
                
                msg = f"{icon} <b>TIN HIEU {signal} - {ten_coin}</b>\n"
                msg += f"━━━━━━━━━━━━━━━━\n"
                msg += f"📊 Do manh: <b>{do_manh}</b> | {trend_count}/3 Trend\n\n"
                msg += f"💰 Gia hien tai: <b>${gia_hien_tai:,.0f}</b>\n"
                msg += f"🎯 Entry ly tuong: <b>${entry:,.0f}</b>\n"
                msg += f"   ↳ Qua: {entry_name}\n"
                msg += f"🛑 SL: <b>${sl:,.0f}</b>\n"
                msg += f"✅ TP1: <b>${tp1:,.0f}</b> | TP2: <b>${tp2:,.0f}</b>\n"
                msg += f"📊 R:R = <b>1:{rr}</b>\n\n"
                msg += f"📝 S/R khung 1h:\n"
                if supports_1h:
                    msg += f"  • Supports: {', '.join([f'${s:.0f}' for s in supports_1h[:3]])}\n"
                if resistances_1h:
                    msg += f"  • Resistances: {', '.join([f'${r:.0f}' for r in resistances_1h[:3]])}\n"
                msg += f"\n📊 Diem tung khung:\n"
                for khung, v in ket_qua.items():
                    msg += f"  • {khung}: L={v['L']}/10 S={v['S']}/10 | {v['che_do']}\n"
                msg += f"\n⏰ {now}"
                
                gui_telegram(msg)
                tin_hieu_cu[COIN] = signal
                
                # GHI LOG CHO TRACKER
                ghi_log_tracker(COIN, signal, do_manh, gia_hien_tai, entry, sl, tp1, tp2, rr)
                
                print(f"   ✅ {ten_coin}: {signal} - {do_manh} | Entry: ${entry:.0f}")
        
        time.sleep(CHU_KY)
        
    except KeyboardInterrupt:
        print("\n👋 Bot da dung!")
        gui_telegram("🛑 Bot tin hieu da dung")
        break
    except Exception as e:
        print(f"❌ Loi: {e}")
        time.sleep(30)