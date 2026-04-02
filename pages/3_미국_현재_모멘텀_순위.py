import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os

# 1. 페이지 설정
st.set_page_config(page_title="미국 모멘텀 순위", layout="wide")

# CSS: 눈 보호를 위한 연한 색상 및 헤더 디자인
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem !important; }
    h1 { font-size: 2.2rem !important; font-weight: 800; margin-bottom: 20px; }
    
    /* 섹션 제목 스타일 */
    .overlap-header {
        background-color: #1E3A8A;
        color: white;
        padding: 10px 15px;
        border-radius: 8px 8px 0 0;
        font-size: 1.2rem;
        font-weight: bold;
        border-bottom: 4px solid #F59E0B;
        margin-bottom: 0px;
    }
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
    /* 고정된 줄 번호를 위한 안내 텍스트 */
    .ruler-info {
        font-size: 0.85rem;
        color: #6B7280;
        margin-bottom: 5px;
        font-style: italic;
    }
    </style>
    """, unsafe_allow_html=True)

# ⭐ 아주 연한 파스텔 톤 하이라이트 (눈 보호용)
def highlight_soft(row, common_tickers):
    styles = [''] * len(row)
    if row.get('종목코드') in common_tickers:
        # 은은한 레몬 크림색 (거의 흰색에 가까운 연한 노랑)
        for i in range(len(styles)):
            styles[i] = 'background-color: #FFFBCC; color: #444; font-weight: bold;'
    return styles

# 테이블 공통 컬럼 설정
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
    
    # 🔗 [수정] 야후 파이낸스 '차트' 링크로 직접 연결
    df_300['종목명_L'] = df_300.apply(lambda r: f"https://finance.yahoo.com/chart/{str(r['종목코드']).replace('.', '-')}#{r['종목명']}", axis=1)

    # 교집합 데이터 추출 (TOP 10 기준)
    top10_12_1 = df_300.sort_values('12-1개월(%)', ascending=False).head(10)
    top10_6_1 = df_300.sort_values('6-1개월(%)', ascending=False).head(10)
    top10_3_1 = df_300.sort_values('3-1개월(%)', ascending=False).head(10)

    overlap_12_6 = top10_12_1[top10_12_1['종목코드'].isin(top10_6_1['종목코드'])].copy()
    overlap_6_3 = top10_6_1[top10_6_1['종목코드'].isin(top10_3_1['종목코드'])].copy()
    
    # 두 교집합 표에 모두 등장하는 종목 (강조용)
    common_tickers = set(overlap_12_6['종목코드']).intersection(set(overlap_6_3['종목코드']))

    # --- 상단: 교집합 섹션 ---
    st.markdown("### 🌟 모멘텀 교집합 (TOP 10 중복 분석)")
    c_over1, c_over2 = st.columns(2)
    
    with c_over1:
        st.markdown('<div class="overlap-header">🔥 12-1M & 6-1M 중복</div>', unsafe_allow_html=True)
        if not overlap_12_6.empty:
            # 💡 [핵심] 인덱스를 1, 2, 3...으로 고정. 정렬 버튼을 눌러도 '왼쪽 회색 숫자'는 1, 2, 3으로 고정됩니다.
            overlap_12_6 = overlap_12_6.reset_index(drop=True)
            overlap_12_6.index += 1
            st.dataframe(overlap_12_6.style.apply(highlight_soft, common_tickers=common_tickers, axis=1), 
                         use_container_width=True, hide_index=False, # 회색 숫자 노출
                         column_order=['통합티커', '종목명_L', '12-1개월(%)', '6-1개월(%)'], column_config=common_config)
        else: st.info("중복 종목 없음")

    with c_over2:
        st.markdown('<div class="overlap-header">⚡ 6-1M & 3-1M 중복</div>', unsafe_allow_html=True)
        if not overlap_6_3.empty:
            overlap_6_3 = overlap_6_3.reset_index(drop=True)
            overlap_6_3.index += 1
            st.dataframe(overlap_6_3.style.apply(highlight_soft, common_tickers=common_tickers, axis=1), 
                         use_container_width=True, hide_index=False,
                         column_order=['통합티커', '종목명_L', '6-1개월(%)', '3-1개월(%)'], column_config=common_config)
        else: st.info("중복 종목 없음")

    # --- 중단: 상위 30위 섹션 ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<p class="ruler-info">※ 표 왼쪽의 회색 숫자는 고정된 줄 번호(눈금자)입니다. 어떤 기준으로 정렬해도 변하지 않습니다.</p>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    
    for col, title, sort_col in zip([col1, col2, col3], 
                                   ["🏆 12-1개월 상위 30", "🏆 6-1개월 상위 30", "🏆 3-1개월 상위 30"], 
                                   ["12-1개월(%)", "6-1개월(%)", "3-1개월(%)"]):
        with col:
            st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)
            df_sub = df_300.sort_values(sort_col, ascending=False).head(30).copy()
            df_sub = df_sub.reset_index(drop=True)
            df_sub.index += 1 # 줄 번호 고정
            st.dataframe(df_sub, use_container_width=True, height=450, hide_index=False,
                         column_order=['통합티커', '종목명_L', sort_col], column_config=common_config)

    st.markdown("---")
    
    # --- 하단: 전체 순위표 ---
    st.markdown(f'### 📊 미국 시총상위 300종목 전체 (기준: {target_date_str})')
    df_300_all = df_300.copy().reset_index(drop=True)
    df_300_all.index += 1 # 시총 순위 눈금자 고정
    st.dataframe(df_300_all, use_container_width=True, height=600, hide_index=False,
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
