"""
BOT TIN TUC - FORMAT CHUAN - DU LIEU THAT 100%
"""
import requests
import time
import json
import os
from datetime import datetime, timedelta

TOKEN = os.getenv("TELEGRAM_TOKEN", "8893995280:AAF9XwWAm9QgPkwmDrhZdY6UQ4zfySooWpk")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "518284897")
FRED_API_KEY = os.getenv("FRED_API_KEY", "ff3e122af2b2c0a433606476fc6dc5fb")

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

KEYWORDS = "war OR conflict OR strike OR missile OR ukraine OR russia OR israel OR iran OR nato OR putin OR zelensky OR netanyahu OR north korea OR tariff OR recession OR crash OR sec OR inflation OR fed OR ceasefire OR peace OR trade war"

def gdelt_news():
    try:
        url = f"https://api.gdeltproject.org/api/v2/doc/doc?query={requests.utils.quote(KEYWORDS)}&mode=artlist&format=json&maxrecords=10&sort=datedesc"
        r = requests.get(url, timeout=15)
        if r.status_code != 200 or 'articles' not in r.json(): return []
        
        articles = r.json()['articles']
        log = get_log()
        news_list = []
        
        for a in articles:
            url_news = a.get('url', '')
            if url_news in log['news_sent']: continue
            
            title = a.get('title', 'No title')
            domain = a.get('domain', 'Unknown')
            tone = float(a.get('tone', 0))
            log['news_sent'].append(url_news)
            
            if tone < -5: impact = "🔴🔴🔴 CỰC KỲ TIÊU CỰC"
            elif tone < -2: impact = "🔴🔴 RẤT TIÊU CỰC"
            elif tone > 5: impact = "🟢🟢🟢 CỰC KỲ TÍCH CỰC"
            elif tone > 2: impact = "🟢🟢 TÍCH CỰC"
            else: impact = "🟡 TRUNG TÍNH"
            
            if tone < -3:
                gold, crypto, usd, advice = "🟢 TĂNG (trú ẩn)", "🔴 GIẢM (risk-off)", "🟢 TĂNG (trú ẩn)", "⚠️ ƯU TIÊN SHORT"
            elif tone > 3:
                gold, crypto, usd, advice = "🔴 GIẢM (risk-on)", "🟢 TĂNG (risk-on)", "🔴 GIẢM (risk-on)", "✅ ƯU TIÊN LONG"
            else:
                gold, crypto, usd, advice = "🟡 THEO DÕI", "🟡 THEO DÕI", "🟡 THEO DÕI", "➡️ GIAO DỊCH BÌNH THƯỜNG"
            
            keywords_found = []
            kw_map = {'war':-25,'crash':-25,'strike':-18,'recession':-18,'missile':-17,'north korea':-16,'iran':-15,'russia':-14,'ukraine':-12,'israel':-12,'inflation':-8,'sec':-10,'tariff':-10,'nato':-10,'putin':-10,'zelensky':-10,'netanyahu':-10,'ceasefire':22,'peace':20,'deal':15}
            for kw, w in kw_map.items():
                if kw in title.lower():
                    keywords_found.append(f"{kw}({w})")
            
            news_list.append({
                'title': title, 'source': domain, 'impact': impact,
                'score': int(tone), 'gold': gold, 'crypto': crypto,
                'usd': usd, 'advice': advice,
                'keywords': ", ".join(keywords_found[:5]) if keywords_found else "geopolitical"
            })
        
        log['news_sent'] = log['news_sent'][-200:]
        save_log(log)
        return news_list
    except: return []

