import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="모멘텀 투자 도우미", layout="wide")
st.title("📈 코스피/코스닥 시총 상위 150 모멘텀 순위 (총 300종목)")
st.write("사용자 맞춤형 모멘텀 가중치: (1개월*-0.2) + (3개월*0.8) + (6개월*0.5) + (12개월*0.2)")
st.write("※ 매월 말일 기준으로 계산되어 다음 달 1일에 자동 업데이트됩니다.")

file_path = 'momentum_data.csv'

if os.path.exists(file_path):
    # 엑셀을 읽어올 때 종목코드가 숫자(예: 005930 -> 5930)로 변하는 걸 막기 위해 문자로 읽어옵니다.
    df_momentum = pd.read_csv(file_path, dtype={'종목코드': str})
    
    base_date_str = df_momentum['기준일(월말)'].iloc[0]
    st.success(f"✅ 현재 데이터 기준일: **{base_date_str}**")
    
    market_filter = st.radio(
        "조회할 시장을 선택하세요:",
        ('전체 보기', 'KOSPI만 보기', 'KOSDAQ만 보기'),
        horizontal=True
    )
    
    if market_filter == 'KOSPI만 보기':
        df_display = df_momentum[df_momentum['시장'] == 'KOSPI'].copy()
    elif market_filter == 'KOSDAQ만 보기':
        df_display = df_momentum[df_momentum['시장'] == 'KOSDAQ'].copy()
    else:
        df_display = df_momentum.copy()
        
    # ⭐ 1. 순위(인덱스)를 0이 아닌 1부터 시작하도록 수정
    df_display.index = range(1, len(df_display) + 1)
    
    # ⭐ 2. 종목코드를 무조건 6자리로 맞추기 (앞에 0 채우기)
    df_display['종목코드'] = df_display['종목코드'].str.zfill(6)
    
    # ⭐ 3. 네이버 금융 링크 컬럼 만들기
    df_display['차트보기'] = "https://finance.naver.com/item/main.naver?code=" + df_display['종목코드']
    
    # 표 출력 (링크를 예쁜 버튼처럼 보여주는 기능 포함)
    st.dataframe(
        df_display,
        use_container_width=True,
        column_config={
            "차트보기": st.column_config.LinkColumn(
                "📈 차트 확인", 
                help="클릭하면 네이버 금융으로 이동합니다.",
                display_text="네이버 금융 열기" # 화면에는 주소 대신 이 글씨가 보입니다.
            )
        }
    )
else:
    st.warning("데이터를 수집하는 중이거나 파일이 없습니다. (자동화 스크립트 실행 대기 중)")
