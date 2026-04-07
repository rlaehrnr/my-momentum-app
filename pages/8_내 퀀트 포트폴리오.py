import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import yfinance as yf
import os

# --- [1. 페이지 설정] ---
st.set_page_config(page_title="내 포트폴리오", layout="wide")
st.markdown("""
    <style>
    .block-container { padding-top: 2rem !important; }
    .main-title { font-size: 1.8rem !important; font-weight: bold; margin-bottom: 1rem; color: #1F2937; }
    .summary-box { background-color: #F3F4F6; padding: 15px; border-radius: 10px; margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">💼 내 퀀트 포트폴리오 트래커</p>', unsafe_allow_html=True)
st.info("💡 엑셀(CSV) 파일을 업로드하거나, 아래 표의 빈칸을 클릭해 직접 종목코드와 매수단가를 입력/수정하세요.")

# --- [2. 🚨에러 방지🚨: 입력된 종목만 개별적으로 실시간 주가/정보 조회] ---
@st.cache_data(ttl=60) # 실시간 성격을 위해 1분마다 캐시 갱신
def fetch_portfolio_data(tickers):
    # 1. 저장된 로컬 모멘텀 데이터를 우선 뒤져서 종목명과 시가총액을 빠르게 찾습니다.
    local_info = {}
    for f in ['data/momentum_data.csv', 'data/momentum_data_daily.csv']:
        if os.path.exists(f):
            try:
                tmp = pd.read_csv(f, dtype={'종목코드': str})
                for _, row in tmp.iterrows():
                    code = str(row['종목코드']).zfill(6)
                    if code not in local_info:
                        local_info[code] = {
                            '종목명': row.get('종목명', code),
                            '시가총액': row.get('시가총액', 0) * 100000000  # 억 단위를 원 단위로 임시 복구
                        }
            except: pass

    results = []
    for code in tickers:
        code_str = str(code).zfill(6)
        name = code_str
        price = 0
        marcap = 0

        # 로컬 데이터에 있으면 이름과 시총 가져오기
        if code_str in local_info:
            name = local_info[code_str]['종목명']
            marcap = local_info[code_str]['시가총액']

        # 2. 현재가는 무조건 Naver 금융(fdr.DataReader)에서 실시간으로 긁어옵니다.
        try:
            df = fdr.DataReader(code_str, datetime.today() - timedelta(days=10))
            if not df.empty:
                price = int(df['Close'].iloc[-1])
        except:
            pass

        # 3. 로컬 파일에도 없는 신규 종목이면 야후 파이낸스에서 이름과 시총을 보조로 가져옵니다.
        if name == code_str:
            try:
                t = yf.Ticker(code_str + ".KS")
                inf = t.info
                if 'regularMarketPrice' not in inf:
                    t = yf.Ticker(code_str + ".KQ")
                    inf = t.info
                name = inf.get('shortName', inf.get('longName', code_str))
                if marcap == 0:
                    marcap = inf.get('marketCap', 0)
            except:
                pass

        results.append({
            '종목코드': code_str,
            '종목명': name,
            '현재가': price,
            '시가총액': marcap
        })
    return pd.DataFrame(results)


# --- [3. 입력부: 파일 업로드 or 직접 입력] ---
col1, col2 = st.columns([1, 2])

with col1:
    uploaded_file = st.file_uploader("📥 엑셀/CSV 업로드 (컬럼: 종목코드, 매수단가, 수량)", type=['csv', 'xlsx'])
    
    if uploaded_file:
        if uploaded_file.name.endswith('csv'):
            df_input = pd.read_csv(uploaded_file, dtype={'종목코드': str})
        else:
            df_input = pd.read_excel(uploaded_file, dtype={'종목코드': str})
    else:
        # 기본 입력 폼 (샘플 데이터)
        df_input = pd.DataFrame({
            "종목코드": ["005930", "000660", "035420"], 
            "매수단가": [75000, 160000, 180000],
            "수량": [100, 50, 30]
        })

with col2:
    st.markdown("### ✍️ 포트폴리오 편집")
    edited_df = st.data_editor(
        df_input, 
        num_rows="dynamic", 
        use_container_width=True,
        column_config={
            "종목코드": st.column_config.TextColumn("종목코드(6자리)", max_chars=6),
            "매수단가": st.column_config.NumberColumn("매수단가(원)", format="%,d", min_value=0),
            "수량": st.column_config.NumberColumn("수량(주)", format="%,d", min_value=1)
        }
    )

# --- [4. 계산 및 결과 출력부] ---
st.markdown("---")

if st.button("🔄 실시간 수익률 계산하기", type="primary"):
    with st.spinner("실시간 주가 및 시가총액을 불러오는 중..."):
        my_portfolio = edited_df.dropna(subset=['종목코드']).copy()
        my_portfolio['종목코드'] = my_portfolio['종목코드'].astype(str).str.zfill(6)
        
        # 입력된 종목코드만 실시간으로 데이터 조회 (에러 원천 차단)
        tickers_to_fetch = my_portfolio['종목코드'].unique()
        live_data_df = fetch_portfolio_data(tickers_to_fetch)
        
        # 포트폴리오와 실시간 데이터 병합
        merged = pd.merge(my_portfolio, live_data_df, on='종목코드', how='left')
        merged = merged.dropna(subset=['현재가'])
        
        # 계산 로직
        merged['수익률(%)'] = merged.apply(lambda x: ((x['현재가'] - x['매수단가']) / x['매수단가'] * 100) if x['매수단가'] > 0 else 0, axis=1)
        merged['평가손익'] = (merged['현재가'] - merged['매수단가']) * merged.get('수량', 1)
        merged['평가금액'] = merged['현재가'] * merged.get('수량', 1)
        merged['시가총액(억)'] = (merged['시가총액'] / 100000000).fillna(0).astype(int)
        
        # 링크 생성
        merged['통합티커_L'] = merged.apply(lambda r: f"https://finance.naver.com/item/main.naver?code={r['종목코드']}#KOSPI:{r['종목코드']}", axis=1)
        merged['종목명_L'] = merged.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드']}#{r['종목명']}", axis=1)
        
        # 총 요약 수치 계산
        total_invested = (merged['매수단가'] * merged.get('수량', 1)).sum()
        total_current = merged['평가금액'].sum()
        total_profit = merged['평가손익'].sum()
        total_profit_pct = (total_profit / total_invested * 100) if total_invested > 0 else 0
        
        # 요약 박스 렌더링
        profit_color = "#E8F5E9" if total_profit > 0 else "#FFEBEE"
        profit_text = "#2E7D32" if total_profit > 0 else "#C62828"
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 총 매수금액", f"{int(total_invested):,}원")
        c2.metric("📈 총 평가금액", f"{int(total_current):,}원")
        c3.metric("총 평가손익", f"{int(total_profit):,}원")
        c4.markdown(f"""
        <div style="background-color: {profit_color}; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid {profit_text};">
            <p style="margin: 0; font-size: 12px; color: {profit_text}; font-weight: bold;">총 수익률</p>
            <h3 style="margin: 0; color: {profit_text};">{total_profit_pct:.2f}%</h3>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        def style_portfolio(df):
            styles = pd.DataFrame('', index=df.index, columns=df.columns)
            for col in ['수익률(%)', '평가손익']:
                if col in df.columns:
                    styles[col] = df[col].apply(lambda x: 'color: #EF4444; font-weight: bold;' if x > 0 else ('color: #3B82F6; font-weight: bold;' if x < 0 else ''))
            return styles

        out_config = {
            "통합티커_L": st.column_config.LinkColumn("티커", display_text=r"#(.+)"), 
            "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), 
            "매수단가": st.column_config.NumberColumn("매수단가", format="%,d원"),
            "현재가": st.column_config.NumberColumn("현재가", format="%,d원"),
            "수량": st.column_config.NumberColumn("수량", format="%,d주"),
            "평가금액": st.column_config.NumberColumn("평가금액", format="%,d원"),
            "평가손익": st.column_config.NumberColumn("평가손익", format="%,d원"),
            "수익률(%)": st.column_config.NumberColumn("수익률(%)", format="%.2f%%"),
            "시가총액(억)": st.column_config.NumberColumn("시가총액(억)", format="%,d")
        }

        st.dataframe(
            merged.style.apply(style_portfolio, axis=None), 
            use_container_width=True, 
            hide_index=True,
            column_order=['통합티커_L', '종목명_L', '시가총액(억)', '수량', '매수단가', '현재가', '평가금액', '평가손익', '수익률(%)'],
            column_config=out_config,
            height=500
        )
