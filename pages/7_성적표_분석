import streamlit as st
import pandas as pd
import os
import glob
import plotly.express as px # 그래프 시각화를 위해 plotly 권장 (없으면 pip install plotly)

# 1. 페이지 설정
st.set_page_config(page_title="모멘텀 성적표 분석", layout="wide")

# CSS: 디자인 최적화
st.markdown("""<style>.block-container { padding-top: 2rem !important; } h1 { font-size: 2.2rem !important; font-weight: 800; }</style>""", unsafe_allow_html=True)

st.title("📈 모멘텀 전략 성과 분석")
st.info("아카이브(archive) 폴더에 저장된 '다음달수익률(%)' 데이터를 바탕으로 전략의 실적을 분석합니다.")

# 2. 데이터 로드 함수
def load_performance_data(folder, prefix):
    files = glob.glob(os.path.join(folder, f"{prefix}*.csv"))
    if not files:
        return pd.DataFrame()
    
    perf_list = []
    for f in sorted(files):
        try:
            # 파일명에서 날짜 추출 (예: momentum_2026_03.csv -> 2026-03)
            date_part = os.path.basename(f).replace(prefix, "").replace(".csv", "")
            df = pd.read_csv(f)
            
            # 해당 월의 '다음달수익률(%)' 평균 계산
            if '다음달수익률(%)' in df.columns:
                avg_ret = df['다음달수익률(%)'].mean()
                # 상위 10개 종목만 따로 계산 (집중 투자 시)
                top10_ret = df.head(10)['다음달수익률(%)'].mean()
                
                perf_list.append({
                    '월별': date_part.replace("_", "-"),
                    '전체평균수익률(%)': round(avg_ret, 2),
                    '상위10개평균(%)': round(top10_ret, 2)
                })
        except: continue
        
    res_df = pd.DataFrame(perf_list)
    if not res_df.empty:
        # 누적 수익률 계산 (복리 적용)
        res_df['누적수익률(%)'] = ((1 + res_df['전체평균수익률(%)']/100).cumprod() - 1) * 100
        res_df['누적수익률(%)'] = res_df['누적수익률(%)'].round(2)
    return res_df

# 3. 탭 구성 (한국, 미국, S&P 500)
tabs = st.tabs(["🇰🇷 한국", "🇺🇸 미국(150위)", "🇺🇸 S&P 500"])
market_configs = [
    ("archive", "momentum_"),
    ("archive_us", "momentum_us_"),
    ("archive_sp500", "momentum_sp500_")
]

for tab, (folder, prefix) in zip(tabs, market_configs):
    with tab:
        df_perf = load_performance_data(folder, prefix)
        
        if df_perf.empty:
            st.warning(f"'{folder}' 폴더에 아직 분석할 아카이브 데이터가 없습니다.")
            continue
            
        # 상단 주요 지표 (Metrics)
        col1, col2, col3 = st.columns(3)
        total_ret = df_perf['누적수익률(%)'].iloc[-1]
        avg_monthly = df_perf['전체평균수익률(%)'].mean()
        hit_rate = (df_perf['전체평균수익률(%)'] > 0).mean() * 100
        
        col1.metric("총 누적 수익률", f"{total_ret}%")
        col2.metric("월평균 수익률", f"{avg_monthly:.2f}%")
        col3.metric("승률 (Plus 월 비중)", f"{hit_rate:.1f}%")

        st.markdown("---")
        
        # 그래프 시각화 (누적 수익률 추이)
        st.subheader("🚀 누적 수익률 성장 곡선")
        st.line_chart(df_perf.set_index('월별')['누적수익률(%)'])

        # 월별 수익률 막대 그래프
        st.subheader("📅 월별 성적표")
        fig = px.bar(df_perf, x='월별', y='전체평균수익률(%)', 
                     text='전체평균수익률(%)', color='전체평균수익률(%)',
                     color_continuous_scale=['#0047AB', '#DDDDDD', '#FF4B4B'],
                     title="월별 평균 수익률 (%)")
        fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        st.plotly_chart(fig, use_container_width=True)

        # 상세 데이터 테이블
        st.subheader("📝 세부 기록")
        st.dataframe(df_perf.sort_values('월별', ascending=False), use_container_width=True)
