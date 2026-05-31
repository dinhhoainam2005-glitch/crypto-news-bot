"""
BACKTEST 180 NGAY - PHAN TICH NANG CAO
Tim cach nang win rate tu 65.8% len 70-75%
"""
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import time

DANH_SACH_COIN = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
NGAY_BACKTEST = 180
ADX_MIN = 22
RR_MIN = 2.0
MIN_SCORE = 6
INITIAL_CAPITAL = 10000
RISK_PER_TRADE = 0.015
MAX_CONCURRENT = 2
COOLDOWN_HOURS = 12
TRADING_FEE = 0.001
SLIPPAGE = 0.0005

def safe_print(msg):
    print(msg, flush=True)

def lay_du_lieu_lich_su(symbol, interval, days_back):
    try:
        all_klines = []
        limit = 1000
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(days=days_back)).timestamp() * 1000)
        
        while start_time < end_time:
            url = "https://api.binance.com/api/v3/klines"
            params = {"symbol": symbol, "interval": interval, "limit": limit, "startTime": start_time, "endTime": end_time}
            response = requests.get(url, params=params, timeout=15)
            if response.status_code != 200: break
            data = response.json()
            if not data: break
            all_klines.extend(data)
            start_time = data[-1][0] + 1
            time.sleep(0.3)
        
        if not all_klines: return None
        
        df = pd.DataFrame(all_klines, columns=['time','open','high','low','close','volume','close_time','quote_volume','trades','taker_buy_base','taker_buy_quote','ignore'])
        for col in ['close','high','low','open','volume']: df[col] = pd.to_numeric(df[col], errors='coerce')
        df['time'] = pd.to_datetime(df['time'], unit='ms')
        return df.dropna(subset=['close','high','low','open']).reset_index(drop=True)
    except: return None

