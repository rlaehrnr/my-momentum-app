import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os

# --- [1. 기본 설정 및 스타일] ---
st.set_page_config(page_title="한국 모멘텀 순위", layout="wide")
st.markdown("""<style>.block-container { padding-top: 2.5rem !important; } h1 { font-size: 2rem !important; } .stTabs [data-baseweb="tab"] { font-size: 18px; font-weight: bold; }</style>""", unsafe_allow_html=True)

# 🔍 지능형 컬럼 매퍼 (파일의 실제 이름을 변수에 연결)
def get_col_map(df):
    mapping = {}
    cols = df.columns
    mapping['1M'] = next((c for c in cols if '1개월' in c or '1M' in c), None)
    mapping['3M'] = next((c for c in cols if '3개월' in c or '3M' in c), None)
    mapping['6M'] = next((c for c in cols if '6개월' in c or '6M' in c), None)
    mapping['12M'] = next((c for c in cols if '12개월' in c or '12M' in c), None)
    mapping['MC'] = next((c for c in cols if '시가' in c or 'mar' in c.lower()), None)
    mapping['CD'] = next((c for c in cols if '코드' in c or 'Code' in c), '종목코드')
    mapping['NM'] = next((c for c in cols if '종목명' in c or 'Name' in c), '종목명')
    mapping['PR'] = next((c for c in cols if '가' in c and '기준' in c or '현재' in c), '기준가')
    return mapping

# 스타일 함수 (수정됨)
def apply_custom_styling(row, idx_df, col_map, common_codes=None):
    styles = [''] * len(row)
    market = row.get('시장', 'KOSPI')
    if market in idx_df.index:
        idx_r = idx_df.loc[market]
        for key in ['1M', '3M', '6M', '12M']:
            col_name = col_map.get(key)
            if col_name and col_name in row.index and col_name in idx_r.index:
                if row[col_name] < idx_r[col_name]:
                    styles[row.index.get_loc(col_name)] = 'background-color: #E3F2FD; color: #0047AB;'
    
    # 교집합 종목명 하이라이트
    cd_col = col_map.get('CD')
    if common_codes and cd_col in row.index and row[cd_col] in common_codes:
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

# --- [2. 탭 구성] ---
tab1, tab2, tab3 = st.tabs(["📅 전월 말일 기준", "🕒 오늘(데일리) 기준", "🎯 KOSPI 200 집중 분석"])
idx_now = get_idx_kr()

# --- 탭 3: KOSPI 200 집중 분석 (여기에 모든 요청 집중 반영) ---
with tab3:
    f_path = 'data/momentum_data.csv'
    if os.path.exists(f_path):
        df_raw = pd.read_csv(f_path, dtype={'종목코드': str, 'Code': str})
        cmap = get_col_map(df_raw)
        
        # 날짜 확인
        d_col = next((c for c in df_raw.columns if '기준' in c or '날짜' in c), None)
        b_date = df_raw[d_col].iloc[0] if d_col else "알 수 없음"
        st.title(f"🎯 KOSPI 200 집중 분석 (기준: {b_date})")

        # 1. 수치형 변환 및 필터링 (KOSPI 보통주)
        for k in ['1M', '3M', '6M', '12M']:
            if cmap[k]: df_raw[cmap[k]] = pd.to_numeric(df_raw[cmap[k]], errors='coerce').round(1)
        
        df_k = df_raw[(df_raw['시장'] == 'KOSPI') & (df_raw[cmap['CD']].str.endswith('0'))].copy()
        if cmap['MC']: df_k = df_k.sort_values(by=cmap['MC'], ascending=False).head(200)

        # 2. 로직 적용 (요청하신 상위 30%, 10% 기준)
        q30 = {k: df_k[cmap[k]].quantile(0.7) for k in ['1M', '3M', '6M', '12M'] if cmap[k]}
        q10_1m = df_k[cmap['1M']].quantile(0.9) if cmap['1M'] else 0
        
        # 퍼펙트 상승 (모든 기간 상위 30% & 양수)
        cond_perf = (df_k[cmap['1M']] >= q30['1M']) & (df_k[cmap['3M']] >= q30['3M']) & \
                    (df_k[cmap['6M']] >= q30['6M']) & (df_k[cmap['12M']] >= q30['12M']) & \
                    (df_k[cmap['1M']] > 0) & (df_k[cmap['3M']] > 0) & (df_k[cmap['6M']] > 0) & (df_k[cmap['12M']] > 0)
        df_perf = df_k[cond_perf].copy()
        
        # 장기주도 단기급등 (12M 상위 30% & 1M 상위 10%)
        cond_spec = (df_k[cmap['12M']] >= q30['12M']) & (df_k[cmap['1M']] >= q10_1m)
        df_spec = df_k[cond_spec].copy()
        
        common_codes = set(df_perf[cmap['CD']]).intersection(set(df_spec[cmap['CD']]))

        # 3. 출력용 전처리
        for d in [df_perf, df_spec, df_k]:
            d['통합티커'] = "KOSPI:" + d[cmap['CD']].str.zfill(6)
            d['종목명_L'] = d.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r[cmap['CD']].zfill(6)}#{r[cmap['NM']]}", axis=1)

        # 컬럼 설정 (소수점 1자리 & 스코어 제외)
        cfg = {
            "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"),
            cmap['PR']: st.column_config.NumberColumn("현재가", format="%,d"),
            cmap['1M']: st.column_config.NumberColumn(format="%.1f"),
            cmap['3M']: st.column_config.NumberColumn(format="%.1f"),
            cmap['6M']: st.column_config.NumberColumn(format="%.1f"),
            cmap['12M']: st.column_config.NumberColumn(format="%.1f")
        }
        if cmap['MC']: cfg[cmap['MC']] = st.column_config.NumberColumn("시가총액", format="%,d")

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🔥 퍼펙트 상승 (전 기간 상위 30%)")
            st.dataframe(df_perf.style.apply(apply_custom_styling, idx_df=idx_now, col_map=cmap, common_codes=common_codes, axis=1), 
                         column_order=['통합티커', '종목명_L', cmap['1M'], cmap['3M'], cmap['6M'], cmap['12M']], column_config=cfg, use_container_width=True)
        with col2:
            st.subheader("🚀 장기 주도 & 단기 급등")
            st.dataframe(df_spec.style.apply(apply_custom_styling, idx_df=idx_now, col_map=cmap, common_codes=common_codes, axis=1), 
                         column_order=['통합티커', '종목명_L', cmap['1M'], cmap['12M']], column_config=cfg, use_container_width=True)

        st.markdown("---")
        st.subheader("🏆 KOSPI 200 시가총액 순위")
        df_k['순위'] = range(1, len(df_k) + 1)
        st.dataframe(df_k.set_index('순위').style.apply(apply_custom_styling, idx_df=idx_now, col_map=cmap, common_codes=common_codes, axis=1), 
                     column_order=['통합티커', '종목명_L', cmap['MC'], cmap['PR'], cmap['1M'], cmap['3M'], cmap['6M'], cmap['12M']], 
                     column_config=cfg, use_container_width=True, height=600)
    else: st.warning("데이터 파일을 찾을 수 없습니다.")

# (참고: 탭 1, 2도 유사한 방식으로 cmap을 적용하면 에러가 안 납니다.)
