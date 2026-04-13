import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import yfinance as yf
import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import io

# --- [1. 설정 및 경로] ---
st.set_page_config(page_title="내 퀀트 포트폴리오", layout="wide")

PORT_PATHS = {
    "ddo": 'data/port_ddo.csv',
    "sso": 'data/port_sso.csv',
    "mom": 'data/port_mom.csv'
}
MASTER_TICKER_PATH = 'data/krx_stock_master.csv'
CONFIG_PATH = 'data/portfolio_config.json' 
FACE_VALUE_PATH = 'data/krx_stock_info.csv' 

if not os.path.exists('data'):
    os.makedirs('data')

st.markdown("""
    <style>
    .block-container { padding-top: 2.5rem !important; }
    .main-title { font-size: 1.8rem !important; font-weight: bold; margin-bottom: 1.5rem; }
    .section-title { font-size: 1.6rem !important; font-weight: bold; margin-top: 25px; margin-bottom: 15px; color: #E5E7EB; }
    .stMetric { background-color: rgba(130, 130, 130, 0.1); padding: 15px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.05); }
    .stTabs [data-baseweb="tab"] { font-size: 18px; font-weight: bold; }
    
    @media (max-width: 768px) {
        div[data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
            min-width: 45% !important; flex: 1 1 45% !important; margin-bottom: 10px !important;
        }
    }
    
    /* 📊 종합 요약 표 디자인 */
    .summary-table { width: 100%; border-collapse: collapse; text-align: center; font-size: 1.15rem; background-color: #1a1c24; border-radius: 12px; overflow: hidden; margin-top: 10px; }
    .summary-table th { background-color: #2d313e; padding: 15px; color: #9ca3af; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px; }
    .summary-table td { padding: 16px; border-bottom: 1px solid #2d313e; color: #e5e7eb; }
    .highlight-cell { background-color: rgba(255, 255, 255, 0.03); font-size: 1.2rem; }
    .summary-total { background-color: #242834; font-size: 1.3rem; }
    
    /* 💡 [신규] 설정 저장 버튼 정사각형 및 위치 맞춤 */
    div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button {
        height: 68px;
        margin-top: 28px;
        white-space: pre-wrap;
        line-height: 1.4;
        font-size: 1.05rem;
    }
    
    /* 숫자 색상 */
    .val-red-thin { color: #FF3333 !important; font-weight: 500; }
    .val-blue-thin { color: #3399FF !important; font-weight: 500; }
    .val-red { color: #FF3333 !important; font-weight: bold; }
    .val-blue { color: #3399FF !important; font-weight: bold; }
    .val-white { color: #ffffff !important; font-weight: bold; }
    .val-gray { color: #9ca3af !important; font-weight: normal !important; }
    
    /* 시작일 기준 수익 강조 박스 */
    .box-red { background-color: rgba(255, 51, 51, 0.15); color: #FF3333; padding: 6px 14px; border-radius: 8px; border: 1px solid rgba(255, 51, 51, 0.3); font-weight: bold;}
    .box-blue { background-color: rgba(51, 153, 255, 0.15); color: #3399FF; padding: 6px 14px; border-radius: 8px; border: 1px solid rgba(51, 153, 255, 0.3); font-weight: bold;}
    </style>
""", unsafe_allow_html=True)

# --- [2. 설정 관리] ---
def load_config():
    default_config = {"start_date": str(datetime.today().date()), "start_ddo": 0, "start_sso": 0, "start_mom": 0}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f: 
                saved = json.load(f)
                for k in default_config.keys():
                    if k in saved: default_config[k] = saved[k]
                return default_config
        except: pass
    return default_config

def save_config(config_data):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f: json.dump(config_data, f)

def parse_krw(val_str, default_val):
    try:
        if isinstance(val_str, str):
            return int(val_str.replace(',', '').replace('₩', '').strip())
        return int(val_str)
    except:
        return default_val

if 'portfolio_config' not in st.session_state:
    st.session_state['portfolio_config'] = load_config()

# --- [3. 데이터 수집 로직] ---

