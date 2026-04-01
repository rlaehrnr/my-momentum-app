import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os

# --- [1. 기본 설정 및 스타일] ---
st.set_page_config(page_title="한국 모멘텀 순위", layout="wide")
st.markdown("""<style>.block-container { padding-top: 2.5rem !important; } h1 { font-size: 2rem !important; } .stTabs [data-baseweb="tab"] { font-size: 18px; font-weight: bold; }</style>""", unsafe_allow_html=True)

# 지능형 컬럼 찾기 함수 (에러 방지의 핵심)
def find_col(df, keywords):
    for col in df.columns:
        if any(k in col.lower() for k in keywords): return col
    return None

# 스타일 함수 (지수보다 수익률 낮으면 파란색)
def apply_custom_styling(row, idx_df, common_codes=None):
    styles = [''] * len(row)
    # 지수와 비교하여 하이라이트
    market = row.get('시장', 'KOSPI')
    if market in idx_df.index:
        idx_r = idx_df.loc[market]
        # 컬럼 이름이 유동적이므로 매칭 필요
        for col in row.index:
            if '개월' in col and col in idx_r.index:
                col_idx = row.index.get_loc(col)
                if row[col] < idx_r[col]:
                    styles[col_idx] = 'background-color: #E3F2FD; color: #0047AB;'
    
    # 교집합 종목 노란색 표시
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

# --- [2. 공통 데이터 처리 준비] ---
tab1, tab2, tab3 = st.tabs(["📅 전월 말일 기준", "🕒 오늘(데일리) 기준", "🎯 KOSPI 200 강세 종목"])
idx_now = get_idx_kr() # 기본 지수 정보

# --- 탭 1: 월말 기준 ---
with tab1:
    f_path = 'data/momentum_data.csv'
    if os.path.exists(f_path):
        df = pd.read_csv(f_path, dtype={'종목코드': str})
        b_date = df['기준일(월말)'].iloc[0]
        st.title(f"📊 한국 모멘텀 (기준: {b_date})")
        
        c_1m, c_3m, c_6m, c_12m = [find_col(df, [k]) for k in ['1개월', '3개월', '6개월', '12개월']]
        
        df['통합티커'] = df['시장'] + ":" + df['종목코드'].str.zfill(6)
        df['종목명_L'] = df.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)
        
        for c in [c_1m, c_3m, c_6m, c_12m]:
            if c: df[c] = pd.to_numeric(df[c], errors='coerce').round(1)

        st.dataframe(df.style.apply(apply_custom_styling, idx_df=idx_now, axis=1), 
                     use_container_width=True, height=560,
                     column_order=list(filter(None, ['통합티커', '종목명_L', '기준가', c_1m, c_3m, c_6m, c_12m])),
                     column_config={c: st.column_config.NumberColumn(format="%.1f") for c in [c_1m, c_3m, c_6m, c_12m] if c})
    else: st.warning("월말 데이터가 없습니다.")

# --- 탭 2: 데일리 기준 ---
with tab2:
    f_daily = 'data/momentum_data_daily.csv'
    if os.path.exists(f_daily):
        df_d = pd.read_csv(f_daily, dtype={'종목코드': str})
        st.title(f"🕒 데일리 모멘텀 (기준: {df_d['기준일'].iloc[0]})")
        
        c_1m, c_12m = find_col(df_d, ['1개월']), find_col(df_d, ['12개월'])
        df_d['통합티커'] = df_d['시장'] + ":" + df_d['종목코드'].str.zfill(6)
        df_d['종목명_L'] = df_d.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)
        
        st.dataframe(df_d.style.apply(apply_custom_styling, idx_df=idx_now, axis=1), 
                     use_container_width=True, height=560,
                     column_order=list(filter(None, ['통합티커', '종목명_L', '기준가', '전일거래량', c_1m, c_12m])),
                     column_config={c_1m: st.column_config.NumberColumn(format="%.1f"), c_12m: st.column_config.NumberColumn(format="%.1f")})

