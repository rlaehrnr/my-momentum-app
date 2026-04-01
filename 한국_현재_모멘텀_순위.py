import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os

# --- [1. 설정 및 스타일] ---
st.set_page_config(page_title="한국 모멘텀 순위", layout="wide")
st.markdown("""
<style>
    .block-container { padding-top: 2rem !important; }
    .main-title { font-size: 1.6rem !important; font-weight: bold; margin-bottom: 1rem; }
    .stTabs [data-baseweb="tab"] { font-size: 18px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# 스타일 함수
def apply_k200_styling(row, idx_df, common_codes=None):
    styles = [''] * len(row)
    market = row.get('시장', 'KOSPI')
    if market in idx_df.index:
        idx_r = idx_df.loc[market]
        for col in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
            if col in row.index and col in idx_r.index:
                col_idx = row.index.get_loc(col)
                if row[col] < idx_r[col]:
                    styles[col_idx] = 'background-color: #E3F2FD; color: #0047AB;'
    if common_codes and '종목코드' in row.index and row['종목코드'] in common_codes:
        if '종목명_L' in row.index:
            styles[row.index.get_loc('종목명_L')] = 'background-color: #FFF59D; color: #D84315; font-weight: bold;'
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

tab1, tab2, tab3 = st.tabs(["📅 전월 말일 기준", "🕒 오늘(데일리) 기준", "🎯 KOSPI 200 강세 종목"])
f_kr = 'data/momentum_data.csv'
f_daily = 'data/momentum_data_daily.csv'

# 공통 Config
main_cfg = {
    "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), 
    "기준가": st.column_config.NumberColumn("말일 종가", format="%,d"), # 탭 1, 3용 명칭 변경
    "1개월(%)": st.column_config.NumberColumn(format="%.1f"), 
    "3개월(%)": st.column_config.NumberColumn(format="%.1f"), 
    "6개월(%)": st.column_config.NumberColumn(format="%.1f"), 
    "12개월(%)": st.column_config.NumberColumn(format="%.1f")
}

# --- 탭 1: 전월 말일 기준 ---
with tab1:
    if os.path.exists(f_kr):
        df_m = pd.read_csv(f_kr, dtype={'종목코드': str})
        b_date = df_m['기준일(월말)'].iloc[0]
        st.markdown(f'<p class="main-title">📊 월간 모멘텀 (기준: {b_date})</p>', unsafe_allow_html=True)
        
        idx_m = get_idx_kr(pd.to_datetime(b_date))
        st.table(idx_m.reset_index().assign(현재가=lambda x: x['현재가'].map('{:,.0f}'.format)))
        
        st.markdown("---")
        # ⭐ 수정 1: 순위 1부터 시작
        df_m.index = range(1, len(df_m) + 1)
        
        df_m['통합티커'] = df_m['시장'] + ":" + df_m['종목코드'].str.zfill(6)
        df_m['종목명_L'] = df_m.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)
        
        # ⭐ 수정 2: '기준가'(말일 종가)를 메인 가격으로 사용
        st.dataframe(df_m.style.apply(apply_k200_styling, idx_df=idx_m, axis=1), use_container_width=True, height=550,
                     column_order=['통합티커', '종목명_L', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)'], column_config=main_cfg)

# --- 탭 2: 오늘 기준 (데일리) ---
with tab2:
    if os.path.exists(f_daily):
        df_d = pd.read_csv(f_daily, dtype={'종목코드': str})
        b_date_d = df_d['기준일'].iloc[0]
        st.markdown(f'<p class="main-title">🕒 데일리 모멘텀 (기준: {b_date_d})</p>', unsafe_allow_html=True)
        
        idx_now = get_idx_kr()
        st.table(idx_now.reset_index().assign(현재가=lambda x: x['현재가'].map('{:,.0f}'.format)))
        
        st.markdown("---")
        # ⭐ 수정 1: 순위 1부터 시작
        df_d.index = range(1, len(df_d) + 1)
        
        df_d['통합티커'] = df_d['시장'] + ":" + df_d['종목코드'].str.zfill(6)
        df_d['종목명_L'] = df_d.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)
        
        daily_cfg = main_cfg.copy()
        daily_cfg["기준가"] = st.column_config.NumberColumn("현재가", format="%,d") # 데일리는 현재가로 표기
        
        st.dataframe(df_d.style.apply(apply_k200_styling, idx_df=idx_now, axis=1), use_container_width=True, height=550,
                     column_order=['통합티커', '종목명_L', '기준가', '전일거래량', '1개월(%)', '12개월(%)'], 
                     column_config={**daily_cfg, "전일거래량": st.column_config.NumberColumn(format="%,d")})

# --- 탭 3: KOSPI 200 집중 분석 ---
with tab3:
    if os.path.exists(f_kr):
        df_raw = pd.read_csv(f_kr, dtype={'종목코드': str})
        b_date_str = df_raw['기준일(월말)'].iloc[0]
        st.markdown(f'<p class="main-title">🎯 KOSPI 200 집중 분석 (기준: {b_date_str})</p>', unsafe_allow_html=True)
        
        idx_k = get_idx_kr(pd.to_datetime(b_date_str))
        st.table(idx_k.reset_index().assign(현재가=lambda x: x['현재가'].map('{:,.0f}'.format)))

        st.markdown("---")
        m_col = next((c for c in df_raw.columns if '시가' in c or 'mar' in c.lower()), '시가총액')
        df_k200 = df_raw[(df_raw['시장'] == 'KOSPI') & (df_raw['종목코드'].str.endswith('0'))].copy()
        if m_col in df_k200.columns: df_k200 = df_k200.sort_values(by=m_col, ascending=False).head(200)
        
        # ⭐ 수정 2: 탭 3도 파일의 '기준가'(말일 종가)를 사용하여 오차 방지
        df_k200['통합티커'] = "KOSPI:" + df_k200['종목코드'].str.zfill(6)
        df_k200['종목명_L'] = df_k200.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)

        q30 = {c: df_k200[c].quantile(0.7) for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']}
        t10_1m = df_k200['1개월(%)'].quantile(0.9)
        
        cond_perf = (df_k200['1개월(%)']>=q30['1개월(%)'])&(df_k200['3개월(%)']>=q30['3개월(%)'])&(df_k200['6개월(%)']>=q30['6개월(%)'])&(df_k200['12개월(%)']>=q30['12개월(%)']) & \
                    (df_k200['1개월(%)']>0)&(df_k200['3개월(%)']>0)&(df_k200['6개월(%)']>0)&(df_k200['12개월(%)']>0)
        df_perf = df_k200[cond_perf].copy()
        df_spec = df_k200[(df_k200['12개월(%)']>=q30['12개월(%)']) & (df_k200['1개월(%)']>=t10_1m)].copy()
        common_codes = set(df_perf['종목코드']).intersection(set(df_spec['종목코드']))

        k_cfg = main_cfg.copy()
        if m_col: k_cfg[m_col] = st.column_config.NumberColumn("시가총액", format="%,d")

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🔥 퍼펙트 상승")
            st.dataframe(df_perf.style.apply(apply_k200_styling, idx_df=idx_k, common_codes=common_codes, axis=1), 
                         use_container_width=True, column_order=['통합티커', '종목명_L', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)'], column_config=k_cfg)
        with col2:
            st.subheader("🚀 장기 주도 & 단기 급등")
            st.dataframe(df_spec.style.apply(apply_k200_styling, idx_df=idx_k, common_codes=common_codes, axis=1), 
                         use_container_width=True, column_order=['통합티커', '종목명_L', '1개월(%)', '12개월(%)'], column_config=k_cfg)

        st.markdown("---")
        st.subheader("🏆 KOSPI 200 시가총액 전체 순위")
        # ⭐ 수정 1: 순위 1부터 시작
        df_k200['순위'] = range(1, len(df_k200) + 1)
        st.dataframe(df_k200.set_index('순위').style.apply(apply_k200_styling, idx_df=idx_k, common_codes=common_codes, axis=1), 
                     use_container_width=True, height=600, column_order=['통합티커', '종목명_L', m_col, '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)'], column_config=k_cfg)
