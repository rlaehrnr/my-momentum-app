import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os

# 1. 기본 설정 및 스타일
st.set_page_config(page_title="한국 모멘텀 순위", layout="wide")
st.markdown("""<style>.block-container { padding-top: 2.5rem !important; } h1 { font-size: 2rem !important; } .stTabs [data-baseweb="tab"] { font-size: 18px; font-weight: bold; }</style>""", unsafe_allow_html=True)

# 스타일 함수 (지수 대비 열세는 파란색, 교집합은 노란색)
def apply_k200_styling(row, idx_df, common_codes):
    styles = [''] * len(row)
    market = row.get('시장', 'KOSPI')
    if market in idx_df.index:
        idx_r = idx_df.loc[market]
        for col in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
            if col in row.index and col in idx_r.index:
                col_idx = row.index.get_loc(col)
                if row[col] < idx_r[col]:
                    styles[col_idx] = 'background-color: #E3F2FD; color: #0047AB;'
    if '종목명_L' in row.index and '종목코드' in row.index:
        if row['종목코드'] in common_codes:
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

# ⭐ 여기서 탭을 먼저 정의해야 NameError가 안 납니다!
tab1, tab2, tab3 = st.tabs(["📅 전월 말일 기준", "🕒 오늘(데일리) 기준", "🎯 KOSPI 200 집중 분석"])

# 데이터 경로 설정
f_kr = 'data/momentum_data.csv'
f_daily = 'data/momentum_data_daily.csv'

# --- 탭 1 & 2는 기존대로 유지 (생략 가능하나 구조상 유지) ---
with tab1:
    if os.path.exists(f_kr):
        df_m = pd.read_csv(f_kr, dtype={'종목코드': str})
        st.title(f"📊 월간 모멘텀 (기준: {df_m['기준일(월말)'].iloc[0]})")
        st.write("월간 데이터 테이블 표시 영역...")

with tab2:
    if os.path.exists(f_daily):
        df_d = pd.read_csv(f_daily, dtype={'종목코드': str})
        st.title(f"🕒 데일리 모멘텀 (기준: {df_d['기준일'].iloc[0]})")
        st.write("데일리 데이터 테이블 표시 영역...")

# --- 탭 3: 사용자 요청 로직 완벽 반영 ---
with tab3:
    if os.path.exists(f_kr):
        df_raw = pd.read_csv(f_kr, dtype={'종목코드': str})
        b_date_str = df_raw['기준일(월말)'].iloc[0] if '기준일(월말)' in df_raw.columns else "날짜정보없음"
        st.title(f"🎯 KOSPI 200 집중 분석 (기준: {b_date_str})")
        
        # 지수 정보 미리 가져오기
        idx_now_k200 = get_idx_kr(pd.to_datetime(b_date_str))
        if not idx_now_k200.empty:
            idx_disp = idx_now_k200.reset_index().copy()
            idx_disp['현재가'] = idx_disp['현재가'].map('{:,.0f}'.format)
            for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
                idx_disp[c] = idx_disp[c].map('{:+.1f}%'.format)
            st.table(idx_disp)

        st.markdown("---")

        # 1. 시가총액 컬럼 대응 및 KOSPI 상위 200 필터링
        m_col = next((c for c in df_raw.columns if '시가' in c or 'mar' in c.lower()), '시가총액')
        df_k200 = df_raw[(df_raw['시장'] == 'KOSPI') & (df_raw['종목코드'].str.endswith('0'))].copy()
        
        if m_col in df_k200.columns:
            df_k200 = df_k200.sort_values(by=m_col, ascending=False).head(200)
        else:
            df_k200 = df_k200.head(200)

        # 2. 전처리 (링크 생성 및 소수점 1자리 고정)
        df_k200['통합티커'] = "KOSPI:" + df_k200['종목코드'].str.zfill(6)
        df_k200['종목명_L'] = df_k200.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)
        
        for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
            if c in df_k200.columns:
                df_k200[c] = pd.to_numeric(df_k200[c], errors='coerce').round(1)

        # 3. ⭐ 사용자 요청 로직 (상위 30%, 상위 10%)
        q30_1m = df_k200['1개월(%)'].quantile(0.7)
        q30_3m = df_k200['3개월(%)'].quantile(0.7)
        q30_6m = df_k200['6개월(%)'].quantile(0.7)
        q30_12m = df_k200['12개월(%)'].quantile(0.7)
        t10_1m = df_k200['1개월(%)'].quantile(0.9)

        # 퍼펙트 상승 (모든 기간 상위 30% & 수익률 > 0)
        cond_perf = (df_k200['1개월(%)'] >= q30_1m) & (df_k200['3개월(%)'] >= q30_3m) & \
                    (df_k200['6개월(%)'] >= q30_6m) & (df_k200['12개월(%)'] >= q30_12m) & \
                    (df_k200['1개월(%)'] > 0) & (df_k200['3개월(%)'] > 0) & \
                    (df_k200['6개월(%)'] > 0) & (df_k200['12개월(%)'] > 0)
        df_perfect = df_k200[cond_perf].copy()

        # 장기주도 단기급등 (12M 상위 30% & 1M 상위 10%)
        cond_spec = (df_k200['12개월(%)'] >= q30_12m) & (df_k200['1개월(%)'] >= t10_1m)
        df_special = df_k200[cond_spec].copy()

        common_codes = set(df_perfect['종목코드']).intersection(set(df_special['종목코드']))

        # 4. 공통 출력 설정
        k200_cfg = {
            "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), 
            "기준가": st.column_config.NumberColumn("현재가", format="%,d"), 
            m_col: st.column_config.NumberColumn("시가총액", format="%,d"),
            "1개월(%)": st.column_config.NumberColumn(format="%.1f"), 
            "3개월(%)": st.column_config.NumberColumn(format="%.1f"), 
            "6개월(%)": st.column_config.NumberColumn(format="%.1f"), 
            "12개월(%)": st.column_config.NumberColumn(format="%.1f")
        }

        # 레이아웃 출력
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🔥 퍼펙트 상승 (1,3,6,12M 상위 30%)")
            st.dataframe(df_perfect.style.apply(apply_k200_styling, idx_df=idx_now_k200, common_codes=common_codes, axis=1), 
                         use_container_width=True, column_order=['통합티커', '종목명_L', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)'], column_config=k200_cfg)
        with col2:
            st.subheader("🚀 장기 주도 & 단기 급등 (12M 30% & 1M 10%)")
            st.dataframe(df_special.style.apply(apply_k200_styling, idx_df=idx_now_k200, common_codes=common_codes, axis=1), 
                         use_container_width=True, column_order=['통합티커', '종목명_L', '1개월(%)', '12개월(%)'], column_config=k200_cfg)

        st.markdown("---")
        st.subheader("🏆 KOSPI 200 시가총액 순위 (1위 ~ 200위)")
        df_k200['순위'] = range(1, len(df_k200) + 1)
        st.dataframe(df_k200.set_index('순위').style.apply(apply_k200_styling, idx_df=idx_now_k200, common_codes=common_codes, axis=1), 
                     use_container_width=True, height=600, column_order=['통합티커', '종목명_L', m_col, '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)'], column_config=k200_cfg)
    else:
        st.warning("데이터 파일을 찾을 수 없습니다.")
