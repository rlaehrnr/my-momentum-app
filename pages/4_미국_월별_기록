import streamlit as st
import pandas as pd
import os
import glob

# 1. 페이지 설정
st.set_page_config(page_title="미국 월별 기록 보관소", layout="wide")

# CSS: 초밀착 레이아웃 (다른 페이지들과 통일)
st.markdown("""
    <style>
    .block-container { padding-top: 2.5rem !important; padding-bottom: 0rem !important; }
    h1 { margin-top: 0px !important; margin-bottom: 10px !important; font-size: 2rem !important; }
    [data-testid="stTable"] { margin-bottom: -25px; }
    hr { margin-top: 5px; margin-bottom: 5px; }
    .stDataFrame { margin-top: -10px; }
    </style>
    """, unsafe_allow_html=True)

st.title("📁 미국 월별 모멘텀 기록 보관소")

# 미국 데이터가 저장되는 폴더
archive_dir = 'archive_us'

# 보관소 폴더 확인
if not os.path.exists(archive_dir) or not os.listdir(archive_dir):
    st.info("아직 저장된 미국 월별 기록이 없습니다. 로봇이 한 달 뒤 첫 미국 성적표를 채점할 때까지 기다려주세요.")
else:
    # 저장된 파일 목록 가져오기 (momentum_us_YYYY_MM.csv 형식)
    csv_files = glob.glob(os.path.join(archive_dir, '*.csv'))
    # 파일명에서 날짜 추출하여 정렬
    options = sorted([os.path.basename(f).replace('momentum_us_', '').replace('.csv', '').replace('_', '년 ') + '월' for f in csv_files], reverse=True)
    
    # 상단 월 선택 바
    selected_month = st.selectbox("📅 조회할 월을 선택하세요 (미국):", options)
    file_month = selected_month.replace('년 ', '_').replace('월', '')
    file_path = os.path.join(archive_dir, f'momentum_us_{file_month}.csv')
    
    if os.path.exists(file_path):
        # 데이터 불러오기
        df = pd.read_csv(file_path)
        df.index = range(1, len(df) + 1)
        df['통합티커'] = df['시장'] + ":" + df['종목코드']
        
        # 야후 파이낸스 링크 생성
        def make_link(row):
            return f"https://finance.yahoo.com/quote/{row['종목코드']}#{row['종목명']}"
        df['종목명'] = df.apply(make_link, axis=1)

        # 엑셀식 숨김 컬럼 및 배치 (성적표인 '다음달수익률' 전진 배치)
        display_order = ['통합티커', '종목명', '다음달수익률(%)', '기준가', '모멘텀스코어', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']

        # 데이터프레임 출력 (15행 높이 고정)
        st.dataframe(
            df,
            use_container_width=True,
            height=560,
            column_order=display_order,
            column_config={
                "종목명": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"),
                "다음달수익률(%)": st.column_config.NumberColumn("다음달성적(%)", format="%.1f", help="미국 대장주 추출 후 한 달간의 실제 수익률입니다."),
                "기준가": st.column_config.NumberColumn("기준가($)", format="%.2f"),
                "1개월(%)": st.column_config.NumberColumn(format="%.1f"),
                "3개월(%)": st.column_config.NumberColumn(format="%.1f"),
                "6개월(%)": st.column_config.NumberColumn(format="%.1f"),
                "12개월(%)": st.column_config.NumberColumn(format="%.1f"),
                "모멘텀스코어": st.column_config.NumberColumn(format="%.2f"),
            }
        )
        
        st.write(f"💡 **미국 시장 {selected_month}** 당시에 뽑혔던 상위 300개 종목의 한 달 뒤 성적표입니다.")
