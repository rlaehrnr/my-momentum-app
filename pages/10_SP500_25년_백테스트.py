import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import numpy as np

# --- [1. 페이지 설정] ---
st.set_page_config(page_title="S&P 500 25년 백테스트", layout="wide")

st.markdown("""
    <style>
    .block-container { padding-top: 2.5rem !important; padding-bottom: 1rem !important; }
    h1 { font-size: 2.2rem !important; font-weight: 800; margin-bottom: 10px; }
    .settings-box { background-color: #f8fafc; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

st.title("🚀 S&P 500 25년 퀀트 백테스트 (2000~2025)")
st.markdown("선생님께서 추출하신 **25년 치 S&P 500 수익률 데이터**를 활용해, 닷컴 버블과 금융위기를 모두 거친 '진짜 장기 백테스트'를 수행합니다.")

# --- [2. 데이터 로드 및 전처리] ---
@st.cache_data(show_spinner=False)
def load_quant_data():
    df = pd.read_csv('sp500_퀀트데이터_2000_2025_Final_Cleaned.csv')
    df['Date'] = pd.to_datetime(df['Date'])
    df['YearMonth'] = df['Date'].dt.to_period('M').astype(str)
    return df

@st.cache_data(show_spinner=False)
def get_market_timing():
    sp500 = yf.Ticker('^GSPC').history(start='1999-01-01', end='2025-12-31')
    sp500.index = sp500.index.tz_localize(None)
    sp500['200MA'] = sp500['Close'].rolling(200).mean()
    
    timing_df = sp500.resample('ME').last()
    timing_df['YearMonth'] = timing_df.index.to_period('M').astype(str)
    timing_df['is_bad_market'] = timing_df['Close'] < timing_df['200MA']
    return timing_df.set_index('YearMonth')

with st.spinner("25년 치 데이터를 불러오는 중입니다..."):
    df = load_quant_data()
    timing_df = get_market_timing()

# --- [3. 시뮬레이션 설정 UI] ---
st.markdown("<div class='settings-box'>", unsafe_allow_html=True)
st.markdown("##### ⚙️ 시뮬레이션 설정 (옵션을 변경하면 차트가 즉시 25년 치를 재계산합니다)")
c1, c2, c3 = st.columns([1, 1, 1.2])
with c1:
    top_n_1 = st.slider("🔥 12M & 6M 강세 (매수 종목 수)", 1, 20, 5)
with c2:
    top_n_2 = st.slider("⚡ 6M & 3M 강세 (매수 종목 수)", 1, 20, 5)
with c3:
    st.markdown("<div style='margin-top:35px;'></div>", unsafe_allow_html=True)
    apply_timing = st.checkbox("🛑 마켓타이밍 적용 (S&P 500 200일선 이탈 시 현금 100%)", value=True)
st.markdown("</div>", unsafe_allow_html=True)

# --- [4. 백테스트 엔진 구동] ---
with st.spinner("25년 치 12만 개 이상의 데이터를 시뮬레이션 중입니다... 🚀"):
    months = sorted(df['YearMonth'].unique())
    
    records = []
    for m in months:
        monthly_data = df[df['YearMonth'] == m]
        
        is_bad = False
        if apply_timing and m in timing_df.index:
            is_bad = timing_df.loc[m, 'is_bad_market']
        
        mult = 0.0 if is_bad else 1.0
        is_invested = mult > 0.0
        
        top_12m = monthly_data.sort_values('Past_12M_Return(%)', ascending=False).head(top_n_1 * 3)
        top_6m = monthly_data.sort_values('Past_6M_Return(%)', ascending=False).head(top_n_1 * 3)
        overlap_1 = top_12m[top_12m['Ticker'].isin(top_6m['Ticker'])].sort_values('Past_6M_Return(%)', ascending=False).head(top_n_1)
        
        top_6m_sub = monthly_data.sort_values('Past_6M_Return(%)', ascending=False).head(top_n_2 * 3)
        top_3m = monthly_data.sort_values('Past_3M_Return(%)', ascending=False).head(top_n_2 * 3)
        overlap_2 = top_6m_sub[top_6m_sub['Ticker'].isin(top_3m['Ticker'])].sort_values('Past_3M_Return(%)', ascending=False).head(top_n_2)
        
        ret_1 = (overlap_1['Forward_1M_Return(%)'].mean() * mult) if not overlap_1.empty else 0.0
        ret_2 = (overlap_2['Forward_1M_Return(%)'].mean() * mult) if not overlap_2.empty else 0.0
        
        combined_tickers = list(set(overlap_1['Ticker'].tolist() + overlap_2['Ticker'].tolist()))
        combined_data = monthly_data[monthly_data['Ticker'].isin(combined_tickers)]
        ret_combined = (combined_data['Forward_1M_Return(%)'].mean() * mult) if not combined_data.empty else 0.0
        
        records.append({
            'YearMonth': m,
            'invested': is_invested,
            f'🔥 12M & 6M (Top {top_n_1})': ret_1,
            f'⚡ 6M & 3M (Top {top_n_2})': ret_2,
            '앙상블 (전략 50:50)': (ret_1 + ret_2) / 2,
            '통합 (모든종목 1/N)': ret_combined
        })
        
    df_res = pd.DataFrame(records)
    
    strategy_cols = [c for c in df_res.columns if c not in ['YearMonth', 'invested']]
    df_cum = (1 + df_res.set_index('YearMonth')[strategy_cols] / 100).cumprod() * 100
    
    first_month = pd.to_datetime(df_res['YearMonth'].iloc[0]) - pd.DateOffset(months=1)
    first_m_str = first_month.strftime('%Y-%m')
    df_cum.loc[first_m_str] = 100
    df_cum = df_cum.sort_index()

# --- [5. 결과 시각화] ---
st.markdown("### 📈 2000년 ~ 2025년 누적 자산 성장 곡선 (Log Scale)")
st.info("💡 25년 장기 투자는 복리 효과로 인해 후반부가 너무 가파르게 보이므로, **수익률의 진정한 변동성을 볼 수 있는 '로그 스케일(Log Scale)'이 적용**되어 있습니다. 2008년 금융위기 방어력을 확인해 보세요!")

df_melt = df_cum.reset_index().melt(id_vars='YearMonth', var_name='전략', value_name='누적수익률')
fig = px.line(df_melt, x='YearMonth', y='누적수익률', color='전략', log_y=True)
fig.update_layout(
    hovermode="x unified",
    dragmode="pan", 
    xaxis_title="투자 기준 월",
    yaxis_title="누적 자산 (초기 자산=100, 로그스케일)",
    legend_title_text="투자 전략",
    margin=dict(l=0, r=0, t=20, b=0)
)
fig.update_xaxes(fixedrange=False)
fig.update_yaxes(fixedrange=False)
fig.update_traces(hovertemplate="<b>%{data.name}</b><br>누적자산: %{y:.1f}<extra></extra>")
st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})

# --- [6. 핵심 통계] ---
st.markdown("### 📊 전략별 25년 핵심 통계")

stats = []
total_months = len(df_res)
invested_months = df_res['invested'].sum()
invest_ratio = (invested_months / total_months) * 100 if total_months > 0 else 0

for col in strategy_cols:
    final_val = df_cum[col].iloc[-1]
    total_ret = final_val - 100
    years = total_months / 12
    
    # 💡 [핵심 수정] CAGR 계산 시 음수 처리 (NaN 방지)
    # 초기 자본이 100이므로, final_val이 0 이하면 -100% (파산) 처리
    if final_val <= 0:
        cagr = -100.0
    else:
        cagr = ((final_val / 100) ** (1 / years) - 1) * 100
    
    if invested_months > 0:
        win_months = (df_res.loc[df_res['invested'], col] > 0).sum()
        win_rate = (win_months / invested_months) * 100
        avg_ret = df_res.loc[df_res['invested'], col].mean()
    else:
        win_rate = avg_ret = 0.0
        
    roll_max = df_cum[col].cummax()
    drawdown = (df_cum[col] / roll_max) - 1.0
    mdd = drawdown.min() * 100
    
    stats.append({
        "전략명": col,
        "CAGR (연평균)": f"{cagr:.1f}%",
        "총 누적수익률": f"{total_ret:,.0f}%",
        "MDD (최대낙폭)": f"{mdd:.1f}%",
        "투자월 비율": f"{invest_ratio:.1f}% ({invested_months}/{total_months}개월)", 
        "월별 승률": f"{win_rate:.1f}% ({win_months}승)", 
        "평균 수익률(투자월)": f"{avg_ret:.2f}%"
    })
    
df_stats = pd.DataFrame(stats)

def style_stats(x):
    if isinstance(x, str) and '%' in x:
        if '-' in x: return 'color: #1976D2; font-weight:bold;'
        elif x != '0.0%': return 'color: #D32F2F; font-weight:bold;'
    return ''
    
try:
    styled_stats = df_stats.style.map(style_stats, subset=['CAGR (연평균)', '총 누적수익률', 'MDD (최대낙폭)'])
except AttributeError:
    styled_stats = df_stats.style.applymap(style_stats, subset=['CAGR (연평균)', '총 누적수익률', 'MDD (최대낙폭)'])
    
st.dataframe(styled_stats, use_container_width=True, hide_index=True)

with st.expander("📝 25년 (300개월) 월별 수익률 상세 기록 열어보기"):
    display_df = df_res.drop(columns=['invested']).set_index('YearMonth')
    st.dataframe(display_df.style.format("{:.2f}%"), use_container_width=True)
