import streamlit as st
import pandas as pd
import os
import glob
from datetime import datetime, timedelta
import numpy as np

# 1. 페이지 설정
st.set_page_config(page_title="한국 모멘텀 기록보관소", layout="wide")

# CSS: 디자인 및 가독성 최적화
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem !important; }
    h1 { font-size: 1.8rem !important; font-weight: 800; margin-bottom: 20px; }
    [data-testid="stDataFrame"] { margin-bottom: -10px !important; }
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
    # 데이터 구조 파악 (연도별 월 리스트)
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

    # --- [데이터 로드 및 컬럼 자동 감지] ---
    target_file = f"{folder}/{prefix}{selected_year}_{selected_month}.csv"
    df = pd.read_csv(target_file, dtype={'종목코드': str})
    
    # 🔍 컬럼명 유연하게 찾기 (에러 방지의 핵심)
    date_col = next((c for c in df.columns if '기준일' in c), None)
    score_col = next((c for c in df.columns if '모멘텀스코어' in c), '모멘텀스코어')
    # '수익률' 글자가 포함된 컬럼을 찾고, 없으면 None 반환
    ret_col = next((c for c in df.columns if '수익률' in c), None)

    # 전달 순위 계산 (직전 달 파일 대조)
    try:
        curr_dt = datetime(int(selected_year), int(selected_month), 1)
        prev_dt = curr_dt - timedelta(days=1)
        prev_file = f"{folder}/{prefix}{prev_dt.strftime('%Y_%m')}.csv"
        if os.path.exists(prev_file):
            df_p = pd.read_csv(prev_file, dtype={'종목코드': str})
            p_score_col = next((c for c in df_p.columns if '모멘텀스코어' in c), None)
            if p_score_col:
                df_p = df_p.sort_values(p_score_col, ascending=False).reset_index(drop=True)
                p_rank_map = {code: i+1 for i, code in enumerate(df_p['종목코드'])}
                df['전달순위'] = df['종목코드'].map(p_rank_map)
        else: df['전달순위'] = None
    except: df['전달순위'] = None

    display_date = df[date_col].iloc[0] if date_col and date_col in df.columns else f"{selected_year}-{selected_month}"
    st.success(f"**{selected_year}년 {selected_month}월** (기준일: {display_date})")

    # 스타일 함수
    def style_returns(val):
        try:
            num = float(val)
            if num > 0: return 'color: #FF4B4B; font-weight: bold;'
            elif num < 0: return 'color: #3182CE; font-weight: bold;'
        except: pass
        return ''

    df.index = range(1, len(df) + 1)
    df['종목명_L'] = df.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)

    # --- [데이터프레임 출력 및 설정] ---
    # 보여줄 컬럼 리스트 구성
    cols_to_show = ['시장', '종목명_L', '기준가', score_col, '전달순위']
    if ret_col: cols_to_show.append(ret_col)

    # 컬럼 상세 설정
    config = {
        "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"),
        "기준가": st.column_config.NumberColumn("현재가", format="%,d"),
        score_col: st.column_config.NumberColumn("스코어", format="%.1f"),
        "전달순위": st.column_config.NumberColumn("전달 순위", format="%d위")
    }
    if ret_col:
        config[ret_col] = st.column_config.NumberColumn("익월 수익률", format="%.2f%%")

    # ⭐ [에러 방지 핵심] 수익률 컬럼이 있을 때만 색상을 칠함
    styled_df = df.style
    if ret_col:
        styled_df = styled_df.map(style_returns, subset=[ret_col])

    # 메인 표 출력
    event = st.dataframe(
        styled_df,
        use_container_width=True, height=500,
        on_select="rerun",
        selection_mode="multi_row",
        column_order=cols_to_show,
        column_config=config
    )

    # --- [하단 지표 및 계산기] ---
    selected_rows = event.selection.rows
    if selected_rows:
        st.markdown("---")
        st.subheader("📝 선택 영역 분석")
        s_df = df.iloc[selected_rows]
        c1, c2, c3 = st.columns(3)
        c1.metric("선택 종목", f"{len(selected_rows)}개")
        if ret_col:
            avg_r = s_df[ret_col].mean()
            win_r = (s_df[ret_col] > 0).mean() * 100
            c2.metric("평균 수익률", f"{avg_r:.2f}%")
            c3.metric("승률", f"{win_r:.1f}%")
    else:
        st.markdown("---")
        def show_top_stats(n, col):
            subset = df.head(n)
            if ret_col and not subset.empty:
                avg = subset[ret_col].mean()
                win = (subset[ret_col] > 0).mean() * 100
                col.metric(f"🏆 Top {n} 성적", f"{avg:.2f}%", f"승률 {win:.1f}%")
            else:
                col.metric(f"🏆 Top {n} 성적", "수익률 정보 없음")

        sc1, sc2, sc3 = st.columns(3)
        show_top_stats(10, sc1)
        show_top_stats(20, sc2)
        show_top_stats(30, sc3)
