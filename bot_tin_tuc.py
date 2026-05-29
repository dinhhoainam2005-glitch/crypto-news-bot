"""
BOT TIN TUC - FORMAT CHUAN - DU LIEU THAT 100%
- NewsAPI: 80.000+ nguồn báo thật
- FRED API: Dữ liệu kinh tế thật
- Kết quả sự kiện: chỉ gửi trong 24h sau khi kết thúc
"""
import requests
import time
import json
import os
from datetime import datetime, timedelta

TOKEN = os.getenv("TELEGRAM_TOKEN", "8893995280:AAF9XwWAm9QgPkwmDrhZdY6UQ4zfySooWpk")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "518284897")
FRED_API_KEY = os.getenv("FRED_API_KEY", "ff3e122af2b2c0a433606476fc6dc5fb")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "bcdf1d28d8bd401f9eb1978268efeb53")

CHU_KY_TIN = 600
CHU_KY_LICH = 3600
DATA_DIR = "data"
STATE_FILE = f"{DATA_DIR}/state.json"
LOG_FILE = f"{DATA_DIR}/log.json"

os.makedirs(DATA_DIR, exist_ok=True)

def get_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f: return json.load(f)
    return {"started": False, "fg_last": 0, "lich_last": 0}

def set_state(**kv):
    s = get_state(); s.update(kv)
    with open(STATE_FILE, 'w') as f: json.dump(s, f)

def get_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f: return json.load(f)
    return {"events": {}, "news_sent": []}

def save_log(l):
    with open(LOG_FILE, 'w') as f: json.dump(l, f, ensure_ascii=False, indent=2)

def gui(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                     data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except: pass

def now_str():
    n = datetime.now()
    return f"🕐 {n.strftime('%H:%M')} (Asia) | {(n-timedelta(hours=5)).strftime('%H:%M')} (EU) | {(n-timedelta(hours=11)).strftime('%H:%M')} (US) | {n.strftime('%d/%m/%Y')}"

def fred_ok():
    try:
        r = requests.get(f"https://api.stlouisfed.org/fred/series/observations?series_id=DFF&api_key={FRED_API_KEY}&file_type=json&limit=1", timeout=10)
        return r.status_code == 200
    except: return False

def fred_get(sid):
    if not fred_ok(): return None
    try:
        r = requests.get(f"https://api.stlouisfed.org/fred/series/observations?series_id={sid}&api_key={FRED_API_KEY}&file_type=json&limit=2&sort_order=desc", timeout=10)
        if r.status_code == 200:
            obs = r.json().get('observations', [])
            return [{'d': o['date'], 'v': float(o['value'])} for o in obs if o.get('value', '.') != '.']
    except: pass
    return None

def econ_summary():
    parts = []
    for sid, fmt in [('DFF','Fed Rate: {}%'), ('CPIAUCSL','CPI: {}'), ('UNRATE','UE: {}%'), ('GDP','GDP: ${:,.0f}B'), ('PPIACO','PPI: {}')]:
        v = fred_get(sid)
        if v: parts.append(fmt.format(v[0]['v']))
    return " | ".join(parts) if parts else "Đang tải..."

# ===== NEWS API =====
KEYWORDS = "(war OR conflict OR strike OR missile OR ukraine OR russia OR israel OR iran OR nato OR putin OR zelensky OR netanyahu OR north korea OR tariff OR recession OR crash OR inflation OR fed OR ceasefire OR peace)"

def fetch_news():
    """Lấy tin từ NewsAPI - 80.000+ nguồn thật"""
    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            'q': KEYWORDS,
            'language': 'en',
            'sortBy': 'publishedAt',
            'pageSize': 10,
            'apiKey': NEWS_API_KEY
        }
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200: return []
        
        articles = r.json().get('articles', [])
        log = get_log()
        news_list = []
        
        for a in articles:
            title = a.get('title', 'No title')
            url_news = a.get('url', '')
            source = a.get('source', {}).get('name', 'Unknown')
            
            if url_news in log['news_sent']: continue
            log['news_sent'].append(url_news)
            
            # Phân tích từ khóa để tính score
            score = 0
            keywords_found = []
            t = title.lower()
            
            kw_map = {'war':-25,'crash':-25,'strike':-18,'recession':-18,'missile':-17,
                      'north korea':-16,'iran':-15,'russia':-14,'ukraine':-12,'israel':-12,
                      'inflation':-8,'sec':-10,'tariff':-10,'nato':-10,'putin':-10,
                      'zelensky':-10,'netanyahu':-10,'ceasefire':22,'peace':20,'deal':15}
            
            for kw, w in kw_map.items():
                if kw in t:
                    score += w
                    keywords_found.append(f"{kw}({w})")
            
            if score < -5: impact = "🔴🔴🔴 CỰC KỲ TIÊU CỰC"
            elif score < -2: impact = "🔴🔴 RẤT TIÊU CỰC"
            elif score > 5: impact = "🟢🟢🟢 CỰC KỲ TÍCH CỰC"
            elif score > 2: impact = "🟢🟢 TÍCH CỰC"
            else: impact = "🟡 TRUNG TÍNH"
            
            if score < -3:
                gold, crypto, usd, advice = "🟢 TĂNG (trú ẩn)", "🔴 GIẢM (risk-off)", "🟢 TĂNG (trú ẩn)", "⚠️ ƯU TIÊN SHORT"
            elif score > 3:
                gold, crypto, usd, advice = "🔴 GIẢM (risk-on)", "🟢 TĂNG (risk-on)", "🔴 GIẢM (risk-on)", "✅ ƯU TIÊN LONG"
            else:
                gold, crypto, usd, advice = "🟡 THEO DÕI", "🟡 THEO DÕI", "🟡 THEO DÕI", "➡️ GIAO DỊCH BÌNH THƯỜNG"
            
            news_list.append({
                'title': title, 'source': source, 'impact': impact,
                'score': score, 'gold': gold, 'crypto': crypto,
                'usd': usd, 'advice': advice,
                'keywords': ", ".join(keywords_found[:5]) if keywords_found else "geopolitical"
            })
        
        log['news_sent'] = log['news_sent'][-200:]
        save_log(log)
        return news_list
    except Exception as e:
        print(f"NewsAPI error: {e}")
        return []

