import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import calendar
from dateutil.relativedelta import relativedelta

st.set_page_config(page_title="과거 모멘텀 조회", layout="wide")
st.title("🕰️ 과거 모멘텀 상위 30위 백테스트")
st.write("클라우드 서버 차단(IP 밴) 문제를 완벽히 해결한 버전입니다! 오픈소스 데이터를 활용하여, **그 당시 시총 상위 300개**를 정확하게 추출해 모멘텀을 계산합니다.")

col1, col2 = st.columns(2)
with col1:
    selected_year = st.selectbox("연도 선택", range(2015, 2027), index=9)
with col2:
    selected_month = st.selectbox("월 선택", range(1, 13), index=0)

# ⭐ 1. 새로운 꼼수: GitHub 오픈소스에서 과거 시가총액 CSV 파일 직접 읽어오기 (차단 절대 없음)
@st.cache_data(ttl=86400)
def get_marcap_data(year):
    url = f"https://raw.githubusercontent.com/FinanceData/marcap/master/data/marcap-{year}.csv.gz"
    # 날짜(Date) 컬럼을 날짜 형식으로 읽어옵니다.
    df = pd.read_csv(url, dtype={'Code': str}, parse_dates=['Date'])
    return df

@st.cache_data(ttl=86400)
def get_historical_momentum_ultimate(year, month):
    try:
        df_marcap = get_marcap_data(year)
    except:
        st.error(f"{year}년의 시가총액 데이터를 오픈소스에서 불러오지 못했습니다.")
        return pd.DataFrame()
        
    # 2. 선택한 연/월의 데이터만 뽑아서 '그 달의 마지막 영업일' 자동으로 찾기
    df_month = df_marcap[(df_marcap['Date'].dt.year == year) & (df_marcap['Date'].dt.month == month)]
    if df_month.empty:
        return pd.DataFrame()
        
    target_date = df_month['Date'].max() # 휴장일 제외하고 그 달의 진짜 마지막 거래일을 알아서 찾아냅니다!
    df_target = df_month[df_month['Date'] == target_date]
    
    progress_text = f"{year}년 {month}월 당시의 KOSPI/KOSDAQ 대장주 300개 발굴 중..."
    my_bar = st.progress(0, text=progress_text)
    
    # ⭐ 3. 타임머신 가동: '그 당시' 시가총액 상위 150개씩 정확히 추출!
    kospi_top = df_target[df_target['Market'] == 'KOSPI'].sort_values('Marcap', ascending=False).head(150)
    kosdaq_top = df_target[df_target['Market'] == 'KOSDAQ'].sort_values('Marcap', ascending=False).head(150)
    target_stocks = pd.concat([kospi_top, kosdaq_top])
    
    results = []
    total_stocks = len(target_stocks)
    
    # 모멘텀 계산용 날짜 세팅
    base_date = target_date
    start_date = base_date - relativedelta(months=15)
    
    # 4. 발굴해 낸 300개 종목에 대해서만 속전속결 모멘텀 계산
    for i, (idx, row) in enumerate(target_stocks.iterrows()):
        code = row['Code']
        name = row['Name']
        market = row['Market']
        
        my_bar.progress((i + 1) / total_stocks, text=f"[{name}] 모멘텀 계산 중... ({i+1}/{total_stocks})")
        
        try:
            # 개별 주가를 가져오는 fdr은 네이버를 쓰므로 IP 차단이 거의 없습니다.
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
        
    # 5. 상위 30개 추출 및 순위 매기기
    result_df = result_df.sort_values('모멘텀스코어', ascending=False).head(30).reset_index(drop=True)
    result_df.index = range(1, len(result_df) + 1)
    
    # 6. 네이버 차트 링크 생성 
    result_df['종목코드'] = result_df['종목코드'].astype(str).str.zfill(6)
    def make_link(row):
        return f"https://m.stock.naver.com/fchart/domestic/stock/{row['종목코드']}#{row['종목명']}"
    result_df['종목명'] = result_df.apply(make_link, axis=1)
    
    return result_df

# 화면 버튼 및 실행
if st.button(f"🚀 {selected_year}년 {selected_month}월 기준 상위 30위 추출하기"):
    with st.spinner(f'타임머신 가동 중... {selected_year}년 {selected_month}월 당시 시총 대장주 300개를 바탕
