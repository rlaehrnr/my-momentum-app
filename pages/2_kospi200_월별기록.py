import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os

# --- [1. 페이지 설정] ---
st.set_page_config(page_title="KOSPI 200 월별 기록", layout="wide")

st.markdown("""
    <style>
    .block-container { padding-top: 2.8rem !important; padding-bottom: 1rem !important; }
    .main-title { font-size: 1.5rem !important; font-weight: bold; margin-bottom: 0.5rem; }
    
    @media (max-width: 768px) {
        div[data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
        }
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
            min-width: 45% !important; 
            flex: 1 1 45% !important;
            margin-bottom: 5px !important;
        }
    }
    
    /* 제목 링크 호버 액션 */
    .title-link:hover { opacity: 0.7; transition: 0.2s; }
    
    /* 컬럼 헤더 줄바꿈 허용 (날짜 표시용) */
    th[data-testid="stTableColumnHeader"] div {
        white-space: pre-wrap !important;
        text-align: center !important;
    }
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
    
    if '다음달수익률(%)' in row.index:
        col_idx = row.index.get_loc('다음달수익률(%)')
        val = row['다음달수익률(%)']
        if pd.notna(val) and val > 0:
            styles[col_idx] = 'color: #D32F2F; font-weight: bold;'
        elif pd.notna(val) and val < 0:
            styles[col_idx] = 'color: #1976D2; font-weight: bold;'
            
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

@st.cache_data(ttl=3600)
def get_kospi_ma_status(target_date_str):
    target_date = pd.to_datetime(target_date_str)
    start_date = target_date - timedelta(days=400)
    try:
        df = fdr.DataReader('KS11', start_date, target_date)
        if df.empty: return pd.DataFrame()
        
        curr_price = df['Close'].iloc[-1]
        url_name = "https://m.stock.naver.com/domestic/index/KOSPI/total#KOSPI"
        url_price = f"https://m.stock.naver.com/fchart/domestic/index/KOSPI#{curr_price:,.2f}"
        
        ma_values = {
            '지수_L': url_name, '현재가_L': url_price, 'base_price': round(curr_price, 2),
            '4개월선': round(df['Close'].rolling(80).mean().iloc[-1], 2),
            '5개월선': round(df['Close'].rolling(100).mean().iloc[-1], 2),
            '6개월선': round(df['Close'].rolling(120).mean().iloc[-1], 2),
            '10개월선': round(df['Close'].rolling(200).mean().iloc[-1], 2),
            '12개월선': round(df['Close'].rolling(240).mean().iloc[-1], 2)
        }
        return pd.DataFrame([ma_values])
    except: return pd.DataFrame()

def style_kospi_ma(df):
    def apply_color(row):
        price = row['base_price']
        styles = [''] * len(row)
        for i, col in enumerate(row.index):
            if '개월선' in col:
                val = row[col]
                if pd.notna(val):
                    if price > val: styles[i] = 'color: #EF4444; font-weight: bold;' 
                    elif price < val: styles[i] = 'color: #3B82F6; font-weight: bold;' 
        return styles
    return df.style.apply(apply_color, axis=1)

kospi_ma_config = {
    "지수_L": st.column_config.LinkColumn("지수", display_text=r"#(.+)"),
    "현재가_L": st.column_config.LinkColumn("현재가", display_text=r"#(.+)"),
    "4개월선": st.column_config.NumberColumn("4개월선", format="%,.2f"),
    "5개월선": st.column_config.NumberColumn("5개월선", format="%,.2f"),
    "6개월선": st.column_config.NumberColumn("6개월선", format="%,.2f"),
    "10개월선": st.column_config.NumberColumn("10개월선", format="%,.2f"),
    "12개월선": st.column_config.NumberColumn("12개월선", format="%,.2f"),
    "base_price": None 
}

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

# 💡 [신규] 백테스트 전체 누적 데이터 생성 함수
@st.cache_data
def build_backtest_summary(df_all):
    records = []
    dates = sorted(df_all['기준일'].unique()) # 과거부터 순차적으로
    
    for d in dates:
        dt = pd.to_datetime(d)
        inv_dt = dt + pd.DateOffset(months=1)
        inv_str = f"{inv_dt.year}-{inv_dt.month:02d}"
        
        df_k200 = df_all[df_all['기준일'] == d].copy()
        df_k200 = df_k200.sort_values(by='시가총액(억)', ascending=False).head(200)
        
        for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '다음달수익률(%)']:
            if c in df_k200.columns:
                df_k200[c] = pd.to_numeric(df_k200[c], errors='coerce').fillna(0)
                
        q30 = {c: df_k200[c].quantile(0.7) for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']}
        t10_1m = df_k200['1개월(%)'].quantile(0.9)

        cond_perf = (df_k200['1개월(%)']>=q30['1개월(%)'])&(df_k200['3개월(%)']>=q30['3개월(%)'])&(df_k200['6개월(%)']>=q30['6개월(%)'])&(df_k200['12개월(%)']>=q30['12개월(%)']) & \
                    (df_k200['1개월(%)']>0)&(df_k200['3개월(%)']>0)&(df_k200['6개월(%)']>0)&(df_k200['12개월(%)']>0)

        df_perf = df_k200[cond_perf].sort_values('3개월(%)', ascending=False)
        df_spec = df_k200[(df_k200['12개월(%)']>=q30['12개월(%)']) & (df_k200['1개월(%)']>=t10_1m)].sort_values('1개월(%)', ascending=False)
        
        def get_ret(df, n=None):
            if df.empty: return 0.0
            if n: return df.head(n)['다음달수익률(%)'].mean()
            return df['다음달수익률(%)'].mean()
            
        records.append({
            '투자월': inv_str,
            '퍼펙트상승(Top5)': get_ret(df_perf, 5),
            '퍼펙트상승(Top10)': get_ret(df_perf, 10),
            '퍼펙트상승(전체)': get_ret(df_perf),
            '달리는말(Top5)': get_ret(df_spec, 5),
            '달리는말(Top10)': get_ret(df_spec, 10),
            '달리는말(전체)': get_ret(df_spec),
        })
    return pd.DataFrame(records)

def get_perf_html(title, df, target_month):
    if df.empty:
        return f"### {title} <span style='font-size: 15px; color: gray; font-weight: normal;'>(해당 종목 없음)</span>"
    
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
    
    return f"### {title} <span style='font-size: 15px; font-weight: normal; color: #666;'> &nbsp; | &nbsp; 📊 {target_month}월 성적 ➔ Top5: <span style='color:{t5_col}; font-weight:bold;'>{t5_str}</span> &nbsp; Top10: <span style='color:{t10_col}; font-weight:bold;'>{t10_str}</span> &nbsp; 모두매수: <span style='color:{a_col}; font-weight:bold;'>{a_str}</span></span>"

# --- [3. 메인 화면 구성] ---

st.markdown('''
    <div style="margin-bottom: 20px;">
        <a href="https://stock.naver.com/" target="_blank" class="title-link" style="text-decoration: none; color: inherit;">
            <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 12px;">
                <h1 style="margin: 0; padding: 0; font-size: 2.2rem; font-weight: 800; line-height: 1.2; word-break: keep-all;">🎯 KOSPI 200 강세 종목 월별 기록</h1>
                <span style="font-size: 0.95rem; color: #3b82f6; background-color: #eff6ff; padding: 4px 10px; border-radius: 6px; border: 1px solid #bfdbfe; white-space: nowrap;">🔗 네이버 증권 이동</span>
            </div>
        </a>
    </div>
''', unsafe_allow_html=True)


f_csv = 'data/한국 코스피 2014년부터 200위까지 자료.csv'

if not os.path.exists(f_csv):
    st.error(f"데이터 파일이 없습니다: {f_csv}")
    st.stop()

df_all = load_historical_data(f_csv)

# 💡 [신규] 두 개의 탭 생성 (월별 상세 분석 / 백테스트 누적 성과)
tab_detail, tab_summary = st.tabs(["📅 월별 상세 분석", "📈 전략 누적 성과 (백테스트)"])

with tab_detail:
    # 💡 [업데이트 1] 년도와 월을 분리해서 선택하게 하는 UI
    dates = sorted(df_all['기준일'].unique(), reverse=True)
    date_map = {}
    for d in dates:
        dt = pd.to_datetime(d)
        inv_dt = dt + pd.DateOffset(months=1)
        date_map[d] = {'year': inv_dt.year, 'month': inv_dt.month, 'base_date': d}
        
    years = sorted(list(set(v['year'] for v in date_map.values())), reverse=True)
    
    st.markdown("<h4 style='margin-bottom: 5px; font-size: 1.1rem; color: #4B5563;'>🔍 확인하고 싶은 '투자 연도'와 '월'을 선택하세요</h4>", unsafe_allow_html=True)
    
    col_y, col_m = st.columns([1, 1])
    with col_y:
        selected_year = st.selectbox("투자 연도", years, format_func=lambda x: f"{x}년 투자")
    with col_m:
        months_for_year = sorted(list(set(v['month'] for v in date_map.values() if v['year'] == selected_year)), reverse=True)
        selected_month = st.selectbox("투자 월", months_for_year, format_func=lambda x: f"{x}월 성적 확인")
        
    # 선택한 연/월을 실제 기준일로 매핑
    selected_date = next(d for d, v in date_map.items() if v['year'] == selected_year and v['month'] == selected_month)

    st.markdown(f"**💡 데이터 기준일:** `{selected_date}` (해당 기준일 종가로 매수하여 {selected_month}월 한 달 동안 투자한 결과입니다.)")

    kospi_ma_df = get_kospi_ma_status(selected_date)
    kospi_curr = 0
    kospi_4m_ma = 0

    if not kospi_ma_df.empty:
        st.dataframe(style_kospi_ma(kospi_ma_df), use_container_width=True, hide_index=True, 
                     column_order=["지수_L", "현재가_L", "4개월선", "5개월선", "6개월선", "10개월선", "12개월선"],
                     column_config=kospi_ma_config)
        kospi_curr = kospi_ma_df['base_price'].iloc[0]
        kospi_4m_ma = kospi_ma_df['4개월선'].iloc[0]

    st.markdown("<br>", unsafe_allow_html=True)

    df_k200 = df_all[df_all['기준일'] == selected_date].copy()

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

    neg_1m_cnt = (df_k200['1개월(%)'] < 0).sum()
    neg_3m_cnt = (df_k200['3개월(%)'] < 0).sum()

    base_dt = pd.to_datetime(selected_date)
    target_dt = base_dt + pd.DateOffset(months=1)
    target_year = target_dt.year
    target_month = target_dt.month

    cycle_year = get_cycle_year(target_year)
    bad_months_this_year = PRESIDENTIAL_DANGEROUS_MONTHS.get(cycle_year, [])
    bad_m_str = ", ".join(f"{m}월" for m in bad_months_this_year) if bad_months_this_year else "없음"

    is_bad_market = (neg_1m_cnt >= 100) and (neg_3m_cnt >= 100)
    is_below_4m_ma = (kospi_curr > 0) and (kospi_curr < kospi_4m_ma)

    reasons = []
    if is_bad_market: reasons.append("하락장(1,3M 100개↑)")
    if is_below_4m_ma: reasons.append("4개월선 이탈")

    if reasons:
        invest_status = "🛑 투자 중지"
        box_color, text_color = "#FFEBEE", "#C62828"
        status_desc = " + ".join(reasons)
    else:
        invest_status = "✅ 투자 진행"
        box_color, text_color = "#E8F5E9", "#2E7D32"
        status_desc = "상승장 & 4개월선 위"

    col1, col2, col3, col4, col5, col6 = st.columns([0.9, 0.9, 1.0, 1.0, 1.4, 1.6])

    with col1: st.metric(label="📈 KOSPI 1M", value=f"{kospi_1m}%")
    with col2: st.metric(label="📈 KOSPI 3M", value=f"{kospi_3m}%")
    with col3: st.metric(label="📉 1개월 하락", value=f"{neg_1m_cnt}개")
    with col4: st.metric(label="📉 3개월 하락", value=f"{neg_3m_cnt}개")
    with col5:
        st.markdown(f'<div style="background-color: #f0f2f6; padding: 10px; border-radius: 10px; text-align: center; border: 1px solid #d1d5db; height: 100%; min-height: 95px; display: flex; flex-direction: column; justify-content: center;"><div style="font-size: 13px; font-weight: bold; color: #333; margin-bottom: 4px;">🇺🇸대통령 <span style="color:#0047AB; font-size:14px;">{cycle_year}년차</span> ({target_year}년)</div><div style="font-size: 13px; font-weight: bold; color: #D84315;">위험달: {bad_m_str}</div></div>', unsafe_allow_html=True)
    with col6:
        st.markdown(f'<div style="background-color: {box_color}; padding: 10px; border-radius: 10px; text-align: center; border: 1px solid {text_color}; display: flex; flex-direction: column; justify-content: center; height: 100%; min-height: 95px;"><p style="margin: 0; font-size: 12px; color: {text_color}; font-weight: bold;">당시 최종 판단 ({status_desc})</p><div style="margin: 4px 0 0 0; font-size: 1.5rem; font-weight: 900; color: {text_color};">{invest_status}</div></div>', unsafe_allow_html=True)
        
    st.markdown("<hr style='margin: 1rem 0;'>", unsafe_allow_html=True)

    for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
        if c in df_k200.columns:
            df_k200[c] = pd.to_numeric(df_k200[c], errors='coerce').fillna(0)

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
        "다음달수익률(%)": st.column_config.NumberColumn(f"{target_month}월 수익률(%)", format="%.2f") 
    }

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(get_perf_html("🔥 퍼펙트 상승", df_perf, target_month), unsafe_allow_html=True)
        st.dataframe(df_perf.style.apply(apply_k200_styling, highlight_codes=top5_perf, overlap_codes=overlap_top5, axis=1), 
                     use_container_width=True, 
                     column_order=['통합티커_L', '종목명_L', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '다음달수익률(%)'], 
                     column_config=main_cfg)
    with col2:
        st.markdown(get_perf_html("🐎 달리는 말", df_spec, target_month), unsafe_allow_html=True)
        st.dataframe(df_spec.style.apply(apply_k200_styling, highlight_codes=top5_spec, overlap_codes=overlap_top5, axis=1), 
                     use_container_width=True, 
                     column_order=['통합티커_L', '종목명_L', '1개월(%)', '12개월(%)', '다음달수익률(%)'], 
                     column_config=main_cfg)

    st.markdown("---")
    st.subheader("🏆 KOSPI 200 전체 순위 (과거)")

    def get_ref_str(m):
        ref_dt = (base_dt.replace(day=1) - pd.DateOffset(months=m-1)) - timedelta(days=1)
        return ref_dt.strftime('%y.%m.%d')

    full_cfg = main_cfg.copy()
    full_cfg['1개월(%)'] = st.column_config.NumberColumn(f"1개월(%)\n({get_ref_str(1)})", format="%.1f")
    full_cfg['3개월(%)'] = st.column_config.NumberColumn(f"3개월(%)\n({get_ref_str(3)})", format="%.1f")
    full_cfg['6개월(%)'] = st.column_config.NumberColumn(f"6개월(%)\n({get_ref_str(6)})", format="%.1f")
    full_cfg['12개월(%)'] = st.column_config.NumberColumn(f"12개월(%)\n({get_ref_str(12)})", format="%.1f")

    st.dataframe(df_k200.style.apply(apply_k200_styling, axis=1), 
                 use_container_width=True, height=600, 
                 column_order=['통합티커_L', '종목명_L', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '다음달수익률(%)'], 
                 column_config=full_cfg)


# 💡 [업데이트 2] 신규 누적 성과(백테스트) 탭 구현
with tab_summary:
    st.markdown("### 📈 퍼펙트 상승 & 달리는 말 전략 누적 백테스트 (2014 ~ 현재)")
    st.info("2014년 2월부터 매월 전략 조건에 맞는 종목(Top5, Top10, 전체)을 기계적으로 매수했을 때의 가상 누적 자산 곡선과 통계입니다. (시작 자산 = 100)")
    
    with st.spinner("백테스트 데이터를 계산 중입니다... (최초 1회만 약 3초 소요)"):
        df_summary = build_backtest_summary(df_all)
    
    # 누적 수익률(복리) 계산 (100 기준)
    df_cum = (1 + df_summary.set_index('투자월') / 100).cumprod() * 100
    
    # 차트 시작점을 깔끔하게 100으로 맞추기 위해 첫 달 이전 날짜 생성
    first_month = pd.to_datetime(df_summary['투자월'].iloc[0]) - pd.DateOffset(months=1)
    first_month_str = f"{first_month.year}-{first_month.month:02d}"
    df_cum.loc[first_month_str] = 100
    df_cum = df_cum.sort_index()

    # 차트 렌더링
    st.line_chart(df_cum, use_container_width=True, height=400)
    
    # 결과 통계 요약표 계산
    st.markdown("#### 📊 전략별 핵심 통계")
    
    stats = []
    for col in df_summary.columns[1:]:
        total_ret = df_cum[col].iloc[-1] - 100
        win_months = (df_summary[col] > 0).sum()
        total_months = len(df_summary)
        win_rate = (win_months / total_months) * 100
        avg_ret = df_summary[col].mean()
        
        stats.append({
            "전략명": col,
            "총 누적수익률": f"{total_ret:,.1f}%",
            "월별 승률": f"{win_rate:.1f}% ({win_months}승 / {total_months}월)",
            "월평균 수익률": f"{avg_ret:.2f}%"
        })
        
    df_stats = pd.DataFrame(stats)
    st.dataframe(df_stats, use_container_width=True, hide_index=True)
    
    with st.expander("📝 월별 수익률 상세 기록 보기"):
        st.dataframe(df_summary.set_index('투자월').style.format("{:.2f}%"), use_container_width=True)
