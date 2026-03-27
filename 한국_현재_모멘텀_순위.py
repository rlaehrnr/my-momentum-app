import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime
import os

# 1. 페이지 설정 및 제목
st.set_page_config(page_title="한국시장 모멘텀 순위", layout="wide")

# 지수 모멘텀 계산 함수 (캐시 적용: 24시간)
@st.cache_data(ttl=86400)
def get_index_momentum():
    indices = {'KOSPI': 'KS11', 'KOSDAQ': 'KQ11'}
    today = datetime.today()
    start_date = today - pd.DateOffset(months=15)
    
    res = []
    for name, code in indices.items():
        try:
            df = fdr.DataReader(code, start_date, today)
            curr = df['Close'].iloc[-1]
            
            def get_ret(m):
                target = df.index[-1] - pd.DateOffset(months=m)
                past_df = df[df.index <= target]
                if past_df.empty: return 0.0
                past_price = past_df['Close'].iloc[-1]
                return round((curr - past_price) / past_price * 100, 2)
            
            res.append({
                '시장': name,
                '현재가': round(curr, 2),
                '1개월(%)': get_ret(1),
                '3개월(%)': get_ret(3),
                '6개월(%)': get_ret(6),
                '12개월(%)': get_ret(12)
            })
        except:
            pass
    return pd.DataFrame(res)

file_path = 'momentum_data.csv'

if os.path.exists(file_path):
    df_raw = pd.read_csv(file_path, dtype={'종목코드': str})
    base_date = df_raw['기준일(월말)'].iloc[0]
    
    # 2. 제목 및 가중치 설명 (여백 최소화)
    st.title(f"📊 한국시장 모멘텀 순위 (기준일: {base_date})")
    st.write("가중치: (1개월*-0.2) + (3개월*0.8) + (6개월*0.5) + (12개월*0.2)")

    # 3. 상단 지수 표 (제목 없이 바로 노출)
    idx_df = get_index_momentum()
    if not idx_df.empty:
        st.table(idx_df)
    
    # 4. 얇은 구분선 (두 표를 연결)
    st.markdown("---")
    
    # 5. 개별 종목 데이터 전처리
    df = df_raw.copy()
    df.index = range(1, len(df) + 1)
    df['종목코드'] = df['종목코드'].str.zfill(6)
    df['통합티커'] = df['시장'] + ":" + df['종목코드']
    
    def make_link(row):
        return f"https://m.stock.naver.com/fchart/domestic/stock/{row['종목코드']}#{row['종목명']}"
    df['종목명'] = df.apply(make_link, axis=1)

    # 6. 개별 종목 표 출력 (15행 높이 고정)
    display_order = ['통합티커', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어']

    st.dataframe(
        df,
        use_container_width=True,
        height=560, # 15개 행에 최적화된 높이
        column_order=display_order,
        column_config={
            "종목명": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"),
            "기준가": st.column_config.NumberColumn(format="%d"),
            "모멘텀스코어": st.column_config.NumberColumn(format="%.2f"),
        }
    )

else:
    st.title("📊 한국시장 모멘텀 순위")
    st.warning("데이터 파일을 찾을 수 없습니다.")
