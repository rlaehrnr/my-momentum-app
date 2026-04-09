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
    .debug-box { background-color: #f0f2f6; border-left: 5px solid #ff4b4b; padding: 10px; margin: 10px 0; font-family: monospace; font-size: 0.8rem; }
    </style>
    """, unsafe_allow_html=True)

# 💡 시장 자동 판별 및 정확한 네이버 링크 생성
def fetch_single_url(ticker, name):
    ticker_str = str(ticker).strip()
    exceptions = {'CIEN': '.K', 'COHR': '.K', 'EQNR': '.K','DELL': '.K'}
    suffix = ''
    exchange_display = "NYSE" 
    try:
        yf_ticker = ticker_str.replace('.', '-')
        stock = yf.Ticker(yf_ticker)
        exchange = stock.info.get('exchange', '')
        if exchange in ['NMS', 'NGM', 'NCM', 'NASDAQ']:
            suffix = '.O'; exchange_display = "NASDAQ"
        elif exchange in ['NYQ', 'NYSE']:
            suffix = ''; exchange_display = "NYSE"
        else:
            suffix = '.O' if len(ticker_str) >= 4 else ''; exchange_display = "NASDAQ" if len(ticker_str) >= 4 else "NYSE"
    except:
        suffix = '.O' if len(ticker_str) >= 4 else ''; exchange_display = "NASDAQ" if len(ticker_str) >= 4 else "NYSE"

    total_url = f"https://m.stock.naver.com/worldstock/stock/{ticker_str}{suffix}/total#{exchange_display}:{ticker_str}"
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

# 💡 [디버그 기능 포함] 지수 데이터 수집
def fetch_index_debug(target_date_str):
    st.write(f"🔍 [지수 수집 시작] 기준일: {target_date_str}")
    try:
        target_date = pd.to_datetime(str(target_date_str).split(' ')[0]).normalize()
        start_date = target_date - timedelta(days=400)
        fetch_end_date = target_date + timedelta(days=5)
        
        res = []
        for name, ticker in [('S&P 500', '^GSPC'), ('NASDAQ', '^IXIC')]:
            st.write(f"📡 {name}({ticker}) 데이터 요청 중...")
            df = yf.Ticker(ticker).history(period="2y")
            if not df.empty:
                df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
                filtered = df[df.index <= target_date]
                if filtered.empty: filtered = df
                curr = filtered['Close'].iloc[-1]
                res.append({
                    '지수_L': f"https://m.stock.naver.com/worldstock/index/{'.INX' if name=='S&P 500' else '.IXIC'}/total#{name}",
                    '현재가_L': f"https://m.stock.naver.com/fchart/foreign/index/{'.INX' if name=='S&P 500' else '.IXIC'}#{curr:,.2f}",
                    'base_price': round(curr, 2),
                    '20일선': round(filtered['Close'].rolling(20).mean().iloc[-1], 2),
                    '60일선': round(filtered['Close'].rolling(60).mean().iloc[-1], 2),
                    '120일선': round(filtered['Close'].rolling(120).mean().iloc[-1], 2),
                    '150일선': round(filtered['Close'].rolling(150).mean().iloc[-1], 2),
                    '200일선': round(filtered['Close'].rolling(200).mean().iloc[-1], 2)
                })
                st.write(f"✅ {name} 수집 완료 (현재가: {curr:,.2f})")
        return pd.DataFrame(res)
    except Exception as e:
        st.error(f"❌ 지수 수집 중 치명적 에러: {e}")
        return pd.DataFrame()

def display_momentum_dashboard(df_raw, target_date_str, is_daily=False):
    st.markdown(f"### 🕵️‍♂️ 수사 보고 (탭: {'데일리' if is_daily else '월말'})")
    
    try:
        # 1. 지수 영역
        ma_df = fetch_index_debug(target_date_str)
        if not ma_df.empty:
            st.dataframe(ma_df, use_container_width=True) # 스타일 빼고 생으로 출력 시도
        
        # 2. 데이터 유효성 검사
        st.write(f"📊 로드된 데이터 행 수: {len(df_raw)}")
        if '종목코드' not in df_raw.columns:
            st.error(f"🚨 '종목코드' 열을 찾을 수 없습니다. 현재 열들: {list(df_raw.columns)}")
            return

        df_500 = df_raw.head(500).copy()
        
        # 3. 데이터 정규화 (이 과정에서 에러가 많이 남)
        st.write("⚙️ 데이터 정규화 진행 중...")
        for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '3-1개월(%)', '6-1개월(%)', '12-1개월(%)', '모멘텀스코어']:
            if c in df_500.columns:
                df_500[c] = pd.to_numeric(df_500[c].astype(str).str.replace('%',''), errors='coerce').fillna(0.0)
        
        st.write("🔗 네이버 링크 동기화 중...")
        ticker_tuples = tuple((str(r['종목코드']), str(r.get('종목명', ''))) for _, r in df_500.iterrows())
        url_map = get_all_urls_concurrently(ticker_tuples)
        df_500['통합티커_L'] = df_500['종목코드'].astype(str).apply(lambda x: url_map.get(x, ("", ""))[0])
        df_500['종목명_L'] = df_500['종목코드'].astype(str).apply(lambda x: url_map.get(x, ("", ""))[1])
        
        st.write("✅ 모든 준비 완료. 표를 그립니다.")
        st.dataframe(df_500.head(100), use_container_width=True)

    except Exception as e:
        st.error("🚨 대시보드 출력 중 에러 발생!")
        st.code(traceback.format_exc())

# --- 실행부 ---
st.title("🇺🇸 S&P 500 모멘텀 순위 (수사 모드)")
t1, t2 = st.tabs(["📅 월말 기준", "🕒 데일리 기준"])

f_sp500 = 'data/momentum_data_sp500.csv'
f_daily = 'data/momentum_data_daily_sp500.csv'

with t1:
    if os.path.exists(f_sp500):
        df_m = pd.read_csv(f_sp500)
        df_m.columns = df_m.columns.str.replace(' ', '')
        display_momentum_dashboard(df_m, df_m['기준일(월말)'].iloc[0], is_daily=False)

with t2:
    if os.path.exists(f_daily):
        df_d = pd.read_csv(f_daily)
        df_d.columns = df_d.columns.str.replace(' ', '')
        # 데일리 파일에 '기준일' 열이 있는지 확인
        if '기준일' in df_d.columns:
            display_momentum_dashboard(df_d, df_d['기준일'].iloc[0], is_daily=True)
        else:
            st.error(f"❌ 데일리 파일에 '기준일' 열이 없습니다. 컬럼명: {list(df_d.columns)}")