@st.cache_data(ttl=86400, show_spinner=False)
def get_face_value_map():
    fv_map = {}
    if os.path.exists(FACE_VALUE_PATH):
        for enc in ['utf-8-sig', 'cp949', 'euc-kr', 'utf-8']:
            try:
                df = pd.read_csv(FACE_VALUE_PATH, dtype={'단축코드': str}, encoding=enc)
                if '단축코드' in df.columns and '액면가' in df.columns:
                    df['단축코드'] = df['단축코드'].astype(str).str.zfill(6)
                    df['액면가'] = pd.to_numeric(df['액면가'].astype(str).str.replace(r'[^0-9.]', '', regex=True), errors='coerce').fillna(0)
                    fv_map = df.set_index('단축코드')['액면가'].to_dict()
                    break
            except: continue
    return fv_map

global_fv_map = get_face_value_map()

@st.cache_data(ttl=86400, show_spinner=False)
def get_stock_master_and_cap():
    master_df = pd.DataFrame(columns=['종목코드', '종목명', '시장구분', '시가총액(억)'])
    cap_map = {}
    if os.path.exists(MASTER_TICKER_PATH):
        for enc in ['utf-8-sig', 'cp949', 'euc-kr', 'utf-8']:
            try:
                df = pd.read_csv(MASTER_TICKER_PATH, dtype={'종목코드': str}, encoding=enc)
                if '종목코드' in df.columns:
                    df['종목코드'] = df['종목코드'].astype(str).str.zfill(6)
                    if '시가총액(억)' in df.columns:
                        df['시가총액(억)'] = pd.to_numeric(df['시가총액(억)'].astype(str).str.replace(r'[^0-9.]', '', regex=True), errors='coerce').fillna(0).astype(int)
                        cap_map = df.set_index('종목코드')['시가총액(억)'].to_dict()
                    master_df = df
                    break
            except: continue
    return master_df, cap_map

master_df, global_cap_map = get_stock_master_and_cap()
if not master_df.empty:
    master_df['검색명'] = "[" + master_df['종목코드'] + "] " + master_df.get('종목명', master_df['종목코드'])
search_options = ["🔍 종목 검색"] + master_df['검색명'].tolist() if not master_df.empty else ["검색 데이터 없음"]

@st.cache_data(ttl=60, show_spinner=False)
def fetch_multi_prices(tickers):
    if not tickers: return {}
    price_map = {}
    def get_price(t):
        curr_val, prev_val = 0, 0
        code_str = str(t).zfill(6) if str(t).isdigit() else str(t)
        try:
            df = fdr.DataReader(code_str, datetime.today() - timedelta(days=15))
            if not df.empty:
                curr_val = int(df['Close'].iloc[-1])
                prev_val = int(df['Close'].iloc[-2]) if len(df) >= 2 else curr_val
        except: pass
        if curr_val == 0:
            try:
                yf_t = code_str + (".KS" if code_str.isdigit() else "")
                hist = yf.Ticker(yf_t).history(period="5d")
                if not hist.empty:
                    curr_val = int(hist['Close'].iloc[-1])
                    prev_val = int(hist['Close'].iloc[-2]) if len(hist) >= 2 else curr_val
            except: pass
        return t, curr_val, prev_val

    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = [executor.submit(get_price, t) for t in tickers]
        for f in as_completed(futures):
            t, curr, prev = f.result()
            price_map[t] = {'curr': curr, 'prev': prev}
    return price_map