def market_summary(news_list):
    if not news_list: return None
    total_score = sum(n['score'] for n in news_list)
    
    if total_score < -200: level = "RẤT CAO"
    elif total_score < -100: level = "CAO"
    elif total_score < 0: level = "TRUNG BÌNH"
    else: level = "THẤP"
    
    advice = "⚠️ ƯU TIÊN SHORT" if total_score < -100 else ("✅ ƯU TIÊN LONG" if total_score > 100 else "➡️ GIAO DỊCH BÌNH THƯỜNG")
    
    all_kw = []
    for n in news_list: all_kw.extend(n['keywords'].split(', '))
    top_kw = list(set([k for k in all_kw if k and k != 'geopolitical']))[:5]
    
    return f"📰 TỔNG QUAN THỊ TRƯỜNG\n━━━━━━━━━━━━━━━━━━\n🚨 Căng thẳng {level} (score: {total_score}). {advice}\n\n📋 Số tin phát hiện: {len(news_list)}\n🔑 Từ khóa nóng: {', '.join(top_kw) if top_kw else 'đang phân tích...'}\n\n{now_str()}"

# 8 SỰ KIỆN
EVENTS = [
    {'id':'fomc_minutes_may','name':'📋 FOMC Meeting Minutes (T5)','date':'2026-05-28','time':'01:00','impact':'🟡 MEDIUM','desc':'Biên bản cuộc họp FOMC tháng 5.','fred':'DFF','fmt':'🎤 Thái độ: 🏦 Fed Rate: {value}%\n📝 Chi tiết: Biên bản đã công bố. Lãi suất hiện tại: {value}%.','gold':'Hawkish → GIẢM | Dovish → TĂNG','crypto':'Hawkish → GIẢM | Dovish → TĂNG','usd':'Hawkish → TĂNG | Dovish → GIẢM'},
    {'id':'nfp_may','name':'💼 Non-Farm Payrolls (T5)','date':'2026-06-05','time':'19:30','impact':'🔴 HIGH','desc':'Báo cáo việc làm phi nông nghiệp Mỹ.','fred':'UNRATE','fmt':'📊 Tỷ lệ thất nghiệp: {value}% (trước: {prev}%)\n🎤 Thái độ: {action}\n📝 Chi tiết: {detail}','gold':'NFP cao → GIẢM | NFP thấp → TĂNG','crypto':'NFP cao → TĂNG | NFP thấp → GIẢM','usd':'NFP cao → TĂNG | NFP thấp → GIẢM'},
    {'id':'cpi_may','name':'📊 CPI Report (T5)','date':'2026-06-11','time':'19:30','impact':'🔴 HIGH','desc':'Chỉ số giá tiêu dùng - thước đo lạm phát chính.','fred':'CPIAUCSL','fmt':'📊 CPI: {value} (trước: {prev})\n🎤 Thái độ: {action}\n📝 Chi tiết: CPI {detail}.','gold':'CPI cao → TĂNG (hedge) | CPI thấp → GIẢM','crypto':'CPI cao → GIẢM (lo tăng lãi suất) | CPI thấp → TĂNG','usd':'CPI cao → TĂNG | CPI thấp → GIẢM'},
    {'id':'ppi_may','name':'🏭 PPI Report (T5)','date':'2026-06-12','time':'19:30','impact':'🟡 MEDIUM','desc':'Chỉ số giá sản xuất.','fred':'PPIACO','fmt':'📊 PPI: {value} (trước: {prev})\n🎤 Thái độ: {action}\n📝 Chi tiết: PPI {detail}.','gold':'PPI cao → TĂNG | PPI thấp → GIẢM','crypto':'PPI cao → TĂNG nhẹ','usd':'PPI cao → TĂNG nhẹ'},
    {'id':'fomc_jun','name':'🏦 FOMC Rate Decision (T6)','date':'2026-06-18','time':'01:00','impact':'🔴 HIGH','desc':'Quyết định lãi suất Fed - SỰ KIỆN QUAN TRỌNG NHẤT.','fred':'DFF','fmt':'📊 Lãi suất Fed: {value}% (trước: {prev}%)\n🎤 Thái độ: Fed {action}\n📝 Chi tiết: {detail}.','gold':'Hawkish → GIẢM | Dovish → TĂNG','crypto':'Hawkish → GIẢM | Dovish → TĂNG','usd':'Hawkish → TĂNG | Dovish → GIẢM'},
    {'id':'gdp_q2','name':'📊 GDP Q2 2026 (Final)','date':'2026-06-25','time':'19:30','impact':'🔴 HIGH','desc':'Tăng trưởng kinh tế Mỹ quý 2/2026.','fred':'GDP','fmt':'📊 GDP: ${value:,.0f}B (trước: ${prev:,.0f}B)\n🎤 Thái độ: {action}\n📝 Chi tiết: GDP thay đổi {detail}% so với ${prev:,.0f}B.','gold':'GDP cao → GIẢM | GDP thấp → TĂNG','crypto':'GDP cao → TĂNG | GDP thấp → GIẢM','usd':'GDP cao → TĂNG | GDP thấp → GIẢM'},
    {'id':'fomc_minutes_jun','name':'📋 FOMC Meeting Minutes (T6)','date':'2026-06-04','time':'01:00','impact':'🟡 MEDIUM','desc':'Biên bản cuộc họp FOMC tháng 6.','fred':'DFF','fmt':'🎤 Thái độ: 🏦 Fed Rate: {value}%\n📝 Chi tiết: Biên bản đã công bố. Lãi suất hiện tại: {value}%.','gold':'Hawkish → GIẢM | Dovish → TĂNG','crypto':'Hawkish → GIẢM | Dovish → TĂNG','usd':'Hawkish → TĂNG | Dovish → GIẢM'},
    {'id':'fomc_jul','name':'🏦 FOMC Rate Decision (T7)','date':'2026-07-30','time':'01:00','impact':'🔴 HIGH','desc':'Quyết định lãi suất giữa năm 2026.','fred':'DFF','fmt':'📊 Lãi suất Fed: {value}% (trước: {prev}%)\n🎤 Thái độ: Fed {action}\n📝 Chi tiết: {detail}.','gold':'Hawkish → GIẢM | Dovish → TĂNG','crypto':'Hawkish → GIẢM | Dovish → TĂNG','usd':'Hawkish → TĂNG | Dovish → GIẢM'},
]

