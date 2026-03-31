import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os

st.set_page_config(page_title="한국 모멘텀 순위", layout="wide")

# CSS: 초밀착 레이아웃
st.markdown("""<style>.block-container { padding-top: 2.5rem !important; } h1 { font-size: 2rem !important; } .stTabs [data-baseweb="tab"] { font-size: 18px; font-weight: bold; }</style>""", unsafe_allow_html=True)

# ⭐ 수정된 스타일 함수: 행 전체가 아니라 특정 '컬럼'만 조준 사격
def apply_custom_styling(row, idx_df):
    styles = [''] * len(row)
    
    # 1. 지수 대비 수익률 하이라이트 (수익률 컬럼들만 파란색)
    if '시장' in row and row['시장'] in idx_df.index:
        idx_r = idx_df.loc[row['시장']]
        for col_name in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
            if col_name in row.index:
                col_idx = row.index.get_loc(col_name)
                if row[col_name] < idx_r[col_name]:
                    styles[col_idx] = 'background-color: #E3F2FD; color: #0047AB;'

    # 2. 거래량 1,000만 주 이상 하이라이트 (거래량 컬럼'만' 연분홍색)
    if '전일거래량' in row.index:
        vol_idx = row.index.get_loc('전일거래량')
        if row['전일거래량'] >= 10000000:
            styles[vol_idx] = 'background-color: #FFEBEE; color: #B71C1C; font-weight: bold;'
            
    return styles

@st.cache_data(ttl=3600)
def get_idx_kr(target_date=None):
    indices = {'KOSPI': 'KS11', 'KOSDAQ': 'KQ11'}
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
                return round((curr_val - p_df['Close'].iloc[-1]) / p_df['Close'].iloc[-1] * 100, 1) if not p_df.empty else 0.0
            res.append({'시장': name, '현재가': curr_val, '1개월(%)': get_ret(1), '3개월(%)': get_ret(3), '6개월(%)': get_ret(6), '12개월(%)': get_ret(12)})
        except: pass
    return pd.DataFrame(res).set_index('시장')

tab1, tab2 = st.tabs(["📅 전월 말일 기준", "🕒 오늘(데일리) 기준"])

with tab1:
    f_kr = 'data/momentum_data.csv'
    if os.path.exists(f_kr):
        df_kr = pd.read_csv(f_kr, dtype={'종목코드': str})
        b_date_str = df_kr['기준일(월말)'].iloc[0]
        st.title(f"📊 한국 모멘텀 (기준: {b_date_str})")
        
        idx_kr = get_idx_kr(pd.to_datetime(b_date_str))
        if not idx_kr.empty: 
            idx_disp = idx_kr.reset_index().copy()
            idx_disp['현재가'] = idx_disp['현재가'].map('{:,.0f}'.format)
            st.table(idx_disp)
        
        st.markdown("---")
        
        try:
            curr_dt = datetime.strptime(b_date_str, '%Y-%m-%d')
            prev_month_dt = curr_dt.replace(day=1) - timedelta(days=1)
            prev_ym = prev_month_dt.strftime('%Y_%m')
            f_prev_archive = f'archive/momentum_{prev_ym}.csv'
            if os.path.exists(f_prev_archive):
                df_prev = pd.read_csv(f_prev_archive, dtype={'종목코드': str})
                prev_rank_map = {code: i+1 for i, code in enumerate(df_prev['종목코드'])}
                df_kr['전달순위'] = df_kr['종목코드'].map(prev_rank_map).apply(lambda x: f"{int(x)}위" if pd.notnull(x) else "⭐ NEW")
            else: df_kr['전달순위'] = "기록 없음"
        except: df_kr['전달순위'] = "-"

        df_kr.index = range(1, len(df_kr) + 1)
        df_kr['통합티커'] = df_kr['시장'] + ":" + df_kr['종목코드'].str.zfill(6)
        df_kr['종목명'] = df_kr.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)

        # 스타일 적용 (수익률 컬럼만 파랑)
        st.dataframe(df_kr.style.apply(apply_custom_styling, idx_df=idx_kr, axis=1), use_container_width=True, height=560, 
                     column_order=['통합티커', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어', '전달순위'], 
                     column_config={
                         "종목명": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), 
                         "기준가": st.column_config.NumberColumn("현재가", format="%,d"), 
                         "1개월(%)": st.column_config.NumberColumn(format="%.1f"), 
                         "3개월(%)": st.column_config.NumberColumn(format="%.1f"), 
                         "6개월(%)": st.column_config.NumberColumn(format="%.1f"), 
                         "12개월(%)": st.column_config.NumberColumn(format="%.1f"), 
                         "모멘텀스코어": st.column_config.NumberColumn(format="%.1f")
                     })

with tab2:
    f_daily = 'data/momentum_data_daily.csv'
    f_monthly_ref = 'data/momentum_data.csv'
    if os.path.exists(f_daily):
        df_d = pd.read_csv(f_daily, dtype={'종목코드': str})
        if os.path.exists(f_monthly_ref):
            df_m_ref = pd.read_csv(f_monthly_ref, dtype={'종목코드': str})
            rank_map = {code: i+1 for i, code in enumerate(df_m_ref['종목코드'])}
            df_d['전월순위'] = df_d['종목코드'].map(rank_map).apply(lambda x: f"{int(x)}위" if pd.notnull(x) else "⭐ NEW")
        else: df_d['전월순위'] = "-"

        st.title(f"🕒 데일리 모멘텀 (기준: {df_d['기준일'].iloc[0]})")
        idx_now = get_idx_kr()
        if not idx_now.empty: 
            idx_disp_now = idx_now.reset_index().copy()
            idx_disp_now['현재가'] = idx_disp_now['현재가'].map('{:,.0f}'.format)
            st.table(idx_disp_now)
        
        st.markdown("---")
        if '전일거래량' not in df_d.columns: df_d['전일거래량'] = 0 

        df_d.index = range(1, len(df_d) + 1)
        df_d['통합티커'] = df_d['시장'] + ":" + df_d['종목코드'].str.zfill(6)
        df_d['종목명'] = df_d.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)

        # 스타일 적용 (거래량 컬럼만 핑크)
        st.dataframe(df_d.style.apply(apply_custom_styling, idx_df=idx_now, axis=1), use_container_width=True, height=560, 
                     column_order=['통합티커', '종목명', '기준가', '전일거래량', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어', '전월순위'], 
                     column_config={
                         "종목명": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), 
                         "기준가": st.column_config.NumberColumn("현재가", format="%,d"), 
                         "전일거래량": st.column_config.NumberColumn("전일거래량", format="%,d"), 
                         "1개월(%)": st.column_config.NumberColumn(format="%.1f"), 
                         "3개월(%)": st.column_config.NumberColumn(format="%.1f"), 
                         "6개월(%)": st.column_config.NumberColumn(format="%.1f"), 
                         "12개월(%)": st.column_config.NumberColumn(format="%.1f"), 
                         "모멘텀스코어": st.column_config.NumberColumn(format="%.1f")
                     })
