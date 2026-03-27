import streamlit as st
import pandas as pd
import os
import glob

st.set_page_config(page_title="한국 모멘텀 기록보관소", layout="wide")

# CSS: 레이아웃 초밀착 및 배경색 완전 제거
st.markdown("""
    <style>
    .block-container { padding-top: 2rem !important; }
    h1 { font-size: 1.8rem !important; font-weight: 800; margin-bottom: 20px; }
    /* 표와 하단 지표 사이의 간격 최소화 */
    [data-testid="stDataFrame"] { margin-bottom: -20px !important; }
    /* 배경색 제거 및 텍스트 시인성 확보 */
    .stMetric { background-color: transparent !important; padding: 0px !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("📁 한국 월별 모멘텀 기록보관소")

folder, prefix = "archive", "momentum_"
files = glob.glob(f"{folder}/{prefix}*.csv")

if not files:
    st.info("데이터가 없습니다. archive 폴더를 확인해주세요.")
else:
    # 1. 연도/월 선택 로직
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
        available_months = sorted(data_struct[selected_year], reverse=True)
        selected_month = st.selectbox("🌙 월", available_months)

    # 데이터 로드
    target_file = f"{folder}/{prefix}{selected_year}_{selected_month}.csv"
    df = pd.read_csv(target_file, dtype={'종목코드': str})
    
    st.success(f"**{selected_year}년 {selected_month}월** (추출 기준일: {df['기준일(월말)'].iloc[0]})")

    # 2. 메인 표 출력 (글자색 포인트만 유지)
    def style_returns(val):
        if val > 0: return 'color: #FF4B4B; font-weight: bold;' # 밝은 빨강 (다크모드 대응)
        elif val < 0: return 'color: #3182CE; font-weight: bold;' # 밝은 파랑 (다크모드 대응)
        return ''

    df.index = range(1, len(df) + 1)
    df['종목명_L'] = df.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)

    st.dataframe(
        df.style.map(style_returns, subset=['다음달수익률(%)']),
        use_container_width=True, height=500,
        column_order=['시장', '종목명_L', '기준가', '모멘텀스코어', '다음달수익률(%)'],
        column_config={
            "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"),
            "기준가": st.column_config.NumberColumn(format="%d"),
            "모멘텀스코어": st.column_config.NumberColumn(format="%.1f"),
            "다음달수익률(%)": st.column_config.NumberColumn(format="%.2f %%")
        }
    )

    # 3. 상위권 포트폴리오 성적 (표 바로 밑에 투명하게 배치)
    def get_stats(data, n):
        subset = data.head(n)
        if subset.empty: return "0.00%", "승률 0%"
        avg = subset['다음달수익률(%)'].mean()
        win = (subset['다음달수익률(%)'] > 0).sum() / len(subset) * 100
        win_display = int(win) if win == int(win) else round(win, 1)
        return f"{avg:.2f}%", f"승률 {win_display}%"

    c1, c2, c3 = st.columns(3)
    
    t10_avg, t10_win = get_stats(df, 10)
    c1.metric("🏆 Top 10 성적", t10_avg, t10_win)

    t20_avg, t20_win = get_stats(df, 20)
    c2.metric("🥈 Top 20 성적", t20_avg, t20_win)

    t30_avg, t30_win = get_stats(df, 30)
    c3.metric("🥉 Top 30 성적", t30_avg, t30_win)
