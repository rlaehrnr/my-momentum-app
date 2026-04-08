import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os

# --- [1. 페이지 설정] ---
st.set_page_config(page_title="KOSPI 200 월별/데일리 기록", layout="wide")
st.markdown("""
<style>
    .block-container { padding-top: 2rem !important; }
    .main-title { font-size: 1.6rem !important; font-weight: bold; margin-bottom: 1rem; }
</style>
""", unsafe_allow_html=True)

# 💡 [대통령 주기 하드코딩] 8년차 주기 위험달 데이터
PRESIDENTIAL_DANGEROUS_MONTHS = {
    1: [2, 9],                 # 1년차 (초선 1년차)
    2: [2, 4, 6, 9, 12],       # 2년차 (초선 중간선거)
    3: [8, 9],                 # 3년차 (초선 3년차)
    4: [3],                    # 4년차 (초선 대선해)
    5: [],                     # 5년차 (재선 1년차 / 2025년 트럼프 2기)
    6: [7],                    # 6년차 (재선 중간선거 / 2026년)
    7: [6, 8, 11, 12],         # 7년차 (재선 3년차 / 2027년 예상)
    8: [1, 6, 9, 10, 11]       # 8년차 (재선 대선해 / 2028년 예상)
}

def get_cycle_year(year):
    return ((year - 2021) % 8) + 1

# --- [2. 스타일 및 헬퍼 함수] ---
def apply_k200_styling(row, highlight_codes=None, overlap_codes=None):
    styles = [''] * len(row)
    
    # 다음달수익률(%) 양수/음수 색상
    if '다음달수익률(%)' in row.index:
        col_idx = row.index.get_loc('다음달수익률(%)')
        val = row['다음달수익률(%)']
        if pd.notna(val) and val > 0:
            styles[col_idx] = 'color: #D32F2F; font-weight: bold;'
        elif pd.notna(val) and val < 0:
            styles[col_idx] = 'color: #1976D2; font-weight: bold;'
            
    # 종목명 하이라이트 (Top 5 단일 및 교집합)
    code = row.get('종목코드')
    if code and '종목명_L' in row.index:
        name_idx = row.index.get_loc('종목명_L')
        if overlap_codes and code in overlap_codes:
            styles[name_idx] = 'background-color: #FFF59D; color: #D84315; font-weight: bold;'
        elif highlight_codes and code in highlight_codes:
            styles[name_idx] = 'background-color: #E8F5E9; color: #2E7D32; font-weight: bold;'
            
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
    df.columns = df.columns.str.replace(' ', '') 
    df['종목코드'] = df['종목코드'].astype(str).str.zfill(6)
    
    if '시가총액' in df.columns:
        df['시가총액(억)'] = (df['시가총액'] / 100000000).fillna(0).astype(int)
    else:
        df['시가총액(억)'] = 0
        
    return df

def get_perf_html(title, df):
    if df.empty:
        return f"### {title} <span style='font-size: 15px; color: gray; font-weight: normal;'>(해당 종목 없음)</span>"
    
    # 💡 데일리 탭을 위해 다음달수익률 컬럼이 없으면 타이틀만 반환
    if '다음달수익률(%)' not in df.columns:
        return f"### {title}"
    
    all_avg = df['다음달수익률(%)'].mean()
    top5_avg = df.head(5)['다음달수익률(%)'].mean()
    top10_avg = df.head(10)['다음달수익률(%)'].mean()
    
    def format_val(v):
        if pd.isna(v): return "0.00%", "gray"
        color = "#D32F2F" if v > 0 else ("#1976D2" if v < 0 else "#555")
        return f"{v:+.2f}%", color
        
    a_str, a_col = format_val(all_avg)
    t5_str, t5_col = format_val(top5_avg)
    t10_str, t10_col = format_val(top10_avg)
    
    return f"### {title} <span style='font-size: 15px; font-weight: normal; color: #666;'> &nbsp; | &nbsp; 📊 다음달 성적 ➔ Top5: <span style='color:{t5_col}; font-weight:bold;'>{t5_str}</span> &nbsp; Top10: <span style='color:{t10_col}; font-weight:bold;'>{t10_str}</span> &nbsp; 모두매수: <span style='color:{a_col}; font-weight:bold;'>{a_str}</span></span>"

def format_invest_month(date_str):
    dt = pd.to_datetime(date_str)
    invest_dt = dt + pd.DateOffset(months=1)
    return f"{invest_dt.year}년 {invest_dt.month}월 투자 (데이터 기준일: {date_str})"


