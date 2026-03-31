import streamlit as st
import pandas as pd
import os
import glob
import plotly.express as px
import plotly.graph_objects as go

# 1. 페이지 설정
st.set_page_config(page_title="모멘텀 정밀 분석", layout="wide")

# CSS: 디자인 최적화
st.markdown("""<style>.block-container { padding-top: 2rem !important; } h1 { font-size: 2.2rem !important; font-weight: 800; }</style>""", unsafe_allow_html=True)

st.title("📊 모멘텀 포트폴리오 정밀 비교")
st.info("TOP 10, 20, 30 규모별 성과와 역대 최고 수익률 종목들을 분석합니다.")

# 2. 데이터 로드 및 다중 포트폴리오 계산 함수
def load_multi_performance(folder, prefix):
    files = glob.glob(os.path.join(folder, f"{prefix}*.csv"))
    if not files:
        return pd.DataFrame(), pd.DataFrame()
    
    perf_list = []
    all_stocks_pool = [] # 역대 최고 수익률 종목을 찾기 위한 전체 데이터 풀
    
    for f in sorted(files):
        try:
            date_part = os.path.basename(f).replace(prefix, "").replace(".csv", "").replace("_", "-")
            df = pd.read_csv(f)
            
            if '다음달수익률(%)' in df.columns:
                # 역대 최고 수익률 계산을 위해 데이터 수집
                temp_df = df.copy()
                temp_df['투자월'] = date_part
                all_stocks_pool.append(temp_df)
                
                # 규모별 평균 수익률 계산
                ret_10 = df.head(10)['다음달수익률(%)'].mean()
                ret_20 = df.head(20)['다음달수익률(%)'].mean()
                ret_30 = df.head(30)['다음달수익률(%)'].mean()
                
                perf_list.append({
                    '월별': date_part,
                    'Top10(%)': round(ret_10, 2),
                    'Top20(%)': round(ret_20, 2),
                    'Top30(%)': round(ret_30, 2)
                })
        except: continue
        
    res_df = pd.DataFrame(perf_list)
    hall_of_fame = pd.concat(all_stocks_pool) if all_stocks_pool else pd.DataFrame()
    
    if not res_df.empty:
        # 누적 수익률(복리) 계산
        for col in ['Top10(%)', 'Top20(%)', 'Top30(%)']:
            res_df[f'누적_{col}'] = ((1 + res_df[col]/100).cumprod() - 1) * 100
            
    return res_df, hall_of_fame

# 3. 마켓별 분석 탭
tabs = st.tabs(["🇰🇷 한국", "🇺🇸 미국(150위)", "🇺🇸 S&P 500"])
configs = [("archive", "momentum_"), ("archive_us", "momentum_us_"), ("archive_sp500", "momentum_sp500_")]

for tab, (folder, prefix) in zip(tabs, configs):
    with tab:
        df_perf, df_hall = load_multi_performance(folder, prefix)
        
        if df_perf.empty:
            st.warning(f"'{folder}' 폴더에 분석 데이터가 없습니다.")
            continue
            
        # --- (1) 규모별 누적 수익률 비교 그래프 ---
        st.subheader("📈 포트폴리오 규모별 누적 수익률 비교")
        
        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(x=df_perf['월별'], y=df_perf['누적_Top10(%)'], name='Top 10 집중투자', line=dict(width=4, color='#FF4B4B')))
        fig_line.add_trace(go.Scatter(x=df_perf['월별'], y=df_perf['누적_Top20(%)'], name='Top 20 표준투자', line=dict(width=2, color='#0047AB')))
        fig_line.add_trace(go.Scatter(x=df_perf['월별'], y=df_perf['누적_Top30(%)'], name='Top 30 분산투자', line=dict(width=2, color='#666666', dash='dot')))
        
        fig_line.update_layout(hovermode='x unified', yaxis_title="누적 수익률 (%)")
        st.plotly_chart(fig_line, use_container_width=True)

        # --- (2) 역대급 효자 종목 (Hall of Fame) ---
        st.markdown("---")
        st.subheader("🏆 역대 최고 수익률 종목 TOP 10 (Hall of Fame)")
        st.write("아카이브된 모든 데이터를 통틀어 단일 월에 가장 높은 수익을 기록했던 '전설의 종목'들입니다.")
        
        if not df_hall.empty:
            # 다음달수익률 기준 내림차순 정렬 후 상위 10개
            best_10 = df_hall.sort_values('다음달수익률(%)', ascending=False).head(10)
            
            st.table(best_10[['투자월', '종목명', '종목코드', '모멘텀스코어', '다음달수익률(%)']].assign(
                **{'다음달수익률(%)': best_10['다음달수익률(%)'].map('{:+.1f}%'.format)}
            ).reset_index(drop=True))
            
            # 최고 수익률 분포 시각화
            fig_hist = px.histogram(df_hall, x='다음달수익률(%)', nbins=50, 
                                   title="전체 종목별 수익률 분포 (어떤 수익률이 가장 많이 나왔나?)",
                                   color_discrete_sequence=['#0047AB'])
            st.plotly_chart(fig_hist, use_container_width=True)

        # --- (3) 상세 수치 비교 ---
        st.markdown("---")
        st.subheader("📋 포트폴리오별 상세 성적표")
        
        summary_data = []
        for col in ['Top10(%)', 'Top20(%)', 'Top30(%)']:
            summary_data.append({
                '구분': col.replace('(%)', ''),
                '최종 누적 수익률': f"{df_perf[f'누적_{col}'].iloc[-1]:.2f}%",
                '월평균 수익률': f"{df_perf[col].mean():.2f}%",
                '최악의 달': f"{df_perf[col].min():.1f}%",
                '승률(Plus 월)': f"{(df_perf[col] > 0).mean()*100:.1f}%"
            })
        st.table(pd.DataFrame(summary_data))
