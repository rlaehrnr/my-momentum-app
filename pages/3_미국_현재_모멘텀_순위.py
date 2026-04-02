import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os

# 1. 페이지 설정
st.set_page_config(page_title="미국 모멘텀 순위", layout="wide")

# CSS: 레이아웃 및 가독성 최적화
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem !important; }
    h1 { font-size: 2.2rem !important; font-weight: 800; margin-bottom: 20px; }
    .stTabs [data-baseweb="tab"] { font-size: 18px; font-weight: bold; }
    
    /* 헤더 스타일 커스텀 */
    .table-header {
        background-color: #262730;
        color: white;
        padding: 8px 15px;
        border-radius: 5px;
        font-size: 1.1rem;
        font-weight: bold;
        margin-bottom: 10px;
        border-left: 8px solid #FF4B4B;
    }
    .overlap-header {
        background-color: #1E3A8A; /* 남색 배경 */
        color: white;
        padding: 8px 15px;
        border-radius: 5px;
        font-size: 1.1rem;
        font-weight: bold;
        margin-bottom: 10px;
        border-left: 8px solid #F59E0B;
    }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def get_idx_us(target_date=None):
    indices = {'미국 시장': 'US500', 'NASDAQ': 'IXIC'}
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
            res.append({'시장': name, '현재가': curr_val, '1개월(%)': get_ret(1), '3개월(%)': get_ret(3), '6개월(%)': get_ret(6), '12개월(%)': get_ret(12)})
        except: pass
    return pd.DataFrame(res).set_index('시장')

# 공통 테이블 설정
common_config = {
    "#": st.column_config.NumberColumn("#", format="%d", width="small"),
    "순위": st.column_config.NumberColumn("원래 순위", format="%d위"),
    "통합티커": st.column_config.TextColumn("티커"),
    "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), 
    "기준가": st.column_config.NumberColumn("현재가", format="$ %,.2f"),
    "3-1개월(%)": st.column_config.NumberColumn("3-1M", format="%.1f%%"),
    "6-1개월(%)": st.column_config.NumberColumn("6-1M", format="%.1f%%"),
    "12-1개월(%)": st.column_config.NumberColumn("12-1M", format="%.1f%%"),
}

