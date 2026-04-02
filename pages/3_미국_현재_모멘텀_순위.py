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
        padding: 10px 15px;
        border-radius: 8px 8px 0 0;
        font-size: 1.1rem;
        font-weight: bold;
        border-bottom: 4px solid #EF4444;
        margin-top: 25px;
    }
    .overlap-header {
        background-color: #1E3A8A;
        color: white;
        padding: 10px 15px;
        border-radius: 8px 8px 0 0;
        font-size: 1.1rem;
        font-weight: bold;
        border-bottom: 4px solid #F59E0B;
    }
    </style>
    """, unsafe_allow_html=True)

# ⭐ 신규: 지수 이동평균선 데이터 수집 함수
@st.cache_data(ttl=3600)
def get_index_ma_status():
    indices = {'S&P 500': 'US500', 'NASDAQ': 'IXIC'}
    today = datetime.today()
    start_date = today - timedelta(days=400) # 200일선 계산을 위해 충분한 데이터 확보
    
    res = []
    for name, code in indices.items():
        try:
            df = fdr.DataReader(code, start_date, today)
            if df.empty: continue
            
            curr_price = df['Close'].iloc[-1]
            # 이동평균선 계산
            ma_values = {
                '지수': name,
                '현재가': round(curr_price, 2),
                '10일선': round(df['Close'].rolling(10).mean().iloc[-1], 2),
                '20일선': round(df['Close'].rolling(20).mean().iloc[-1], 2),
                '60일선': round(df['Close'].rolling(60).mean().iloc[-1], 2),
                '120일선': round(df['Close'].rolling(120).mean().iloc[-1], 2),
                '200일선': round(df['Close'].rolling(200).mean().iloc[-1], 2)
            }
            res.append(ma_values)
        except: pass
    return pd.DataFrame(res)

# ⭐ 신규: 이동평균선 색상 스타일 함수
def style_index_ma(df):
    def apply_color(row):
        price = row['현재가']
        styles = [''] * len(row)
        for i, col in enumerate(row.index):
            if '일선' in col:
                val = row[col]
                if val < price:
                    styles[i] = 'color: #EF4444; font-weight: bold;' # 현재가보다 낮으면 붉은색
                elif val > price:
                    styles[i] = 'color: #3B82F6; font-weight: bold;' # 현재가보다 높으면 파란색
        return styles
    return df.style.apply(apply_color, axis=1)

# 기존 하이라이트 함수
def highlight_name_only(row, common_tickers):
    styles = [''] * len(row)
    if row.get('종목코드') in common_tickers:
        if '종목명_L' in row.index:
            name_idx = row.index.get_loc('종목명_L')
            styles[name_idx] = 'background-color: #FFF9C4; color: #1F2937; font-weight: bold;'
    return styles

# 기존 테이블 설정
common_config = {
    "순위": st.column_config.NumberColumn("순위", format="%d", width=40),
    "통합티커": st.column_config.TextColumn("티커", width=105),
    "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)", width=None),
    "기준가": st.column_config.NumberColumn("현재가", format="$ %,.2f", width=95),
    "12-1개월(%)": st.column_config.NumberColumn("12-1M", format="%.1f%%", width=85),
    "6-1개월(%)": st.column_config.NumberColumn("6-1M", format="%.1f%%", width=85),
    "3-1개월(%)": st.column_config.NumberColumn("3-1M", format="%.1f%%", width=85),
}

def display_momentum_dashboard(df_raw, target_date_str):
    # --- [상단 신규 추가] 지수 이동평균선 현황판 ---
    st.markdown("### 📊 주요 지수 이동평균선 현황")
    ma_df = get_index_ma_status()
    if not ma_df.empty:
        st.dataframe(style_index_ma(ma_df), use_container_width=True, hide_index=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # 기존 로직 (건드리지 않음)
    df_300 = df_raw.head(300).copy()
    for c in ['3-1개월(%)', '6-1개월(%)', '12-1개월(%)']:
        if c in df_300.columns:
            df_300[c] = pd.to_numeric(df_300[c], errors='coerce').fillna(0.0)

    df_300['통합티커'] = df_300['시장'].astype(str) + ":" + df_300['종목코드'].astype(str)
    df_300['종목명_L'] = df_300.apply(lambda r: f"https://finance.yahoo.com/chart/{str(r['종목코드']).replace('.', '-')}#{r['종목명']}", axis=1)

    top10_12_1 = df_300.sort_values('12-1개월(%)', ascending=False).head(10)
    top10_6_1 = df_300.sort_values('6-1개월(%)', ascending=False).head(10)
    top10_3_1 = df_300.sort_values('3-1개월(%)', ascending=False).head(10)

    overlap_12_6 = top10_12_1[top10_12_1['종목코드'].isin(top10_6_1['종목코드'])].copy()
    overlap_6_3 = top10_6_1[top10_6_1['종목코드'].isin(top10_3_1['종목코드'])].copy()
    common_tickers = set(overlap_12_6['종목코드']).intersection(set(overlap_6_3['종목코드']))

    st.markdown("### 🌟 모멘텀 교집합 (TOP 10 중복 분석)")
    c_over1, c_over2 = st.columns(2)
    with c_over1:
        st.markdown('<div class="overlap-header">🔥 12-1M & 6-1M 중복</div>', unsafe_allow_html=True)
        if not overlap_12_6.empty:
            overlap_12_6['순위'] = range(1, len(overlap_12_6) + 1)
            st.dataframe(overlap_12_6.style.apply(highlight_name_only, common_tickers=common_tickers, axis=1), 
                         use_container_width=True, hide_index=True,
                         column_order=['순위', '통합티커', '종목명_L', '12-1개월(%)', '6-1개월(%)'], column_config=common_config)
        else: st.info("중복 종목 없음")
    with c_over2:
        st.markdown('<div class="overlap-header">⚡ 6-1M & 3-1M 중복</div>', unsafe_allow_html=True)
        if not overlap_6_3.empty:
            overlap_6_3['순위'] = range(1, len(overlap_6_3) + 1)
            st.dataframe(overlap_6_3.style.apply(highlight_name_only, common_tickers=common_tickers, axis=1), 
                         use_container_width=True, hide_index=True,
                         column_order=['순위', '통합티커', '종목명_L', '6-1개월(%)', '3-1개월(%)'], column_config=common_config)
        else: st.info("중복 종목 없음")

    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    for col, title, sort_col in zip([col1, col2, col3], 
                                   ["🏆 12-1개월 상위 30", "🏆 6-1개월 상위 30", "🏆 3-1개월 상위 30"], 
                                   ["12-1개월(%)", "6-1개월(%)", "3-1개월(%)"]):
        with col:
            st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)
            df_sub = df_300.sort_values(sort_col, ascending=False).head(30).copy()
            df_sub['순위'] = range(1, 31)
            st.dataframe(df_sub.style.apply(highlight_name_only, common_tickers=common_tickers, axis=1), 
                         use_container_width=True, height=450, hide_index=True,
                         column_order=['순위', '통합티커', '종목명_L', sort_col], column_config=common_config)

    st.markdown("---")
    st.markdown(f'### 📊 미국 시총상위 300종목 전체 (기준: {target_date_str})')
    df_300_all = df_300.copy()
    df_300_all['순위'] = range(1, len(df_300_all) + 1)
    st.dataframe(df_300_all.style.apply(highlight_name_only, common_tickers=common_tickers, axis=1), 
                 use_container_width=True, height=600, hide_index=True,
                 column_order=['순위', '통합티커', '종목명_L', '기준가', '3-1개월(%)', '6-1개월(%)', '12-1개월(%)'],
                 column_config=common_config)

# 실행부
st.title("🇺🇸 미국 시총상위 모멘텀")
t1, t2 = st.tabs(["📅 전월 말일 기준", "🕒 오늘(데일리) 기준"])

f_us, f_daily = 'data/momentum_data_us.csv', 'data/momentum_data_daily_us.csv'

with t1:
    if os.path.exists(f_us):
        df = pd.read_csv(f_us, dtype={'종목코드': str})
        df.columns = df.columns.str.replace(' ', '')
        display_momentum_dashboard(df, df['기준일(월말)'].iloc[0])
with t2:
    if os.path.exists(f_daily):
        df = pd.read_csv(f_daily, dtype={'종목코드': str})
        df.columns = df.columns.str.replace(' ', '')
        display_momentum_dashboard(df, df['기준일'].iloc[0])