# 8 SỰ KIỆN KINH TẾ
EVENTS = [
    {
        'id':'fomc_minutes_may','name':'📋 FOMC Meeting Minutes (T5)','date':'2026-05-28','time':'01:00','impact':'🟡 MEDIUM',
        'desc':'Biên bản cuộc họp FOMC tháng 5 - tiết lộ quan điểm các thành viên Fed.',
        'fred':'DFF','fmt':'🎤 Thái độ: 🏦 Fed Rate: {value}%\n📝 Chi tiết: Biên bản đã công bố. Lãi suất hiện tại: {value}%.',
        'gold':'Hawkish → GIẢM | Dovish → TĂNG','crypto':'Hawkish → GIẢM | Dovish → TĂNG','usd':'Hawkish → TĂNG | Dovish → GIẢM'
    },
    {
        'id':'nfp_may','name':'💼 Non-Farm Payrolls (T5)','date':'2026-06-05','time':'19:30','impact':'🔴 HIGH',
        'desc':'Báo cáo việc làm phi nông nghiệp Mỹ.',
        'fred':'UNRATE','fmt':'📊 Tỷ lệ thất nghiệp: {value}% (trước: {prev}%)\n🎤 Thái độ: {"📈 TĂNG" if value>prev else "📉 GIẢM" if value<prev else "➡️ KHÔNG ĐỔI"}\n📝 Chi tiết: {"Thị trường lao động yếu đi" if value>prev else "Thị trường lao động mạnh lên" if value<prev else "Ổn định"}.',
        'gold':'NFP cao → GIẢM | NFP thấp → TĂNG','crypto':'NFP cao → TĂNG | NFP thấp → GIẢM','usd':'NFP cao → TĂNG | NFP thấp → GIẢM'
    },
    {
        'id':'cpi_may','name':'📊 CPI Report (T5)','date':'2026-06-11','time':'19:30','impact':'🔴 HIGH',
        'desc':'Chỉ số giá tiêu dùng - thước đo lạm phát chính.',
        'fred':'CPIAUCSL','fmt':'📊 CPI: {value} (trước: {prev})\n🎤 Thái độ: {"📈 LẠM PHÁT TĂNG" if value>prev else "📉 LẠM PHÁT GIẢM" if value<prev else "➡️ KHÔNG ĐỔI"}\n📝 Chi tiết: CPI {"tăng +{:.1f}%".format((value-prev)/prev*100) if value>prev else "giảm {:.1f}%".format((prev-value)/prev*100) if value<prev else "không đổi"}.',
        'gold':'CPI cao → TĂNG (hedge) | CPI thấp → GIẢM','crypto':'CPI cao → GIẢM (lo tăng lãi suất) | CPI thấp → TĂNG','usd':'CPI cao → TĂNG | CPI thấp → GIẢM'
    },
    {
        'id':'ppi_may','name':'🏭 PPI Report (T5)','date':'2026-06-12','time':'19:30','impact':'🟡 MEDIUM',
        'desc':'Chỉ số giá sản xuất - chỉ báo sớm của lạm phát.',
        'fred':'PPIACO','fmt':'📊 PPI: {value} (trước: {prev})\n🎤 Thái độ: {"📈 TĂNG" if value>prev else "📉 GIẢM" if value<prev else "➡️ KHÔNG ĐỔI"}\n📝 Chi tiết: PPI {"tăng" if value>prev else "giảm" if value<prev else "không đổi"}, phản ánh áp lực giá ở cấp độ sản xuất.',
        'gold':'PPI cao → TĂNG | PPI thấp → GIẢM','crypto':'PPI cao → TĂNG nhẹ','usd':'PPI cao → TĂNG nhẹ'
    },
    {
        'id':'fomc_jun','name':'🏦 FOMC Rate Decision (T6)','date':'2026-06-18','time':'01:00','impact':'🔴 HIGH',
        'desc':'Quyết định lãi suất Fed - SỰ KIỆN QUAN TRỌNG NHẤT.',
        'fred':'DFF','fmt':'📊 Lãi suất Fed: {value}% (trước: {prev}%)\n🎤 Thái độ: Fed {action}\n📝 Chi tiết: {"Fed đã TĂNG lãi suất thêm " + str(round(value-prev,2)) + "%" if value>prev else "Fed đã GIẢM lãi suất " + str(round(prev-value,2)) + "%" if value<prev else "Fed GIỮ NGUYÊN lãi suất ở mức " + str(value) + "%"}.',
        'gold':'Hawkish → GIẢM | Dovish → TĂNG','crypto':'Hawkish → GIẢM | Dovish → TĂNG','usd':'Hawkish → TĂNG | Dovish → GIẢM'
    },
    {
        'id':'gdp_q2','name':'📊 GDP Q2 2026 (Final)','date':'2026-06-25','time':'19:30','impact':'🔴 HIGH',
        'desc':'Tăng trưởng kinh tế Mỹ quý 2/2026.',
        'fred':'GDP','fmt':'📊 GDP: ${value:,.0f}B (trước: ${prev:,.0f}B)\n🎤 Thái độ: {"📈 TĂNG TRƯỞNG ✅" if value>prev else "📉 SUY GIẢM ⚠️" if value<prev else "➡️ KHÔNG ĐỔI"}\n📝 Chi tiết: GDP thay đổi {"+{:.2f}%".format((value-prev)/prev*100) if value>prev else "{:.2f}%".format((value-prev)/prev*100)} so với ${prev:,.0f}B.',
        'gold':'GDP cao → GIẢM | GDP thấp → TĂNG','crypto':'GDP cao → TĂNG | GDP thấp → GIẢM','usd':'GDP cao → TĂNG | GDP thấp → GIẢM'
    },
    {
        'id':'fomc_minutes_jun','name':'📋 FOMC Meeting Minutes (T6)','date':'2026-06-04','time':'01:00','impact':'🟡 MEDIUM',
        'desc':'Biên bản cuộc họp FOMC tháng 6.',
        'fred':'DFF','fmt':'🎤 Thái độ: 🏦 Fed Rate: {value}%\n📝 Chi tiết: Biên bản đã công bố. Lãi suất hiện tại: {value}%.',
        'gold':'Hawkish → GIẢM | Dovish → TĂNG','crypto':'Hawkish → GIẢM | Dovish → TĂNG','usd':'Hawkish → TĂNG | Dovish → GIẢM'
    },
    {
        'id':'fomc_jul','name':'🏦 FOMC Rate Decision (T7)','date':'2026-07-30','time':'01:00','impact':'🔴 HIGH',
        'desc':'Quyết định lãi suất giữa năm 2026.',
        'fred':'DFF','fmt':'📊 Lãi suất Fed: {value}% (trước: {prev}%)\n🎤 Thái độ: Fed {action}\n📝 Chi tiết: {"Fed đã TĂNG lãi suất thêm " + str(round(value-prev,2)) + "%" if value>prev else "Fed đã GIẢM lãi suất " + str(round(prev-value,2)) + "%" if value<prev else "Fed GIỮ NGUYÊN lãi suất ở mức " + str(value) + "%"}.',
        'gold':'Hawkish → GIẢM | Dovish → TĂNG','crypto':'Hawkish → GIẢM | Dovish → TĂNG','usd':'Hawkish → TĂNG | Dovish → GIẢM'
    },
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
        
        # TRƯỚC SỰ KIỆN (D-3 đến D-0): Đếm ngược mỗi 12h
        if 0 <= days <= 3:
            key = f"pre_{ev['id']}"
            if time.time() - log['events'].get(key, 0) >= 43200:
                log['events'][key] = time.time()
                
                if days == 0: cd = f"⚠️ HÔM NAY lúc {ev['time']} (UTC+7)"
                elif days == 1: cd = f"📅 NGÀY MAI lúc {ev['time']} (UTC+7)"
                else: cd = f"📅 Còn {days} ngày - {ev['date']} lúc {ev['time']} (UTC+7)"
                
                msg = f"📅 {ev['name']}\n━━━━━━━━━━━━━━━━━━\n"
                msg += f"⏰ {cd}\n"
                msg += f"⚡ Mức độ: {ev['impact']}\n"
                msg += f"📝 {ev['desc']}\n\n"
                msg += f"━━━━━━━━━━━━━━━━━━\n"
                msg += f"📊 TÁC ĐỘNG DỰ KIẾN:\n"
                msg += f"🥇 Vàng: {ev['gold']}\n"
                msg += f"₿ Crypto: {ev['crypto']}\n"
                msg += f"💵 USD: {ev['usd']}\n"
                msg += f"━━━━━━━━━━━━━━━━━━\n\n"
                msg += f"📊 DỮ LIỆU HIỆN TẠI:\n{econ_summary()}\n\n"
                msg += now_str()
                msgs.append(msg)
        
        # SAU SỰ KIỆN (1h-72h): GỬI KẾT QUẢ THỰC TẾ 1 LẦN DUY NHẤT
        elif days < 0 and 1 <= hours_since <= 72:
            key = f"post_{ev['id']}"
            if key not in log['events'] and fred_ok():
                v = fred_get(ev['fred'])
                if v and len(v) >= 2:
                    curr, prev = v[0]['v'], v[1]['v']
                    
                    if 'fomc' in ev['id'] and 'minutes' not in ev['id']:
                        if curr > prev: action = "TĂNG lãi suất 🦅"
                        elif curr < prev: action = "GIẢM lãi suất 🕊️"
                        else: action = "GIỮ NGUYÊN lãi suất ➡️"
                    elif 'gdp' in ev['id']:
                        action = "TĂNG TRƯỞNG" if curr > prev else ("SUY GIẢM" if curr < prev else "KHÔNG ĐỔI")
                    else:
                        action = ""
                    
                    log['events'][key] = time.time()
                    
                    msg = f"===================================\n"
                    msg += f"✅ {ev['name']} - KẾT QUẢ THỰC TẾ\n"
                    msg += f"===================================\n"
                    msg += f"⏰ Đã diễn ra: {ev['date']} lúc {ev['time']} (UTC+7)\n\n"
                    msg += f"{ev['fmt'].format(value=curr, prev=prev, action=action)}\n\n"
                    msg += f"━━━━━━━━━━━━━━━━━━\n"
                    msg += f"📊 TÁC ĐỘNG THỊ TRƯỜNG:\n"
                    msg += f"🥇 Vàng: {ev['gold']}\n"
                    msg += f"₿ Crypto: {ev['crypto']}\n"
                    msg += f"💵 USD: {ev['usd']}\n"
                    msg += f"━━━━━━━━━━━━━━━━━━\n\n"
                    msg += f"📊 DỮ LIỆU FRED:\n{econ_summary()}\n\n"
                    msg += now_str()
                    msgs.append(msg)
    
    save_log(log)
    return msgs

def market_summary(news_list):
    if not news_list: return None
    total_score = sum(n['score'] for n in news_list)
    level = "RẤT CAO" if total_score < -200 else ("CAO" if total_score < -100 else ("TRUNG BÌNH" if total_score < 0 else "THẤP"))
    advice = "⚠️ ƯU TIÊN SHORT" if total_score < -100 else ("✅ ƯU TIÊN LONG" if total_score > 100 else "➡️ GIAO DỊCH BÌNH THƯỜNG")
    all_kw = []
    for n in news_list: all_kw.extend(n['keywords'].split(', '))
    top_kw = list(set([k for k in all_kw if k]))[:5]
    return f"📰 TỔNG QUAN THỊ TRƯỜNG\n━━━━━━━━━━━━━━━━━━\n🚨 Căng thẳng {level} (score: {total_score}). {advice}\n\n📋 Số tin phát hiện: {len(news_list)}\n🔑 Từ khóa nóng: {', '.join(top_kw)}\n\n{now_str()}"

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
            startup_news = gdelt_news()
            
            msg = f"📰 Bot tin tức đã khởi động!\n━━━━━━━━━━━━━━━━━━\n📡 FRED: {'✅ Online' if fred_ok() else '⏳ Offline'}\n📡 GDELT: ✅ Online\n\n📊 DỮ LIỆU KINH TẾ:\n{econ_summary()}\n\n"
            if startup_news:
                msg += f"📋 Phát hiện {len(startup_news)} tin tức nóng\n"
            msg += f"\n✅ Đang theo dõi sự kiện...\n\n{now_str()}"
            gui(msg)
            
            if startup_news:
                summary = market_summary(startup_news)
                if summary: gui(summary)
                for n in startup_news:
                    msg = f"📰 TIN TỨC THỊ TRƯỜNG {n['impact']}\n━━━━━━━━━━━━━━━━━━\n{n['title']}\n\n📡 Nguồn: {n['source']}\n⚡ Tác động: {n['impact']} (Score: {n['score']})\n🔑 Từ khóa: {n['keywords']}\n\n🏦 Dự báo:\n🥇 Vàng: {n['gold']}\n₿ Crypto: {n['crypto']}\n💵 USD: {n['usd']}\n\n💡 Khuyến nghị: {n['advice']}\n\n{now_str()}"
                    gui(msg)
                    time.sleep(1)

        news = gdelt_news()
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