def load_portfolio(path):
    if os.path.exists(path):
        for enc in ['utf-8-sig', 'cp949', 'euc-kr', 'utf-8']:
            try:
                df = pd.read_csv(path, dtype={'종목코드': str}, encoding=enc)
                df = df.dropna(subset=['종목코드'])
                df['종목코드'] = df['종목코드'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(6)
                if '종목명' not in df.columns:
                    name_map = master_df.set_index('종목코드')['종목명'].to_dict() if not master_df.empty else {}
                    df['종목명'] = df['종목코드'].map(name_map).fillna('이름없음')
                for c in ['매수단가', '수량']:
                    if c in df.columns: df[c] = pd.to_numeric(df[c].astype(str).str.replace(r'[^0-9.]', '', regex=True), errors='coerce').fillna(0).astype(int)
                    else: df[c] = 0
                return df[["종목명", "종목코드", "매수단가", "수량"]]
            except: continue
    return pd.DataFrame(columns=["종목명", "종목코드", "매수단가", "수량"])

for p_key, path in [("ddo", PORT_PATHS["ddo"]), ("sso", PORT_PATHS["sso"]), ("mom", PORT_PATHS["mom"])]:
    if f'df_{p_key}' not in st.session_state:
        st.session_state[f'df_{p_key}'] = load_portfolio(path)

all_tickers = set()
for p_key in ["ddo", "sso", "mom"]:
    all_tickers.update(st.session_state[f'df_{p_key}']['종목코드'].tolist())
global_prices = fetch_multi_prices(tuple(sorted(all_tickers)))

# --- [4. 개별 포트폴리오 탭 렌더링] ---
def render_portfolio_tab(port_name, port_key, path, prices):
    scoreboard_placeholder = st.container()
    st.markdown("---")
    
    col_add, col_file = st.columns([1.5, 1])
    with col_add:
        with st.expander(f"➕ {port_name} 종목 추가", expanded=False):
            with st.form(f"add_{port_key}", clear_on_submit=True):
                sel = st.selectbox("종목 검색", options=search_options, key=f"sel_{port_key}")
                c1, c2 = st.columns(2)
                p = c1.number_input("매수단가", min_value=0, step=100, key=f"p_{port_key}")
                q = c2.number_input("수량", min_value=1, step=1, key=f"q_{port_key}")
                if st.form_submit_button("추가"):
                    if sel and sel != search_options[0]:
                        code, name = sel[1:7], sel[9:]
                        new_row = pd.DataFrame([{"종목명": name, "종목코드": code, "매수단가": int(p), "수량": int(q)}])
                        st.session_state[f'df_{port_key}'] = pd.concat([st.session_state[f'df_{port_key}'], new_row], ignore_index=True)
                        # 💡 행 추가 시에도 인덱스 1부터 재정렬
                        st.session_state[f'df_{port_key}'].index = range(1, len(st.session_state[f'df_{port_key}']) + 1)
                        st.session_state[f'df_{port_key}'].to_csv(path, index=False, encoding='utf-8-sig')
                        st.rerun()
    with col_file:
        with st.expander("📂 엑셀 업로드", expanded=False):
            up_file = st.file_uploader("CSV/XLSX", type=['csv', 'xlsx'], key=f"up_{port_key}")
            if up_file and st.button("반영", key=f"btn_{port_key}"):
                try:
                    up_file.seek(0)
                    up_df = pd.read_csv(up_file, encoding='utf-8-sig') if up_file.name.endswith('csv') else pd.read_excel(up_file)
                    up_df.columns = up_df.columns.str.strip()
                    up_df['종목코드'] = up_df['종목코드'].astype(str).str.zfill(6)
                    st.session_state[f'df_{port_key}'] = up_df
                    # 💡 파일 업로드 시에도 인덱스 1부터 재정렬
                    st.session_state[f'df_{port_key}'].index = range(1, len(st.session_state[f'df_{port_key}']) + 1)
                    st.session_state[f'df_{port_key}'].to_csv(path, index=False, encoding='utf-8-sig')
                    st.rerun()
                except: st.error("파일 오류")

    st.markdown(f"### 📝 {port_name} 편집")
    
    # 💡 [업데이트] 데이터 에디터에 넘기기 직전에 인덱스를 1부터 시작하도록 설정
    st.session_state[f'df_{port_key}'].index = range(1, len(st.session_state[f'df_{port_key}']) + 1)
    df_editor = st.data_editor(st.session_state[f'df_{port_key}'], num_rows="dynamic", use_container_width=True, key=f"ed_{port_key}")
    
    if st.button("저장", key=f"sv_{port_key}"):
        df_editor.index = range(1, len(df_editor) + 1) # 저장할 때도 1번부터 정리
        st.session_state[f'df_{port_key}'] = df_editor
        st.session_state[f'df_{port_key}'].to_csv(path, index=False, encoding='utf-8-sig')
        st.rerun()

    with scoreboard_placeholder:
        st.markdown(f"### 🚀 {port_name} 실시간 성적표")
        df = st.session_state[f'df_{port_key}'].copy()
        if not df.empty:
            df['시총(억)'] = df['종목코드'].map(global_cap_map).fillna(0)
            df['액면가'] = df['종목코드'].map(global_fv_map).fillna(0)
            df['현재가'] = df['종목코드'].apply(lambda x: prices.get(x, {}).get('curr', 0))
            df['전일종가'] = df['종목코드'].apply(lambda x: prices.get(x, {}).get('prev', 0))
            
            df['전일대비(%)'] = df.apply(lambda r: ((r['현재가'] - r['전일종가']) / r['전일종가'] * 100) if r['전일종가'] > 0 else 0, axis=1)
            df['평가금액'] = df['현재가'] * df['수량']
            df['평가손익'] = (df['현재가'] - df['매수단가']) * df['수량']
            df['수익률(%)'] = df.apply(lambda r: (r['평가손익'] / (r['매수단가'] * r['수량']) * 100) if (r['매수단가'] * r['수량']) > 0 else 0, axis=1)
            
            t_buy = (df['매수단가']*df['수량']).sum()
            t_val = df['평가금액'].sum()
            t_profit = df['평가손익'].sum()
            t_prev_val = (df['전일종가']*df['수량']).sum()
            d_diff = t_val - t_prev_val
            d_pct = (d_diff / t_prev_val * 100) if t_prev_val > 0 else 0
            
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("💰 총 매수", f"{int(t_buy):,}원")
            c2.metric("📈 총 평가액", f"{int(t_val):,}원")
            c3.metric("🌟 오늘 변동액", f"{int(d_diff):,}원", delta=f"{d_pct:.2f}%")
            c4.metric("💸 총 평가손익", f"{int(t_profit):,}원", delta=f"{int(t_profit):,}원")
            c5.metric("📊 총 수익률", f"{(t_profit/t_buy*100) if t_buy > 0 else 0:.2f}%", delta=f"{(t_profit/t_buy*100) if t_buy > 0 else 0:.2f}%")
            
            def make_links(r):
                market_val = str(r.get('시장구분', ''))
                m = "KOSDAQ" if "코스닥" in market_val or "KOSDAQ" in market_val.upper() else "KOSPI"
                t_url = f"https://finance.naver.com/item/main.naver?code={r['종목코드']}#{m}:{r['종목코드']}"
                n_url = f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드']}#{r['종목명']}"
                return pd.Series([t_url, n_url])
            
            df[['티커_L', '종목명_L']] = df.apply(make_links, axis=1)

            def style_port_final(st_df):
                s = pd.DataFrame('', index=st_df.index, columns=st_df.columns)
                for col in ['전일대비(%)', '평가손익', '수익률(%)']:
                    s[col] = st_df[col].apply(lambda x: 'color: #FF3333; font-weight:bold;' if x > 0 else ('color: #3399FF; font-weight:bold;' if x < 0 else ''))
                
                highlight_css = 'background-color: rgba(255, 167, 38, 0.1); color: #FFA726; border: 1px solid #FFA726; font-weight:bold; border-radius: 4px;'
                warning_css = 'background-color: rgba(255, 0, 0, 0.2); color: #FF3333; border: 2px solid #FF3333; font-weight:bold; border-radius: 4px;'
                
                if '시총(억)' in st_df.columns:
                    s['시총(억)'] = st_df['시총(억)'].apply(lambda x: highlight_css if 0 < x <= 150 else '')
                
                for i, row in st_df.iterrows():
                    if row['액면가'] > 0 and row['현재가'] < row['액면가']:
                        s.loc[i, '현재가'] = warning_css
                        s.loc[i, '액면가'] = warning_css
                    elif 0 < row['현재가'] < 1000:
                        s.loc[i, '현재가'] = highlight_css
                    
                return s

            st.dataframe(df.style.apply(style_port_final, axis=None).format({'전일대비(%)':'{:.2f}%','수익률(%)':'{:.2f}%','시총(억)':'{:,}','매수단가':'{:,}','액면가':'{:,}','현재가':'{:,}','평가금액':'{:,}','평가손익':'{:,}'}), 
                         use_container_width=True, hide_index=True,
                         column_order=['티커_L', '종목명_L', '시총(억)', '수량', '매수단가', '액면가', '현재가', '전일대비(%)', '평가금액', '평가손익', '수익률(%)'],
                         column_config={
                             "티커_L": st.column_config.LinkColumn("코드", display_text=r"#(.+)"),
                             "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)")
                         })

