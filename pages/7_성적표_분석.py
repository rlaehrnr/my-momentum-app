import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime
import os
import glob
import plotly.express as px
import numpy as np

# 1. 페이지 설정
st.set_page_config(page_title="KOSPI 200 전략 최적화", layout="wide")

# CSS: 시인성 강화
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem !important; }
    h1 { font-size: 2.2rem !important; font-weight: 800; color: #1E1E1E; }
    [data-testid="stMetricValue"] { font-size: 2.0rem !important; color: #0047AB !important; font-weight: 800 !important; }
    .stMetric { background-color: #f0f2f6 !important; padding: 20px !important; border-radius: 12px !important; border: 2px solid #d1d5db !important; }
    .section-title { background-color: #1F2937; color: white; padding: 10px 15px; border-radius: 8px 8px 0 0; font-size: 1.2rem; font-weight: bold; border-bottom: 4px solid #EF4444; margin-top: 20px; }
    </style>
    """, unsafe_allow_html=True)

st.title("🎯 KOSPI 200 전략별 최적 구간 탐색기")

# 2. 데이터 로드 및 전처리 (캐싱)
@st.cache_data(ttl=3600)
def load_and_process_strategy_data(folder="archive", prefix="momentum_"):
    files = glob.glob(os.path.join(folder, f"{prefix}*.csv"))
    if not files: return pd.DataFrame()

    try:
        kospi_info = fdr.StockListing('KOSPI')[['Code', 'Marcap']]
        kospi_info['Code'] = kospi_info['Code'].astype(str).str.zfill(6)
    except:
        kospi_info = pd.DataFrame(columns=['Code', 'Marcap'])

    all_perf, all_spec, all_inter = [], [], []

    for f in sorted(files):
        try:
            df = pd.read_csv(f, dtype={'종목코드': str})
            df.columns = df.columns.str.replace(' ', '')
            if '다음달수익률(%)' not in df.columns: continue

            df['종목코드'] = df['종목코드'].astype(str).str.zfill(6) 

            for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '다음달수익률(%)', '모멘텀스코어']:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

            df_k = df[(df['시장'] == 'KOSPI') & (df['종목코드'].str.endswith('0'))].copy()
            if not kospi_info.empty:
                df_k = df_k.merge(kospi_info, left_on='종목코드', right_on='Code', how='left')
                df_k['시가총액'] = df_k['Marcap'].fillna(0)
                df_k = df_k.sort_values(by='시가총액', ascending=False).head(200)

            if df_k.empty: continue

            q30 = {c: df_k[c].quantile(0.7) for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']}
            t10_1m = df_k['1개월(%)'].quantile(0.9)

            cond_perf = (df_k['1개월(%)']>=q30['1개월(%)'])&(df_k['3개월(%)']>=q30['3개월(%)'])&(df_k['6개월(%)']>=q30['6개월(%)'])&(df_k['12개월(%)']>=q30['12개월(%)']) & \
                        (df_k['1개월(%)']>0)&(df_k['3개월(%)']>0)&(df_k['6개월(%)']>0)&(df_k['12개월(%)']>0)
            cond_spec = (df_k['12개월(%)']>=q30['12개월(%)']) & (df_k['1개월(%)']>=t10_1m)

            # 💡 전략별 정렬 기준 (KOSPI 200 페이지와 동일하게 모멘텀스코어 기준)
            df_perf = df_k[cond_perf].sort_values('모멘텀스코어', ascending=False).copy()
            df_spec = df_k[cond_spec].sort_values('모멘텀스코어', ascending=False).copy()
            df_inter = df_k[cond_perf & cond_spec].sort_values('모멘텀스코어', ascending=False).copy()

            def extract_strategy(d, strat_name, target_list):
                if not d.empty:
                    d = d.reset_index(drop=True)
                    d['전략순위'] = range(1, len(d) + 1)
                    d['전략명'] = strat_name
                    # 디버깅을 위해 종목명도 포함해서 저장
                    target_list.append(d[['기준일(월말)', '다음달수익률(%)', '전략순위', '전략명', '종목명', '모멘텀스코어', '1개월(%)']])

            extract_strategy(df_perf, '🔥 퍼펙트 상승', all_perf)
            extract_strategy(df_spec, '🚀 달리는 말', all_spec)
            extract_strategy(df_inter, '🌟 교집합', all_inter)

        except: continue

    combined = all_perf + all_spec + all_inter
    return pd.concat(combined, ignore_index=True) if combined else pd.DataFrame()

# 3. 데이터 준비
df_master = load_and_process_strategy_data()

if df_master.empty:
    st.error("데이터가 부족합니다.")
    st.stop()

# --- [시뮬레이션 엔진] ---
def run_range_simulation(df, strategy_name):
    strat_df = df[df['전략명'] == strategy_name]
    if strat_df.empty: return pd.DataFrame()

    dates = sorted(strat_df['기준일(월말)'].unique())
    results = []

    test_ranges = [(1, 1), (2, 2), (1, 3), (1, 5), (1, 10)]

    for s, e in test_ranges:
        monthly_returns = []
        for d in dates:
            month_data = strat_df[(strat_df['기준일(월말)'] == d) & (strat_df['전략순위'] >= s) & (strat_df['전략순위'] <= e)]
            ret = month_data['다음달수익률(%)'].mean() if not month_data.empty else 0.0
            monthly_returns.append(ret)

        perf = pd.Series(monthly_returns)
        equity = (1 + perf/100).cumprod()
        cum_ret = (equity.iloc[-1] - 1) * 100 if not equity.empty else 0
        peak = equity.cummax()
        mdd = ((equity - peak)/peak * 100).min() if not peak.empty else 0
        win_rate = (perf > 0).mean() * 100

        label = f"{s}위 전몰빵" if s == e else f"{s}위 ~ {e}위 분산"
        results.append({"투자 전략 (순위)": label, "최종 누적 수익률": cum_ret, "최대 낙폭(MDD)": mdd, "월간 승률": win_rate})

    return pd.DataFrame(results).sort_values("최종 누적 수익률", ascending=False)

# 상단 요약 렌더링
col1, col2, col3 = st.columns(3)
strategies = ['🔥 퍼펙트 상승', '🚀 달리는 말', '🌟 교집합']
for col, strat in zip([col1, col2, col3], strategies):
    with col:
        st.markdown(f'<div class="section-title">{strat} 성과</div>', unsafe_allow_html=True)
        res = run_range_simulation(df_master, strat)
        if not res.empty:
            st.dataframe(res.style.format({'최종 누적 수익률': '{:.2f}%', '최대 낙폭(MDD)': '{:.2f}%', '월간 승률': '{:.1f}%'}), use_container_width=True, hide_index=True)

st.markdown("---")

# --- [하단 커스텀 백테스팅] ---
st.subheader("🔬 커스텀 구간 정밀 백테스팅")
c1, c2 = st.columns([1, 2])
with c1:
    sel_strat = st.selectbox("전략 선택", strategies)
    sel_range = st.slider("순위 범위", 1, 15, (1, 1))

s_start, s_end = sel_range
target_df = df_master[df_master['전략명'] == sel_strat]

if not target_df.empty:
    dates = sorted(target_df['기준일(월말)'].unique())
    monthly_results = []

    for d in dates:
        month_data = target_df[(target_df['기준일(월말)'] == d) & (target_df['전략순위'] >= s_start) & (target_df['전략순위'] <= s_end)]
        
        # 💡 [핵심 디버깅] 2026-01-30일의 1위 종목 데이터 강제 노출
        if d == '2026-01-30' and s_start == 1 and s_end == 1:
            st.warning(f"🔍 2026-01-30 당시 {sel_strat} 1위 종목 실시간 검증")
            st.write(month_data[['기준일(월말)', '전략순위', '종목명', '다음달수익률(%)', '모멘텀스코어', '1개월(%)']])

        ret = month_data['다음달수익률(%)'].mean() if not month_data.empty else 0.0
        monthly_results.append({'월별': d, '수익률': ret})

    sim_df = pd.DataFrame(monthly_results)
    sim_df['지수'] = (1 + sim_df['수익률']/100).cumprod()
    sim_df['누적수익률'] = (sim_df['지수'] - 1) * 100
    
    m1, m2, m3 = st.columns(3)
    m1.metric("누적 수익률", f"{sim_df['누적수익률'].iloc[-1]:.2f}%")
    m2.metric("월간 승률", f"{(sim_df['수익률'] > 0).mean()*100:.1f}%")
    m3.metric("최대 낙폭(MDD)", f"{((sim_df['지수'] - sim_df['지수'].cummax())/sim_df['지수'].cummax()*100).min():.2f}%")

    chart_col, table_col = st.columns([2, 1])
    with chart_col:
        st.plotly_chart(px.area(sim_df, x='월별', y='누적수익률', title=f"{sel_strat} {s_start}-{s_end}위 수익곡선"), use_container_width=True)
    with table_col:
        st.dataframe(sim_df[['월별', '수익률']].sort_values('월별', ascending=False), use_container_width=True, height=400, hide_index=True)
