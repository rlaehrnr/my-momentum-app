import streamlit as st
import pandas as pd
import os

# 1. 페이지 설정 및 제목 (기준일 통합)
st.set_page_config(page_title="한국시장 모멘텀 순위", layout="wide")

file_path = 'momentum_data.csv'

if os.path.exists(file_path):
    df_raw = pd.read_csv(file_path, dtype={'종목코드': str})
    base_date = df_raw['기준일(월말)'].iloc[0]
    
    # 제목에 기준일 포함 (기존 날짜 표시 삭제)
    st.title(f"📊 한국시장 모멘텀 순위 (기준일: {base_date})")
    st.write("가중치: (1개월*-0.2) + (3개월*0.8) + (6개월*0.5) + (12개월*0.2)")

    # 2. 데이터 전처리
    df = df_raw.copy()
    df.index = range(1, len(df) + 1)
    df['종목코드'] = df['종목코드'].str.zfill(6)
    df['통합티커'] = df['시장'] + ":" + df['종목코드']
    
    # 네이버 금융 링크 생성
    def make_link(row):
        return f"https://m.stock.naver.com/fchart/domestic/stock/{row['종목코드']}#{row['종목명']}"
    df['종목명'] = df.apply(make_link, axis=1)

    # 3. 엑셀 스타일 표 구성
    # 사용자님이 원하신 '기본은 숨김, 원하면 표시'를 위해 column_order를 사용합니다.
    # 여기에 적히지 않은 '시장', '종목코드' 등은 표 상단 툴바에서 꺼낼 수 있습니다.
    display_order = ['통합티커', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어']

    st.dataframe(
        df,
        use_container_width=True,
        column_order=display_order, # ⭐ 기본으로 보여줄 순서 (나머지는 자동 숨김)
        column_config={
            "종목명": st.column_config.LinkColumn(
                "종목명", 
                display_text=r"#(.+)" 
            ),
            "기준가": st.column_config.NumberColumn(format="%d"),
            "모멘텀스코어": st.column_config.NumberColumn(format="%.2f"),
        }
    )
    
    st.info("💡 **엑셀처럼 사용하기:** 표 우측 상단의 **아이콘(🔍 또는 ☰)**을 누르면 숨겨진 '시장' 컬럼을 꺼내거나, 원하는 종목을 필터링할 수 있습니다.")

else:
    st.title("📊 한국시장 모멘텀 순위")
    st.warning("데이터 파일을 찾을 수 없습니다.")
