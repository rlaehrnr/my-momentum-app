import streamlit as st
import FinanceDataReader as fdr
from pykrx import stock  
import pandas as pd
import calendar
from dateutil.relativedelta import relativedelta

st.set_page_config(page_title="과거 모멘텀 조회", layout="wide")
st.title("🕰️ 과거 모멘텀 상위 30위 백테스트")
st.write("선택한 과거 시점 당시에 **시가총액 상위 150위**였던 KOSPI/KOSDAQ 종목(총 300개)을 정확히 추려내어, 그 당시의 모멘텀 순위를 계산합니다.")

col1, col2 = st.columns(2)
with col1:
    selected_year = st.selectbox("연도 선택", range(2015, 2027), index=9)
with col2:
    selected_month = st.selectbox("월 선택", range(1, 13), index=0)

@st.cache_data(ttl=86400)
def get_historical_momentum_top300(year, month):
    # 1. 기준일 계산
    last_day = calendar.monthrange(year, month)[1]
    base_date = pd.Timestamp(year=year, month=month, day=last_day)
    start_date = base_date - relativedelta(months=15)
    
    # ⭐ 2. 완벽한 영업일 찾기 꼼수 (삼성전자 주가 달력 활용)
    # pykrx의 잦은 에러를 피하기 위해, 우량주인 삼성전자의 마지막 거래일을 그 달의 영업일 말일로 씁니다.
    start_str = f"{year}-{month:02d}-01"
    end_str = f"{year}-{month:02d}-{last_day:02d}"
    
    try:
        df_cal = fdr.DataReader('005930', start_str, end_str)
        if df_cal.empty:
            return pd.DataFrame()
        # 삼성전자 데이터의 가장 마지막 날짜를 추출 (예: 20240131)
        target_date_str = df_cal.index[-1].strftime("%Y%m%d")
    except:
        st.error("영업일 달력을 불러오지 못했습니다.")
        return pd.DataFrame()
    
    progress_text = f"{year}년 {month}월 당시의 시가총액 상위 종목을 발굴하는 중..."
    my_bar = st.progress(0, text=progress_text)
    
    # 3. pykrx로 과거 시가총액 순위 가져오기
    try:
        kospi_cap = stock.get_market_cap(target_date_str, market="KOSPI")
        kosdaq_cap = stock.get_market_cap(target_date_str, market="KOSDAQ")
        
        kospi_top = kospi_cap.sort_values("시가총액", ascending=False).head(150)
        kosdaq_top = kosdaq_cap.sort_values("시가총액", ascending=False).head(150)
        
        kospi_codes = kospi_top.index.tolist()
        kosdaq_codes = kosdaq_top.index.tolist()
    except Exception as e:
        my_bar.empty()
        st.error(f"해당 시점의 시가총액 데이터를 불러오지 못했습니다. ({e})")
        return pd.DataFrame()
        
    results = []
    total_stocks = 300
    
    # 4. 발굴해 낸 300개 종목 리스트 합치기
    target_stocks = []
    for code in kospi_codes:
        target_stocks.append({'Code': code, 'Market': 'KOSPI'})
    for code in kosdaq_codes:
        target_stocks.append({'Code': code, 'Market': 'KOSDAQ'})
        
    # 5. 300개 종목에 대해서만 속전속결 모멘텀 계산
    for i, row in enumerate(target_stocks):
        code = row['Code']
        market = row['Market']
        
        try:
            name = stock.get_market_ticker_name(code) 
        except:
            name = code # 종목명을 못 가져오면 코드라도 표시
            
        my_bar.progress((i + 1) / total_stocks, text=f"[{name}] 모멘텀 계산 중... ({i+1}/{total_stocks})")
        
        try:
            df = fdr.DataReader(code, start_date, base_date)
            if len(df) < 200: 
                continue
                
            current_price = df['Close'].iloc[-1]
            
            def get_past_price(months_ago):
                target_date = base_date - pd.offsets.MonthEnd(months_ago)
                past_df = df[df.index <= target_date]
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
        
    # 6. 상위 30개 추출
    result_df = result_df.sort_values('모멘텀스코어', ascending=False).head(30).reset_index(drop=True)
    result_df.index = range(1, len(result_df) + 1)
    
    # 7. 네이버 차트 링크 생성 
    def make_link(row):
        return f"https://m.stock.naver.com/fchart/domestic/stock/{row['종목코드']}#{row['종목명']}"
    result_df['종목명'] = result_df.apply(make_link, axis=1)
    
    return result_df

if st.button(f"🚀 {selected_year}년 {selected_month}월 기준 상위 30위 추출하기"):
    with st.spinner(f'타임머신 가동 중... {selected_year}년 {selected_month}월 당시 시총 상위 300개 종목을 추출하여 계산합니다.'):
        df_history = get_historical_momentum_top300(selected_year, selected_month)
        
    if df_history is not None and not df_history.empty:
        st.success(f"✅ {selected_year}년 {selected_month}월 말일 기준, 당시 시총 상위 300개 중 모멘텀 1~30위 발굴 완료!")
        
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
        st.error("데이터를 불러오지 못했습니다. 너무 먼 과거이거나 주말/휴장일 관련 오류일 수 있습니다.")
