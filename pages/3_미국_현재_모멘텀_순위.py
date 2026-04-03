import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os
import yfinance as yf

# 1. 페이지 설정
st.set_page_config(page_title="미국 모멘텀 순위", layout="wide")

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

# 종목별 티커용(total)과 종목명용(fchart) 링크 생성
@st.cache_data(ttl=604800)
def get_naver_stock_urls_cached(ticker, name, display_ticker):
    ticker_str = str(ticker).strip()
    
    exceptions = {
        'CIEN': '.K',
        'COHR': '.K',
    }
    
    if ticker_str in exceptions:
        suffix = exceptions[ticker_str]
    else:
        try:
            yf_ticker = ticker_str.replace('.', '-')
            stock = yf.Ticker(yf_ticker)
            exchange = stock.info.get('exchange', '')
            
            mapping = {
                'NMS': '.O',  
                'NGM': '.O',  
                'NCM': '.O',  
                'NYQ': '',    
                'ASE': '.A',  
                'BATS': '.K', 
                'PCX': '.P',  
            }
            
            if exchange in mapping:
                suffix = mapping[exchange]
            else:
                suffix = '.O' if len(ticker_str) >= 4 else ''
                
        except:
            suffix = '.O' if len(ticker_str) >= 4 else ''

    total_url = f"https://m.stock.naver.com/worldstock/stock/{ticker_str}{suffix}/total#{display_ticker}"
    chart_url = f"https://m.stock.naver.com/fchart/foreign/stock/{ticker_str}{suffix}#{name}"
    
    return total_url, chart_url

# 💡 [지수 데이터 수집] 20, 60, 120, 150, 200일선으로 변경
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
            
            # S&P 500 및 NASDAQ에 따라 링크 다르게 생성
            if name == 'S&P 500':
                url_name = f"https://m.stock.naver.com/worldstock/index/.INX/total#{name}"
                url_price = f"https://m.stock.naver.com/fchart/foreign/index/.INX#{curr_price:,.2f}"
            else:
                url_name = f"https://m.stock.naver.com/worldstock/index/.IXIC/total#{name}"
                url_price = f"https://m.stock.naver.com/fchart/foreign/index/.IXIC#{curr_price:,.2f}"
            
            ma_values = {
                '지수_L': url_name,
                '현재가_L': url_price,
                'base_price': round(curr_price, 2), # 스타일 비교용
                '20일선': round(df['Close'].rolling(20).mean().iloc[-1], 2),
                '60일선': round(df['Close'].rolling(60).mean().iloc[-1], 2),
                '120일선': round(df['Close'].rolling(120).mean().iloc[-1], 2), # 💡 추가
                '150일선': round(df['Close'].rolling(150).mean().iloc[-1], 2),
                '200일선': round(df['Close'].rolling(200).mean().iloc[-1], 2)
            }
            res.append(ma_values)
        except: pass
    return pd.DataFrame(res)

# 이동평균선 색상 스타일 함수
def style_index_ma(df):
    def apply_color(row):
        price = row['base_price']
        styles = [''] * len(row)
        for i, col in enumerate(row.index):
            if '일선' in col:
                val = row[col]
                if pd.notna(val):
                    if val < price:
                        styles[i] = 'color: #EF4444; font-weight: bold;' 
                    elif val > price:
                        styles[i] = 'color: #3B82F6; font-weight: bold;' 
        return styles
    return df.style.apply(apply_color, axis=1)

# 💡 지수 테이블 설정 (10일선 제거 및 120일선 추가)
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

def highlight_name_only(row, common_tickers):
    styles = [''] * len(row)
    if row.get('종목코드') in common_tickers:
        if '종목명_L' in row.index:
            name_idx = row.index.get_loc('종목명_L')
            styles[name_idx] = 'background-color: #FFF9C4; color: #1F2937; font-weight: bold; border-radius: 4px;'
    return styles

# 종목 테이블 컬럼 설정
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

@st.cache_data(ttl=3600)
def get_idx_us(target_date=None):
    indices = {'미국 시장': 'US500', 'NASDAQ': 'IXIC'}
    today = datetime.today()
    res = []
    for name, code in indices.items():
        try:
            df = fdr.DataReader(code, today - pd.DateOffset(months=16), today)
            curr_val = df.loc[df.index <= target_date]['Close'].iloc[-1] if target_date else df['Close'].iloc[-1]
            last_idx_date = df.index[df.index <= (target_date if target_date else today)][-1]
            def get_ret(m):
                ref_day = (last_idx_date.replace(day=1) - pd.DateOffset(months=m-1)) - timedelta(days=1)
                p_df = df[df.index <= ref_day]
                return round((curr_val - p_df['Close'].iloc[-1]) / p_df['Close'].iloc[-1] * 100, 2) if not p_df.empty else 0.0
            res.append({'시장': name, '현재가': curr_val, '1개월(%)': get_ret(1), '3개월(%)': get_ret(3), '6개월(%)': get_ret(6), '12개월(%)': get_ret(12)})
        except: pass
    return pd.DataFrame(res).set_index('시장')

