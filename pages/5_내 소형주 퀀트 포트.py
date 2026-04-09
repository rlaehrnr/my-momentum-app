import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import yfinance as yf
import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- [1. 설정 및 경로] ---
st.set_page_config(page_title="내 퀀트 포트폴리오", layout="wide")

PORT_PATHS = {
    "ddo": 'data/port_ddo.csv',
    "sso": 'data/port_sso.csv',
    "mom": 'data/port_mom.csv'
}
MASTER_TICKER_PATH = 'data/krx_stock_master.csv'
CONFIG_PATH = 'data/portfolio_config.json' 

if not os.path.exists('data'):
    os.makedirs('data')

st.markdown("""
    <style>
    .block-container { padding-top: 2.5rem !important; }
    .main-title { font-size: 1.8rem !important; font-weight: bold; margin-bottom: 1.5rem; }
    .stTabs [data-baseweb="tab"] { font-size: 18px; font-weight: bold; }
    
    /* 💡 요약 표 세련된 디자인 */
    .summary-table { width: 100%; border-collapse: collapse; text-align: center; font-size: 1.1rem; background-color: #1a1c24; border-radius: 12px; overflow: hidden; }
    .summary-table th { background-color: #2d313e; padding: 15px; color: #9ca3af; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px; }
    .summary-table td { padding: 16px; border-bottom: 1px solid #2d313e; color: #e5e7eb; }
    
    /* 강조 컬럼 (시작일 기준 수익) */
    .highlight-cell { background-color: rgba(255, 255, 255, 0.03); font-size: 1.2rem; }
    
    /* 합계 행 */
    .summary-total { background-color: #242834; font-size: 1.25rem; border-top: 2px solid #4b5563; }
    
    /* 숫자 색상 (눈 편한 톤) */
    .val-red { color: #ff6b6b !important; }
    .val-blue { color: #5dade2 !important; }
    .val-white { color: #ffffff !important; }
    
    /* 시작일 기준 수익 강조 박스 */
    .box-red { background-color: rgba(255, 107, 107, 0.15); color: #ff6b6b; padding: 4px 12px; border-radius: 6px; }
    .box-blue { background-color: rgba(93, 173, 226, 0.15); color: #5dade2; padding: 4px 12px; border-radius: 6px; }
    </style>
""", unsafe_allow_html=True)

