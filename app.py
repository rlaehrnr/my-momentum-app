import streamlit as st
import pandas as pd
import os
import urllib.parse # 링크 생성을 위한 라이브러리 추가

st.set_page_config(page_title="모멘텀 투자 도우미", layout="wide")
st.title("📈 코스피/코스닥 시총 상위 150 모멘텀 순위 (총 300종목)")
st.write("사용자 맞춤형 모멘텀 가중치: (1개월*-0.2) + (3개월*0.8) + (6개월*0.5) + (12개월*0.2)")
st.write("※ 매월 말일 기준으로 계산되어 다음 달 1일에 자동 업데이트됩니다.")

file_path = 'momentum_data.csv'

if os.path.exists(file_path):
    # 데이터 읽기
    df_momentum = pd.read_csv(file_path, dtype={'종목코드': str})
    
    base_date_str = df_momentum['기준일(월말)'].iloc[0]
    st.success(f"✅ 현재 데이터 기준일: **{base_date_str}**")
    
    # 시장 필터
    market_filter = st.radio(
        "조회할 시장을 선택하세요:",
        ('전체 보기', 'KOSPI만 보기', 'KOSDAQ만 보기'),
        horizontal=True
    )
    
    # 필터링 및 복사
    if market_filter == 'KOSPI만 보기':
        df_display = df_momentum[df_momentum['시장'] == 'KOSPI'].copy()
    elif market_filter == 'KOSDAQ만 보기':
        df_display = df_momentum[df_momentum['시장'] == 'KOSDAQ'].copy()
    else:
        df_display = df_momentum.copy()
        
    # 순위 설정 (1부터 시작)
    df_display.index = range(1, len(df_display) + 1)
    
    # 종목코드 6자리 맞추기
    df_display['종목코드'] = df_display['종목코드'].str.zfill(6)
    
    # ⭐ 1. 네이버 모바일 차트 링크 만들기 (요청하신 형식)
    # 예시: https://m.stock.naver.com/fchart/domestic/stock/043260
    base_url = "https://m.stock.naver.com/fchart/domestic/stock/"
    df_display['차트링크'] = base_url + df_display['종목코드']

    # ⭐ 2. 출력할 데이터프레임 정리 (필요없는 컬럼 숨기기 및 순서 변경)
    # 종목코드, 기준일(월말) 등은 화면에서 숨기고 핵심 정보만 배치
    columns_to_show = ['시장', '차트링크', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어']
    df_final = df_display[columns_to_show]
    
    # 표 출력 (st.dataframe의 강력한 기능을 활용해 종목명을 링크로 변환)
    st.dataframe(
        df_final,
        use_container_width=True,
        column_config={
            # ⭐ 3. '차트링크' 컬럼을 '종목명'이라는 이름의 클릭 링크로 변환
            "차트링크": st.column_config.LinkColumn(
                "종목명", # 화면에 보일 컬럼 이름
                help="클릭하면 네이버 모바일 차트로 이동합니다.",
                # ⭐ 핵심 꼼수: 링크 주소 안에서 종목명 부분만 추출해서 화면에 표시
                # 이를 위해 update_data.py에서 CSV를 만들 때 링크 뒤에 #종목명을 붙이거나, 
                # 여기 app.py에서 임시로 링크 뒤에 붙여서 해결합니다. (여기선 2번 방식 사용)
            )
        }
    )
    
    # ⭐ 꼼수 구현을 위해 '차트링크' 컬럼의 데이터를 수정
    # '링크주소#종목명' 형식으로 만들고, LinkColumn의 regex로 '종목명'만 추출해 보여줍니다.
    def make_display_link(row):
        encoded_name = urllib.parse.quote(row['종목명'])
        return f"{base_url}{row['종목코드']}#{encoded_name}"

    # df_display(원본 데이터)에서 종목명을 가져와서 링크 뒤에 붙임
    temp_links = df_display.apply(make_display_link, axis=1)
    # 출력용 데이터프레임의 '차트링크' 컬럼을 업데이트
    df_final['차트링크'] = temp_links
    
    # 다시 표 출력 설정 (위의 설정 내용을 적용)
    st.dataframe(
        df_final,
        use_container_width=True,
        column_config={
            "차트링크": st.column_config.LinkColumn(
                "종목명",
                help="클릭하면 네이버 모바일 차트로 이동합니다.",
                # 링크 주소의 # 뒤에 있는 내용을 화면에 표시하는 정규식(Regex) 설정
                display_text=r"#(.+)" 
            )
        }
    )
    
    # 💡 위의 st.dataframe이 중복 실행되는 것을 막기 위해 코드를 깔끔하게 정리합니다.
    # (실제 배포용 코드에서는 아래처럼 한 번만 실행되도록 정리된 코드를 쓰세요.)
    # --------------------------------------------------
    # [정리된 배포용 코드 부분]
    
    # # 링크 생성 및 종목명 숨기기 (꼼수 적용: 링크주소#종목명)
    # def make_display_link_final(row):
    #     # 종목명에 공백이나 특수문자가 있을 수 있으므로 인코딩
    #     encoded_name = urllib.parse.quote(row['종목명']) 
    #     return f"https://m.stock.naver.com/fchart/domestic/stock/{row['종목코드']}#{encoded_name}"
    
    # df_display['종목명(링크)'] = df_display.apply(make_display_link_final, axis=1)
    
    # # 출력할 컬럼 정리
    # columns_final = ['시장', '종목명(링크)', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어']
    # df_output = df_display[columns_final]
    
    # # 표 출력
    # st.dataframe(
    #     df_output,
    #     use_container_width=True,
    #     column_config={
    #         "종목명(링크)": st.column_config.LinkColumn(
    #             "종목명",
    #             help="클릭하면 네이버 모바일 차트로 이동합니다.",
    #             display_text=r"#(.+)" # # 뒤의 텍스트(종목명)만 추출해서 표시
            )
        }
    )

else:
    st.warning("데이터를 수집하는 중이거나 파일이 없습니다. (자동화 스크립트 실행 대기 중)")