# =====================================================================
# 💡 [핵심] 기존의 메인 로직을 "함수"로 묶어서 월간/데일리에서 공통으로 사용합니다.
# =====================================================================
def render_kospi200_dashboard(df_k200, selected_date, is_daily=False):
    # 티커(PC홈), 종목명(모바일 차트) 링크 설정
    df_k200['통합티커_L'] = df_k200.apply(
        lambda r: f"https://finance.naver.com/item/main.naver?code={r['종목코드']}#KOSPI:{r['종목코드']}", axis=1
    )
    df_k200['종목명_L'] = df_k200.apply(
        lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드']}#{r['종목명']}", axis=1
    )

    df_k200 = df_k200.sort_values(by='시가총액(억)', ascending=False).head(200)
    df_k200['시총순위'] = range(1, len(df_k200) + 1)
    df_k200 = df_k200.set_index('시총순위')

    kospi_1m, kospi_3m = get_idx_kr(selected_date)

    # 하락 종목 계산을 위해 안전 변환
    for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
        if c in df_k200.columns:
            df_k200[c] = pd.to_numeric(df_k200[c], errors='coerce').fillna(0)

    neg_1m_cnt = (df_k200['1개월(%)'] < 0).sum()
    neg_3m_cnt = (df_k200['3개월(%)'] < 0).sum()

    base_dt = pd.to_datetime(selected_date)
    # 월간이면 다음 달 투자 준비, 데일리면 이번 달 기준
    target_dt = base_dt + pd.DateOffset(months=1) if not is_daily else base_dt
    target_year = target_dt.year
    target_month = target_dt.month

    cycle_year = get_cycle_year(target_year)
    bad_months_this_year = PRESIDENTIAL_DANGEROUS_MONTHS.get(cycle_year, [])
    bad_m_str = ", ".join(f"{m}월" for m in bad_months_this_year) if bad_months_this_year else "없음"

    is_bad_market = (neg_1m_cnt >= 100) and (neg_3m_cnt >= 100)
    is_bad_season = target_month in bad_months_this_year

    reasons = []
    if is_bad_market: reasons.append("시장 하락장")
    if is_bad_season: reasons.append(f"위험달({target_month}월)")

    if reasons:
        invest_status = "🛑 투자 중지"
        box_color, text_color = "#FFEBEE", "#C62828"
        status_desc = " + ".join(reasons)
    else:
        invest_status = "✅ 투자 진행"
        box_color, text_color = "#E8F5E9", "#2E7D32"
        status_desc = "하락장 통과 & 양호한 달"

    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3, col4, col5, col6 = st.columns([0.9, 0.9, 1.0, 1.0, 1.4, 1.6])

    with col1: st.metric(label="📈 KOSPI 1M", value=f"{kospi_1m}%")
    with col2: st.metric(label="📈 KOSPI 3M", value=f"{kospi_3m}%")
    with col3: st.metric(label="📉 1개월 하락", value=f"{neg_1m_cnt}개")
    with col4: st.metric(label="📉 3개월 하락", value=f"{neg_3m_cnt}개")
    with col5:
        st.markdown(f"""
        <div style="background-color: #f0f2f6; padding: 12px 10px; border-radius: 10px; text-align: center; border: 1px solid #d1d5db; height: 100%;">
            <div style="font-size: 13px; font-weight: bold; color: #333; margin-bottom: 5px;">🇺🇸대통령 <span style="color:#0047AB; font-size:15px;">{cycle_year}년차</span> ({target_year}년)</div>
            <div style="font-size: 13px; font-weight: bold; color: #D84315;">위험달: {bad_m_str}</div>
        </div>
        """, unsafe_allow_html=True)
    with col6:
        st.markdown(f"""
        <div style="background-color: {box_color}; padding: 10px; border-radius: 10px; text-align: center; border: 1px solid {text_color};">
            <p style="margin: 0; font-size: 12px; color: {text_color}; font-weight: bold;">당시 최종 판단 ({status_desc})</p>
            <h3 style="margin: 3px 0 0 0; color: {text_color};">{invest_status}</h3>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("<br><hr>", unsafe_allow_html=True)

    q30 = {c: df_k200[c].quantile(0.7) for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']}
    t10_1m = df_k200['1개월(%)'].quantile(0.9)

    cond_perf = (df_k200['1개월(%)']>=q30['1개월(%)'])&(df_k200['3개월(%)']>=q30['3개월(%)'])&(df_k200['6개월(%)']>=q30['6개월(%)'])&(df_k200['12개월(%)']>=q30['12개월(%)']) & \
                (df_k200['1개월(%)']>0)&(df_k200['3개월(%)']>0)&(df_k200['6개월(%)']>0)&(df_k200['12개월(%)']>0)

    df_perf = df_k200[cond_perf].sort_values('3개월(%)', ascending=False).copy()
    df_spec = df_k200[(df_k200['12개월(%)']>=q30['12개월(%)']) & (df_k200['1개월(%)']>=t10_1m)].sort_values('1개월(%)', ascending=False).copy()

    top5_perf = df_perf.head(5)['종목코드'].tolist()
    top5_spec = df_spec.head(5)['종목코드'].tolist()
    overlap_top5 = set(top5_perf).intersection(set(top5_spec))

    main_cfg = {
        "통합티커_L": st.column_config.LinkColumn("티커", display_text=r"#(.+)"), 
        "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), 
        "1개월(%)": st.column_config.NumberColumn(format="%.1f"), 
        "3개월(%)": st.column_config.NumberColumn(format="%.1f"), 
        "6개월(%)": st.column_config.NumberColumn(format="%.1f"), 
        "12개월(%)": st.column_config.NumberColumn(format="%.1f"),
        "다음달수익률(%)": st.column_config.NumberColumn("다음달수익률(%)", format="%.2f") 
    }

    # 💡 데일리 데이터에는 다음달수익률 컬럼이 없으므로 동적으로 컬럼 숨기기
    has_next = '다음달수익률(%)' in df_k200.columns
    perf_cols = ['통합티커_L', '종목명_L', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)'] + (['다음달수익률(%)'] if has_next else [])
    spec_cols = ['통합티커_L', '종목명_L', '1개월(%)', '12개월(%)'] + (['다음달수익률(%)'] if has_next else [])
    all_cols =  ['통합티커_L', '종목명_L', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)'] + (['다음달수익률(%)'] if has_next else [])

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(get_perf_html("🔥 퍼펙트 상승", df_perf), unsafe_allow_html=True)
        st.dataframe(df_perf.style.apply(apply_k200_styling, highlight_codes=top5_perf, overlap_codes=overlap_top5, axis=1), 
                     use_container_width=True, column_order=perf_cols, column_config=main_cfg)
    with c2:
        st.markdown(get_perf_html("🐎 달리는 말", df_spec), unsafe_allow_html=True)
        st.dataframe(df_spec.style.apply(apply_k200_styling, highlight_codes=top5_spec, overlap_codes=overlap_top5, axis=1), 
                     use_container_width=True, column_order=spec_cols, column_config=main_cfg)

    st.markdown("---")
    st.subheader("🏆 KOSPI 200 전체 순위")
    st.dataframe(df_k200.style.apply(apply_k200_styling, axis=1), 
                 use_container_width=True, height=600, 
                 column_order=all_cols, column_config=main_cfg)


# =====================================================================
# 💡 [3. 메인 화면 탭 구성]
# =====================================================================
st.title("🇰🇷 KOSPI 200 강세 종목 분석")

tab_history, tab_daily = st.tabs(["📅 과거 월별 기록", "🕒 오늘(데일리) 기준"])

with tab_history:
    f_csv = 'data/한국 코스피 2014년부터 200위까지 자료.csv'
    if not os.path.exists(f_csv):
        st.error(f"데이터 파일이 없습니다: {f_csv}")
    else:
        df_all = load_historical_data(f_csv)
        dates = sorted(df_all['기준일'].unique(), reverse=True)
        
        st.markdown("<h4 style='margin-bottom: 5px;'>📅 확인하고 싶은 '투자 월'을 선택하세요</h4>", unsafe_allow_html=True)
        selected_date = st.selectbox("조회일", dates, format_func=format_invest_month, label_visibility="collapsed")
        
        invest_title = format_invest_month(selected_date)
        st.markdown(f'<p class="main-title">🎯 KOSPI 200 과거 기록 분석 ➔ {invest_title}</p>', unsafe_allow_html=True)
        
        df_k200_hist = df_all[df_all['기준일'] == selected_date].copy()
        render_kospi200_dashboard(df_k200_hist, selected_date, is_daily=False)

with tab_daily:
    f_daily = 'data/momentum_data_daily.csv'
    if not os.path.exists(f_daily):
        st.error(f"데이터 파일이 없습니다: {f_daily} (데일리 업데이트를 먼저 실행해주세요)")
    else:
        df_daily = pd.read_csv(f_daily, dtype={'종목코드': str})
        df_daily.columns = df_daily.columns.str.replace(' ', '')
        df_daily['종목코드'] = df_daily['종목코드'].astype(str).str.zfill(6)
        
        if '시가총액' in df_daily.columns:
            df_daily['시가총액(억)'] = (pd.to_numeric(df_daily['시가총액'], errors='coerce') / 100000000).fillna(0).astype(int)
        else:
            df_daily['시가총액(억)'] = 0
            
        daily_date = df_daily['기준일'].iloc[0] if '기준일' in df_daily.columns else datetime.today().strftime('%Y-%m-%d')
        
        # 데일리 파일에서 KOSPI 종목만 추출
        df_daily_kospi = df_daily[df_daily['시장'] == 'KOSPI'].copy() if '시장' in df_daily.columns else df_daily.copy()
        
        st.markdown(f'<p class="main-title">🎯 KOSPI 200 데일리 현황 ➔ 기준일: {daily_date}</p>', unsafe_allow_html=True)
        
        if not df_daily_kospi.empty:
            render_kospi200_dashboard(df_daily_kospi, daily_date, is_daily=True)
        else:
            st.info("오늘의 KOSPI 종목 데이터가 없습니다.")