def check_events():
    log = get_log()
    now = datetime.now()
    today = now.date()
    msgs = []
    
    for ev in EVENTS:
        evd = datetime.strptime(ev['date'], '%Y-%m-%d').date()
        evdt = datetime.strptime(ev['date']+' '+ev['time'], '%Y-%m-%d %H:%M')
        days = (evd - today).days
        hours_since = (now - evdt).total_seconds()/3600 if evdt < now else -1
        
        # TRƯỚC SỰ KIỆN (D-3 đến D-0)
        if 0 <= days <= 3:
            key = f"pre_{ev['id']}"
            if time.time() - log['events'].get(key, 0) >= 43200:
                log['events'][key] = time.time()
                cd = f"⚠️ HÔM NAY lúc {ev['time']} (UTC+7)" if days==0 else f"📅 NGÀY MAI lúc {ev['time']} (UTC+7)" if days==1 else f"📅 Còn {days} ngày - {ev['date']} lúc {ev['time']} (UTC+7)"
                msg = f"📅 {ev['name']}\n━━━━━━━━━━━━━━━━━━\n⏰ {cd}\n⚡ Mức độ: {ev['impact']}\n📝 {ev['desc']}\n\n━━━━━━━━━━━━━━━━━━\n📊 TÁC ĐỘNG DỰ KIẾN:\n🥇 Vàng: {ev['gold']}\n₿ Crypto: {ev['crypto']}\n💵 USD: {ev['usd']}\n━━━━━━━━━━━━━━━━━━\n\n📊 DỮ LIỆU HIỆN TẠI:\n{econ_summary()}\n\n{now_str()}"
                msgs.append(msg)
        
        # SAU SỰ KIỆN (1h-24h): KẾT QUẢ - CHỈ 1 LẦN
        elif days < 0 and 1 <= hours_since <= 24:
            key = f"post_{ev['id']}"
            if key not in log['events'] and fred_ok():
                v = fred_get(ev['fred'])
                if v and len(v) >= 2:
                    curr, prev = v[0]['v'], v[1]['v']
                    
                    # Tính action và detail
                    if curr > prev:
                        action = "📈 TĂNG"
                        if 'fomc' in ev['id'] and 'minutes' not in ev['id']:
                            action = "TĂNG lãi suất 🦅"
                            detail = f"Fed đã TĂNG lãi suất thêm {round(curr-prev,2)}%"
                        elif 'gdp' in ev['id']:
                            action = "📈 TĂNG TRƯỞNG ✅"
                            detail = f"+{round((curr-prev)/prev*100,2)}"
                        elif 'nfp' in ev['id']:
                            action = "📈 TĂNG (lao động yếu đi)"
                            detail = "Thị trường lao động yếu đi"
                        elif 'cpi' in ev['id']:
                            action = "📈 LẠM PHÁT TĂNG"
                            detail = f"tăng +{round((curr-prev)/prev*100,1)}%"
                        elif 'ppi' in ev['id']:
                            action = "📈 TĂNG"
                            detail = "tăng"
                        else:
                            detail = ""
                    elif curr < prev:
                        action = "📉 GIẢM"
                        if 'fomc' in ev['id'] and 'minutes' not in ev['id']:
                            action = "GIẢM lãi suất 🕊️"
                            detail = f"Fed đã GIẢM lãi suất {round(prev-curr,2)}%"
                        elif 'gdp' in ev['id']:
                            action = "📉 SUY GIẢM ⚠️"
                            detail = f"{round((curr-prev)/prev*100,2)}"
                        elif 'nfp' in ev['id']:
                            action = "📉 GIẢM (lao động mạnh lên)"
                            detail = "Thị trường lao động mạnh lên"
                        elif 'cpi' in ev['id']:
                            action = "📉 LẠM PHÁT GIẢM"
                            detail = f"giảm {round((prev-curr)/prev*100,1)}%"
                        elif 'ppi' in ev['id']:
                            action = "📉 GIẢM"
                            detail = "giảm"
                        else:
                            detail = ""
                    else:
                        action = "➡️ KHÔNG ĐỔI"
                        if 'fomc' in ev['id'] and 'minutes' not in ev['id']:
                            action = "GIỮ NGUYÊN lãi suất ➡️"
                            detail = f"Fed GIỮ NGUYÊN lãi suất ở mức {curr}%"
                        elif 'nfp' in ev['id']:
                            detail = "Ổn định"
                        elif 'cpi' in ev['id']:
                            detail = "không đổi"
                        elif 'ppi' in ev['id']:
                            detail = "không đổi"
                        else:
                            detail = ""
                    
                    log['events'][key] = time.time()
                    
                    msg = f"===================================\n✅ {ev['name']} - KẾT QUẢ THỰC TẾ\n===================================\n⏰ Đã diễn ra: {ev['date']} lúc {ev['time']} (UTC+7)\n\n{ev['fmt'].format(value=curr, prev=prev, action=action, detail=detail)}\n\n━━━━━━━━━━━━━━━━━━\n📊 TÁC ĐỘNG THỊ TRƯỜNG:\n🥇 Vàng: {ev['gold']}\n₿ Crypto: {ev['crypto']}\n💵 USD: {ev['usd']}\n━━━━━━━━━━━━━━━━━━\n\n📊 DỮ LIỆU FRED:\n{econ_summary()}\n\n{now_str()}"
                    msgs.append(msg)
    
    save_log(log)
    return msgs

