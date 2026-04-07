import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import yfinance as yf
import os

# --- [1. 설정 및 경로] ---
st.set_page_config(page_title="내 포트폴리오", layout="wide")
PORTFOLIO_PATH = 'data/my_portfolio.csv'

if not os.path.exists('data'):
    os.makedirs('data')

st.markdown("""
    <style>
    .block-container { padding-top: 2rem !important; }
    .main-title { font-size: 1.8rem !important; font-weight: bold; margin-bottom: 1rem; color: #1F2937; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">💼 내 퀀트 포트폴리오 관리</p>', unsafe_allow_html=True)

# --- [2. 💡 한국 전체 종목 리스트 캐싱 (검색창 용도)] ---
@st.cache_data(ttl=86400) # 하루에 한 번만 갱신
def get_krx_master():
    try:
        df = fdr.StockListing('KRX')
        code_col = 'Code' if 'Code' in df.columns else 'Symbol'
        df['종목코드'] = df[code_col].astype(str).str.zfill(6)
        # 드롭다운에 보여줄 포맷: [005930] 삼성전자
        df['검색명'] = "[" + df['종목코드'] + "] " + df['Name']
        return df[['종목코드', 'Name', '검색명']]
    except:
        return pd.DataFrame(columns=['종목코드', 'Name', '검색명'])

master_df = get_krx_master()
search_options = ["🔍 종목을 검색하세요 (예: 삼성)"] + master_df['검색명'].tolist()

# --- [3. 실시간 데이터 수집 함수] ---
@st.cache_data(ttl=60)
def fetch_live_data(tickers):
    if not tickers:
        return pd.DataFrame()
    
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
            df = fdr.DataReader(code_str, datetime.today() - timedelta(days=10))
            if not df.empty:
                price = int(df['Close'].iloc[-1])
        except: pass

        results.append({'종목코드': code_str, '종목명': name, '현재가': price, '시가총액_raw': marcap})
    
    return pd.DataFrame(results)

# --- [4. 데이터 로드] ---
if os.path.exists(PORTFOLIO_PATH):
    df_load = pd.read_csv(PORTFOLIO_PATH, dtype={'종목코드': str})
else:
    df_load = pd.DataFrame(columns=["종목코드", "매수단가", "수량"])

# --- [5. UI 레이아웃 (검색창 & 편집기)] ---
col_search, col_edit = st.columns([1.2, 2])

with col_search:
    st.markdown("### 🔎 종목명으로 자동 추가")
    st.info("입력창을 클릭하고 '삼성'이나 '현대'를 쳐보세요!")
    
    # 💡 폼을 사용하여 종목 검색 및 추가
    with st.form("add_stock_form", clear_on_submit=True):
        selected_stock = st.selectbox("종목 선택", options=search_options)
        
        c1, c2 = st.columns(2)
        buy_p = c1.number_input("매수단가(원)", min_value=0, step=100)
        qty = c2.number_input("수량(주)", min_value=1, step=1)
        
        add_btn = st.form_submit_button("➕ 포트폴리오에 추가", use_container_width=True)
        
        if add_btn:
            if selected_stock == search_options[0]:
                st.warning("종목을 검색해서 선택해주세요!")
            else:
                # "[005930] 삼성전자" 에서 "005930"만 추출
                extracted_code = selected_stock[1:7]
                new_row = pd.DataFrame([{"종목코드": extracted_code, "매수단가": buy_p, "수량": qty}])
                df_load = pd.concat([df_load, new_row], ignore_index=True)
                df_load.to_csv(PORTFOLIO_PATH, index=False, encoding='utf-8-sig')
                st.rerun() # 추가 즉시 화면 새로고침

with col_edit:
    st.markdown("### 📝 포트폴리오 목록 (수정/삭제 가능)")
    # 표에서 직접 숫자를 바꾸거나, 행을 선택해 삭제(Delete 키)할 수 있습니다.
    edited_df = st.data_editor(
        df_load, 
        num_rows="dynamic", 
        use_container_width=True,
        key="portfolio_editor",
        column_config={
            "종목코드": st.column_config.TextColumn("종목코드", help="미국 티커는 표에서 직접 입력하세요"),
            "매수단가": st.column_config.NumberColumn("매수단가", format="%,d"),
            "수량": st.column_config.NumberColumn("수량", format="%,d")
        }
    )
    
    save_btn = st.button("💾 표 변경사항 저장", use_container_width=True)
    if save_btn:
        save_df = edited_df.dropna(subset=['종목코드']).copy()
        save_df['종목코드'] = save_df['종목코드'].astype(str).apply(lambda x: x.zfill(6) if x.isdigit() else x)
        save_df.to_csv(PORTFOLIO_PATH, index=False, encoding='utf-8-sig')
        st.success("✅ 표 수정 내역이 저장되었습니다.")

# --- [6. 결과 출력: 실시간 계산] ---
st.markdown("---")
if st.button("🔄 실시간 수익률 조회하기", use_container_width=True, type="primary"):
    my_portfolio = edited_df.dropna(subset=['종목코드']).copy()
    if my_portfolio.empty:
        st.warning("먼저 종목을 추가해주세요.")
    else:
        with st.spinner("실시간 데이터를 불러오는 중..."):
            my_portfolio['종목코드'] = my_portfolio['종목코드'].astype(str).apply(lambda x: x.zfill(6) if x.isdigit() else x)
            tickers_tuple = tuple(my_portfolio['종목코드'].unique())
            
            live_info = fetch_live_data(tickers_tuple)
            
            merged = pd.merge(my_portfolio, live_info, on='종목코드', how='left')
            merged = merged.dropna(subset=['현재가'])
            
            merged['평가금액'] = merged['현재가'] * merged['수량']
            merged['평가손익'] = (merged['현재가'] - merged['매수단가']) * merged['수량']
            merged['수익률(%)'] = (merged['평가손익'] / (merged['매수단가'] * merged['수량']) * 100).fillna(0)
            merged['시가총액(억)'] = (merged['시가총액_raw'] / 100000000).fillna(0).astype(int)
            
            merged['티커_L'] = merged.apply(lambda r: f"https://finance.naver.com/item/main.naver?code={r['종목코드']}#{r['종목코드']}", axis=1)
            merged['종목명_L'] = merged.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드']}#{r['종목명']}", axis=1)
            
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

# --- [7. 백업] ---
if os.path.exists(PORTFOLIO_PATH):
    with st.sidebar:
        st.markdown("---")
        with open(PORTFOLIO_PATH, "rb") as file:
            st.download_button(
                label="📥 포트폴리오 엑셀 다운로드",
                data=file,
                file_name=f"my_portfolio_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
