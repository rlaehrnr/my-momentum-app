import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- [1. 설정 및 스타일] ---
st.set_page_config(page_title="KOSPI 200 강세 종목", layout="wide")

st.markdown("""
    <style>
    .block-container { padding-top: 3.5rem !important; }
    .main-title { font-size: 1.6rem !important; font-weight: bold; margin-bottom: 1rem; }
    .stTabs [data-baseweb="tab"] { font-size: 18px; font-weight: bold; }
    
    @media (max-width: 768px) {
        div[data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
        }
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
            min-width: 45% !important; 
            flex: 1 1 45% !important;
            margin-bottom: 10px !important;
        }
    }
    
    /* 제목 링크 호버 액션 */
    .title-link:hover { opacity: 0.7; transition: 0.2s; }
    /* 수익률 링크 호버 액션 */
    .return-link:hover { opacity: 0.6; }
    
    /* 컬럼 헤더 줄바꿈 허용 (날짜 표시용) */
    th[data-testid="stTableColumnHeader"] div {
        white-space: pre-wrap !important;
        text-align: center !important;
    }
    </style>
""", unsafe_allow_html=True)

PRESIDENTIAL_DANGEROUS_MONTHS = {
    1: [2, 9], 2: [1, 2, 4, 5, 6, 9], 3: [9], 4: [3],
    5: [3], 6: [7], 7: [8, 9, 10, 11], 8: [1, 9, 10, 11]
}

def get_cycle_year(year):
    return ((year - 2021) % 8) + 1

def apply_k200_styling(row, idx_df, highlight_codes=None, overlap_codes=None):
    styles = [''] * len(row)
    market = row.get('시장', 'KOSPI')
    if isinstance(idx_df, pd.DataFrame) and market in idx_df.index:
        idx_r = idx_df.loc[market]
        for col in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
            if col in row.index and col in idx_r.index:
                col_idx = row.index.get_loc(col)
                if row[col] < idx_r[col]:
                    styles[col_idx] = 'background-color: #E3F2FD; color: #0047AB;'
                    
    code = row.get('종목코드')
    if code and '종목명_L' in row.index:
        name_idx = row.index.get_loc('종목명_L')
        if overlap_codes and code in overlap_codes:
            styles[name_idx] = 'background-color: #FFF59D; color: #D84315; font-weight: bold;'
        elif highlight_codes and code in highlight_codes:
            styles[name_idx] = 'background-color: #E8F5E9; color: #2E7D32; font-weight: bold;'
            
    return styles

@st.cache_data(ttl=3600)
def get_idx_kr(target_date=None):
    indices = {'KOSPI': 'KS11', 'KOSDAQ': 'KQ11'}
    today = datetime.today()
    res = []
    for name, code in indices.items():
        try:
            df = fdr.DataReader(code, today - pd.DateOffset(months=18), today)
            curr_val = df.loc[df.index <= target_date]['Close'].iloc[-1] if target_date else df['Close'].iloc[-1]
            last_date = df.index[df.index <= (target_date if target_date else today)][-1]
            def get_ret(m):
                ref = (last_date.replace(day=1) - pd.DateOffset(months=m-1)) - timedelta(days=1)
                p_df = df[df.index <= ref]
                return round(((curr_val / p_df['Close'].iloc[-1]) - 1) * 100, 1) if not p_df.empty else 0.0
            res.append({'시장': name, '현재가': curr_val, '1개월(%)': get_ret(1), '3개월(%)': get_ret(3), '6개월(%)': get_ret(6), '12개월(%)': get_ret(12)})
        except: pass
    return pd.DataFrame(res).set_index('시장')

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

@st.cache_data(ttl=300, show_spinner=False)
def fetch_current_prices_fast(tickers):
    prices = {}
    def get_price(t):
        try:
            yf_t = str(t).zfill(6) + ".KS"
            hist = yf.Ticker(yf_t).history(period="1d")
            if not hist.empty:
                return t, int(hist['Close'].iloc[-1])
        except: pass
        return t, 0

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(get_price, t) for t in tickers]
        for f in as_completed(futures):
            t, p = f.result()
            if p > 0:
                prices[t] = p
    return prices

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

main_cfg = {
    "통합티커_L": st.column_config.LinkColumn("티커", display_text=r"#(.+)"), 
    "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), 
    "기준가": st.column_config.NumberColumn("종가", format="%,d"),
    "1개월(%)": st.column_config.NumberColumn(format="%.1f"), 
    "3개월(%)": st.column_config.NumberColumn(format="%.1f"), 
    "6개월(%)": st.column_config.NumberColumn(format="%.1f"), 
    "12개월(%)": st.column_config.NumberColumn(format="%.1f"),
    "모멘텀스코어": st.column_config.NumberColumn("스코어", format="%.2f"),
    "전달순위": st.column_config.NumberColumn("전달 순위", format="%d위"),
    "전일거래량": st.column_config.NumberColumn("거래량", format="%,d") 
}

