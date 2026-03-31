import streamlit as st
import pandas as pd
import os
import glob
import plotly.express as px
import plotly.graph_objects as go

# ... (상단 데이터 로드 함수 등은 동일하게 유지) ...

for tab, (folder, prefix) in zip(tabs, configs):
    with tab:
        df_master = load_total_archive(folder, prefix)
        if df_master.empty:
            st.warning("데이터가 부족합니다.")
            continue

        # --- [신규 파트: 최적 노다지 구간 자동 탐색기] ---
        st.markdown("---")
        st.header("🏆 전수조사: 어디가 가장 '노다지' 구간인가?")
        st.write("컴퓨터가 모든 구간(시작 순위 1~50위, 종목 수 10~50개)을 시뮬레이션하여 가장 높은 누적 수익률을 기록한 구간을 찾아냅니다.")

        if st.button(f"🚀 최적 수익 구간 전수조사 시작 ({name_tag})", key=f"btn_{prefix}"):
            with st.spinner("과거 모든 데이터를 조합하여 최적의 구간을 계산 중입니다..."):
                search_results = []
                
                # 시작 순위: 1위부터 50위까지 5단위로 테스트
                # 종목 수: 10개부터 50개까지 5단위로 테스트
                for start in range(1, 51, 5):
                    for size in range(10, 51, 5):
                        end = start + size - 1
                        
                        # 해당 구간 필터링
                        sub_df = df_master[(df_master['순위'] >= start) & (df_master['순위'] <= end)]
                        
                        if not sub_df.empty:
                            # 월별 평균 수익률 및 복리 누적 수익률 계산
                            m_perf = sub_df.groupby('기준일(월말)')['다음달수익률(%)'].mean()
                            if not m_perf.empty:
                                # 복리 누적 수익률 공식: [(1+r1)*(1+r2)*...]-1
                                cum_ret = ((1 + m_perf/100).cumprod().iloc[-1] - 1) * 100
                                win_rate = (m_perf > 0).mean() * 100
                                
                                search_results.append({
                                    "시작 순위": f"{start}위",
                                    "종목 수": f"{size}개",
                                    "구간 범위": f"{start}위 ~ {end}위",
                                    "최종 누적 수익률": round(cum_ret, 2),
                                    "월간 승률": round(win_rate, 1)
                                })
                
                if search_results:
                    optimizer_df = pd.DataFrame(search_results).sort_values("최종 누적 수익률", ascending=False)
                    
                    # 1. 챔피언 구간 발표
                    winner = optimizer_df.iloc[0]
                    st.success(f"🎊 분석 결과, 가장 수익률이 좋은 구간은 **[{winner['구간 범위']}]** 입니다!")
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("최고 누적 수익률", f"{winner['최종 누적 수익률']}%")
                    c2.metric("최적 시작 순위", winner['시작 순위'])
                    c3.metric("최적 종목 수", winner['종목 수'])
                    
                    # 2. TOP 10 노다지 구간 표
                    st.markdown("---")
                    st.subheader("📊 수익률 상위 10개 구간 리스트")
                    st.table(optimizer_df.head(10).assign(
                        **{'최종 누적 수익률': optimizer_df['최종 누적 수익률'].head(10).map('{:,.2f}%'.format),
                           '월간 승률': optimizer_df['월간 승률'].head(10).map('{:.1f}%'.format)}
                    ).reset_index(drop=True))
                    
                    # 3. 열지도(Heatmap) 시각화 - 시작순위 vs 종목수
                    st.subheader("🗺️ 구간별 수익률 열지도 (어디에 수익이 몰려있나?)")
                    # 피벗 테이블 생성
                    heatmap_data = optimizer_df.pivot(index="종목 수", columns="시작 순위", values="최종 누적 수익률")
                    # 정렬 (인덱스와 컬럼 순서 맞추기)
                    heatmap_data = heatmap_data.sort_index(ascending=False)
                    
                    fig_heat = px.imshow(heatmap_data, 
                                         labels=dict(x="시작 순위", y="종목 수", color="누적 수익률(%)"),
                                         color_continuous_scale='RdBu_r',
                                         aspect="auto")
                    st.plotly_chart(fig_heat, use_container_width=True)
                else:
                    st.error("분석 가능한 데이터가 충분하지 않습니다.")

        # --- [그 아래에 기존의 '내 맘대로 구간 테스트' 위치] ---
        st.markdown("---")
        # (기존 슬라이더 및 상세 분석 코드...)
