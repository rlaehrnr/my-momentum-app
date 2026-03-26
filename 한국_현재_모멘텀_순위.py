import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="모멘텀 투자 도우미", layout="wide")
st.title("📈 코스피/코스닥 시총 상위 150 모멘텀 순위")
st.write("사용자 맞춤형 모멘텀 가중치: (1개월*-0.2) + (3개월*0.8) + (6개월*0.5) + (12개월*0.2)")

file_path = 'momentum_data.csv'

if os.path.exists(file_path):
    df_momentum = pd.read_csv(file_path, dtype={'종목코드': str})
    
    base_date_str = df_momentum['기준일(월말)'].iloc[0]
    st.success(f"✅ 현재 데이터 기준일: **{base_date_str}**")
    
    market_filter = st.radio("조회할 시장 선택:", ('전체 보기', 'KOSPI만 보기', 'KOSDAQ만 보기'), horizontal=True)
    
    if market_filter == 'KOSPI만 보기':
        df_display = df_momentum[df_momentum['시장'] == 'KOSPI'].copy()
    elif market_filter == 'KOSDAQ만 보기':
        df_display = df_momentum[df_momentum['시장'] == 'KOSDAQ'].copy()
    else:
        df_display = df_momentum.copy()
        
    df_display.index = range(1, len(df_display) + 1)
    df_display['종목코드'] = df_display['종목코드'].str.zfill(6)
    df_display['통합티커'] = df_display['시장'] + ":" + df_display['종목코드']
    
    def make_link(row):
        return f"https://m.stock.naver.com/fchart/domestic/stock/{row['종목코드']}#{row['종목명']}"
    df_display['종목명'] = df_display.apply(make_link, axis=1)
    
    # ⭐ 상세 정보 보기 체크박스
    show_details = st.checkbox("🔎 종목코드 및 시장 상세 정보 보기", value=False)
    
    # 기본 노출 컬럼 (깨끗한 버전)
    cols = ['통합티커', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어']
    
    if show_details:
        cols = ['통합티커', '종목코드', '시장', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어']

    st.dataframe(
        df_display[cols],
        use_container_width=True,
        column_config={"종목명": st.column_config.LinkColumn("종목명", display_text=r"#(.+)")}
    )
else:
    st.warning("데이터 파일이 없습니다. 로봇이 계산할 때까지 기다려주세요.")
