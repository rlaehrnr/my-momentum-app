import streamlit as st
import pandas as pd
import os
import glob
from datetime import datetime, timedelta
import numpy as np

# 1. 페이지 설정
st.set_page_config(page_title="한국 모멘텀 기록보관소", layout="wide")

# CSS: 레이아웃 및 메트릭 시인성 강화
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem !important; }
    h1 { font-size: 1.8rem !important; font-weight: 800; margin-bottom: 20px; }
    [data-testid="stDataFrame"] { margin-bottom: -10px !important; }
    /* 메트릭 카드 시인성 확보 (진한 배경) */
    [data-testid="stMetricValue"] { font-size: 1.5rem !important; color: #0047AB !important; font-weight: 700; }
    .stMetric { background-color: #f0f2f6 !important; padding: 15px !important; border-radius: 10px; border: 1px solid #d1d5db; }
    </style>
    """, unsafe_allow_html=True)

st.title("📁 한국 월별 모멘텀 기록보관소")

folder, prefix = "archive", "momentum_"
files = glob.glob(f"{folder}/{prefix}*.csv")

if not files:
    st.info("데이터가 없습니다. archive 폴더를 확인해주세요.")
else:
    # 데이터 구조 파악
    data_struct = {}
    for f in files:
        fname = os.path.basename(f)
        try:
            date_part = fname.replace(prefix, "").replace(".csv", "")
            year, month = date_part.split('_')
            if year not in data_struct: data_struct[year] = []
            data_struct[year].append(month)
        except: continue

    sorted_years = sorted(data_struct.keys(), reverse=True)
    
    col_y, col_m, _ = st.columns([1, 1, 4])
    with col_y:
        selected_year = st.selectbox("📅 연도", sorted_years)
    with col_m:
        available_months = sorted(data_struct[selected_year], key=lambda x: int(x))
        selected_month = st.selectbox("🌙 월", available_months)

    # --- [핵심 추가: 전달 순위 로직] ---
    target_file = f"{folder}/{prefix}{selected_year}_{selected_month}.csv"
    df = pd.read_csv(target_file, dtype={'종목코드': str})
    
    try:
        # 현재 선택된 달의 직전 달 계산
        curr_dt = datetime(int(selected_year), int(selected_month), 1)
        prev_dt = curr_dt - timedelta(days=1)
        p_year = prev_dt.strftime('%Y')
        p_month = prev_dt.strftime('%m')
        prev_file = f"{folder}/{prefix}{p_year}_{p_month}.csv"

        if os.path.exists(prev_file):
            df_p = pd.read_csv(prev_file, dtype={'종목코드': str})
            # 스코어 기준 정렬 후 순위 맵 생성
            df_p = df_p.sort_values('모멘텀스코어', ascending=False).reset_index(drop=True)
            p_rank_map = {code: i+1 for i, code in enumerate(df_p['종목코드'])}
            df['전달순위'] = df['종목코드'].map(p_rank_map)
        else:
            df['전달순위'] = None # 이전 달 기록이 없으면 빈칸
    except:
        df['전달순위'] = None

    st.success(f"**{selected_year}년 {selected_month}월** (추출 기준일: {df['기준일(월말)'].iloc[0]})")

    # 데이터 스타일링
    def style_returns(val):
        if val > 0: return 'color: #FF4B4B; font-weight: bold;'
        elif val < 0: return 'color: #3182CE; font-weight: bold;'
        return ''

    df.index = range(1, len(df) + 1)
    df['종목명_L'] = df.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)

    # --- [업그레이드: 선택 이벤트 감지] ---
    event = st.dataframe(
        df.style.map(style_returns, subset=['다음달수익률(%)']),
        use_container_width=True, height=500,
        on_select="rerun", # 엑셀 스타일 계산기 작동
        selection_mode="multi_row",
        column_order=['시장', '종목명_L', '기준가', '모멘텀스코어', '전달순위', '다음달수익률(%)'],
        column_config={
            "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"),
            "기준가": st.column_config.NumberColumn("현재가", format="%,d"),
            "모멘텀스코어": st.column_config.NumberColumn(format="%.1f"),
            "전달순위": st.column_config.NumberColumn("전달 순위", format="%d위"), # ⭐ 숫자 정렬 지원
            "다음달수익률(%)": st.column_config.NumberColumn("익월 수익률", format="%.2f %%")
        }
    )

    # --- [하단 지표 및 엑셀 스타일 계산기] ---
    selected_rows = event.selection.rows
    
    if selected_rows:
        # 엑셀 스타일 계산기 (선택 시)
        st.markdown("---")
        st.subheader("📝 선택 종목 분석 (상태 표시줄)")
        s_df = df.iloc[selected_rows]
        avg_ret = s_df['다음달수익률(%)'].mean()
        win_rate = (s_df['다음달수익률(%)'] > 0).mean() * 100
        
        cols = st.columns(3)
        cols[0].metric("선택 종목 수", f"{len(selected_rows)}개")
        cols[1].metric("선택 평균 수익률", f"{avg_ret:.2f}%")
        cols[2].metric("선택 승률", f"{win_rate:.1f}%")
    else:
        # 기본 상위권 성적표 (미선택 시)
        def get_stats(data, n):
            subset = data.head(n)
            if subset.empty: return "0.00%", "0%"
            avg = subset['다음달수익률(%)'].mean()
            win = (subset['다음달수익률(%)'] > 0).mean() * 100
            return f"{avg:.2f}%", f"{win:.1f}%"

        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        t10_a, t10_w = get_stats(df, 10)
        c1.metric("🏆 Top 10 성적", t10_a, f"승률 {t10_w}")
        t20_a, t20_w = get_stats(df, 20)
        c2.metric("🥈 Top 20 성적", t20_a, f"승률 {t20_w}")
        t30_a, t30_w = get_stats(df, 30)
        c3.metric("🥉 Top 30 성적", t30_a, f"승률 {t30_w}")