# =========================================================
# 🚀 메인 대시보드
# =========================================================
st.markdown('<p class="main-title">💼 내 퀀트 포트폴리오 종합 대시보드</p>', unsafe_allow_html=True)
tabs = st.tabs(["📊 종합 요약", "🌱 또", "🌿 쏘", "🍀 맘", "⚖️ 리밸런싱 계산기"])

with tabs[0]:
    config = st.session_state['portfolio_config']
    
    total_start_sum = config.get('start_ddo', 0) + config.get('start_sso', 0) + config.get('start_mom', 0)
    try:
        dt_obj = datetime.strptime(config['start_date'], '%Y-%m-%d')
        display_date_str = f"{dt_obj.strftime('%y')}년 {dt_obj.month}월 {dt_obj.day}일"
    except:
        display_date_str = config['start_date']
        
    st.markdown(f"##### ⚙️ 비교 시점 및 시작 수익금 설정 <span style='font-size: 1rem; color: #9ca3af; font-weight: normal; margin-left: 10px;'>(기준일 : {display_date_str}, 총 시작금 : {total_start_sum:,}원)</span>", unsafe_allow_html=True)
    
    with st.form("config_form"):
        # 💡 [업데이트] 버튼을 넣기 위해 컬럼을 5개로 쪼개고 버튼을 오른쪽에 배치
        c_dt, c_d, c_s, c_m, c_btn = st.columns([1.2, 1, 1, 1, 0.7])
        try: dt_val = datetime.strptime(config['start_date'], '%Y-%m-%d').date()
        except: dt_val = datetime.today().date()
        
        with c_dt: new_date = st.date_input("📅 시작일", value=dt_val)
        with c_d: str_ddo = st.text_input("💰 [또] 시작금", value=f"{config['start_ddo']:,}")
        with c_s: str_sso = st.text_input("💰 [쏘] 시작금", value=f"{config['start_sso']:,}")
        with c_m: str_mom = st.text_input("💰 [맘] 시작금", value=f"{config['start_mom']:,}")
        
        with c_btn:
            # 💡 [업데이트] 줄바꿈 기호(\n)를 사용해 버튼 글씨를 두 줄로 만듭니다.
            submitted = st.form_submit_button("설정\n저장", use_container_width=True)
        
        if submitted:
            new_ddo = parse_krw(str_ddo, config['start_ddo'])
            new_sso = parse_krw(str_sso, config['start_sso'])
            new_mom = parse_krw(str_mom, config['start_mom'])
            
            new_config = {"start_date": str(new_date), "start_ddo": new_ddo, "start_sso": new_sso, "start_mom": new_mom}
            st.session_state['portfolio_config'] = new_config
            save_config(new_config)
            st.rerun()

    st.markdown('<p class="section-title">🏆 포트폴리오 성과 요약</p>', unsafe_allow_html=True)
    
    summary_data, total_buy, total_profit, total_daily, total_since, total_prev_all = [], 0, 0, 0, 0, 0

    for p_name, p_key in [("또", "ddo"), ("쏘", "sso"), ("맘", "mom")]:
        df = st.session_state[f'df_{p_key}']
        start_val = config[f'start_{p_key}']
        if not df.empty:
            df['curr'] = df['종목코드'].apply(lambda x: global_prices.get(x, {}).get('curr', 0))
            df['prev'] = df['종목코드'].apply(lambda x: global_prices.get(x, {}).get('prev', 0))
            t_buy = (df['매수단가'] * df['수량']).sum()
            t_val = (df['curr'] * df['수량']).sum()
            t_prev = (df['prev'] * df['수량']).sum()
            t_profit = t_val - t_buy
            d_diff = t_val - t_prev
            d_pct = (d_diff / t_prev * 100) if t_prev > 0 else 0
            since_start = t_profit - start_val
            
            total_buy += t_buy; total_profit += t_profit; total_daily += d_diff; total_since += since_start; total_prev_all += t_prev
            summary_data.append({"name": p_name, "daily": d_diff, "daily_pct": d_pct, "pct": (t_profit/t_buy*100), "profit": t_profit, "since": since_start})
        else:
            summary_data.append({"name": p_name, "daily": 0, "daily_pct": 0, "pct": 0, "profit": 0, "since": -start_val})
            total_since -= start_val

    total_since_color = "#FF3333" if total_since >= 0 else "#3399FF"
    html = f"<table class='summary-table'><thead><tr><th>포트폴리오</th><th>오늘의 등락</th><th>오늘의 등락률</th><th>총 수익률</th><th>현재 수익 금액</th><th style='color:#ffffff; background-color:#3e4452;'>시작일 기준 수익 금액</th></tr></thead><tbody>"
    
    def get_thin_cls(v):
        if v > 0: return "val-red-thin"
        elif v < 0: return "val-blue-thin"
        return "val-gray"

    def get_cls(v, is_box=False):
        cls = "val-red" if v > 0 else ("val-blue" if v < 0 else "val-gray")
        if is_box and v != 0: return f"box-red" if v > 0 else "box-blue"
        return cls

    for r in summary_data:
        box_cls = get_cls(r['since'], True)
        html += f"<tr><td><b>{r['name']}</b></td>"
        html += f"<td class='{get_thin_cls(r['daily'])}'>₩{int(r['daily']):,}</td>"
        html += f"<td class='{get_thin_cls(r['daily_pct'])}'>{r['daily_pct']:.2f}%</td>"
        html += f"<td class='{get_cls(r['pct'])}'>{r['pct']:.2f}%</td>"
        html += f"<td class='{get_cls(r['profit'])}'>₩{int(r['profit']):,}</td>"
        html += f"<td class='highlight-cell'><span class='{box_cls}'>₩{int(r['since']):,}</span></td></tr>"

    total_daily_pct_all = (total_daily / total_prev_all * 100) if total_prev_all > 0 else 0
    html += f"<tr class='summary-total' style='border-top: 2px solid {total_since_color};'><td><b>합계</b></td>"
    html += f"<td class='{get_thin_cls(total_daily)}'>₩{int(total_daily):,}</td>"
    html += f"<td class='{get_thin_cls(total_daily_pct_all)}'>{total_daily_pct_all:.2f}%</td>"
    html += f"<td class='val-white'><b>{total_profit/total_buy*100 if total_buy>0 else 0:.2f}%</b></td>"
    html += f"<td class='{get_cls(total_profit)}'><b>₩{int(total_profit):,}</b></td>"
    html += f"<td class='highlight-cell'><span style='font-size:1.4rem;' class='{get_cls(total_since, True)}'>₩{int(total_since):,}</span></td></tr>"
    html += "</tbody></table>"
    st.markdown(html, unsafe_allow_html=True)

