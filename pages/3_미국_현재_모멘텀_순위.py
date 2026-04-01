import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os

# 1. 페이지 설정
st.set_page_config(page_title="미국 모멘텀 순위", layout="wide")

# CSS: 레이아웃 최적화
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem !important; }
    h1 { font-size: 2.0rem !important; font-weight: 800; margin-bottom: 10px; }
    [data-testid="stTable"] { margin-bottom: -25px; }
    .stTabs [data-baseweb="tab"] { font-size: 18px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# ⭐ 통합 스타일 함수: 지수 대비 약세(파랑) + 1,000만 주 이상(분홍) + 교집합(노랑)
def apply_custom_styling(row, idx_df, common_codes=None):
    m_map = {'NYSE': 'S&P 500', 'NASDAQ': 'NASDAQ'}
    target = m_map.get(row.get('시장', 'NYSE'))
    styles = [''] * len(row)
    
    # 1. 지수 대비 수익률 하이라이트 (파란색)
    if target in idx_df.index:
        idx_r = idx_df.loc[target]
        for col in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
            if col in row.index:
                col_idx = row.index.get_loc(col)
                if row[col] < idx_r[col]:
                    styles[col_idx] = 'background-color: #E3F2FD; color: #0047AB;'

    # 2. 거래량 1,000만 주 이상 하이라이트 (연분홍색)
    if '전일거래량' in row.index and row['전일거래량'] >= 10000000:
        vol_idx = row.index.get_loc('전일거래량')
        styles[vol_idx] = 'background-color: #FFEBEE; color: #B71C1C; font-weight: bold;'
        
    # 3. 교집합 종목 하이라이트 (노란색)
    if common_codes and '종목코드' in row.index and row['종목코드'] in common_codes:
        if '종목명_L' in row.index:
            styles[row.index.get_loc('종목명_L')] = 'background-color: #FFF59D; color: #D84315; font-weight: bold;'
            
    return styles

@st.cache_data(ttl=3600)
def get_idx_us(target_date=None):
    indices = {'S&P 500': 'US500', 'NASDAQ': 'IXIC'}
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

# 탭 순서
tab1, tab2, tab3 = st.tabs(["🎯 미국 강세 종목", "📅 전월 말일 기준", "🕒 오늘(데일리) 기준"])

# 공통 컬럼 설정
common_config = {
    "통합티커": st.column_config.TextColumn("티커"),
    "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), 
    "기준가": st.column_config.NumberColumn("현재가", format="$ %,.2f"),
    "전일거래량": st.column_config.NumberColumn("전일거래량", format="%,d"),
    "1개월(%)": st.column_config.NumberColumn("1M (%)", format="%.1f%%"),
    "3개월(%)": st.column_config.NumberColumn("3M (%)", format="%.1f%%"),
    "6개월(%)": st.column_config.NumberColumn("6M (%)", format="%.1f%%"),
    "12개월(%)": st.column_config.NumberColumn("12M (%)", format="%.1f%%"),
    "모멘텀스코어": st.column_config.NumberColumn("스코어", format="%.2f"),
}

# --- [탭 1: 미국 시총상위 강세 종목 (CSV 순수 로딩)] ---
with tab1:
    f_us = 'data/momentum_data_us.csv'
    if os.path.exists(f_us):
        df_raw_us = pd.read_csv(f_us, dtype={'종목코드': str})
        df_raw_us.columns = df_raw_us.columns.str.replace(' ', '')
        
        b_date_str = df_raw_us['기준일(월말)'].iloc[0]
        st.markdown(f'<p style="font-size: 1.6rem !important; font-weight: bold; margin-bottom: 1rem;">🎯 미국 시총상위 강세 종목 집중 분석 (기준: {b_date_str})</p>', unsafe_allow_html=True)
        
        idx_us = get_idx_us(pd.to_datetime(b_date_str))
        sp500_1m = idx_us.loc['S&P 500', '1개월(%)'] if 'S&P 500' in idx_us.index else 0.0
        sp500_3m = idx_us.loc['S&P 500', '3개월(%)'] if 'S&P 500' in idx_us.index else 0.0

        # 인터넷 다운로드 로직 전부 삭제! 순수 CSV 데이터만 사용
        df_us_300 = df_raw_us.copy()
        
        # CSV에 있는 300종목 순위 부여 (스코어 순)
        df_us_300['순위'] = range(1, len(df_us_300) + 1)
        df_us_300 = df_us_300.set_index('순위')
        
        df_us_300['통합티커'] = df_us_300['시장'] + ":" + df_us_300['종목코드']
        df_us_300['종목명_L'] = df_us_300.apply(lambda r: f"https://finance.yahoo.com/quote/{str(r['종목코드']).replace('.', '-')}#{r['종목명']}", axis=1)

        neg_1m_cnt = (df_us_300['1개월(%)'] < 0).sum()
        neg_3m_cnt = (df_us_300['3개월(%)'] < 0).sum()
        
        if neg_1m_cnt >= 150 and neg_3m_cnt >= 150:
            invest_status, box_color, text_color = "🛑 투자 중지", "#FFEBEE", "#C62828"
        else:
            invest_status, box_color, text_color = "✅ 투자 진행", "#E8F5E9", "#2E7D32"

        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 1.5])
        
        with col1: st.metric(label="📈 S&P 500 1M", value=f"{sp500_1m}%")
        with col2: st.metric(label="📈 S&P 500 3M", value=f"{sp500_3m}%")
        with col3: st.metric(label="📉 1개월 하락 종목", value=f"{neg_1m_cnt}개")
        with col4: st.metric(label="📉 3개월 하락 종목", value=f"{neg_3m_cnt}개")
        with col5:
            st.markdown(f"""
            <div style="background-color: {box_color}; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid {text_color};">
                <p style="margin: 0; font-size: 14px; color: {text_color}; font-weight: bold;">최종 판단 지표</p>
                <h3 style="margin: 5px 0 0 0; color: {text_color};">{invest_status}</h3>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown("<br><hr>", unsafe_allow_html=True)

        q30 = {c: df_us_300[c].quantile(0.7) for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']}
        t10_1m = df_us_300['1개월(%)'].quantile(0.9)
        
        cond_perf = (df_us_300['1개월(%)']>=q30['1개월(%)'])&(df_us_300['3개월(%)']>=q30['3개월(%)'])&(df_us_300['6개월(%)']>=q30['6개월(%)'])&(df_us_300['12개월(%)']>=q30['12개월(%)']) & \
                    (df_us_300['1개월(%)']>0)&(df_us_300['3개월(%)']>0)&(df_
