import streamlit as st
import pandas as pd
import os
import glob

st.set_page_config(page_title="S&P 500 기록보관소", layout="wide")

# CSS: 사용자님이 공유해주신 초밀착 및 투명 디자인 완벽 적용
st.markdown("""
    <style>
    .block-container { padding-top: 2rem !important; }
    h1 { font-size: 1.8rem !important; font-weight: 800; margin-bottom: 20px; }
    /* 표와 하단 지표 사이 간격 최소화 */
    [data-testid="stDataFrame"] { margin-bottom: -20px !important; }
    /* 메트릭 배경 투명화 및 시인성 확보 */
    .stMetric { background-color: transparent !important; padding: 0px !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("📁 S&P 500 월별 모멘텀 기록보관소")

# S&P 500 전용 아카이브 폴더 설정
folder, prefix = "archive_sp500", "momentum_sp500_"
files = glob.glob(f"{folder}/{prefix}*.csv")

if not files:
    st.info("데이터가 없습니다. archive_sp500 폴더를 확인해주세요.")
else:
    # 1. 데이터 구조 파악 (연도별로 월 리스트 저장)
    data_struct = {}
    for f in files:
        fname = os.path.basename(f)
        try:
            # 파일명 형식: momentum_sp500_2026_03.csv
            date_part = fname.replace(prefix, "").replace(".csv", "")
            year, month = date_part.split('_')
            if year not in data_struct: data_struct[year] = []
            data_struct[year].append(month)
        except: continue

    # 연도는 최신순 (2026, 2025...)
    sorted_years = sorted(data_struct.keys(), reverse=True)
    
    col_y, col_m, _ = st.columns([1, 1, 4])
    with col_y:
        selected_year = st.selectbox("📅 연도", sorted_years)
    with col_m:
        # 월은 1월부터 순서대로
        available_months = sorted(data_struct[selected_year], key=lambda x: int(x))
        selected_month = st.selectbox("🌙 월", available_months)

    # 데이터 로드
    target_file = f"{folder}/{prefix}{selected_year}_{selected_month}.csv"
    df = pd.read_csv(target_file, dtype={'종목코드': str})
    
    # 기준일 표시 (기준일 또는 기준일(월말) 컬럼 대응)
    ref_col = '기준일(월말)' if '기준일(월말)' in df.columns else '기준일'
    st.success(f"**{selected_year}년 {selected_month}월** (추출 기준일: {df[ref_col].iloc[0]})")

    # 2. 메인 표 출력 스타일 설정
    def style_returns(val):
        if val > 0: return 'color: #FF4B4B; font-weight: bold;' # 상승: 빨강
        elif val < 0: return 'color: #3182CE; font-weight: bold;' # 하락: 파랑
        return ''

    df.index = range(1, len(df) + 1)
    
    # 미국 주식은 구글 파이낸스 링크로 연결 (사용자님 선호도 반영)
    df['종목명_L'] = df.apply(lambda r: f"https://www.google.com/finance/quote/{r['종목코드']}:NASDAQ#{r['종목명']}", axis=1)

    st.dataframe(
        df.style.map(style_returns, subset=['다음달수익률(%)']),
        use_container_width=True, height=500,
        column_order=['시장', '종목명_L', '기준가', '모멘텀스코어', '다음달수익률(%)'],
        column_config={
            "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"),
            "기준가": st.column_config.NumberColumn(format="$ %.2f"), # 달러 표시
            "모멘텀스코어": st.column_config.NumberColumn(format="%.1f"),
            "다음달수익률(%)": st.column_config.NumberColumn(format="%.2f %%")
        }
    )

    # 3. 상위권 포트폴리오 성적 (표 바로 밑 밀착 배치)
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
