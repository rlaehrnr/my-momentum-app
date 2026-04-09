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
    .main-title { font-size: 1.8rem !important; font-weight: bold; margin-bottom: 1rem; }
    .stMetric { background-color: rgba(130, 130, 130, 0.1); padding: 15px; border-radius: 10px; }
    .stTabs [data-baseweb="tab"] { font-size: 18px; font-weight: bold; }
    
    @media (max-width: 768px) {
        div[data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
            min-width: 45% !important; flex: 1 1 45% !important; margin-bottom: 10px !important;
        }
    }
    
    .summary-table { width: 100%; border-collapse: collapse; text-align: center; font-size: 1.15rem; background-color: #111827; border-radius: 8px; overflow: hidden; margin-top: 10px; }
    .summary-table th { background-color: #374151; padding: 14px; border-bottom: 2px solid #4B5563; color: #F3F4F6; }
    .summary-table td { padding: 14px; border-bottom: 1px solid #374151; color: #E5E7EB; font-weight: 600; }
    .summary-total { background-color: #1F2937; font-size: 1.3rem; }
    .summary-total td { border-top: 2px solid #9CA3AF !important; }
    .val-red { color: #FF5252 !important; font-weight: bold; }
    .val-blue { color: #448AFF !important; font-weight: bold; }
    .val-gray { color: #9CA3AF !important; font-weight: normal; }
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
                if '종목코드' in df.columns and '종목명' in df.columns:
                    df['종목코드'] = df['종목코드'].astype(str).str.zfill(6)
                    df['검색명'] = "[" + df['종목코드'] + "] " + df['종목명']
                    
                    if '시가총액(억)' in df.columns:
                        df['시가총액(억)'] = pd.to_numeric(df['시가총액(억)'].astype(str).str.replace(r'[^0-9.]', '', regex=True), errors='coerce').fillna(0).astype(int)
                        cap_map = df.set_index('종목코드')['시가총액(억)'].to_dict()
                    master_df = df
                    break
            except: continue
    return master_df, cap_map

master_df, global_cap_map = get_stock_master_and_cap()
search_options = ["🔍 검색해서 추가 (삼성, 카카오 등)"] + master_df['검색명'].tolist() if not master_df.empty else ["검색 데이터가 없습니다."]

# --- [4. 초고속 실시간 가격 수집 함수] ---
@st.cache_data(ttl=60, show_spinner=False)
def fetch_multi_prices(tickers):
    if not tickers: return {}
    price_map = {}
    
    def get_price(t):
        curr_val, prev_val = 0, 0
        t_str = str(t).replace('.0', '')
        code_str = t_str.zfill(6) if t_str.isdigit() else t_str
        
        try:
            df = fdr.DataReader(code_str, datetime.today() - timedelta(days=15))
            if not df.empty and len(df) >= 2:
                curr_val, prev_val = int(df['Close'].iloc[-1]), int(df['Close'].iloc[-2])
            elif len(df) == 1:
                curr_val = prev_val = int(df['Close'].iloc[-1])
        except: pass
            
        if curr_val == 0:
            try:
                yf_t = code_str + ".KS" if code_str.isdigit() else code_str
                hist = yf.Ticker(yf_t).history(period="5d")
                if not hist.empty and len(hist) >= 2:
                    curr_val, prev_val = int(hist['Close'].iloc[-1]), int(hist['Close'].iloc[-2])
            except: pass
        
        if prev_val == 0: prev_val = curr_val
        return t, curr_val, prev_val

    with ThreadPoolExecutor(max_workers=30) as executor:
        future_to_t = {executor.submit(get_price, t): t for t in tickers}
        for future in as_completed(future_to_t):
            t, curr, prev = future.result()
            price_map[t] = {'curr': curr, 'prev': prev}
    return price_map

def load_portfolio(path):
    if os.path.exists(path):
        for enc in ['utf-8-sig', 'cp949', 'euc-kr', 'utf-8']:
            try:
                df = pd.read_csv(path, dtype={'종목코드': str}, encoding=enc)
                df['종목코드'] = df['종목코드'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(6)
                df['매수단가'] = pd.to_numeric(df['매수단가'], errors='coerce').fillna(0).astype(int)
                df['수량'] = pd.to_numeric(df['수량'], errors='coerce').fillna(0).astype(int)
                return df
            except Exception as e:
                continue
    return pd.DataFrame(columns=["종목명", "종목코드", "매수단가", "수량"])

# --- [5. 개별 포트폴리오 렌더링 함수] ---
def render_portfolio_tab(port_name, port_key, path):
    # 💡 [버그 완벽 수정] 탭을 전환할 때마다 최신 파일을 로드하도록 보장
    if f'df_{port_key}' not in st.session_state:
        st.session_state[f'df_{port_key}'] = load_portfolio(path)

    scoreboard_placeholder = st.container()
    st.markdown("---")

    col_add, col_file = st.columns([1.5, 1])
    with col_add:
        with st.expander(f"➕ {port_name} 포트폴리오 개별 종목 추가", expanded=True):
            # 💡 [핵심] 폼(Form)과 입력창의 key를 완벽히 분리
            with st.form(f"add_form_{port_key}", clear_on_submit=True):
                sel = st.selectbox("종목 검색", options=search_options, key=f"sel_{port_key}")
                c1, c2 = st.columns(2)
                p = c1.number_input("매수단가", min_value=0, step=100, key=f"p_{port_key}")
                q = c2.number_input("수량", min_value=1, step=1, key=f"q_{port_key}")
                
                if st.form_submit_button("포트폴리오에 추가"):
                    if sel and sel != search_options[0]:
                        code, name = sel[1:7], sel[9:]
                        new_row = pd.DataFrame([{"종목명": name, "종목코드": code, "매수단가": int(p), "수량": int(q)}])
                        st.session_state[f'df_{port_key}'] = pd.concat([st.session_state[f'df_{port_key}'], new_row], ignore_index=True)
                        st.session_state[f'df_{port_key}'].to_csv(path, index=False, encoding='utf-8-sig')
                        st.rerun()

    with col_file:
        with st.expander("📂 엑셀/CSV로 한꺼번에 넣기", expanded=True):
            up_file = st.file_uploader("파일 양식 (종목코드, 매수단가, 수량)", type=['csv', 'xlsx'], key=f"up_{port_key}")
            if up_file:
                if st.button("🚀 업로드 데이터 반영하기", key=f"btn_up_{port_key}"):
                    try:
                        if up_file.name.endswith('csv'): 
                            try: up_df = pd.read_csv(up_file, encoding='utf-8-sig')
                            except: 
                                up_file.seek(0)
                                try: up_df = pd.read_csv(up_file, encoding='cp949')
                                except: 
                                    up_file.seek(0)
                                    up_df = pd.read_csv(up_file, encoding='euc-kr')
                        else: up_df = pd.read_excel(up_file)
                        
                        up_df.columns = up_df.columns.str.strip()
                        if '종목코드' in up_df.columns:
                            up_df = up_df.dropna(subset=['종목코드'])
                            up_df['종목코드'] = up_df['종목코드'].astype(str).str.replace(r'\.0$', '', regex=True).apply(lambda x: str(x).zfill(6) if str(x).isdigit() else str(x))
                            
                            if '종목명' not in up_df.columns:
                                name_map = master_df.set_index('종목코드')['종목명'].to_dict() if not master_df.empty else {}
                                up_df['종목명'] = up_df['종목코드'].map(name_map).fillna('미등록종목')
                            
                            cols_to_keep = ["종목명", "종목코드", "매수단가", "수량"]
                            for c in cols_to_keep:
                                if c not in up_df.columns: up_df[c] = 0 if c in ['매수단가', '수량'] else ''
                            
                            up_df['매수단가'] = pd.to_numeric(up_df['매수단가'].astype(str).str.replace(r'[^0-9.]', '', regex=True), errors='coerce').fillna(0).astype(int)
                            up_df['수량'] = pd.to_numeric(up_df['수량'].astype(str).str.replace(r'[^0-9.]', '', regex=True), errors='coerce').fillna(0).astype(int)
                            
                            st.session_state[f'df_{port_key}'] = up_df[cols_to_keep]
                            st.session_state[f'df_{port_key}'].to_csv(path, index=False, encoding='utf-8-sig')
                            st.success(f"✅ {port_name} 업로드 완료!")
                            st.rerun()
                        else: st.error("엑셀 첫 줄에 '종목코드'가 있어야 합니다!")
                    except Exception as e: st.error(f"파일을 읽을 수 없습니다: {e}")

    st.markdown(f"### 📝 {port_name} 목록 편집")
    
    # 💡 데이터 에디터에 표시하기 전 데이터 복사 및 정제
    edit_view_df = st.session_state[f'df_{port_key}'].copy()
    edit_view_df['매수단가'] = pd.to_numeric(edit_view_df['매수단가'], errors='coerce').fillna(0).astype(int)
    edit_view_df['수량'] = pd.to_numeric(edit_view_df['수량'], errors='coerce').fillna(0).astype(int)
    edit_view_df.index = range(1, len(edit_view_df) + 1)

    edited_df = st.data_editor(
        edit_view_df, num_rows="dynamic", use_container_width=True, key=f"editor_{port_key}",
        column_order=["종목명", "종목코드", "매수단가", "수량"],
        column_config={
            "종목명": st.column_config.TextColumn("종목명"),
            "종목코드": st.column_config.TextColumn("코드/티커"),
            "매수단가": st.column_config.NumberColumn("매수단가", format="%,d"),
            "수량": st.column_config.NumberColumn("수량", format="%,d")
        }
    )

    if st.button("💾 변경사항 저장 (삭제/수정)", use_container_width=True, key=f"save_{port_key}"):
        save_df = edited_df.dropna(subset=['종목코드']).copy()
        save_df['종목코드'] = save_df['종목코드'].astype(str).str.replace(r'\.0$', '', regex=True).apply(lambda x: str(x).zfill(6) if str(x).isdigit() else str(x))
        save_df['매수단가'] = pd.to_numeric(save_df['매수단가'], errors='coerce').fillna(0).astype(int)
        save_df['수량'] = pd.to_numeric(save_df['수량'], errors='coerce').fillna(0).astype(int)
        
        save_df.index = range(len(save_df))
        st.session_state[f'df_{port_key}'] = save_df
        st.session_state[f'df_{port_key}'].to_csv(path, index=False, encoding='utf-8-sig')
        st.rerun()

    with scoreboard_placeholder:
        st.markdown(f"### 🚀 {port_name} 실시간 성적표")
        valid_portfolio = st.session_state[f'df_{port_key}'].dropna(subset=['종목코드']).copy()

        if not valid_portfolio.empty:
            with st.spinner("📡 최신 주가를 수집 중입니다..."):
                display_df = valid_portfolio.copy()
                display_df['종목코드'] = display_df['종목코드'].astype(str).str.replace(r'\.0$', '', regex=True).apply(lambda x: str(x).zfill(6) if str(x).isdigit() else str(x))
                display_df['시가총액(억)'] = display_df['종목코드'].map(global_cap_map).fillna(0).astype(int)

                price_dict = fetch_multi_prices(tuple(display_df['종목코드'].unique()))
                display_df['현재가'] = display_df['종목코드'].apply(lambda x: price_dict.get(x, {}).get('curr', 0)).astype(int)
                display_df['전일종가'] = display_df['종목코드'].apply(lambda x: price_dict.get(x, {}).get('prev', 0)).astype(int)
                
                display_df['전일비'] = display_df['현재가'] - display_df['전일종가']
                display_df['전일대비(%)'] = display_df.apply(lambda r: (r['전일비'] / r['전일종가'] * 100) if r['전일종가'] > 0 else 0, axis=1)
                display_df['평가금액'] = display_df['현재가'] * display_df['수량']
                display_df['전일평가금액'] = display_df['전일종가'] * display_df['수량']
                display_df['평가손익'] = (display_df['현재가'] - display_df['매수단가']) * display_df['수량']
                display_df['수익률(%)'] = display_df.apply(lambda r: (r['평가손익'] / (r['매수단가'] * r['수량']) * 100) if (r['매수단가'] * r['수량']) > 0 else 0, axis=1)
                
                if '시장구분' in master_df.columns:
                    m_info = master_df[['종목코드', '시장구분']].drop_duplicates(subset=['종목코드'])
                    display_df = pd.merge(display_df, m_info, on='종목코드', how='left')
                else: display_df['시장구분'] = "KOSPI"
                
                def make_links(r):
                    market_val = str(r.get('시장구분', ''))
                    m = "KOSDAQ" if "코스닥" in market_val or "KOSDAQ" in market_val.upper() else "KOSPI"
                    t_url = f"https://finance.naver.com/item/main.naver?code={r['종목코드']}#{m}:{r['종목코드']}"
                    n_url = f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드']}#{r['종목명']}"
                    return pd.Series([t_url, n_url])
                display_df[['티커_L', '종목명_L']] = display_df.apply(make_links, axis=1)

                total_buy = (display_df['매수단가'] * display_df['수량']).sum()
                total_val = display_df['평가금액'].sum()
                total_prev_val = display_df['전일평가금액'].sum()
                total_daily_diff = total_val - total_prev_val
                total_daily_pct = (total_daily_diff / total_prev_val * 100) if total_prev_val > 0 else 0
                total_profit = display_df['평가손익'].sum()
                total_pct = (total_profit / total_buy * 100) if total_buy > 0 else 0
                
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("💰 총 매수", f"{int(total_buy):,}원")
                c2.metric("📈 총 평가액", f"{int(total_val):,}원")
                c3.metric("🌟 오늘 변동액", f"{int(total_daily_diff):,}원", delta=f"{total_daily_pct:.2f}%")
                c4.metric("💸 총 평가손익", f"{int(total_profit):,}원", delta=f"{int(total_profit):,}원")
                c5.metric("📊 총 수익률", f"{total_pct:.2f}%", delta=f"{total_pct:.2f}%")
                
                display_df.index = range(1, len(display_df) + 1)
                
                def style_fn(df):
                    styles = pd.DataFrame('', index=df.index, columns=df.columns)
                    for c in ['수익률(%)', '평가손익', '전일대비(%)']:
                        if c in df.columns:
                            styles[c] = df[c].apply(lambda x: 'color: #FF5252; font-weight:bold;' if x > 0 else ('color: #448AFF; font-weight:bold;' if x < 0 else ''))
                    return styles

                st.dataframe(display_df.style.apply(style_fn, axis=None), use_container_width=True, hide_index=False,
                    column_order=['티커_L', '종목명_L', '시가총액(억)', '수량', '매수단가', '현재가', '전일대비(%)', '평가금액', '평가손익', '수익률(%)'],
                    column_config={
                        "티커_L": st.column_config.LinkColumn("티커", display_text=r"#(.+)"),
                        "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"),
                        "시가총액(억)": st.column_config.NumberColumn("시총(억)", format="%,d"),
                        "매수단가": st.column_config.NumberColumn(format="%,d"),
                        "현재가": st.column_config.NumberColumn(format="%,d"),
                        "전일대비(%)": st.column_config.NumberColumn("전일비(%)", format="%.2f%%"),
                        "평가금액": st.column_config.NumberColumn(format="%,d"),
                        "평가손익": st.column_config.NumberColumn(format="%,d"),
                        "수량": st.column_config.NumberColumn(format="%,d"),
                        "수익률(%)": st.column_config.NumberColumn(format="%.2f%%"),
                    }, height=450)
        else:
            st.info(f"👇 아래에서 '{port_name}' 포트폴리오에 종목을 추가하시면 실시간 성적표가 나타납니다.")


# =========================================================
# 🚀 메인 화면 구성 (탭 분리)
# =========================================================
st.markdown('<p class="main-title">💼 내 퀀트 포트폴리오 종합 대시보드</p>', unsafe_allow_html=True)

tab_summary, tab_ddo, tab_sso, tab_mom = st.tabs(["📊 종합 요약", "📁 또", "📁 쏘", "📁 맘"])

# --- [종합 요약 탭] ---
with tab_summary:
    config = load_config()
    
    st.markdown("##### 📅 비교시점 시작일 설정")
    try:
        dt_val = datetime.strptime(config['start_date'], '%Y-%m-%d').date()
    except:
        dt_val = datetime.today().date()
        
    c_date, _ = st.columns([1, 4])
    new_date = c_date.date_input("시작일", value=dt_val, label_visibility="collapsed", key="global_start_date")

    st.markdown("##### 📝 비교시점 시작 수익금액 설정 (원)")
    c1, c2, c3 = st.columns(3)
    
    new_ddo = c1.number_input("📁 [또] 시작 수익금", value=config['start_ddo'], step=100000, key="cfg_ddo")
    new_sso = c2.number_input("📁 [쏘] 시작 수익금", value=config['start_sso'], step=100000, key="cfg_sso")
    new_mom = c3.number_input("📁 [맘] 시작 수익금", value=config['start_mom'], step=100000, key="cfg_mom")
    
    if str(new_date) != config['start_date'] or new_ddo != config['start_ddo'] or new_sso != config['start_sso'] or new_mom != config['start_mom']:
        config['start_date'] = str(new_date)
        config['start_ddo'] = new_ddo
        config['start_sso'] = new_sso
        config['start_mom'] = new_mom
        save_config(config)
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 🏆 포트폴리오 총합계")

    summary_data = []
    total_buy_all = 0
    total_profit_all = 0       
    total_daily_diff_all = 0
    total_since_start_all = 0  

    all_tickers = set()
    ports = [("또", "ddo", PORT_PATHS["ddo"]), ("쏘", "sso", PORT_PATHS["sso"]), ("맘", "mom", PORT_PATHS["mom"])]
    
    # 각 포트폴리오별 파일을 읽어서 티커 수집
    for _, _, path in ports:
        df = load_portfolio(path)
        all_tickers.update(df['종목코드'].tolist())
    price_dict = fetch_multi_prices(tuple(all_tickers))

    for p_name, p_key, path in ports:
        df = load_portfolio(path)
        start_val = config[f'start_{p_key}']
        
        if not df.empty:
            df['현재가'] = df['종목코드'].apply(lambda x: price_dict.get(x, {}).get('curr', 0)).astype(int)
            df['전일종가'] = df['종목코드'].apply(lambda x: price_dict.get(x, {}).get('prev', 0)).astype(int)
            
            df['평가금액'] = df['현재가'] * df['수량']
            df['전일평가금액'] = df['전일종가'] * df['수량']
            df['평가손익'] = (df['현재가'] - df['매수단가']) * df['수량']
            
            t_buy = (df['매수단가'] * df['수량']).sum()
            t_val = df['평가금액'].sum()
            t_prev_val = df['전일평가금액'].sum()
            
            d_diff = t_val - t_prev_val
            t_profit = df['평가손익'].sum()
            t_pct = (t_profit / t_buy * 100) if t_buy > 0 else 0
            
            since_start_profit = t_profit - start_val
            
            total_buy_all += t_buy
            total_profit_all += t_profit
            total_daily_diff_all += d_diff
            total_since_start_all += since_start_profit
            
            summary_data.append({
                "포트폴리오": p_name,
                "오늘의 등락": d_diff,
                "총 수익률": t_pct,
                "현재 수익 금액": t_profit,
                "시작일 기준 수익 금액": since_start_profit
            })
        else:
            summary_data.append({
                "포트폴리오": p_name, "오늘의 등락": 0, "총 수익률": 0.0, 
                "현재 수익 금액": 0, "시작일 기준 수익 금액": -start_val
            })
            total_since_start_all += (-start_val)

    final_pct = (total_profit_all / total_buy_all * 100) if total_buy_all > 0 else 0.0

    html_str = "<table class='summary-table'><thead><tr><th>포트폴리오</th><th>오늘의 등락</th><th>총 수익률</th><th>현재 수익 금액</th><th>시작일 기준 수익 금액</th></tr></thead><tbody>"
    
    def get_color_class(val):
        if val > 0: return "val-red"
        elif val < 0: return "val-blue"
        return "val-gray"
        
    for row in summary_data:
        c_diff = get_color_class(row['오늘의 등락'])
        c_pct = get_color_class(row['총 수익률'])
        c_prof = get_color_class(row['현재 수익 금액'])
        c_since = get_color_class(row['시작일 기준 수익 금액'])
        
        html_str += f"<tr><td>{row['포트폴리오']}</td>"
        html_str += f"<td class='{c_diff}'>₩{int(row['오늘의 등락']):,}</td>"
        html_str += f"<td class='{c_pct}'>{row['총 수익률']:.2f}%</td>"
        html_str += f"<td class='{c_prof}'>₩{int(row['현재 수익 금액']):,}</td>"
        html_str += f"<td class='{c_since}'>₩{int(row['시작일 기준 수익 금액']):,}</td></tr>"

    c_tot_diff = get_color_class(total_daily_diff_all)
    c_tot_prof = get_color_class(total_profit_all)
    c_tot_since = get_color_class(total_since_start_all)
    
    html_str += f"<tr class='summary-total'><td>합계</td>"
    html_str += f"<td class='{c_tot_diff}'>₩{int(total_daily_diff_all):,}</td>"
    html_str += f"<td></td>"
    html_str += f"<td class='{c_tot_prof}'>₩{int(total_profit_all):,}</td>"
    html_str += f"<td class='{c_tot_since}'>₩{int(total_since_start_all):,}</td></tr>"
    html_str += "</tbody></table>"

    st.markdown(html_str, unsafe_allow_html=True)


# --- [각 포트폴리오 탭 렌더링] ---
with tab_ddo: render_portfolio_tab("또", "ddo", PORT_PATHS["ddo"])
with tab_sso: render_portfolio_tab("쏘", "sso", PORT_PATHS["sso"])
with tab_mom: render_portfolio_tab("맘", "mom", PORT_PATHS["mom"])
