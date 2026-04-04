import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os
import yfinance as yf

# --- [1. 설정 및 스타일] ---
st.set_page_config(page_title="한국 모멘텀 순위", layout="wide")
st.markdown("""
    <style>
    .block-container { padding-top: 2rem !important; }
    .main-title { font-size: 1.6rem !important; font-weight: bold; margin-bottom: 1rem; }
    .stTabs [data-baseweb="tab"] { font-size: 18px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# 💡 [대통령 주기 하드코딩] 8년차 주기 위험달 데이터
PRESIDENTIAL_DANGEROUS_MONTHS = {
    1: [2, 9],                 
    2: [1, 2, 4, 5, 6, 9],       
    3: [9],                 
    4: [3],                    
    5: [3],                     
    6: [7],                    
    7: [8, 9, 10, 11],         
    8: [1, 9, 10, 11]       
}

def get_cycle_year(year):
    return ((year - 2021) % 8) + 1

# 💡 [스타일 함수]
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

# KOSPI 이동평균선 계산
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
    except: 
        return pd.DataFrame()

# 이동평균선 색상 적용
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

tab1, tab2, tab3 = st.tabs(["🎯 KOSPI 200 강세 종목", "📅 전월 말일 기준", "🕒 오늘(데일리) 기준"])

f_kr = 'data/momentum_data.csv'
f_daily = 'data/momentum_data_daily.csv'

# 💡 [복구 완료] 전달순위를 다시 NumberColumn으로 되돌려 정렬 문제와 값 누락을 원천 차단했습니다.
main_cfg = {
    "통합티커_L": st.column_config.LinkColumn("티커", display_text=r"#(.+)"), 
    "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), 
    "기준가": st.column_config.NumberColumn("종가", format="%,d"),
    "1개월(%)": st.column_config.NumberColumn(format="%.1f"), 
    "3개월(%)": st.column_config.NumberColumn(format="%.1f"), 
    "6개월(%)": st.column_config.NumberColumn(format="%.1f"), 
    "12개월(%)": st.column_config.NumberColumn(format="%.1f"),
    "모멘텀스코어": st.column_config.NumberColumn("스코어", format="%.2f"),
    "전달순위": st.column_config.NumberColumn("전달 순위", format="%d위")
}

# --- 탭 1: KOSPI 200 집중 분석 ---
with tab1:
    if os.path.exists(f_kr):
        df_raw = pd.read_csv(f_kr, dtype={'종목코드': str})
        df_raw.columns = df_raw.columns.str.strip()
        
        b_date_str = df_raw['기준일(월말)'].iloc[0]
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

        df_k200 = df_raw[df_raw['시장'] == 'KOSPI'].copy()
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
        target_dt = base_dt + pd.DateOffset(months=1)
        target_year = target_dt.year
        target_month = target_dt.month
        
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

        k_cfg = main_cfg.copy()
        k_cfg['시가총액'] = st.column_config.NumberColumn("시가총액(억)", format="%,d")

        col_p1, col_p2 = st.columns(2)
        with col_p1:
            st.subheader("🔥 퍼펙트 상승")
            st.dataframe(df_perf.style.apply(apply_k200_styling, idx_df=idx_k, highlight_codes=top5_perf, overlap_codes=overlap_top5, axis=1), use_container_width=True, column_order=['통합티커_L', '종목명_L', '시가총액', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)'], column_config=k_cfg)
        with col_p2:
            st.subheader("🚀 달리는 말")
            st.dataframe(df_spec.style.apply(apply_k200_styling, idx_df=idx_k, highlight_codes=top5_spec, overlap_codes=overlap_top5, axis=1), use_container_width=True, column_order=['통합티커_L', '종목명_L', '시가총액', '1개월(%)', '12개월(%)'], column_config=k_cfg)

        st.markdown("---")
        st.subheader("🏆 KOSPI 200 시가총액 전체 순위")
        st.dataframe(df_k200.style.apply(apply_k200_styling, idx_df=idx_k, axis=1), use_container_width=True, height=600, column_order=['통합티커_L', '종목명_L', '시가총액', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)'], column_config=k_cfg)

# --- 탭 2: 전월 말일 기준 ---

with tab2:

    if os.path.exists(f_kr):

        df_m = pd.read_csv(f_kr, dtype={'종목코드': str})

        df_m['전달순위'] = pd.to_numeric(df_m['전달순위'], errors='coerce')

        b_date_m = df_m['기준일(월말)'].iloc[0]

        st.markdown(f'<p class="main-title">📊 월간 모멘텀 (기준: {b_date_m})</p>', unsafe_allow_html=True)

        

        idx_m = get_idx_kr(pd.to_datetime(b_date_m))

        idx_m_disp = idx_m.reset_index().copy()

        idx_m_disp['시장_L'] = idx_m_disp['시장'].apply(lambda x: f"https://m.stock.naver.com/domestic/index/{x}/total#{x}")

        idx_m_disp['현재가_L'] = idx_m_disp.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/index/{r['시장']}#{r['현재가']:,.0f}", axis=1)

        

        idx_cfg = {"시장_L": st.column_config.LinkColumn("시장", display_text=r"#(.+)"), "현재가_L": st.column_config.LinkColumn("현재가", display_text=r"#(.+)")}

        st.dataframe(idx_m_disp[['시장_L', '현재가_L', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']], use_container_width=True, hide_index=True, column_config=idx_cfg)

        

        st.markdown("---")

        df_m['통합티커_L'] = df_m.apply(lambda r: f"https://finance.naver.com/item/main.naver?code={str(r['종목코드']).zfill(6)}#{r['시장']}:{str(r['종목코드']).zfill(6)}", axis=1)

        df_m['종목명_L'] = df_m.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{str(r['종목코드']).zfill(6)}#{r['종목명']}", axis=1)

        st.dataframe(df_m.style.apply(apply_k200_styling, idx_df=idx_m, axis=1), use_container_width=True, height=550, column_order=['통합티커_L', '종목명_L', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어', '전달순위'], column_config=main_cfg)



# --- 탭 3: 오늘 기준 (데일리) ---

with tab3:

    if os.path.exists(f_daily):

        df_d = pd.read_csv(f_daily, dtype={'종목코드': str})

        b_date_d = df_d['기준일'].iloc[0]

        st.markdown(f'<p class="main-title">🕒 데일리 모멘텀 (기준: {b_date_d})</p>', unsafe_allow_html=True)

        

        idx_now = get_idx_kr()

        idx_now_disp = idx_now.reset_index().copy()

        idx_now_disp['시장_L'] = idx_now_disp['시장'].apply(lambda x: f"https://m.stock.naver.com/domestic/index/{x}/total#{x}")

        idx_now_disp['현재가_L'] = idx_now_disp.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/index/{r['시장']}#{r['현재가']:,.0f}", axis=1)

        

        st.dataframe(idx_now_disp[['시장_L', '현재가_L', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']], use_container_width=True, hide_index=True, column_config=idx_cfg)

        

        st.markdown("---")

        df_d['통합티커_L'] = df_d.apply(lambda r: f"https://finance.naver.com/item/main.naver?code={str(r['종목코드']).zfill(6)}#{r['시장']}:{str(r['종목코드']).zfill(6)}", axis=1)

        df_d['종목명_L'] = df_d.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{str(r['종목코드']).zfill(6)}#{r['종목명']}", axis=1)

        

        daily_cfg = main_cfg.copy()

        daily_cfg["기준가"] = st.column_config.NumberColumn("현재가", format="%,d") 

        daily_cfg["전일거래량"] = st.column_config.NumberColumn("전일거래량", format="%,d")

        st.dataframe(df_d.style.apply(apply_k200_styling, idx_df=idx_now, axis=1), use_container_width=True, height=600, column_order=['통합티커_L', '종목명_L', '기준가', '전일거래량', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어', '전달순위'], column_config=daily_cfg)
