import streamlit as st
import pandas as pd
import os
import glob
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# 1. 페이지 설정
st.set_page_config(page_title="모멘텀 구간 시뮬레이터", layout="wide")

# CSS: 디자인 최적화
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem !important; }
    h1 { font-size: 2.2rem !important; font-weight: 800; color: #1E1E1E; }
    .stMetric { background-color: #f0f2f6; padding: 15px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

st.title("🎯 모멘텀 구간 최적화 시뮬레이터")

# 2. 데이터 로드 함수
@st.cache_data
def load_total_archive(folder, prefix):
    files = glob.glob(os.path.join(folder, f"{prefix}*.csv"))
    if not files: return pd.DataFrame()
    
    all_data = []
    for f in sorted(files):
        try:
            df = pd.read_csv(f)
            if '다음달수익률(%)' in df.columns:
                df = df.sort_values('모멘텀스코어', ascending=False).reset_index(drop=True)
                df['순위'] = df.index + 1
                all_data.append(df)
        except: continue
    return pd.concat(all_data) if all_data else pd.DataFrame()

# 3. 마켓 선택 탭
tabs = st.tabs(["🇰🇷 한국 시장", "🇺🇸 미국(150위)", "🇺🇸 S&P 500"])
configs = [("archive", "momentum_"), ("archive_us", "momentum_us_"), ("archive_sp500", "momentum_sp500_")]

for tab, (folder, prefix) in zip(tabs, configs):
    with tab:
        df_master = load_total_archive(folder, prefix)
        if df_master.empty:
            st.warning("데이터가 부족합니다. 'monthly' 스크립트를 실행하여 아카이브를 먼저 쌓아주세요.")
            continue

        # --- [UPGRADE 1: 최상단 구간 설정 슬라이더] ---
        st.subheader("🔍 포트폴리오 구간 설정")
        col_input1, col_input2 = st.columns([2, 1])
        
        with col_input1:
            # 슬라이더로 직관적인 구간 선택
            rank_range = st.slider(
                "분석할 순위 범위를 선택하세요 (예: 11위~30위)",
                1, 200, (1, 20), step=1, key=f"range_{prefix}"
            )
        with col_input2:
            st.write("") # 간격 맞춤
            st.info(f"💡 현재 **{rank_range[1] - rank_range[0] + 1}개** 종목을 집중 분석 중입니다.")

        # 데이터 필터링
        u_start, u_end = rank_range
        u_df = df_master[(df_master['순위'] >= u_start) & (df_master['순위'] <= u_end)]
        
        if not u_df.empty:
            # 월별 수익률 집계
            monthly_perf = u_df.groupby('기준일(월말)')['다음달수익률(%)'].mean().reset_index()
            monthly_perf.columns = ['월별', '수익률']
            monthly_perf['누적수익률'] = ((1 + monthly_perf['수익률']/100).cumprod() - 1) * 100
            
            # --- [UPGRADE 2: 핵심 요약 지표 (Metrics)] ---
            st.markdown("---")
            m1, m2, m3, m4 = st.columns(4)
            
            total_ret = monthly_perf['누적수익률'].iloc[-1]
            win_rate = (monthly_perf['수익률'] > 0).mean() * 100
            # 최대 낙폭(MDD) 계산
            peak = monthly_perf['누적수익률'].cummax()
            drawdown = monthly_perf['누적수익률'] - peak
            mdd = drawdown.min()
            # 샤프지수 대용 (변동성 대비 수익)
            vol = monthly_perf['수익률'].std()
            sharpe_alt = (monthly_perf['수익률'].mean() / vol) if vol != 0 else 0

            m1.metric("최종 누적 수익률", f"{total_ret:.2f}%")
            m2.metric("월간 승률", f"{win_rate:.1f}%")
            m3.metric("최대 낙폭 (MDD)", f"{mdd:.1f}%", delta_color="inverse")
            m4.metric("수익 안정성 (Sharpe)", f"{sharpe_alt:.2f}")

            # --- [UPGRADE 3: 시각화 도구] ---
            st.markdown("---")
            chart_col, table_col = st.columns([1.5, 1])
            
            with chart_col:
                st.subheader("📈 구간 누적 수익률 곡선")
                fig_line = px.area(monthly_perf, x='월별', y='누적수익률', title=f"{u_start}위~{u_end}위 투자 결과")
                fig_line.update_traces(line_color='#0047AB', fillcolor='rgba(0, 71, 171, 0.2)')
                st.plotly_chart(fig_line, use_container_width=True)

            with table_col:
                st.subheader("📅 월별 성적표")
                # 수익률에 따라 색상 입힌 표
                def color_ret(val):
                    color = 'red' if val < 0 else 'blue'
                    return f'color: {color}'
                
                st.dataframe(
                    monthly_perf[['월별', '수익률']].sort_values('월별', ascending=False).style.applymap(color_ret, subset=['수익률']),
                    use_container_width=True, height=400
                )

            # --- [UPGRADE 4: 구간 내 종목별 기여도 분석] ---
            st.markdown("---")
            st.subheader("🏆 해당 구간 역대 최고/최악 종목")
            st.write("이 구간에서 어떤 종목들이 전체 성적을 견인했는지 확인하세요.")
            
            best_stocks = u_df.sort_values('다음달수익률(%)', ascending=False).head(5)
            worst_stocks = u_df.sort_values('다음달수익률(%)', ascending=True).head(5)
            
            col_b, col_w = st.columns(2)
            with col_b:
                st.write("**[Best 5]**")
                st.table(best_stocks[['기준일(월말)', '종목명', '다음달수익률(%)']])
            with col_w:
                st.write("**[Worst 5]**")
                st.table(worst_stocks[['기준일(월말)', '종목명', '다음달수익률(%)']])

        else:
            st.error("해당 구간에 데이터가 존재하지 않습니다. 범위를 조정해주세요.")
