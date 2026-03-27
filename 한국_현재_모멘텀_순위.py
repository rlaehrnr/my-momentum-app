import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os

# 1. 페이지 설정
st.set_page_config(page_title="한국 모멘텀 순위", layout="wide")

# CSS: 초밀착 레이아웃
st.markdown("""<style>.block-container { padding-top: 2.5rem !important; } h1 { margin-top: 0px !important; } .stDataFrame { margin-top: -10px; } .stTabs [data-baseweb="tab"] { font-size: 18px; font-weight: bold; }</style>""", unsafe_allow_html=True)

# 🎨 하이라이트 함수 (고대비)
def highlight_kr(row, idx_df):
    styles = [''] * len(row)
    if row['시장'] in idx_df.index:
        idx_r = idx_df.loc[row['시장']]
        for col in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
            col_idx = row.index.get_loc(col)
            if row[col] < idx_r[col]: styles[col_idx] = 'background-color: #0047AB; color: #FFFFFF; font-weight: bold;'
    return styles

# 지수 데이터 함수 (캐시 적용)
@st.cache_data(ttl=3600)
def get_idx_kr(target_date=None):
    indices = {'KOSPI': 'KS11', 'KOSDAQ': 'KQ11'}
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
                return round((curr - p_df['Close'].iloc[-1]) / p_df['Close'].iloc[-1] * 100, 1) if not p_df.empty else 0.0
            res.append({'시장': name, '현재가': round(curr, 1), '1개월(%)': get_ret(1), '3개월(%)': get_ret(3), '6개월(%)': get_ret(6), '12개월(%)': get_ret(12)})
        except: pass
    return pd.DataFrame(res).set_index('시장')

tab1, tab2 = st.tabs(["📅 전월 말일 기준", "🕒 오늘(데일리) 기준"])

# [탭 1: 월말 고정 데이터]
with tab1:
    f_kr = 'momentum_data.csv'
    if os.path.exists(f_kr):
        df_kr = pd.read_csv(f_kr, dtype={'종목코드': str})
        b_date = df_kr['기준일(월말)'].iloc[0]
        st.title(f"📊 한국 모멘텀 (기준일: {b_date})")
        idx_kr = get_idx_kr(pd.to_datetime(b_date))
        if not idx_kr.empty: st.table(idx_kr.reset_index().assign(**{c: idx_kr.reset_index()[c].map('{:.1f}'.format) for c in idx_kr.columns if c != '시장'}))
        df_kr['통합티커'] = df_kr['시장'] + ":" + df_kr['종목코드'].str.zfill(6)
        df_kr['종목명'] = df_kr.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)
        st.dataframe(df_kr.style.apply(highlight_kr, idx_df=idx_kr, axis=1), use_container_width=True, height=560, column_order=['통합티커', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어'], column_config={"종목명": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), "기준가": st.column_config.NumberColumn(format="%d")})

# [탭 2: 데일리 데이터 - 로봇이 저장한 파일 읽기]
with tab2:
    f_daily = 'momentum_data_daily.csv'
    if os.path.exists(f_daily):
        df_daily = pd.read_csv(f_daily, dtype={'종목코드': str})
        d_date = df_daily['기준일'].iloc[0]
        st.title(f"🕒 데일리 모멘텀 (기준일: {d_date})")
        idx_now = get_idx_kr() # 지수만 실시간(캐시)으로 가져옴
        if not idx_now.empty: st.table(idx_now.reset_index().assign(**{c: idx_now.reset_index()[c].map('{:.1f}'.format) for c in idx_now.columns if c != '시장'}))
        df_daily['통합티커'] = df_daily['시장'] + ":" + df_daily['종목코드'].str.zfill(6)
        df_daily['종목명'] = df_daily.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)
        st.dataframe(df_daily.style.apply(highlight_kr, idx_df=idx_now, axis=1), use_container_width=True, height=560, column_order=['통합티커', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어'], column_config={"종목명": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), "기준가": st.column_config.NumberColumn(format="%d")})
    else: st.warning("데일리 데이터 파일이 아직 생성되지 않았습니다. 로봇을 실행해주세요.")
