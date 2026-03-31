import streamlit as st
import pandas as pd
import os
import glob
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="모멘텀 최적화 분석", layout="wide")

st.title("🎯 모멘텀 순위별 성과 감쇄(Decay) 분석")
st.info("1위부터 300위까지 각 순위가 역대 기록한 평균 수익률을 분석하여 최적의 포트폴리오 규모를 도출합니다.")

def load_all_data(folder, prefix):
    files = glob.glob(os.path.join(folder, f"{prefix}*.csv"))
    if not files: return pd.DataFrame()
    
    all_data = []
    for f in sorted(files):
        try:
            df = pd.read_csv(f)
            if '다음달수익률(%)' in df.columns:
                # 💡 파일 내에서의 순위(Rank)를 1부터 다시 매김 (혹시 모르니)
                df = df.sort_values('모멘텀스코어', ascending=False).reset_index(drop=True)
                df['순위'] = df.index + 1
                all_data.append(df[['순위', '다음달수익률(%)', '종목명']])
        except: continue
    return pd.concat(all_data) if all_data else pd.DataFrame()

tabs = st.tabs(["🇰🇷 한국", "🇺🇸 미국(150위)", "🇺🇸 S&P 500"])
configs = [("archive", "momentum_"), ("archive_us", "momentum_us_"), ("archive_sp500", "momentum_sp500_")]

for tab, (folder, prefix) in zip(tabs, configs):
    with tab:
        df_all = load_all_data(folder, prefix)
        if df_all.empty:
            st.warning("데이터가 부족합니다.")
            continue

        # --- (1) 순위별 평균 수익률 분석 ---
        # 순위별로 그룹화하여 평균 수익률 계산
        rank_perf = df_all.groupby('순위')['다음달수익률(%)'].mean().reset_index()
        
        # 💡 노이즈 제거를 위한 이동평균(Rolling Average) 추가
        rank_perf['수익률_추세선'] = rank_perf['다음달수익률(%)'].rolling(window=10, min_periods=1).mean()

        st.subheader("📉 순위가 낮아질수록 수익률은 어떻게 변하는가?")
        fig = go.Figure()
        # 원본 데이터 (연한 색)
        fig.add_trace(go.Bar(x=rank_perf['순위'], y=rank_perf['다음달수익률(%)'], name='순위별 평균', marker_color='lightgrey'))
        # 추세선 (진한 색)
        fig.add_trace(go.Scatter(x=rank_perf['순위'], y=rank_perf['수익률_추세선'], name='수익률 추세(10일 이동평균)', line=dict(color='#FF4B4B', width=3)))
        
        fig.update_layout(xaxis_title="순위 (1위 -> 300위)", yaxis_title="평균 수익률 (%)", hovermode='x unified')
        st.plotly_chart(fig, use_container_width=True)

        # --- (2) 누적 종목 수에 따른 포트폴리오 수익률 ---
        # 1위부터 N위까지 묶었을 때의 평균 수익률 변화
        rank_perf['누적포트폴리오수익률'] = rank_perf['다음달수익률(%)'].expanding().mean()
        
        st.subheader("⚖️ 종목 수(N)를 늘릴 때 포트폴리오 전체 수익률 변화")
        st.write("왼쪽에서 오른쪽으로 갈수록 종목을 더 많이 섞는 것입니다. 수익률이 꺾이기 시작하는 지점을 찾으세요.")
        fig2 = px.line(rank_perf, x='순위', y='누적포트폴리오수익률', title="1위부터 N위까지 포함했을 때의 평균 수익률")
        fig2.add_hline(y=0, line_dash="dash", line_color="red")
        st.plotly_chart(fig2, use_container_width=True)

        # --- (3) 데이터 기반 전략 제안 ---
        st.markdown("---")
        st.subheader("💡 데이터 분석 결과 가이드")
        
        # 가장 수익률이 높은 누적 종목 수 찾기
        best_n = rank_perf.loc[rank_perf['누적포트폴리오수익률'].idxmax(), '순위']
        max_ret = rank_perf['누적포트폴리오수익률'].max()
        
        # 수익률이 0 이하로 떨어지기 시작하는 '데드라인' 순위
        under_zero = rank_perf[rank_perf['수익률_추세선'] < 0]
        deadline = under_zero['순위'].min() if not under_zero.empty else len(rank_perf)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("수익률 정점 (종목 수)", f"TOP {int(best_n)}")
            st.caption(f"1위부터 {int(best_n)}위까지 섞을 때 수익이 가장 극대화됩니다.")
        with c2:
            st.metric("최고 기대 수익률", f"{max_ret:.2f}%")
            st.caption("해당 포트폴리오 구성 시의 월평균 기대치입니다.")
        with c3:
            st.metric("유효 모멘텀 한계선", f"{int(deadline)}위")
            st.caption(f"{int(deadline)}위 이후부터는 모멘텀의 힘이 사라집니다.")

        st.warning(f"**결론:** 사용자님의 데이터상 가장 유리한 포트폴리오는 **상위 {int(best_n)}~{int(best_n+10)}개**를 집중 보유하는 것입니다. {int(deadline)}위가 넘어가면 종목을 섞을수록 계좌 수익률을 깎아먹는 '물타기'가 됩니다.")
