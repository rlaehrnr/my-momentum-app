import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os

# 1. 페이지 설정
st.set_page_config(page_title="미국 모멘텀 순위", layout="wide")

# CSS: 레이아웃 최적화
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem !important; }
    h1 { font-size: 2.0rem !important; font-weight: 800; margin-bottom: 10px; }
    [data-testid="stTable"] { margin-bottom: -25px; }
    .stTabs [data-baseweb="tab"] { font-size: 18px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# 지수 비교 하이라이트 함수 (NYSE는 S&P500, NASDAQ은 나스닥 지수와 비교)
def highlight_us(row, idx_df):
    m_map = {'NYSE': 'S&P 500', 'NASDAQ': 'NASDAQ'}
    target = m_map.get(row['시장'])
    styles = [''] * len(row)
    if target in idx_df.index:
        idx_r = idx_df.loc[target]
        for col in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
            if col in row.index:
                col_idx = row.index.get_loc(col)
                if row[col] < idx_r[col]:
                    styles[col_idx] = 'background-color: #0047AB; color: #FFFFFF; font-weight: bold;'
    return styles

# 미국 대통령 집권 연차 필터 (2026년 = 6년차)
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

# 상단 타이틀 및 필터 정보
st.title("🇺🇸 미국 시총상위 모멘텀")
cy, status = get_pres_status()
st.info(f"**미국 집권 {cy}년차** | {status}")

tab1, tab2 = st.tabs(["📅 전월 말일 기준", "🕒 오늘(데일리) 기준"])

# 공통 컬럼 설정
common_config = {
    "통합티커": st.column_config.TextColumn("티커"),
    "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), 
    "기준가": st.column_config.NumberColumn("기준가", format="$ %.2f"),
    "1개월(%)": st.column_config.NumberColumn("1M (%)", format="%.2f%%"),
    "3개월(%)": st.column_config.NumberColumn("3M (%)", format="%.2f%%"),
    "6개월(%)": st.column_config.NumberColumn("6M (%)", format="%.2f%%"),
    "12개월(%)": st.column_config.NumberColumn("12M (%)", format="%.2f%%"),
    "모멘텀스코어": st.column_config.NumberColumn("스코어", format="%.2f"),
}

# --- [탭 1: 월말 고정 데이터] ---
with tab1:
    f_us = 'data/momentum_data_us.csv'
    if os.path.exists(f_us):
        df_us = pd.read_csv(f_us, dtype={'종목코드': str})
        b_date_str = df_us['기준일(월말)'].iloc[0]
        st.subheader(f"📅 월말 기준 데이터 (기준일: {b_date_str})")
        
        idx_us = get_idx_us(pd.to_datetime(b_date_str))
        if not idx_us.empty:
            st.table(idx_us.reset_index().assign(**{c: idx_us.reset_index()[c].map('{:.1f}'.format) for c in idx_us.columns if c != '시장'}))
        
        # [지지난달 순위 대조]
        try:
            curr_dt = datetime.strptime(b_date_str, '%Y-%m-%d')
            prev_month_dt = curr_dt.replace(day=1) - timedelta(days=1)
            prev_ym = prev_month_dt.strftime('%Y_%m')
            f_prev_archive = f'archive_us/momentum_us_{prev_ym}.csv' # 미국 아카이브 폴더
            
            if os.path.exists(f_prev_archive):
                df_prev = pd.read_csv(f_prev_archive, dtype={'종목코드': str})
                prev_rank_map = {code: i+1 for i, code in enumerate(df_prev['종목코드'])}
                df_us['전달순위'] = df_us['종목코드'].map(prev_rank_map).fillna("⭐ NEW")
                df_us['전달순위'] = df_us['전달순위'].apply(lambda x: f"{x}위" if isinstance(x, int) else x)
            else: df_us['전달순위'] = "기록 없음"
        except: df_us['전달순위'] = "-"

        st.markdown("---")
        df_us.index = range(1, len(df_us) + 1)
        df_us['통합티커'] = df_us['시장'] + ":" + df_us['종목코드']
        df_us['종목명_L'] = df_us.apply(lambda r: f"https://finance.yahoo.com/chart/{r['종목코드'].replace('.', '-')}#{r['종목명']}", axis=1)

        st.dataframe(
            df_us.style.apply(highlight_us, idx_df=idx_us, axis=1),
            use_container_width=True, height=600,
            column_order=['통합티커', '종목명_L', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어', '전달순위'],
            column_config={**common_config, "전달순위": st.column_config.TextColumn("전달 순위")}
        )
    else: st.warning("미국 월말 데이터 파일이 없습니다.")

# --- [탭 2: 데일리 데이터] ---
with tab2:
    f_daily_us = 'data/momentum_data_daily_us.csv'
    f_monthly_ref = 'data/momentum_data_us.csv' # 비교용 월말 데이터
    
    if os.path.exists(f_daily_us):
        df_d_us = pd.read_csv(f_daily_us, dtype={'종목코드': str})
        
        # [전월 순위 대조]
        if os.path.exists(f_monthly_ref):
            df_m_ref = pd.read_csv(f_monthly_ref, dtype={'종목코드': str})
            rank_map = {code: i+1 for i, code in enumerate(df_m_ref['종목코드'])}
            df_d_us['전월순위'] = df_d_us['종목코드'].map(rank_map).fillna("⭐ NEW")
            df_d_us['전월순위'] = df_d_us['전월순위'].apply(lambda x: f"{x}위" if isinstance(x, int) else x)
        else: df_d_us['전월순위'] = "-"

        d_date = df_d_us['기준일'].iloc[0]
        st.subheader(f"🕒 미국 데일리 실시간 (기준일: {d_date})")
        
        idx_now = get_idx_us() 
        if not idx_now.empty:
            st.table(idx_now.reset_index().assign(**{c: idx_now.reset_index()[c].map('{:.1f}'.format) for c in idx_now.columns if c != '시장'}))
        
        st.markdown("---")
        df_d_us.index = range(1, len(df_d_us) + 1)
        df_d_us['통합티커'] = df_d_us['시장'] + ":" + df_d_us['종목코드']
        df_d_us['종목명_L'] = df_d_us.apply(lambda r: f"https://finance.yahoo.com/chart/{r['종목코드'].replace('.', '-')}#{r['종목명']}", axis=1)

        st.dataframe(
            df_d_us.style.apply(highlight_us, idx_df=idx_now, axis=1),
            use_container_width=True, height=600,
            column_order=['통합티커', '종목명_L', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어', '전월순위'],
            column_config={**common_config, "전월순위": st.column_config.TextColumn("전월 순위")}
        )
    else: st.warning("미국 데일리 데이터 파일이 없습니다.")
