import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os

# 1. 페이지 설정
st.set_page_config(page_title="S&P 500 모멘텀 순위", layout="wide")

# CSS: 초밀착 레이아웃
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem !important; }
    h1 { font-size: 2rem !important; font-weight: 800; margin-bottom: 10px; }
    [data-testid="stTable"] { margin-bottom: -25px; }
    .stTabs [data-baseweb="tab"] { font-size: 18px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# 지수 비교 하이라이트 함수
def highlight_sp500(row, idx_df):
    target = 'S&P 500'
    styles = [''] * len(row)
    if target in idx_df.index:
        idx_r = idx_df.loc[target]
        for col in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
            if col in row.index:
                col_idx = row.index.get_loc(col)
                if row[col] < idx_r[col]:
                    styles[col_idx] = 'background-color: #0047AB; color: #FFFFFF; font-weight: bold;'
    return styles

# 미국 대통령 집권 연차 필터 (2026년 6년차)
def get_pres_status():
    now = datetime.now()
    year, month = now.year, now.month
    cycle_year = (year - 2020) % 8
    if cycle_year == 0: cycle_year = 8
    exclusion_rules = {
        1: [2, 3, 8], 2: [1, 4, 6, 9], 3: [9], 4: [10],
        5: [2, 3, 8], 6: [7, 8, 9], 7: [9], 8: [1, 2, 8, 9]
    }
    is_excluded = month in exclusion_rules.get(cycle_year, [])
    status = "🔴 현재는 현금 비중 확대를 권장합니다" if is_excluded else "🟢 현재는 적극 투자하기 좋은 달입니다"
    return cycle_year, status

@st.cache_data(ttl=3600)
def get_idx_us(target_date=None):
    indices = {'S&P 500': 'US500', 'NASDAQ': 'IXIC'}
    today = datetime.today()
    res = []
    for name, code in indices.items():
        try:
            df = fdr.DataReader(code, today - pd.DateOffset(months=16), today)
            curr_val = df.loc[df.index <= target_date]['Close'].iloc[-1] if target_date else df['Close'].iloc[-1]
            last_idx_date = df.index[df.index <= (target_date if target_date else today)][-1]
            def get_ret(m):
                ref_day = (last_idx_date.replace(day=1) - pd.DateOffset(months=m-1)) - timedelta(days=1)
                p_df = df[df.index <= ref_day]
                return round((curr_val - p_df['Close'].iloc[-1]) / p_df['Close'].iloc[-1] * 100, 2) if not p_df.empty else 0.0
            res.append({'시장': name, '현재가': round(curr_val, 1), '1개월(%)': get_ret(1), '3개월(%)': get_ret(3), '6개월(%)': get_ret(6), '12개월(%)': get_ret(12)})
        except: pass
    return pd.DataFrame(res).set_index('시장')

# ⭐ 네이버 차트 마스터 링크 함수 (NYSE의 .K/.N 구분 해결)
def get_naver_master_link(row):
    symbol = str(row['종목코드']).strip().upper().replace('.', '_')
    market = str(row['시장']).strip().upper()
    
    # 1. 나스닥은 무조건 .O
    if 'NASDAQ' in market:
        suffix = '.O'
    # 2. 뉴욕거래소(NYSE) 처리
    else:
        # 💡 네이버에서 .N을 사용하는 '비교적 최신 상장' NYSE 종목들
        # (여기에 없는 NYSE 종목은 자동으로 .K로 연결됩니다)
        new_nyse_list = ['V', 'MA', 'SQ', 'SNAP', 'UBER', 'LYFT', 'PINS', 'NET'] 
        if symbol in new_nyse_list:
            suffix = '.N'
        else:
            suffix = '.K' # CIEN, KO, F, GE 등 대부분의 우량주는 .K
            
    return f"https://m.stock.naver.com/fchart/foreign/stock/{symbol}{suffix}#{row['종목명']}"

# 상단 타이틀
st.title("🇺🇸 S&P 500 모멘텀 순위")
cy, status = get_pres_status()
st.info(f"**미국 집권 {cy}년차** | {status}")

tab1, tab2 = st.tabs(["📅 전월 말일 기준", "🕒 오늘(데일리) 기준"])

# 공통 컬럼 설정
common_config = {
    "시장": st.column_config.TextColumn("거래소"),
    "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), 
    "기준가": st.column_config.NumberColumn("기준가", format="$ %.2f"),
    "1개월(%)": st.column_config.NumberColumn("1M (%)", format="%.2f%%"),
    "3개월(%)": st.column_config.NumberColumn("3M (%)", format="%.2f%%"),
    "6개월(%)": st.column_config.NumberColumn("6M (%)", format="%.2f%%"),
    "12개월(%)": st.column_config.NumberColumn("12M (%)", format="%.2f%%"),
    "모멘텀스코어": st.column_config.NumberColumn("스코어", format="%.2f"),
}

# --- [탭 1 / 탭 2 공통 적용] ---
for tab, file_path, rank_col_name in zip([tab1, tab2], 
                                         ['data/momentum_data_sp500.csv', 'data/momentum_data_daily_sp500.csv'],
                                         ['전달순위', '전월순위']):
    with tab:
        if os.path.exists(file_path):
            df = pd.read_csv(file_path, dtype={'종목코드': str})
            # (중략된 순위 비교 및 지수 테이블 로직은 이전과 동일하게 유지)
            # ...
            # 핵심은 아래의 링크 적용 부분입니다.
            df['종목명_L'] = df.apply(get_naver_master_link, axis=1)
            
            # (데이터프레임 출력 부분)
            st.dataframe(df, column_config=common_config, ...)
