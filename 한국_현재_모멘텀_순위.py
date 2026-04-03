import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os

# --- [1. 설정 및 스타일] ---
st.set_page_config(page_title="한국 모멘텀 순위", layout="wide")
st.markdown("""
    <style>
    .block-container { padding-top: 2rem !important; }
    .main-title { font-size: 1.6rem !important; font-weight: bold; margin-bottom: 1rem; }
    .stTabs [data-baseweb="tab"] { font-size: 18px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# 스타일 함수
def apply_k200_styling(row, idx_df, common_codes=None):
    styles = [''] * len(row)
    market = row.get('시장', 'KOSPI')
    if market in idx_df.index:
        idx_r = idx_df.loc[market]
        for col in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
            if col in row.index and col in idx_r.index:
                col_idx = row.index.get_loc(col)
                if row[col] < idx_r[col]:
                    styles[col_idx] = 'background-color: #E3F2FD; color: #0047AB;'
    if common_codes and '종목코드' in row.index and row['종목코드'] in common_codes:
        if '종목명_L' in row.index:
            styles[row.index.get_loc('종목명_L')] = 'background-color: #FFF59D; color: #D84315; font-weight: bold;'
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

tab1, tab2, tab3 = st.tabs(["🎯 KOSPI 200 강세 종목", "📅 전월 말일 기준", "🕒 오늘(데일리) 기준"])

f_kr = 'data/momentum_data.csv'
f_daily = 'data/momentum_data_daily.csv'

# 공통 Config
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
        b_date_str = df_raw['기준일(월말)'].iloc[0]
        st.markdown(f'<p class="main-title">🎯 KOSPI 200 집중 분석 (기준: {b_date_str})</p>', unsafe_allow_html=True)
        
        idx_k = get_idx_kr(pd.to_datetime(b_date_str))
        kospi_1m = idx_k.loc['KOSPI', '1개월(%)'] if 'KOSPI' in idx_k.index else 0.0
        kospi_3m = idx_k.loc['KOSPI', '3개월(%)'] if 'KOSPI' in idx_k.index else 0.0

        df_k200 = df_raw[(df_raw['시장'] == 'KOSPI') & (df_raw['종목코드'].str.endswith('0'))].copy()
        
        try:
            kospi_info = fdr.StockListing('KOSPI')[['Code', 'Marcap']]
            df_k200 = df_k200.merge(kospi_info, left_on='종목코드', right_on='Code', how='left')
            df_k200['시가총액'] = (df_k200['Marcap'] / 100000000).fillna(0).astype(int)
        except:
            df_k200['시가총액'] = 0
            
        df_k200 = df_k200.sort_values(by='시가총액', ascending=False).head(200)
        df_k200['시총순위'] = range(1, len(df_k200) + 1)
        df_k200 = df_k200.set_index('시총순위')
        
        df_k200['통합티커_L'] = df_k200.apply(
            lambda r: f"https://finance.naver.com/item/main.naver?code={str(r['종목코드']).zfill(6)}#KOSPI:{str(r['종목코드']).zfill(6)}", axis=1
        )
        df_k200['종목명_L'] = df_k200.apply(
            lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{str(r['종목코드']).zfill(6)}#{r['종목명']}", axis=1
        )

        neg_1m_cnt = (df_k200['1개월(%)'] < 0).sum()
        neg_3m_cnt = (df_k200['3개월(%)'] < 0).sum()
        neg_6m_cnt = (df_k200['6개월(%)'] < 0).sum()
        
        if neg_3m_cnt >= 100 and (neg_1m_cnt >= 100 or neg_6m_cnt >= 100):
            invest_status, box_color, text_color = "🛑 투자 중지", "#FFEBEE", "#C62828"
        else:
            invest_status, box_color, text_color = "✅ 투자 진행", "#E8F5E9", "#2E7D32"

        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2, col3, col4, col5, col6 = st.columns([0.9, 0.9, 1.1, 1.1, 1.1, 1.6])
        
        with col1: st.metric(label="📈 KOSPI 1M", value=f"{kospi_1m}%")
        with col2: st.metric(label="📈 KOSPI 3M", value=f"{kospi_3m}%")
        with col3: st.metric(label="📉 1개월 하락", value=f"{neg_1m_cnt}개")
        with col4: st.metric(label="📉 3개월 하락", value=f"{neg_3m_cnt}개")
        with col5: st.metric(label="📉 6개월 하락", value=f"{neg_6m_cnt}개")
        with col6:
            st.markdown(f"""
            <div style="background-color: {box_color}; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid {text_color};">
                <p style="margin: 0; font-size: 14px; color: {text_color}; font-weight: bold;">최종 판단 지표</p>
                <h3 style="margin: 5px 0 0 0; color: {text_color};">{invest_status}</h3>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown("<br><hr>", unsafe_allow_html=True)

        q30 = {c: df_k200[c].quantile(0.7) for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']}
        t10_1m = df_k200['1개월(%)'].quantile(0.9)
        
        cond_perf = (df_k200['1개월(%)']>=q30['1개월(%)'])&(df_k200['3개월(%)']>=q30['3개월(%)'])&(df_k200['6개월(%)']>=q30['6개월(%)'])&(df_k200['12개월(%)']>=q30['12개월(%)']) & \
                    (df_k200['1개월(%)']>0)&(df_k200['3개월(%)']>0)&(df_k200['6개월(%)']>0)&(df_k200['12개월(%)']>0)
                    
        df_perf = df_k200[cond_perf].sort_values('1개월(%)', ascending=False).copy()
        df_spec = df_k200[(df_k200['12개월(%)']>=q30['12개월(%)']) & (df_k200['1개월(%)']>=t10_1m)].sort_values('1개월(%)', ascending=False).copy()
        common_codes = set(df_perf['종목코드']).intersection(set(df_spec['종목코드']))

        k_cfg = main_cfg.copy()
        k_cfg['시가총액'] = st.column_config.NumberColumn("시가총액(억)", format="%,d")

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🔥 퍼펙트 상승")
            st.dataframe(df_perf.style.apply(apply_k200_styling, idx_df=idx_k, common_codes=common_codes, axis=1), 
                         use_container_width=True, 
                         column_order=['통합티커_L', '종목명_L', '시가총액', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)'], 
                         column_config=k_cfg)
        with col2:
            st.subheader("🚀 달리는 말")
            st.dataframe(df_spec.style.apply(apply_k200_styling, idx_df=idx_k, common_codes=common_codes, axis=1), 
                         use_container_width=True, 
                         column_order=['통합티커_L', '종목명_L', '시가총액', '1개월(%)', '12개월(%)'], 
                         column_config=k_cfg)

        st.markdown("---")
        st.subheader("🏆 KOSPI 200 시가총액 전체 순위")
        st.dataframe(df_k200.style.apply(apply_k200_styling, idx_df=idx_k, common_codes=common_codes, axis=1), 
                     use_container_width=True, height=600, 
                     column_order=['통합티커_L', '종목명_L', '시가총액', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)'], 
                     column_config=k_cfg)

# --- 탭 2: 전월 말일 기준 ---
with tab2:
    if os.path.exists(f_kr):
        df_m = pd.read_csv(f_kr, dtype={'종목코드': str})
        df_m['전달순위'] = pd.to_numeric(df_m['전달순위'], errors='coerce')
        b_date = df_m['기준일(월말)'].iloc[0]
        st.markdown(f'<p class="main-title">📊 월간 모멘텀 (기준: {b_date})</p>', unsafe_allow_html=True)
        
        idx_m = get_idx_kr(pd.to_datetime(b_date))
        
        # 💡 [핵심] 정적인 st.table 대신 st.dataframe을 활용해 지수명/현재가 링크 부여
        idx_m_disp = idx_m.reset_index().copy()
        
        # 링크 생성 (시장: 종합정보, 현재가: 모바일 차트)
        idx_m_disp['시장_L'] = idx_m_disp['시장'].apply(lambda x: f"https://m.stock.naver.com/domestic/index/{x}/total#{x}")
        idx_m_disp['현재가_L'] = idx_m_disp.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/index/{r['시장']}#{r['현재가']:,.0f}", axis=1)
        
        for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
            if c in idx_m_disp.columns:
                idx_m_disp[c] = idx_m_disp[c].map('{:.1f}'.format)
                
        idx_cfg = {
            "시장_L": st.column_config.LinkColumn("시장", display_text=r"#(.+)"),
            "현재가_L": st.column_config.LinkColumn("현재가", display_text=r"#(.+)")
        }
        
        st.dataframe(idx_m_disp[['시장_L', '현재가_L', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']], 
                     use_container_width=True, hide_index=True, column_config=idx_cfg)
        
        st.markdown("---")
        df_m.index = range(1, len(df_m) + 1)
        
        df_m['통합티커_L'] = df_m.apply(
            lambda r: f"https://finance.naver.com/item/main.naver?code={str(r['종목코드']).zfill(6)}#{r['시장']}:{str(r['종목코드']).zfill(6)}", axis=1
        )
        df_m['종목명_L'] = df_m.apply(
            lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{str(r['종목코드']).zfill(6)}#{r['종목명']}", axis=1
        )
        
        st.dataframe(df_m.style.apply(apply_k200_styling, idx_df=idx_m, axis=1), 
                     use_container_width=True, height=550,
                     column_order=['통합티커_L', '종목명_L', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어', '전달순위'], 
                     column_config=main_cfg)

# --- 탭 3: 오늘 기준 (데일리) ---
with tab3:
    if os.path.exists(f_daily):
        df_d = pd.read_csv(f_daily, dtype={'종목코드': str})
        df_d['전달순위'] = pd.to_numeric(df_d['전달순위'], errors='coerce')
        b_date_d = df_d['기준일'].iloc[0]
        st.markdown(f'<p class="main-title">🕒 데일리 모멘텀 (기준: {b_date_d})</p>', unsafe_allow_html=True)
        
        idx_now = get_idx_kr()
        
        # 💡 [핵심] 정적인 st.table 대신 st.dataframe을 활용해 지수명/현재가 링크 부여
        idx_now_disp = idx_now.reset_index().copy()
        
        # 링크 생성 (시장: 종합정보, 현재가: 모바일 차트)
        idx_now_disp['시장_L'] = idx_now_disp['시장'].apply(lambda x: f"https://m.stock.naver.com/domestic/index/{x}/total#{x}")
        idx_now_disp['현재가_L'] = idx_now_disp.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/index/{r['시장']}#{r['현재가']:,.0f}", axis=1)
        
        for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
            if c in idx_now_disp.columns:
                idx_now_disp[c] = idx_now_disp[c].map('{:.1f}'.format)
                
        idx_cfg = {
            "시장_L": st.column_config.LinkColumn("시장", display_text=r"#(.+)"),
            "현재가_L": st.column_config.LinkColumn("현재가", display_text=r"#(.+)")
        }
        
        st.dataframe(idx_now_disp[['시장_L', '현재가_L', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']], 
                     use_container_width=True, hide_index=True, column_config=idx_cfg)
        
        st.markdown("---")
        df_d.index = range(1, len(df_d) + 1)
        
        df_d['통합티커_L'] = df_d.apply(
            lambda r: f"https://finance.naver.com/item/main.naver?code={str(r['종목코드']).zfill(6)}#{r['시장']}:{str(r['종목코드']).zfill(6)}", axis=1
        )
        df_d['종목명_L'] = df_d.apply(
            lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{str(r['종목코드']).zfill(6)}#{r['종목명']}", axis=1
        )
        
        daily_cfg = main_cfg.copy()
        daily_cfg["기준가"] = st.column_config.NumberColumn("현재가", format="%,d") 
        daily_cfg["전일거래량"] = st.column_config.NumberColumn("전일거래량", format="%,d")
        
        st.dataframe(df_d.style.apply(apply_k200_styling, idx_df=idx_now, axis=1), 
                     use_container_width=True, height=600,
                     column_order=['통합티커_L', '종목명_L', '기준가', '전일거래량', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어', '전달순위'], 
                     column_config=daily_cfg)
