import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os

# 1. 페이지 설정
st.set_page_config(page_title="S&P 500 모멘텀 순위", layout="wide")

# CSS: 레이아웃 최적화 (초밀착)
st.markdown("""
    <style>
    .block-container { padding-top: 2.5rem !important; }
    h1 { font-size: 2rem !important; }
    [data-testid="stTable"] { margin-bottom: -25px; }
    .stTabs [data-baseweb="tab"] { font-size: 18px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# 지수 비교 하이라이트 함수
def highlight_sp500(row, idx_df):
    m_map = {'NYSE': 'S&P 500', 'NASDAQ': 'NASDAQ'} # S&P 500 종목도 거래소에 따라 구분될 수 있음
    target = m_map.get(row['시장'], 'S&P 500') # 기본값을 S&P 500으로
    styles = [''] * len(row)
    if target in idx_df.index:
        idx_r = idx_df.loc[target]
        for col in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
            col_idx = row.index.get_loc(col)
            if row[col] < idx_r[col]:
                styles[col_idx] = 'background-color: #0047AB; color: #FFFFFF; font-weight: bold;'
    return styles

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
                return round((curr_val - p_df['Close'].iloc[-1]) / p_df['Close'].iloc[-1] * 100, 1) if not p_df.empty else 0.0
            res.append({'시장': name, '현재가': round(curr_val, 1), '1개월(%)': get_ret(1), '3개월(%)': get_ret(3), '6개월(%)': get_ret(6), '12개월(%)': get_ret(12)})
        except: pass
    return pd.DataFrame(res).set_index('시장')

tab1, tab2 = st.tabs(["📅 전월 말일 기준", "🕒 오늘(데일리) 기준"])

# [탭 1: 월말 고정 데이터]
with tab1:
    f_sp500 = 'data/momentum_data_sp500.csv' # 파일명 변경!
    if os.path.exists(f_sp500):
        df_sp500 = pd.read_csv(f_sp500, dtype={'종목코드': str})
        b_date = df_sp500['기준일(월말)'].iloc[0]
        st.title(f"🇺🇸 S&P 500 모멘텀 (기준: {b_date})")
        
        idx_us = get_idx_us(pd.to_datetime(b_date))
        if not idx_us.empty:
            st.table(idx_us.reset_index().assign(**{c: idx_us.reset_index()[c].map('{:.1f}'.format) for c in idx_us.columns if c != '시장'}))
        
        st.markdown("---")
        df_sp500.index = range(1, len(df_sp500) + 1)
        df_sp500['통합티커'] = df_sp500['시장'] + ":" + df_sp500['종목코드']
        df_sp500['종목명'] = df_sp500.apply(lambda r: f"https://finance.yahoo.com/quote/{r['종목코드']}#{r['종목명']}", axis=1)

        st.dataframe(
            df_sp500.style.apply(highlight_sp500, idx_df=idx_us, axis=1),
            use_container_width=True, height=560,
            column_order=['통합티커', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어'],
            column_config={
                "종목명": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"),
                "기준가": st.column_config.NumberColumn(format="%.2f"),
                "1개월(%)": st.column_config.NumberColumn(format="%.1f"),
                "3개월(%)": st.column_config.NumberColumn(format="%.1f"),
                "6개월(%)": st.column_config.NumberColumn(format="%.1f"),
                "12개월(%)": st.column_config.NumberColumn(format="%.1f"),
                "모멘텀스코어": st.column_config.NumberColumn(format="%.1f")
            }
        )
    else: st.warning("S&P 500 월말 데이터 파일이 없습니다. (data/momentum_data_sp500.csv)")

# [탭 2: 데일리 데이터]
with tab2:
    f_daily_sp500 = 'data/momentum_data_daily_sp500.csv' # 파일명 변경!
    if os.path.exists(f_daily_sp500):
        df_d_sp500 = pd.read_csv(f_daily_sp500, dtype={'종목코드': str})
        d_date = df_d_sp500['기준일'].iloc[0]
        st.title(f"🕒 S&P 500 데일리 (기준: {d_date})")
        
        idx_now = get_idx_us() 
        if not idx_now.empty:
            st.table(idx_now.reset_index().assign(**{c: idx_now.reset_index()[c].map('{:.1f}'.format) for c in idx_now.columns if c != '시장'}))
        
        st.markdown("---")
        df_d_sp500.index = range(1, len(df_d_sp500) + 1)
        df_d_sp500['통합티커'] = df_d_sp500['시장'] + ":" + df_d_sp500['종목코드']
        df_d_sp500['종목명'] = df_d_sp500.apply(lambda r: f"https://finance.yahoo.com/quote/{r['종목코드']}#{r['종목명']}", axis=1)

        st.dataframe(
            df_d_sp500.style.apply(highlight_sp500, idx_df=idx_now, axis=1),
            use_container_width=True, height=560,
            column_order=['통합티커', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어'],
            column_config={
                "종목명": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"),
                "기준가": st.column_config.NumberColumn(format="%.2f"),
                "1개월(%)": st.column_config.NumberColumn(format="%.1f"),
                "3개월(%)": st.column_config.NumberColumn(format="%.1f"),
                "6개월(%)": st.column_config.NumberColumn(format="%.1f"),
                "12개월(%)": st.column_config.NumberColumn(format="%.1f"),
                "모멘텀스코어": st.column_config.NumberColumn(format="%.1f")
            }
        )
    else: st.warning("S&P 500 데일리 데이터 파일이 없습니다. (data/momentum_data_daily_sp500.csv)")
