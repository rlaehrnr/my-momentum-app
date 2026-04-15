import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import os
import glob
from datetime import datetime, timedelta
import plotly.express as px
import numpy as np

# --- [1. 페이지 설정 및 CSS] ---
st.set_page_config(page_title="한국 모멘텀 기록보관소", layout="wide")

st.markdown("""
    <style>
    .block-container { padding-top: 2rem !important; padding-bottom: 1rem !important; }
    h1 { font-size: 1.8rem !important; font-weight: 800; margin-bottom: 20px; }
    .settings-box { background-color: #f8fafc; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 20px; }
    .title-link:hover { opacity: 0.7; transition: 0.2s; }
    th[data-testid="stTableColumnHeader"] div { white-space: pre-wrap !important; text-align: center !important; }
    </style>
    """, unsafe_allow_html=True)

# --- [2. 데이터 로드 및 전처리 엔진] ---
@st.cache_data(show_spinner=False)
def load_all_archive_data():
    folder, prefix = "archive", "momentum_"
    files = glob.glob(f"{folder}/{prefix}*.csv")
    if not files:
        return pd.DataFrame()
    
    all_dfs = []
    for f in files:
        df = pd.read_csv(f, dtype={'종목코드': str})
        fname = os.path.basename(f)
        date_part = fname.replace(prefix, "").replace(".csv", "")
        year, month = date_part.split('_')
        
        df['투자연도'] = int(year)
        df['투자월_숫자'] = int(month)
        df['YearMonth'] = f"{year}-{month.zfill(2)}"
        df['종목코드'] = df['종목코드'].astype(str).str.strip().str.zfill(6)
        
        num_cols = ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '다음달수익률(%)', '모멘텀스코어']
        for c in num_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
        
        all_dfs.append(df)
    
    return pd.concat(all_dfs, ignore_index=True)

# 💡 [핵심 업데이트] 지정한 개월수(N)의 이동평균선을 실시간으로 계산하는 함수
@st.cache_data(show_spinner=False)
def get_kospi_timing(ma_months):
    ks11 = fdr.DataReader('KS11', '2005-01-01') # 넉넉하게 과거 데이터부터
    ma_days = ma_months * 20 # 1개월을 대략 20거래일로 계산
    ks11['MA'] = ks11['Close'].rolling(ma_days).mean()
    ks11['YearMonth'] = ks11.index.to_period('M').astype(str)
    
    timing_df = ks11.resample('ME').last()
    timing_df['is_below_ma'] = timing_df['Close'] < timing_df['MA']
    return timing_df.set_index('YearMonth')

# --- [3. 메인 앱 시작] ---
st.title("📁 한국 월별 모멘텀 기록보관소")

df_master = load_all_archive_data()

if df_master.empty:
    st.info("데이터가 없습니다. archive 폴더에 'momentum_YYYY_MM.csv' 파일들을 넣어주세요.")
    st.stop()

# 탭 구성
tab_detail, tab_summary, tab_custom = st.tabs(["📅 월별 상세 분석", "📈 전략조합 장기 백테스트", "🏅 스코어 커스텀 백테스트"])

# ==========================================
# 탭 1: 월별 상세 분석
# ==========================================
with tab_detail:
    sorted_years = sorted(df_master['투자연도'].unique().astype(str), reverse=True)
    
    col_y, col_m, _ = st.columns([1, 1, 4])
    with col_y: selected_year = st.selectbox("📅 연도", sorted_years, key='y_detail')
    with col_m:
        available_months = sorted(df_master[df_master['투자연도'] == int(selected_year)]['투자월_숫자'].unique())
        selected_month = st.selectbox("🌙 월", available_months, key='m_detail')

    df_monthly = df_master[(df_master['투자연도'] == int(selected_year)) & (df_master['투자월_숫자'] == int(selected_month))].copy()
    
    # 전달 순위 로직
    prev_dt = datetime(int(selected_year), int(selected_month), 1) - timedelta(days=1)
    prev_ym = prev_dt.strftime('%Y-%m')
    df_prev = df_master[df_master['YearMonth'] == prev_ym]
    
    if not df_prev.empty:
        df_prev = df_prev.sort_values('모멘텀스코어', ascending=False).reset_index(drop=True)
        prev_rank_dict = {code: idx + 1 for idx, code in enumerate(df_prev['종목코드'])}
        df_monthly['전달순위'] = df_monthly['종목코드'].map(prev_rank_dict)
    else:
        df_monthly['전달순위'] = None

    target_date = df_monthly['YearMonth'].iloc[0]
    st.success(f"✅ **{selected_year}년 {selected_month}월** 데이터 기준")

    df_monthly = df_monthly.sort_values('모멘텀스코어', ascending=False).reset_index(drop=True)
    df_monthly.index = range(1, len(df_monthly) + 1)
    df_monthly['종목명_L'] = df_monthly.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드']}#{r['종목명']}", axis=1)

    display_cols = ['시장', '종목명_L', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '전달순위', '다음달수익률(%)']
    
    st.dataframe(
        df_monthly.style.map(lambda x: 'color: #FF4B4B; font-weight: bold;' if x > 0 else ('color: #3182CE; font-weight: bold;' if x < 0 else ''), subset=['다음달수익률(%)']),
        use_container_width=True, height=500,
        column_order=[c for c in display_cols if c in df_monthly.columns],
        column_config={
            "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"),
            "기준가": st.column_config.NumberColumn(format="%,d"),
            "전달순위": st.column_config.NumberColumn("전달 순위", format="%d위"),
            "다음달수익률(%)": st.column_config.NumberColumn(format="%.2f %%")
        }
    )

