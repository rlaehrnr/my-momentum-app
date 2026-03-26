import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="모멘텀 투자 도우미", layout="wide")
st.title("📈 코스피/코스닥 시총 상위 150 모멘텀 순위 (총 300종목)")
st.write("사용자 맞춤형 모멘텀 가중치: (1개월*-0.2) + (3개월*0.8) + (6개월*0.5) + (12개월*0.2)")
st.write("※ 매월 말일 기준으로 계산되어 다음 달 1일에 자동 업데이트됩니다.")

file_path = 'momentum_data.csv'

if os.path.exists(file_path):
    df_momentum = pd.read_csv(file_path)
    
    base_date_str = df_momentum['기준일(월말)'].iloc[0]
    st.success(f"✅ 현재 데이터 기준일: **{base_date_str}**")
    
    # ⭐ 시장 필터 기능 추가
    market_filter = st.radio(
        "조회할 시장을 선택하세요:",
        ('전체 보기', 'KOSPI만 보기', 'KOSDAQ만 보기'),
        horizontal=True
    )
    
    if market_filter == 'KOSPI만 보기':
        df_display = df_momentum[df_momentum['시장'] == 'KOSPI']
    elif market_filter == 'KOSDAQ만 보기':
        df_display = df_momentum[df_momentum['시장'] == 'KOSDAQ']
    else:
        df_display = df_momentum
        
    st.dataframe(df_display, use_container_width=True)
else:
    st.warning("데이터를 수집하는 중이거나 파일이 없습니다. (자동화 스크립트 실행 대기 중)")
