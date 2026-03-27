import streamlit as st
import pandas as pd
import os
import glob

st.set_page_config(page_title="한국 모멘텀 기록보관소", layout="wide")

# CSS: 가독성 극대화 및 레이아웃 조정
st.markdown("""
    <style>
    .block-container { padding-top: 2rem !important; }
    h1 { font-size: 2rem !important; color: #1E1E1E; }
    .stSelectbox { margin-bottom: -10px; }
    /* 수익률 테이블 텍스트 중앙 정렬 */
    [data-testid="stDataFrame"] td { text-align: center !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("📁 한국 월별 모멘텀 기록보관소")

folder = "archive"
prefix = "momentum_"

# 1. 파일 목록 가져오기 및 연/월 추출
files = glob.glob(f"{folder}/{prefix}*.csv")
if not files:
    st.info("데이터가 없습니다. archive 폴더에 CSV 파일을 업로드해주세요.")
else:
    # 파일명에서 연도와 월을 추출하여 딕셔너리 구조 생성
    data_struct = {}
    for f in files:
        fname = os.path.basename(f)
        date_part = fname.replace(prefix, "").replace(".csv", "") # '2026_03'
        year, month = date_part.split('_')
        if year not in data_struct:
            data_struct[year] = []
        data_struct[year].append(month)

    # 연도와 월 정렬
    sorted_years = sorted(data_struct.keys(), reverse=True)

    # 2. 연도와 월 선택박스 (가로 배치)
    col_y, col_m, col_empty = st.columns([1, 1, 4])
    with col_y:
        selected_year = st.selectbox("📅 연도 선택", sorted_years)
    with col_m:
        available_months = sorted(data_struct[selected_year], reverse=True)
        selected_month = st.selectbox("🌙 월 선택", available_months)

    # 선택된 파일 로드
    target_file = f"{folder}/{prefix}{selected_year}_{selected_month}.csv"
    df = pd.read_csv(target_file, dtype={'종목코드': str})
    
    # 상단 안내 문구
    st.success(f"✅ **{selected_year}년 {selected_month}월 성적표** (추출 기준일: {df['기준일(월말)'].iloc[0]})")

    # 3. Top 10, 20, 30 수익률 분석 지표
    def get_top_stats(data):
        stats = []
        for n in [10, 20, 30]:
            subset = data.head(n)
            avg_ret = subset['다음달수익률(%)'].mean()
            win_rate = (subset['다음달수익률(%)'] > 0).sum() / len(subset) * 100
            stats.append({
                "대상": f"Top {n}",
                "평균 수익률": f"{avg_ret:.2f}%",
                "상승 종목 비율 (승률)": f"{win_rate:.1f}%"
            })
        return pd.DataFrame(stats)

    st.subheader("🏆 상위권 포트폴리오 성적")
    stats_df = get_top_stats(df)
    
    # 메트릭을 가로로 배치
    c1, c2, c3 = st.columns(3)
    ranks = ["Top 10", "Top 20", "Top 30"]
    cols = [c1, c2, c3]
    for i in range(3):
        cols[i].metric(stats_df.iloc[i]['대상'], stats_df.iloc[i]['평균 수익률'], stats_df.iloc[i]['상승 종목 비율 (승률)'])

    st.markdown("---")

    # 4. 수익률 가독성 스타일링 함수
    def style_returns(val):
        if val > 0:
            return 'color: #D32F2F; background-color: #FFEBEE; font-weight: bold;' # 진한 빨강 + 연분홍 배경
        elif val < 0:
            return 'color: #1976D2; background-color: #E3F2FD; font-weight: bold;' # 진한 파랑 + 연파랑 배경
        return ''

    # 데이터프레임 출력 설정
    df.index = range(1, len(df) + 1)
    df['종목명_link'] = df.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)

    st.dataframe(
        df.style.map(style_returns, subset=['다음달수익률(%)']),
        use_container_width=True, height=550,
        column_order=['시장', '종목명_link', '기준가', '모멘텀스코어', '다음달수익률(%)'],
        column_config={
            "종목명_link": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"),
            "기준가": st.column_config.NumberColumn(format="%d"),
            "모멘텀스코어": st.column_config.NumberColumn(format="%.1f"),
            "다음달수익률(%)": st.column_config.NumberColumn(format="%.2f %%")
        }
    )