with tabs[1]: render_portfolio_tab("또", "ddo", PORT_PATHS["ddo"], global_prices)
with tabs[2]: render_portfolio_tab("쏘", "sso", PORT_PATHS["sso"], global_prices)
with tabs[3]: render_portfolio_tab("맘", "mom", PORT_PATHS["mom"], global_prices)

with tabs[4]:
    st.markdown('<p class="section-title">⚖️ 포트폴리오 교체/리밸런싱 계산기</p>', unsafe_allow_html=True)
    st.info("현재 보유 중인 포트폴리오를 기준으로, 새롭게 설정할 '목표 포트폴리오(엑셀/CSV)'를 업로드하면 최적의 매수/매도 주문 수량을 자동으로 계산해 드립니다.")
    
    c_sel, c_up = st.columns([1, 2])
    target_port_info = c_sel.selectbox("🔄 기준 포트폴리오 선택", options=[("또", "ddo"), ("쏘", "sso"), ("맘", "mom")], format_func=lambda x: f"[{x[0]}] 포트폴리오 기준")
    
    up_target = c_up.file_uploader("목표 엑셀/CSV 업로드 양식 (필수 열: '코드번호 (A포함)', '목표금액(100만원 단위)')", type=['csv', 'xlsx'], key="up_rebal")
    
    if up_target:
        try:
            up_target.seek(0)
            tgt_df = pd.read_csv(up_target, encoding='utf-8-sig') if up_target.name.endswith('csv') else pd.read_excel(up_target)
            tgt_df.columns = tgt_df.columns.str.strip()
            
            code_col = [col for col in tgt_df.columns if '코드번호' in col]
            target_col = [col for col in tgt_df.columns if '목표금액' in col]
            
            if not code_col or not target_col:
                st.error("🚨 업로드하신 파일 첫 줄에 '코드번호'와 '목표금액'이라는 이름의 열(컬럼)이 반드시 포함되어야 합니다!")
            else:
                code_col = code_col[0]
                target_col = target_col[0]
                
                tgt_df = tgt_df.dropna(subset=[code_col])
                
                tgt_df['종목코드'] = tgt_df[code_col].astype(str).str.replace(r'^[A-Za-z]+', '', regex=True).str.replace(r'\.0$', '', regex=True).str.zfill(6)
                tgt_df['목표금액'] = pd.to_numeric(tgt_df[target_col].astype(str).str.replace(r'[^0-9.]', '', regex=True), errors='coerce').fillna(0).astype(int) * 10000
                
                curr_df = st.session_state[f'df_{target_port_info[1]}'].copy()
                
                merged = pd.merge(curr_df[['종목코드', '수량']], tgt_df[['종목코드', '목표금액']], on='종목코드', how='outer')
                merged['수량'] = merged['수량'].fillna(0).astype(int)
                merged['목표금액'] = merged['목표금액'].fillna(0).astype(int)
                
                merged['시총(억)'] = merged['종목코드'].map(global_cap_map).fillna(0)
                merged['액면가'] = merged['종목코드'].map(global_fv_map).fillna(0)
                
                name_map = master_df.set_index('종목코드')['종목명'].to_dict() if not master_df.empty else {}
                merged['종목명'] = merged['종목코드'].map(name_map).fillna('이름없음')
                
                reb_tickers = tuple(merged['종목코드'].unique())
                reb_prices = fetch_multi_prices(reb_tickers)
                
                merged['현재가'] = merged['종목코드'].apply(lambda x: reb_prices.get(x, {}).get('curr', 0))
                merged['현재평가금액'] = merged['수량'] * merged['현재가']
                merged['차액'] = merged['목표금액'] - merged['현재평가금액']
                
                def get_rebal_action(row):
                    if row['목표금액'] == 0 and row['수량'] > 0: return "전량매도"
                    if row['수량'] == 0 and row['목표금액'] > 0: return "신규매수"
                    if row['차액'] > 0: return "추가매수"
                    if row['차액'] < 0: return "부분매도"
                    return "유지"
                    
                merged['주문'] = merged.apply(get_rebal_action, axis=1)
                
                def get_rebal_qty(row):
                    if row['현재가'] == 0: return 0
                    if row['주문'] == "전량매도": return row['수량']
                    return int(abs(row['차액']) // row['현재가'])
                    
                merged['주문수량'] = merged.apply(get_rebal_qty, axis=1)
                
                def get_signed_amount(row):
                    val = row['주문수량'] * row['현재가']
                    if row['주문'] in ["신규매수", "추가매수"]: return val
                    if row['주문'] in ["전량매도", "부분매도"]: return -val
                    return 0
                    
                merged['예상체결금액'] = merged.apply(get_signed_amount, axis=1)
                
                merged = merged[(merged['수량'] > 0) | (merged['목표금액'] > 0)]
                merged = merged.sort_values(by='종목명', ascending=True)
                
                buy_sum = merged[merged['예상체결금액'] > 0]['예상체결금액'].sum()
                sell_sum = merged[merged['예상체결금액'] < 0]['예상체결금액'].abs().sum()
                net_cash = sell_sum - buy_sum
                
                if net_cash >= 0:
                    net_css = "color: #FF3333; font-size: 1.25rem; padding: 2px 10px; margin-left: 5px; background-color: rgba(255, 51, 51, 0.15); border-radius: 6px;"
                    net_text = f"₩{net_cash:,} 잔금"
                else:
                    net_css = "color: #3399FF; font-size: 1.25rem; padding: 2px 10px; margin-left: 5px; background-color: rgba(51, 153, 255, 0.15); border-radius: 6px;"
                    net_text = f"₩{abs(net_cash):,} 추가 투자 필요"
                
                col_header, col_btn = st.columns([5, 1])
                
                with col_header:
                    st.markdown(f"**🔵 총 매도 확보 자금:** `₩{sell_sum:,}` &nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp; **🔴 총 예상 매수 자금:** `₩{buy_sum:,}` &nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp; **💡 리밸런싱 후 잔액:** <span style='{net_css}'>**{net_text}**</span>", unsafe_allow_html=True)
                
                display_reb = merged[['종목코드', '종목명', '시총(억)', '현재가', '액면가', '수량', '현재평가금액', '목표금액', '주문', '주문수량', '예상체결금액']]
                
                with col_btn:
                    csv_data = display_reb.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label="📥 결과 다운로드 (CSV)",
                        data=csv_data,
                        file_name=f"리밸런싱결과_{datetime.today().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                
                def style_rebal(st_df):
                    s = pd.DataFrame('', index=st_df.index, columns=st_df.columns)
                    
                    highlight_css = 'background-color: rgba(255, 167, 38, 0.1); color: #FFA726; border: 1px solid #FFA726; font-weight:bold; border-radius: 4px;'
                    warning_css = 'background-color: rgba(255, 0, 0, 0.2); color: #FF3333; border: 2px solid #FF3333; font-weight:bold; border-radius: 4px;'
                    
                    if '시총(억)' in st_df.columns:
                        s['시총(억)'] = st_df['시총(억)'].apply(lambda x: highlight_css if 0 < x <= 150 else '')
                    
                    for i, row in st_df.iterrows():
                        if row['주문'] in ["신규매수", "추가매수"]:
                            s.loc[i, '주문'] = 'color: #FF3333; font-weight: bold; background-color: rgba(255,51,51,0.1);'
                            s.loc[i, '주문수량'] = 'color: #FF3333; font-weight: bold;'
                            s.loc[i, '예상체결금액'] = 'color: #FF3333; font-weight: bold;'
                        elif row['주문'] in ["전량매도", "부분매도"]:
                            s.loc[i, '주문'] = 'color: #3399FF; font-weight: bold; background-color: rgba(51,153,255,0.1);'
                            s.loc[i, '주문수량'] = 'color: #3399FF; font-weight: bold;'
                            s.loc[i, '예상체결금액'] = 'color: #3399FF; font-weight: bold;'
                        else:
                            s.loc[i, '주문'] = 'color: #9ca3af;'
                            s.loc[i, '예상체결금액'] = 'color: #9ca3af;'
                            
                        if row['액면가'] > 0 and row['현재가'] < row['액면가']:
                            s.loc[i, '현재가'] = warning_css
                            s.loc[i, '액면가'] = warning_css
                        elif 0 < row['현재가'] < 1000:
                            s.loc[i, '현재가'] = highlight_css
                            
                    return s
                
                def format_expected_amount(val):
                    if val > 0: return f"+{val:,}"
                    elif val < 0: return f"{val:,}"
                    else: return "0"
                    
                st.dataframe(
                    display_reb.style.apply(style_rebal, axis=None).format({
                        '시총(억)': '{:,}',
                        '현재가': '{:,}',
                        '액면가': '{:,}',
                        '수량': '{:,}',
                        '현재평가금액': '{:,}',
                        '목표금액': '{:,}',
                        '주문수량': '{:,}',
                        '예상체결금액': format_expected_amount
                    }),
                    use_container_width=True, hide_index=True
                )
        except Exception as e:
            st.error(f"리밸런싱 계산 중 오류가 발생했습니다. 파일 형식을 다시 확인해 주세요. (에러내용: {e})")