def render_kospi200_dashboard(df_raw, b_date_str, is_daily=False):
    st.markdown(f'<p class="main-title">🎯 KOSPI 200 집중 분석 (기준: {b_date_str})</p>', unsafe_allow_html=True)
    
    kospi_ma_df = get_kospi_ma_status(b_date_str)
    kospi_curr = 0
    kospi_4m_ma = 0
    
    if not kospi_ma_df.empty:
        st.dataframe(style_kospi_ma(kospi_ma_df), use_container_width=True, hide_index=True, 
                     column_order=["지수_L", "현재가_L", "4개월선", "5개월선", "6개월선", "10개월선", "12개월선"],
                     column_config=kospi_ma_config)
        kospi_curr = kospi_ma_df['base_price'].iloc[0]
        kospi_4m_ma = kospi_ma_df['4개월선'].iloc[0]
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    idx_k = get_idx_kr(pd.to_datetime(b_date_str))
    kospi_1m = idx_k.loc['KOSPI', '1개월(%)'] if 'KOSPI' in idx_k.index else 0.0
    kospi_3m = idx_k.loc['KOSPI', '3개월(%)'] if 'KOSPI' in idx_k.index else 0.0

    df_k200 = df_raw[df_raw['시장'] == 'KOSPI'].copy() if '시장' in df_raw.columns else df_raw.copy()
    df_k200['종목코드'] = df_k200['종목코드'].astype(str).str.zfill(6)
    df_k200 = df_k200[df_k200['종목코드'].str.endswith('0')].copy()
    
    if '시가총액' in df_k200.columns:
        df_k200['시가총액'] = pd.to_numeric(df_k200['시가총액'], errors='coerce').fillna(0)
        if df_k200['시가총액'].max() > 10**10:
            df_k200['시가총액'] = (df_k200['시가총액'] / 100000000).astype(int)
        else:
            df_k200['시가총액'] = df_k200['시가총액'].astype(int)
    else:
        df_k200['시가총액'] = 0

    df_k200 = df_k200.sort_values(by='시가총액', ascending=False).head(200)
    df_k200.index = range(1, len(df_k200) + 1)
    
    df_k200['통합티커_L'] = df_k200.apply(lambda r: f"https://finance.naver.com/item/main.naver?code={r['종목코드']}#KOSPI:{r['종목코드']}", axis=1)
    df_k200['종목명_L'] = df_k200.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드']}#{r['종목명']}", axis=1)

    neg_1m_cnt = (df_k200['1개월(%)'] < 0).sum()
    neg_3m_cnt = (df_k200['3개월(%)'] < 0).sum()
    
    base_dt = pd.to_datetime(b_date_str)
    target_dt = base_dt + pd.DateOffset(months=1) if not is_daily else base_dt
    target_year, target_month = target_dt.year, target_dt.month
    
    cycle_year = get_cycle_year(target_year)
    bad_months = PRESIDENTIAL_DANGEROUS_MONTHS.get(cycle_year, [])
    bad_m_str = ", ".join(f"{m}월" for m in bad_months) if bad_months else "없음"

    is_bad_market = (neg_1m_cnt >= 100) and (neg_3m_cnt >= 100)
    is_below_4m_ma = (kospi_curr < kospi_4m_ma) if kospi_curr > 0 else False
    
    reasons = []
    if is_bad_market: reasons.append("하락장(1,3M 100개↑)")
    if is_below_4m_ma: reasons.append("KOSPI 4개월선 이탈")

    if reasons:
        invest_status, box_color, text_color = "🛑 투자 중지", "#FFEBEE", "#C62828"
        status_desc = " + ".join(reasons)
    else:
        invest_status, box_color, text_color = "✅ 투자 진행", "#E8F5E9", "#2E7D32"
        status_desc = "상승장 & 4개월선 위"

    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3, col4, col5, col6 = st.columns([0.9, 0.9, 1.0, 1.0, 1.4, 1.6])
    with col1: st.metric(label="📈 KOSPI 1M", value=f"{kospi_1m}%")
    with col2: st.metric(label="📈 KOSPI 3M", value=f"{kospi_3m}%")
    with col3: st.metric(label="📉 1개월 하락", value=f"{neg_1m_cnt}개")
    with col4: st.metric(label="📉 3개월 하락", value=f"{neg_3m_cnt}개")
    with col5:
        st.markdown(f'<div style="background-color: #f0f2f6; padding: 12px 10px; border-radius: 10px; text-align: center; border: 1px solid #d1d5db; height: 100%;"><div style="font-size: 13px; font-weight: bold; color: #333; margin-bottom: 5px;">🇺🇸대통령 <span style="color:#0047AB; font-size:15px;">{cycle_year}년차</span> ({target_year}년)</div><div style="font-size: 13px; font-weight: bold; color: #D84315;">위험달: {bad_m_str}</div></div>', unsafe_allow_html=True)
    with col6:
        st.markdown(f'<div style="background-color: {box_color}; padding: 10px; border-radius: 10px; text-align: center; border: 1px solid {text_color};"><p style="margin: 0; font-size: 12px; color: {text_color}; font-weight: bold;">최종 판단 ({status_desc})</p><h3 style="margin: 3px 0 0 0; color: {text_color};">{invest_status}</h3></div>', unsafe_allow_html=True)
        
    st.markdown("<br><hr>", unsafe_allow_html=True)

    q30 = {c: df_k200[c].quantile(0.7) for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']}
    t10_1m = df_k200['1개월(%)'].quantile(0.9)
    cond_perf = (df_k200['1개월(%)']>=q30['1개월(%)'])&(df_k200['3개월(%)']>=q30['3개월(%)'])&(df_k200['6개월(%)']>=q30['6개월(%)'])&(df_k200['12개월(%)']>=q30['12개월(%)']) & (df_k200['1개월(%)']>0)&(df_k200['3개월(%)']>0)&(df_k200['6개월(%)']>0)&(df_k200['12개월(%)']>0)
    
    df_perf = df_k200[cond_perf].sort_values('3개월(%)', ascending=False).copy()
    df_spec = df_k200[(df_k200['12개월(%)']>=q30['12개월(%)']) & (df_k200['1개월(%)']>=t10_1m)].sort_values('1개월(%)', ascending=False).copy()
    
    top5_perf = df_perf.head(5)['종목코드'].tolist()
    top5_spec = df_spec.head(5)['종목코드'].tolist()
    overlap_top5 = set(top5_perf).intersection(set(top5_spec))

    # 💡 [핵심] 1, 3, 6, 12개월 전 기준 날짜 계산 함수
    def get_ref_str(m):
        ref_dt = (base_dt.replace(day=1) - pd.DateOffset(months=m-1)) - timedelta(days=1)
        return ref_dt.strftime('%y.%m.%d')

    k_cfg = main_cfg.copy()
    k_cfg['시가총액'] = st.column_config.NumberColumn("시가총액(억)", format="%,d")
    
    # 💡 [신규] 컬럼 헤더에 기준 날짜(YY.MM.DD) 추가 반영
    k_cfg['1개월(%)'] = st.column_config.NumberColumn(f"1개월(%)\n({get_ref_str(1)})", format="%.1f")
    k_cfg['3개월(%)'] = st.column_config.NumberColumn(f"3개월(%)\n({get_ref_str(3)})", format="%.1f")
    k_cfg['6개월(%)'] = st.column_config.NumberColumn(f"6개월(%)\n({get_ref_str(6)})", format="%.1f")
    k_cfg['12개월(%)'] = st.column_config.NumberColumn(f"12개월(%)\n({get_ref_str(12)})", format="%.1f")

    if not is_daily and (top5_perf or top5_spec):
        track_codes = list(set(top5_perf + top5_spec))
        curr_prices = fetch_current_prices_fast(track_codes)
    else:
        curr_prices = {}

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        st.subheader("🔥 퍼펙트 상승")
        
        if not is_daily and top5_perf:
            rets = []
            for code in top5_perf:
                row = df_k200[df_k200['종목코드'] == code].iloc[0]
                base_p = row['기준가']
                curr_p = curr_prices.get(code, base_p)
                ret = ((curr_p - base_p) / base_p * 100) if base_p > 0 else 0
                rets.append((code, ret))
            
            if rets:
                avg_ret = sum(r[1] for r in rets) / len(rets)
                ret_strs = []
                for code, r in rets:
                    color = '#FF3333' if r > 0 else '#3399FF' if r < 0 else '#555'
                    link = f"https://m.stock.naver.com/fchart/domestic/stock/{code}#"
                    ret_strs.append(f"<a href='{link}' target='_blank' class='return-link' style='color: {color}; font-weight: 600; text-decoration: underline; text-decoration-style: dotted; text-underline-offset: 3px;'>{r:.1f}%</a>")
                
                ret_str = ", ".join(ret_strs)
                avg_color = '#FF3333' if avg_ret > 0 else '#3399FF' if avg_ret < 0 else '#555'
                st.markdown(f"<div style='font-size: 0.95rem; margin-top: -10px; margin-bottom: 12px; color: #6b7280;'>이번달 수익률 : {ret_str} (평균 <strong style='color: {avg_color};'>{avg_ret:.1f}%</strong>)</div>", unsafe_allow_html=True)
                
        st.dataframe(df_perf.style.apply(apply_k200_styling, idx_df=idx_k, highlight_codes=top5_perf, overlap_codes=overlap_top5, axis=1), use_container_width=True, column_order=['통합티커_L', '종목명_L', '시가총액', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)'], column_config=k_cfg)
        
    with col_p2:
        st.subheader("🚀 달리는 말")
        
        if not is_daily and top5_spec:
            rets = []
            for code in top5_spec:
                row = df_k200[df_k200['종목코드'] == code].iloc[0]
                base_p = row['기준가']
                curr_p = curr_prices.get(code, base_p)
                ret = ((curr_p - base_p) / base_p * 100) if base_p > 0 else 0
                rets.append((code, ret))
            
            if rets:
                avg_ret = sum(r[1] for r in rets) / len(rets)
                ret_strs = []
                for code, r in rets:
                    color = '#FF3333' if r > 0 else '#3399FF' if r < 0 else '#555'
                    link = f"https://m.stock.naver.com/fchart/domestic/stock/{code}#"
                    ret_strs.append(f"<a href='{link}' target='_blank' class='return-link' style='color: {color}; font-weight: 600; text-decoration: underline; text-decoration-style: dotted; text-underline-offset: 3px;'>{r:.1f}%</a>")
                
                ret_str = ", ".join(ret_strs)
                avg_color = '#FF3333' if avg_ret > 0 else '#3399FF' if avg_ret < 0 else '#555'
                st.markdown(f"<div style='font-size: 0.95rem; margin-top: -10px; margin-bottom: 12px; color: #6b7280;'>이번달 수익률 : {ret_str} (평균 <strong style='color: {avg_color};'>{avg_ret:.1f}%</strong>)</div>", unsafe_allow_html=True)

        st.dataframe(df_spec.style.apply(apply_k200_styling, idx_df=idx_k, highlight_codes=top5_spec, overlap_codes=overlap_top5, axis=1), use_container_width=True, column_order=['통합티커_L', '종목명_L', '시가총액', '1개월(%)', '12개월(%)'], column_config=k_cfg)

    st.markdown("---")
    st.subheader("🏆 KOSPI 200 시가총액 전체 순위")
    
    full_table_cols = ['통합티커_L', '종목명_L', '시가총액', '기준가']
    if is_daily and '전일거래량' in df_k200.columns:
        df_k200['전일거래량'] = pd.to_numeric(df_k200['전일거래량'], errors='coerce').fillna(0)
        full_table_cols.append('전일거래량')
    full_table_cols.extend(['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)'])
    
    st.dataframe(df_k200.style.apply(apply_k200_styling, idx_df=idx_k, axis=1), 
                 use_container_width=True, height=600, 
                 column_order=full_table_cols, 
                 column_config=k_cfg)


# =========================================================
# 💡 화면 구성부 (월간 / 데일리 탭)
# =========================================================

st.markdown('''
    <a href="https://stock.naver.com/" target="_blank" class="title-link" style="text-decoration: none; color: inherit;">
        <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 12px; margin-top: 15px; margin-bottom: 10px;">
            <h1 style="margin: 0; padding: 0; font-size: 2.2rem; line-height: 1.2; word-break: keep-all;">🎯 KOSPI 200 강세 종목 분석</h1>
            <span style="font-size: 0.95rem; color: #3b82f6; background-color: #eff6ff; padding: 4px 10px; border-radius: 6px; border: 1px solid #bfdbfe; white-space: nowrap;">🔗 네이버 증권 이동</span>
        </div>
    </a>
''', unsafe_allow_html=True)

tab_monthly, tab_daily = st.tabs(["📅 전월 말일 기준", "🕒 오늘(데일리) 기준"])

f_kr = 'data/momentum_data.csv'
f_daily = 'data/momentum_data_daily.csv'

with tab_monthly:
    if os.path.exists(f_kr):
        df_m = pd.read_csv(f_kr, dtype={'종목코드': str})
        df_m.columns = df_m.columns.str.strip()
        b_date_m = df_m['기준일(월말)'].iloc[0] if '기준일(월말)' in df_m.columns else "기준일 불명"
        render_kospi200_dashboard(df_m, b_date_m, is_daily=False)
    else:
        st.error(f"데이터 파일이 없습니다: {f_kr}")

with tab_daily:
    if os.path.exists(f_daily):
        df_d = pd.read_csv(f_daily, dtype={'종목코드': str})
        df_d.columns = df_d.columns.str.strip()
        b_date_d = df_d['기준일'].iloc[0] if '기준일' in df_d.columns else "기준일 불명"
        render_kospi200_dashboard(df_d, b_date_d, is_daily=True)
    else:
        st.error(f"데이터 파일이 없습니다: {f_daily}")
