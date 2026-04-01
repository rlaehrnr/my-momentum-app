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

# ⭐ 통합 스타일 함수: 지수 대비 약세(파랑) + 1,000만 주 이상(분홍)
def apply_custom_styling(row, idx_df):
    m_map = {'NYSE': 'S&P 500', 'NASDAQ': 'NASDAQ'}
    target = m_map.get(row['시장'])
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

tab1, tab2 = st.tabs(["📅 전월 말일 기준", "🕒 오늘(데일리) 기준"])

# 공통 컬럼 설정 (정렬 및 콤마 적용)
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

# --- [탭 1: 월말 고정 데이터] ---
with tab1:
    f_us = 'data/momentum_data_us.csv'
    if os.path.exists(f_us):
        df_us = pd.read_csv(f_us, dtype={'종목코드': str})
        
        # 💡 [추가] 컬럼 이름의 공백 제거 및 전달순위 숫자 변환
        df_us.columns = df_us.columns.str.replace(' ', '')
        
        b_date_str = df_us['기준일(월말)'].iloc[0]
        st.subheader(f"📅 월말 기준 데이터 (기준일: {b_date_str})")
        
        idx_us = get_idx_us(pd.to_datetime(b_date_str))
        if not idx_us.empty:
            idx_disp = idx_us.reset_index().copy()
            idx_disp['현재가'] = idx_disp['현재가'].map('{:,.1f}'.format)
            for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
                idx_disp[c] = idx_disp[c].map('{:+.1f}%'.format)
            st.table(idx_disp)
        
        # 💡 [순위 로직 수정] 
        # CSV에 이미 '전달순위'가 있다면 그걸 숫자로 바꾸고, 없을 때만 아카이브를 찾습니다.
        if '전달순위' in df_us.columns and df_us['전달순위'].notnull().any():
            df_us['전달순위'] = pd.to_numeric(df_us['전달순위'], errors='coerce')
        else:
            try:
                curr_dt = datetime.strptime(b_date_str, '%Y-%m-%d')
                prev_month_dt = curr_dt.replace(day=1) - timedelta(days=1)
                prev_ym = prev_month_dt.strftime('%Y_%m')
                f_prev_archive = f'archive_us/momentum_us_{prev_ym}.csv'
                
                if os.path.exists(f_prev_archive):
                    df_prev = pd.read_csv(f_prev_archive, dtype={'종목코드': str})
                    prev_rank_map = {str(code).strip().upper(): i+1 for i, code in enumerate(df_prev['종목코드'])}
                    df_us['전달순위'] = df_us['종목코드'].str.strip().str.upper().map(prev_rank_map)
                else: 
                    df_us['전달순위'] = None
            except: 
                df_us['전달순위'] = None

        st.markdown("---")
        df_us.index = range(1, len(df_us) + 1)
        df_us['통합티커'] = df_us['시장'] + ":" + df_us['종목코드']
        df_us['종목명_L'] = df_us.apply(lambda r: f"https://finance.yahoo.com/chart/{str(r['종목코드']).replace('.', '-')}#{r['종목명']}", axis=1)

        # 💡 column_config와 정렬이 잘 작동하도록 설정
        st.dataframe(
            df_us.style.apply(apply_custom_styling, idx_df=idx_us, axis=1),
            use_container_width=True, height=600,
            column_order=['통합티커', '종목명_L', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어', '전달순위'],
            column_config={**common_config, "전달순위": st.column_config.NumberColumn("전달 순위", format="%d위")}
        )

# --- [탭 2: 데일리 데이터] ---
with tab2:
    f_daily_us = 'data/momentum_data_daily_us.csv'
    f_monthly_ref = 'data/momentum_data_us.csv'
    
    if os.path.exists(f_daily_us):
        df_d_us = pd.read_csv(f_daily_us, dtype={'종목코드': str})
        
        # [전월 순위 대조 - 숫자로 변환]
        if os.path.exists(f_monthly_ref):
            df_m_ref = pd.read_csv(f_monthly_ref, dtype={'종목코드': str})
            rank_map = {code: i+1 for i, code in enumerate(df_m_ref['종목코드'])}
            df_d_us['전월순위'] = df_d_us['종목코드'].map(rank_map)
        else: df_d_us['전월순위'] = None

        d_date = df_d_us['기준일'].iloc[0]
        st.subheader(f"🕒 미국 데일리 실시간 (기준일: {d_date})")
        
        idx_now = get_idx_us() 
        if not idx_now.empty:
            idx_disp_now = idx_now.reset_index().copy()
            idx_disp_now['현재가'] = idx_disp_now['현재가'].map('{:,.1f}'.format)
            for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
                idx_disp_now[c] = idx_disp_now[c].map('{:+.1f}%'.format)
            st.table(idx_disp_now)
        
        st.markdown("---")
        # 거래량 데이터가 없는 경우 0으로 초기화
        if '전일거래량' not in df_d_us.columns: df_d_us['전일거래량'] = 0

        df_d_us.index = range(1, len(df_d_us) + 1)
        df_d_us['통합티커'] = df_d_us['시장'] + ":" + df_d_us['종목코드']
        df_d_us['종목명_L'] = df_d_us.apply(lambda r: f"https://finance.yahoo.com/chart/{r['종목코드'].replace('.', '-')}#{r['종목명']}", axis=1)

        st.dataframe(
            df_d_us.style.apply(apply_custom_styling, idx_df=idx_now, axis=1),
            use_container_width=True, height=600,
            column_order=['통합티커', '종목명_L', '기준가', '전일거래량', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어', '전월순위'],
            column_config={**common_config, "전월순위": st.column_config.NumberColumn("전월 순위", format="%d위")}
        )
