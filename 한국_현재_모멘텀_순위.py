import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os

# 1. 페이지 설정
st.set_page_config(page_title="한국 모멘텀 순위", layout="wide")

# CSS: 초밀착 레이아웃 및 디자인 최적화
st.markdown("""
    <style>
    /* 전체 상단 여백 최적화 (잘림 방지) */
    .block-container { padding-top: 2.5rem !important; padding-bottom: 0rem !important; }
    
    /* 제목 및 간격 조정 */
    h1 { margin-top: 0px !important; margin-bottom: 10px !important; font-size: 2rem !important; }
    [data-testid="stTable"] { margin-bottom: -25px; }
    hr { margin-top: 5px; margin-bottom: 5px; }
    .stDataFrame { margin-top: -10px; }
    
    /* 탭 디자인 */
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; font-size: 18px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# 🎨 하이라이트 함수 (지수보다 낮은 수익률은 짙은 파란색 배경 + 흰색 굵은 글씨)
def highlight_kr(row, idx_df):
    styles = [''] * len(row)
    if row['시장'] in idx_df.index:
        idx_r = idx_df.loc[row['시장']]
        for col in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
            col_idx = row.index.get_loc(col)
            # 수치 비교 후 스타일 적용
            if row[col] < idx_r[col]:
                styles[col_idx] = 'background-color: #0047AB; color: #FFFFFF; font-weight: bold;'
    return styles

# --- 지수 데이터 함수 (캐시 적용) ---
@st.cache_data(ttl=3600)
def get_idx_kr(target_date=None):
    indices = {'KOSPI': 'KS11', 'KOSDAQ': 'KQ11'}
    today = datetime.today()
    res = []
    for name, code in indices.items():
        try:
            df = fdr.DataReader(code, today - pd.DateOffset(months=16), today)
            # 기준일이 있으면 해당일 종가, 없으면 최신 종가
            curr_val = df.loc[df.index <= target_date]['Close'].iloc[-1] if target_date else df['Close'].iloc[-1]
            last_idx_date = df.index[df.index <= (target_date if target_date else today)][-1]

            def get_ret(m):
                # 정확한 m개월 전 '말일' 찾기 로직
                ref_day = (last_idx_date.replace(day=1) - pd.DateOffset(months=m-1)) - timedelta(days=1)
                past_df = df[df.index <= ref_day]
                if past_df.empty: return 0.0
                return round((curr_val - past_df['Close'].iloc[-1]) / past_df['Close'].iloc[-1] * 100, 1)
            
            res.append({
                '시장': name, 
                '현재가': round(curr_val, 1), 
                '1개월(%)': get_ret(1), '3개월(%)': get_ret(3), '6개월(%)': get_ret(6), '12개월(%)': get_ret(12)
            })
        except: pass
    return pd.DataFrame(res).set_index('시장')

# --- 탭 구성 ---
tab1, tab2 = st.tabs(["📅 전월 말일 기준", "🕒 오늘(데일리) 기준"])

# ---------------------------------------------------------
# [탭 1: 월말 고정 데이터]
# ---------------------------------------------------------
with tab1:
    f_kr = 'momentum_data.csv'
    if os.path.exists(f_kr):
        df_kr = pd.read_csv(f_kr, dtype={'종목코드': str})
        b_date = df_kr['기준일(월말)'].iloc[0]
        st.title(f"📊 한국 모멘텀 (기준일: {b_date})")
        
        # 지수 전광판
        idx_kr = get_idx_kr(pd.to_datetime(b_date))
        if not idx_kr.empty:
            st.table(idx_kr.reset_index().assign(**{c: idx_kr.reset_index()[c].map('{:.1f}'.format) for c in idx_kr.columns if c != '시장'}))
        
        st.markdown("---")
        
        # 데이터 전처리
        df_kr.index = range(1, len(df_kr) + 1) # ⭐ 1위부터 시작
        df_kr['통합티커'] = df_kr['시장'] + ":" + df_kr['종목코드'].str.zfill(6)
        df_kr['종목명'] = df_kr.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)

        # 표 출력
        st.dataframe(
            df_kr.style.apply(highlight_kr, idx_df=idx_kr, axis=1),
            use_container_width=True, height=560,
            column_order=['통합티커', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어'],
            column_config={
                "종목명": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"),
                "기준가": st.column_config.NumberColumn(format="%d"),
                "1개월(%)": st.column_config.NumberColumn(format="%.1f"),
                "3개월(%)": st.column_config.NumberColumn(format="%.1f"),
                "6개월(%)": st.column_config.NumberColumn(format="%.1f"),
                "12개월(%)": st.column_config.NumberColumn(format="%.1f"),
                "모멘텀스코어": st.column_config.NumberColumn(format="%.1f")
            }
        )
    else: st.warning("월말 데이터 파일(momentum_data.csv)이 없습니다.")

# ---------------------------------------------------------
# [탭 2: 데일리 데이터]
# ---------------------------------------------------------
with tab2:
    f_daily = 'momentum_data_daily.csv'
    if os.path.exists(f_daily):
        df_daily = pd.read_csv(f_daily, dtype={'종목코드': str})
        d_date = df_daily['기준일'].iloc[0]
        st.title(f"🕒 데일리 모멘텀 (기준일: {d_date})")
        
        # 오늘 기준 지수 전광판
        idx_now = get_idx_kr() 
        if not idx_now.empty:
            st.table(idx_now.reset_index().assign(**{c: idx_now.reset_index()[c].map('{:.1f}'.format) for c in idx_now.columns if c != '시장'}))
        
        st.markdown("---")
        
        # 데이터 전처리
        df_daily.index = range(1, len(df_daily) + 1) # ⭐ 1위부터 시작
        df_daily['통합티커'] = df_daily['시장'] + ":" + df_daily['종목코드'].str.zfill(6)
        df_daily['종목명'] = df_daily.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)

        # 표 출력
        st.dataframe(
            df_daily.style.apply(highlight_kr, idx_df=idx_now, axis=1),
            use_container_width=True, height=560,
            column_order=['통합티커', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어'],
            column_config={
                "종목명": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"),
                "기준가": st.column_config.NumberColumn(format="%d"),
                "1개월(%)": st.column_config.NumberColumn(format="%.1f"),
                "3개월(%)": st.column_config.NumberColumn(format="%.1f"),
                "6개월(%)": st.column_config.NumberColumn(format="%.1f"),
                "12개월(%)": st.column_config.NumberColumn(format="%.1f"),
                "모멘텀스코어": st.column_config.NumberColumn(format="%.1f")
            }
        )
    else: st.warning("데일리 데이터 파일이 아직 생성되지 않았습니다. 로봇을 실행해주세요.")
