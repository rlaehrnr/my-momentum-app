import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime
import os

# 1. 페이지 설정
st.set_page_config(page_title="글로벌 모멘텀 순위", layout="wide")

# CSS: 초밀착 레이아웃 및 탭 디자인
st.markdown("""
    <style>
    [data-testid="stTable"] { margin-bottom: -20px; }
    hr { margin-top: 5px; margin-bottom: 5px; }
    .stDataFrame { margin-top: -10px; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; font-size: 18px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 지수 데이터 함수 ---
@st.cache_data(ttl=86400)
def get_index_momentum(market_type='KR'):
    if market_type == 'KR':
        indices = {'KOSPI': 'KS11', 'KOSDAQ': 'KQ11'}
    else:
        indices = {'S&P 500': 'US500', 'NASDAQ': 'IXIC'}
        
    today = datetime.today()
    start_date = today - pd.DateOffset(months=15)
    res = []
    for name, code in indices.items():
        try:
            df = fdr.DataReader(code, start_date, today)
            curr = df['Close'].iloc[-1]
            def get_ret(m):
                p_df = df[df.index <= (df.index[-1] - pd.DateOffset(months=m))]
                return round((curr - p_df['Close'].iloc[-1]) / p_df['Close'].iloc[-1] * 100, 1)
            res.append({'시장': name, '현재가': round(curr, 1), '1개월(%)': get_ret(1), '3개월(%)': get_ret(3), '6개월(%)': get_ret(6), '12개월(%)': get_ret(12)})
        except: pass
    return pd.DataFrame(res).set_index('시장')

# --- 탭 구성 ---
tab_kr, tab_us = st.tabs(["🇰🇷 한국 시장 모멘텀", "🇺🇸 미국 시장 모멘텀"])

# ---------------------------------------------------------
# [탭 1: 한국 시장]
# ---------------------------------------------------------
with tab_kr:
    file_kr = 'momentum_data.csv'
    if os.path.exists(file_kr):
        df_kr = pd.read_csv(file_kr, dtype={'종목코드': str})
        base_date_kr = df_kr['기준일(월말)'].iloc[0]
        st.title(f"📊 한국 모멘텀 (기준일: {base_date_kr})")
        
        # 지수 표
        idx_kr = get_index_momentum('KR')
        if not idx_kr.empty:
            st.table(idx_kr.reset_index().assign(**{col: idx_kr.reset_index()[col].map('{:.1f}'.format) for col in idx_kr.columns if col != '시장'}))

        st.markdown("---")
        
        # 데이터 전처리
        df_kr['종목코드'] = df_kr['종목코드'].str.zfill(6)
        df_kr['통합티커'] = df_kr['시장'] + ":" + df_kr['종목코드']
        df_kr['종목명'] = df_kr.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드']}#{r['종목명']}", axis=1)

        # 하이라이트 함수
        def hl_kr(row):
            styles = [''] * len(row)
            if row['시장'] in idx_kr.index:
                idx_r = idx_kr.loc[row['시장']]
                for col in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
                    if row[col] < idx_r[col]: styles[row.index.get_loc(col)] = 'background-color: #e6f3ff;'
            return styles

        st.dataframe(df_kr.style.apply(hl_kr, axis=1), use_container_width=True, height=560, 
                     column_order=['통합티커', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어'],
                     column_config={"종목명": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), "기준가": st.column_config.NumberColumn(format="%d"),
                                    "1개월(%)": st.column_config.NumberColumn(format="%.1f"), "3개월(%)": st.column_config.NumberColumn(format="%.1f"),
                                    "6개월(%)": st.column_config.NumberColumn(format="%.1f"), "12개월(%)": st.column_config.NumberColumn(format="%.1f"),
                                    "모멘텀스코어": st.column_config.NumberColumn(format="%.2f")})
    else: st.warning("한국 데이터가 없습니다.")

# ---------------------------------------------------------
# [탭 2: 미국 시장]
# ---------------------------------------------------------
with tab_us:
    file_us = 'momentum_data_us.csv'
    if os.path.exists(file_us):
        df_us = pd.read_csv(file_us)
        base_date_us = df_us['기준일(월말)'].iloc[0]
        st.title(f"🇺🇸 미국 모멘텀 (기준일: {base_date_us})")
        
        # 지수 표
        idx_us = get_index_momentum('US')
        if not idx_us.empty:
            st.table(idx_us.reset_index().assign(**{col: idx_us.reset_index()[col].map('{:.1f}'.format) for col in idx_us.columns if col != '시장'}))

        st.markdown("---")

        df_us['통합티커'] = df_us['시장'] + ":" + df_us['종목코드']
        df_us['종목명'] = df_us.apply(lambda r: f"https://finance.yahoo.com/quote/{r['종목코드']}#{r['종목명']}", axis=1)

        # 미국 하이라이트 (NYSE -> S&P 500, NASDAQ -> NASDAQ 매칭)
        def hl_us(row):
            m_map = {'NYSE': 'S&P 500', 'NASDAQ': 'NASDAQ'}
            styles = [''] * len(row)
            target = m_map.get(row['시장'])
            if target in idx_us.index:
                idx_r = idx_us.loc[target]
                for col in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
                    if row[col] < idx_r[col]: styles[row.index.get_loc(col)] = 'background-color: #e6f3ff;'
            return styles

        st.dataframe(df_us.style.apply(hl_us, axis=1), use_container_width=True, height=560,
                     column_order=['통합티커', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어'],
                     column_config={"종목명": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), "기준가": st.column_config.NumberColumn(format="%.2f"),
                                    "1개월(%)": st.column_config.NumberColumn(format="%.1f"), "3개월(%)": st.column_config.NumberColumn(format="%.1f"),
                                    "6개월(%)": st.column_config.NumberColumn(format="%.1f"), "12개월(%)": st.column_config.NumberColumn(format="%.1f"),
                                    "모멘텀스코어": st.column_config.NumberColumn(format="%.2f")})
    else: st.warning("미국 데이터가 아직 수집되지 않았습니다. GitHub Actions 로봇을 한 번 돌려주세요!")
