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

# --- [3. 실시간 가격 수집 함수] ---
@st.cache_data(ttl=60)
def fetch_multi_prices(tickers):
    if not tickers: return {}
    price_map = {}
    
    for t in tickers:
        val = 0
        code_str = str(t).zfill(6) if str(t).isdigit() else str(t)
        
        try:
            df = fdr.DataReader(code_str, datetime.today() - timedelta(days=10))
            if not df.empty:
                val = int(df['Close'].iloc[-1])
        except:
            pass
            
        if val == 0:
            try:
                yf_t = code_str + ".KS" if code_str.isdigit() else code_str
                hist = yf.Ticker(yf_t).history(period="5d")
                if not hist.empty:
                    val = int(hist['Close'].iloc[-1])
                elif code_str.isdigit(): 
                    hist_kq = yf.Ticker(code_str + ".KQ").history(period="5d")
                    if not hist_kq.empty:
                        val = int(hist_kq['Close'].iloc[-1])
            except:
                pass
                
        price_map[t] = val
            
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
    with st.spinner("실시간 주가 분석 중... (수 초 소요)"):
        display_df = valid_portfolio.copy()
        display_df['종목코드'] = display_df['종목코드'].astype(str).apply(lambda x: x.zfill(6) if x.isdigit() else x)
        
        unique_tickers = tuple(display_df['종목코드'].unique())
        price_dict = fetch_multi_prices(unique_tickers)
        
        display_df['현재가'] = display_df['종목코드'].map(price_dict).fillna(0)
        display_df['평가금액'] = display_df['현재가'] * display_df['수량']
        display_df['평가손익'] = (display_df['현재가'] - display_df['매수단가']) * display_df['수량']
        
        display_df['수익률(%)'] = display_df.apply(
            lambda r: (r['평가손익'] / (r['매수단가'] * r['수량']) * 100) if (r['매수단가'] * r['수량']) > 0 else 0, 
            axis=1
        )
        
        if '시장구분' in master_df.columns:
            m_info = master_df.set_index('종목코드')[['시장구분']]
            display_df = display_df.join(m_info, on='종목코드')
        else:
            display_df['시장구분'] = "KOSPI"
        
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
        up_file = st.file_uploader("파일 양식 (종목코드, 매수단가, 수량)", type=['csv', 'xlsx'])
        if up_file:
            try:
                # 💡 강철 방어: 파일 읽을 때 자료형을 지정하지 않고 일단 모두 읽어옵니다.
                if up_file.name.endswith('csv'): 
                    try: up_df = pd.read_csv(up_file, encoding='utf-8-sig')
                    except: up_df = pd.read_csv(up_file, encoding='cp949')
                else: 
                    up_df = pd.read_excel(up_file)
                
                # 컬럼명 공백 제거 (사용자 실수 방지)
                up_df.columns = up_df.columns.str.strip()
                
                if st.button("🚀 업로드 데이터 반영하기"):
                    if '종목코드' not in up_df.columns:
                        st.error("엑셀 파일 가장 윗줄에 '종목코드'라는 글자가 꼭 있어야 합니다!")
                    else:
                        # 엑셀이 5930.0 처럼 읽어오는 것 방지
                        up_df['종목코드'] = up_df['종목코드'].astype(str).str.replace(r'\.0$', '', regex=True)
                        up_df['종목코드'] = up_df['종목코드'].apply(lambda x: x.zfill(6) if x.isdigit() else x)
                        
                        if '종목명' not in up_df.columns:
                            name_map = master_df.set_index('종목코드')['종목명'].to_dict() if not master_df.empty else {}
                            up_df['종목명'] = up_df['종목코드'].map(name_map).fillna('미등록종목')
                        
                        cols_to_keep = ["종목명", "종목코드", "매수단가", "수량"]
                        for c in cols_to_keep:
                            if c not in up_df.columns: 
                                up_df[c] = 0 if c in ['매수단가', '수량'] else ''
                        
                        # 숫자 데이터 강제 변환 (문자 섞여있어도 에러 안 나게)
                        up_df['매수단가'] = pd.to_numeric(up_df['매수단가'], errors='coerce').fillna(0)
                        up_df['수량'] = pd.to_numeric(up_df['수량'], errors='coerce').fillna(0)
                        
                        st.session_state.temp_df = up_df[cols_to_keep]
                        st.session_state.temp_df.to_csv(PORTFOLIO_PATH, index=False, encoding='utf-8-sig')
                        st.success("✅ 파일 업로드가 완벽하게 처리되었습니다!")
                        st.rerun()
            except Exception as e: 
                st.error(f"알 수 없는 오류가 발생했습니다. 헤더 이름을 확인해 주세요.")

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
