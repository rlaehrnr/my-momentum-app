import streamlit as st
import pandas as pd
import os

# 1. 페이지 설정 및 제목 (날짜 통합)
st.set_page_config(page_title="한국시장 모멘텀 순위", layout="wide")

file_path = 'momentum_data.csv'

if os.path.exists(file_path):
    df_raw = pd.read_csv(file_path, dtype={'종목코드': str})
    base_date = df_raw['기준일(월말)'].iloc[0]
    
    # 제목에 날짜를 합치고 깔끔하게 배치
    st.title(f"📊 한국시장 모멘텀 순위 (기준일: {base_date})")
    st.write("가중치: (1개월*-0.2) + (3개월*0.8) + (6개월*0.5) + (12개월*0.2)")

    # 2. 데이터 전처리
    df = df_raw.copy()
    df.index = range(1, len(df) + 1)
    df['종목코드'] = df['종목코드'].str.zfill(6)
    df['통합티커'] = df['시장'] + ":" + df['종목코드']
    
    def make_link(row):
        return f"https://m.stock.naver.com/fchart/domestic/stock/{row['종목코드']}#{row['종목명']}"
    df['종목명'] = df.apply(make_link, axis=1)

    # 3. 엑셀형 '숨김 컬럼' 제어 (상단에 아주 작게 배치)
    # 별도의 버튼 없이, 보이지 않지만 표 안에 숨겨두는 방식은 
    # 웹 환경 특성상 '멀티 셀렉트'가 가장 직관적이라 우측 상단에 작게 배치했습니다.
    cols_to_add = st.multiselect("추가 정보 보기:", ["시장", "종목코드"], help="표에서 숨겨진 정보를 꺼내볼 수 있습니다.")

    # 기본 노출 순서
    base_cols = ['통합티커', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어']
    final_display_cols = base_cols + cols_to_add

    # 4. 메인 표 출력 (20행 높이 설정)
    st.dataframe(
        df[final_display_cols],
        use_container_width=True,
        height=735,  # ⭐ 약 20행 + 헤더가 한눈에 들어오는 최적의 높이입니다.
        column_config={
            "종목명": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"),
            "기준가": st.column_config.NumberColumn(format="%d"),
            "모멘텀스코어": st.column_config.NumberColumn(format="%.2f"),
        }
    )

else:
    st.title("📊 한국시장 모멘텀 순위")
    st.warning("데이터 파일을 찾을 수 없습니다.")
