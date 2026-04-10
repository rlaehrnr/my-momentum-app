import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed

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

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_index_data_bulletproof(target_date_str):
    try:
        target_date = pd.to_datetime(str(target_date_str).split(' ')[0]).normalize()
    except:
        target_date = pd.to_datetime(datetime.today().date())
        
    res = []
    
    for name, ticker, fdr_ticker in [('S&P 500', '^GSPC', 'US500'), ('NASDAQ', '^IXIC', 'IXIC')]:
        df = pd.DataFrame()
        try: 
            df = yf.Ticker(ticker).history(period="2y")
        except: pass
        
        if df.empty:
            try: df = fdr.DataReader(fdr_ticker)
            except: pass
            
        if not df.empty:
            df = df.dropna(subset=['Close'])
            
            if not df.empty:
                df.index = pd.to_datetime(df.index)
                if df.index.tz is not None:
                    df.index = df.index.tz_localize(None)
                df.index = df.index.normalize()
                
                filtered_df = df[df.index <= target_date]
                if filtered_df.empty: 
                    filtered_df = df 
                    
                curr = filtered_df['Close'].iloc[-1]
                actual_date = filtered_df.index[-1].strftime('%Y-%m-%d')
                url_idx = ".INX" if name == 'S&P 500' else ".IXIC"
                
                res.append({
                    '실제기준일': actual_date,
                    '지수_L': f"https://m.stock.naver.com/worldstock/index/{url_idx}/total#{name}", 
                    '현재가_L': f"https://m.stock.naver.com/fchart/foreign/index/{url_idx}#{curr:,.2f}", 
                    'base_price': round(curr, 2),
                    '20일선': round(filtered_df['Close'].rolling(20).mean().iloc[-1], 2) if len(filtered_df) >= 20 else None,
                    '60일선': round(filtered_df['Close'].rolling(60).mean().iloc[-1], 2) if len(filtered_df) >= 60 else None,
                    '120일선': round(filtered_df['Close'].rolling(120).mean().iloc[-1], 2) if len(filtered_df) >= 120 else None,
                    '150일선': round(filtered_df['Close'].rolling(150).mean().iloc[-1], 2) if len(filtered_df) >= 150 else None,
                    '200일선': round(filtered_df['Close'].rolling(200).mean().iloc[-1], 2) if len(filtered_df) >= 200 else None
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
    "base_price": None,
    "실제기준일": None
}

# 💡 [업데이트] super_overlap_codes(초강력 교집합)를 받아서 글씨색을 붉은색으로 덧씌우는 로직 추가!
def highlight_target_codes(row, target_codes, super_overlap_codes=None, bg_color="#E8F5E9", text_color="#2E7D32", super_text_color="#D50000"):
    styles = [''] * len(row)
    code = row.get('종목코드')
    
    if '종목명_L' in row.index:
        name_idx = row.index.get_loc('종목명_L')
        
        is_top10 = code in target_codes
        is_super = super_overlap_codes and (code in super_overlap_codes)
        
        if is_top10 or is_super:
            style_str = "font-weight: bold; border-radius: 4px;"
            # 스코어 Top 10이면 배경색 지정
            if is_top10:
                style_str += f" background-color: {bg_color};"
            # 교집합 Top 5에 둘 다 들면 붉은색 글씨 덮어쓰기, 아니면 기본 초록색 글씨
            if is_super:
                style_str += f" color: {super_text_color} !important;" 
            elif is_top10:
                style_str += f" color: {text_color};"
                
            styles[name_idx] = style_str
            
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

def display_momentum_dashboard(df_raw, target_date_str, is_daily=False):
    ma_df = fetch_index_data_bulletproof(target_date_str)
    
    actual_display_date = ma_df.iloc[0]['실제기준일'] if not ma_df.empty else str(target_date_str).split(' ')[0]
    
    if not ma_df.empty:
        sp500_row = ma_df.iloc[0]
        sp500_curr = sp500_row['base_price']
        sp500_200ma = sp500_row['200일선']
        
        if pd.notna(sp500_200ma) and sp500_curr >= sp500_200ma:
            status_html = f'<span style="background-color: #E8F5E9; color: #2E7D32; padding: 4px 10px; border-radius: 6px; font-size: 1.1rem; margin-left: 15px; vertical-align: middle;">✅ 투자 진행 (현재가 > 200일선)</span>'
        elif pd.notna(sp500_200ma):
            status_html = f'<span style="background-color: #FFEBEE; color: #C62828; padding: 4px 10px; border-radius: 6px; font-size: 1.1rem; margin-left: 15px; vertical-align: middle;">🛑 투자 중지 (현재가 < 200일선)</span>'
        else:
            status_html = ""
            
        st.markdown(f"### 📊 주요 지수 이동평균선 현황 (기준일: {actual_display_date}){status_html}", unsafe_allow_html=True)
        st.dataframe(style_index_ma(ma_df), use_container_width=True, hide_index=True, 
                     column_order=["지수_L", "현재가_L", "20일선", "60일선", "120일선", "150일선", "200일선"],
                     column_config=ma_config)
    else:
        st.markdown(f"### 📊 주요 지수 이동평균선 현황 (기준일: {actual_display_date})")
        st.warning("⚠️ 지수 데이터를 일시적으로 불러오지 못했습니다.")
        
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

    # 💡 [업데이트 1] 모멘텀 스코어 Top 10으로 범위 확장
    if '모멘텀스코어' in df_500.columns:
        top10_momentum_codes = df_500.sort_values('모멘텀스코어', ascending=False).head(10)['종목코드'].tolist()
    else:
        top10_momentum_codes = []

    with st.spinner("🚀 S&P 500 전체 종목 정보를 동기화 중입니다..."):
        ticker_tuples = tuple((str(r['종목코드']), str(r.get('종목명', ''))) for _, r in df_500.iterrows())
        url_map = get_all_urls_concurrently(ticker_tuples)
        
        df_500['통합티커_L'] = df_500['종목코드'].astype(str).apply(lambda x: url_map.get(x, ("", ""))[0])
        df_500['종목명_L'] = df_500['종목코드'].astype(str).apply(lambda x: url_map.get(x, ("", ""))[1])

    super_overlap_codes = []
    
    if all(c in df_500.columns for c in ['12-1개월(%)', '6-1개월(%)', '3-1개월(%)']):
        top10_12_1 = df_500.sort_values('12-1개월(%)', ascending=False).head(10)
        top10_6_1 = df_500.sort_values('6-1개월(%)', ascending=False).head(10)
        top10_3_1 = df_500.sort_values('3-1개월(%)', ascending=False).head(10)

        overlap_12_6 = top10_12_1[top10_12_1['종목코드'].isin(top10_6_1['종목코드'])].sort_values('6-1개월(%)', ascending=False).copy()
        overlap_6_3 = top10_6_1[top10_6_1['종목코드'].isin(top10_3_1['종목코드'])].sort_values('6-1개월(%)', ascending=False).copy()

        # 💡 [업데이트 2] 양쪽 교집합 테이블의 Top 5에 모두 속하는 진정한 중복 종목 추출
        top5_12_6 = overlap_12_6.head(5)['종목코드'].tolist()
        top5_6_3 = overlap_6_3.head(5)['종목코드'].tolist()
        super_overlap_codes = list(set(top5_12_6) & set(top5_6_3))

        st.markdown("### 🌟 모멘텀 교집합 (TOP 10 중복 분석)")
        c_over1, c_over2 = st.columns(2)
        with c_over1:
            st.markdown('<div class="overlap-header">🔥 12-1M & 6-1M 중복</div>', unsafe_allow_html=True)
            if not overlap_12_6.empty:
                overlap_12_6['순위'] = range(1, len(overlap_12_6) + 1)
                st.dataframe(overlap_12_6.style.apply(highlight_target_codes, target_codes=top10_momentum_codes, super_overlap_codes=super_overlap_codes, axis=1), 
                             use_container_width=True, hide_index=True,
                             column_order=['순위', '통합티커_L', '종목명_L', '12-1개월(%)', '6-1개월(%)'], column_config=base_config)
            else: st.info("중복 종목 없음")
        with c_over2:
            st.markdown('<div class="overlap-header">⚡ 6-1M & 3-1M 중복</div>', unsafe_allow_html=True)
            if not overlap_6_3.empty:
                overlap_6_3['순위'] = range(1, len(overlap_6_3) + 1)
                st.dataframe(overlap_6_3.style.apply(highlight_target_codes, target_codes=top10_momentum_codes, super_overlap_codes=super_overlap_codes, axis=1), 
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
                st.dataframe(df_sub.style.apply(highlight_target_codes, target_codes=top10_momentum_codes, super_overlap_codes=super_overlap_codes, axis=1), 
                             use_container_width=True, height=450, hide_index=True,
                             column_order=['순위', '통합티커_L', '종목명_L', sort_col], column_config=sub_config)

    # --- 하단: 전체 ---
    st.markdown("---")
    st.markdown(f'### 📊 S&P 500 전체 종목 (기준: {actual_display_date})')
    
    df_500_all = df_500.copy()
    df_500_all['순위'] = range(1, len(df_500_all) + 1)
    
    full_order = ['순위', '통합티커_L', '종목명_L', '현재가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '3-1개월(%)', '6-1개월(%)', '12-1개월(%)', '모멘텀스코어', '전달순위']
    if is_daily: full_order.insert(4, '전일거래량')
    full_order = [col for col in full_order if col in df_500_all.columns or col in ['순위', '통합티커_L', '종목명_L']]
    
    st.dataframe(df_500_all.style.apply(highlight_target_codes, target_codes=top10_momentum_codes, super_overlap_codes=super_overlap_codes, axis=1), 
                 use_container_width=True, height=600, hide_index=True,
                 column_order=full_order, column_config=base_config)

def get_date_column(df):
    for col in ['기준일(월말)', '기준일', '기준일(데일리)', 'Date', 'date', '날짜']:
        if col in df.columns: return col
    return None

# ==========================================
# 🚀 실행부
# ==========================================
st.title("🇺🇸 S&P 500 모멘텀 순위")
t1, t2 = st.tabs(["📅 전월 말일 기준", "🕒 오늘(데일리) 기준"])

f_sp500 = 'data/momentum_data_sp500.csv'
f_daily = 'data/momentum_data_daily_sp500.csv'

def safe_read(filepath):
    try:
        df = pd.read_csv(filepath, dtype={'종목코드': str})
        df.columns = df.columns.str.strip().str.replace('\ufeff', '')
        return df
    except:
        return pd.DataFrame()

with t1:
    if os.path.exists(f_sp500):
        df_m = safe_read(f_sp500)
        
        if not df_m.empty:
            date_col = get_date_column(df_m)
            if not date_col and len(df_m.columns) > 0: date_col = df_m.columns[0]
            
            if '전달순위' not in df_m.columns or df_m['전달순위'].isnull().all():
                try:
                    b_date_str = df_m[date_col].iloc[0]
                    curr_dt = pd.to_datetime(str(b_date_str).split(' ')[0])
                    prev_month_dt = curr_dt.replace(day=1) - timedelta(days=1)
                    prev_ym = prev_month_dt.strftime('%Y_%m')
                    f_prev_archive = f'archive_sp500/momentum_sp500_{prev_ym}.csv'
                    
                    if os.path.exists(f_prev_archive):
                        df_prev = safe_read(f_prev_archive)
                        if '종목코드' in df_prev.columns:
                            prev_map = {str(c).strip().upper(): i+1 for i, c in enumerate(df_prev['종목코드'])}
                            df_m['전달순위'] = df_m['종목코드'].astype(str).str.strip().str.upper().map(prev_map)
                except: pass
                
            display_momentum_dashboard(df_m, df_m[date_col].iloc[0], is_daily=False)
    else:
        st.warning(f"⚠️ {f_sp500} 파일이 아직 생성되지 않았습니다.")

with t2:
    if os.path.exists(f_daily):
        df_d = safe_read(f_daily)
        
        if not df_d.empty:
            date_col = get_date_column(df_d)
            if not date_col and len(df_d.columns) > 0: date_col = df_d.columns[0]
            
            if os.path.exists(f_sp500):
                df_m_ref = safe_read(f_sp500)
                if not df_m_ref.empty and '종목코드' in df_m_ref.columns and '종목코드' in df_d.columns:
                    rank_map = {str(c).strip().upper(): i+1 for i, c in enumerate(df_m_ref['종목코드'])}
                    df_d['전달순위'] = df_d['종목코드'].astype(str).str.strip().str.upper().map(rank_map)
                    
            display_momentum_dashboard(df_d, df_d[date_col].iloc[0], is_daily=True)
    else:
        st.warning(f"⚠️ {f_daily} 파일이 아직 생성되지 않았습니다.")
