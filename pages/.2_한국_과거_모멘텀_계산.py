import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import calendar
from dateutil.relativedelta import relativedelta
import requests
import io

st.set_page_config(page_title="과거 모멘텀 조회", layout="wide")
st.title("🕰️ 과거 모멘텀 상위 30위 백테스트")

col1, col2 = st.columns(2)
with col1:
    selected_year = st.selectbox("연도 선택", range(2015, 2027), index=9)
with col2:
    selected_month = st.selectbox("월 선택", range(1, 13), index=0)

@st.cache_data(ttl=86400)
def get_marcap_data(year):
    url = f"https://raw.githubusercontent.com/FinanceData/marcap/master/data/marcap-{year}.parquet"
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    df = pd.read_parquet(io.BytesIO(response.content))
    df['Code'] = df['Code'].astype(str).str.zfill(6)
    return df

if st.button(f"🚀 {selected_year}년 {selected_month}월 기준 추출하기"):
    with st.spinner('당시 시총 300대 장주를 분석 중...'):
        try:
            df_marcap = get_marcap_data(selected_year)
            df_m = df_marcap[(df_marcap['Date'].dt.year == selected_year) & (df_marcap['Date'].dt.month == selected_month)]
            target_date = df_m['Date'].max()
            df_target = df_m[df_m['Date'] == target_date]
            
            k_top = df_target[df_target['Market'] == 'KOSPI'].sort_values('Marcap', ascending=False).head(150)
            q_top = df_target[df_target['Market'] == 'KOSDAQ'].sort_values('Marcap', ascending=False).head(150)
            stocks = pd.concat([k_top, q_top])
            
            results = []
            my_bar = st.progress(0)
            for i, (idx, row) in enumerate(stocks.iterrows()):
                code, name, market = row['Code'], row['Name'], row['Market']
                my_bar.progress((i+1)/300)
                try:
                    df = fdr.DataReader(code, target_date - relativedelta(months=15), target_date)
                    curr = df['Close'].iloc[-1]
                    def get_r(m):
                        p_t = target_date - pd.offsets.MonthEnd(m)
                        p_d = df[df.index <= p_t]
                        return (curr - p_d['Close'].iloc[-1]) / p_d['Close'].iloc[-1] * 100
                    r1, r3, r6, r12 = get_r(1), get_r(3), get_r(6), get_r(12)
                    score = (r1*-0.2) + (r3*0.8) + (r6*0.5) + (r12*0.2)
                    results.append({'시장': market, '종목명': name, '종목코드': code, '기준가': curr, '1개월(%)': round(r1,2), '3개월(%)': round(r3,2), '6개월(%)': round(r6,2), '12개월(%)': round(r12,2), '모멘텀스코어': round(score,2)})
                except: pass
            
            res_df = pd.DataFrame(results).sort_values('모멘텀스코어', ascending=False).head(30)
            res_df.index = range(1, len(res_df)+1)
            res_df['통합티커'] = res_df['시장'] + ":" + res_df['종목코드']
            
            def make_link(row): return f"https://m.stock.naver.com/fchart/domestic/stock/{row['종목코드']}#{row['종목명']}"
            res_df['종목명'] = res_df.apply(make_link, axis=1)

            show_details = st.checkbox("🔎 상세 정보 보기", value=False)
            cols = ['통합티커', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어']
            if show_details: cols = ['통합티커', '종목코드', '시장', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어']
            
            st.dataframe(res_df[cols], use_container_width=True, column_config={"종목명": st.column_config.LinkColumn("종목명", display_text=r"#(.+)")})
        except Exception as e:
            st.error(f"오류 발생: {e}")
