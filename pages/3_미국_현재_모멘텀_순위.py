import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os

# 1. 페이지 설정
st.set_page_config(page_title="미국 모멘텀 순위", layout="wide")

# CSS: 고정 눈금자 및 테이블 디자인 최적화
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem !important; }
    h1 { font-size: 2.2rem !important; font-weight: 800; margin-bottom: 20px; }
    
    /* 섹션 제목 스타일 */
    .section-header {
        background-color: #1F2937;
        color: #FFFFFF;
        padding: 10px 15px;
        border-radius: 8px 8px 0 0;
        font-size: 1.1rem;
        font-weight: bold;
        border-bottom: 4px solid #EF4444;
        margin-bottom: 0px;
    }
    .overlap-header {
        background-color: #1E3A8A;
        color: white;
        padding: 10px 15px;
        border-radius: 8px 8px 0 0;
        font-size: 1.1rem;
        font-weight: bold;
        border-bottom: 4px solid #F59E0B;
        margin-bottom: 0px;
    }
    
    /* 절대 움직이지 않는 눈금자 숫자 스타일 */
    .ruler-num {
        height: 35.5px; /* 표의 행 높이와 정밀하게 맞춤 */
        display: flex;
        align-items: center;
        justify-content: flex-end;
        padding-right: 10px;
        color: #9CA3AF;
        font-family: monospace;
        font-size: 0.9rem;
        border-right: 2px solid #374151;
        margin-right: 5px;
    }
    .ruler-header {
        height: 35px;
        display: flex;
        align-items: center;
        justify-content: flex-end;
        padding-right: 10px;
        font-weight: bold;
        color: #6B7280;
    }
    </style>
    """, unsafe_allow_html=True)

# ⭐ 겹치는 종목 하이라이트 (종목명 칸만 강조!)
def highlight_overlap_name(row, common_tickers):
    styles = [''] * len(row)
    if row.get('종목코드') in common_tickers:
        if '종목명_L' in row.index:
            name_idx = row.index.get_loc('종목명_L')
            # 사용자님이 좋아하셨던 노란색 계열 강조
            styles[name_idx] = 'background-color: #FFF9C4; color: #1F2937; font-weight: bold; border-radius: 4px;'
    return styles

# 테이블 설정
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
    # 🔗 야후 파이낸스 차트 링크 적용
    df_300['종목명_L'] = df_300.apply(lambda r: f"https://finance.yahoo.com/chart/{str(r['종목코드']).replace('.', '-')}#{r['종목명']}", axis=1)

    # 교집합 추출
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
        st.markdown('<div class="overlap-header">🔥 12-1M & 6-1M 중복</div>', unsafe_allow_html=True)
        if not overlap_12_6.empty:
            # 💡 [눈금자 구현] 표 바깥 왼쪽에 번호를 배치
            r_col, t_col = st.columns([0.07, 0.93])
            with r_col:
                st.markdown('<div class="ruler-header">No</div>', unsafe_allow_html=True)
                for i in range(1, len(overlap_12_6) + 1):
                    st.markdown(f'<div class="ruler-num">{i}</div>', unsafe_allow_html=True)
            with t_col:
                st.dataframe(overlap_12_6.style.apply(highlight_overlap_name, common_tickers=common_tickers, axis=1), 
                             use_container_width=True, hide_index=True,
                             column_order=['통합티커', '종목명_L', '12-1개월(%)', '6-1개월(%)'], column_config=common_config)
        else: st.info("중복 없음")

    with c_over2:
        st.markdown('<div class="overlap-header">⚡ 6-1M & 3-1M 중복</div>', unsafe_allow_html=True)
        if not overlap_6_3.empty:
            r_col, t_col = st.columns([0.07, 0.93])
            with r_col:
                st.markdown('<div class="ruler-header">No</div>', unsafe_allow_html=True)
                for i in range(1, len(overlap_6_3) + 1):
                    st.markdown(f'<div class="ruler-num">{i}</div>', unsafe_allow_html=True)
            with t_col:
                st.dataframe(overlap_6_3.style.apply(highlight_overlap_name, common_tickers=common_tickers, axis=1), 
                             use_container_width=True, hide_index=True,
                             column_order=['통합티커', '종목명_L', '6-1개월(%)', '3-1개월(%)'], column_config=common_config)
        else: st.info("중복 없음")

    # --- 중단: 상위 30위 섹션 ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<p style="color: #6B7280; font-size: 0.9rem; font-style: italic;">※ 왼쪽의 No 숫자는 고정된 눈금자입니다. 표를 정렬해도 변하지 않습니다.</p>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    for col, title, sort_col in zip([col1, col2, col3], 
                                   ["🏆 12-1개월 상위 30", "🏆 6-1개월 상위 30", "🏆 3-1개월 상위 30"], 
                                   ["12-1개월(%)", "6-1개월(%)", "3-1개월(%)"]):
        with col:
            st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)
            r_col, t_col = st.columns([0.12, 0.88]) # 3분할이라 간격을 조금 더 줌
            with r_col:
                st.markdown('<div class="ruler-header">No</div>', unsafe_allow_html=True)
                for i in range(1, 31):
                    st.markdown(f'<div class="ruler-num">{i}</div>', unsafe_allow_html=True)
            with t_col:
                df_sub = df_300.sort_values(sort_col, ascending=False).head(30)
                st.dataframe(df_sub.style.apply(highlight_overlap_name, common_tickers=common_tickers, axis=1), 
                             use_container_width=True, height=1105, hide_index=True, # 높이를 눈금자와 맞춤
                             column_order=['통합티커', '종목명_L', sort_col], column_config=common_config)

    st.markdown("---")
    
    # --- 하단: 전체 순위표 ---
    st.markdown(f'### 📊 미국 시총상위 300종목 전체 (기준: {target_date_str})')
    r_col, t_col = st.columns([0.05, 0.95])
    with r_col:
        st.markdown('<div class="ruler-header">No</div>', unsafe_allow_html=True)
        for i in range(1, 301):
            st.markdown(f'<div class="ruler-num">{i}</div>', unsafe_allow_html=True)
    with t_col:
        st.dataframe(df_300, use_container_width=True, height=1100, hide_index=True,
                     column_order=['통합티커', '종목명_L', '기준가', '3-1개월(%)', '6-1개월(%)', '12-1개월(%)'],
                     column_config=common_config)

# 앱 실행
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