# --- 탭 3: KOSPI 200 집중 분석 ---
with tab3:
    if os.path.exists('data/momentum_data.csv'):
        df_k = pd.read_csv('data/momentum_data.csv', dtype={'종목코드': str})
        c_1m, c_3m, c_6m, c_12m = [find_col(df_k, [k]) for k in ['1개월', '3개월', '6개월', '12개월']]
        m_col = find_col(df_k, ['시가', 'mar'])
        
        # 필터링
        df_k = df_k[(df_k['시장'] == 'KOSPI') & (df_k['종목코드'].str.endswith('0'))].copy()
        if m_col: df_k = df_k.sort_values(by=m_col, ascending=False).head(200)
        
        # 수치 변환
        for c in [c_1m, c_3m, c_6m, c_12m]:
            if c: df_k[c] = pd.to_numeric(df_k[c], errors='coerce').round(1)

        # ⭐ [로직 적용] 퍼펙트(All Top 30% & > 0) / 스페셜(12M Top 30% & 1M Top 10%)
        q30 = {c: df_k[c].quantile(0.7) for c in [c_1m, c_3m, c_6m, c_12m] if c}
        q10_1m = df_k[c_1m].quantile(0.9) if c_1m else 0
        
        cond_perf = (df_k[c_1m]>=q30[c_1m])&(df_k[c_3m]>=q30[c_3m])&(df_k[c_6m]>=q30[c_6m])&(df_k[c_12m]>=q30[c_12m]) & \
                    (df_k[c_1m]>0)&(df_k[c_3m]>0)&(df_k[c_6m]>0)&(df_k[c_12m]>0)
        df_perf = df_k[cond_perf].copy()
        
        cond_spec = (df_k[c_12m]>=q30[c_12m])&(df_k[c_1m]>=q10_1m)
        df_spec = df_k[cond_spec].copy()
        
        common_codes = set(df_perf['종목코드']).intersection(set(df_spec['종목코드']))

        # 공통 설정
        df_k['통합티커'] = "KOSPI:" + df_k['종목코드'].str.zfill(6)
        df_k['종목명_L'] = df_k.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)
        
        cfg = {c: st.column_config.NumberColumn(format="%.1f") for c in [c_1m, c_3m, c_6m, c_12m] if c}
        cfg.update({"종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), "기준가": st.column_config.NumberColumn("현재가", format="%,d")})
        if m_col: cfg[m_col] = st.column_config.NumberColumn("시가총액", format="%,d")

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🔥 퍼펙트 상승 (1,3,6,12M 상위 30%)")
            st.dataframe(df_perf.style.apply(apply_custom_styling, idx_df=idx_now, common_codes=common_codes, axis=1), 
                         column_order=list(filter(None, ['통합티커', '종목명_L', c_1m, c_3m, c_6m, c_12m])), column_config=cfg, use_container_width=True)
        with col2:
            st.subheader("🚀 장기 주도 & 단기 급등 (12M 30% & 1M 10%)")
            st.dataframe(df_spec.style.apply(apply_custom_styling, idx_df=idx_now, common_codes=common_codes, axis=1), 
                         column_order=list(filter(None, ['통합티커', '종목명_L', c_1m, c_12m])), column_config=cfg, use_container_width=True)

        st.markdown("---")
        st.subheader("🏆 KOSPI 200 시가총액 순위")
        df_k['순위'] = range(1, len(df_k) + 1)
        st.dataframe(df_k.set_index('순위').style.apply(apply_custom_styling, idx_df=idx_now, common_codes=common_codes, axis=1), 
                     column_order=list(filter(None, ['통합티커', '종목명_L', m_col, '기준가', c_1m, c_3m, c_6m, c_12m])), 
                     column_config=cfg, use_container_width=True, height=600)
