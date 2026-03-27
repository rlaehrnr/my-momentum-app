import streamlit as st
import pandas as pd
import os

# 1. 페이지 설정 및 제목 (날짜 통합)
st.set_page_config(page_title="한국시장 모멘텀 순위", layout="wide")

file_path = 'momentum_data.csv'

if os.path.exists(file_path):
    df_raw = pd.read_csv(file_path, dtype={'종목코드': str})
    base_date = df_raw['기준일(월말)'].iloc[0]
    
    # 제목에 날짜 합치기
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

    # 3. 기본으로 보여줄 컬럼 순서 (여기에 없는 '시장', '종목코드'는 데이터에만 존재하고 숨겨짐)
    # 엑셀의 '숨기기'와 같은 효과입니다.
    display_order = ['통합티커', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어']

    # 4. 메인 표 출력 (15행 높이 설정)
    st.dataframe(
        df,
        use_container_width=True,
        height=560,  # ⭐ 헤더 + 15개 행이 한눈에 들어오는 최적의 높이
        column_order=display_order, # ⭐ 화면에 보일 컬럼들만 순서대로 배치
        column_config={
            "종목명": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"),
            "기준가": st.column_config.NumberColumn(format="%d"),
            "모멘텀스코어": st.column_config.NumberColumn(format="%.2f"),
        }
    )

else:
    st.title("📊 한국시장 모멘텀 순위")
    st.warning("데이터 파일을 찾을 수 없습니다.")
