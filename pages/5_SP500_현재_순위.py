import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os
import yfinance as yf # 💡 [필수] yfinance 라이브러리 임포트 추가

# 1. 페이지 설정
st.set_page_config(page_title="S&P 500 모멘텀 순위", layout="wide")

# CSS: 가독성 및 디자인 최적화
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem !important; }
    h1 { font-size: 2.2rem !important; font-weight: 800; margin-bottom: 10px; }
    .stTabs [data-baseweb="tab"] { font-size: 18px; font-weight: bold; }
    
    /* 섹션 제목 스타일 */
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

# 💡 [핵심 추가] 네이버 주식 모바일 차트 링크 생성 함수 (캐싱 적용)
@st.cache_data(ttl=604800)
def get_naver_stock_link_cached(ticker, name):
    ticker_str = str(ticker).strip()
    
    # 💡 [핵심 추가] 야후와 네이버의 소속 거래소 기준이 달라서 에러가 나는 종목들 강제 지정
    exceptions = {
        'CIEN': '.K',
        'COHR': '.K',
        # 나중에 또 네이버에서 튕기는 종목을 발견하시면 
        # 여기에 '티커': '.접미사' 형태로 추가만 해주시면 영구 해결됩니다!
    }
    
    # 1. 예외 사전에 등록된 녀석이면 묻지도 따지지도 않고 강제 접미사 부여
    if ticker_str in exceptions:
        return f"https://m.stock.naver.com/fchart/foreign/stock/{ticker_str}{exceptions[ticker_str]}#{name}"
        
    # 2. 일반 종목들은 정상적으로 yfinance 조회 로직을 탐
    try:
        yf_ticker = ticker_str.replace('.', '-')
        stock = yf.Ticker(yf_ticker)
        exchange = stock.info.get('exchange', '')
        
        mapping = {
            'NMS': '.O',  
            'NGM': '.O',  
            'NCM': '.O',  
            'NYQ': '',    # NYSE는 접미사 없음
            'ASE': '.A',  
            'BATS': '.K', 
            'PCX': '.P',  
        }
        
        if exchange in mapping:
            suffix = mapping[exchange]
        else:
            suffix = '.O' if len(ticker_str) >= 4 else ''
            
        return f"https://m.stock.naver.com/fchart/foreign/stock/{ticker_str}{suffix}#{name}"
    
    except:
        suffix = '.O' if len(ticker_str) >= 4 else ''
        return f"https://m.stock.naver.com/fchart/foreign/stock/{ticker_str}{suffix}#{name}"

# 특정 과거 날짜 기준의 지수 이동평균선 데이터 수집
@st.cache_data(ttl=3600)
def get_index_ma_status(target_date_str):
    indices = {'S&P 500': 'US500', 'NASDAQ': 'IXIC'}
    target_date = pd.to_datetime(target_date_str)
    start_date = target_date - timedelta(days=400) 
    
    res = []
    for name, code in indices.items():
        try:
            df = fdr.DataReader(code, start_date, target_date)
            if df.empty: continue
            
            curr_price = df['Close'].iloc[-1]
            url = f"https://m.stock.naver.com/fchart/foreign/index/.INX#{name}" if name == 'S&P 500' else f"https://m.stock.naver.com/fchart/foreign/index/.IXIC#{name}"
            
            ma_values = {
                '지수_L': url,
                '현재가': round(curr_price, 2),
                '10일선': round(df['Close'].rolling(10).mean().iloc[-1], 2),
                '20일선': round(df['Close'].rolling(20).mean().iloc[-1], 2),
                '60일선': round(df['Close'].rolling(60).mean().iloc[-1], 2),
                '120일선': round(df['Close'].rolling(120).mean().iloc[-1], 2),
                '200일선': round(df['Close'].rolling(200).mean().iloc[-1], 2)
            }
            res.append(ma_values)
        except: pass
    return pd.DataFrame(res)

# 이동평균선 색상 스타일 함수
def style_index_ma(df):
    def apply_color(row):
        price = row['현재가']
        styles = [''] * len(row)
        for i, col in enumerate(row.index):
            if '일선' in col:
                val = row[col]
                if val < price:
                    styles[i] = 'color: #EF4444; font-weight: bold;' # 붉은색
                elif val > price:
                    styles[i] = 'color: #3B82F6; font-weight: bold;' # 파란색
        return styles
    return df.style.apply(apply_color, axis=1)

