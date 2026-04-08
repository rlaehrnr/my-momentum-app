import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import yfinance as yf
import os

# --- [1. 설정 및 경로] ---
st.set_page_config(page_title="내 포트폴리오", layout="wide")
PORTFOLIO_PATH = 'data/my_portfolio.csv'
MASTER_TICKER_PATH = 'data/krx_stock_master.csv'

if not os.path.exists('data'):
    os.makedirs('data')

# 💡 여백(padding-top)을 1.5rem -> 3rem으로 늘려서 타이틀이 잘리지 않게 수정
st.markdown("""
    <style>
    .block-container { padding-top: 3rem !important; }
    .main-title { font-size: 1.8rem !important; font-weight: bold; margin-bottom: 1rem; color: #1F2937; }
    .stMetric { background-color: #f8f9fa; padding: 10px; border-radius: 10px; border: 1px solid #e9ecef; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">💼 내 퀀트 포트폴리오 대시보드</p>', unsafe_allow_html=True)

# --- [2. 마스터 데이터 로드 (💡 인코딩 에러 철벽 방어)] ---
@st.cache_data(ttl=86400)
def get_stock_master():
    if os.path.exists(MASTER_TICKER_PATH):
        # 엑셀에서 저장된 CSV의 다양한 한글 인코딩 방식을 모두 시도합니다.
        for enc in ['utf-8-sig', 'cp949', 'euc-kr', 'utf-8']:
            try:
                df = pd.read_csv(MASTER_TICKER_PATH, dtype={'종목코드': str}, encoding=enc)
                if '종목코드' in df.columns and '종목명' in df.columns:
                    df['종목코드'] = df['종목코드'].astype(str).str.zfill(6)
                    df['검색명'] = "[" + df['종목코드'] + "] " + df['종목명']
                    return df
            except:
                continue
                
    # 파일이 없거나 도저히 못 읽겠으면 임시방편으로 기존 데이터에서 추출
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

# --- [3. 실시간 가격 대량 수집 함수] ---
@st.cache_data(ttl=60)
def fetch_multi_prices(tickers):
    if not tickers: return {}
    price_map = {}
    
    yf_tickers = [ (t + ".KS" if t.isdigit() else t) for t in tickers ]
    try:
        data = yf.download(yf_tickers, period="5d", interval="1d", group_by='ticker', progress=False)
        for t in tickers:
            yf_t = t + ".KS" if t.isdigit() else t
            try:
                if len(tickers) == 1: val = data['Close'].iloc[-1]
                else: val = data[yf_t]['Close'].iloc[-1]
                
                if pd.isna(val) and t.isdigit():
                    val = yf.download(t + ".KQ", period="1d", progress=False)['Close'].iloc[-1]
                
                price_map[t] = int(val) if not pd.isna(val) else 0
            except: price_map[t] = 0
    except:
        for t in tickers:
            try:
                df = fdr.DataReader(t, datetime.today() - timedelta(days=7))
                price_map[t] = int(df['Close'].iloc[-1]) if not df.empty else 0
            except: price_map[t] = 0
            
    return price_map

# --- [4. 데이터 로드 로직] ---
def load_portfolio():
    if os.path.exists(PORTFOLIO_PATH):
        try:
            df = pd.read_csv(PORTFOLIO_PATH, dtype={'종목코드': str})
            df['종목코드'] = df['종목코드'].str.zfill(6)
            return df
        except: pass
    return pd.DataFrame(columns=["종목명", "종목코드", "매수단가", "수량"])

if 'temp_df' not in st.session_state:
    st.session_state.temp_df = load_portfolio()

# =========================================================
# 🚀 레이아웃 1: 실시간 성적표 (상단 배치)
# =========================================================
st.markdown("### 🚀 실시간 성적표")

valid_portfolio = st.session_state.temp_df.dropna(subset=['종목코드']).copy()

if not valid_portfolio.empty:
    with st.spinner("실시간 주가 분석 중..."):
        display_df = valid_portfolio.copy()
        display_df['종목코드'] = display_df['종목코드'].astype(str).apply(lambda x: x.zfill(6) if x.isdigit() else x)
        
        unique_tickers = tuple(display_df['종목코드'].unique())
        price_dict = fetch_multi_prices(unique_tickers)
        
        display_df['현재가'] = display_df['종목코드'].map(price_dict).fillna(0)
        display_df['평가금액'] = display_df['현재가'] * display_df['수량']
        display_df['평가손익'] = (display_df['현재가'] - display_df['매수단가']) * display_df['수량']
        display_df['수익률(%)'] = (display_df['평가손익'] / (display_df['매수단가'] * display_df['수량']) * 100).fillna(0)
        
        if '시장구분' in master_df.columns:
            m_info = master_df.set_index('종목코드')[['시장구분']]
            display_df = display_df.join(m_info, on='종목코드')
        else:
            display_df['시장구분'] = "KOSPI" # 기본값
        
        def make_links(r):
            m = "KOSDAQ" if "코스닥" in str(r.get('시장구분', '')) else "KOSPI"
            t_url = f"https://finance.naver.com/item/main.naver?code={r['종목코드']}#{m}:{r['종목코드']}"
            n_url = f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드']}#{r['종목명']}"
            return pd.Series([t_url, n_url])

        display_df[['티커_L', '종목명_L']] = display_df.apply(make_links, axis=1)

        total_buy = (display_df['매수단가'] * display_df['수량']).sum()
        total_val = display_df['평가금액'].sum()
        total_profit = display_df['평가손익'].sum()
        total_pct = (total_profit / total_buy * 100) if total_buy > 0 else 0
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 총 매수", f"{int(total_buy):,}원")
        c2.metric("📈 총 평가액", f"{int(total_val):,}원")
        c3.metric("손익금", f"{int(total_profit):,}원", delta=f"{int(total_profit):,}원")
        c4.metric("수익률", f"{total_pct:.2f}%", delta=f"{total_pct:.2f}%")
        
        def style_fn(df):
            styles = pd.DataFrame('', index=df.index, columns=df.columns)
            for c in ['수익률(%)', '평가손익']:
                styles[c] = df[c].apply(lambda x: 'color: #EF4444; font-weight:bold;' if x > 0 else ('color: #3B82F6; font-weight:bold;' if x < 0 else ''))
            return styles

        st.dataframe(
            display_df.style.apply(style_fn, axis=None),
            use_container_width=True, hide_index=True,
            column_order=['티커_L', '종목명_L', '수량', '매수단가', '현재가', '평가금액', '평가손익', '수익률(%)'],
            column_config={
                "티커_L": st.column_config.LinkColumn("티커", display_text=r"#(.+)"),
                "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"),
                "매수단가": st.column_config.NumberColumn(format="%,d"),
                "현재가": st.column_config.NumberColumn(format="%,d"),
                "평가금액": st.column_config.NumberColumn(format="%,d"),
                "평가손익": st.column_config.NumberColumn(format="%,d"),
                "수익률(%)": st.column_config.NumberColumn(format="%.2f%%"),
            }, height=450
        )
else:
    st.info("👇 아래에서 포트폴리오에 종목을 추가하시면 실시간 성적표가 나타납니다.")

st.markdown("---")

# =========================================================
# ⚙️ 레이아웃 2: 종목 추가 및 편집 (하단 배치)
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
                    new_row = pd.DataFrame([{"종목명": name, "종목코드": code, "매수단가": p, "수량": q}])
                    st.session_state.temp_df = pd.concat([st.session_state.temp_df, new_row], ignore_index=True)
                    st.session_state.temp_df.to_csv(PORTFOLIO_PATH, index=False, encoding='utf-8-sig')
                    st.rerun()

with col_file:
    with st.expander("📂 엑셀/CSV로 한꺼번에 넣기", expanded=True):
        up_file = st.file_uploader("파일 선택", type=['csv', 'xlsx'])
        if up_file:
            try:
                # 엑셀 업로드 시 인코딩 에러 방지
                if up_file.name.endswith('csv'): 
                    try: up_df = pd.read_csv(up_file, dtype={'종목코드': str}, encoding='utf-8-sig')
                    except: up_df = pd.read_csv(up_file, dtype={'종목코드': str}, encoding='cp949')
                else: 
                    up_df = pd.read_excel(up_file, dtype={'종목코드': str})
                
                if st.button("🚀 업로드 데이터 반영하기"):
                    up_df['종목코드'] = up_df['종목코드'].str.zfill(6)
                    if '종목명' not in up_df.columns:
                        name_map = master_df.set_index('종목코드')['종목명'].to_dict() if not master_df.empty else {}
                        up_df['종목명'] = up_df['종목코드'].map(name_map).fillna('미등록종목')
                    
                    # 필수 컬럼만 추출하여 반영
                    cols_to_keep = ["종목명", "종목코드", "매수단가", "수량"]
                    for c in cols_to_keep:
                        if c not in up_df.columns: up_df[c] = 0 if c in ['매수단가', '수량'] else ''
                    
                    st.session_state.temp_df = up_df[cols_to_keep]
                    st.session_state.temp_df.to_csv(PORTFOLIO_PATH, index=False, encoding='utf-8-sig')
                    st.success("업로드 완료!")
                    st.rerun()
            except Exception as e: 
                st.error(f"파일 양식이 맞지 않습니다. (필수: 종목코드, 매수단가, 수량)")

st.markdown("### 📝 포트폴리오 목록 편집")
edited_df = st.data_editor(
    st.session_state.temp_df,
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
    st.session_state.temp_df = edited_df.dropna(subset=['종목코드'])
    st.session_state.temp_df.to_csv(PORTFOLIO_PATH, index=False, encoding='utf-8-sig')
    st.rerun()
