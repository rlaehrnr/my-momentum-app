import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os

st.set_page_config(page_title="미국 모멘텀 순위", layout="wide")

# CSS (한국 페이지와 통일)
st.markdown("""<style>.block-container { padding-top: 2.5rem !important; } h1 { font-size: 2rem !important; } .stDataFrame { margin-top: -10px; } .stTabs [data-baseweb="tab"] { font-size: 18px; font-weight: bold; }</style>""", unsafe_allow_html=True)

# 지수 함수
@st.cache_data(ttl=3600)
def get_idx_us(target_date=None):
    indices = {'S&P 500': 'US500', 'NASDAQ': 'IXIC'}
    today = datetime.today()
    res = []
    for name, code in indices.items():
        try:
            df = fdr.DataReader(code, today - pd.DateOffset(months=15), today)
            curr = df.loc[df.index <= target_date]['Close'].iloc[-1] if target_date else df['Close'].iloc[-1]
            last_date = df.index[df.index <= (target_date if target_date else today)][-1]
            def get_ret(m):
                ref = (last_date - pd.DateOffset(months=m)).replace(day=1) - timedelta(days=1)
                p_df = df[df.index <= ref]
                return round((curr - p_df['Close'].iloc[-1]) / p_df['Close'].iloc[-1] * 100, 1)
            res.append({'시장': name, '현재가': round(curr, 1), '1개월(%)': get_ret(1), '3개월(%)': get_ret(3), '6개월(%)': get_ret(6), '12개월(%)': get_ret(12)})
        except: pass
    return pd.DataFrame(res).set_index('시장')

# 하이라이트 함수 (미국용 매칭)
def highlight_us(row, idx_df):
    m_map = {'NYSE': 'S&P 500', 'NASDAQ': 'NASDAQ'}
    target = m_map.get(row['시장'])
    styles = [''] * len(row)
    if target in idx_df.index:
        idx_r = idx_df.loc[target]
        for col in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
            col_idx = row.index.get_loc(col)
            if row[col] < idx_r[col]: styles[col_idx] = 'background-color: #0047AB; color: #FFFFFF; font-weight: bold;'
    return styles

tab1, tab2 = st.tabs(["📅 전월 말일 기준", "🕒 오늘(데일리) 기준"])

# [탭 1: 월말 고정]
with tab1:
    f_us = 'momentum_data_us.csv'
    if os.path.exists(f_us):
        df = pd.read_csv(f_us)
        b_date = df['기준일(월말)'].iloc[0]
        st.title(f"🇺🇸 미국 모멘텀 (기준일: {b_date})")
        idx = get_idx_us(pd.to_datetime(b_date))
        if not idx.empty: st.table(idx.reset_index().assign(**{c: idx.reset_index()[c].map('{:.1f}'.format) for c in idx.columns if c != '시장'}))
        df['통합티커'] = df['시장'] + ":" + df['종목코드']
        df['종목명'] = df.apply(lambda r: f"https://finance.yahoo.com/quote/{r['종목코드']}#{r['종목명']}", axis=1)
        st.dataframe(df.style.apply(highlight_us, idx_df=idx, axis=1), use_container_width=True, height=560, column_order=['통합티커', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어'], column_config={"종목명": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), "기준가": st.column_config.NumberColumn(format="%.2f"), "1개월(%)": st.column_config.NumberColumn(format="%.1f"), "3개월(%)": st.column_config.NumberColumn(format="%.1f"), "6개월(%)": st.column_config.NumberColumn(format="%.1f"), "12개월(%)": st.column_config.NumberColumn(format="%.1f"), "모멘텀스코어": st.column_config.NumberColumn(format="%.1f")})

# [탭 2: 데일리]
with tab2:
    f_daily = 'momentum_data_daily_us.csv'
    if os.path.exists(f_daily):
        df_d = pd.read_csv(f_daily)
        d_date = df_d['기준일'].iloc[0]
        st.title(f"🕒 미국 데일리 (기준일: {d_date})")
        idx_now = get_idx_us()
        if not idx_now.empty: st.table(idx_now.reset_index().assign(**{c: idx_now.reset_index()[c].map('{:.1f}'.format) for c in idx_now.columns if c != '시장'}))
        df_d['통합티커'] = df_d['시장'] + ":" + df_d['종목코드']
        df_d['종목명'] = df_d.apply(lambda r: f"https://finance.yahoo.com/quote/{r['종목코드']}#{r['종목명']}", axis=1)
        st.dataframe(df_d.style.apply(highlight_us, idx_df=idx_now, axis=1), use_container_width=True, height=560, column_order=['통합티커', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어'], column_config={"종목명": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), "기준가": st.column_config.NumberColumn(format="%.2f"), "1개월(%)": st.column_config.NumberColumn(format="%.1f"), "3개월(%)": st.column_config.NumberColumn(format="%.1f"), "6개월(%)": st.column_config.NumberColumn(format="%.1f"), "12개월(%)": st.column_config.NumberColumn(format="%.1f"), "모멘텀스코어": st.column_config.NumberColumn(format="%.1f")})