# --- [2. 설정 파일 로드/저장] ---
def load_config():
    default_config = {
        "start_date": str(datetime.today().date()), 
        "start_ddo": 0, "start_sso": 0, "start_mom": 0
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f: 
                saved_config = json.load(f)
                for k in default_config.keys():
                    if k in saved_config: default_config[k] = saved_config[k]
                return default_config
        except: pass
    return default_config

def save_config(config_data):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f: json.dump(config_data, f)

# --- [3. 마스터 데이터 & 시가총액 로드] ---
@st.cache_data(ttl=86400, show_spinner=False)
def get_stock_master_and_cap():
    master_df = pd.DataFrame(columns=['종목코드', '종목명', '시장구분', '검색명', '시가총액(억)'])
    cap_map = {}
    if os.path.exists(MASTER_TICKER_PATH):
        for enc in ['utf-8-sig', 'cp949', 'euc-kr', 'utf-8']:
            try:
                df = pd.read_csv(MASTER_TICKER_PATH, dtype={'종목코드': str}, encoding=enc)
                if '종목코드' in df.columns:
                    df['종목코드'] = df['종목코드'].astype(str).str.zfill(6)
                    df['검색명'] = "[" + df['종목코드'] + "] " + df.get('종목명', df['종목코드'])
                    if '시가총액(억)' in df.columns:
                        df['시가총액(억)'] = pd.to_numeric(df['시가총액(억)'].astype(str).str.replace(r'[^0-9.]', '', regex=True), errors='coerce').fillna(0).astype(int)
                        cap_map = df.set_index('종목코드')['시가총액(억)'].to_dict()
                    master_df = df
                    break
            except: continue
    return master_df, cap_map

master_df, global_cap_map = get_stock_master_and_cap()
search_options = ["🔍 종목 검색"] + master_df['검색명'].tolist() if not master_df.empty else ["검색 데이터 없음"]

# --- [4. 가격 수집 & 포트 로드] ---
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

# --- [5. 개별 포트폴리오 탭 렌더링] ---
def render_portfolio_tab(port_name, port_key, path):
    if f'df_{port_key}' not in st.session_state:
        st.session_state[f'df_{port_key}'] = load_portfolio(path)

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
                    st.session_state[f'df_{port_key}'].to_csv(path, index=False, encoding='utf-8-sig')
                    st.rerun()
                except: st.error("파일 오류")

    st.markdown(f"### 📝 {port_name} 편집")
    df_editor = st.data_editor(st.session_state[f'df_{port_key}'], num_rows="dynamic", use_container_width=True, key=f"ed_{port_key}")
    if st.button("저장", key=f"sv_{port_key}"):
        st.session_state[f'df_{port_key}'] = df_editor
        st.session_state[f'df_{port_key}'].to_csv(path, index=False, encoding='utf-8-sig')
        st.rerun()

    with scoreboard_placeholder:
        st.markdown(f"### 🚀 {port_name} 실시간")
        df = st.session_state[f'df_{port_key}'].copy()
        if not df.empty:
            with st.spinner("로딩..."):
                prices = fetch_multi_prices(tuple(df['종목코드'].unique()))
                df['시총(억)'] = df['종목코드'].map(global_cap_map).fillna(0)
                df['현재가'] = df['종목코드'].apply(lambda x: prices.get(x, {}).get('curr', 0))
                df['전일종가'] = df['종목코드'].apply(lambda x: prices.get(x, {}).get('prev', 0))
                df['전일비(%)'] = ((df['현재가'] - df['전일종가']) / df['전일종가'] * 100).fillna(0)
                df['평가금액'] = df['현재가'] * df['수량']
                df['평가손익'] = (df['현재가'] - df['매수단가']) * df['수량']
                df['수익률(%)'] = (df['평가손익'] / (df['매수단가'] * df['수량']) * 100).fillna(0)
                
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("총 매수", f"₩{(df['매수단가']*df['수량']).sum():,}")
                c2.metric("총 평가", f"₩{df['평가금액'].sum():,}")
                c4.metric("평가손익", f"₩{df['평가손익'].sum():,}")
                c5.metric("수익률", f"{df['평가손익'].sum()/(df['매수단가']*df['수량']).sum()*100:.2f}%")
                
                st.dataframe(df.style.format({'전일비(%)':'{:.2f}%','수익률(%)':'{:.2f}%'}), use_container_width=True, hide_index=True)

# =========================================================
# 🚀 메인 화면 구성
# =========================================================
st.markdown('<p class="main-title">💼 내 퀀트 포트폴리오 종합 대시보드</p>', unsafe_allow_html=True)
tabs = st.tabs(["📊 종합 요약", "📁 또", "📁 쏘", "📁 맘"])

with tabs[0]:
    config = load_config()
    
    # 💡 [업데이트] 설정을 한 줄로 깔끔하게 배치
    st.markdown("##### ⚙️ 비교 시점 및 시작 수익금 설정")
    c_dt, c_d, c_s, c_m = st.columns([1.2, 1, 1, 1])
    
    try: dt_val = datetime.strptime(config['start_date'], '%Y-%m-%d').date()
    except: dt_val = datetime.today().date()
    
    new_date = c_dt.date_input("📅 시작일", value=dt_val)
    new_ddo = c_d.number_input("💰 [또] 시작금", value=config['start_ddo'], step=100000)
    new_sso = c_s.number_input("💰 [쏘] 시작금", value=config['start_sso'], step=100000)
    new_mom = c_m.number_input("💰 [맘] 시작금", value=config['start_mom'], step=100000)
    
    if str(new_date) != config['start_date'] or new_ddo != config['start_ddo'] or new_sso != config['start_sso'] or new_mom != config['start_mom']:
        config.update({"start_date": str(new_date), "start_ddo": new_ddo, "start_sso": new_sso, "start_mom": new_mom})
        save_config(config); st.rerun()

    st.markdown("<br>### 🏆 포트폴리오 성과 요약", unsafe_allow_html=True)
    
    summary_data = []
    total_buy, total_profit, total_daily, total_since = 0, 0, 0, 0
    
    all_codes = []
    for p in PORT_PATHS.values(): all_codes.extend(load_portfolio(p)['종목코드'].tolist())
    prices = fetch_multi_prices(tuple(set(all_codes)))

    for p_name, p_key in [("또", "ddo"), ("쏘", "sso"), ("맘", "mom")]:
        df = load_portfolio(PORT_PATHS[p_key])
        start_val = config[f'start_{p_key}']
        if not df.empty:
            df['curr'] = df['종목코드'].apply(lambda x: prices.get(x, {}).get('curr', 0))
            df['prev'] = df['종목코드'].apply(lambda x: prices.get(x, {}).get('prev', 0))
            t_buy = (df['매수단가'] * df['수량']).sum()
            t_val = (df['curr'] * df['수량']).sum()
            t_prev = (df['prev'] * df['수량']).sum()
            t_profit = t_val - t_buy
            d_diff = t_val - t_prev
            since_start = t_profit - start_val
            
            total_buy += t_buy; total_profit += t_profit; total_daily += d_diff; total_since += since_start
            summary_data.append({"name": p_name, "daily": d_diff, "pct": (t_profit/t_buy*100), "profit": t_profit, "since": since_start})
        else:
            summary_data.append({"name": p_name, "daily": 0, "pct": 0, "profit": 0, "since": -start_val})
            total_since -= start_val

    # 💡 [업데이트] 가독성이 개선된 HTML 표 출력
    html = "<table class='summary-table'><thead><tr><th>포트폴리오</th><th>오늘의 등락</th><th>총 수익률</th><th>현재 수익 금액</th><th style='color:#ffffff; background-color:#3e4452;'>시작일 기준 수익 금액</th></tr></thead><tbody>"
    
    def get_cls(v, is_box=False):
        cls = "val-red" if v > 0 else ("val-blue" if v < 0 else "val-gray")
        if is_box and v != 0: return f"box-red" if v > 0 else "box-blue"
        return cls

    for r in summary_data:
        box_cls = get_cls(r['since'], True)
        html += f"<tr><td>{r['name']}</td>"
        html += f"<td class='{get_cls(r['daily'])}'>₩{int(r['daily']):,}</td>"
        html += f"<td class='{get_cls(r['pct'])}'>{r['pct']:.2f}%</td>"
        html += f"<td class='{get_cls(r['profit'])}'>₩{int(r['profit']):,}</td>"
        html += f"<td class='highlight-cell'><span class='{box_cls}'>₩{int(r['since']):,}</span></td></tr>"

    html += f"<tr class='summary-total'><td><b>합계</b></td>"
    html += f"<td class='{get_cls(total_daily)}'><b>₩{int(total_daily):,}</b></td>"
    html += f"<td class='val-white'><b>{total_profit/total_buy*100 if total_buy>0 else 0:.2f}%</b></td>"
    html += f"<td class='{get_cls(total_profit)}'><b>₩{int(total_profit):,}</b></td>"
    html += f"<td class='highlight-cell' style='border-top:2px solid #5dade2 !important;'><span style='font-size:1.4rem;' class='{get_cls(total_since, True)}'>₩{int(total_since):,}</span></td></tr>"
    html += "</tbody></table>"
    st.markdown(html, unsafe_allow_html=True)

with tabs[1]: render_portfolio_tab("또", "ddo", PORT_PATHS["ddo"])
with tabs[2]: render_portfolio_tab("쏘", "sso", PORT_PATHS["sso"])
with tabs[3]: render_portfolio_tab("맘", "mom", PORT_PATHS["mom"])
