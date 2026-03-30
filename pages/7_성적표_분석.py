import streamlit as st
import pandas as pd
import os
import glob
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="TOP 10 성적표 분석", layout="wide")

# CSS: 디자인 최적화
st.markdown("""<style>.block-container { padding-top: 2rem !important; } h1 { font-size: 2.2rem !important; font-weight: 800; }</style>""", unsafe_allow_html=True)

st.title("🏆 TOP 10 모멘텀 성과 분석")
st.info("각 월별 모멘텀 스코어 **상위 10개 종목**에 집중 투자했을 때의 가상 수익률을 분석합니다.")

# 2. 데이터 로드 및 TOP 10 계산 함수
def load_top10_performance(folder, prefix):
    files = glob.glob(os.path.join(folder, f"{prefix}*.csv"))
    if not files:
        return pd.DataFrame()
    
    perf_list = []
    # 파일명 정렬 (날짜 순서대로)
    for f in sorted(files):
        try:
            # 파일명에서 날짜 추출 (예: 2026_03)
            date_part = os.path.basename(f).replace(prefix, "").replace(".csv", "")
            df = pd.read_csv(f)
            
            # 💡 [핵심] 상위 10개만 추출하여 수익률 계산
            if '다음달수익률(%)' in df.columns:
                top10_df = df.head(10) # 모멘텀 스코어 내림차순 상위 10개
                avg_ret = top10_df['다음달수익률(%)'].mean()
                
                # 해당 월의 베스트 종목 찾기
                best_stock = top10_df.loc[top10_df['다음달수익률(%)'].idxmax()]
                
                perf_list.append({
                    '월별': date_part.replace("_", "-"),
                    'TOP10_평균수익률(%)': round(avg_ret, 2),
                    '최고수익종목': best_stock['종목명'],
                    '최고수익률(%)': best_stock['다음달수익률(%)']
                })
        except: continue
        
    res_df = pd.DataFrame(perf_list)
    if not res_df.empty:
        # 누적 수익률 계산 (복리 적용)
        res_df['누적수익률(%)'] = ((1 + res_df['TOP10_평균수익률(%)']/100).cumprod() - 1) * 100
        res_df['누적수익률(%)'] = res_df['누적수익률(%)'].round(2)
    return res_df

# 3. 마켓별 분석 탭
tabs = st.tabs(["🇰🇷 한국", "🇺🇸 미국(150위)", "🇺🇸 S&P 500"])
configs = [
    ("archive", "momentum_"),
    ("archive_us", "momentum_us_"),
    ("archive_sp500", "momentum_sp500_")
]

for tab, (folder, prefix) in zip(tabs, configs):
    with tab:
        df_perf = load_top10_performance(folder, prefix)
        
        if df_perf.empty:
            st.warning(f"'{folder}' 폴더에 분석할 TOP 10 데이터가 없습니다. monthly 스크립트를 먼저 실행해주세요.")
            continue
            
        # 상단 주요 지표
        m1, m2, m3 = st.columns(3)
        total_ret = df_perf['누적수익률(%)'].iloc[-1]
        win_rate = (df_perf['TOP10_평균수익률(%)'] > 0).mean() * 100
        best_month = df_perf.loc[df_perf['TOP10_평균수익률(%)'].idxmax()]
        
        m1.metric("총 누적 수익률", f"{total_ret}%")
        m2.metric("월간 승률", f"{win_rate:.1f}%")
        m3.metric("최고의 달", f"{best_month['월별']}", f"{best_month['TOP10_평균수익률(%)']}%")

        st.markdown("---")
        
        # 1. 누적 수익률 차트
        st.subheader("📈 TOP 10 누적 수익률 곡선")
        st.line_chart(df_perf.set_index('월별')['누적수익률(%)'])

        # 2. 월별 수익률 막대 차트
        st.subheader("📅 월별 성적 (TOP 10 평균)")
        fig = px.bar(df_perf, x='월별', y='TOP10_평균수익률(%)', 
                     color='TOP10_평균수익률(%)', 
                     color_continuous_scale='RdBu_r', # 빨강(하락)/파랑(상승)
                     text_auto='.1f')
        st.plotly_chart(fig, use_container_width=True)

        # 3. 상세 기록 테이블
        st.subheader("📋 상세 기록")
        st.dataframe(
            df_perf.sort_values('월별', ascending=False), 
            use_container_width=True,
            column_config={
                "월별": "투자 월",
                "TOP10_평균수익률(%)": st.column_config.NumberColumn("평균 수익률", format="%.2f%%"),
                "누적수익률(%)": st.column_config.NumberColumn("누적 수익률", format="%.2f%%"),
                "최고수익률(%)": st.column_config.NumberColumn("최고 종목 수익률", format="%.1f%%")
            }
        )
