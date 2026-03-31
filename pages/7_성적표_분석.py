import streamlit as st
import pandas as pd
import os
import glob
import plotly.express as px
import plotly.graph_objects as go

# 1. 페이지 설정
st.set_page_config(page_title="모멘텀 구간 시뮬레이터", layout="wide")

# CSS: 메트릭 숫자가 안 보일 수 있는 현상 방지 (배경색 및 글자색 강제 지정)
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem !important; }
    h1 { font-size: 2.2rem !important; font-weight: 800; color: #1E1E1E; }
    /* 메트릭 카드 가독성 강화 */
    [data-testid="stMetricValue"] { font-size: 1.8rem !important; color: #0047AB !important; }
    [data-testid="stMetricLabel"] { font-weight: bold !important; color: #333333 !important; }
    .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #dee2e6; }
    </style>
    """, unsafe_allow_html=True)

st.title("🎯 모멘텀 구간 최적화 시뮬레이터")

# 2. 데이터 로드 함수 (캐싱 적용)
@st.cache_data
def load_total_archive(folder, prefix):
    # 해당 폴더 내의 모든 CSV 파일을 가져옴
    files = glob.glob(os.path.join(folder, f"{prefix}*.csv"))
    if not files: return pd.DataFrame()
    
    all_data = []
    for f in sorted(files):
        try:
            df = pd.read_csv(f)
            # 컬럼명 확인 및 전처리
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
            st.warning(f"💡 '{folder}' 폴더에 CSV 파일이 없습니다. 월말 스크립트를 먼저 실행해 주세요.")
            continue

        # --- [구간 설정 섹션] ---
        st.subheader("🔍 포트폴리오 구간 설정")
        col_input1, col_input2 = st.columns([2, 1])
        
        with col_input1:
            rank_range = st.slider(
                "분석할 순위 범위를 선택하세요",
                1, 300, (1, 20), step=1, key=f"range_{prefix}"
            )
        with col_input2:
            st.write("") 
            st.info(f"✅ 현재 **{rank_range[0]}위 ~ {rank_range[1]}위** 분석 중")

        # 데이터 필터링
        u_start, u_end = rank_range
        u_df = df_master[(df_master['순위'] >= u_start) & (df_master['순위'] <= u_end)]
        
        # 월별 수익률 집계 (기준일별 평균)
        if not u_df.empty:
            # '기준일(월말)' 컬럼을 기준으로 그룹화
            date_col = '기준일(월말)' if '기준일(월말)' in u_df.columns else '기준일'
            monthly_perf = u_df.groupby(date_col)['다음달수익률(%)'].mean().reset_index()
            monthly_perf.columns = ['월별', '수익률']
            
            # 수익률이 모두 0인지 확인 (데이터 존재 여부 체크)
            if monthly_perf['수익률'].abs().sum() == 0:
                st.warning("⚠️ 선택한 구간의 수익률 데이터가 모두 0입니다. (과거 성적표가 아직 기록되지 않았습니다.)")

            # --- [복리 기반 성과 지표 계산] ---
            # 1. 누적 지수(Equity Curve)
            monthly_perf['지수'] = (1 + monthly_perf['수익률']/100).cumprod()
            monthly_perf['누적수익률'] = (monthly_perf['지수'] - 1) * 100
            
            # 2. MDD (전고점 대비 하락률)
            peak = monthly_perf['지수'].cummax()
            drawdown = (monthly_perf['지수'] - peak) / peak * 100
            mdd_val = drawdown.min()
            
            # 3. 승률 및 안정성
            win_rate = (monthly_perf['수익률'] > 0).mean() * 100
            vol = monthly_perf['수익률'].std()
            sharpe = (monthly_perf['수익률'].mean() / vol) if vol > 0 else 0

            # --- [핵심 지표 출력 (수익률 부분)] ---
            st.markdown("---")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("최종 누적 수익률", f"{monthly_perf['누적수익률'].iloc[-1]:.2f}%")
            m2.metric("월간 승률", f"{win_rate:.1f}%")
            m3.metric("최대 낙폭 (MDD)", f"{mdd_val:.2f}%")
            m4.metric("수익 안정성", f"{sharpe:.2f}")

            # --- [그래프 및 표 상세] ---
            st.markdown("---")
            chart_col, table_col = st.columns([1.6, 1])
            
            with chart_col:
                st.subheader("📈 구간 누적 수익률 곡선")
                fig_line = px.area(monthly_perf, x='월별', y='누적수익률')
                fig_line.update_traces(line_color='#0047AB', fillcolor='rgba(0, 71, 171, 0.1)')
                fig_line.update_layout(hovermode='x unified', margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig_line, use_container_width=True)

            with table_col:
                st.subheader("📅 월별 상세 성적")
                st.dataframe(
                    monthly_perf[['월별', '수익률']].sort_values('월별', ascending=False),
                    use_container_width=True, height=400,
                    column_config={
                        "수익률": st.column_config.NumberColumn("수익률", format="%.2f%%")
                    }
                )

            # --- [구간 내 종목 리스트] ---
            st.markdown("---")
            st.subheader(f"🏆 {u_start}위~{u_end}위 역대 베스트 종목")
            best_stocks = u_df.sort_values('다음달수익률(%)', ascending=False).head(10)
            st.table(best_stocks[['월별', '종목명', '다음달수익률(%)']].assign(
                **{'다음달수익률(%)': best_stocks['다음달수익률(%)'].map('{:+.2f}%'.format)}
            ).rename(columns={'월별': '투자월'}).reset_index(drop=True))

        else:
            st.error("분석할 데이터가 없습니다. 범위를 조정해 주세요.")