def tinh_chi_bao(df):
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    df['RSI'] = 100 - (100 / (1 + gain.rolling(14).mean() / loss.rolling(14).mean()))
    df['MA20'] = df['close'].rolling(20).mean()
    df['MA50'] = df['close'].rolling(50).mean()
    e12 = df['close'].ewm(span=12, adjust=False).mean()
    e26 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = e12 - e26
    df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_hist'] = df['MACD'] - df['MACD_signal']
    
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    df['TR'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = df['TR'].rolling(14).mean()
    
    pdm = df['high'].diff().clip(lower=0)
    mdm = -df['low'].diff().clip(upper=0)
    pdt = pdm.where(pdm > mdm, 0)
    mdt = mdm.where(mdm > pdm, 0)
    atr14 = df['TR'].rolling(14).mean()
    pdi = 100 * (pdt.rolling(14).mean() / atr14)
    mdi = 100 * (mdt.rolling(14).mean() / atr14)
    df['ADX'] = (100 * (pdi - mdi).abs() / (pdi + mdi)).rolling(14).mean()
    df['DI_plus'] = pdi
    df['DI_minus'] = mdi
    
    df['Volume_Ratio'] = df['volume'] / df['volume'].rolling(20).mean()
    df['BB_mid'] = df['close'].rolling(20).mean()
    df['BB_std'] = df['close'].rolling(20).std()
    df['BB_upper'] = df['BB_mid'] + 2 * df['BB_std']
    df['BB_lower'] = df['BB_mid'] - 2 * df['BB_std']
    
    low_14 = df['low'].rolling(14).min()
    high_14 = df['high'].rolling(14).max()
    df['Stoch_K'] = 100 * ((df['close'] - low_14) / (high_14 - low_14))
    df['Stoch_D'] = df['Stoch_K'].rolling(3).mean()
    
    # Them chi bao moi
    df['EMA9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['price_change_1h'] = df['close'].pct_change()
    df['price_change_4h'] = df['close'].pct_change(4)
    df['volatility_24h'] = df['close'].rolling(24).std() / df['close'].rolling(24).mean()
    
    return df

def cham_diem_khung(df, i):
    if i < 60: return 0, 0, []
    
    rsi = df['RSI'].iloc[i]
    adx = df['ADX'].iloc[i]
    di_plus = df['DI_plus'].iloc[i]
    di_minus = df['DI_minus'].iloc[i]
    ma20 = df['MA20'].iloc[i]
    ma50 = df['MA50'].iloc[i]
    ema9 = df['EMA9'].iloc[i]
    ema21 = df['EMA21'].iloc[i]
    macd_hist = df['MACD_hist'].iloc[i]
    macd_prev = df['MACD_hist'].iloc[i-1]
    stoch_k = df['Stoch_K'].iloc[i]
    stoch_d = df['Stoch_D'].iloc[i]
    volr = df['Volume_Ratio'].iloc[i]
    gia = df['close'].iloc[i]
    gia_prev = df['close'].iloc[i-1]
    bb_lower = df['BB_lower'].iloc[i]
    bb_upper = df['BB_upper'].iloc[i]
    vol_24h = df['volatility_24h'].iloc[i]
    price_chg_4h = df['price_change_4h'].iloc[i]
    
    if pd.isna(rsi) or pd.isna(adx): return 0, 0, []
    
    diemL = 0
    diemS = 0
    ly_do = []
    
    # RSI (0-4 diem)
    if rsi < 25: diemL += 4; ly_do.append(f"RSI={rsi:.0f}")
    elif rsi < 35: diemL += 2
    elif rsi > 75: diemS += 4
    elif rsi > 65: diemS += 2
    
    # ADX/DI (0-3 diem)
    if adx > 25:
        if di_plus > di_minus: diemL += 3; ly_do.append("Trend tăng")
        else: diemS += 3; ly_do.append("Trend giảm")
    
    # MA & EMA (0-3 diem)
    if not pd.isna(ma20) and not pd.isna(ma50):
        if ma20 > ma50 and ema9 > ema21: diemL += 3
        elif ma20 < ma50 and ema9 < ema21: diemS += 3
        elif ma20 > ma50: diemL += 2
        else: diemS += 2
    
    # MACD (0-3 diem)
    if macd_hist > 0 and macd_prev <= 0: diemL += 3; ly_do.append("MACD cắt lên")
    elif macd_hist < 0 and macd_prev >= 0: diemS += 3; ly_do.append("MACD cắt xuống")
    
    # Stochastic (0-2 diem)
    if stoch_k < 20 and stoch_k > stoch_d: diemL += 2; ly_do.append(f"Stoch={stoch_k:.0f}")
    elif stoch_k > 80 and stoch_k < stoch_d: diemS += 2
    
    # Volume (0-2 diem)
    if volr > 2.0:
        if gia > gia_prev: diemL += 2; ly_do.append(f"Vol x{volr:.1f}")
        else: diemS += 2
    
    # Bollinger Bands (0-2 diem)
    if not pd.isna(bb_lower) and gia <= bb_lower * 1.005: diemL += 2; ly_do.append("BB dưới")
    if not pd.isna(bb_upper) and gia >= bb_upper * 0.995: diemS += 2; ly_do.append("BB trên")
    
    # Volatility (0-1 diem) - tranh thi truong bien dong qua manh
    if not pd.isna(vol_24h) and vol_24h > 0.05:
        if diemL > diemS: diemL -= 1
        else: diemS -= 1
    
    # Price change 4h (0-1 diem) - xu huong ngan han
    if not pd.isna(price_chg_4h):
        if price_chg_4h > 0.03: diemL += 1
        elif price_chg_4h < -0.03: diemS += 1
    
    ly_do.append(f"ADX={adx:.0f}")
    return diemL, diemS, ly_do

def tinh_entry_sltp(df, signal, i):
    gia = df['close'].iloc[i]
    atr = df['ATR'].iloc[i]
    ma20 = df['MA20'].iloc[i]
    if pd.isna(atr) or atr == 0: atr = gia * 0.01
    
    if signal == "LONG":
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

class BacktestEngine:
    def __init__(self, capital=10000):
        self.initial = capital
        self.capital = capital
        self.trades = []
        self.positions = []
        self.equity = []
    
    def can_open(self): return len(self.positions) < MAX_CONCURRENT
    
    def open_position(self, coin, signal, entry, sl, tp1, tp2, tp3, ts):
        if not self.can_open(): return False
        risk = self.capital * RISK_PER_TRADE
        dist = abs(entry - sl)
        if dist == 0: return False
        qty = risk / dist
        if qty * entry > self.capital * 0.5: return False
        
        self.positions.append({'coin':coin,'signal':signal,'entry':entry,'sl':sl,'tp':tp1,'qty':qty,'status':'PENDING','entry_time':ts})
        return True
    
    def update(self, df, i, ts):
        if not self.positions: return []
        cp = df['close'].iloc[i]; ch = df['high'].iloc[i]; cl = df['low'].iloc[i]
        closed = []
        
        for pos in self.positions[:]:
            if pos['status'] == 'PENDING':
                if pos['signal'] == 'LONG' and cl <= pos['entry']:
                    pos['status'] = 'ACTIVE'; pos['entry_price'] = pos['entry']
                    self.capital -= pos['qty'] * pos['entry_price'] * TRADING_FEE
                elif pos['signal'] == 'SHORT' and ch >= pos['entry']:
                    pos['status'] = 'ACTIVE'; pos['entry_price'] = pos['entry']
                    self.capital -= pos['qty'] * pos['entry_price'] * TRADING_FEE
                continue
            
            if pos['status'] != 'ACTIVE': continue
            
            hit = False; ep = None; result = None
            if pos['signal'] == 'LONG':
                if cl <= pos['sl']: hit = True; ep = pos['sl'] * (1 - SLIPPAGE); result = 'LOSS'
                elif ch >= pos['tp']: hit = True; ep = pos['tp']; result = 'WIN'
            else:
                if ch >= pos['sl']: hit = True; ep = pos['sl'] * (1 + SLIPPAGE); result = 'LOSS'
                elif cl <= pos['tp']: hit = True; ep = pos['tp']; result = 'WIN'
            
            if hit:
                ev = pos['qty'] * pos['entry_price']; xv = pos['qty'] * ep
                fee = xv * TRADING_FEE
                pnl = (xv - ev - fee) if pos['signal'] == 'LONG' else (ev - xv - fee)
                pnl_pct = (pnl / self.capital) * 100 if self.capital > 0 else 0
                
                self.trades.append({'coin':pos['coin'],'signal':pos['signal'],'entry_price':pos['entry_price'],'exit_price':ep,'pnl_pct':pnl_pct,'pnl_amount':pnl,'result':result,'entry_time':pos.get('entry_time'),'exit_time':ts})
                self.capital += pnl
                self.positions.remove(pos)
                closed.append({'coin':pos['coin'],'result':result,'pnl_pct':pnl_pct})
        
        # Equity curve
        ur = 0
        for pos in self.positions:
            if pos['status'] == 'ACTIVE':
                ur += pos['qty'] * (cp - pos['entry_price']) if pos['signal'] == 'LONG' else pos['qty'] * (pos['entry_price'] - cp)
        self.equity.append({'ts':ts,'equity':self.capital+ur,'capital':self.capital})
        return closed
    
    def close_all(self, cp):
        for pos in self.positions[:]:
            if pos['status'] != 'ACTIVE': self.positions.remove(pos); continue
            ev = pos['qty'] * pos['entry_price']; xv = pos['qty'] * cp
            fee = xv * TRADING_FEE
            pnl = (xv - ev - fee) if pos['signal'] == 'LONG' else (ev - xv - fee)
            pnl_pct = (pnl / self.capital) * 100 if self.capital > 0 else 0
            self.trades.append({'coin':pos['coin'],'signal':pos['signal'],'pnl_pct':pnl_pct,'pnl_amount':pnl,'result':'WIN' if pnl > 0 else 'LOSS'})
            self.capital += pnl
            self.positions.remove(pos)
    
    def stats(self):
        if not self.trades: return None
        wins = [t for t in self.trades if t['result']=='WIN']
        losses = [t for t in self.trades if t['result']=='LOSS']
        total = len(self.trades)
        wr = len(wins)/total*100 if total>0 else 0
        total_pnl = sum(t['pnl_pct'] for t in self.trades)
        avg_win = np.mean([t['pnl_pct'] for t in wins]) if wins else 0
        avg_loss = np.mean([t['pnl_pct'] for t in losses]) if losses else 0
        gp = sum(t['pnl_pct'] for t in wins)
        gl = abs(sum(t['pnl_pct'] for t in losses))
        pf = gp/gl if gl>0 else float('inf')
        
        max_dd = 0
        if self.equity:
            peak = self.equity[0]['equity']
            for e in self.equity:
                if e['equity']>peak: peak=e['equity']
                dd = (peak-e['equity'])/peak*100 if peak>0 else 0
                max_dd = max(max_dd, dd)
        
        return {'total_trades':total,'wins':len(wins),'losses':len(losses),'win_rate':wr,'total_pnl_pct':total_pnl,'avg_win':avg_win,'avg_loss':avg_loss,'profit_factor':pf,'max_drawdown':max_dd,'final_capital':self.capital,'roi':(self.capital-self.initial)/self.initial*100}

def run_backtest(days, min_score, adx_min, rr_min, cooldown):
    safe_print(f"\n{'='*60}")
    safe_print(f"🔬 TEST: Score≥{min_score} | ADX>{adx_min} | R:R≥{rr_min} | Cooldown={cooldown}h")
    
    all_data = {}
    for coin in DANH_SACH_COIN:
        df = lay_du_lieu_lich_su(coin, "1h", days)
        if df is not None:
            df = tinh_chi_bao(df)
            all_data[coin] = df
    
    if not all_data: return None
    
    all_ts = sorted(set().union(*[set(df['time'].tolist()) for df in all_data.values()]))
    engine = BacktestEngine(INITIAL_CAPITAL)
    last_sig = {}
    
    for idx, ts in enumerate(all_ts):
        for coin in DANH_SACH_COIN:
            if coin not in all_data: continue
            df = all_data[coin]
            mask = df['time'] == ts
            if not mask.any(): continue
            i = df[mask].index[0]
            
            engine.update(df, i, ts)
            
            if not engine.can_open(): continue
            if any(p['coin']==coin for p in engine.positions): continue
            if coin in last_sig:
                if (ts - last_sig[coin]).total_seconds()/3600 < cooldown: continue
            if i < 60: continue
            
            adx = df['ADX'].iloc[i]
            if pd.isna(adx) or adx < adx_min: continue
            
            diemL, diemS, _ = cham_diem_khung(df, i)
            
            signal = None
            if diemL >= min_score and diemL > diemS: signal = "LONG"
            elif diemS >= min_score and diemS > diemL: signal = "SHORT"
            if not signal: continue
            
            result = tinh_entry_sltp(df, signal, i)
            if result is None: continue
            entry, sl, tp1, tp2, tp3 = result
            
            risk = abs(entry-sl); reward = abs(tp1-entry)
            if risk == 0 or reward/risk < rr_min: continue
            
            if engine.open_position(coin, signal, entry, sl, tp1, tp2, tp3, ts):
                last_sig[coin] = ts
    
    final_ts = all_ts[-1]
    for coin, df in all_data.items():
        engine.close_all(df['close'].iloc[-1])
    
    return engine.stats()

# ============================================
# CHAY THU CAC THAM SO
# ============================================
safe_print("="*60)
safe_print("🔬 TOI UU THAM SO - 180 NGAY BACKTEST")
safe_print("="*60)

# Cac bo tham so test
test_configs = [
    # (name, min_score, adx_min, rr_min, cooldown)
    ("Hien tai", 6, 22, 2.0, 12),
    ("Chat hon", 7, 25, 2.0, 12),
    ("Chat hon nua", 7, 25, 2.5, 24),
    ("Nhieu tin hieu hon", 5, 20, 1.8, 8),
    ("Can bang", 6, 22, 2.2, 12),
]

results = []
for name, score, adx, rr, cd in test_configs:
    stats = run_backtest(180, score, adx, rr, cd)
    if stats:
        results.append({'name':name,'score':score,'adx':adx,'rr':rr,'cd':cd,**stats})
        safe_print(f"  {name}: WR={stats['win_rate']:.1f}% | ROI={stats['roi']:.1f}% | Trades={stats['total_trades']} | PF={stats['profit_factor']:.2f} | DD={stats['max_drawdown']:.1f}%")

# In bang tong ket
safe_print(f"\n{'='*80}")
safe_print(f"📊 BANG TONG KET")
safe_print(f"{'='*80}")
safe_print(f"{'Cau hinh':<20} {'Score':>6} {'ADX':>5} {'R:R':>5} {'CD(h)':>6} {'Trades':>7} {'WR':>7} {'ROI':>9} {'PF':>6} {'DD':>7}")
safe_print(f"{'-'*80}")
for r in results:
    safe_print(f"{r['name']:<20} {r['score']:>6} {r['adx']:>5} {r['rr']:>5} {r['cd']:>6} {r['total_trades']:>7} {r['win_rate']:>6.1f}% {r['roi']:>8.1f}% {r['profit_factor']:>5.2f} {r['max_drawdown']:>6.1f}%")

# Tim cau hinh tot nhat
best = max(results, key=lambda x: x['profit_factor'])
safe_print(f"\n🏆 CAU HINH TOT NHAT: {best['name']}")
safe_print(f"   Score≥{best['score']} | ADX>{best['adx']} | R:R≥{best['rr']} | Cooldown={best['cd']}h")
safe_print(f"   WR: {best['win_rate']:.1f}% | ROI: {best['roi']:.1f}% | PF: {best['profit_factor']:.2f} | DD: {best['max_drawdown']:.1f}%")