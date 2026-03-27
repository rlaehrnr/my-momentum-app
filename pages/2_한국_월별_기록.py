import streamlit as st
import pandas as pd
import os
import glob

st.set_page_config(page_title="한국 모멘텀 기록보관소", layout="wide")

# CSS 설정
st.markdown("""<style>.block-container { padding-top: 2.5rem !important; } h1 { font-size: 2rem !important; }</style>""", unsafe_allow_html=True)

st.title("📁 한국 월별 모멘텀 기록보관소")

folder = "archive"
prefix = "momentum_"

# 파일 목록 가져오기 (최신순)
files = glob.glob(f"{folder}/{prefix}*.csv")
files.sort(reverse=True)

if not files:
    st.info("한국 시장 기록이 아직 없습니다. 로봇이 월말에 첫 배달을 완료하면 나타납니다.")
else:
    # 파일명(예: momentum_2026_03.csv)에서 '투자 월' 추출
    file_map = {}
    for f in files:
        fname = os.path.basename(f)
        date_part = fname.replace(prefix, "").replace(".csv", "") # '2026_03'
        year, month = date_part.split('_')
        display_name = f"📅 {year}년 {month}월 투자 성적표"
        file_map[display_name] = f

    selected_display = st.selectbox("조회할 달을 선택하세요", list(file_map.keys()))
    selected_file = file_map[selected_display]

    df = pd.read_csv(selected_file, dtype={'종목코드': str})
    base_date = df['기준일(월말)'].iloc[0]
    
    st.success(f"✅ 이 리스트는 **{base_date}** 종가를 기준으로 추출된 종목들입니다.")

    def color_returns(val):
        if val > 0: return 'color: #FF4B4B; font-weight: bold;'
        elif val < 0: return 'color: #31333F; background-color: #E6F3FF;'
        return ''

    df.index = range(1, len(df) + 1)
    df['종목명'] = df.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)

    st.dataframe(
        df.style.applymap(color_returns, subset=['다음달수익률(%)']),
        use_container_width=True, height=600,
        column_order=['시장', '종목명', '종목코드', '기준가', '모멘텀스코어', '다음달수익률(%)'],
        column_config={
            "종목명": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"),
            "기준가": st.column_config.NumberColumn(format="%d"),
            "모멘텀스코어": st.column_config.NumberColumn(format="%.1f"),
            "다음달수익률(%)": st.column_config.NumberColumn(format="%.1f %%")
        }
    )
    
    avg_ret = df['다음달수익률(%)'].mean()
    win_rate = (df['다음달수익률(%)'] > 0).sum() / len(df) * 100
    c1, c2 = st.columns(2)
    c1.metric("평균 수익률", f"{avg_ret:.1f}%")
    c2.metric("상승 종목 비율", f"{win_rate:.1f}%")
