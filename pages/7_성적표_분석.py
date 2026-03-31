import streamlit as st
import pandas as pd
import os
import glob
import plotly.express as px
import plotly.graph_objects as go

# 1. 페이지 설정
st.set_page_config(page_title="모멘텀 전략 최적화", layout="wide")

# CSS: 디자인 최적화
st.markdown("""<style>.block-container { padding-top: 2rem !important; } h1 { font-size: 2.2rem !important; font-weight: 800; }</style>""", unsafe_allow_html=True)

st.title("🎯 전략 성과 분석 및 포트폴리오 가이드")

# 2. 데이터 로드 및 다중 포트폴리오 계산 함수
def load_multi_performance(folder, prefix):
    files = glob.glob(os.path.join(folder, f"{prefix}*.csv"))
    if not files: return pd.DataFrame(), pd.DataFrame()
    
    perf_list, all_stocks_pool = [], []
    
    for f in sorted(files):
        try:
            date_part = os.path.basename(f).replace(prefix, "").replace(".csv", "").replace("_", "-")
            df = pd.read_csv(f)
            if '다음달수익률(%)' in df.columns:
                temp_df = df.copy(); temp_df['투자월'] = date_part
                all_stocks_pool.append(temp_df)
                
                ret_10 = df.head(10)['다음달수익률(%)'].mean()
                ret_20 = df.head(20)['다음달수익률(%)'].mean()
                ret_30 = df.head(30)['다음달수익률(%)'].mean()
                
                perf_list.append({'월별': date_part, 'Top10(%)': round(ret_10, 2), 'Top20(%)': round(ret_20, 2), 'Top30(%)': round(ret_30, 2)})
        except: continue
        
    res_df = pd.DataFrame(perf_list)
    hall_of_fame = pd.concat(all_stocks_pool) if all_stocks_pool else pd.DataFrame()
    
    if not res_df.empty:
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
            
        # --- (1) 누적 수익률 비교 ---
        st.subheader("📈 포트폴리오 규모별 성장 곡선")
        fig_line = go.Figure()
        colors = {'Top10': '#FF4B4B', 'Top20': '#0047AB', 'Top30': '#666666'}
        for key in ['Top10', 'Top20', 'Top30']:
            fig_line.add_trace(go.Scatter(x=df_perf['월별'], y=df_perf[f'누적_{key}(%)'], name=f'{key} 집중투자', line=dict(width=3 if key=='Top10' else 2, color=colors[key])))
        st.plotly_chart(fig_line, use_container_width=True)

        # --- (2) 수익률 분포 상세 분석 ---
        st.markdown("---")
        st.subheader("📊 수익률 분포 상세 (전체 종목 기준)")
        
        c1, c2 = st.columns([1.2, 1])
        with c1:
            fig_hist = px.histogram(df_hall, x='다음달수익률(%)', nbins=40, color_discrete_sequence=['#0047AB'], title="수익률 히스토그램")
            st.plotly_chart(fig_hist, use_container_width=True)
            
        with c2:
            st.write("**[수익률 구간별 요약 표]**")
            # 💡 수익률 구간 나누기 (Bins)
            bins = [-float('inf'), -20, -10, -5, 0, 5, 10, 20, float('inf')]
            labels = ['-20% 미만', '-20% ~ -10%', '-10% ~ -5%', '-5% ~ 0%', '0% ~ 5%', '5% ~ 10%', '10% ~ 20%', '20% 이상']
            df_hall['구간'] = pd.cut(df_hall['다음달수익률(%)'], bins=bins, labels=labels)
            
            dist_df = df_hall['구간'].value_counts().reindex(labels).reset_index()
            dist_df.columns = ['수익률 구간', '종목 수']
            dist_df['비중(%)'] = (dist_df['종목 수'] / dist_df['종목 수'].sum() * 100).round(1)
            
            # 표 스타일 적용 (수익 구간 강조)
            st.table(dist_df.assign(**{'비중(%)': dist_df['비중(%)'].map('{:.1f}%'.format)}))

        # --- (3) 포트폴리오 최적화 제안 (가이드) ---
        st.markdown("---")
        st.subheader("💡 투자 성향별 최적 포트폴리오 제안")
        
        # 성과 지표 계산
        metrics = []
        for key in ['Top10', 'Top20', 'Top30']:
            ret_col = f'{key}(%)'
            cum_ret = df_perf[f'누적_{key}(%)'].iloc[-1]
            volatility = df_perf[ret_col].std() # 변동성
            mdd = (df_perf[f'누적_{key}(%)'] - df_perf[f'누적_{key}(%)'].cummax()).min() # 최대 하락폭
            metrics.append({'전략': key, '누적수익': cum_ret, '변동성': volatility, 'MDD': mdd})
        
        m_df = pd.DataFrame(metrics)
        best_ret_strat = m_df.loc[m_df['누적수익'].idxmax(), '전략']
        best_stab_strat = m_df.loc[m_df['변동성'].idxmin(), '전략']

        g1, g2 = st.columns(2)
        with g1:
            st.success(f"🚀 **수익 극대화형 추천: {best_ret_strat}**")
            st.write(f"과거 데이터상 가장 높은 누적 수익({m_df['누적수익'].max():.1f}%)을 기록했습니다. 하락장에서의 변동성을 견딜 수 있는 공격적인 투자자에게 적합합니다.")
        with g2:
            st.info(f"🛡️ **안정 추구형 추천: {best_stab_strat}**")
            st.write(f"변동성이 {m_df['변동성'].min():.2f}%로 가장 낮아 심리적으로 편안한 매매가 가능합니다. 큰 손실 없이 꾸준한 우상향을 원하는 분께 추천합니다.")

        # 상세 비교 표
        st.table(m_df.rename(columns={'누적수익': '최종 누적수익률(%)', '변동성': '월간 수익률 변동성(%)', 'MDD': '최대 하락폭(MDD, %)'}).assign(
            **{c: m_df[c].map('{:,.2f}'.format) for c in m_df.columns if c != '전략'}
        ))
