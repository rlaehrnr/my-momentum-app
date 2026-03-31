import streamlit as st
import pandas as pd
import os
import glob
import plotly.express as px
import plotly.graph_objects as go

# 1. 페이지 설정
st.set_page_config(page_title="모멘텀 구간 최적화", layout="wide")

# CSS: 디자인 및 가독성 최적화
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem !important; }
    h1 { font-size: 2.2rem !important; font-weight: 800; color: #1E1E1E; }
    [data-testid="stMetricValue"] { font-size: 1.8rem !important; color: #0047AB !important; }
    .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #dee2e6; }
    </style>
    """, unsafe_allow_html=True)

st.title("🎯 모멘텀 최적 구간 탐색기")

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

# 3. 마켓 선택 탭 (이름 태그 포함)
tabs_name = ["🇰🇷 한국 시장", "🇺🇸 미국(150위)", "🇺🇸 S&P 500"]
tabs = st.tabs(tabs_name)
configs = [
    ("archive", "momentum_", "한국"), 
    ("archive_us", "momentum_us_", "미국(150위)"), 
    ("archive_sp500", "momentum_sp500_", "S&P 500")
]

for tab, (folder, prefix, name_tag) in zip(tabs, configs):
    with tab:
        df_master = load_total_archive(folder, prefix)
        
        if df_master.empty:
            st.warning(f"💡 '{folder}' 폴더에 데이터가 없습니다.")
            continue

        # --- [1. 최적 노다지 구간 자동 탐색기] ---
        st.header(f"🚀 {name_tag} 최적 수익 구간 전수조사")
        st.write("컴퓨터가 시작 순위(1~50위)와 종목 수(10~50개)를 조합하여 수익률이 가장 높은 '챔피언 구간'을 찾습니다.")

        if st.button(f"🔎 전수조사 시작 ({name_tag})", key=f"btn_{prefix}"):
            with st.spinner("모든 시나리오를 계산 중입니다..."):
                search_results = []
                # 시작 순위: 1, 6, 11... 46위까지 (5단위)
                # 종목 수: 10, 15, 20... 50개까지 (5단위)
                for start in range(1, 51, 5):
                    for size in range(10, 51, 5):
                        end = start + size - 1
                        sub_df = df_master[(df_master['순위'] >= start) & (df_master['순위'] <= end)]
                        
                        if not sub_df.empty:
                            # 월별 평균 수익률 계산
                            m_perf = sub_df.groupby('기준일(월말)')['다음달수익률(%)'].mean()
                            if not m_perf.empty:
                                # 복리 누적 수익률 계산
                                cum_ret = ((1 + m_perf/100).cumprod().iloc[-1] - 1) * 100
                                win_rate = (m_perf > 0).mean() * 100
                                
                                search_results.append({
                                    "시작 순위": f"{start}위",
                                    "종목 수": f"{size}개",
                                    "구간": f"{start}위 ~ {end}위",
                                    "최종 누적 수익률": round(cum_ret, 2),
                                    "월간 승률": round(win_rate, 1)
                                })
                
                if search_results:
                    optimizer_df = pd.DataFrame(search_results).sort_values("최종 누적 수익률", ascending=False)
                    winner = optimizer_df.iloc[0]
                    
                    st.success(f"🏆 분석 완료! 가장 수익률이 좋은 구간은 **[{winner['구간']}]** 입니다.")
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("최고 누적 수익률", f"{winner['최종 누적 수익률']}%")
                    c2.metric("권장 시작 순위", winner['시작 순위'])
                    c3.metric("권장 매수 종목 수", winner['종목 수'])
                    
                    st.markdown("---")
                    st.subheader("📊 수익률 TOP 10 구간 리스트")
                    st.table(optimizer_df.head(10).assign(
                        **{'최종 누적 수익률': optimizer_df['최종 누적 수익률'].head(10).map('{:,.2f}%'.format)}
                    ).reset_index(drop=True))
                else:
                    st.error("분석할 충분한 데이터가 없습니다.")

        st.markdown("---")

        # --- [2. 내 맘대로 구간 정밀 분석 (기존 기능)] ---
        st.subheader("🔬 구간 정밀 시뮬레이션")
        rank_range = st.slider(
            "분석할 범위를 직접 조절해보세요",
            1, 300, (1, 20), step=1, key=f"range_{prefix}"
        )

        u_start, u_end = rank_range
        u_df = df_master[(df_master['순위'] >= u_start) & (df_master['순위'] <= u_end)]
        
        if not u_df.empty:
            monthly_perf = u_df.groupby('기준일(월말)')['다음달수익률(%)'].mean().reset_index()
            monthly_perf.columns = ['월별', '수익률']
            
            # 복리 계산 기반 지표
            monthly_perf['지수'] = (1 + monthly_perf['수익률']/100).cumprod()
            monthly_perf['누적수익률'] = (monthly_perf['지수'] - 1) * 100
            
            peak = monthly_perf['지수'].cummax()
            mdd = ((monthly_perf['지수'] - peak) / peak * 100).min()
            
            # 지표 출력
            st.markdown("---")
            m1, m2, m3 = st.columns(3)
            m1.metric("누적 수익률", f"{monthly_perf['누적수익률'].iloc[-1]:.2f}%")
            m2.metric("월간 승률", f"{(monthly_perf['수익률'] > 0).mean()*100:.1f}%")
            m3.metric("최대 낙폭 (MDD)", f"{mdd:.2f}%")

            # 시각화
            chart_col, table_col = st.columns([1.6, 1])
            with chart_col:
                st.subheader("📈 누적 수익 곡선")
                fig = px.area(monthly_perf, x='월별', y='누적수익률')
                fig.update_traces(line_color='#0047AB', fillcolor='rgba(0, 71, 171, 0.1)')
                st.plotly_chart(fig, use_container_width=True)
            with table_col:
                st.subheader("📅 월별 상세 성적")
                st.dataframe(
                    monthly_perf[['월별', '수익률']].sort_values('월별', ascending=False),
                    use_container_width=True, height=400,
                    column_config={"수익률": st.column_config.NumberColumn(format="%.2f%%")}
                )
