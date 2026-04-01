import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os

# --- [1. 기본 설정 및 스타일] ---
st.set_page_config(page_title="한국 모멘텀 순위", layout="wide")
st.markdown("""<style>.block-container { padding-top: 2.5rem !important; } h1 { font-size: 2rem !important; } .stTabs [data-baseweb="tab"] { font-size: 18px; font-weight: bold; }</style>""", unsafe_allow_html=True)

# 지능형 컬럼 찾기 (파일마다 다른 이름 대응)
def find_col(df, keywords):
    for col in df.columns:
        if any(k in col for k in keywords): return col
    return None

# 스타일 함수 (지수 대비 열세 파란색, 교집합 노란색)
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

# --- [2. 탭 생성 및 공통 데이터] ---
tab1, tab2, tab3 = st.tabs(["📅 전월 말일 기준", "🕒 오늘(데일리) 기준", "🎯 KOSPI 200 강세 종목"])
f_kr = 'data/momentum_data.csv'
f_daily = 'data/momentum_data_daily.csv'

# --- [3. 탭 1: 월간 기준] ---
with tab1:
    if os.path.exists(f_kr):
        df_m = pd.read_csv(f_kr, dtype={'종목코드': str})
        b_date = df_m['기준일(월말)'].iloc[0] if '기준일(월말)' in df_m.columns else "날짜정보없음"
        st.title(f"📊 한국 모멘텀 (기준: {b_date})")
        
        idx_m = get_idx_kr(pd.to_datetime(b_date))
        
        # 전처리
        df_m['통합티커'] = df_m['시장'] + ":" + df_m['종목코드'].str.zfill(6)
        df_m['종목명_L'] = df_m.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)
        for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
            if c in df_m.columns: df_m[c] = pd.to_numeric(df_m[c], errors='coerce').round(1)

        st.dataframe(df_m.style.apply(apply_k200_styling, idx_df=idx_m, axis=1), use_container_width=True, height=560,
                     column_order=['통합티커', '종목명_L', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)'],
                     column_config={"종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), "기준가": st.column_config.NumberColumn("현재가", format="%,d"), 
                                    "1개월(%)": st.column_config.NumberColumn(format="%.1f"), "3개월(%)": st.column_config.NumberColumn(format="%.1f"), 
                                    "6개월(%)": st.column_config.NumberColumn(format="%.1f"), "12개월(%)": st.column_config.NumberColumn(format="%.1f")})

# --- [4. 탭 2: 데일리 기준] ---
with tab2:
    if os.path.exists(f_daily):
        df_d = pd.read_csv(f_daily, dtype={'종목코드': str})
        st.title(f"🕒 데일리 모멘텀 (기준: {df_d['기준일'].iloc[0]})")
        
        idx_now = get_idx_kr()
        
        df_d['통합티커'] = df_d['시장'] + ":" + df_d['종목코드'].str.zfill(6)
        df_d['종목명_L'] = df_d.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)
        for c in ['1개월(%)', '12개월(%)']:
            if c in df_d.columns: df_d[c] = pd.to_numeric(df_d[c], errors='coerce').round(1)

        st.dataframe(df_d.style.apply(apply_k200_styling, idx_df=idx_now, axis=1), use_container_width=True, height=560,
                     column_order=['통합티커', '종목명_L', '기준가', '전일거래량', '1개월(%)', '12개월(%)'],
                     column_config={"종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), "기준가": st.column_config.NumberColumn("현재가", format="%,d"),
                                    "전일거래량": st.column_config.NumberColumn(format="%,d"), "1개월(%)": st.column_config.NumberColumn(format="%.1f"), "12개월(%)": st.column_config.NumberColumn(format="%.1f")})

# --- [5. 탭 3: KOSPI 200 집중 분석] ---
with tab3:
    if os.path.exists(f_kr):
        df_raw = pd.read_csv(f_kr, dtype={'종목코드': str})
        b_date_str = df_raw['기준일(월말)'].iloc[0] if '기준일(월말)' in df_raw.columns else "날짜정보없음"
        st.title(f"🎯 KOSPI 200 집중 분석 (기준: {b_date_str})")
        
        idx_k = get_idx_kr(pd.to_datetime(b_date_str))
        
        # 상위 200 필터링
        m_col = next((c for c in df_raw.columns if '시가' in c or 'mar' in c.lower()), '시가총액')
        df_k200 = df_raw[(df_raw['시장'] == 'KOSPI') & (df_raw['종목코드'].str.endswith('0'))].copy()
        if m_col in df_k200.columns: df_k200 = df_k200.sort_values(by=m_col, ascending=False).head(200)
        
        # 전처리
        df_k200['통합티커'] = "KOSPI:" + df_k200['종목코드'].str.zfill(6)
        df_k200['종목명_L'] = df_k200.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)
        for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
            df_k200[c] = pd.to_numeric(df_k200[c], errors='coerce').round(1)

        # 로직: 상위 30% / 상위 10%
        q30 = {c: df_k200[c].quantile(0.7) for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']}
        t10_1m = df_k200['1개월(%)'].quantile(0.9)
        
        cond_perf = (df_k200['1개월(%)']>=q30['1개월(%)'])&(df_k200['3개월(%)']>=q30['3개월(%)'])&(df_k200['6개월(%)']>=q30['6개월(%)'])&(df_k200['12개월(%)']>=q30['12개월(%)']) & \
                    (df_k200['1개월(%)']>0)&(df_k200['3개월(%)']>0)&(df_k200['6개월(%)']>0)&(df_k200['12개월(%)']>0)
        df_perf = df_k200[cond_perf].copy()
        df_spec = df_k200[(df_k200['12개월(%)']>=q30['12개월(%)']) & (df_k200['1개월(%)']>=t10_1m)].copy()
        common_codes = set(df_perf['종목코드']).intersection(set(df_spec['종목코드']))

        k_cfg = { "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), "기준가": st.column_config.NumberColumn("현재가", format="%,d"), 
                  m_col: st.column_config.NumberColumn("시가총액", format="%,d"), "1개월(%)": st.column_config.NumberColumn(format="%.1f"), 
                  "3개월(%)": st.column_config.NumberColumn(format="%.1f"), "6개월(%)": st.column_config.NumberColumn(format="%.1f"), "12개월(%)": st.column_config.NumberColumn(format="%.1f")}

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
        st.subheader("🏆 KOSPI 200 시가총액 순위")
        df_k200['순위'] = range(1, len(df_k200) + 1)
        st.dataframe(df_k200.set_index('순위').style.apply(apply_k200_styling, idx_df=idx_k, common_codes=common_codes, axis=1), 
                     use_container_width=True, height=600, column_order=['통합티커', '종목명_L', m_col, '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)'], column_config=k_cfg)
