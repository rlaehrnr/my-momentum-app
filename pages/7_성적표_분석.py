import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime
import os
import glob
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="KOSPI 200 전략 최적화", layout="wide")

# CSS: 시인성 강화 (진한 배경/진한 글자 강제 지정)
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem !important; }
    h1 { font-size: 2.2rem !important; font-weight: 800; color: #1E1E1E; }
    
    /* 메트릭 카드 시인성 강화 */
    [data-testid="stMetricValue"] { 
        font-size: 2.0rem !important; 
        color: #0047AB !important; 
        font-weight: 800 !important;
    }
    [data-testid="stMetricLabel"] { 
        font-weight: bold !important; 
        color: #333333 !important; 
    }
    .stMetric { 
        background-color: #f0f2f6 !important; 
        padding: 20px !important; 
        border-radius: 12px !important; 
        border: 2px solid #d1d5db !important;
    }
    
    .section-title {
        background-color: #1F2937;
        color: white;
        padding: 10px 15px;
        border-radius: 8px 8px 0 0;
        font-size: 1.2rem;
        font-weight: bold;
        border-bottom: 4px solid #EF4444;
        margin-top: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🎯 KOSPI 200 전략별 최적 구간 탐색기")

# 2. 데이터 로드 및 KOSPI 200 전략 백테스팅 전처리 (캐싱)
@st.cache_data(ttl=3600)
def load_and_process_strategy_data(folder="archive", prefix="momentum_"):
    files = glob.glob(os.path.join(folder, f"{prefix}*.csv"))
    if not files: return pd.DataFrame()

    # KOSPI 200 필터링을 위한 시가총액 정보 가져오기 (현재 기준 근사치)
    try:
        kospi_info = fdr.StockListing('KOSPI')[['Code', 'Marcap']]
    except:
        kospi_info = pd.DataFrame(columns=['Code', 'Marcap'])

    all_perf = []
    all_spec = []
    all_inter = []

    for f in sorted(files):
        try:
            df = pd.read_csv(f, dtype={'종목코드': str})
            if '다음달수익률(%)' not in df.columns: continue

            # 숫자 변환
            for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '다음달수익률(%)', '모멘텀스코어']:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

            # KOSPI 200 후보군 필터링 (KOSPI & 끝자리 0)
            df_k = df[(df['시장'] == 'KOSPI') & (df['종목코드'].str.endswith('0'))].copy()
            if not kospi_info.empty:
                df_k = df_k.merge(kospi_info, left_on='종목코드', right_on='Code', how='left')
                df_k['시가총액'] = df_k['Marcap'].fillna(0)
                df_k = df_k.sort_values(by='시가총액', ascending=False).head(200)

            if df_k.empty: continue

            # 분위수 계산
            q30 = {c: df_k[c].quantile(0.7) for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']}
            t10_1m = df_k['1개월(%)'].quantile(0.9)

            # 조건 검출
            cond_perf = (df_k['1개월(%)']>=q30['1개월(%)'])&(df_k['3개월(%)']>=q30['3개월(%)'])&(df_k['6개월(%)']>=q30['6개월(%)'])&(df_k['12개월(%)']>=q30['12개월(%)']) & \
                        (df_k['1개월(%)']>0)&(df_k['3개월(%)']>0)&(df_k['6개월(%)']>0)&(df_k['12개월(%)']>0)
            cond_spec = (df_k['12개월(%)']>=q30['12개월(%)']) & (df_k['1개월(%)']>=t10_1m)

            df_perf = df_k[cond_perf].sort_values('모멘텀스코어', ascending=False).copy()
            df_spec = df_k[cond_spec].sort_values('모멘텀스코어', ascending=False).copy()
            df_inter = df_k[cond_perf & cond_spec].sort_values('모멘텀스코어', ascending=False).copy()

            b_date = df['기준일(월말)'].iloc[0]

            # 전략별 데이터 적재 보조 함수
            def extract_strategy(d, strat_name, target_list):
                if not d.empty:
                    d['전략순위'] = range(1, len(d) + 1) # 모멘텀스코어 기준 순위
                    d['전략명'] = strat_name
                    target_list.append(d[['기준일(월말)', '다음달수익률(%)', '전략순위', '전략명']])

            extract_strategy(df_perf, '🔥 퍼펙트 상승', all_perf)
            extract_strategy(df_spec, '🚀 달리는 말', all_spec)
            extract_strategy(df_inter, '🌟 교집합', all_inter)

        except Exception as e:
            continue

    combined = all_perf + all_spec + all_inter
    return pd.concat(combined, ignore_index=True) if combined else pd.DataFrame()

# 3. 데이터 준비
df_master = load_and_process_strategy_data()

if df_master.empty:
    st.error("분석할 과거 아카이브 데이터(archive 폴더)가 부족하거나 없습니다.")
    st.stop()

# --- [시뮬레이션 엔진] ---
def run_range_simulation(df, strategy_name):
    strat_df = df[df['전략명'] == strategy_name]
    if strat_df.empty: return pd.DataFrame()

    dates = sorted(strat_df['기준일(월말)'].unique())
    results = []

    # 테스트할 다양한 순위 구간 (단일 등수 및 분산)
    test_ranges = [
        (1, 1), (2, 2), (3, 3), (4, 4), (5, 5), # 단독 매수
        (1, 2), (1, 3), (1, 5), (1, 10),        # 1위부터 누적 분산
        (2, 3), (2, 5), (3, 5)                  # 상위권 일부 분산
    ]

    for s, e in test_ranges:
        monthly_returns = []
        for d in dates:
            month_data = strat_df[(strat_df['기준일(월말)'] == d) & (strat_df['전략순위'] >= s) & (strat_df['전략순위'] <= e)]
            if not month_data.empty:
                monthly_returns.append(month_data['다음달수익률(%)'].mean())
            else:
                monthly_returns.append(0.0) # 조건에 맞는 종목이 없으면 현금 보유(0%)

        perf = pd.Series(monthly_returns)
        equity = (1 + perf/100).cumprod()
        cum_ret = (equity.iloc[-1] - 1) * 100
        peak = equity.cummax()
        mdd = ((equity - peak)/peak * 100).min()
        win_rate = (perf > 0).mean() * 100

        label = f"{s}위 전몰빵" if s == e else f"{s}위 ~ {e}위 분산"
        results.append({
            "투자 전략 (순위)": label,
            "최종 누적 수익률": cum_ret,
            "최대 낙폭(MDD)": mdd,
            "월간 승률": win_rate
        })

    return pd.DataFrame(results).sort_values("최종 누적 수익률", ascending=False)

# 포맷팅 함수
def format_sim_df(df):
    return df.assign(
        **{
            '최종 누적 수익률': df['최종 누적 수익률'].map('{:,.2f}%'.format),
            '최대 낙폭(MDD)': df['최대 낙폭(MDD)'].map('{:,.2f}%'.format),
            '월간 승률': df['월간 승률'].map('{:,.1f}%'.format)
        }
    ).reset_index(drop=True)

# --- [화면 렌더링 1. 전략별 자동 비교] ---
st.write("과거 아카이브를 전수조사하여, KOSPI 200 각 전략에서 **몇 등 종목을 샀을 때 가장 수익률이 좋은지** 검증합니다.")

col1, col2, col3 = st.columns(3)

strategies = ['🔥 퍼펙트 상승', '🚀 달리는 말', '🌟 교집합']
cols = [col1, col2, col3]

for col, strat in zip(cols, strategies):
    with col:
        st.markdown(f'<div class="section-title">{strat} 성과표</div>', unsafe_allow_html=True)
        res_df = run_range_simulation(df_master, strat)
        
        if not res_df.empty:
            # 1등 전략 하이라이트 표시
            best = res_df.iloc[0]
            st.success(f"🏆 Best: **{best['투자 전략 (순위)']}** ({best['최종 누적 수익률']:.2f}%)")
            st.dataframe(format_sim_df(res_df), use_container_width=True, hide_index=True)
        else:
            st.info("데이터 부족")

st.markdown("---")

# --- [화면 렌더링 2. 정밀 시뮬레이터 (차트 포함)] ---
st.subheader("🔬 커스텀 구간 정밀 백테스팅")

c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    sel_strat = st.selectbox("분석할 전략 선택", strategies)
with c2:
    sel_range = st.slider("투자할 순위 범위 설정", 1, 15, (1, 3))

# 선택한 설정으로 상세 데이터 생성
s_start, s_end = sel_range
target_df = df_master[df_master['전략명'] == sel_strat]

if not target_df.empty:
    dates = sorted(target_df['기준일(월말)'].unique())
    monthly_data = []

    for d in dates:
        month_data = target_df[(target_df['기준일(월말)'] == d) & (target_df['전략순위'] >= s_start) & (target_df['전략순위'] <= s_end)]
        ret = month_data['다음달수익률(%)'].mean() if not month_data.empty else 0.0
        monthly_data.append({'월별': d, '수익률': ret})

    sim_df = pd.DataFrame(monthly_data)
    sim_df['지수'] = (1 + sim_df['수익률']/100).cumprod()
    sim_df['누적수익률'] = (sim_df['지수'] - 1) * 100
    
    peak = sim_df['지수'].cummax()
    mdd = ((sim_df['지수'] - peak) / peak * 100).min()
    win_rate = (sim_df['수익률'] > 0).mean() * 100
    vol = sim_df['수익률'].std()
    sharpe = (sim_df['수익률'].mean() / vol) if vol > 0 else 0

    st.markdown("<br>", unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("최종 누적 수익률", f"{sim_df['누적수익률'].iloc[-1]:.2f}%")
    m2.metric("월간 승률", f"{win_rate:.1f}%")
    m3.metric("최대 낙폭 (MDD)", f"{mdd:.2f}%")
    m4.metric("안정성 (Sharpe)", f"{sharpe:.2f}")

    chart_col, table_col = st.columns([1.6, 1])
    with chart_col:
        st.markdown(f"**📈 [{sel_strat}] {s_start}~{s_end}위 누적 수익 곡선**")
        fig = px.area(sim_df, x='월별', y='누적수익률')
        fig.update_traces(line_color='#0047AB', fillcolor='rgba(0, 71, 171, 0.1)')
        st.plotly_chart(fig, use_container_width=True)
    with table_col:
        st.markdown("**📅 월별 상세 성적**")
        st.dataframe(
            sim_df[['월별', '수익률']].sort_values('월별', ascending=False),
            use_container_width=True, height=450, hide_index=True,
            column_config={"수익률": st.column_config.NumberColumn(format="%.2f%%")}
        )
else:
    st.warning("선택한 전략의 데이터가 없습니다.")