ma_config = {
    "지수_L": st.column_config.LinkColumn("지수", display_text=r"#(.+)"),
    "현재가": st.column_config.NumberColumn("현재가", format="%.2f"),
    "10일선": st.column_config.NumberColumn("10일선", format="%.2f"),
    "20일선": st.column_config.NumberColumn("20일선", format="%.2f"),
    "60일선": st.column_config.NumberColumn("60일선", format="%.2f"),
    "120일선": st.column_config.NumberColumn("120일선", format="%.2f"),
    "200일선": st.column_config.NumberColumn("200일선", format="%.2f")
}

# 겹치는 종목 하이라이트
def highlight_name_only(row, common_tickers):
    styles = [''] * len(row)
    if row.get('종목코드') in common_tickers:
        if '종목명_L' in row.index:
            name_idx = row.index.get_loc('종목명_L')
            styles[name_idx] = 'background-color: #FFF9C4; color: #1F2937; font-weight: bold; border-radius: 4px;'
    return styles

# 컬럼 설정 (잘림 방지)
base_config = {
    "순위": st.column_config.NumberColumn("순위", format="%d", width=40),
    "통합티커": st.column_config.TextColumn("티커", width=105),
    "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)", width=None), 
    "기준가": st.column_config.NumberColumn("현재가", format="$ %,.2f", width=95),
    "1개월(%)": st.column_config.NumberColumn("1M", format="%.1f%%", width=75),
    "3개월(%)": st.column_config.NumberColumn("3M", format="%.1f%%", width=75),
    "6개월(%)": st.column_config.NumberColumn("6M", format="%.1f%%", width=75),
    "12개월(%)": st.column_config.NumberColumn("12M", format="%.1f%%", width=75),
    "3-1개월(%)": st.column_config.NumberColumn("3-1M", format="%.1f%%", width=85),
    "6-1개월(%)": st.column_config.NumberColumn("6-1M", format="%.1f%%", width=85),
    "12-1개월(%)": st.column_config.NumberColumn("12-1M", format="%.1f%%", width=85),
    "모멘텀스코어": st.column_config.NumberColumn("스코어", format="%.2f", width=80),
    "전일거래량": st.column_config.NumberColumn("거래량", format="%,d", width=85),
    "전달순위": st.column_config.NumberColumn("전월순위", format="%d위", width=75),
}

def display_momentum_dashboard(df_raw, target_date_str, is_daily=False):
    # 기준일 명시 및 해당 기준일의 MA 계산
    st.markdown(f"### 📊 주요 지수 이동평균선 현황 (기준일: {target_date_str})")
    ma_df = get_index_ma_status(target_date_str)
    if not ma_df.empty:
        st.dataframe(style_index_ma(ma_df), use_container_width=True, hide_index=True, column_config=ma_config)
    st.markdown("<br>", unsafe_allow_html=True)

    df_500 = df_raw.head(500).copy() # S&P 500은 500개
    
    if is_daily:
        if '전일거래량' in df_500.columns:
            df_500['전일거래량'] = pd.to_numeric(df_500['전일거래량'], errors='coerce').fillna(0)
        if '전달순위' in df_500.columns:
            df_500['전달순위'] = pd.to_numeric(df_500['전달순위'], errors='coerce')

    for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '3-1개월(%)', '6-1개월(%)', '12-1개월(%)', '모멘텀스코어']:
        if c in df_500.columns:
            df_500[c] = pd.to_numeric(df_500[c], errors='coerce').fillna(0.0)

    df_500['통합티커'] = df_500['시장'].astype(str) + ":" + df_500['종목코드'].astype(str)
    
    # 💡 [적용] 야후 파이낸스 대신 네이버 링크 적용! 원본 티커 그대로 전달
    df_500['종목명_L'] = df_500.apply(
        lambda r: get_naver_stock_link_cached(str(r['종목코드']), r['종목명']), 
        axis=1
    )

    top10_12_1 = df_500.sort_values('12-1개월(%)', ascending=False).head(10)
    top10_6_1 = df_500.sort_values('6-1개월(%)', ascending=False).head(10)
    top10_3_1 = df_500.sort_values('3-1개월(%)', ascending=False).head(10)

    overlap_12_6 = top10_12_1[top10_12_1['종목코드'].isin(top10_6_1['종목코드'])].copy()
    overlap_6_3 = top10_6_1[top10_6_1['종목코드'].isin(top10_3_1['종목코드'])].copy()
    common_tickers = set(overlap_12_6['종목코드']).intersection(set(overlap_6_3['종목코드']))

    # --- 상단: 교집합 ---
    st.markdown("### 🌟 모멘텀 교집합 (TOP 10 중복 분석)")
    c_over1, c_over2 = st.columns(2)
    with c_over1:
        st.markdown('<div class="overlap-header">🔥 12-1M & 6-1M 중복</div>', unsafe_allow_html=True)
        if not overlap_12_6.empty:
            overlap_12_6['순위'] = range(1, len(overlap_12_6) + 1)
            st.dataframe(overlap_12_6.style.apply(highlight_name_only, common_tickers=common_tickers, axis=1), 
                         use_container_width=True, hide_index=True,
                         column_order=['순위', '통합티커', '종목명_L', '12-1개월(%)', '6-1개월(%)'], column_config=base_config)
        else: st.info("중복 종목 없음")
    with c_over2:
        st.markdown('<div class="overlap-header">⚡ 6-1M & 3-1M 중복</div>', unsafe_allow_html=True)
        if not overlap_6_3.empty:
            overlap_6_3['순위'] = range(1, len(overlap_6_3) + 1)
            st.dataframe(overlap_6_3.style.apply(highlight_name_only, common_tickers=common_tickers, axis=1), 
                         use_container_width=True, hide_index=True,
                         column_order=['순위', '통합티커', '종목명_L', '6-1개월(%)', '3-1개월(%)'], column_config=base_config)
        else: st.info("중복 종목 없음")

    # --- 중단: 상위 30위 ---
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
            st.dataframe(df_sub.style.apply(highlight_name_only, common_tickers=common_tickers, axis=1), 
                         use_container_width=True, height=450, hide_index=True,
                         column_order=['순위', '통합티커', '종목명_L', sort_col], column_config=sub_config)

    # --- 하단: 전체 ---
    st.markdown("---")
    st.markdown(f'### 📊 S&P 500 전체 종목 (기준: {target_date_str})')
    df_500_all = df_500.copy()
    df_500_all['순위'] = range(1, len(df_500_all) + 1)
    
    if is_daily:
        full_order = ['순위', '통합티커', '종목명_L', '기준가', '전일거래량', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '3-1개월(%)', '6-1개월(%)', '12-1개월(%)', '모멘텀스코어', '전달순위']
    else:
        full_order = ['순위', '통합티커', '종목명_L', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '3-1개월(%)', '6-1개월(%)', '12-1개월(%)', '모멘텀스코어', '전달순위']
    
    full_order = [col for col in full_order if col in df_500_all.columns or col == '순위']
    
    st.dataframe(df_500_all.style.apply(highlight_name_only, common_tickers=common_tickers, axis=1), 
                 use_container_width=True, height=600, hide_index=True,
                 column_order=full_order, column_config=base_config)

