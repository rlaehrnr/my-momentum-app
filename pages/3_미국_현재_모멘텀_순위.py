import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os

# 1. 페이지 설정
st.set_page_config(page_title="미국 모멘텀 순위", layout="wide")

# CSS: 레이아웃 및 서체 최적화
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem !important; }
    h1 { font-size: 2.0rem !important; font-weight: 800; margin-bottom: 10px; }
    .stTabs [data-baseweb="tab"] { font-size: 18px; font-weight: bold; }
    .sub-header { font-size: 1.2rem; font-weight: bold; margin-top: 10px; margin-bottom: 10px; padding-left: 10px; border-left: 5px solid #FF4B4B; background-color: #f0f2f6; padding-top: 5px; padding-bottom: 5px; }
    </style>
    """, unsafe_allow_html=True)

# ⭐ 모멘텀 중복 강조 스타일 함수
def highlight_overlap(row, overlap_groups):
    styles = [''] * len(row)
    code = row.get('종목코드')
    
    # 1. 트리플 크라운 (A+B 모두 해당)
    if code in overlap_groups['AB']:
        bg_color = '#FFF9C4'  # 노란색 (Triple)
        color = '#F57F17'
    # 2. A그룹 (12-1 & 6-1 중복)
    elif code in overlap_groups['A']:
        bg_color = '#E1F5FE'  # 연파랑 (Long-term)
        color = '#01579B'
    # 3. B그룹 (6-1 & 3-1 중복)
    elif code in overlap_groups['B']:
        bg_color = '#F3E5F5'  # 연보라 (Short-term)
        color = '#4A148C'
    else:
        return styles

    if '종목명_L' in row.index:
        idx = row.index.get_loc('종목명_L')
        styles[idx] = f'background-color: {bg_color}; color: {color}; font-weight: bold; border-radius: 4px;'
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

# 상단 타이틀
st.title("🇺🇸 미국 시총상위 모멘텀")

tab1, tab2, tab3 = st.tabs(["🎯 미국 시총상위 300 전체 순위", "📅 전월 말일 기준", "🕒 오늘(데일리) 기준"])

common_config = {
    "순위": st.column_config.NumberColumn("순위", format="%d위", width="small"),
    "통합티커": st.column_config.TextColumn("티커"),
    "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), 
    "기준가": st.column_config.NumberColumn("현재가", format="$ %,.2f"),
    "1개월(%)": st.column_config.NumberColumn("1M", format="%.1f%%"),
    "3개월(%)": st.column_config.NumberColumn("3M", format="%.1f%%"),
    "6개월(%)": st.column_config.NumberColumn("6M", format="%.1f%%"),
    "12개월(%)": st.column_config.NumberColumn("12M", format="%.1f%%"),
    "3-1개월(%)": st.column_config.NumberColumn("3-1M", format="%.1f%%"),
    "6-1개월(%)": st.column_config.NumberColumn("6-1M", format="%.1f%%"),
    "12-1개월(%)": st.column_config.NumberColumn("12-1M", format="%.1f%%"),
}

def display_momentum_dashboard(df_raw, target_date_str, idx_df):
    df_300 = df_raw.head(300).copy()
    df_300['통합티커'] = df_300['시장'] + ":" + df_300['종목코드']
    df_300['종목명_L'] = df_300.apply(lambda r: f"https://finance.yahoo.com/quote/{str(r['종목코드']).replace('.', '-')}#{r['종목명']}", axis=1)

    # 중복 체크를 위한 상위 30위 종목코드 집합 추출
    top12_1_codes = set(df_300.sort_values('12-1개월(%)', ascending=False).head(30)['종목코드'])
    top6_1_codes = set(df_300.sort_values('6-1개월(%)', ascending=False).head(30)['종목코드'])
    top3_1_codes = set(df_300.sort_values('3-1개월(%)', ascending=False).head(30)['종목코드'])

    overlap_groups = {
        'A': top12_1_codes.intersection(top6_1_codes),
        'B': top6_1_codes.intersection(top3_1_codes),
        'AB': top12_1_codes.intersection(top6_1_codes).intersection(top3_1_codes)
    }

    # --- 상단 3개 섹션 (순위 컬럼 추가) ---
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown('<p class="sub-header">🏆 12-1개월 상위 30</p>', unsafe_allow_html=True)
        # 해당 지표로 정렬 후 고정 순위 부여
        df1 = df_300.sort_values('12-1개월(%)', ascending=False).head(30).copy()
        df1['순위'] = range(1, 31)
        st.dataframe(df1.style.apply(highlight_overlap, overlap_groups=overlap_groups, axis=1),
                     use_container_width=True, height=450, hide_index=True,
                     column_order=['순위', '통합티커', '종목명_L', '12-1개월(%)'], column_config=common_config)

    with col2:
        st.markdown('<p class="sub-header">🏆 6-1개월 상위 30</p>', unsafe_allow_html=True)
        df2 = df_300.sort_values('6-1개월(%)', ascending=False).head(30).copy()
        df2['순위'] = range(1, 31)
        st.dataframe(df2.style.apply(highlight_overlap, overlap_groups=overlap_groups, axis=1),
                     use_container_width=True, height=450, hide_index=True,
                     column_order=['순위', '통합티커', '종목명_L', '6-1개월(%)'], column_config=common_config)

    with col3:
        st.markdown('<p class="sub-header">🏆 3-1개월 상위 30</p>', unsafe_allow_html=True)
        df3 = df_300.sort_values('3-1개월(%)', ascending=False).head(30).copy()
        df3['순위'] = range(1, 31)
        st.dataframe(df3.style.apply(highlight_overlap, overlap_groups=overlap_groups, axis=1),
                     use_container_width=True, height=450, hide_index=True,
                     column_order=['순위', '통합티커', '종목명_L', '3-1개월(%)'], column_config=common_config)

    st.markdown("---")
    
    # --- 하단 전체 순위표 (원래 시총 순위) ---
    st.markdown(f'### 📊 미국 시총상위 300종목 전체 현황 (기준: {target_date_str})')
    df_300['시총순위'] = range(1, len(df_300) + 1)
    st.dataframe(df_300.style.apply(highlight_overlap, overlap_groups=overlap_groups, axis=1),
                 use_container_width=True, height=600, hide_index=True,
                 column_order=['시총순위', '통합티커', '종목명_L', '기준가', '3-1개월(%)', '6-1개월(%)', '12-1개월(%)'],
                 column_config={**common_config, "시총순위": st.column_config.NumberColumn("시총순위", format="%d위")})

# 탭 내용 구현
with tab1:
    f_us = 'data/momentum_data_us.csv'
    if os.path.exists(f_us):
        df_raw = pd.read_csv(f_us, dtype={'종목코드': str})
        df_raw.columns = df_raw.columns.str.replace(' ', '')
        b_date = df_raw['기준일(월말)'].iloc[0]
        idx_us = get_idx_us(pd.to_datetime(b_date))
        display_momentum_dashboard(df_raw, b_date, idx_us)

with tab2:
    if os.path.exists(f_us):
        df_raw = pd.read_csv(f_us, dtype={'종목코드': str})
        df_raw.columns = df_raw.columns.str.replace(' ', '')
        b_date = df_raw['기준일(월말)'].iloc[0]
        idx_us = get_idx_us(pd.to_datetime(b_date))
        display_momentum_dashboard(df_raw, b_date, idx_us)

with tab3:
    f_daily = 'data/momentum_data_daily_us.csv'
    if os.path.exists(f_daily):
        df_raw = pd.read_csv(f_daily, dtype={'종목코드': str})
        d_date = df_raw['기준일'].iloc[0]
        idx_now = get_idx_us()
        display_momentum_dashboard(df_raw, d_date, idx_now)
