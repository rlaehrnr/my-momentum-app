import streamlit as st
import pandas as pd
import os
import glob

st.set_page_config(page_title="한국 모멘텀 기록보관소", layout="wide")
st.markdown("""<style>.block-container { padding-top: 2.5rem !important; } h1 { font-size: 2rem !important; }</style>""", unsafe_allow_html=True)

st.title("📁 한국 월별 모멘텀 기록보관소")

folder, prefix = "archive", "momentum_"
files = sorted(glob.glob(f"{folder}/{prefix}*.csv"), reverse=True)

if not files:
    st.info("기록이 아직 없습니다.")
else:
    file_map = {f"📅 {os.path.basename(f).replace(prefix, '').replace('.csv', '').split('_')[0]}년 {os.path.basename(f).replace(prefix, '').replace('.csv', '').split('_')[1]}월 투자 성적표": f for f in files}
    selected_file = file_map[st.selectbox("조회할 달을 선택하세요", list(file_map.keys()))]

    df = pd.read_csv(selected_file, dtype={'종목코드': str})
    st.success(f"✅ 이 리스트는 **{df['기준일(월말)'].iloc[0]}** 종가를 기준으로 추출되었습니다.")

    df.index = range(1, len(df) + 1)
    df['종목명'] = df.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)

    st.dataframe(
        df.style.applymap(lambda v: 'color: #FF4B4B; font-weight: bold;' if v > 0 else ('color: #31333F; background-color: #E6F3FF;' if v < 0 else ''), subset=['다음달수익률(%)']),
        use_container_width=True, height=600,
        column_order=['시장', '종목명', '기준가', '모멘텀스코어', '다음달수익률(%)'],
        column_config={"종목명": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), "기준가": st.column_config.NumberColumn(format="%d"), "다음달수익률(%)": st.column_config.NumberColumn(format="%.1f %%")}
    )
    
    avg_ret = df['다음달수익률(%)'].mean()
    win_rate = (df['다음달수익률(%)'] > 0).sum() / len(df) * 100
    c1, c2 = st.columns(2)
    c1.metric("평균 수익률", f"{avg_ret:.1f}%")
    c2.metric("상승 종목 비율", f"{win_rate:.1f}%")