# 실행부
st.title("🇺🇸 S&P 500 모멘텀 순위")
t1, t2 = st.tabs(["📅 전월 말일 기준", "🕒 오늘(데일리) 기준"])

f_sp500 = 'data/momentum_data_sp500.csv'
f_daily = 'data/momentum_data_daily_sp500.csv'

with t1:
    if os.path.exists(f_sp500):
        df_m = pd.read_csv(f_sp500, dtype={'종목코드': str})
        df_m.columns = df_m.columns.str.replace(' ', '')
        
        # S&P 500 고유 로직: 전달순위 보정
        if '전달순위' not in df_m.columns or df_m['전달순위'].isnull().all():
            try:
                b_date_str = df_m['기준일(월말)'].iloc[0]
                curr_dt = datetime.strptime(b_date_str, '%Y-%m-%d')
                prev_month_dt = curr_dt.replace(day=1) - timedelta(days=1)
                prev_ym = prev_month_dt.strftime('%Y_%m')
                f_prev_archive = f'archive_sp500/momentum_sp500_{prev_ym}.csv'
                
                if os.path.exists(f_prev_archive):
                    df_prev = pd.read_csv(f_prev_archive, dtype={'종목코드': str})
                    prev_map = {str(c).strip().upper(): i+1 for i, c in enumerate(df_prev['종목코드'])}
                    df_m['전달순위'] = df_m['종목코드'].str.strip().str.upper().map(prev_map)
            except: pass
            
        display_momentum_dashboard(df_m, df_m['기준일(월말)'].iloc[0], is_daily=False)

with t2:
    if os.path.exists(f_daily):
        df_d = pd.read_csv(f_daily, dtype={'종목코드': str})
        df_d.columns = df_d.columns.str.replace(' ', '')
        
        if os.path.exists(f_sp500):
            df_m_ref = pd.read_csv(f_sp500, dtype={'종목코드': str})
            rank_map = {str(c).strip().upper(): i+1 for i, c in enumerate(df_m_ref['종목코드'])}
            df_d['전달순위'] = df_d['종목코드'].str.strip().str.upper().map(rank_map)
            
        display_momentum_dashboard(df_d, df_d['기준일'].iloc[0], is_daily=True)