def display_momentum_dashboard(df_raw, target_date_str, is_daily=False):
    st.markdown(f"### 📊 주요 지수 이동평균선 현황 (기준일: {target_date_str})")
    ma_df = get_index_ma_status(target_date_str)
    
    # 💡 [지수 테이블 출력] 10일선 제거하고 120일선 추가된 순서로 변경
    if not ma_df.empty:
        st.dataframe(
            style_index_ma(ma_df), 
            use_container_width=True, 
            hide_index=True, 
            column_order=["지수_L", "현재가_L", "20일선", "60일선", "120일선", "150일선", "200일선"],
            column_config=ma_config
        )
    st.markdown("<br>", unsafe_allow_html=True)

    df_300 = df_raw.head(300).copy()
    
    if not is_daily:
        if '전달순위' not in df_300.columns and '기준일(월말)' in df_raw.columns:
            dates = sorted(df_raw['기준일(월말)'].dropna().unique(), reverse=True)
            if len(dates) >= 2:
                prev_date = dates[1] 
                prev_df = df_raw[df_raw['기준일(월말)'] == prev_date].copy()
                prev_df['calc_rank'] = range(1, len(prev_df) + 1) 
                rank_map = prev_df.set_index('종목코드')['calc_rank'].to_dict()
                df_300['전달순위'] = df_300['종목코드'].map(rank_map)

    if is_daily:
        if '전일거래량' in df_300.columns:
            df_300['전일거래량'] = pd.to_numeric(df_300['전일거래량'], errors='coerce').fillna(0)

    if '전달순위' in df_300.columns:
        df_300['전달순위'] = pd.to_numeric(df_300['전달순위'], errors='coerce')
        df_300['전달순위'] = df_300['전달순위'].apply(lambda x: f"{int(x)}위" if pd.notna(x) and x > 0 else "NEW")

    for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '3-1개월(%)', '6-1개월(%)', '12-1개월(%)', '모멘텀스코어']:
        if c in df_300.columns:
            df_300[c] = pd.to_numeric(df_300[c], errors='coerce').fillna(0.0)

    links_df = df_300.apply(
        lambda r: pd.Series(get_naver_stock_urls_cached(r['종목코드'], r['종목명'], f"{r.get('시장', '')}:{r['종목코드']}")), 
        axis=1
    )
    df_300['통합티커_L'] = links_df[0] 
    df_300['종목명_L'] = links_df[1]  

    top10_12_1 = df_300.sort_values('12-1개월(%)', ascending=False).head(10)
    top10_6_1 = df_300.sort_values('6-1개월(%)', ascending=False).head(10)
    top10_3_1 = df_300.sort_values('3-1개월(%)', ascending=False).head(10)

    overlap_12_6 = top10_12_1[top10_12_1['종목코드'].isin(top10_6_1['종목코드'])].sort_values('6-1개월(%)', ascending=False).copy()
    overlap_6_3 = top10_6_1[top10_6_1['종목코드'].isin(top10_3_1['종목코드'])].sort_values('6-1개월(%)', ascending=False).copy()
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
                         column_order=['순위', '통합티커_L', '종목명_L', '12-1개월(%)', '6-1개월(%)'], column_config=base_config)
        else: st.info("중복 종목 없음")
    with c_over2:
        st.markdown('<div class="overlap-header">⚡ 6-1M & 3-1M 중복</div>', unsafe_allow_html=True)
        if not overlap_6_3.empty:
            overlap_6_3['순위'] = range(1, len(overlap_6_3) + 1)
            st.dataframe(overlap_6_3.style.apply(highlight_name_only, common_tickers=common_tickers, axis=1), 
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
            df_sub = df_300.sort_values(sort_col, ascending=False).head(30).copy()
            df_sub['순위'] = range(1, 31)
            st.dataframe(df_sub.style.apply(highlight_name_only, common_tickers=common_tickers, axis=1), 
                         use_container_width=True, height=450, hide_index=True,
                         column_order=['순위', '통합티커_L', '종목명_L', sort_col], column_config=sub_config)

    st.markdown("---")
    st.markdown(f'### 📊 미국 시총상위 300종목 전체 (기준: {target_date_str})')
    df_300_all = df_300.copy()
    df_300_all['순위'] = range(1, len(df_300_all) + 1)
    
    full_order = ['순위', '통합티커_L', '종목명_L', '현재가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '3-1개월(%)', '6-1개월(%)', '12-1개월(%)', '모멘텀스코어', '전달순위']
    if is_daily:
        full_order.insert(4, '전일거래량')
    
    full_order = [col for col in full_order if col in df_300_all.columns or col in ['순위', '통합티커_L', '종목명_L']]
    
    st.dataframe(df_300_all.style.apply(highlight_name_only, common_tickers=common_tickers, axis=1), 
                 use_container_width=True, height=600, hide_index=True,
                 column_order=full_order, column_config=base_config)

# 실행부
st.title("🇺🇸 미국 시총상위 모멘텀")
t1, t2 = st.tabs(["📅 전월 말일 기준", "🕒 오늘(데일리) 기준"])

f_us, f_daily = 'data/momentum_data_us.csv', 'data/momentum_data_daily_us.csv'

with t1:
    if os.path.exists(f_us):
        df = pd.read_csv(f_us, dtype={'종목코드': str})
        df.columns = df.columns.str.replace(' ', '')
        display_momentum_dashboard(df, df['기준일(월말)'].iloc[0], is_daily=False)
with t2:
    if os.path.exists(f_daily):
        df = pd.read_csv(f_daily, dtype={'종목코드': str})
        df.columns = df.columns.str.replace(' ', '')
        display_momentum_dashboard(df, df['기준일'].iloc[0], is_daily=True)