# ==========================================
# 탭 2: 전략조합 장기 백테스트
# ==========================================
with tab_summary:
    col_title, col_check = st.columns([1, 4])
    with col_title:
        st.markdown("<h4 style='margin-top: 5px; margin-bottom: 0px;'>⚙️ 시뮬레이션 설정</h4>", unsafe_allow_html=True)
    with col_check:
        st.markdown("<div style='margin-top: 8px;'>", unsafe_allow_html=True)
        apply_timing = st.checkbox("🛑 마켓타이밍 적용 (선택한 이평선 이탈 시 현금 100%)", value=True, key='timing_tab2')
        st.markdown("</div>", unsafe_allow_html=True)
        
    # 💡 [업데이트] 마켓타이밍 개월선 선택 슬라이더 추가 (4등분)
    c1, c_ma, c2, c3 = st.columns([1, 0.8, 1, 1])
    with c1:
        years_list = sorted(df_master['투자연도'].unique().astype(int))
        min_y, max_y = min(years_list), max(years_list)
        start_year, end_year = st.slider("📅 테스트 기간", min_y, max_y, (min_y, max_y), key='year_tab2')
    with c_ma:
        ma_months_t2 = st.slider("📉 마켓타이밍 (개월선)", 1, 12, 4, key='ma_t2')
    with c2:
        rank_1_start, rank_1_end = st.slider("🔥 12-1 & 6-1 전략", 1, 30, (1, 5))
    with c3:
        rank_2_start, rank_2_end = st.slider("⚡ 6-1 & 3-1 전략", 1, 30, (1, 5))
        
    if rank_1_start > rank_1_end or rank_2_start > rank_2_end:
        st.error("🚨 순위 범위가 잘못되었습니다.")
        st.stop()
    
    with st.spinner("수익률 계산 중..."):
        timing_df_t2 = get_kospi_timing(ma_months_t2)
        months = [m for m in sorted(df_master['YearMonth'].unique()) if start_year <= int(m[:4]) <= end_year]
        records = []
        for m in months:
            m_data = df_master[df_master['YearMonth'] == m]
            
            # 💡 종목 수 조건 삭제. 오직 '지정된 KOSPI 이평선 이탈' 여부만 체크
            is_below_ma = False
            if m in timing_df_t2.index:
                is_below_ma = timing_df_t2.loc[m, 'is_below_ma']
                
            mult = 0.0 if (apply_timing and is_below_ma) else 1.0
            
            # 전략 1
            top_12 = m_data.sort_values('12개월(%)', ascending=False).head(40)
            top_6 = m_data.sort_values('6개월(%)', ascending=False).head(40)
            overlap_1 = top_12[top_12['종목코드'].isin(top_6['종목코드'])].sort_values('6개월(%)', ascending=False).iloc[rank_1_start-1:rank_1_end]
            
            # 전략 2
            top_6_2 = m_data.sort_values('6개월(%)', ascending=False).head(40)
            top_3 = m_data.sort_values('3개월(%)', ascending=False).head(40)
            overlap_2 = top_6_2[top_6_2['종목코드'].isin(top_3['종목코드'])].sort_values('3개월(%)', ascending=False).iloc[rank_2_start-1:rank_2_end]
            
            ret_1 = (overlap_1['다음달수익률(%)'].mean() * mult) if not overlap_1.empty else 0.0
            ret_2 = (overlap_2['다음달수익률(%)'].mean() * mult) if not overlap_2.empty else 0.0
            
            records.append({
                'YearMonth': m,
                '전략1': ret_1, '전략2': ret_2,
                '앙상블(50:50)': (ret_1 + ret_2) / 2
            })
            
        df_res = pd.DataFrame(records)
        if not df_res.empty:
            df_cum = (1 + df_res.set_index('YearMonth') / 100).cumprod() * 100
            st.markdown(f"### 📈 {start_year}~{end_year} 누적 수익률 곡선 (마켓타이밍: KOSPI {ma_months_t2}개월선 적용)")
            st.line_chart(df_cum)
            
            final_stats = []
            for col in df_cum.columns:
                total_ret = df_cum[col].iloc[-1] - 100
                mdd = ((df_cum[col] / df_cum[col].cummax()) - 1).min() * 100
                final_stats.append({"전략명": col, "총 수익률": f"{total_ret:.1f}%", "MDD": f"{mdd:.1f}%"})
            st.table(pd.DataFrame(final_stats))

