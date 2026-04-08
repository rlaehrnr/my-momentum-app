import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os
import yfinance as yf

# --- [1. 설정 및 스타일] ---
st.set_page_config(page_title="한국 모멘텀 순위", layout="wide")
st.markdown("""
    <style>
    .block-container { padding-top: 2rem !important; }
    .main-title { font-size: 1.6rem !important; font-weight: bold; margin-bottom: 1rem; }
    .stTabs [data-baseweb="tab"] { font-size: 18px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

def apply_k200_styling(row, idx_df, highlight_codes=None, overlap_codes=None):
    styles = [''] * len(row)
    market = row.get('시장', 'KOSPI')
    if isinstance(idx_df, pd.DataFrame) and market in idx_df.index:
        idx_r = idx_df.loc[market]
        for col in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
            if col in row.index and col in idx_r.index:
                col_idx = row.index.get_loc(col)
                if row[col] < idx_r[col]:
                    styles[col_idx] = 'background-color: #E3F2FD; color: #0047AB;'
                    
    code = row.get('종목코드')
    if code and '종목명_L' in row.index:
        name_idx = row.index.get_loc('종목명_L')
        if overlap_codes and code in overlap_codes:
            styles[name_idx] = 'background-color: #FFF59D; color: #D84315; font-weight: bold;'
        elif highlight_codes and code in highlight_codes:
            styles[name_idx] = 'background-color: #E8F5E9; color: #2E7D32; font-weight: bold;'
            
    return styles

@st.cache_data(ttl=3600)
def get_idx_kr(target_date=None):
    indices = {'KOSPI': 'KS11', 'KOSDAQ': 'KQ11'}
    today = datetime.today()
    res = []
    for name, code in indices.items():
        try:
            df = fdr.DataReader(code, today - pd.DateOffset(months=18), today)
            curr_val = df.loc[df.index <= target_date]['Close'].iloc[-1] if target_date else df['Close'].iloc[-1]
            last_date = df.index[df.index <= (target_date if target_date else today)][-1]
            def get_ret(m):
                ref = (last_date.replace(day=1) - pd.DateOffset(months=m-1)) - timedelta(days=1)
                p_df = df[df.index <= ref]
                return round(((curr_val / p_df['Close'].iloc[-1]) - 1) * 100, 1) if not p_df.empty else 0.0
            res.append({'시장': name, '현재가': curr_val, '1개월(%)': get_ret(1), '3개월(%)': get_ret(3), '6개월(%)': get_ret(6), '12개월(%)': get_ret(12)})
        except: pass
    return pd.DataFrame(res).set_index('시장')

# 공통 컬럼 설정
main_cfg = {
    "통합티커_L": st.column_config.LinkColumn("티커", display_text=r"#(.+)"), 
    "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), 
    "기준가": st.column_config.NumberColumn("종가", format="%,d"),
    "1개월(%)": st.column_config.NumberColumn(format="%.1f"), 
    "3개월(%)": st.column_config.NumberColumn(format="%.1f"), 
    "6개월(%)": st.column_config.NumberColumn(format="%.1f"), 
    "12개월(%)": st.column_config.NumberColumn(format="%.1f"),
    "모멘텀스코어": st.column_config.NumberColumn("스코어", format="%.2f"),
    "전달순위": st.column_config.NumberColumn("전달 순위", format="%d위")
}

f_kr = 'data/momentum_data.csv'
f_daily = 'data/momentum_data_daily.csv'

# 💡 KOSPI 200 탭을 분리하고 남은 2개의 탭
tab_monthly, tab_daily = st.tabs(["📅 전월 말일 기준", "🕒 오늘(데일리) 기준"])

# --- 탭 1: 전월 말일 기준 ---
with tab_monthly:
    if os.path.exists(f_kr):
        df_m = pd.read_csv(f_kr, dtype={'종목코드': str})
        
        if '전달순위' in df_m.columns:
            df_m['전달순위'] = pd.to_numeric(df_m['전달순위'], errors='coerce')
            
        df_m.index = range(1, len(df_m) + 1)
        b_date_m = df_m['기준일(월말)'].iloc[0]
        
        st.markdown(f'<p class="main-title">📊 월간 모멘텀 (기준: {b_date_m})</p>', unsafe_allow_html=True)
        
        idx_m = get_idx_kr(pd.to_datetime(b_date_m))
        idx_m_disp = idx_m.reset_index().copy()
        idx_m_disp['시장_L'] = idx_m_disp['시장'].apply(lambda x: f"https://m.stock.naver.com/domestic/index/{x}/total#{x}")
        idx_m_disp['현재가_L'] = idx_m_disp.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/index/{r['시장']}#{r['현재가']:,.2f}", axis=1)
        
        idx_cfg = {"시장_L": st.column_config.LinkColumn("시장", display_text=r"#(.+)"), "현재가_L": st.column_config.LinkColumn("현재가", display_text=r"#(.+)")}
        st.dataframe(idx_m_disp[['시장_L', '현재가_L', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']], use_container_width=True, hide_index=True, column_config=idx_cfg)
        
        st.markdown("---")
        df_m['통합티커_L'] = df_m.apply(lambda r: f"https://finance.naver.com/item/main.naver?code={str(r['종목코드']).zfill(6)}#{r['시장']}:{str(r['종목코드']).zfill(6)}", axis=1)
        df_m['종목명_L'] = df_m.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{str(r['종목코드']).zfill(6)}#{r['종목명']}", axis=1)
        
        st.dataframe(df_m.style.apply(apply_k200_styling, idx_df=idx_m, axis=1), use_container_width=True, height=550, column_order=['통합티커_L', '종목명_L', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어', '전달순위'], column_config=main_cfg)

# --- 탭 2: 오늘 기준 (데일리) ---
with tab_daily:
    if os.path.exists(f_daily):
        df_d = pd.read_csv(f_daily, dtype={'종목코드': str})
        
        if '전달순위' in df_d.columns:
            df_d['전달순위'] = pd.to_numeric(df_d['전달순위'], errors='coerce')
            
        df_d.index = range(1, len(df_d) + 1)
        b_date_d = df_d['기준일'].iloc[0]
        
        st.markdown(f'<p class="main-title">🕒 데일리 모멘텀 (기준: {b_date_d})</p>', unsafe_allow_html=True)
        
        idx_now = get_idx_kr()
        idx_now_disp = idx_now.reset_index().copy()
        idx_now_disp['시장_L'] = idx_now_disp['시장'].apply(lambda x: f"https://m.stock.naver.com/domestic/index/{x}/total#{x}")
        idx_now_disp['현재가_L'] = idx_now_disp.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/index/{r['시장']}#{r['현재가']:,.2f}", axis=1)
        
        st.dataframe(idx_now_disp[['시장_L', '현재가_L', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']], use_container_width=True, hide_index=True, column_config=idx_cfg)
        
        st.markdown("---")
        df_d['통합티커_L'] = df_d.apply(lambda r: f"https://finance.naver.com/item/main.naver?code={str(r['종목코드']).zfill(6)}#{r['시장']}:{str(r['종목코드']).zfill(6)}", axis=1)
        df_d['종목명_L'] = df_d.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{str(r['종목코드']).zfill(6)}#{r['종목명']}", axis=1)
        
        daily_cfg = main_cfg.copy()
        daily_cfg["기준가"] = st.column_config.NumberColumn("현재가", format="%,d") 
        daily_cfg["전일거래량"] = st.column_config.NumberColumn("전일거래량", format="%,d")
        
        st.dataframe(df_d.style.apply(apply_k200_styling, idx_df=idx_now, axis=1), use_container_width=True, height=600, column_order=['통합티커_L', '종목명_L', '기준가', '전일거래량', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어', '전달순위'], column_config=daily_cfg)