def display_momentum_dashboard(df_raw, target_date_str):
    df_300 = df_raw.head(300).copy()
    df_300['통합티커'] = df_300['시장'] + ":" + df_300['종목코드']
    df_300['종목명_L'] = df_300.apply(lambda r: f"https://finance.yahoo.com/quote/{str(r['종목코드']).replace('.', '-')}#{r['종목명']}", axis=1)

    # 1. 교집합 데이터 추출 (각 지표별 TOP 10 기준)
    top10_12_1 = df_300.sort_values('12-1개월(%)', ascending=False).head(10)
    top10_6_1 = df_300.sort_values('6-1개월(%)', ascending=False).head(10)
    top10_3_1 = df_300.sort_values('3-1개월(%)', ascending=False).head(10)

    overlap_12_6 = top10_12_1[top10_12_1['종목코드'].isin(top10_6_1['종목코드'])].copy()
    overlap_6_3 = top10_6_1[top10_6_1['종목코드'].isin(top10_3_1['종목코드'])].copy()

    # --- 상단 레이아웃 1: 중복 종목 요약 ---
    st.markdown("### 🌟 모멘텀 교집합 (TOP 10 중복 종목)")
    c_over1, c_over2 = st.columns(2)
    
    with c_over1:
        st.markdown('<div class="overlap-header">🔥 12-1M & 6-1M 교집합 (TOP 10)</div>', unsafe_allow_html=True)
        if not overlap_12_6.empty:
            overlap_12_6['#'] = range(1, len(overlap_12_6) + 1)
            st.dataframe(overlap_12_6, use_container_width=True, hide_index=True,
                         column_order=['#', '통합티커', '종목명_L', '12-1개월(%)', '6-1개월(%)'], column_config=common_config)
        else:
            st.info("현재 12-1M와 6-1M TOP 10 중 겹치는 종목이 없습니다.")

    with c_over2:
        st.markdown('<div class="overlap-header">⚡ 6-1M & 3-1M 교집합 (TOP 10)</div>', unsafe_allow_html=True)
        if not overlap_6_3.empty:
            overlap_6_3['#'] = range(1, len(overlap_6_3) + 1)
            st.dataframe(overlap_6_3, use_container_width=True, hide_index=True,
                         column_order=['#', '통합티커', '종목명_L', '6-1개월(%)', '3-1개월(%)'], column_config=common_config)
        else:
            st.info("현재 6-1M와 3-1M TOP 10 중 겹치는 종목이 없습니다.")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- 상단 레이아웃 2: 각 지표별 상위 30위 ---
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown('<div class="table-header">🏆 12-1개월 상위 30</div>', unsafe_allow_html=True)
        df1 = df_300.sort_values('12-1개월(%)', ascending=False).head(30).copy()
        df1['#'] = range(1, 31) # 고정 번호
        df1['순위'] = range(1, 31) # 원래 순위 기록
        st.dataframe(df1, use_container_width=True, height=450, hide_index=True,
                     column_order=['#', '통합티커', '종목명_L', '12-1개월(%)'], column_config=common_config)

    with col2:
        st.markdown('<div class="table-header">🏆 6-1개월 상위 30</div>', unsafe_allow_html=True)
        df2 = df_300.sort_values('6-1개월(%)', ascending=False).head(30).copy()
        df2['#'] = range(1, 31)
        df2['순위'] = range(1, 31)
        st.dataframe(df2, use_container_width=True, height=450, hide_index=True,
                     column_order=['#', '통합티커', '종목명_L', '6-1개월(%)'], column_config=common_config)

    with col3:
        st.markdown('<div class="table-header">🏆 3-1개월 상위 30</div>', unsafe_allow_html=True)
        df3 = df_300.sort_values('3-1개월(%)', ascending=False).head(30).copy()
        df3['#'] = range(1, 31)
        df3['순위'] = range(1, 31)
        st.dataframe(df3, use_container_width=True, height=450, hide_index=True,
                     column_order=['#', '통합티커', '종목명_L', '3-1개월(%)'], column_config=common_config)

    st.markdown("---")
    
    # --- 하단: 전체 순위표 ---
    st.markdown(f'### 📊 미국 시총상위 300종목 전체 (기준: {target_date_str})')
    df_300['시총순위'] = range(1, len(df_300) + 1)
    st.dataframe(df_300, use_container_width=True, height=600, hide_index=True,
                 column_order=['시총순위', '통합티커', '종목명_L', '기준가', '3-1개월(%)', '6-1개월(%)', '12-1개월(%)'],
                 column_config={**common_config, "시총순위": st.column_config.NumberColumn("시총순위", format="%d위")})

# 상단 타이틀
st.title("🇺🇸 미국 시총상위 모멘텀")

tab1, tab2, tab3 = st.tabs(["🎯 미국 시총상위 300 전체 순위", "📅 전월 말일 기준", "🕒 오늘(데일리) 기준"])

with tab1:
    f_us = 'data/momentum_data_us.csv'
    if os.path.exists(f_us):
        df_raw = pd.read_csv(f_us, dtype={'종목코드': str})
        df_raw.columns = df_raw.columns.str.replace(' ', '')
        b_date = df_raw['기준일(월말)'].iloc[0]
        display_momentum_dashboard(df_raw, b_date)

with tab2:
    if os.path.exists(f_us):
        df_raw = pd.read_csv(f_us, dtype={'종목코드': str})
        df_raw.columns = df_raw.columns.str.replace(' ', '')
        b_date = df_raw['기준일(월말)'].iloc[0]
        display_momentum_dashboard(df_raw, b_date)

with tab3:
    f_daily = 'data/momentum_data_daily_us.csv'
    if os.path.exists(f_daily):
        df_raw = pd.read_csv(f_daily, dtype={'종목코드': str})
        d_date = df_raw['기준일'].iloc[0]
        display_momentum_dashboard(df_raw, d_date)