# ==========================================
# 탭 3: 모멘텀 스코어 커스텀 백테스트
# ==========================================
with tab_custom:
    col_title, col_check = st.columns([1, 4])
    with col_title:
        st.markdown("<h4 style='margin-top: 5px; margin-bottom: 0px;'>⚙️ 스코어 가중치 설정</h4>", unsafe_allow_html=True)
    with col_check:
        st.markdown("<div style='margin-top: 8px;'>", unsafe_allow_html=True)
        apply_timing_c = st.checkbox("🛑 마켓타이밍 적용 (선택한 이평선 이탈 시 현금 100%)", value=True, key='timing_tab3')
        st.markdown("</div>", unsafe_allow_html=True)
        
    with st.form("custom_weight_form", border=False):
        c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 0.8])
        with c1: w1 = st.number_input("📉 1개월 가중치", value=0.2, step=0.1, format="%.1f")
        with c2: w3 = st.number_input("📈 3개월 가중치", value=0.8, step=0.1, format="%.1f")
        with c3: w6 = st.number_input("📈 6개월 가중치", value=0.0, step=0.1, format="%.1f")
        with c4: w12 = st.number_input("📈 12개월 가중치", value=0.0, step=0.1, format="%.1f")
        with c5:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            apply_weights = st.form_submit_button("✅ 스코어 적용", use_container_width=True)
            
    st.markdown("<hr style='margin: 0px 0px 15px 0px;'>", unsafe_allow_html=True)
    
    # 💡 커스텀 탭에도 마켓타이밍 슬라이더 추가
    c6, c_ma_c, c7 = st.columns([1, 1, 1])
    with c6:
        start_year_c, end_year_c = st.slider("📅 테스트 기간 (연도)", min_y, max_y, (min_y, max_y), key='year_tab3')
    with c_ma_c:
        ma_months_t3 = st.slider("📉 마켓타이밍 (개월선)", 1, 12, 4, key='ma_t3')
    with c7:
        rank_c_start, rank_c_end = st.slider("🏅 매수 순위 범위", 1, 50, (1, 10))

    with st.spinner("커스텀 스코어 계산 중..."):
        timing_df_t3 = get_kospi_timing(ma_months_t3)
        
        df_calc = df_master.copy()
        df_calc['CustomScore'] = (df_calc['1개월(%)']*w1) + (df_calc['3개월(%)']*w3) + (df_calc['6개월(%)']*w6) + (df_calc['12개월(%)']*w12)
        
        months_c = [m for m in sorted(df_calc['YearMonth'].unique()) if start_year_c <= int(m[:4]) <= end_year_c]
        records_c = []
        for m in months_c:
            m_data = df_calc[df_calc['YearMonth'] == m]
            
            is_below_ma = False
            if m in timing_df_t3.index:
                is_below_ma = timing_df_t3.loc[m, 'is_below_ma']
                
            mult = 0.0 if (apply_timing_c and is_below_ma) else 1.0
            
            target_group = m_data.sort_values('CustomScore', ascending=False).iloc[rank_c_start-1 : rank_c_end]
            ret_target = (target_group['다음달수익률(%)'].mean() * mult) if not target_group.empty else 0.0
            
            records_c.append({'YearMonth': m, f'🏅 커스텀 스코어 ({rank_c_start}~{rank_c_end}위)': ret_target})
            
        df_res_c = pd.DataFrame(records_c).set_index('YearMonth').fillna(0.0)
        if not df_res_c.empty:
            df_cum_c = (1 + df_res_c / 100).cumprod() * 100
            st.markdown(f"### 📈 커스텀 스코어 누적 수익률 (마켓타이밍: KOSPI {ma_months_t3}개월선 적용)")
            st.line_chart(df_cum_c)
            
            final_val = df_cum_c.iloc[-1].values[0]
            total_ret = final_val - 100
            mdd = ((df_cum_c / df_cum_c.cummax()) - 1).min().values[0] * 100
            
            col_a, col_b = st.columns(2)
            col_a.metric("🚀 최종 누적 수익률", f"{total_ret:.1f}%")
            col_b.metric("📉 MDD (최대낙폭)", f"{mdd:.1f}%")
            
            with st.expander("📝 월별 상세 수익률 보기"):
                st.dataframe(df_res_c.style.format("{:.2f}%"), use_container_width=True)
