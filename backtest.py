"""
BOT V16 - BALANCED VERSION
Dựa trên phân tích thực tế từ backtest
"""
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import time

# ============================================
# CONFIG CÂN BẰNG
# ============================================
DANH_SACH_COIN = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
NGAY_BACKTEST = 90
ADX_MIN = 22  # Không quá cao
RR_MIN = 2.0  # Vừa phải
INITIAL_CAPITAL = 10000
RISK_PER_TRADE = 0.015  # 1.5%
MAX_CONCURRENT = 2  # Tối đa 2 lệnh

# Điểm - dựa trên phân tích thực tế
MIN_SCORE = 6  # Từ 6 điểm trở lên (loại bỏ tín hiệu yếu)
COOLDOWN_HOURS = 12  # 12 tiếng giữa các tín hiệu cùng coin

def safe_print(msg):
    print(msg, flush=True)

# ============================================
# LẤY DỮ LIỆU
# ============================================
def lay_du_lieu_lich_su(symbol, interval, days_back):
    try:
        all_klines = []
        limit = 1000
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(days=days_back)).timestamp() * 1000)
        
        while start_time < end_time:
            url = "https://api.binance.com/api/v3/klines"
            params = {
                "symbol": symbol,
                "interval": interval,
                "limit": limit,
                "startTime": start_time,
                "endTime": end_time
            }
            
            response = requests.get(url, params=params, timeout=15)
            if response.status_code != 200:
                break
            
            data = response.json()
            if not data:
                break
            
            all_klines.extend(data)
            start_time = data[-1][0] + 1
            time.sleep(0.3)
        
        if not all_klines:
            return None
        
        df = pd.DataFrame(all_klines, columns=[
            'time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades',
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])
        
        for col in ['close', 'high', 'low', 'open', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df['time'] = pd.to_datetime(df['time'], unit='ms')
        df = df.dropna(subset=['close', 'high', 'low', 'open'])
        
        return df
    except:
        return None

# ============================================
# CHỈ BÁO
# ============================================
def tinh_chi_bao(df):
    # RSI
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MA
    df['MA20'] = df['close'].rolling(20).mean()
    df['MA50'] = df['close'].rolling(50).mean()
    
    # MACD
    e12 = df['close'].ewm(span=12, adjust=False).mean()
    e26 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = e12 - e26
    df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_hist'] = df['MACD'] - df['MACD_signal']
    
    # ATR
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    df['TR'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = df['TR'].rolling(14).mean()
    
    # ADX
    pdm = df['high'].diff().clip(lower=0)
    mdm = -df['low'].diff().clip(upper=0)
    
    pdt = pdm.where(pdm > mdm, 0)
    mdt = mdm.where(mdm > pdm, 0)
    
    atr14 = df['TR'].rolling(14).mean()
    pdi = 100 * (pdt.rolling(14).mean() / atr14)
    mdi = 100 * (mdt.rolling(14).mean() / atr14)
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi)
    df['ADX'] = dx.rolling(14).mean()
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
# SCORING - CÂN BẰNG
# ============================================
def cham_diem_khung(df, i):
    if i < 60:
        return 0, 0, []
    
    rsi = df['RSI'].iloc[i]
    adx = df['ADX'].iloc[i]
    di_plus = df['DI_plus'].iloc[i]
    di_minus = df['DI_minus'].iloc[i]
    ma20 = df['MA20'].iloc[i]
    ma50 = df['MA50'].iloc[i]
    macd_hist = df['MACD_hist'].iloc[i]
    macd_prev = df['MACD_hist'].iloc[i-1]
    stoch_k = df['Stoch_K'].iloc[i]
    stoch_d = df['Stoch_D'].iloc[i]
    volr = df['Volume_Ratio'].iloc[i]
    gia = df['close'].iloc[i]
    gia_prev = df['close'].iloc[i-1]
    
    if pd.isna(rsi) or pd.isna(adx):
        return 0, 0, []
    
    diemL = 0
    diemS = 0
    ly_do = []
    
    # === RSI (0-3 điểm) ===
    if rsi < 30:
        diemL += 3
        ly_do.append(f"RSI={rsi:.0f}")
    elif rsi < 40:
        diemL += 1
    elif rsi > 70:
        diemS += 3
    elif rsi > 60:
        diemS += 1
    
    # === ADX/DI (0-3 điểm) ===
    if adx > 25:
        if di_plus > di_minus:
            diemL += 3
            ly_do.append("Trend tăng")
        else:
            diemS += 3
            ly_do.append("Trend giảm")
    
    # === MA (0-2 điểm) ===
    if not pd.isna(ma20) and not pd.isna(ma50):
        if ma20 > ma50:
            diemL += 2
        else:
            diemS += 2
    
    # === MACD (0-3 điểm) ===
    if macd_hist > 0 and macd_prev <= 0:
        diemL += 3
        ly_do.append("MACD cắt lên")
    elif macd_hist < 0 and macd_prev >= 0:
        diemS += 3
        ly_do.append("MACD cắt xuống")
    
    # === Stochastic (0-2 điểm) ===
    if stoch_k < 20 and stoch_k > stoch_d:
        diemL += 2
        ly_do.append(f"Stoch={stoch_k:.0f}")
    elif stoch_k > 80 and stoch_k < stoch_d:
        diemS += 2
    
    # === Volume (0-2 điểm) ===
    if volr > 2.0:
        if gia > gia_prev:
            diemL += 2
            ly_do.append(f"Vol x{volr:.1f}")
        else:
            diemS += 2
    
    # === Giá vs BB (0-1 điểm) ===
    bb_lower = df['BB_lower'].iloc[i]
    bb_upper = df['BB_upper'].iloc[i]
    if not pd.isna(bb_lower) and gia <= bb_lower * 1.01:
        diemL += 1
    if not pd.isna(bb_upper) and gia >= bb_upper * 0.99:
        diemS += 1
    
    ly_do.append(f"ADX={adx:.0f}")
    return diemL, diemS, ly_do

# ============================================
# ENTRY/SL/TP
# ============================================
def tinh_entry_sltp_sr(df, signal, i):
    gia = df['close'].iloc[i]
    atr = df['ATR'].iloc[i]
    ma20 = df['MA20'].iloc[i]
    
    if pd.isna(atr) or atr == 0:
        atr = gia * 0.01
    
    if signal == "LONG":
        # Entry = giá hiện tại hoặc MA20 (cái nào thấp hơn)
        entry = min(gia, ma20) if not pd.isna(ma20) else gia
        sl = round(entry - atr * 2, 2)
        tp1 = round(entry + atr * 4, 2)
        tp2 = round(entry + atr * 6, 2)
    else:
        entry = max(gia, ma20) if not pd.isna(ma20) else gia
        sl = round(entry + atr * 2, 2)
        tp1 = round(entry - atr * 4, 2)
        tp2 = round(entry - atr * 6, 2)
    
    return entry, sl, tp1, tp2, tp2

# ============================================
# BACKTEST ENGINE ĐƠN GIẢN
# ============================================
class BacktestEngine:
    def __init__(self, initial_capital=10000):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.trades = []
        self.positions = []
    
    def can_open(self):
        return len(self.positions) < MAX_CONCURRENT
    
    def open_position(self, coin, signal, entry, sl, tp1, tp2, tp3, timestamp):
        if not self.can_open():
            return False
        
        risk = self.capital * RISK_PER_TRADE
        stop_dist = abs(entry - sl)
        if stop_dist == 0:
            return False
        
        qty = risk / stop_dist
        
        self.positions.append({
            'coin': coin,
            'signal': signal,
            'entry': entry,
            'sl': sl,
            'tp': tp1,
            'qty': qty,
            'status': 'PENDING',
            'entry_time': timestamp
        })
        return True
    
    def update(self, df, i, timestamp):
        if not self.positions:
            return []
        
        current_price = df['close'].iloc[i]
        current_high = df['high'].iloc[i]
        current_low = df['low'].iloc[i]
        
        closed = []
        
        for pos in self.positions[:]:
            # PENDING -> ACTIVE
            if pos['status'] == 'PENDING':
                if pos['signal'] == 'LONG' and current_low <= pos['entry']:
                    pos['status'] = 'ACTIVE'
                    pos['entry_price'] = pos['entry']
                elif pos['signal'] == 'SHORT' and current_high >= pos['entry']:
                    pos['status'] = 'ACTIVE'
                    pos['entry_price'] = pos['entry']
                continue
            
            if pos['status'] != 'ACTIVE':
                continue
            
            # Kiểm tra SL/TP
            hit = False
            exit_price = None
            result = None
            
            if pos['signal'] == 'LONG':
                if current_low <= pos['sl']:
                    hit = True
                    exit_price = pos['sl']
                    result = 'LOSS'
                elif current_high >= pos['tp']:
                    hit = True
                    exit_price = pos['tp']
                    result = 'WIN'
            else:
                if current_high >= pos['sl']:
                    hit = True
                    exit_price = pos['sl']
                    result = 'LOSS'
                elif current_low <= pos['tp']:
                    hit = True
                    exit_price = pos['tp']
                    result = 'WIN'
            
            if hit:
                entry_val = pos['qty'] * pos['entry_price']
                exit_val = pos['qty'] * exit_price
                
                if pos['signal'] == 'LONG':
                    pnl = exit_val - entry_val
                else:
                    pnl = entry_val - exit_val
                
                pnl_pct = (pnl / self.capital) * 100 if self.capital > 0 else 0
                
                self.trades.append({
                    'coin': pos['coin'],
                    'signal': pos['signal'],
                    'pnl_pct': pnl_pct,
                    'pnl_amount': pnl,
                    'result': result
                })
                
                self.capital += pnl
                self.positions.remove(pos)
                closed.append({'coin': pos['coin'], 'result': result, 'pnl': pnl_pct})
        
        return closed
    
    def close_all(self, current_price):
        for pos in self.positions[:]:
            if pos['status'] != 'ACTIVE':
                self.positions.remove(pos)
                continue
            
            entry_val = pos['qty'] * pos['entry_price']
            exit_val = pos['qty'] * current_price
            
            if pos['signal'] == 'LONG':
                pnl = exit_val - entry_val
            else:
                pnl = entry_val - exit_val
            
            pnl_pct = (pnl / self.capital) * 100 if self.capital > 0 else 0
            
            self.trades.append({
                'coin': pos['coin'],
                'signal': pos['signal'],
                'pnl_pct': pnl_pct,
                'pnl_amount': pnl,
                'result': 'WIN' if pnl > 0 else 'LOSS'
            })
            
            self.capital += pnl
            self.positions.remove(pos)
    
    def get_stats(self):
        if not self.trades:
            return None
        
        wins = [t for t in self.trades if t['result'] == 'WIN']
        losses = [t for t in self.trades if t['result'] == 'LOSS']
        
        total = len(self.trades)
        wr = len(wins) / total * 100 if total > 0 else 0
        total_pnl = sum(t['pnl_pct'] for t in self.trades)
        avg_win = np.mean([t['pnl_pct'] for t in wins]) if wins else 0
        avg_loss = np.mean([t['pnl_pct'] for t in losses]) if losses else 0
        
        gross_profit = sum(t['pnl_pct'] for t in wins)
        gross_loss = abs(sum(t['pnl_pct'] for t in losses))
        pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        return {
            'total_trades': total,
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': wr,
            'total_pnl_pct': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': pf,
            'final_capital': self.capital,
            'roi': (self.capital - self.initial_capital) / self.initial_capital * 100
        }

# ============================================
# CHẠY BACKTEST
# ============================================
def chay_backtest():
    safe_print("="*60)
    safe_print(f"🚀 BOT V16 - BALANCED - {NGAY_BACKTEST} NGÀY")
    safe_print(f"⚙️ Score≥{MIN_SCORE} | ADX>{ADX_MIN} | R:R≥{RR_MIN} | Cooldown {COOLDOWN_HOURS}h")
    safe_print("="*60)
    
    # Lấy dữ liệu
    all_data = {}
    for coin in DANH_SACH_COIN:
        safe_print(f"📥 Đang tải {coin}...")
        df = lay_du_lieu_lich_su(coin, "1h", NGAY_BACKTEST)
        if df is not None:
            df = tinh_chi_bao(df)
            all_data[coin] = df
            safe_print(f"  ✅ {len(df)} nến")
        time.sleep(1)
    
    if not all_data:
        return
    
    engine = BacktestEngine(INITIAL_CAPITAL)
    all_timestamps = sorted(set().union(*[set(df['time'].tolist()) for df in all_data.values()]))
    
    last_signal = {}
    signals = 0
    
    safe_print(f"\n📊 Backtest {len(all_timestamps)} điểm...")
    
    for idx, timestamp in enumerate(all_timestamps):
        if idx % 500 == 0:
            safe_print(f"⏳ {idx}/{len(all_timestamps)} | Vốn: ${engine.capital:,.0f} | Lệnh: {len(engine.trades)} | Đang mở: {len(engine.positions)}")
        
        for coin in DANH_SACH_COIN:
            if coin not in all_data:
                continue
            
            df = all_data[coin]
            mask = df['time'] == timestamp
            if not mask.any():
                continue
            
            i = df[mask].index[0]
            
            # Cập nhật vị thế
            closed = engine.update(df, i, timestamp)
            for c in closed:
                safe_print(f"  {'✅' if c['result']=='WIN' else '❌'} {c['coin']}: {c['pnl']:+.2f}% | Vốn: ${engine.capital:,.0f}")
            
            # Kiểm tra mở vị thế mới
            if not engine.can_open():
                continue
            
            # Coin đã có vị thế?
            if any(p['coin'] == coin for p in engine.positions):
                continue
            
            # Cooldown?
            if coin in last_signal:
                hours = (timestamp - last_signal[coin]).total_seconds() / 3600
                if hours < COOLDOWN_HOURS:
                    continue
            
            if i < 60:
                continue
            
            adx = df['ADX'].iloc[i]
            if pd.isna(adx) or adx < ADX_MIN:
                continue
            
            diemL, diemS, ly_do = cham_diem_khung(df, i)
            
            signal = None
            score = 0
            if diemL >= MIN_SCORE and diemL > diemS:
                signal = "LONG"
                score = diemL
            elif diemS >= MIN_SCORE and diemS > diemL:
                signal = "SHORT"
                score = diemS
            
            if not signal:
                continue
            
            result = tinh_entry_sltp_sr(df, signal, i)
            if result is None:
                continue
            
            entry, sl, tp1, tp2, tp3 = result
            
            risk = abs(entry - sl)
            reward = abs(tp1 - entry)
            rr_val = reward / risk if risk > 0 else 0
            
            if rr_val < RR_MIN:
                continue
            
            if engine.open_position(coin, signal, entry, sl, tp1, tp2, tp3, timestamp):
                last_signal[coin] = timestamp
                signals += 1
                
                safe_print(f"\n🎯 #{signals} {coin} {signal} | Score: {score}")
                safe_print(f"   Entry: ${entry:,.2f} | SL: ${sl:,.2f} | TP: ${tp1:,.2f}")
                safe_print(f"   R:R = 1:{rr_val:.1f} | {', '.join(ly_do)}")
    
    # Đóng tất cả
    final_ts = all_timestamps[-1]
    for coin, df in all_data.items():
        engine.close_all(df['close'].iloc[-1])
    
    # Kết quả
    stats = engine.get_stats()
    if stats:
        safe_print("\n" + "="*60)
        safe_print("📊 KẾT QUẢ")
        safe_print("="*60)
        safe_print(f"💰 Vốn: ${INITIAL_CAPITAL:,.0f} → ${stats['final_capital']:,.0f}")
        safe_print(f"📈 ROI: {stats['roi']:.2f}%")
        safe_print(f"🔄 Lệnh: {stats['total_trades']} | ✅ {stats['wins']} | ❌ {stats['losses']}")
        safe_print(f"📊 Win Rate: {stats['win_rate']:.1f}%")
        safe_print(f"💰 PnL: {stats['total_pnl_pct']:.2f}%")
        safe_print(f"📊 Avg Win: {stats['avg_win']:.2f}% | Avg Loss: {stats['avg_loss']:.2f}%")
        safe_print(f"📐 Profit Factor: {stats['profit_factor']:.2f}")
        
        for coin in DANH_SACH_COIN:
            ct = [t for t in engine.trades if t.get('coin') == coin]
            if ct:
                w = len([t for t in ct if t['result'] == 'WIN'])
                pnl = sum(t['pnl_pct'] for t in ct)
                safe_print(f"  {coin}: {len(ct)} lệnh | WR: {w/len(ct)*100:.0f}% | PnL: {pnl:.2f}%")
    
    safe_print(f"\n✅ Tổng tín hiệu: {signals}")

if __name__ == "__main__":
    chay_backtest()