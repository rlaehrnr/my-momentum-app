import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import os
import glob
from datetime import datetime, timedelta
import plotly.express as px
import numpy as np

# --- [1. 페이지 설정 및 CSS] ---
st.set_page_config(page_title="한국 모멘텀 기록보관소", layout="wide")

st.markdown("""
    <style>
    .block-container { padding-top: 2.8rem !important; padding-bottom: 1rem !important; }
    h1 { font-size: 2.2rem !important; font-weight: 800; margin-bottom: 10px; }
    .strategy-desc { font-size: 0.85rem; color: #9ca3af; margin-bottom: 10px; line-height: 1.2; }
    
    /* 💡 가로형 라디오 버튼 간격 조절 */
    div[role="radiogroup"] { gap: 15px !important; flex-wrap: wrap; }
    
    @media (max-width: 768px) {
        div[data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
            min-width: 45% !important; flex: 1 1 45% !important; margin-bottom: 5px !important;
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
def apply_kr_styling(row, highlight_codes=None, overlap_codes=None):
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

@st.cache_data(show_spinner=False)
def load_all_archive_data():
    folder, prefix = "archive", "momentum_"
    files = glob.glob(f"{folder}/{prefix}*.csv")
    if not files: return pd.DataFrame()
    
    all_dfs = []
    for f in files:
        df = pd.read_csv(f, dtype={'종목코드': str})
        fname = os.path.basename(f)
        date_part = fname.replace(prefix, "").replace(".csv", "")
        year, month = date_part.split('_')
        
        df['투자연도'] = int(year)
        df['투자월_숫자'] = int(month)
        df['YearMonth'] = f"{year}-{month.zfill(2)}"
        if '종목코드' in df.columns:
            df['종목코드'] = df['종목코드'].astype(str).str.strip().str.zfill(6)
        
        num_cols = ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '다음달수익률(%)', '모멘텀스코어']
        for c in num_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
        all_dfs.append(df)
    return pd.concat(all_dfs, ignore_index=True)

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
        ma_values = {
            '지수_L': "https://m.stock.naver.com/domestic/index/KOSPI/total#KOSPI", 
            '현재가_L': f"https://m.stock.naver.com/fchart/domestic/index/KOSPI#{curr_price:,.2f}", 
            'base_price': round(curr_price, 2),
            '4개월선': round(df['Close'].rolling(80).mean().iloc[-1], 2),
            '5개월선': round(df['Close'].rolling(100).mean().iloc[-1], 2),
            '6개월선': round(df['Close'].rolling(120).mean().iloc[-1], 2),
            '10개월선': round(df['Close'].rolling(200).mean().iloc[-1], 2),
            '12개월선': round(df['Close'].rolling(240).mean().iloc[-1], 2)
        }
        return pd.DataFrame([ma_values])
    except: return pd.DataFrame()

@st.cache_data(show_spinner=False)
def get_kospi_timing(ma_months):
    ks11 = fdr.DataReader('KS11', '2005-01-01') 
    ma_days = ma_months * 20 
    ks11['MA'] = ks11['Close'].rolling(ma_days).mean()
    ks11['YearMonth'] = ks11.index.to_period('M').astype(str)
    timing_df = ks11.resample('ME').last()
    timing_df['is_below_ma'] = timing_df['Close'] < timing_df['MA']
    return timing_df.set_index('YearMonth')

def style_kospi_ma(df):
    def apply_color(row):
        price = row['base_price']
        styles = [''] * len(row)
        for i, col in enumerate(row.index):
            if '개월선' in col:
                val = row[col]
                if pd.notna(val) and price > val: styles[i] = 'color: #EF4444; font-weight: bold;' 
                elif pd.notna(val) and price < val: styles[i] = 'color: #3B82F6; font-weight: bold;' 
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

# --- [3. 메인 앱 시작] ---
st.markdown('''
    <div style="margin-bottom: 20px;">
        <a href="https://stock.naver.com/" target="_blank" class="title-link" style="text-decoration: none; color: inherit;">
            <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 12px;">
                <h1 style="margin: 0; padding: 0; font-size: 2.2rem; font-weight: 800; line-height: 1.2; word-break: keep-all;">📁 한국 전체 모멘텀 월별 기록</h1>
                <span style="font-size: 0.95rem; color: #3b82f6; background-color: #eff6ff; padding: 4px 10px; border-radius: 6px; border: 1px solid #bfdbfe; white-space: nowrap;">🔗 네이버 증권 이동</span>
            </div>
        </a>
    </div>
''', unsafe_allow_html=True)

df_master = load_all_archive_data()

if df_master.empty:
    st.info("데이터가 없습니다. archive 폴더에 'momentum_YYYY_MM.csv' 파일들을 넣어주세요.")
    st.stop()

tab_detail, tab_summary, tab_custom = st.tabs(["📅 월별 상세 분석", "📈 전략조합 장기 백테스트", "🏅 스코어 커스텀 백테스트"])

# ==========================================
# 탭 1: 월별 상세 분석
# ==========================================
with tab_detail:
    sorted_years = sorted(df_master['투자연도'].unique().astype(str), reverse=True)
    
    # 💡 [핵심] 연도는 드롭다운(수정불가), 월은 가로형 라디오버튼으로 배치!
    col_y, col_info = st.columns([2, 8])
    with col_y: 
        selected_year = st.selectbox("📅 투자 연도", sorted_years, key='y_detail', format_func=lambda x: f"{x}년")
    
    available_months = sorted(df_master[df_master['투자연도'] == int(selected_year)]['투자월_숫자'].unique())
    
    df_monthly = df_master[(df_master['투자연도'] == int(selected_year))].copy()
    
    target_date_temp = df_monthly['YearMonth'].iloc[0]
    with col_info:
        # 날짜 임시 표기 (월 선택 후 정확해짐)
        pass 
        
    st.markdown("<div style='margin-bottom: 5px;'></div>", unsafe_allow_html=True)
    selected_month = st.radio("🌙 투자 월 선택", available_months, horizontal=True, key='m_detail', format_func=lambda x: f"{x}월")
    
    df_monthly = df_monthly[df_monthly['투자월_숫자'] == int(selected_month)].copy()
    
    # 💡 데이터 기준일 추출
    target_date_str = df_monthly['기준일(월말)'].iloc[0] if '기준일(월말)' in df_monthly.columns else (datetime(int(selected_year), int(selected_month), 1) - timedelta(days=1)).strftime('%Y-%m-%d')
    
    with col_info:
        st.markdown(f"<div style='margin-top: 32px; text-align: right; color: #9ca3af; font-size: 0.95rem;'>💡 <b>데이터 기준일:</b> {target_date_str}</div>", unsafe_allow_html=True)

    kospi_ma_df = get_kospi_ma_status(target_date_str)
    kospi_curr = kospi_ma_df['base_price'].iloc[0] if not kospi_ma_df.empty else 0
    kospi_4m_ma = kospi_ma_df['4개월선'].iloc[0] if not kospi_ma_df.empty else 0

    if not kospi_ma_df.empty:
        st.dataframe(style_kospi_ma(kospi_ma_df), use_container_width=True, hide_index=True, 
                     column_order=["지수_L", "현재가_L", "4개월선", "5개월선", "6개월선", "10개월선", "12개월선"],
                     column_config=kospi_ma_config)

    st.markdown("<br>", unsafe_allow_html=True)

    kospi_1m, kospi_3m = get_idx_kr(target_date_str)
    neg_1m_cnt = (df_monthly['1개월(%)'] < 0).sum()
    neg_3m_cnt = (df_monthly['3개월(%)'] < 0).sum()

    base_dt = pd.to_datetime(target_date_str)
    target_year = int(selected_year)
    target_month_num = int(selected_month)
    cycle_year = get_cycle_year(target_year)
    bad_months_this_year = PRESIDENTIAL_DANGEROUS_MONTHS.get(cycle_year, [])
    bad_m_str = ", ".join(f"{m}월" for m in bad_months_this_year) if bad_months_this_year else "없음"

    # 💡 [핵심] 하락 개수 무시, 4개월선 위만 무조건 투자 진행!
    is_below_4m_ma = (kospi_curr > 0) and (kospi_curr < kospi_4m_ma)

    if is_below_4m_ma:
        invest_status = "🛑 투자 중지"
        box_color, text_color = "#FFEBEE", "#C62828"
        status_desc = "4개월선 이탈"
    else:
        invest_status = "✅ 투자 진행"
        box_color, text_color = "#E8F5E9", "#2E7D32"
        status_desc = "4개월선 위"

    col1, col2, col3, col4, col5, col6 = st.columns([0.9, 0.9, 1.0, 1.0, 1.4, 1.6])
    with col1: st.metric(label="📈 KOSPI 1M", value=f"{kospi_1m}%")
    with col2: st.metric(label="📈 KOSPI 3M", value=f"{kospi_3m}%")
    with col3: st.metric(label="📉 1개월 하락", value=f"{neg_1m_cnt}개")
    with col4: st.metric(label="📉 3개월 하락", value=f"{neg_3m_cnt}개")
    with col5:
        st.markdown(f'<div style="background-color: #f0f2f6; padding: 10px; border-radius: 10px; text-align: center; border: 1px solid #d1d5db; height: 100%; min-height: 95px; display: flex; flex-direction: column; justify-content: center;"><div style="font-size: 13px; font-weight: bold; color: #333; margin-bottom: 4px;">🇺🇸대통령 <span style="color:#0047AB; font-size:14px;">{get_cycle_year(int(selected_year))}년차</span> ({selected_year}년)</div><div style="font-size: 13px; font-weight: bold; color: #D84315;">위험달: {bad_m_str}</div></div>', unsafe_allow_html=True)
    with col6:
        st.markdown(f'<div style="background-color: {box_color}; padding: 10px; border-radius: 10px; text-align: center; border: 1px solid {text_color}; display: flex; flex-direction: column; justify-content: center; height: 100%; min-height: 95px;"><p style="margin: 0; font-size: 12px; color: {text_color}; font-weight: bold;">당시 최종 판단 ({status_desc})</p><div style="margin: 4px 0 0 0; font-size: 1.5rem; font-weight: 900; color: {text_color};">{invest_status}</div></div>', unsafe_allow_html=True)
        
    st.markdown("<hr style='margin: 1rem 0;'>", unsafe_allow_html=True)

    def make_links(r):
        m = str(r.get('시장', 'KOSPI'))
        m_tag = "KOSDAQ" if "코스닥" in m or "KOSDAQ" in m.upper() else "KOSPI"
        t_url = f"https://finance.naver.com/item/main.naver?code={r['종목코드']}#{m_tag}:{r['종목코드']}"
        n_url = f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드']}#{r['종목명']}"
        return pd.Series([t_url, n_url])

    q30 = {c: df_monthly[c].quantile(0.7) for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']}
    t10_1m = df_monthly['1개월(%)'].quantile(0.9)

    df_perf = df_monthly[(df_monthly['1개월(%)']>=q30['1개월(%)'])&(df_monthly['3개월(%)']>=q30['3개월(%)'])&(df_monthly['6개월(%)']>=q30['6개월(%)'])&(df_monthly['12개월(%)']>=q30['12개월(%)']) & (df_monthly['1개월(%)']>0)].sort_values('3개월(%)', ascending=False).copy()
    df_spec = df_monthly[(df_monthly['12개월(%)']>=q30['12개월(%)']) & (df_monthly['1개월(%)']>=t10_1m)].sort_values('1개월(%)', ascending=False).copy()

    top30_perf = df_perf.head(30)['종목코드'].tolist()
    top30_spec = df_spec.head(30)['종목코드'].tolist()
    overlap_30 = set(top30_perf).intersection(set(top30_spec))

    df_monthly[['티커_L', '종목명_L']] = df_monthly.apply(make_links, axis=1)
    df_perf[['티커_L', '종목명_L']] = df_perf.apply(make_links, axis=1)
    df_spec[['티커_L', '종목명_L']] = df_spec.apply(make_links, axis=1)
    
    df_monthly.index = range(1, len(df_monthly) + 1)
    
    main_cfg = {
        "티커_L": st.column_config.LinkColumn("티커", display_text=r"#(.+)"),
        "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"),
        "기준가": st.column_config.NumberColumn(format="%,d"),
        "모멘텀스코어": st.column_config.NumberColumn("모멘텀스코어", format="%.2f"),
        "1개월(%)": st.column_config.NumberColumn(format="%.2f"),
        "3개월(%)": st.column_config.NumberColumn(format="%.2f"),
        "6개월(%)": st.column_config.NumberColumn(format="%.2f"),
        "12개월(%)": st.column_config.NumberColumn(format="%.2f"),
        "다음달수익률(%)": st.column_config.NumberColumn(f"{target_month_num}월 수익률(%)", format="%.2f %%")
    }

    c_left, c_right = st.columns(2)
    with c_left:
        st.markdown(get_perf_html("🔥 퍼펙트 상승", df_perf, target_month_num), unsafe_allow_html=True)
        st.markdown('<p class="strategy-desc">1, 3, 6, 12개월 수익률이 모두 상위 30% 이내이며 0보다 큰 종목 (3개월 수익률 순)</p>', unsafe_allow_html=True)
        st.dataframe(df_perf.style.apply(apply_kr_styling, highlight_codes=top30_perf, overlap_codes=overlap_30, axis=1), use_container_width=True, hide_index=True, column_order=['티커_L', '종목명_L', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '다음달수익률(%)'], column_config=main_cfg)
    with c_right:
        st.markdown(get_perf_html("🐎 달리는 말", df_spec, target_month_num), unsafe_allow_html=True)
        st.markdown('<p class="strategy-desc">12개월 수익률이 상위 30% 이내이며 1개월 수익률이 상위 10% 이내인 종목 (1개월 수익률 순)</p>', unsafe_allow_html=True)
        st.dataframe(df_spec.style.apply(apply_kr_styling, highlight_codes=top30_spec, overlap_codes=overlap_30, axis=1), use_container_width=True, hide_index=True, column_order=['티커_L', '종목명_L', '1개월(%)', '12개월(%)', '다음달수익률(%)'], column_config=main_cfg)

    st.markdown("---")
    st.subheader("🏆 전체 종목 모멘텀 순위")
    st.dataframe(df_monthly.sort_values('모멘텀스코어', ascending=False).style.map(lambda x: 'color: #FF4B4B; font-weight: bold;' if x > 0 else ('color: #3182CE; font-weight: bold;' if x < 0 else ''), subset=['다음달수익률(%)']), use_container_width=True, height=500, hide_index=True, column_order=['시장', '티커_L', '종목명_L', '기준가', '모멘텀스코어', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '다음달수익률(%)'], column_config=main_cfg)

# ==========================================
# 탭 2: 전략조합 장기 백테스트
# ==========================================
with tab_summary:
    st.markdown("<h4 style='margin-top: 5px; margin-bottom: 0px;'>⚙️ 시뮬레이션 설정</h4>", unsafe_allow_html=True)
    
    c1, c_ma, c_chk = st.columns([1, 1, 1.5])
    with c1: start_year, end_year = st.slider("📅 테스트 기간 (연도)", min_y, max_y, (min_y, max_y), key='year_tab2')
    with c_ma: ma_months_t2 = st.slider("📉 마켓타이밍 (개월선)", 1, 12, 4, key='ma_t2')
    with c_chk:
        st.markdown("<div style='margin-top: 35px;'></div>", unsafe_allow_html=True)
        apply_timing = st.checkbox("🛑 마켓타이밍 적용 (선택 이평선 이탈 시 현금 100%)", value=True, key='timing_tab2')

    st.markdown("<hr style='margin: 10px 0px;'>", unsafe_allow_html=True)
    st.markdown("##### 🔥 전략 상세 조건 필터")
    
    # 💡 [핵심] 상위 % 조건을 마음대로 바꿀 수 있는 슬라이더 장착!
    c2, c3, c4, c5 = st.columns([1, 1, 1, 1])
    with c2: perf_pct = st.slider("🔥 퍼펙트 상승 (1,3,6,12M 상위 %)", 5, 50, 30, step=5)
    with c3: rank_1_start, rank_1_end = st.slider("🔥 퍼펙트 상승 (매수 순위)", 1, 30, (4, 9))
    with c4: spec_12m_pct = st.slider("🐎 달리는 말 (12M 상위 %, 1M은 10%)", 5, 50, 30, step=5)
    with c5: rank_2_start, rank_2_end = st.slider("🐎 달리는 말 (매수 순위)", 1, 30, (5, 10))
        
    if rank_1_start > rank_1_end or rank_2_start > rank_2_end:
        st.error("🚨 순위 범위가 잘못되었습니다.")
        st.stop()
    
    with st.spinner("수익률 계산 중..."):
        timing_df_t2 = get_kospi_timing(ma_months_t2)
        months = [m for m in sorted(df_master['YearMonth'].unique()) if start_year <= int(m[:4]) <= end_year]
        records = []
        for m in months:
            m_data = df_master[df_master['YearMonth'] == m]
            base_dt = pd.to_datetime(m); inv_dt = base_dt + pd.DateOffset(months=1); inv_str = inv_dt.strftime('%Y-%m')
            
            is_below_ma = timing_df_t2.loc[m, 'is_below_ma'] if m in timing_df_t2.index else False
            mult = 0.0 if (apply_timing and is_below_ma) else 1.0
            
            # 💡 [핵심] 설정된 상위 % 슬라이더 값을 동적으로 계산에 적용
            q_perf = 1.0 - (perf_pct / 100.0)
            q_spec = 1.0 - (spec_12m_pct / 100.0)
            
            q_val_1 = m_data['1개월(%)'].quantile(q_perf)
            q_val_3 = m_data['3개월(%)'].quantile(q_perf)
            q_val_6 = m_data['6개월(%)'].quantile(q_perf)
            q_val_12 = m_data['12개월(%)'].quantile(q_perf)
            
            t_val_12 = m_data['12개월(%)'].quantile(q_spec)
            t_val_1 = m_data['1개월(%)'].quantile(0.9) # 1개월은 상위 10% 고정
            
            cond_p = (m_data['1개월(%)']>=q_val_1)&(m_data['3개월(%)']>=q_val_3)&(m_data['6개월(%)']>=q_val_6)&(m_data['12개월(%)']>=q_val_12)&(m_data['1개월(%)']>0)
            cond_s = (m_data['12개월(%)']>=t_val_12)&(m_data['1개월(%)']>=t_val_1)
            
            df_p = m_data[cond_p].sort_values('3개월(%)', ascending=False)
            df_s = m_data[cond_s].sort_values('1개월(%)', ascending=False)
            
            overlap_1 = df_p.iloc[rank_1_start-1 : rank_1_end]
            overlap_2 = df_s.iloc[rank_2_start-1 : rank_2_end]
            
            ret_1 = (overlap_1['다음달수익률(%)'].mean() * mult) if not overlap_1.empty else 0.0
            ret_2 = (overlap_2['다음달수익률(%)'].mean() * mult) if not overlap_2.empty else 0.0
            
            records.append({'투자월': inv_str, 'invested': (mult > 0), f'🔥 퍼펙트 상승 ({rank_1_start}~{rank_1_end}위)': ret_1, f'🐎 달리는 말 ({rank_2_start}~{rank_2_end}위)': ret_2, '앙상블 (전략 50:50)': (ret_1 + ret_2) / 2})
            
        df_res = pd.DataFrame(records).fillna(0.0)
        if not df_res.empty:
            strategy_cols = [c for c in df_res.columns if c not in ['투자월', 'invested']]
            df_cum = (1 + df_res.set_index('투자월')[strategy_cols] / 100).cumprod() * 100
            df_cum.loc[(pd.to_datetime(df_res['투자월'].iloc[0]) - pd.DateOffset(months=1)).strftime('%Y-%m')] = 100
            df_cum = df_cum.sort_index()

            st.markdown(f"### 📈 누적 수익률 곡선 (마켓타이밍: KOSPI {ma_months_t2}개월선)")
            df_melt = df_cum.reset_index().melt(id_vars='투자월', var_name='전략', value_name='누적수익률')
            fig = px.line(df_melt, x='투자월', y='누적수익률', color='전략', log_y=True)
            fig.update_layout(hovermode="x unified", dragmode="pan", xaxis_title="투자 기준 월", yaxis_title="누적 자산 (로그스케일)", margin=dict(l=0, r=0, t=20, b=0))
            st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})
            
            st.markdown("#### 📊 전략별 핵심 통계 (초기 자본 100 기준)")
            stats = []
            total_months = len(df_res)
            invested_months = df_res['invested'].sum()
            invest_ratio = (invested_months / total_months) * 100 if total_months > 0 else 0

            for col in strategy_cols:
                final_val = df_cum[col].iloc[-1]
                total_ret = final_val - 100
                years = total_months / 12
                cagr = ((final_val / 100) ** (1 / years) - 1) * 100 if final_val > 0 else -100.0
                
                if invested_months > 0:
                    win_months = (df_res.loc[df_res['invested'], col] > 0).sum()
                    win_rate = (win_months / invested_months) * 100
                    avg_ret = df_res.loc[df_res['invested'], col].mean()
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
                display_df = df_res.drop(columns=['invested']).set_index('투자월')
                st.dataframe(display_df.style.format("{:.2f}%"), use_container_width=True)

# ==========================================
# 탭 3: 모멘텀 스코어 커스텀 백테스트
# ==========================================
with tab_custom:
    col_title, col_check = st.columns([1, 4])
    with col_title: st.markdown("<h4 style='margin-top: 5px; margin-bottom: 0px;'>⚙️ 스코어 가중치</h4>", unsafe_allow_html=True)
    with col_check: st.markdown("<div style='margin-top: 8px;'>", unsafe_allow_html=True); apply_timing_c = st.checkbox("🛑 마켓타이밍 적용", value=True, key='timing_tab3'); st.markdown("</div>", unsafe_allow_html=True)
    
    with st.form("custom_weight_form", border=False):
        c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 0.8])
        # 💡 [핵심복구] 소수점 1자리(%.1f) 표시
        with c1: w1 = st.number_input("📉 1M 가중치", value=0.2, step=0.1, format="%.1f")
        with c2: w3 = st.number_input("📈 3M 가중치", value=0.8, step=0.1, format="%.1f")
        with c3: w6 = st.number_input("📈 6M 가중치", value=0.0, step=0.1, format="%.1f")
        with c4: w12 = st.number_input("📈 12M 가중치", value=0.0, step=0.1, format="%.1f")
        with c5: st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True); apply_weights = st.form_submit_button("✅ 스코어 적용", use_container_width=True)
            
    st.markdown("<hr style='margin: 0px 0px 15px 0px;'>", unsafe_allow_html=True)
    
    c6, c_ma_c, c7 = st.columns([1, 1, 1])
    with c6: start_year_c, end_year_c = st.slider("📅 테스트 기간 (연도)", min_y, max_y, (min_y, max_y), key='year_tab3')
    with c_ma_c: ma_months_t3 = st.slider("📉 마켓타이밍 (개월선) ", 1, 12, 4, key='ma_t3')
    with c7: rank_c_start, rank_c_end = st.slider("🏅 매수 순위 범위 ", 1, 50, (1, 10))

    with st.spinner("계산 중..."):
        timing_df_t3 = get_kospi_timing(ma_months_t3)
        df_calc = df_master.copy()
        df_calc['CustomScore'] = (df_calc['1개월(%)']*w1) + (df_calc['3개월(%)']*w3) + (df_calc['6개월(%)']*w6) + (df_calc['12개월(%)']*w12)
        
        months_c = [m for m in sorted(df_calc['YearMonth'].unique()) if start_year_c <= int(m[:4]) <= end_year_c]
        records_c = []
        for m in months_c:
            m_data = df_calc[df_calc['YearMonth'] == m]; inv_str = (pd.to_datetime(m) + pd.DateOffset(months=1)).strftime('%Y-%m')
            is_below_ma = timing_df_t3.loc[m, 'is_below_ma'] if m in timing_df_t3.index else False
            mult = 0.0 if (apply_timing_c and is_below_ma) else 1.0
            target_group = m_data.sort_values('CustomScore', ascending=False).iloc[rank_c_start-1 : rank_c_end]
            records_c.append({'투자월': inv_str, 'invested': (mult > 0), f'🏅 커스텀 스코어 ({rank_c_start}~{rank_c_end}위)': (target_group['다음달수익률(%)'].mean() * mult) if not target_group.empty else 0.0})
            
        df_res_c = pd.DataFrame(records_c).fillna(0.0)
        if not df_res_c.empty:
            strategy_cols_c = [c for c in df_res_c.columns if c not in ['투자월', 'invested']]
            df_cum_c = (1 + df_res_c.set_index('투자월')[strategy_cols_c] / 100).cumprod() * 100
            df_cum_c.loc[(pd.to_datetime(df_res_c['투자월'].iloc[0]) - pd.DateOffset(months=1)).strftime('%Y-%m')] = 100
            
            st.markdown(f"### 📈 커스텀 스코어 누적 수익률 (마켓타이밍: KOSPI {ma_months_t3}개월선)")
            df_melt_c = df_cum_c.reset_index().melt(id_vars='투자월', var_name='전략', value_name='누적수익률')
            fig_c = px.line(df_melt_c, x='투자월', y='누적수익률', color='전략', log_y=True) 
            fig_c.update_layout(hovermode="x unified", dragmode="pan", xaxis_title="투자 기준 월", yaxis_title="누적 자산 (로그스케일)", margin=dict(l=0, r=0, t=20, b=0))
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

            with st.expander("📝 월별 상세 수익률 보기"):
                display_df_c = df_res_c.drop(columns=['invested']).set_index('투자월')
                st.dataframe(display_df_c.style.format("{:.2f}%"), use_container_width=True)
