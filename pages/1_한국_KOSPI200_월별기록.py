import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os

# --- [1. 페이지 설정] ---
st.set_page_config(page_title="KOSPI 200 월별 기록", layout="wide")
st.markdown("""
<style>
    .block-container { padding-top: 2rem !important; }
    .main-title { font-size: 1.6rem !important; font-weight: bold; margin-bottom: 1rem; }
</style>
""", unsafe_allow_html=True)

# --- [2. 스타일 및 헬퍼 함수] ---
def apply_k200_styling(row, common_codes=None):
    styles = [''] * len(row)
    if '다음달수익률(%)' in row.index:
        col_idx = row.index.get_loc('다음달수익률(%)')
        val = row['다음달수익률(%)']
        if pd.notna(val) and val > 0:
            styles[col_idx] = 'color: #D32F2F; font-weight: bold;'
        elif pd.notna(val) and val < 0:
            styles[col_idx] = 'color: #1976D2; font-weight: bold;'
            
    if common_codes and '종목코드' in row.index and row['종목코드'] in common_codes:
        if '종목명_L' in row.index:
            styles[row.index.get_loc('종목명_L')] = 'background-color: #FFF59D; color: #D84315; font-weight: bold;'
    return styles

@st.cache_data(ttl=3600)
def get_idx_kr(target_date_str):
    target_date = pd.to_datetime(target_date_str)
    try:
        df = fdr.DataReader('KS11', target_date - pd.DateOffset(months=18), target_date)
        if df.empty: return 0.0, 0.0
        
        curr_val = df.loc[df.index <= target_date]['Close'].iloc[-1]
        last_date = df.index[df.index <= target_date][-1]
        def get_ret(m):
            ref = (last_date.replace(day=1) - pd.DateOffset(months=m-1)) - timedelta(days=1)
            p_df = df[df.index <= ref]
            return round(((curr_val / p_df['Close'].iloc[-1]) - 1) * 100, 1) if not p_df.empty else 0.0
        return get_ret(1), get_ret(3)
    except: 
        return 0.0, 0.0

@st.cache_data
def load_historical_data(filepath):
    df = pd.read_csv(filepath)
    df['종목코드'] = df['종목코드'].astype(str).str.zfill(6)
    df['시가총액(억)'] = (df['시가총액'] / 100000000).fillna(0).astype(int)
    return df

# 💡 [핵심 수정] Top 5, Top 10 선정 기준을 12개월 수익률 내림차순으로 변경
def get_perf_html(title, df):
    if df.empty:
        return f"### {title} <span style='font-size: 15px; color: gray; font-weight: normal;'>(해당 종목 없음)</span>"
    
    # 1. 모두 매수 시 평균
    all_avg = df['다음달수익률(%)'].mean()
    
    # 2. 12개월(%) 기준으로 내림차순 정렬 후 Top 5, Top 10 추출
    df_sorted = df.sort_values(by='12개월(%)', ascending=False)
    top5_avg = df_sorted.head(5)['다음달수익률(%)'].mean()
    top10_avg = df_sorted.head(10)['다음달수익률(%)'].mean()
    
    def format_val(v):
        if pd.isna(v): return "0.00%", "gray"
        color = "#D32F2F" if v > 0 else ("#1976D2" if v < 0 else "#555")
        return f"{v:+.2f}%", color
        
    a_str, a_col = format_val(all_avg)
    t5_str, t5_col = format_val(top5_avg)
    t10_str, t10_col = format_val(top10_avg)
    
    return f"### {title} <span style='font-size: 15px; font-weight: normal; color: #666;'> &nbsp; | &nbsp; 📊 다음달 성적 ➔ Top5(12M순): <span style='color:{t5_col}; font-weight:bold;'>{t5_str}</span> &nbsp; Top10(12M순): <span style='color:{t10_col}; font-weight:bold;'>{t10_str}</span> &nbsp; 모두매수: <span style='color:{a_col}; font-weight:bold;'>{a_str}</span></span>"

# --- [3. 메인 로직] ---
f_csv = 'data/한국 코스피 2014년부터 200위까지 자료.csv'

if not os.path.exists(f_csv):
    st.error(f"데이터 파일이 없습니다: {f_csv}")
    st.stop()

df_all = load_historical_data(f_csv)

dates = sorted(df_all['기준일'].unique(), reverse=True)

# 💡 글씨 잘림 방지를 위해 라벨을 마크다운으로 따로 뺐습니다.
st.markdown("<h4 style='margin-bottom: 5px;'>📅 조회 기준일(월말) 선택</h4>", unsafe_allow_html=True)
selected_date = st.selectbox("조회일", dates, label_visibility="collapsed")

st.markdown(f'<p class="main-title">🎯 KOSPI 200 과거 기록 분석 (기준일: {selected_date})</p>', unsafe_allow_html=True)

df_k200 = df_all[df_all['기준일'] == selected_date].copy()
df_k200['통합티커'] = "KOSPI:" + df_k200['종목코드']
df_k200['종목명_L'] = df_k200.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드']}#{r['종목명']}", axis=1)

