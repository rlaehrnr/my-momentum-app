import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import yfinance as yf
import os

# --- [1. 설정 및 경로] ---
st.set_page_config(page_title="내 포트폴리오", layout="wide")
PORTFOLIO_PATH = 'data/my_portfolio.csv'

# 폴더가 없으면 생성
if not os.path.exists('data'):
    os.makedirs('data')

st.markdown("""
    <style>
    .block-container { padding-top: 2rem !important; }
    .main-title { font-size: 1.8rem !important; font-weight: bold; margin-bottom: 1rem; color: #1F2937; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">💼 내 퀀트 포트폴리오 관리</p>', unsafe_allow_html=True)

# --- [2. 데이터 수집 함수 (캐시 적용)] ---
@st.cache_data(ttl=60)
def fetch_live_data(tickers):
    if not tickers:
        return pd.DataFrame()
    
    # 로컬 파일에서 이름/시총 정보 백업용으로 읽기
    local_info = {}
    for f in ['data/momentum_data.csv', 'data/momentum_data_daily.csv']:
        if os.path.exists(f):
            try:
                tmp = pd.read_csv(f, dtype={'종목코드': str})
                for _, row in tmp.iterrows():
                    code = str(row['종목코드']).zfill(6)
                    if code not in local_info:
                        local_info[code] = {'Name': row.get('종목명', code), 'Marcap': row.get('시가총액', 0) * 100000000}
            except: pass

    results = []
    for code in tickers:
        code_str = str(code).zfill(6)
        name, price, marcap = code_str, 0, 0
        
        if code_str in local_info:
            name = local_info[code_str]['Name']
            marcap = local_info[code_str]['Marcap']

        try:
            # 실시간 주가 (최근 5일치 중 마지막 데이터)
            df = fdr.DataReader(code_str, datetime.today() - timedelta(days=7))
            if not df.empty:
                price = int(df['Close'].iloc[-1])
        except: pass

        results.append({'종목코드': code_str, '종목명': name, '현재가': price, '시가총액_raw': marcap})
    
    return pd.DataFrame(results)

# --- [3. 데이터 로드 로직] ---
# 저장된 파일이 있으면 불러오고, 없으면 기본 양식을 만듭니다.
if os.path.exists(PORTFOLIO_PATH):
    df_load = pd.read_csv(PORTFOLIO_PATH, dtype={'종목코드': str})
else:
    df_load = pd.DataFrame(columns=["종목코드", "매수단가", "수량"])

# --- [4. 화면 레이아웃: 편집 및 저장] ---
col_edit, col_info = st.columns([1.2, 2])

with col_edit:
    st.subheader("📝 포트폴리오 편집")
    # data_editor를 사용하여 직접 수정/추가/삭제
    edited_df = st.data_editor(
        df_load, 
        num_rows="dynamic", 
        use_container_width=True,
        key="portfolio_editor",
        column_config={
            "종목코드": st.column_config.TextColumn("종목코드", help="6자리 숫자를 입력하세요"),
            "매수단가": st.column_config.NumberColumn("매수단가", format="%,d"),
            "수량": st.column_config.NumberColumn("수량", format="%,d")
        }
    )
    
    save_btn = st.button("💾 포트폴리오 저장하기", use_container_width=True, type="primary")
    
    if save_btn:
        # 유효한 종목코드만 필터링하여 저장
        save_df = edited_df.dropna(subset=['종목코드']).copy()
        save_df['종목코드'] = save_df['종목코드'].astype(str).str.zfill(6)
        save_df.to_csv(PORTFOLIO_PATH, index=False, encoding='utf-8-sig')
        st.success("✅ 저장 완료! 이제 '조회' 버튼을 누르거나 페이지를 새로고침하세요.")

# --- [5. 결과 출력: 실시간 계산] ---
st.markdown("---")
if st.button("🔄 실시간 수익률 조회하기", use_container_width=True):
    my_portfolio = edited_df.dropna(subset=['종목코드']).copy()
    if my_portfolio.empty:
        st.warning("먼저 종목을 입력하고 저장하세요.")
    else:
        with st.spinner("실시간 데이터를 불러오는 중..."):
            my_portfolio['종목코드'] = my_portfolio['종목코드'].astype(str).str.zfill(6)
            tickers_tuple = tuple(my_portfolio['종목코드'].unique())
            
            live_info = fetch_live_data(tickers_tuple)
            
            # 데이터 병합 및 계산
            merged = pd.merge(my_portfolio, live_info, on='종목코드', how='left')
            merged = merged.dropna(subset=['현재가'])
            
            merged['평가금액'] = merged['현재가'] * merged['수량']
            merged['평가손익'] = (merged['현재가'] - merged['매수단가']) * merged['수량']
            merged['수익률(%)'] = (merged['평가손익'] / (merged['매수단가'] * merged['수량']) * 100).fillna(0)
            merged['시가총액(억)'] = (merged['시가총액_raw'] / 100000000).fillna(0).astype(int)
            
            # 네이버 링크
            merged['티커_L'] = merged.apply(lambda r: f"https://finance.naver.com/item/main.naver?code={r['종목코드']}#{r['종목코드']}", axis=1)
            merged['종목명_L'] = merged.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드']}#{r['종목명']}", axis=1)
            
            # 요약 수치
            total_buy = (merged['매수단가'] * merged['수량']).sum()
            total_val = merged['평가금액'].sum()
            total_profit = merged['평가손익'].sum()
            total_pct = (total_profit / total_buy * 100) if total_buy > 0 else 0
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("💰 총 매수금액", f"{int(total_buy):,}원")
            c2.metric("📈 총 평가금액", f"{int(total_val):,}원")
            c3.metric("평가손익", f"{int(total_profit):,}원", delta=f"{int(total_profit):,}원")
            c4.metric("총 수익률", f"{total_pct:.2f}%", delta=f"{total_pct:.2f}%")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # 스타일 및 출력
            def style_result(df):
                styles = pd.DataFrame('', index=df.index, columns=df.columns)
                if '수익률(%)' in df.columns:
                    styles['수익률(%)'] = df['수익률(%)'].apply(lambda x: 'color: #EF4444; font-weight:bold;' if x > 0 else ('color: #3B82F6; font-weight:bold;' if x < 0 else ''))
                if '평가손익' in df.columns:
                    styles['평가손익'] = df['평가손익'].apply(lambda x: 'color: #EF4444;' if x > 0 else ('color: #3B82F6;' if x < 0 else ''))
                return styles

            out_cfg = {
                "티커_L": st.column_config.LinkColumn("티커", display_text=r"#(.+)"),
                "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"),
                "매수단가": st.column_config.NumberColumn("매수단가", format="%,d원"),
                "현재가": st.column_config.NumberColumn("현재가", format="%,d원"),
                "평가금액": st.column_config.NumberColumn("평가금액", format="%,d원"),
                "평가손익": st.column_config.NumberColumn("평가손익", format="%,d원"),
                "수익률(%)": st.column_config.NumberColumn("수익률(%)", format="%.2f%%"),
                "시가총액(억)": st.column_config.NumberColumn("시총(억)", format="%,d")
            }
            
            st.dataframe(
                merged.style.apply(style_result, axis=None),
                use_container_width=True, hide_index=True,
                column_order=['티커_L', '종목명_L', '시가총액(억)', '수량', '매수단가', '현재가', '평가금액', '평가손익', '수익률(%)'],
                column_config=out_cfg, height=600
            )

# --- [6. 백업용 다운로드] ---
if os.path.exists(PORTFOLIO_PATH):
    with st.sidebar:
        st.markdown("---")
        with open(PORTFOLIO_PATH, "rb") as file:
            st.download_button(
                label="📥 내 포트폴리오 파일로 내보내기",
                data=file,
                file_name=f"my_portfolio_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
