import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os
import plotly.express as px

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
    
    .settings-box { background-color: #f8fafc; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 20px; }
    .title-link:hover { opacity: 0.7; transition: 0.2s; }
    th[data-testid="stTableColumnHeader"] div { white-space: pre-wrap !important; text-align: center !important; }
    </style>
""", unsafe_allow_html=True)

PRESIDENTIAL_DANGEROUS_MONTHS = {
    1: [2, 9], 2: [2, 4, 6, 9, 12], 3: [8, 9], 4: [3],
    5: [], 6: [7], 7: [6, 8, 11, 12], 8: [1, 6, 9, 10, 11]
}

def get_cycle_year(year):
    return ((year - 2021) % 8) + 1

# --- [2. 헬퍼 함수] ---
def apply_k200_styling(row, highlight_codes=None, overlap_codes=None):
    styles = [''] * len(row)
    if '다음달수익률(%)' in row.index:
        col_idx = row.index.get_loc('다음달수익률(%)')
        val = row['다음달수익률(%)']
        if pd.notna(val) and val > 0: styles[col_idx] = 'color: #D32F2F; font-weight: bold;'
        elif pd.notna(val) and val < 0: styles[col_idx] = 'color: #1976D2; font-weight: bold;'
            
    code = row.get('종목코드')
    if code and '종목명_L' in row.index:
        name_idx = row.index.get_loc('종목명_L')
        if overlap_codes and code in overlap_codes: styles[name_idx] = 'background-color: #FFF59D; color: #D84315; font-weight: bold;'
        elif highlight_codes and code in highlight_codes: styles[name_idx] = 'background-color: #E8F5E9; color: #2E7D32; font-weight: bold;'
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
    except: return 0.0, 0.0

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
    if '시가총액' in df.columns: df['시가총액(억)'] = (df['시가총액'] / 100000000).fillna(0).astype(int)
    else: df['시가총액(억)'] = 0
    return df

# 💡 [업데이트] 빠른 백테스트 슬라이싱을 위해 데이터프레임을 통째로 캐싱
@st.cache_data
def prep_backtest_data(df_all):
    min_date = pd.to_datetime(df_all['기준일'].min()) - timedelta(days=400)
    max_date = pd.to_datetime(df_all['기준일'].max()) + timedelta(days=31)
    try:
        ks11 = fdr.DataReader('KS11', min_date, max_date)
        ks11['4MA'] = ks11['Close'].rolling(80).mean()
    except: ks11 = pd.DataFrame()

    monthly_data = []
    dates = sorted(df_all['기준일'].unique())

    for d in dates:
        dt = pd.to_datetime(d)
        inv_dt = dt + pd.DateOffset(months=1)
        inv_str = f"{inv_dt.year}-{inv_dt.month:02d}"
        inv_year = inv_dt.year

        df_k200 = df_all[df_all['기준일'] == d].copy()
        df_k200 = df_k200.sort_values(by='시가총액(억)', ascending=False).head(200)

        for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '다음달수익률(%)']:
            if c in df_k200.columns: df_k200[c] = pd.to_numeric(df_k200[c], errors='coerce').fillna(0)

        q30 = {c: df_k200[c].quantile(0.7) for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']}
        t10_1m = df_k200['1개월(%)'].quantile(0.9)

        cond_perf = (df_k200['1개월(%)']>=q30['1개월(%)'])&(df_k200['3개월(%)']>=q30['3개월(%)'])&(df_k200['6개월(%)']>=q30['6개월(%)'])&(df_k200['12개월(%)']>=q30['12개월(%)']) & (df_k200['1개월(%)']>0)&(df_k200['3개월(%)']>0)&(df_k200['6개월(%)']>0)&(df_k200['12개월(%)']>0)

        df_perf = df_k200[cond_perf].sort_values('3개월(%)', ascending=False)
        df_spec = df_k200[(df_k200['12개월(%)']>=q30['12개월(%)']) & (df_k200['1개월(%)']>=t10_1m)].sort_values('1개월(%)', ascending=False)

        is_bad = False
        if not ks11.empty:
            ks_sub = ks11.loc[ks11.index <= dt]
            if not ks_sub.empty:
                ks_row = ks_sub.iloc[-1]
                kospi_curr = ks_row['Close']
                kospi_4m = ks_row['4MA']
                neg_1m = (df_k200['1개월(%)'] < 0).sum()
                neg_3m = (df_k200['3개월(%)'] < 0).sum()
                is_bad = (neg_1m >= 100 and neg_3m >= 100) or (pd.notna(kospi_4m) and kospi_curr < kospi_4m)

        monthly_data.append({
            '투자월': inv_str,
            '투자연도': inv_year,
            'is_bad': is_bad,
            'df_perf': df_perf, # 필터링된 전체 리스트 (백테스트에서 슬라이싱용)
            'df_spec': df_spec, 
            'df_k200': df_k200  # KOSPI 200 전체 리스트 (커스텀 스코어용)
        })
    return monthly_data

def get_perf_html(title, df, target_month):
    if df.empty: return f"### {title} <span style='font-size: 15px; color: gray; font-weight: normal;'>(해당 종목 없음)</span>"
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

# 💡 탭 3개로 구성 변경
tab_detail, tab_summary, tab_custom = st.tabs(["📅 월별 상세 분석", "📈 전략 누적 성과 (백테스트)", "🏅 스코어 커스텀 백테스트"])

# ==========================================
# 탭 1: 월별 상세 분석
# ==========================================
with tab_detail:
    dates = sorted(df_all['기준일'].unique(), reverse=True)
    date_map = {}
    for d in dates:
        dt = pd.to_datetime(d)
        inv_dt = dt + pd.DateOffset(months=1)
        date_map[d] = {'year': inv_dt.year, 'month': inv_dt.month, 'base_date': d}
        
    years = sorted(list(set(v['year'] for v in date_map.values())), reverse=True)
    
    col_y, col_m, col_info = st.columns([1.5, 1.5, 6])
    with col_y:
        selected_year = st.selectbox("투자 연도", years, format_func=lambda x: f"{x}년")
    with col_m:
        months_for_year = sorted(list(set(v['month'] for v in date_map.values() if v['year'] == selected_year)), reverse=False)
        selected_month = st.selectbox("투자 월", months_for_year, format_func=lambda x: f"{x}월")
        
    selected_date = next(d for d, v in date_map.items() if v['year'] == selected_year and v['month'] == selected_month)

    with col_info:
        st.markdown(f"<div style='margin-top: 32px; color: #6b7280; font-size: 0.95rem;'>💡 <b>데이터 기준일:</b> {selected_date}</div>", unsafe_allow_html=True)

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


# ==========================================
# 탭 2: 전략 누적 성과 (백테스트)
# ==========================================
with tab_summary:
    col_title, col_check = st.columns([1, 4])
    with col_title:
        st.markdown("<h4 style='margin-top: 5px; margin-bottom: 0px;'>⚙️ 시뮬레이션 설정</h4>", unsafe_allow_html=True)
    with col_check:
        st.markdown("<div style='margin-top: 8px;'>", unsafe_allow_html=True)
        apply_timing = st.checkbox("🛑 마켓타이밍 적용 (조건 미달 시 현금 100%)", value=True, key='k_timing2')
        st.markdown("</div>", unsafe_allow_html=True)
        
    with st.spinner("백테스트 데이터를 준비 중입니다... (최초 1회만)"):
        monthly_data = prep_backtest_data(df_all)
        
    c1, c2, c3 = st.columns(3)
    with c1:
        years_list = sorted(list(set([m['투자연도'] for m in monthly_data])))
        min_y, max_y = min(years_list), max(years_list)
        start_year, end_year = st.slider("📅 테스트 기간 (연도)", min_y, max_y, (min_y, max_y), key='k_yr2')
    with c2:
        rank_p_start, rank_p_end = st.slider("🔥 퍼펙트 상승 (매수 순위)", 1, 30, (1, 5))
    with c3:
        rank_s_start, rank_s_end = st.slider("🐎 달리는 말 (매수 순위)", 1, 30, (1, 5))
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    if rank_p_start > rank_p_end or rank_s_start > rank_s_end:
        st.error("🚨 순위 범위가 잘못되었습니다. (예: 2~6위 형태로 설정해주세요)")
        st.stop()
        
    with st.spinner("수익률 계산 중..."):
        records = []
        for m in monthly_data:
            if not (start_year <= m['투자연도'] <= end_year): continue
            
            mult = 0.0 if (apply_timing and m['is_bad']) else 1.0
            is_invested = mult > 0.0  
            
            # 💡 슬라이싱 적용
            df_p = m['df_perf'].iloc[rank_p_start-1 : rank_p_end]
            df_s = m['df_spec'].iloc[rank_s_start-1 : rank_s_end]
            
            ret_p = (df_p['다음달수익률(%)'].mean() * mult) if not df_p.empty else 0.0
            ret_s = (df_s['다음달수익률(%)'].mean() * mult) if not df_s.empty else 0.0
            
            combined_tickers = list(set(df_p['종목코드'].tolist() + df_s['종목코드'].tolist()))
            df_c = m['df_k200'][m['df_k200']['종목코드'].isin(combined_tickers)]
            ret_combined = (df_c['다음달수익률(%)'].mean() * mult) if not df_c.empty else 0.0
            
            ret_ensemble = (ret_p + ret_s) / 2
            
            records.append({
                '투자월': m['투자월'],
                'invested': is_invested,
                f'🔥 퍼펙트상승 ({rank_p_start}~{rank_p_end}위)': ret_p,
                f'🐎 달리는말 ({rank_s_start}~{rank_s_end}위)': ret_s,
                '앙상블 (전략 50:50)': ret_ensemble,
                '통합 (모든종목 동일비중)': ret_combined
            })
            
        df_summary = pd.DataFrame(records)
        df_summary.fillna(0.0, inplace=True)
        
        if not df_summary.empty:
            strategy_cols = [c for c in df_summary.columns if c not in ['투자월', 'invested']]
            df_cum = (1 + df_summary.set_index('투자월')[strategy_cols] / 100).cumprod() * 100
            
            first_m_str = (pd.to_datetime(df_summary['투자월'].iloc[0]) - pd.DateOffset(months=1)).strftime('%Y-%m')
            df_cum.loc[first_m_str] = 100
            df_cum = df_cum.sort_index()

            st.markdown(f"### 📈 {start_year}년 ~ {end_year}년 누적 자산 성장 곡선 (Log Scale)")
            df_melt = df_cum.reset_index().melt(id_vars='투자월', var_name='전략', value_name='누적수익률')
            fig = px.line(df_melt, x='투자월', y='누적수익률', color='전략', log_y=True)
            fig.update_layout(hovermode="x unified", dragmode="pan", xaxis_title="투자 기준 월", yaxis_title="누적 자산 (초기 자본 = 100, 로그스케일)", legend_title_text="투자 전략", margin=dict(l=0, r=0, t=20, b=0))
            st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True, 'displayModeBar': True})
            
            st.markdown("#### 📊 전략별 핵심 통계 (초기 자본 100 기준)")
            stats = []
            total_months = len(df_summary)
            invested_months = df_summary['invested'].sum()
            invest_ratio = (invested_months / total_months) * 100 if total_months > 0 else 0

            for col in strategy_cols:
                final_val = df_cum[col].iloc[-1]
                total_ret = final_val - 100
                years = total_months / 12
                cagr = ((final_val / 100) ** (1 / years) - 1) * 100 if final_val > 0 else -100.0
                
                if invested_months > 0:
                    win_months = (df_summary.loc[df_summary['invested'], col] > 0).sum()
                    win_rate = (win_months / invested_months) * 100
                    avg_ret = df_summary.loc[df_summary['invested'], col].mean()
                else: win_months = 0; win_rate = 0.0; avg_ret = 0.0
                
                roll_max = df_cum[col].cummax()
                mdd = ((df_cum[col] / roll_max) - 1.0).min() * 100
                
                stats.append({"전략명": col, "CAGR (연평균)": f"{cagr:.1f}%", "총 누적수익률": f"{total_ret:,.1f}%", "MDD (최대낙폭)": f"{mdd:.1f}%", "투자월 비율": f"{invest_ratio:.1f}% ({invested_months}/{total_months}개월)", "월별 승률": f"{win_rate:.1f}% ({win_months}승)", "평균 수익률(투자월)": f"{avg_ret:.2f}%"})
                
            df_stats = pd.DataFrame(stats)
            def style_stats(x):
                if isinstance(x, str) and '%' in x:
                    if '-' in x: return 'color: #1976D2; font-weight:bold;'
                    elif x != '0.0%': return 'color: #D32F2F; font-weight:bold;'
                return ''
            try: styled_stats = df_stats.style.map(style_stats, subset=['CAGR (연평균)', '총 누적수익률', 'MDD (최대낙폭)'])
            except AttributeError: styled_stats = df_stats.style.applymap(style_stats, subset=['CAGR (연평균)', '총 누적수익률', 'MDD (최대낙폭)'])
            st.dataframe(styled_stats, use_container_width=True, hide_index=True)
            
            with st.expander(f"📝 {start_year}~{end_year}년 ({total_months}개월) 월별 수익률 상세 기록 보기"):
                display_df = df_summary.drop(columns=['invested']).set_index('투자월')
                st.dataframe(display_df.style.format("{:.2f}%"), use_container_width=True)


# ==========================================
# 탭 3: 모멘텀 스코어 커스텀 백테스트
# ==========================================
with tab_custom:
    col_title, col_check = st.columns([1, 4])
    with col_title:
        st.markdown("<h4 style='margin-top: 5px; margin-bottom: 0px;'>⚙️ 스코어 가중치 설정</h4>", unsafe_allow_html=True)
    with col_check:
        st.markdown("<div style='margin-top: 8px;'>", unsafe_allow_html=True)
        apply_timing_c = st.checkbox("🛑 마켓타이밍 적용 (조건 미달 시 현금 100%)", value=True, key='k_timing3')
        st.markdown("</div>", unsafe_allow_html=True)
        
    with st.form("custom_weight_form_k200", border=False):
        c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 0.8])
        with c1: w1 = st.number_input("📉 1개월 가중치", value=-0.1, step=0.1, format="%.1f")
        with c2: w3 = st.number_input("📈 3개월 가중치", value=0.7, step=0.1, format="%.1f")
        with c3: w6 = st.number_input("📈 6개월 가중치", value=0.4, step=0.1, format="%.1f")
        with c4: w12 = st.number_input("📈 12개월 가중치", value=0.0, step=0.1, format="%.1f")
        with c5:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            apply_weights = st.form_submit_button("✅ 스코어 적용", use_container_width=True)
            
    st.markdown("<hr style='margin: 0px 0px 15px 0px;'>", unsafe_allow_html=True)
    
    c6, c7, _ = st.columns([1, 1, 1])
    with c6:
        years_list = sorted(list(set([m['투자연도'] for m in monthly_data])))
        min_y, max_y = min(years_list), max(years_list)
        start_year_c, end_year_c = st.slider("📅 테스트 기간 (연도)", min_y, max_y, (min_y, max_y), key='k_yr3')
    with c7:
        rank_c_start, rank_c_end = st.slider("🏅 매수 순위 범위 (커스텀 스코어 기준)", 1, 30, (1, 10), key='k_rnk3')

    if rank_c_start > rank_c_end:
        st.error("🚨 순위 범위가 잘못되었습니다.")
        st.stop()
        
    with st.spinner("커스텀 스코어 재계산 및 시뮬레이션 중..."):
        records_c = []
        for m in monthly_data:
            if not (start_year_c <= m['투자연도'] <= end_year_c): continue
            
            mult = 0.0 if (apply_timing_c and m['is_bad']) else 1.0
            is_invested = mult > 0.0
            
            df_calc = m['df_k200'].copy()
            df_calc['커스텀스코어'] = (df_calc['1개월(%)']*w1) + (df_calc['3개월(%)']*w3) + (df_calc['6개월(%)']*w6) + (df_calc['12개월(%)']*w12)
            
            target_group = df_calc.sort_values('커스텀스코어', ascending=False).iloc[rank_c_start-1 : rank_c_end]
            ret_target = (target_group['다음달수익률(%)'].mean() * mult) if not target_group.empty else 0.0
            
            records_c.append({
                '투자월': m['투자월'], 'invested': is_invested,
                f'🏅 커스텀 스코어 ({rank_c_start}~{rank_c_end}위)': ret_target
            })
            
        df_res_c = pd.DataFrame(records_c).fillna(0.0)
        
        if not df_res_c.empty:
            strategy_cols_c = [c for c in df_res_c.columns if c not in ['투자월', 'invested']]
            df_cum_c = (1 + df_res_c.set_index('투자월')[strategy_cols_c] / 100).cumprod() * 100
            first_m_str_c = (pd.to_datetime(df_res_c['투자월'].iloc[0]) - pd.DateOffset(months=1)).strftime('%Y-%m')
            df_cum_c.loc[first_m_str_c] = 100
            df_cum_c = df_cum_c.sort_index()

            st.markdown(f"### 📈 {start_year_c}년 ~ {end_year_c}년 누적 자산 성장 곡선 (Log Scale)")
            df_melt_c = df_cum_c.reset_index().melt(id_vars='투자월', var_name='전략', value_name='누적수익률')
            fig_c = px.line(df_melt_c, x='투자월', y='누적수익률', color='전략', log_y=True) 
            fig_c.update_layout(hovermode="x unified", dragmode="pan", xaxis_title="투자 기준 월", yaxis_title="누적 자산 (초기 자본 = 100)", margin=dict(l=0, r=0, t=20, b=0))
            st.plotly_chart(fig_c, use_container_width=True, config={'scrollZoom': True})

            st.markdown("#### 📊 전략 핵심 통계")
            stats_c = []
            total_months = len(df_res_c)
            invested_months = df_res_c['invested'].sum()
            invest_ratio = (invested_months / total_months) * 100 if total_months > 0 else 0

            col_name = strategy_cols_c[0]
            final_val = df_cum_c[col_name].iloc[-1]
            total_ret = final_val - 100
            years = total_months / 12
            cagr = ((final_val / 100) ** (1 / years) - 1) * 100 if final_val > 0 else -100.0
            
            if invested_months > 0:
                win_months = (df_res_c.loc[df_res_c['invested'], col_name] > 0).sum()
                win_rate = (win_months / invested_months) * 100
                avg_ret = df_res_c.loc[df_res_c['invested'], col_name].mean()
            else: win_rate = avg_ret = 0.0
            
            roll_max = df_cum_c[col_name].cummax()
            mdd = ((df_cum_c[col_name] / roll_max) - 1.0).min() * 100
            
            stats_c.append({"전략명": col_name, "CAGR (연평균)": f"{cagr:.1f}%", "총 누적수익률": f"{total_ret:,.1f}%", "MDD (최대낙폭)": f"{mdd:.1f}%", "투자월 비율": f"{invest_ratio:.1f}% ({invested_months}/{total_months}개월)", "월별 승률": f"{win_rate:.1f}% ({win_months}승)", "평균 수익률(투자월)": f"{avg_ret:.2f}%"})
            
            df_stats_c = pd.DataFrame(stats_c)
            try: styled_stats_c = df_stats_c.style.map(style_stats, subset=['CAGR (연평균)', '총 누적수익률', 'MDD (최대낙폭)'])
            except AttributeError: styled_stats_c = df_stats_c.style.applymap(style_stats, subset=['CAGR (연평균)', '총 누적수익률', 'MDD (최대낙폭)'])
            st.dataframe(styled_stats_c, use_container_width=True, hide_index=True)

            with st.expander(f"📝 {start_year_c}~{end_year_c}년 ({total_months}개월) 월별 수익률 상세 기록 보기"):
                display_df_c = df_res_c.drop(columns=['invested']).set_index('투자월')
                st.dataframe(display_df_c.style.format("{:.2f}%"), use_container_width=True)
