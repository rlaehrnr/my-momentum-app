import streamlit as st
import pandas as pd
import os
import glob

st.set_page_config(page_title="한국 모멘텀 기록보관소", layout="wide")

# CSS: 초밀착 레이아웃 및 가독성 설정
st.markdown("""
    <style>
    .block-container { padding-top: 2rem !important; }
    h1 { font-size: 1.8rem !important; font-weight: 800; margin-bottom: 20px; }
    /* 표 안의 숫자 가독성 향상 */
    [data-testid="stDataFrame"] td { font-family: 'Pretendard', sans-serif; }
    </style>
    """, unsafe_allow_html=True)

st.title("📁 한국 월별 모멘텀 기록보관소")

folder, prefix = "archive", "momentum_"
files = glob.glob(f"{folder}/{prefix}*.csv")

if not files:
    st.info("데이터가 없습니다. archive 폴더를 확인해주세요.")
else:
    # 1. 연도/월 선택 로직 (이전과 동일하게 편리하게 유지)
    data_struct = {}
    for f in files:
        fname = os.path.basename(f)
        date_part = fname.replace(prefix, "").replace(".csv", "")
        year, month = date_part.split('_')
        if year not in data_struct: data_struct[year] = []
        data_struct[year].append(month)

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

    # 2. 메인 표 출력 (눈부신 배경색 제거, 글자색만 유지)
    def style_returns(val):
        if val > 0: return 'color: #D32F2F; font-weight: bold;' # 빨간색 글자
        elif val < 0: return 'color: #1976D2; font-weight: bold;' # 파란색 글자
        return ''

    df.index = range(1, len(df) + 1)
    df['종목명_L'] = df.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)

    st.dataframe(
        df.style.map(style_returns, subset=['다음달수익률(%)']),
        use_container_width=True, height=520,
        column_order=['시장', '종목명_L', '기준가', '모멘텀스코어', '다음달수익률(%)'],
        column_config={
            "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"),
            "기준가": st.column_config.NumberColumn(format="%d"),
            "모멘텀스코어": st.column_config.NumberColumn(format="%.1f"),
            "다음달수익률(%)": st.column_config.NumberColumn(format="%.2f %%")
        }
    )

    st.markdown("---")

    # 3. 상위권 포트폴리오 성적 (표 하단으로 이동 및 깔끔한 칸 맞춤)
    c1, c2, c3 = st.columns(3)
    
    def get_stats(data, n):
        subset = data.head(n)
        avg = subset['다음달수익률(%)'].mean()
        win = (subset['다음달수익률(%)'] > 0).sum() / len(subset) * 100
        return f"{avg:.2f}%", f"승률 {win.replace('.0', '') if win == int(win) else f'{win:.1f}'}%"

    # Top 10 성적
    t10_avg, t10_win = get_stats(df, 10)
    c1.metric("🏆 Top 10 성적", t10_avg, t10_win)

    # Top 20 성적
    t20_avg, t20_win = get_stats(df, 20)
    c2.metric("🥈 Top 20 성적", t20_avg, t20_win)

    # Top 30 성적
    t30_avg, t30_win = get_stats(df, 30)
    c3.metric("🥉 Top 30 성적", t30_avg, t30_win)
