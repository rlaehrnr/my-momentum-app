import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os

st.set_page_config(page_title="한국 모멘텀 순위", layout="wide")

# CSS: 레이아웃 최적화
st.markdown("""<style>.block-container { padding-top: 2.5rem !important; } h1 { font-size: 2rem !important; } .stMultiSelect { margin-top: -15px; margin-bottom: 10px; }</style>""", unsafe_allow_html=True)

# 지수 비교 하이라이트 함수
def highlight_kr(row, idx_df):
    styles = [''] * len(row)
    if row['시장'] in idx_df.index:
        idx_r = idx_df.loc[row['시장']]
        for col in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
            col_idx = row.index.get_loc(col)
            if row[col] < idx_r[col]: styles[col_idx] = 'background-color: #0047AB; color: #FFFFFF; font-weight: bold;'
    return styles

@st.cache_data(ttl=3600)
def get_idx_kr(target_date=None):
    indices = {'KOSPI': 'KS11', 'KOSDAQ': 'KQ11'}
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

# [탭 1: 월말 고정]
with tab1:
    f_kr = 'data/momentum_data.csv'
    if os.path.exists(f_kr):
        df_kr = pd.read_csv(f_kr, dtype={'종목코드': str})
        
        # ⭐ 시장 필터 추가
        mkts_1 = st.multiselect("🔎 시장 필터", options=df_kr['시장'].unique(), default=df_kr['시장'].unique(), key="m_f_1")
        df_filtered_1 = df_kr[df_kr['시장'].isin(mkts_1)].copy()
        
        st.title(f"📊 한국 모멘텀 (기준: {df_kr['기준일(월말)'].iloc[0]})")
        idx_kr = get_idx_kr(pd.to_datetime(df_kr['기준일(월말)'].iloc[0]))
        if not idx_kr.empty: st.table(idx_kr.reset_index().assign(**{c: idx_kr.reset_index()[c].map('{:.1f}'.format) for c in idx_kr.columns if c != '시장'}))
        
        df_filtered_1.index = range(1, len(df_filtered_1) + 1)
        df_filtered_1['통합티커'] = df_filtered_1['시장'] + ":" + df_filtered_1['종목코드'].str.zfill(6)
        df_filtered_1['종목명'] = df_filtered_1.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)
        
        st.dataframe(df_filtered_1.style.apply(highlight_kr, idx_df=idx_kr, axis=1), use_container_width=True, height=550, column_order=['통합티커', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어'], column_config={"종목명": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), "기준가": st.column_config.NumberColumn(format="%d")})

# [탭 2: 데일리]
with tab2:
    f_daily = 'data/momentum_data_daily.csv'
    if os.path.exists(f_daily):
        df_d = pd.read_csv(f_daily, dtype={'종목코드': str})
        
        # ⭐ 시장 필터 추가
        mkts_2 = st.multiselect("🔎 시장 필터", options=df_d['시장'].unique(), default=df_d['시장'].unique(), key="m_f_2")
        df_filtered_2 = df_d[df_d['시장'].isin(mkts_2)].copy()
        
        st.title(f"🕒 데일리 모멘텀 (기준: {df_d['기준일'].iloc[0]})")
        idx_now = get_idx_kr()
        if not idx_now.empty: st.table(idx_now.reset_index().assign(**{c: idx_now.reset_index()[c].map('{:.1f}'.format) for c in idx_now.columns if c != '시장'}))
        
        df_filtered_2.index = range(1, len(df_filtered_2) + 1)
        df_filtered_2['통합티커'] = df_filtered_2['시장'] + ":" + df_filtered_2['종목코드'].str.zfill(6)
        df_filtered_2['종목명'] = df_filtered_2.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)
        
        st.dataframe(df_filtered_2.style.apply(highlight_kr, idx_df=idx_now, axis=1), use_container_width=True, height=550, column_order=['통합티커', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어'], column_config={"종목명": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), "기준가": st.column_config.NumberColumn(format="%d")})
