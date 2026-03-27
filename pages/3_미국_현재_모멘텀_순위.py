
import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime
import os

# 1. 페이지 설정
st.set_page_config(page_title="미국 모멘텀 순위", layout="wide")

# CSS: 초밀착 레이아웃
st.markdown("""
    <style>
    .block-container { padding-top: 2.5rem !important; padding-bottom: 0rem !important; }
    h1 { margin-top: 0px !important; margin-bottom: 10px !important; font-size: 2rem !important; }
    [data-testid="stTable"] { margin-bottom: -25px; }
    hr { margin-top: 5px; margin-bottom: 5px; }
    .stDataFrame { margin-top: -10px; }
    </style>
    """, unsafe_allow_html=True)

# 지수 데이터 함수 (US 전용)
@st.cache_data(ttl=86400)
def get_index_momentum_us():
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

# 하이라이트 함수 (NYSE -> S&P 500 매칭)
def highlight_us(row, idx_df):
    m_map = {'NYSE': 'S&P 500', 'NASDAQ': 'NASDAQ'}
    target = m_map.get(row['시장'])
    styles = [''] * len(row)
    if target in idx_df.index:
        idx_r = idx_df.loc[target]
        for col in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
            col_idx = row.index.get_loc(col)
            if row[col] < idx_r[col]:
                styles[col_idx] = 'background-color: #0047AB; color: #FFFFFF; font-weight: bold;'
    return styles

file_us = 'momentum_data_us.csv'
if os.path.exists(file_us):
    df_us = pd.read_csv(file_us)
    base_date = df_us['기준일(월말)'].iloc[0]
    st.title(f"🇺🇸 미국 모멘텀 순위 (기준일: {base_date})")
    
    idx_us = get_index_momentum_us()
    if not idx_us.empty:
        idx_disp = idx_us.reset_index().copy()
        for col in ['현재가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
            idx_disp[col] = idx_disp[col].map('{:.1f}'.format)
        st.table(idx_disp)

    st.markdown("---")

    df_us['통합티커'] = df_us['시장'] + ":" + df_us['종목코드']
    df_us['종목명'] = df_us.apply(lambda r: f"https://finance.yahoo.com/quote/{r['종목코드']}#{r['종목명']}", axis=1)

    styled_df = df_us.style.apply(highlight_us, idx_df=idx_us, axis=1)

    st.dataframe(styled_df, use_container_width=True, height=560,
                 column_order=['통합티커', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어'],
                 column_config={"종목명": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), "기준가": st.column_config.NumberColumn(format="%.2f"),
                                "1개월(%)": st.column_config.NumberColumn(format="%.1f"), "3개월(%)": st.column_config.NumberColumn(format="%.1f"),
                                "6개월(%)": st.column_config.NumberColumn(format="%.1f"), "12개월(%)": st.column_config.NumberColumn(format="%.1f"),
                                "모멘텀스코어": st.column_config.NumberColumn(format="%.2f")})
else:
    st.title("🇺🇸 미국 모멘텀 순위")
    st.warning("미국 데이터 파일이 없습니다. 로봇을 실행해주세요.")
