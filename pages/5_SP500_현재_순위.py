import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="S&P 500 현재 순위", layout="wide")

# CSS: 레이아웃 초밀착 및 가독성 설정
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem !important; }
    h1 { font-size: 1.8rem !important; font-weight: 800; margin-bottom: 10px; }
    [data-testid="stDataFrame"] { margin-top: -10px; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { 
        height: 40px; white-space: pre-wrap; background-color: #f0f2f6; 
        border-radius: 5px; padding: 0px 20px;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🚀 S&P 500 현재 모멘텀 순위")

# 1. 대통령 집권 연차 필터 (V2 규칙 적용)
def get_pres_status():
    now = datetime.now()
    year, month = now.year, now.month
    cycle_year = (year - 2016) % 8
    if cycle_year == 0: cycle_year = 8
    
    exclusion_rules = {
        1: [2, 3, 8], 2: [1, 4, 6, 9], 3: [9], 4: [10],
        5: [2, 3, 8], 6: [7, 8, 9], 7: [9], 8: [1, 2, 8, 9]
    }
    is_excluded = month in exclusion_rules.get(cycle_year, [])
    color = "🔴 현재는 현금 비중을 늘려야 하는 달입니다 (주의)" if is_excluded else "🟢 현재는 적극적으로 투자하기 좋은 달입니다 (양호)"
    return cycle_year, color

cy, status = get_pres_status()
st.info(f"🇺🇸 **미국 집권 {cy}년차** | 필터 상태: **{status}**")

# 2. 데이터 수집 및 계산 함수 (캐시 적용)
@st.cache_data(ttl=3600) # 1시간마다 자동 갱신
def get_sp500_data():
    df_sp500 = fdr.StockListing('S&P500')
    # 실제 운영 시 속도를 위해 상위 300~500개 조절 가능
    symbols = df_sp500['Symbol'].tolist()
    
    monthly_data = []
    daily_data = []
    
    end_dt = datetime.now()
    start_dt = end_dt - pd.DateOffset(months=15)
    
    # 진행 바
    p_bar = st.progress(0, text="S&P 500 종목 분석 중...")
    
    for i, sym in enumerate(symbols):
        try:
            df = fdr.DataReader(sym, start_dt, end_dt)
            if len(df) < 250: continue
            
            curr_p = df['Close'].iloc[-1]
            prev_p = df['Close'].iloc[-2]
            
            # --- 월별 모멘텀 계산 ---
            def get_m_ret(m):
                past_p = df['Close'].iloc[-1 * (m * 21)]
                return (curr_p - past_p) / past_p * 100
            
            r1, r3, r6, r12 = get_m_ret(1), get_m_ret(3), get_m_ret(6), get_m_ret(12)
            m_score = (r1*-0.2) + (r3*0.8) + (r6*0.5) + (r12*0.2)
            
            monthly_data.append({
                'Symbol': sym, 'Name': df_sp500[df_sp500['Symbol']==sym]['Name'].values[0],
                'Price': curr_p, 'Score': round(m_score, 2),
                '1M': round(r1, 1), '3M': round(r3, 1), '6M': round(r6, 1), '12M': round(r12, 1)
            })
            
            # --- 일별 모멘텀 계산 ---
            def get_d_ret(d):
                past_p = df['Close'].iloc[-1 - d]
                return (curr_p - past_p) / past_p * 100
            
            d1, d3, d5 = get_d_ret(1), get_d_ret(3), get_d_ret(5)
            d_score = (d1 * 1.0) + (d3 * 0.5) + (d5 * 0.3)
            
            daily_data.append({
                'Symbol': sym, 'Name': df_sp500[df_sp500['Symbol']==sym]['Name'].values[0],
                'Price': curr_p, 'Score': round(d_score, 2),
                '1D': round(d1, 1), '3D': round(d3, 1), '5D': round(d5, 1)
            })
        except: continue
        if i % 50 == 0: p_bar.progress((i+1)/len(symbols))

    p_bar.empty()
    
    m_df = pd.DataFrame(monthly_data).sort_values('Score', ascending=False)
    m_df.insert(0, 'Rank', range(1, len(m_df)+1))
    
    d_df = pd.DataFrame(daily_data).sort_values('Score', ascending=False)
    d_df.insert(0, 'Rank', range(1, len(d_df)+1))
    
    return m_df, d_df

# 3. 탭 구성
tab_m, tab_d = st.tabs(["📅 월별 순위 (중장기)", "⏱️ 일별 순위 (단기)"])

m_res, d_res = get_sp500_data()

def style_val(val):
    if val > 0: return 'color: #FF4B4B; font-weight: bold;'
    elif val < 0: return 'color: #3182CE; font-weight: bold;'
    return ''

with tab_m:
    st.dataframe(
        m_res.style.map(style_val, subset=['1M', '3M', '6M', '12M']),
        use_container_width=True, height=600, hide_index=True,
        column_config={"Symbol": "티커", "Price": st.column_config.NumberColumn(format="$ %.2f")}
    )

with tab_d:
    st.dataframe(
        d_res.style.map(style_val, subset=['1D', '3D', '5D']),
        use_container_width=True, height=600, hide_index=True,
        column_config={"Symbol": "티커", "Price": st.column_config.NumberColumn(format="$ %.2f")}
    )
