import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime
import os

# 1. 페이지 설정
st.set_page_config(page_title="한국시장 모멘텀 순위", layout="wide")

# CSS를 사용하여 표 사이의 간격을 강제로 줄임
st.markdown("""
    <style>
    [data-testid="stTable"] { margin-bottom: -20px; }
    hr { margin-top: 5px; margin-bottom: 5px; }
    .stDataFrame { margin-top: -10px; }
    </style>
    """, unsafe_allow_html=True)

# 지수 데이터 가져오기 (캐시 24시간)
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
                return round((curr - past_df['Close'].iloc[-1]) / past_df['Close'].iloc[-1] * 100, 1)
            res.append({'시장': name, '현재가': round(curr, 1), '1개월(%)': get_ret(1), '3개월(%)': get_ret(3), '6개월(%)': get_ret(6), '12개월(%)': get_ret(12)})
        except: pass
    return pd.DataFrame(res).set_index('시장')

file_path = 'momentum_data.csv'

if os.path.exists(file_path):
    df_raw = pd.read_csv(file_path, dtype={'종목코드': str})
    base_date = df_raw['기준일(월말)'].iloc[0]
    
    # 제목 및 지수 표 출력
    st.title(f"📊 한국시장 모멘텀 순위 (기준일: {base_date})")
    st.write("가중치: (1개월*-0.2) + (3개월*0.8) + (6개월*0.5) + (12개월*0.2)")

    idx_data = get_index_momentum()
    if not idx_data.empty:
        # 지수 표는 간단하게 st.table로 출력 (소수점 1자리 자동 적용됨)
        st.table(idx_data.reset_index())

    st.markdown("---") # 얇은 구분선

    # 데이터 전처리
    df = df_raw.copy()
    df['종목코드'] = df['종목코드'].str.zfill(6)
    df['통합티커'] = df['시장'] + ":" + df['종목코드']
    
    def make_link(row):
        return f"https://m.stock.naver.com/fchart/domestic/stock/{row['종목코드']}#{row['종목명']}"
    df['종목명'] = df.apply(make_link, axis=1)

    # 🎨 조건부 서식 함수 (지수보다 낮은 수익률은 옅은 파란색)
    def highlight_below_index(row):
        market = row['시장']
        styles = [''] * len(row)
        if market in idx_data.index:
            idx_row = idx_data.loc[market]
            cols_to_check = ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']
            for col in cols_to_check:
                col_idx = row.index.get_loc(col)
                if row[col] < idx_row[col]:
                    styles[col_idx] = 'background-color: #e6f3ff; color: #000000;'
        return styles

    # 화면에 보여줄 컬럼 순서
    display_order = ['통합티커', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어']
    
    # 스타일 적용 및 출력
    styled_df = df.style.apply(highlight_below_index, axis=1)

    st.dataframe(
        styled_df,
        use_container_width=True,
        height=560,
        column_order=display_order,
        column_config={
            "종목명": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"),
            "기준가": st.column_config.NumberColumn(format="%d"),
            "1개월(%)": st.column_config.NumberColumn(format="%.1f"),
            "3개월(%)": st.column_config.NumberColumn(format="%.1f"),
            "6개월(%)": st.column_config.NumberColumn(format="%.1f"),
            "12개월(%)": st.column_config.NumberColumn(format="%.1f"),
            "모멘텀스코어": st.column_config.NumberColumn(format="%.2f"),
        }
    )
else:
    st.warning("데이터 파일을 찾을 수 없습니다.")
