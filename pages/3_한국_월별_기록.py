import streamlit as st
import pandas as pd
import os
import glob

st.set_page_config(page_title="월별 기록 보관소", layout="wide")
st.title("📁 자동 저장된 월별 모멘텀 기록")

archive_dir = 'archive'

if not os.path.exists(archive_dir) or not os.listdir(archive_dir):
    st.info("아직 저장된 기록이 없습니다.")
else:
    csv_files = glob.glob(os.path.join(archive_dir, '*.csv'))
    options = sorted([os.path.basename(f).replace('momentum_', '').replace('.csv', '').replace('_', '년 ') + '월' for f in csv_files], reverse=True)
    
    selected_month = st.selectbox("조회할 월 선택:", options)
    file_name = f"momentum_{selected_month.replace('년 ', '_').replace('월', '')}.csv"
    
    df = pd.read_csv(os.path.join(archive_dir, file_name), dtype={'종목코드': str})
    df.index = range(1, len(df)+1)
    df['종목코드'] = df['종목코드'].str.zfill(6)
    df['통합티커'] = df['시장'] + ":" + df['종목코드']
    
    def make_link(row): return f"https://m.stock.naver.com/fchart/domestic/stock/{row['종목코드']}#{row['종목명']}"
    df['종목명'] = df.apply(make_link, axis=1)
    
    show_details = st.checkbox("🔎 상세 정보 보기", value=False)
    # 기록 보관소는 '다음달수익률(%)'이 핵심!
    cols = ['통합티커', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어', '다음달수익률(%)']
    
    if show_details:
        cols = ['통합티커', '종목코드', '시장', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어', '다음달수익률(%)']
    
    # 데이터에 있는 컬럼만 필터링
    cols = [c for c in cols if c in df.columns]
    
    st.dataframe(df[cols], use_container_width=True, column_config={"종목명": st.column_config.LinkColumn("종목명", display_text=r"#(.+)")})
