import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback

# 1. 페이지 설정
st.set_page_config(page_title="S&P 500 모멘텀 순위", layout="wide")

# CSS: 가독성 및 디자인 최적화
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem !important; }
    h1 { font-size: 2.2rem !important; font-weight: 800; margin-bottom: 10px; }
    .stTabs [data-baseweb="tab"] { font-size: 18px; font-weight: bold; }
    
    .section-header {
        background-color: #1F2937;
        color: #FFFFFF;
        padding: 10px 12px;
        border-radius: 8px 8px 0 0;
        font-size: 1.1rem;
        font-weight: 700;
        border-bottom: 4px solid #EF4444;
        margin-top: 20px;
    }
    .overlap-header {
        background-color: #1E3A8A;
        color: white;
        padding: 10px 12px;
        border-radius: 8px 8px 0 0;
        font-size: 1.1rem;
        font-weight: 700;
        border-bottom: 4px solid #F59E0B;
    }
    </style>
    """, unsafe_allow_html=True)

# 💡 시장 자동 판별 및 정확한 네이버 링크 생성
def fetch_single_url(ticker, name):
    ticker_str = str(ticker).strip()
    exceptions = {'CIEN': '.K', 'COHR': '.K', 'EQNR': '.K','DELL': '.K'}
    suffix = ''
    exchange_display = "NYSE" 
    
    if ticker_str in exceptions:
        suffix = exceptions[ticker_str]
    else:
        try:
            yf_ticker = ticker_str.replace('.', '-')
            stock = yf.Ticker(yf_ticker)
            exchange = stock.info.get('exchange', '')
            
            if exchange in ['NMS', 'NGM', 'NCM', 'NASDAQ']:
                suffix = '.O'
                exchange_display = "NASDAQ"
            elif exchange in ['NYQ', 'NYSE']:
                suffix = ''
                exchange_display = "NYSE"
            elif exchange == 'ASE':
                suffix = '.A'
                exchange_display = "AMEX"
            elif exchange == 'BATS':
                suffix = '.K'
                exchange_display = "BATS"
            else:
                suffix = '.O' if len(ticker_str) >= 4 else ''
                exchange_display = "NASDAQ" if len(ticker_str) >= 4 else "NYSE"
        except:
            suffix = '.O' if len(ticker_str) >= 4 else ''
            exchange_display = "NASDAQ" if len(ticker_str) >= 4 else "NYSE"

    display_ticker = f"{exchange_display}:{ticker_str}"
    total_url = f"https://m.stock.naver.com/worldstock/stock/{ticker_str}{suffix}/total#{display_ticker}"
    chart_url = f"https://m.stock.naver.com/fchart/foreign/stock/{ticker_str}{suffix}#{name}"
    
    return ticker_str, total_url, chart_url

@st.cache_data(ttl=604800, show_spinner=False)
def get_all_urls_concurrently(ticker_data_tuples):
    urls = {}
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(fetch_single_url, t, n) for t, n in ticker_data_tuples]
        for future in as_completed(futures):
            t_str, total_url, chart_url = future.result()
            urls[t_str] = (total_url, chart_url)
    return urls

# 💡 [핵심] 캐시를 제거하여 멈춤 현상 원천 차단 + 3중 방어 데이터 수집
def fetch_index_data_final(target_date_str):
    try:
        target_date = pd.to_datetime(str(target_date_str).split(' ')[0]).normalize()
    except:
        target_date = pd.to_datetime(datetime.today().date())
        
    start_date = target_date - timedelta(days=400) 
    fetch_end_date = target_date + timedelta(days=2)
    
    res = []
    
    # 1️⃣ S&P 500 데이터
    df_sp = pd.DataFrame()
    try: df_sp = yf.Ticker('^GSPC').history(period="2y")
    except: pass
    
    if df_sp.empty:
        try: df_sp = fdr.DataReader('US500')
        except: pass
        
    if not df_sp.empty:
        df_sp.index = pd.to_datetime(df_sp.index).tz_localize(None).normalize()
        filtered_sp = df_sp[df_sp.index <= target_date]
        if filtered_sp.empty: filtered_sp = df_sp
        
        curr = filtered_sp['Close'].iloc[-1]
        res.append({
            '지수_L': "https://m.stock.naver.com/worldstock/index/.INX/total#S&P 500", 
            '현재가_L': f"https://m.stock.naver.com/fchart/foreign/index/.INX#{curr:,.2f}", 
            'base_price': round(curr, 2),
            '20일선': round(filtered_sp['Close'].rolling(20).mean().iloc[-1], 2),
            '60일선': round(filtered_sp['Close'].rolling(60).mean().iloc[-1], 2),
            '120일선': round(filtered_sp['Close'].rolling(120).mean().iloc[-1], 2),
            '150일선': round(filtered_sp['Close'].rolling(150).mean().iloc[-1], 2),
            '200일선': round(filtered_sp['Close'].rolling(200).mean().iloc[-1], 2)
        })

    # 2️⃣ NASDAQ 데이터
    df_nd = pd.DataFrame()
    try: df_nd = yf.Ticker('^IXIC').history(period="2y")
    except: pass
    
    if df_nd.empty:
        try: df_nd = fdr.DataReader('IXIC')
        except: pass
        
    if not df_nd.empty:
        df_nd.index = pd.to_datetime(df_nd.index).tz_localize(None).normalize()
        filtered_nd = df_nd[df_nd.index <= target_date]
        if filtered_nd.empty: filtered_nd = df_nd
        
        curr = filtered_nd['Close'].iloc[-1]
        res.append({
            '지수_L': "https://m.stock.naver.com/worldstock/index/.IXIC/total#NASDAQ", 
            '현재가_L': f"https://m.stock.naver.com/fchart/foreign/index/.IXIC#{curr:,.2f}", 
            'base_price': round(curr, 2),
            '20일선': round(filtered_nd['Close'].rolling(20).mean().iloc[-1], 2),
            '60일선': round(filtered_nd['Close'].rolling(60).mean().iloc[-1], 2),
            '120일선': round(filtered_nd['Close'].rolling(120).mean().iloc[-1], 2),
            '150일선': round(filtered_nd['Close'].rolling(150).mean().iloc[-1], 2),
            '200일선': round(filtered_nd['Close'].rolling(200).mean().iloc[-1], 2)
        })

    return pd.DataFrame(res)

def style_index_ma(df):
    def apply_color(row):
        price = row['base_price']
        styles = [''] * len(row)
        for i, col in enumerate(row.index):
            if '일선' in col:
                val = row[col]
                if pd.notna(val):
                    if val < price: styles[i] = 'color: #EF4444; font-weight: bold;' 
                    elif val > price: styles[i] = 'color: #3B82F6; font-weight: bold;' 
        return styles
    return df.style.apply(apply_color, axis=1)

ma_config = {
    "지수_L": st.column_config.LinkColumn("지수", display_text=r"#(.+)"),
    "현재가_L": st.column_config.LinkColumn("현재가", display_text=r"#(.+)"),
    "20일선": st.column_config.NumberColumn("20일선", format="%,.2f"),
    "60일선": st.column_config.NumberColumn("60일선", format="%,.2f"),
    "120일선": st.column_config.NumberColumn("120일선", format="%,.2f"),
    "150일선": st.column_config.NumberColumn("150일선", format="%,.2f"),
    "200일선": st.column_config.NumberColumn("200일선", format="%,.2f"),
    "base_price": None
}

def highlight_target_codes(row, target_codes, bg_color="#E8F5E9", text_color="#2E7D32"):
    styles = [''] * len(row)
    if row.get('종목코드') in target_codes:
        if '종목명_L' in row.index:
            name_idx = row.index.get_loc('종목명_L')
            styles[name_idx] = f'background-color: {bg_color}; color: {text_color}; font-weight: bold; border-radius: 4px;'
    return styles

base_config = {
    "순위": st.column_config.NumberColumn("순위", format="%d", width=40),
    "통합티커_L": st.column_config.LinkColumn("티커", display_text=r"#(.+)", width=105),
    "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)", width=None), 
    "현재가": st.column_config.NumberColumn("현재가", format="$ %,.2f", width=95),
    "1개월(%)": st.column_config.NumberColumn("1M", format="%.1f%%", width=75),
    "3개월(%)": st.column_config.NumberColumn("3M", format="%.1f%%", width=75),
    "6개월(%)": st.column_config.NumberColumn("6M", format="%.1f%%", width=75),
    "12개월(%)": st.column_config.NumberColumn("12M", format="%.1f%%", width=75),
    "3-1개월(%)": st.column_config.NumberColumn("3-1M", format="%.1f%%", width=85),
    "6-1개월(%)": st.column_config.NumberColumn("6-1M", format="%.1f%%", width=85),
    "12-1개월(%)": st.column_config.NumberColumn("12-1M", format="%.1f%%", width=85),
    "모멘텀스코어": st.column_config.NumberColumn("스코어", format="%.2f", width=80),
    "전일거래량": st.column_config.NumberColumn("거래량", format="%,d", width=85),
    "전달순위": st.column_config.TextColumn("전월순위", width=75),
}

# 💡 [핵심] 화면이 하얗게 뻗는 것을 방지하는 Try-Except 방어막 추가
def display_momentum_dashboard(df_raw, target_date_str, is_daily=False):
    try:
        if '종목코드' not in df_raw.columns:
            st.error(f"🚨 데이터에 '종목코드' 열이 없습니다! 파일이 깨졌거나 형식이 다릅니다. (현재 컬럼: {list(df_raw.columns)})")
            return

        ma_df = fetch_index_data_final(target_date_str)
        display_date = str(target_date_str).split(' ')[0]
        
        if not ma_df.empty:
            sp500_row = ma_df.iloc[0]
            sp500_curr = sp500_row['base_price']
            sp500_200ma = sp500_row['200일선']
            
            if sp500_curr >= sp500_200ma:
                status_html = f'<span style="background-color: #E8F5E9; color: #2E7D32; padding: 4px 10px; border-radius: 6px; font-size: 1.1rem; margin-left: 15px; vertical-align: middle;">✅ 투자 진행 (현재가 > 200일선)</span>'
            else:
                status_html = f'<span style="background-color: #FFEBEE; color: #C62828; padding: 4px 10px; border-radius: 6px; font-size: 1.1rem; margin-left: 15px; vertical-align: middle;">🛑 투자 중지 (현재가 < 200일선)</span>'
                
            st.markdown(f"### 📊 주요 지수 이동평균선 현황 (기준일: {display_date}){status_html}", unsafe_allow_html=True)
            st.dataframe(style_index_ma(ma_df), use_container_width=True, hide_index=True, 
                         column_order=["지수_L", "현재가_L", "20일선", "60일선", "120일선", "150일선", "200일선"],
                         column_config=ma_config)
        else:
            st.markdown(f"### 📊 주요 지수 이동평균선 현황 (기준일: {display_date})")
            st.warning("⚠️ 지수 데이터를 일시적으로 불러오지 못했습니다. 표시는 생략합니다.")
            
        st.markdown("<br>", unsafe_allow_html=True)

        df_500 = df_raw.head(500).copy() 
        
        if is_daily:
            if '전일거래량' in df_500.columns:
                df_500['전일거래량'] = pd.to_numeric(df_500['전일거래량'], errors='coerce').fillna(0)

        if '전달순위' in df_500.columns:
            df_500['전달순위'] = pd.to_numeric(df_500['전달순위'], errors='coerce')
            df_500['전달순위'] = df_500['전달순위'].apply(lambda x: f"{int(x)}위" if pd.notna(x) and x > 0 else "NEW")

        for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '3-1개월(%)', '6-1개월(%)', '12-1개월(%)', '모멘텀스코어']:
            if c in df_500.columns:
                df_500[c] = pd.to_numeric(df_500[c], errors='coerce').fillna(0.0)

        if '모멘텀스코어' in df_500.columns:
            top8_momentum_codes = df_500.sort_values('모멘텀스코어', ascending=False).head(8)['종목코드'].tolist()
        else:
            top8_momentum_codes = []

        with st.spinner("🚀 S&P 500 전체 종목 정보를 동기화 중입니다..."):
            ticker_tuples = tuple((str(r['종목코드']), str(r.get('종목명', ''))) for _, r in df_500.iterrows())
            url_map = get_all_urls_concurrently(ticker_tuples)
            
            df_500['통합티커_L'] = df_500['종목코드'].astype(str).apply(lambda x: url_map.get(x, ("", ""))[0])
            df_500['종목명_L'] = df_500['종목코드'].astype(str).apply(lambda x: url_map.get(x, ("", ""))[1])

        # 교집합 계산
        if all(c in df_500.columns for c in ['12-1개월(%)', '6-1개월(%)', '3-1개월(%)']):
            top10_12_1 = df_500.sort_values('12-1개월(%)', ascending=False).head(10)
            top10_6_1 = df_500.sort_values('6-1개월(%)', ascending=False).head(10)
            top10_3_1 = df_500.sort_values('3-1개월(%)', ascending=False).head(10)

            overlap_12_6 = top10_12_1[top10_12_1['종목코드'].isin(top10_6_1['종목코드'])].sort_values('6-1개월(%)', ascending=False).copy()
            overlap_6_3 = top10_6_1[top10_6_1['종목코드'].isin(top10_3_1['종목코드'])].sort_values('6-1개월(%)', ascending=False).copy()

            st.markdown("### 🌟 모멘텀 교집합 (TOP 10 중복 분석)")
            c_over1, c_over2 = st.columns(2)
            with c_over1:
                st.markdown('<div class="overlap-header">🔥 12-1M & 6-1M 중복</div>', unsafe_allow_html=True)
                if not overlap_12_6.empty:
                    overlap_12_6['순위'] = range(1, len(overlap_12_6) + 1)
                    st.dataframe(overlap_12_6.style.apply(highlight_target_codes, target_codes=top8_momentum_codes, axis=1), 
                                 use_container_width=True, hide_index=True,
                                 column_order=['순위', '통합티커_L', '종목명_L', '12-1개월(%)', '6-1개월(%)'], column_config=base_config)
                else: st.info("중복 종목 없음")
            with c_over2:
                st.markdown('<div class="overlap-header">⚡ 6-1M & 3-1M 중복</div>', unsafe_allow_html=True)
                if not overlap_6_3.empty:
                    overlap_6_3['순위'] = range(1, len(overlap_6_3) + 1)
                    st.dataframe(overlap_6_3.style.apply(highlight_target_codes, target_codes=top8_momentum_codes, axis=1), 
                                 use_container_width=True, hide_index=True,
                                 column_order=['순위', '통합티커_L', '종목명_L', '6-1개월(%)', '3-1개월(%)'], column_config=base_config)
                else: st.info("중복 종목 없음")

            st.markdown("<br>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns(3)
            
            sub_config = base_config.copy()
            sub_config["12-1개월(%)"] = st.column_config.NumberColumn("12-1", format="%.1f%%", width="small")
            sub_config["6-1개월(%)"] = st.column_config.NumberColumn("6-1", format="%.1f%%", width="small")
            sub_config["3-1개월(%)"] = st.column_config.NumberColumn("3-1", format="%.1f%%", width="small")

            for col, title, sort_col in zip([col1, col2, col3], 
                                           ["🏆 12-1개월 상위 30", "🏆 6-1개월 상위 30", "🏆 3-1개월 상위 30"], 
                                           ["12-1개월(%)", "6-1개월(%)", "3-1개월(%)"]):
                with col:
                    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)
                    df_sub = df_500.sort_values(sort_col, ascending=False).head(30).copy()
                    df_sub['순위'] = range(1, 31)
                    st.dataframe(df_sub.style.apply(highlight_target_codes, target_codes=top8_momentum_codes, axis=1), 
                                 use_container_width=True, height=450, hide_index=True,
                                 column_order=['순위', '통합티커_L', '종목명_L', sort_col], column_config=sub_config)

        # --- 하단: 전체 ---
        st.markdown("---")
        st.markdown(f'### 📊 S&P 500 전체 종목 (기준: {display_date})')
        
        df_500_all = df_500.copy()
        df_500_all['순위'] = range(1, len(df_500_all) + 1)
        
        full_order = ['순위', '통합티커_L', '종목명_L', '현재가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '3-1개월(%)', '6-1개월(%)', '12-1개월(%)', '모멘텀스코어', '전달순위']
        if is_daily: full_order.insert(4, '전일거래량')
        full_order = [col for col in full_order if col in df_500_all.columns or col in ['순위', '통합티커_L', '종목명_L']]
        
        st.dataframe(df_500_all.style.apply(highlight_target_codes, target_codes=top8_momentum_codes, axis=1), 
                     use_container_width=True, height=600, hide_index=True,
                     column_order=full_order, column_config=base_config)
                     
    except Exception as e:
        # 에러가 발생하더라도 백지가 되지 않고 화면에 상세 내용을 뿌려줍니다.
        st.error("🚨 화면을 그리는 도중 예상치 못한 에러가 발생했습니다.")
        st.code(traceback.format_exc())

# 💡 [핵심] 보이지 않는 특수문자와 띄어쓰기를 완벽하게 파괴하는 강력한 파일 읽기 함수
def safe_read_csv(filepath):
    for enc in ['utf-8-sig', 'cp949', 'euc-kr', 'utf-8']:
        try:
            df = pd.read_csv(filepath, dtype=str, encoding=enc)
            if not df.empty:
                # 컬럼명에 있는 모든 공백과 투명 특수문자(\ufeff) 완벽 삭제
                df.columns = df.columns.str.replace(r'[\s\ufeff]', '', regex=True)
                return df
        except: pass
    return pd.DataFrame()

def get_date_column(df):
    for col in ['기준일', '기준일(데일리)', '기준일(월말)', 'Date', 'date', '날짜']:
        if col in df.columns: return col
    return None

# 실행부
st.title("🇺🇸 S&P 500 모멘텀 순위")
t1, t2 = st.tabs(["📅 전월 말일 기준", "🕒 오늘(데일리) 기준"])

f_sp500 = 'data/momentum_data_sp500.csv'
f_daily = 'data/momentum_data_daily_sp500.csv'

with t1:
    if os.path.exists(f_sp500):
        df_m = safe_read_csv(f_sp500)
        if not df_m.empty:
            date_col_m = get_date_column(df_m)
            if date_col_m:
                if '전달순위' not in df_m.columns or df_m['전달순위'].isnull().all():
                    try:
                        b_date_str = df_m[date_col_m].iloc[0]
                        curr_dt = pd.to_datetime(b_date_str)
                        prev_month_dt = curr_dt.replace(day=1) - timedelta(days=1)
                        prev_ym = prev_month_dt.strftime('%Y_%m')
                        f_prev_archive = f'archive_sp500/momentum_sp500_{prev_ym}.csv'
                        
                        if os.path.exists(f_prev_archive):
                            df_prev = safe_read_csv(f_prev_archive)
                            if '종목코드' in df_prev.columns:
                                prev_map = {str(c).strip().upper(): i+1 for i, c in enumerate(df_prev['종목코드'])}
                                df_m['전달순위'] = df_m['종목코드'].str.strip().str.upper().map(prev_map)
                    except: pass
                    
                display_momentum_dashboard(df_m, df_m[date_col_m].iloc[0], is_daily=False)
            else:
                st.error(f"❌ 월말 데이터에 기준일 컬럼이 없습니다. (현재 컬럼: {list(df_m.columns)})")
        else:
            st.error(f"❌ {f_sp500} 파일을 읽을 수 없습니다.")
    else:
        st.warning(f"⚠️ {f_sp500} 파일이 아직 생성되지 않았습니다.")

with t2:
    if os.path.exists(f_daily):
        df_d = safe_read_csv(f_daily)
        if not df_d.empty:
            date_col_d = get_date_column(df_d)
            if date_col_d:
                if os.path.exists(f_sp500):
                    df_m_ref = safe_read_csv(f_sp500)
                    if not df_m_ref.empty and '종목코드' in df_m_ref.columns and '종목코드' in df_d.columns:
                        rank_map = {str(c).strip().upper(): i+1 for i, c in enumerate(df_m_ref['종목코드'])}
                        df_d['전달순위'] = df_d['종목코드'].str.strip().str.upper().map(rank_map)
                    
                display_momentum_dashboard(df_d, df_d[date_col_d].iloc[0], is_daily=True)
            else:
                st.error(f"❌ 데일리 데이터에 기준일 컬럼이 없습니다. (현재 컬럼: {list(df_d.columns)})")
        else:
            st.error(f"❌ {f_daily} 파일을 읽을 수 없습니다.")
    else:
        st.warning(f"⚠️ {f_daily} 파일이 아직 생성되지 않았습니다. 데이터를 업데이트해 주세요.")
