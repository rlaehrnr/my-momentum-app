import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="모멘텀 투자 도우미", layout="wide")
st.title("📈 코스피/코스닥 시총 상위 150 모멘텀 순위 (총 300종목)")
st.write("사용자 맞춤형 모멘텀 가중치: (1개월*-0.2) + (3개월*0.8) + (6개월*0.5) + (12개월*0.2)")
st.write("※ 매월 말일 기준으로 계산되어 다음 달 1일에 자동 업데이트됩니다.")

file_path = 'momentum_data.csv'

if os.path.exists(file_path):
    # 1. 데이터 읽기 (종목코드 앞의 0이 사라지지 않도록 문자로 읽어옴)
    df_momentum = pd.read_csv(file_path, dtype={'종목코드': str})
    
    base_date_str = df_momentum['기준일(월말)'].iloc[0]
    st.success(f"✅ 현재 데이터 기준일: **{base_date_str}**")
    
    # 2. 시장 필터 생성
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
        
    # 3. 왼쪽 순위(인덱스)를 1부터 시작하도록 맞춤
    df_display.index = range(1, len(df_display) + 1)
    
    # 4. 종목코드 6자리 맞추기 (예: 5930 -> 005930)
    df_display['종목코드'] = df_display['종목코드'].str.zfill(6)
    
    # 5. 종목명을 클릭 가능한 네이버 모바일 차트 링크로 변환 (꼼수 적용: URL#종목명)
    def make_link(row):
        return f"https://m.stock.naver.com/fchart/domestic/stock/{row['종목코드']}#{row['종목명']}"
        
    df_display['종목명'] = df_display.apply(make_link, axis=1)
    
    # 6. 화면에 보여줄 컬럼만 선택하고 순서 배치
    columns_to_show = ['시장', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어']
    df_final = df_display[columns_to_show]
    
    # 7. 표 출력
    st.dataframe(
        df_final,
        use_container_width=True,
        column_config={
            "종목명": st.column_config.LinkColumn(
                "종목명", # 표기될 컬럼 이름
                help="클릭하면 네이버 모바일 차트로 이동합니다.",
                display_text=r"#(.+)" # 링크 주소의 '#' 뒤에 있는 글자(실제 종목명)만 화면에 표시
            )
        }
    )
else:
    st.warning("데이터를 수집하는 중이거나 파일이 없습니다. (자동화 스크립트 실행 대기 중)")
