import streamlit as st
import pandas as pd
import os

# 페이지 설정
st.set_page_config(page_title="한국시장 모멘텀 순위", layout="wide")

file_path = 'momentum_data.csv'

if os.path.exists(file_path):
    # 1. 데이터 불러오기
    df_momentum = pd.read_csv(file_path, dtype={'종목코드': str})
    
    # 2. 제목 설정 (기준일 포함 및 기존 기준일 표시 삭제)
    base_date_str = df_momentum['기준일(월말)'].iloc[0]
    st.title(f"📊 한국시장 모멘텀 순위 (기준일: {base_date_str})")
    st.write("가중치: (1개월*-0.2) + (3개월*0.8) + (6개월*0.5) + (12개월*0.2)")

    # 3. 데이터 전처리
    df_display = df_momentum.copy()
    df_display.index = range(1, len(df_display) + 1)
    df_display['종목코드'] = df_display['종목코드'].str.zfill(6)
    df_display['통합티커'] = df_display['시장'] + ":" + df_display['종목코드']
    
    # 네이버 금융 링크 생성
    def make_link(row):
        return f"https://m.stock.naver.com/fchart/domestic/stock/{row['종목코드']}#{row['종목명']}"
    df_display['종목명'] = df_display.apply(make_link, axis=1)

    # 4. 컬럼 관리 (기본 노출 vs 숨김 항목)
    # 기본적으로 보여줄 컬럼들
    default_cols = ['통합티커', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어']
    # 사용자가 추가로 선택해서 볼 수 있는 숨겨진 컬럼들
    hidden_cols = ['시장', '종목코드']
    all_available_cols = default_cols + hidden_cols

    # ⭐ 상단 컬럼 선택기 (엑셀의 숨기기 취소 기능처럼 사용)
    selected_cols = st.multiselect(
        "표에 표시할 추가 정보를 선택하세요 (시장, 종목코드 등):",
        options=hidden_cols,
        default=[]
    )

    # 최종적으로 화면에 뿌릴 컬럼 순서 정렬
    final_cols = default_cols + selected_cols
    
    # 5. 메인 데이터프레임 출력
    # Streamlit의 st.dataframe은 자동으로 열 필터링(Excel 방식) 기능을 지원합니다.
    st.dataframe(
        df_display[final_cols],
        use_container_width=True,
        column_config={
            "종목명": st.column_config.LinkColumn(
                "종목명", 
                help="클릭하면 네이버 모바일 차트로 이동합니다.",
                display_text=r"#(.+)" 
            ),
            "기준가": st.column_config.NumberColumn(format="%d"),
            "모멘텀스코어": st.column_config.NumberColumn(format="%.2f"),
        },
        hide_index=False # 순위(1, 2, 3...)를 보기 위해 인덱스 유지
    )
    
    st.info("💡 팁: 표의 각 컬럼 헤더에 마우스를 올리면 나타나는 **돋보기나 필터 아이콘**을 눌러 엑셀처럼 KOSPI/KOSDAQ을 골라볼 수 있습니다.")

else:
    st.title("📊 한국시장 모멘텀 순위")
    st.warning("데이터 파일(`momentum_data.csv`)을 찾을 수 없습니다. 로봇이 데이터를 생성할 때까지 기다려주세요.")
