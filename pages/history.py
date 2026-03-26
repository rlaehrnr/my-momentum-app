import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import calendar
from dateutil.relativedelta import relativedelta
import requests
import io

st.set_page_config(page_title="과거 모멘텀 조회", layout="wide")
st.title("🕰️ 과거 모멘텀 상위 30위 백테스트")
st.write("오픈소스 데이터를 활용하여, **그 당시 시총 상위 300개**를 정확하게 추출해 모멘텀을 계산합니다.")

col1, col2 = st.columns(2)
with col1:
    selected_year = st.selectbox("연도 선택", range(2015, 2027), index=9)
with col2:
    selected_month = st.selectbox("월 선택", range(1, 13), index=0)

# ⭐ 핵심 수정: .csv.gz 대신 새로운 포맷인 .parquet 파일로 요청!
@st.cache_data(ttl=86400)
def get_marcap_data(year):
    url = f"https://raw.githubusercontent.com/FinanceData/marcap/master/data/marcap-{year}.parquet"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    response = requests.get(url, headers=headers)
    response.raise_for_status() 
    
    # Parquet 전용 읽기 명령어로 변경
    df = pd.read_parquet(io.BytesIO(response.content))
    df['Code'] = df['Code'].astype(str).str.zfill(6)
    return df

@st.cache_data(ttl=86400)
def get_historical_momentum_ultimate(year, month):
    try:
        df_marcap = get_marcap_data(year)
    except Exception as e:
        st.error(f"{year}년 시가총액 데이터를 불러오지 못했습니다. 상세 이유: {e}")
        return pd.DataFrame()
        
    df_month = df_marcap[(df_marcap['Date'].dt.year == year) & (df_marcap['Date'].dt.month == month)]
    if df_month.empty:
        return pd.DataFrame()
        
    target_date = df_month['Date'].max() 
    df_target = df_month[df_month['Date'] == target_date]
    
    progress_text = f"{year}년 {month}월 당시의 KOSPI/KOSDAQ 대장주 300개 발굴 중..."
    my_bar = st.progress(0, text=progress_text)
    
    kospi_top = df_target[df_target['Market'] == 'KOSPI'].sort_values('Marcap', ascending=False).head(150)
    kosdaq_top = df_target[df_target['Market'] == 'KOSDAQ'].sort_values('Marcap', ascending=False).head(150)
    target_stocks = pd.concat([kospi_top, kosdaq_top])
    
    results = []
    total_stocks = len(target_stocks)
    
    base_date = target_date
    start_date = base_date - relativedelta(months=15)
    
    for i, (idx, row) in enumerate(target_stocks.iterrows()):
        code = row['Code']
        name = row['Name']
        market = row['Market']
        
        my_bar.progress((i + 1) / total_stocks, text=f"[{name}] 모멘텀 계산 중... ({i+1}/{total_stocks})")
        
        try:
            df = fdr.DataReader(code, start_date, base_date)
            if len(df) < 200: 
                continue
                
            current_price = df['Close'].iloc[-1]
            
            def get_past_price(months_ago):
                past_target = base_date - pd.offsets.MonthEnd(months_ago)
                past_df = df[df.index <= past_target]
                if past_df.empty: return current_price
                return past_df['Close'].iloc[-1]
            
            price_1m = get_past_price(1)
            price_3m = get_past_price(3)
            price_6m = get_past_price(6)
            price_12m = get_past_price(12)
            
            ret_1m = (current_price - price_1m) / price_1m * 100
            ret_3m = (current_price - price_3m) / price_3m * 100
            ret_6m = (current_price - price_6m) / price_6m * 100
            ret_12m = (current_price - price_12m) / price_12m * 100
            
            custom_score = (ret_1m * -0.2) + (ret_3m * 0.8) + (ret_6m * 0.5) + (ret_12m * 0.2)
            
            results.append({
                '시장': market,
                '종목명': name,
                '종목코드': code,
                '기준가': current_price,
                '1개월(%)': round(ret_1m, 2),
                '3개월(%)': round(ret_3m, 2),
                '6개월(%)': round(ret_6m, 2),
                '12개월(%)': round(ret_12m, 2),
                '모멘텀스코어': round(custom_score, 2)
            })
        except:
            pass
            
    my_bar.empty() 
    
    result_df = pd.DataFrame(results)
    if result_df.empty:
        return result_df
        
    result_df = result_df.sort_values('모멘텀스코어', ascending=False).head(30).reset_index(drop=True)
    result_df.index = range(1, len(result_df) + 1)
    
    result_df['종목코드'] = result_df['종목코드'].astype(str).str.zfill(6)
    def make_link(row):
        return f"https://m.stock.naver.com/fchart/domestic/stock/{row['종목코드']}#{row['종목명']}"
    result_df['종목명'] = result_df.apply(make_link, axis=1)
    
    return result_df

if st.button(f"🚀 {selected_year}년 {selected_month}월 기준 상위 30위 추출하기"):
    with st.spinner(f'타임머신 가동 중... {selected_year}년 {selected_month}월 당시 시총 대장주 300개를 바탕으로 발굴합니다.'):
        df_history = get_historical_momentum_ultimate(selected_year, selected_month)
        
    if df_history is not None and not df_history.empty:
        st.success(f"✅ {selected_year}년 {selected_month}월 말일 기준, 당시 300개 종목 중 모멘텀 1~30위 발굴 완료!")
        
        columns_to_show = ['시장', '종목명', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어']
        df_final = df_history[columns_to_show]
        
        st.dataframe(
            df_final,
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
        st.warning("데이터를 불러오는 중 문제가 발생했습니다.")
