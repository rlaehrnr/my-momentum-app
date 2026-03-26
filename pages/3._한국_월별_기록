import streamlit as st
import pandas as pd
import os
import glob

st.set_page_config(page_title="월별 기록 보관소", layout="wide")
st.title("📁 자동 저장된 월별 모멘텀 기록")
st.write("매월 1일 로봇이 자동으로 계산한 결과가 이곳에 영구적으로 보관되어, 0.1초 만에 바로 조회할 수 있습니다.")

archive_dir = 'archive'

# 폴더가 없거나 비어있는 경우
if not os.path.exists(archive_dir) or not os.listdir(archive_dir):
    st.info("아직 저장된 과거 기록이 없습니다. 다음 달 1일에 자동 업데이트가 실행되거나, 수동으로 로봇을 한 번 돌리면 첫 번째 기록이 생성됩니다!")
else:
    # archive 폴더 안의 모든 csv 파일 찾기
    csv_files = glob.glob(os.path.join(archive_dir, '*.csv'))
    
    # 파일 이름을 보기 좋게 변환 (예: archive/momentum_2026_03.csv -> 2026년 03월)
    options = []
    file_dict = {}
    for f in csv_files:
        basename = os.path.basename(f)
        name_part = basename.replace('momentum_', '').replace('.csv', '')
        if len(name_part) == 7: # YYYY_MM 형식인지 확인
            year, month = name_part.split('_')
            display_name = f"{year}년 {month}월"
            options.append(display_name)
            file_dict[display_name] = f
    
    # 최신 날짜가 맨 위에 오도록 정렬
    options.sort(reverse=True)
    
    if options:
        selected_month = st.selectbox("조회할 월을 선택하세요:", options)
        selected_file = file_dict[selected_month]
        
        # 선택한 월의 데이터 읽어오기
        df_momentum = pd.read_csv(selected_file, dtype={'종목코드': str})
        
        # 1페이지와 동일하게 표 세팅 (순위 1부터, 코드 6자리, 통합티커 생성)
        df_momentum.index = range(1, len(df_momentum) + 1)
        df_momentum['종목코드'] = df_momentum['종목코드'].str.zfill(6)
        
        if '시장' in df_momentum.columns and '종목코드' in df_momentum.columns:
            df_momentum['통합티커'] = df_momentum['시장'] + ":" + df_momentum['종목코드']
            
        def make_link(row):
            # 종목명이 없는 경우를 대비한 안전 장치
            name = row.get('종목명', row['종목코드']) 
            return f"https://m.stock.naver.com/fchart/domestic/stock/{row['종목코드']}#{name}"
            
        df_momentum['종목명'] = df_momentum.apply(make_link, axis=1)
        
        # 시장 필터
        market_filter = st.radio("조회할 시장을 선택하세요:", ('전체 보기', 'KOSPI만 보기', 'KOSDAQ만 보기'), horizontal=True)
        if market_filter == 'KOSPI만 보기':
            df_display = df_momentum[df_momentum['시장'] == 'KOSPI'].copy()
        elif market_filter == 'KOSDAQ만 보기':
            df_display = df_momentum[df_momentum['시장'] == 'KOSDAQ'].copy()
        else:
            df_display = df_momentum.copy()
            
        # 보여줄 컬럼 지정
        columns_to_show = ['통합티커', '종목코드', '시장', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어']
        # 혹시 예전 데이터에 없는 컬럼이 있을 경우를 대비해 필터링
        columns_to_show = [c for c in columns_to_show if c in df_display.columns]
        
        st.dataframe(
            df_display[columns_to_show],
            use_container_width=True,
            column_config={
                "종목명": st.column_config.LinkColumn(
                    "종목명", 
                    help="클릭하면 네이버 모바일 차트로 이동합니다.",
                    display_text=r"#(.+)" 
                )
            }
        )
    else:
        st.info("읽을 수 있는 기록 파일이 없습니다.")