df_k200 = df_k200.sort_values(by='시가총액', ascending=False).head(200)
df_k200['시총순위'] = range(1, len(df_k200) + 1)
df_k200 = df_k200.set_index('시총순위')

kospi_1m, kospi_3m = get_idx_kr(selected_date)

neg_1m_cnt = (df_k200['1개월(%)'] < 0).sum()
neg_3m_cnt = (df_k200['3개월(%)'] < 0).sum()

if neg_1m_cnt >= 100 and neg_3m_cnt >= 100:
    invest_status, box_color, text_color = "🛑 투자 중지", "#FFEBEE", "#C62828"
else:
    invest_status, box_color, text_color = "✅ 투자 진행", "#E8F5E9", "#2E7D32"

st.markdown("<br>", unsafe_allow_html=True)
col1, col2, col3, col4, col5 = st.columns([1, 1, 1.2, 1.2, 1.5])

with col1: st.metric(label="📈 KOSPI 1M", value=f"{kospi_1m}%")
with col2: st.metric(label="📈 KOSPI 3M", value=f"{kospi_3m}%")
with col3: st.metric(label="📉 1개월 하락 종목", value=f"{neg_1m_cnt}개")
with col4: st.metric(label="📉 3개월 하락 종목", value=f"{neg_3m_cnt}개")
with col5:
    st.markdown(f"""
    <div style="background-color: {box_color}; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid {text_color};">
        <p style="margin: 0; font-size: 14px; color: {text_color}; font-weight: bold;">당시 최종 판단 지표</p>
        <h3 style="margin: 5px 0 0 0; color: {text_color};">{invest_status}</h3>
    </div>
    """, unsafe_allow_html=True)
    
st.markdown("<br><hr>", unsafe_allow_html=True)

q30 = {c: df_k200[c].quantile(0.7) for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']}
t10_1m = df_k200['1개월(%)'].quantile(0.9)

cond_perf = (df_k200['1개월(%)']>=q30['1개월(%)'])&(df_k200['3개월(%)']>=q30['3개월(%)'])&(df_k200['6개월(%)']>=q30['6개월(%)'])&(df_k200['12개월(%)']>=q30['12개월(%)']) & \
            (df_k200['1개월(%)']>0)&(df_k200['3개월(%)']>0)&(df_k200['6개월(%)']>0)&(df_k200['12개월(%)']>0)
df_perf = df_k200[cond_perf].copy()
df_spec = df_k200[(df_k200['12개월(%)']>=q30['12개월(%)']) & (df_k200['1개월(%)']>=t10_1m)].copy()

common_codes = set(df_perf['종목코드']).intersection(set(df_spec['종목코드']))
df_common = df_k200[df_k200['종목코드'].isin(common_codes)].copy()

main_cfg = {
    "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), 
    "시가총액(억)": st.column_config.NumberColumn("시가총액(억)", format="%,d"),
    "1개월(%)": st.column_config.NumberColumn(format="%.1f"), 
    "3개월(%)": st.column_config.NumberColumn(format="%.1f"), 
    "6개월(%)": st.column_config.NumberColumn(format="%.1f"), 
    "12개월(%)": st.column_config.NumberColumn(format="%.1f"),
    "다음달수익률(%)": st.column_config.NumberColumn("다음달수익률(%)", format="%.2f") 
}

col1, col2 = st.columns(2)
with col1:
    st.markdown(get_perf_html("🔥 퍼펙트 상승", df_perf), unsafe_allow_html=True)
    st.dataframe(df_perf.style.apply(apply_k200_styling, common_codes=common_codes, axis=1), 
                 use_container_width=True, 
                 column_order=['통합티커', '종목명_L', '시가총액(억)', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '다음달수익률(%)'], 
                 column_config=main_cfg)
with col2:
    st.markdown(get_perf_html("🚀 장기 주도 & 단기 급등", df_spec), unsafe_allow_html=True)
    st.dataframe(df_spec.style.apply(apply_k200_styling, common_codes=common_codes, axis=1), 
                 use_container_width=True, 
                 column_order=['통합티커', '종목명_L', '시가총액(억)', '1개월(%)', '12개월(%)', '다음달수익률(%)'], 
                 column_config=main_cfg)

st.markdown("---")

st.markdown(get_perf_html("🌟 강력 추천 교집합 종목 (퍼펙트 + 장기주도)", df_common), unsafe_allow_html=True)
if not df_common.empty:
    st.dataframe(df_common.style.apply(apply_k200_styling, common_codes=common_codes, axis=1), 
                 use_container_width=True, 
                 column_order=['통합티커', '종목명_L', '시가총액(억)', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '다음달수익률(%)'], 
                 column_config=main_cfg)
else:
    st.info("해당 월에는 두 조건을 모두 만족하는 교집합 종목이 없습니다.")

st.markdown("---")
st.subheader("🏆 KOSPI 200 시가총액 전체 순위 (과거)")
st.dataframe(df_k200.style.apply(apply_k200_styling, common_codes=common_codes, axis=1), 
             use_container_width=True, height=600, 
             column_order=['통합티커', '종목명_L', '시가총액(억)', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '다음달수익률(%)'], 
             column_config=main_cfg)
