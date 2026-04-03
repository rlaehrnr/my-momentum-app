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

# 💡 [대통령 주기 하드코딩] 사용자가 제공한 8년차 주기 위험달 데이터
PRESIDENTIAL_DANGEROUS_MONTHS = {
    1: [2, 9],                 # 1년차 (초선 1년차)
    2: [2, 4, 6, 9, 12],       # 2년차 (초선 중간선거)
    3: [8, 9],                 # 3년차 (초선 3년차)
    4: [3],                    # 4년차 (초선 대선해)
    5: [],                     # 5년차 (재선 1년차 / 2025년 트럼프 2기)
    6: [7],                    # 6년차 (재선 중간선거 / 2026년)
    7: [6, 8, 11, 12],         # 7년차 (재선 3년차 / 2027년 예상)
    8: [1, 6, 9, 10, 11]       # 8년차 (재선 대선해 / 2028년 예상)
}

def get_cycle_year(year):
    # 2021년을 1년차로 기준하여 8년 주기 계산 (2021=1, 2025=5, 2026=6...)
    return ((year - 2021) % 8) + 1

# 💡 [스타일 함수] Top 5 단일 강조(녹색) & Top 5 교집합 강조(노랑+빨강) 동시 적용
def apply_k200_styling(row, idx_df, highlight_codes=None, overlap_codes=None):
    styles = [''] * len(row)
    market = row.get('시장', 'KOSPI')
    if market in idx_df.index:
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
            # 양쪽 모두 5순위 안에 드는 종목 (노란색/빨간글씨)
            styles[name_idx] = 'background-color: #FFF59D; color: #D84315; font-weight: bold;'
        elif highlight_codes and code in highlight_codes:
            # 해당 전략 5순위 안에 드는 종목 (연두색/녹색글씨)
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

        # 종목코드 6자리 통일 및 본주 필터링
        df_k200 = df_raw[df_raw['시장'] == 'KOSPI'].copy()
        df_k200['종목코드'] = df_k200['종목코드'].astype(str).str.replace(r'[^0-9]', '', regex=True).str.zfill(6)
        df_k200 = df_k200[df_k200['종목코드'].str.endswith('0')].copy()
        
        # 💡 [버그 픽스 복구] 시가총액 0원 방지 3중 철통 방어 로직
        try:
            # 1. 파일 내 자체 데이터 확인 (우선순위 1)
            if '시가총액' in df_k200.columns and pd.to_numeric(df_k200['시가총액'], errors='coerce').sum() > 0:
                df_k200['시가총액'] = pd.to_numeric(df_k200['시가총액'], errors='coerce').fillna(0)
                # 만약 원단위라면 억단위로 변환
                if df_k200['시가총액'].max() > 10000000000:
                    df_k200['시가총액'] = df_k200['시가총액'] / 100000000
                df_k200['시가총액'] = df_k200['시가총액'].astype(int)
            else:
                # 2. FDR 활용 (우선순위 2)
                kospi_info = fdr.StockListing('KOSPI')
                
                # 라이브러리 버전에 따라 종목코드 컬럼명이 Code 또는 Symbol 일 수 있음
                code_col = 'Code' if 'Code' in kospi_info.columns else ('Symbol' if 'Symbol' in kospi_info.columns else None)
                
                if code_col and 'Marcap' in kospi_info.columns:
                    k_info = kospi_info[[code_col, 'Marcap']].copy()
                    k_info.columns = ['Code', 'Marcap']
                    k_info['Code'] = k_info['Code'].astype(str).str.replace(r'[^0-9]', '', regex=True).str.zfill(6)
                    
                    df_k200 = df_k200.merge(k_info, left_on='종목코드', right_on='Code', how='left')
                    df_k200['시가총액'] = (pd.to_numeric(df_k200['Marcap'], errors='coerce').fillna(0) / 100000000).astype(int)
                else:
                    df_k200['시가총액'] = 0
        except Exception as e:
            df_k200['시가총액'] = 0
            st.warning(f"⚠️ 시가총액 API 로딩 에러: {e}") # 3. 통신 에러 발생시 원인 파악을 위해 화면에 경고 노출
            
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
        
        # 💡 [미국 대통령 8년차 주기 및 투자 월 계산 로직 - 하드코딩 적용]
        base_dt = pd.to_datetime(b_date_str)
        target_dt = base_dt + pd.DateOffset(months=1)
        target_year = target_dt.year
        target_month = target_dt.month
        
        # 8년 주기 계산 (2021년 = 1년차)
        cycle_year = get_cycle_year(target_year)
        
        # 하드코딩된 위험달 매핑 가져오기
        bad_months_this_year = PRESIDENTIAL_DANGEROUS_MONTHS.get(cycle_year, [])
        bad_m_str = ", ".join(f"{m}월" for m in bad_months_this_year) if bad_months_this_year else "없음"

        # 💡 [투자 중지 로직 결합]
        is_bad_market = (neg_1m_cnt >= 100) and (neg_3m_cnt >= 100)
        is_bad_season = target_month in bad_months_this_year
        
        reasons = []
        if is_bad_market: reasons.append("시장 하락장")
        if is_bad_season: reasons.append(f"위험달({target_month}월)")

        if reasons:
            invest_status = "🛑 투자 중지"
            box_color, text_color = "#FFEBEE", "#C62828"
            status_desc = " + ".join(reasons)
        else:
            invest_status = "✅ 투자 진행"
            box_color, text_color = "#E8F5E9", "#2E7D32"
            status_desc = "하락장 통과 & 양호한 달"

        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2, col3, col4, col5, col6 = st.columns([0.9, 0.9, 1.0, 1.0, 1.4, 1.6])
        
        with col1: st.metric(label="📈 KOSPI 1M", value=f"{kospi_1m}%")
        with col2: st.metric(label="📈 KOSPI 3M", value=f"{kospi_3m}%")
        with col3: st.metric(label="📉 1개월 하락", value=f"{neg_1m_cnt}개")
        with col4: st.metric(label="📉 3개월 하락", value=f"{neg_3m_cnt}개")
        with col5:
            # 💡 미국 대통령 주기 박스 렌더링
            st.markdown(f"""
            <div style="background-color: #f0f2f6; padding: 12px 10px; border-radius: 10px; text-align: center; border: 1px solid #d1d5db; height: 100%;">
                <div style="font-size: 13px; font-weight: bold; color: #333; margin-bottom: 5px;">🇺🇸대통령 <span style="color:#0047AB; font-size:15px;">{cycle_year}년차</span> ({target_year}년)</div>
                <div style="font-size: 13px; font-weight: bold; color: #D84315;">위험달: {bad_m_str}</div>
            </div>
            """, unsafe_allow_html=True)
        with col6:
            st.markdown(f"""
            <div style="background-color: {box_color}; padding: 10px; border-radius: 10px; text-align: center; border: 1px solid {text_color};">
                <p style="margin: 0; font-size: 12px; color: {text_color}; font-weight: bold;">최종 판단 ({status_desc})</p>
                <h3 style="margin: 3px 0 0 0; color: {text_color};">{invest_status}</h3>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown("<br><hr>", unsafe_allow_html=True)

        q30 = {c: df_k200[c].quantile(0.7) for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']}
        t10_1m = df_k200['1개월(%)'].quantile(0.9)
        
        cond_perf = (df_k200['1개월(%)']>=q30['1개월(%)'])&(df_k200['3개월(%)']>=q30['3개월(%)'])&(df_k200['6개월(%)']>=q30['6개월(%)'])&(df_k200['12개월(%)']>=q30['12개월(%)']) & \
                    (df_k200['1개월(%)']>0)&(df_k200['3개월(%)']>0)&(df_k200['6개월(%)']>0)&(df_k200['12개월(%)']>0)
                    
        # 💡 [정렬 변경] 퍼펙트는 3개월 기준, 달리는말은 1개월 기준 내림차순
        df_perf = df_k200[cond_perf].sort_values('3개월(%)', ascending=False).copy()
        df_spec = df_k200[(df_k200['12개월(%)']>=q30['12개월(%)']) & (df_k200['1개월(%)']>=t10_1m)].sort_values('1개월(%)', ascending=False).copy()
        
        # 💡 [Top 5 추출 및 교집합 계산 로직]
        top5_perf = df_perf.head(5)['종목코드'].tolist()
        top5_spec = df_spec.head(5)['종목코드'].tolist()
        overlap_top5 = set(top5_perf).intersection(set(top5_spec))

        k_cfg = main_cfg.copy()
        k_cfg['시가총액'] = st.column_config.NumberColumn("시가총액(억)", format="%,d")

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🔥 퍼펙트 상승")
            st.dataframe(df_perf.style.apply(apply_k200_styling, idx_df=idx_k, highlight_codes=top5_perf, overlap_codes=overlap_top5, axis=1), 
                         use_container_width=True, 
                         column_order=['통합티커_L', '종목명_L', '시가총액', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)'], 
                         column_config=k_cfg)
        with col2:
            st.subheader("🚀 달리는 말")
            st.dataframe(df_spec.style.apply(apply_k200_styling, idx_df=idx_k, highlight_codes=top5_spec, overlap_codes=overlap_top5, axis=1), 
                         use_container_width=True, 
                         column_order=['통합티커_L', '종목명_L', '시가총액', '1개월(%)', '12개월(%)'], 
                         column_config=k_cfg)

        st.markdown("---")
        st.subheader("🏆 KOSPI 200 시가총액 전체 순위")
        st.dataframe(df_k200.style.apply(apply_k200_styling, idx_df=idx_k, axis=1), 
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
        idx_m_disp = idx_m.reset_index().copy()
        
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
        idx_now_disp = idx_now.reset_index().copy()
        
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
