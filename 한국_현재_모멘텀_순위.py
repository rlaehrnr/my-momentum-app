import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime
import os

# 1. 페이지 설정
st.set_page_config(page_title="글로벌 모멘텀 순위", layout="wide")

# ⭐ [CSS 수정] 잘리는 현상을 막기 위해 음수 마진을 제거하고 패딩을 최적화했습니다.
st.markdown("""
    <style>
    /* 상단 컨테이너 여백 조정 (잘림 방지) */
    .block-container { padding-top: 2.5rem !important; padding-bottom: 0rem !important; }
    
    /* 제목(h1) 마진 정상화 */
    h1 { margin-top: 0px !important; margin-bottom: 10px !important; font-size: 2rem !important; }
    
    /* 탭 디자인 및 간격 */
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; font-size: 18px; font-weight: bold; }
    
    /* 표와 구분선 사이의 간격은 여전히 밀착 유지 */
    [data-testid="stTable"] { margin-bottom: -25px; }
    hr { margin-top: 5px; margin-bottom: 5px; }
    .stDataFrame { margin-top: -15px; }
    
    /* 탭 위의 음수 마진을 제거하여 글자 잘림 해결 */
    div[data-testid="stVerticalBlock"] > div:has(div.stTabs) { margin-top: 0px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 지수 데이터 함수 (캐시 24시간) ---
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

# 🎨 공통 하이라이트 스타일 함수
def get_highlight_style(row, idx_df, market_map=None):
    market_key = row['시장']
    if market_map: market_key = market_map.get(row['시장'])
    styles = [''] * len(row)
    if market_key in idx_df.index:
        idx_r = idx_df.loc[market_key]
        for col in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
            col_idx = row.index.get_loc(col)
            if row[col] < idx_r[col]:
                styles[col_idx] = 'background-color: #0047AB; color: #FFFFFF; font-weight: bold;'
    return styles

# --- 탭 구성 ---
tab_kr, tab_us = st.tabs(["🇰🇷 한국 시장 모멘텀", "🇺🇸 미국 시장 모멘텀"])

# [탭 1: 한국 시장]
with tab_kr:
    file_kr = 'momentum_data.csv'
    if os.path.exists(file_kr):
        df_kr = pd.read_csv(file_kr, dtype={'종목코드': str})
        base_date_kr = df_kr['기준일(월말)'].iloc[0]
        st.title(f"📊 한국 모멘텀 (기준일: {base_date_kr})")
        
        idx_kr = get_index_momentum('KR')
        if not idx_kr.empty:
            idx_disp = idx_kr.reset_index().copy()
            for col in ['현재가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
                idx_disp[col] = idx_disp[col].map('{:.1f}'.format)
            st.table(idx_disp)

        st.markdown("---")
        df_kr['종목코드'] = df_kr['종목코드'].str.zfill(6)
        df_kr['통합티커'] = df_kr['시장'] + ":" + df_kr['종목코드']
        df_kr['종목명'] = df_kr.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드']}#{r['종목명']}", axis=1)
        styled_kr = df_kr.style.apply(get_highlight_style, idx_df=idx_kr, axis=1)
        st.dataframe(styled_kr, use_container_width=True, height=560, 
                     column_order=['통합티커', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어'],
                     column_config={"종목명": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), "기준가": st.column_config.NumberColumn(format="%d"),
                                    "1개월(%)": st.column_config.NumberColumn(format="%.1f"), "3개월(%)": st.column_config.NumberColumn(format="%.1f"),
                                    "6개월(%)": st.column_config.NumberColumn(format="%.1f"), "12개월(%)": st.column_config.NumberColumn(format="%.1f"),
                                    "모멘텀스코어": st.column_config.NumberColumn(format="%.2f")})

# [탭 2: 미국 시장]
with tab_us:
    file_us = 'momentum_data_us.csv'
    if os.path.exists(file_us):
        df_us = pd.read_csv(file_us)
        base_date_us = df_us['기준일(월말)'].iloc[0]
        st.title(f"🇺🇸 미국 모멘텀 (기준일: {base_date_us})")
        
        idx_us = get_index_momentum('US')
        if not idx_us.empty:
            idx_disp_us = idx_us.reset_index().copy()
            for col in ['현재가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
                idx_disp_us[col] = idx_disp_us[col].map('{:.1f}'.format)
            st.table(idx_disp_us)

        st.markdown("---")
        df_us['통합티커'] = df_us['시장'] + ":" + df_us['종목코드']
        df_us['종목명'] = df_us.apply(lambda r: f"https://finance.yahoo.com/quote/{r['종목코드']}#{r['종목명']}", axis=1)
        m_map_us = {'NYSE': 'S&P 500', 'NASDAQ': 'NASDAQ'}
        styled_us = df_us.style.apply(get_highlight_style, idx_df=idx_us, market_map=m_map_us, axis=1)
        st.dataframe(styled_us, use_container_width=True, height=560,
                     column_order=['통합티커', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어'],
                     column_config={"종목명": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), "기준가": st.column_config.NumberColumn(format="%.2f"),
                                    "1개월(%)": st.column_config.NumberColumn(format="%.1f"), "3개월(%)": st.column_config.NumberColumn(format="%.1f"),
                                    "6개월(%)": st.column_config.NumberColumn(format="%.1f"), "12개월(%)": st.column_config.NumberColumn(format="%.1f"),
                                    "모멘텀스코어": st.column_config.NumberColumn(format="%.2f")})
