import streamlit as st
import pandas as pd
import FinanceDataReader as fdr

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

# --- [2. KRX 전체 데이터 캐싱 (현재가, 시가총액, 종목명 가져오기 용도)] ---
@st.cache_data(ttl=600) # 10분마다 갱신
def get_krx_data():
    df = fdr.StockListing('KRX')
    # 라이브러리 버전에 따라 Code 또는 Symbol로 나옴
    code_col = 'Code' if 'Code' in df.columns else 'Symbol'
    df = df.rename(columns={code_col: '종목코드', 'Name': '종목명', 'Close': '현재가', 'Marcap': '시가총액'})
    df['종목코드'] = df['종목코드'].astype(str).str.zfill(6)
    return df[['종목코드', '종목명', '현재가', '시가총액']]

krx_df = get_krx_data()

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
    # 사용자가 화면에서 직접 행을 추가/삭제하고 숫자를 수정할 수 있는 에디터
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
        # 입력된 종목코드 보정
        my_portfolio = edited_df.dropna(subset=['종목코드']).copy()
        my_portfolio['종목코드'] = my_portfolio['종목코드'].astype(str).str.zfill(6)
        
        # KRX 데이터와 병합하여 현재가, 시가총액, 이름 가져오기
        merged = pd.merge(my_portfolio, krx_df, on='종목코드', how='left')
        
        # 값이 없는(상장폐지나 오타) 종목 제외
        merged = merged.dropna(subset=['현재가'])
        
        # 계산 로직
        merged['수익률(%)'] = ((merged['현재가'] - merged['매수단가']) / merged['매수단가']) * 100
        merged['평가손익'] = (merged['현재가'] - merged['매수단가']) * merged.get('수량', 1)
        merged['평가금액'] = merged['현재가'] * merged.get('수량', 1)
        merged['시가총액(억)'] = (merged['시가총액'] / 100000000).astype(int)
        
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
        
        # 결과 테이블 렌더링 (스타일 적용)
        def style_portfolio(df):
            styles = pd.DataFrame('', index=df.index, columns=df.columns)
            # 수익률과 평가손익에 색상 적용 (빨강=수익, 파랑=손실)
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
