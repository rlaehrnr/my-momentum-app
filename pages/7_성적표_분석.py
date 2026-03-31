import streamlit as st
import pandas as pd
import os
import glob
import plotly.express as px
import plotly.graph_objects as go

# 1. 페이지 설정
st.set_page_config(page_title="모멘텀 구간 시뮬레이터", layout="wide")

# CSS: 디자인 및 가독성 최적화
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem !important; }
    h1 { font-size: 2.2rem !important; font-weight: 800; color: #1E1E1E; }
    .stMetric { background-color: #f0f2f6; padding: 15px; border-radius: 10px; border: 1px solid #d1d5db; }
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
                # 스코어 기준 재정렬 및 순위 부여
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
            st.warning(f"'{folder}' 폴더에 분석할 아카이브 데이터가 없습니다.")
            continue

        # --- [최상단: 구간 설정 슬라이더] ---
        st.subheader("🔍 포트폴리오 구간 설정")
        col_input1, col_input2 = st.columns([2, 1])
        
        with col_input1:
            rank_range = st.slider(
                "분석할 순위 범위를 선택하세요",
                1, 300, (1, 20), step=1, key=f"range_{prefix}"
            )
        with col_input2:
            st.write("") 
            st.success(f"✅ 현재 **{rank_range[0]}위 ~ {rank_range[1]}위** 구간을 분석 중입니다.")

        # 데이터 필터링
        u_start, u_end = rank_range
        u_df = df_master[(df_master['순위'] >= u_start) & (df_master['순위'] <= u_end)]
        
        if not u_df.empty:
            # 월별 수익률 집계
            monthly_perf = u_df.groupby('기준일(월말)')['다음달수익률(%)'].mean().reset_index()
            monthly_perf.columns = ['월별', '수익률']
            
            # ⭐ [복리 계산] 누적 지수(Equity Curve) 생성
            # 100원에서 시작한다고 가정
            monthly_perf['지수'] = (1 + monthly_perf['수익률']/100).cumprod()
            monthly_perf['누적수익률'] = (monthly_perf['지수'] - 1) * 100
            
            # ⭐ [MDD 교정] 전고점 대비 하락률로 계산 (복리 방식)
            peak = monthly_perf['지수'].cummax()
            drawdown = (monthly_perf['지수'] - peak) / peak * 100
            mdd = drawdown.min()
            
            # 변동성 및 샤프지수
            vol = monthly_perf['수익률'].std()
            sharpe = (monthly_perf['수익률'].mean() / vol) if vol > 0 else 0

            # --- [핵심 지표 출력] ---
            st.markdown("---")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("최종 누적 수익률", f"{monthly_perf['누적수익률'].iloc[-1]:.2f}%")
            m2.metric("월간 승률", f"{(monthly_perf['수익률'] > 0).mean()*100:.1f}%")
            m3.metric("최대 낙폭 (MDD)", f"{mdd:.2f}%")
            m4.metric("수익 안정성 (Sharpe)", f"{sharpe:.2f}")

            # --- [시각화 및 표] ---
            st.markdown("---")
            chart_col, table_col = st.columns([1.6, 1])
            
            with chart_col:
                st.subheader("📈 구간 누적 수익률 곡선")
                fig_line = px.area(monthly_perf, x='월별', y='누적수익률')
                fig_line.update_traces(line_color='#0047AB', fillcolor='rgba(0, 71, 171, 0.1)')
                fig_line.update_layout(hovermode='x unified', yaxis_title="누적 수익률 (%)")
                st.plotly_chart(fig_line, use_container_width=True)

            with table_col:
                st.subheader("📅 월별 성적표")
                # ⭐ 수익률 소수점 2째자리 고정 및 스타일 적용
                st.dataframe(
                    monthly_perf[['월별', '수익률']].sort_values('월별', ascending=False),
                    use_container_width=True, height=450,
                    column_config={
                        "월별": "투자 월",
                        "수익률": st.column_config.NumberColumn("수익률", format="%.2f%%")
                    }
                )

            # --- [종목별 상세 분석] ---
            st.markdown("---")
            st.subheader(f"🏆 {u_start}위~{u_end}위 구간 역대 BEST 10 종목")
            best_stocks = u_df.sort_values('다음달수익률(%)', ascending=False).head(10)
            
            st.table(best_stocks[['기준일(월말)', '종목명', '다음달수익률(%)']].assign(
                **{'다음달수익률(%)': best_stocks['다음달수익률(%)'].map('{:+.2f}%'.format)}
            ).reset_index(drop=True))

        else:
            st.error("해당 구간에 데이터가 없습니다. 범위를 다시 설정해주세요.")