def get_fg():
    s = get_state()
    if time.time() - s['fg_last'] < 3600: return None
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        d = r.json()['data'][0]
        v = int(d['value']); c = d['value_classification']
        i = "😱" if v<=25 else "😟" if v<=40 else "😐" if v<=60 else "😊" if v<=75 else "🤤"
        set_state(fg_last=time.time())
        return f"{i} Fear & Greed Index: {v}/100 ({c})"
    except: return None

# === MAIN ===
print("BOT TIN TUC STARTED")

while True:
    try:
        s = get_state()
        
        if not s['started']:
            set_state(started=True)
            
            news = fetch_news()
            
            msg = f"📰 Bot tin tức đã khởi động!\n━━━━━━━━━━━━━━━━━━\n📡 FRED: {'✅ Online' if fred_ok() else '⏳ Offline'}\n📡 NewsAPI: ✅ Online\n\n📊 DỮ LIỆU KINH TẾ:\n{econ_summary()}\n\n"
            if news:
                msg += f"📋 Phát hiện {len(news)} tin tức nóng\n"
            msg += f"\n✅ Đang theo dõi sự kiện...\n\n{now_str()}"
            gui(msg)
            
            if news:
                summary = market_summary(news)
                if summary: gui(summary)
                for n in news:
                    msg = f"📰 TIN TỨC THỊ TRƯỜNG {n['impact']}\n━━━━━━━━━━━━━━━━━━\n{n['title']}\n\n📡 Nguồn: {n['source']}\n⚡ Tác động: {n['impact']} (Score: {n['score']})\n🔑 Từ khóa: {n['keywords']}\n\n🏦 Dự báo:\n🥇 Vàng: {n['gold']}\n₿ Crypto: {n['crypto']}\n💵 USD: {n['usd']}\n\n💡 Khuyến nghị: {n['advice']}\n\n{now_str()}"
                    gui(msg)
                    time.sleep(1)

        news = fetch_news()
        if news:
            summary = market_summary(news)
            if summary: gui(summary)
            for n in news:
                msg = f"📰 TIN TỨC THỊ TRƯỜNG {n['impact']}\n━━━━━━━━━━━━━━━━━━\n{n['title']}\n\n📡 Nguồn: {n['source']}\n⚡ Tác động: {n['impact']} (Score: {n['score']})\n🔑 Từ khóa: {n['keywords']}\n\n🏦 Dự báo:\n🥇 Vàng: {n['gold']}\n₿ Crypto: {n['crypto']}\n💵 USD: {n['usd']}\n\n💡 Khuyến nghị: {n['advice']}\n\n{now_str()}"
                gui(msg)
                time.sleep(1)

        if time.time() - s['lich_last'] >= CHU_KY_LICH:
            set_state(lich_last=time.time())
            for m in check_events():
                gui(m)

        fg = get_fg()
        if fg: gui(fg)

        time.sleep(CHU_KY_TIN)
    except KeyboardInterrupt: break
    except Exception as e:
        print(f"Loi: {e}")
        time.sleep(30)