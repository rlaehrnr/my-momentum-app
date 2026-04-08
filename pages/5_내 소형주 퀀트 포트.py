import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import yfinance as yf
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- [1. 설정 및 경로] ---
st.set_page_config(page_title="내 포트폴리오", layout="wide")
PORTFOLIO_PATH = 'data/my_portfolio.csv'
MASTER_TICKER_PATH = 'data/krx_stock_master.csv'

if not os.path.exists('data'):
    os.makedirs('data')

st.markdown("""
    <style>
    .block-container { padding-top: 3rem !important; }
    .main-title { font-size: 1.8rem !important; font-weight: bold; margin-bottom: 1rem; }
    .stMetric { background-color: rgba(130, 130, 130, 0.1); padding: 15px; border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">💼 내 퀀트 포트폴리오 대시보드</p>', unsafe_allow_html=True)

# --- [2. 마스터 데이터 로드] ---
@st.cache_data(ttl=86400)
def get_stock_master():
    if os.path.exists(MASTER_TICKER_PATH):
        for enc in ['utf-8-sig', 'cp949', 'euc-kr', 'utf-8']:
            try:
                df = pd.read_csv(MASTER_TICKER_PATH, dtype={'종목코드': str}, encoding=enc)
                if '종목코드' in df.columns and '종목명' in df.columns:
                    df['종목코드'] = df['종목코드'].astype(str).str.zfill(6)
                    df['검색명'] = "[" + df['종목코드'] + "] " + df['종목명']
                    return df
            except:
                continue
                
    res = []
    for f in ['data/momentum_data.csv', 'data/momentum_data_daily.csv']:
        if os.path.exists(f):
            try:
                tmp = pd.read_csv(f, dtype={'종목코드': str})
                for _, row in tmp.iterrows():
                    code = str(row['종목코드']).zfill(6)
                    name = row.get('종목명', code)
                    res.append({'종목코드': code, '종목명': name, '검색명': f"[{code}] {name}"})
            except: pass
    if res:
        return pd.DataFrame(res).drop_duplicates(subset=['종목코드'])
        
    return pd.DataFrame(columns=['종목코드', '종목명', '시장구분', '검색명'])

master_df = get_stock_master()
search_options = ["🔍 검색해서 추가 (삼성, 카카오 등)"] + master_df['검색명'].tolist() if not master_df.empty else ["검색 데이터가 없습니다."]

# --- [3. 초고속 실시간 가격 수집 함수] ---
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
                curr_val = int(df['Close'].iloc[-1])
                prev_val = int(df['Close'].iloc[-2])
            elif len(df) == 1:
                curr_val = prev_val = int(df['Close'].iloc[-1])
        except: pass
            
        if curr_val == 0:
            try:
                yf_t = code_str + ".KS" if code_str.isdigit() else code_str
                hist = yf.Ticker(yf_t).history(period="5d")
                if not hist.empty and len(hist) >= 2:
                    curr_val = int(hist['Close'].iloc[-1])
                    prev_val = int(hist['Close'].iloc[-2])
                elif code_str.isdigit(): 
                    hist_kq = yf.Ticker(code_str + ".KQ").history(period="5d")
                    if not hist_kq.empty and len(hist_kq) >= 2:
                        curr_val = int(hist_kq['Close'].iloc[-1])
                        prev_val = int(hist_kq['Close'].iloc[-2])
            except: pass
        
        if prev_val == 0: prev_val = curr_val
        return t, curr_val, prev_val

    # 💡 동시 작업자를 30명으로 늘려 압도적으로 빠르게 수집
    with ThreadPoolExecutor(max_workers=30) as executor:
        future_to_t = {executor.submit(get_price, t): t for t in tickers}
        for future in as_completed(future_to_t):
            t, curr, prev = future.result()
            price_map[t] = {'curr': curr, 'prev': prev}
            
    return price_map

# --- [4. 데이터 로드 로직] ---
def load_portfolio():
    if os.path.exists(PORTFOLIO_PATH):
        try:
            df = pd.read_csv(PORTFOLIO_PATH, dtype={'종목코드': str})
            df['종목코드'] = df['종목코드'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(6)
            df['매수단가'] = pd.to_numeric(df['매수단가'], errors='coerce').fillna(0).astype(int)
            df['수량'] = pd.to_numeric(df['수량'], errors='coerce').fillna(0).astype(int)
            return df
        except: pass
    return pd.DataFrame(columns=["종목명", "종목코드", "매수단가", "수량"])

if 'temp_df' not in st.session_state:
    st.session_state.temp_df = load_portfolio()

# =========================================================
# 🚀 레이아웃 마법 1: 상단 성적표용 '빈 공간'만 먼저 만들어 두기
# =========================================================
scoreboard_placeholder = st.container()

st.markdown("---")

# =========================================================
# ⚙️ 레이아웃 마법 2: 가벼운 하단 UI(입력창/표)를 즉시 화면에 그리기
# =========================================================
col_add, col_file = st.columns([1.5, 1])

with col_add:
    with st.expander("➕ 개별 종목 검색해서 추가", expanded=True):
        with st.form("add_form", clear_on_submit=True):
            sel = st.selectbox("종목 검색", options=search_options)
            c1, c2 = st.columns(2)
            p = c1.number_input("매수단가", min_value=0, step=100)
            q = c2.number_input("수량", min_value=1, step=1)
            
            if st.form_submit_button("포트폴리오에 추가"):
                if sel and sel != search_options[0]:
                    code, name = sel[1:7], sel[9:]
                    new_row = pd.DataFrame([{"종목명": name, "종목코드": code, "매수단가": int(p), "수량": int(q)}])
                    st.session_state.temp_df = pd.concat([st.session_state.temp_df, new_row], ignore_index=True)
                    st.session_state.temp_df.to_csv(PORTFOLIO_PATH, index=False, encoding='utf-8-sig')
                    st.rerun()

with col_file:
    with st.expander("📂 엑셀/CSV로 한꺼번에 넣기", expanded=True):
        up_file = st.file_uploader("파일 양식 (종목코드, 매수단가, 수량)", type=['csv', 'xlsx'])
        if up_file:
            try:
                if up_file.name.endswith('csv'): 
                    try: up_df = pd.read_csv(up_file, encoding='utf-8-sig')
                    except: up_df = pd.read_csv(up_file, encoding='cp949')
                else: 
                    up_df = pd.read_excel(up_file)
                
                up_df.columns = up_df.columns.str.strip()
                
                if st.button("🚀 업로드 데이터 반영하기"):
                    if '종목코드' not in up_df.columns:
                        st.error("엑셀 파일 첫 줄에 '종목코드'가 있어야 합니다!")
                    else:
                        up_df = up_df.dropna(subset=['종목코드'])
                        up_df['종목코드'] = up_df['종목코드'].astype(str).str.replace(r'\.0$', '', regex=True)
                        up_df['종목코드'] = up_df['종목코드'].apply(lambda x: str(x).zfill(6) if str(x).isdigit() else str(x))
                        
                        if '종목명' not in up_df.columns:
                            name_map = master_df.set_index('종목코드')['종목명'].to_dict() if not master_df.empty else {}
                            up_df['종목명'] = up_df['종목코드'].map(name_map).fillna('미등록종목')
                        
                        cols_to_keep = ["종목명", "종목코드", "매수단가", "수량"]
                        for c in cols_to_keep:
                            if c not in up_df.columns: up_df[c] = 0 if c in ['매수단가', '수량'] else ''
                        
                        up_df['매수단가'] = pd.to_numeric(up_df['매수단가'].astype(str).str.replace(r'[^0-9.]', '', regex=True), errors='coerce').fillna(0).astype(int)
                        up_df['수량'] = pd.to_numeric(up_df['수량'].astype(str).str.replace(r'[^0-9.]', '', regex=True), errors='coerce').fillna(0).astype(int)
                        
                        st.session_state.temp_df = up_df[cols_to_keep]
                        st.session_state.temp_df.to_csv(PORTFOLIO_PATH, index=False, encoding='utf-8-sig')
                        st.success("✅ 파일 업로드 완료!")
                        st.rerun()
            except Exception as e: 
                st.error(f"오류: {e}")

st.markdown("### 📝 포트폴리오 목록 편집")
edit_view_df = st.session_state.temp_df.copy()
edit_view_df['매수단가'] = pd.to_numeric(edit_view_df['매수단가'], errors='coerce').fillna(0).astype(int)
edit_view_df['수량'] = pd.to_numeric(edit_view_df['수량'], errors='coerce').fillna(0).astype(int)
edit_view_df.index = range(1, len(edit_view_df) + 1)

edited_df = st.data_editor(
    edit_view_df,
    num_rows="dynamic",
    use_container_width=True,
    column_order=["종목명", "종목코드", "매수단가", "수량"],
    column_config={
        "종목명": st.column_config.TextColumn("종목명"),
        "종목코드": st.column_config.TextColumn("코드/티커"),
        "매수단가": st.column_config.NumberColumn("매수단가", format="%,d"),
        "수량": st.column_config.NumberColumn("수량", format="%,d")
    }
)

if st.button("💾 위 표의 변경사항 저장 (삭제/수정)", use_container_width=True):
    save_df = edited_df.dropna(subset=['종목코드']).copy()
    save_df['종목코드'] = save_df['종목코드'].astype(str).str.replace(r'\.0$', '', regex=True).apply(lambda x: str(x).zfill(6) if str(x).isdigit() else str(x))
    save_df['매수단가'] = pd.to_numeric(save_df['매수단가'], errors='coerce').fillna(0).astype(int)
    save_df['수량'] = pd.to_numeric(save_df['수량'], errors='coerce').fillna(0).astype(int)
    
    save_df.index = range(len(save_df))
    st.session_state.temp_df = save_df
    st.session_state.temp_df.to_csv(PORTFOLIO_PATH, index=False, encoding='utf-8-sig')
    st.rerun()

# =========================================================
# 🚀 레이아웃 마법 3: 화면이 다 그려진 후 '백그라운드' 느낌으로 상단 채우기
# =========================================================
with scoreboard_placeholder:
    st.markdown("### 🚀 실시간 성적표")

    valid_portfolio = st.session_state.temp_df.dropna(subset=['종목코드']).copy()

    if not valid_portfolio.empty:
        # 하단 화면은 이미 떠 있는 상태에서, 요기만 로딩이 돌아갑니다!
        with st.spinner("📡 최신 주가를 수집 중입니다... (아래 화면은 조작 가능합니다)"):
            display_df = valid_portfolio.copy()
            display_df['종목코드'] = display_df['종목코드'].astype(str).str.replace(r'\.0$', '', regex=True).apply(lambda x: str(x).zfill(6) if str(x).isdigit() else str(x))
            display_df['매수단가'] = pd.to_numeric(display_df['매수단가'], errors='coerce').fillna(0).astype(int)
            display_df['수량'] = pd.to_numeric(display_df['수량'], errors='coerce').fillna(0).astype(int)

            unique_tickers = tuple(display_df['종목코드'].unique())
            price_dict = fetch_multi_prices(unique_tickers)
            
            display_df['현재가'] = display_df['종목코드'].apply(lambda x: price_dict.get(x, {}).get('curr', 0)).astype(int)
            display_df['전일종가'] = display_df['종목코드'].apply(lambda x: price_dict.get(x, {}).get('prev', 0)).astype(int)
            
            display_df['전일비'] = display_df['현재가'] - display_df['전일종가']
            display_df['전일대비(%)'] = display_df.apply(
                lambda r: (r['전일비'] / r['전일종가'] * 100) if r['전일종가'] > 0 else 0, axis=1
            )

            display_df['평가금액'] = display_df['현재가'] * display_df['수량']
            display_df['전일평가금액'] = display_df['전일종가'] * display_df['수량']
            display_df['평가손익'] = (display_df['현재가'] - display_df['매수단가']) * display_df['수량']
            display_df['수익률(%)'] = display_df.apply(
                lambda r: (r['평가손익'] / (r['매수단가'] * r['수량']) * 100) if (r['매수단가'] * r['수량']) > 0 else 0, axis=1
            )
            
            if '시장구분' in master_df.columns:
                m_info = master_df[['종목코드', '시장구분']].drop_duplicates(subset=['종목코드'])
                display_df = pd.merge(display_df, m_info, on='종목코드', how='left')
            else:
                display_df['시장구분'] = "KOSPI"
            
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
                        styles[c] = df[c].apply(lambda x: 'color: #EF4444; font-weight:bold;' if x > 0 else ('color: #3B82F6; font-weight:bold;' if x < 0 else ''))
                return styles

            st.dataframe(
                display_df.style.apply(style_fn, axis=None),
                use_container_width=True, hide_index=False,
                column_order=['티커_L', '종목명_L', '수량', '매수단가', '현재가', '전일대비(%)', '평가금액', '평가손익', '수익률(%)'],
                column_config={
                    "티커_L": st.column_config.LinkColumn("티커", display_text=r"#(.+)"),
                    "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"),
                    "매수단가": st.column_config.NumberColumn(format="%,d"),
                    "현재가": st.column_config.NumberColumn(format="%,d"),
                    "전일대비(%)": st.column_config.NumberColumn("전일비(%)", format="%.2f%%"),
                    "평가금액": st.column_config.NumberColumn(format="%,d"),
                    "평가손익": st.column_config.NumberColumn(format="%,d"),
                    "수량": st.column_config.NumberColumn(format="%,d"),
                    "수익률(%)": st.column_config.NumberColumn(format="%.2f%%"),
                }, height=450
            )
    else:
        st.info("👇 아래에서 포트폴리오에 종목을 추가하시면 실시간 성적표가 나타납니다.")
