import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os

# 1. 페이지 설정
st.set_page_config(page_title="미국 모멘텀 순위", layout="wide")

# CSS: 가독성 및 디자인 강화
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem !important; }
    h1 { font-size: 2.2rem !important; font-weight: 800; margin-bottom: 20px; }
    .stTabs [data-baseweb="tab"] { font-size: 18px; font-weight: bold; }
    
    /* 섹션 제목 스타일 */
    .section-header {
        background-color: #1F2937;
        color: #FFFFFF;
        padding: 10px 20px;
        border-radius: 8px 8px 0 0;
        font-size: 1.1rem;
        font-weight: bold;
        border-bottom: 4px solid #EF4444;
        margin-top: 20px;
    }
    .overlap-header {
        background-color: #1E3A8A;
        color: white;
        padding: 10px 20px;
        border-radius: 8px 8px 0 0;
        font-size: 1.1rem;
        font-weight: bold;
        border-bottom: 4px solid #F59E0B;
    }
    /* 개수 표시 배지 */
    .count-badge {
        background-color: #4B5563;
        color: white;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 0.8rem;
        margin-left: 10px;
        vertical-align: middle;
    }
    </style>
    """, unsafe_allow_html=True)

# ⭐ 눈이 편한 아주 연한 하이라이트
def highlight_soft(row, common_tickers):
    styles = [''] * len(row)
    if row.get('종목코드') in common_tickers:
        # 아주 연한 크림색 (눈 보호)
        for i in range(len(styles)):
            styles[i] = 'background-color: #FFF9E5; color: #5D4037; font-weight: bold;'
    return styles

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

# 테이블 공통 설정
common_config = {
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
    
    # 🔗 야후 파이낸스 차트(chart) 링크 적용
    df_300['종목명_L'] = df_300.apply(lambda r: f"https://finance.yahoo.com/chart/{str(r['종목코드']).replace('.', '-')}#{r['종목명']}", axis=1)

    # 교집합 데이터 추출 (TOP 10 기준)
    top10_12_1 = df_300.sort_values('12-1개월(%)', ascending=False).head(10)
    top10_6_1 = df_300.sort_values('6-1개월(%)', ascending=False).head(10)
    top10_3_1 = df_300.sort_values('3-1개월(%)', ascending=False).head(10)

    overlap_12_6 = top10_12_1[top10_12_1['종목코드'].isin(top10_6_1['종목코드'])].copy()
    overlap_6_3 = top10_6_1[top10_6_1['종목코드'].isin(top10_3_1['종목코드'])].copy()
    
    common_tickers = set(overlap_12_6['종목코드']).intersection(set(overlap_6_3['종목코드']))

    # --- 상단: 교집합 섹션 ---
    st.markdown("### 🌟 모멘텀 교집합 (TOP 10 중복 분석)")
    c_over1, c_over2 = st.columns(2)
    
    with c_over1:
        st.markdown(f'<div class="overlap-header">🔥 12-1M & 6-1M 중복 <span class="count-badge">{len(overlap_12_6)}개 종목</span></div>', unsafe_allow_html=True)
        if not overlap_12_6.empty:
            overlap_12_6 = overlap_12_6.reset_index(drop=True)
            overlap_12_6.index += 1 
            st.dataframe(overlap_12_6.style.apply(highlight_soft, common_tickers=common_tickers, axis=1), 
                         use_container_width=True, hide_index=False,
                         column_order=['통합티커', '종목명_L', '12-1개월(%)', '6-1개월(%)'], column_config=common_config)
        else: st.info("중복 없음")

    with c_over2:
        st.markdown(f'<div class="overlap-header">⚡ 6-1M & 3-1M 중복 <span class="count-badge">{len(overlap_6_3)}개 종목</span></div>', unsafe_allow_html=True)
        if not overlap_6_3.empty:
            overlap_6_3 = overlap_6_3.reset_index(drop=True)
            overlap_6_3.index += 1
            st.dataframe(overlap_6_3.style.apply(highlight_soft, common_tickers=common_tickers, axis=1), 
                         use_container_width=True, hide_index=False,
                         column_order=['통합티커', '종목명_L', '6-1개월(%)', '3-1개월(%)'], column_config=common_config)
        else: st.info("중복 없음")

    # --- 중단: 상위 30위 섹션 ---
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    
    for col, title, sort_col in zip([col1, col2, col3], 
                                   ["🏆 12-1개월 상위 30", "🏆 6-1개월 상위 30", "🏆 3-1개월 상위 30"], 
                                   ["12-1개월(%)", "6-1개월(%)", "3-1개월(%)"]):
        with col:
            st.markdown(f'<div class="section-header">{title} <span class="count-badge">30개</span></div>', unsafe_allow_html=True)
            df_sub = df_300.sort_values(sort_col, ascending=False).head(30).copy()
            df_sub = df_sub.reset_index(drop=True)
            df_sub.index += 1 
            # hide_index=False 가 바로 그 '왼쪽 회색 숫자'를 보여주는 설정입니다!
            st.dataframe(df_sub, use_container_width=True, height=450, hide_index=False,
                         column_order=['통합티커', '종목명_L', sort_col], column_config=common_config)

    st.markdown("---")
    
    # --- 하단: 전체 순위표 ---
    st.markdown(f'### 📊 미국 시총상위 300종목 전체 리스트 (기준: {target_date_str})')
    df_300_all = df_300.copy().reset_index(drop=True)
    df_300_all.index += 1 
    st.dataframe(df_300_all, use_container_width=True, height=600, hide_index=False,
                 column_order=['통합티커', '종목명_L', '기준가', '3-1개월(%)', '6-1개월(%)', '12-1개월(%)'],
                 column_config=common_config)

# 실행부
st.title("🇺🇸 미국 시총상위 모멘텀")
t1, t2 = st.tabs(["📅 전월 말일 기준", "🕒 오늘(데일리) 기준"])

f_us, f_daily = 'data/momentum_data_us.csv', 'data/momentum_data_daily_us.csv'

with t1:
    if os.path.exists(f_us):
        df = pd.read_csv(f_us, dtype={'종목코드': str})
        display_momentum_dashboard(df, df['기준일(월말)'].iloc[0])

with t2:
    if os.path.exists(f_daily):
        df = pd.read_csv(f_daily, dtype={'종목코드': str})
        display_momentum_dashboard(df, df['기준일'].iloc[0])
