import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime
import os
import glob
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="KOSPI 200 전략 최적화", layout="wide")

# CSS: 시인성 강화
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem !important; }
    h1 { font-size: 2.2rem !important; font-weight: 800; color: #1E1E1E; }
    
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

# 2. 데이터 로드 및 전처리 (캐싱)
@st.cache_data(ttl=3600)
def load_and_process_strategy_data(folder="archive", prefix="momentum_"):
    files = glob.glob(os.path.join(folder, f"{prefix}*.csv"))
    if not files: return pd.DataFrame()

    # KOSPI 200 필터링을 위한 시가총액 정보 (티커 6자리 보정 완벽 적용)
    try:
        kospi_info = fdr.StockListing('KOSPI')[['Code', 'Marcap']]
        kospi_info['Code'] = kospi_info['Code'].astype(str).str.zfill(6)
    except:
        kospi_info = pd.DataFrame(columns=['Code', 'Marcap'])

    all_perf, all_spec, all_inter = [], [], []

    for f in sorted(files):
        try:
            df = pd.read_csv(f, dtype={'종목코드': str})
            # 💡 [버그 픽스] 컬럼명 공백 제거 완벽 대응
            df.columns = df.columns.str.replace(' ', '') 
            
            if '다음달수익률(%)' not in df.columns: continue

            # 💡 [버그 픽스] 티커 6자리 통일하여 병합 실패 원천 차단
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

            # 💡 [핵심] KOSPI 200 페이지와 동일하게 '모멘텀스코어' 기준으로 강제 정렬하여 1등을 정확히 매핑!
            df_perf = df_k[cond_perf].sort_values('모멘텀스코어', ascending=False).copy()
            df_spec = df_k[cond_spec].sort_values('모멘텀스코어', ascending=False).copy()
            df_inter = df_k[cond_perf & cond_spec].sort_values('모멘텀스코어', ascending=False).copy()

            def extract_strategy(d, strat_name, target_list):
                if not d.empty:
                    d = d.reset_index(drop=True)
                    d['전략순위'] = range(1, len(d) + 1) 
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

    test_ranges = [
        (1, 1), (2, 2), (3, 3), (4, 4), (5, 5), 
        (1, 2), (1, 3), (1, 5), (1, 10),        
        (2, 3), (2, 5), (3, 5)                  
    ]

    for s, e in test_ranges:
        monthly_returns = []
            for d in dates:
                    # 이 줄의 시작 여백과 아래 줄들의 여백이 수직으로 딱 맞아야 합니다.
                    month_data = target_df[(target_df['기준일(월말)'] == d) & (target_df['전략순위'] >= s_start) & (target_df['전략순위'] <= s_end)]
                    
                    # 💡 [디버깅 코드 삽입] 들여쓰기 칸 수를 위 줄과 똑같이 맞췄습니다.
                    if d == '2026-01-30' and s_start == 1 and s_end == 1:
                        st.write(f"🚩 디버깅: {sel_strat} 1위 종목 상세 (2026-01-30)")
                        st.write(month_data)
                    
                    ret = month_data['다음달수익률(%)'].mean() if not month_data.empty else 0.0
                    monthly_data.append({'월별': d, '수익률': ret})

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
            best = res_df.iloc[0]
            st.success(f"🏆 Best: **{best['투자 전략 (순위)']}** ({best['최종 누적 수익률']:.2f}%)")
            st.dataframe(format_sim_df(res_df), use_container_width=True, hide_index=True)
        else:
            st.info("데이터 부족")

st.markdown("---")

# --- [화면 렌더링 2. 정밀 시뮬레이터] ---
st.subheader("🔬 커스텀 구간 정밀 백테스팅")

c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    sel_strat = st.selectbox("분석할 전략 선택", strategies)
with c2:
    sel_range = st.slider("투자할 순위 범위 설정", 1, 15, (1, 3))

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
