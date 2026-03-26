import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta

# 웹 페이지 기본 설정
st.set_page_config(page_title="모멘텀 투자 도우미", layout="wide")
st.title("📈 코스피/코스닥 상위 150 모멘텀 순위")
st.write("1, 3, 6, 12개월 수익률을 계산하여 평균 모멘텀 순위로 정렬합니다.")

# 데이터 불러오기 함수 (캐싱을 적용해 한 번 불러오면 하루 동안은 빠르게 뜸)
@st.cache_data(ttl=86400)
def load_data():
    progress_text = "데이터를 수집하고 계산하는 중입니다. (약 1~2분 소요)"
    progress_bar = st.progress(0, text=progress_text)
    
    # 1. 한국 주식 전 종목 가져오기
    krx = fdr.StockListing('KRX')
    krx = krx[krx['Market'].isin(['KOSPI', 'KOSDAQ'])] # 코스피, 코스닥만 필터링
    
    # 2. 시가총액(Marcap) 기준 상위 150개 종목 추출
    top150 = krx.sort_values('Marcap', ascending=False).head(150)
    
    today = datetime.today()
    start_date = today - relativedelta(months=13) # 1년치 과거 데이터 넉넉하게
    
    results = []
    total_stocks = len(top150)
    
    for i, (idx, row) in enumerate(top150.iterrows()):
        code = row['Code']
        name = row['Name']
        
        try:
            # 개별 종목의 1년치 일봉 데이터 가져오기
            df = fdr.DataReader(code, start_date, today)
            if len(df) < 200: # 상장된지 1년이 안 된 종목은 제외
                continue
            
            current_price = df['Close'].iloc[-1]
            
            # N개월 전 종가 가져오는 함수
            def get_past_price(months_ago):
                target_date = today - relativedelta(months=months_ago)
                # 타겟 날짜 이전의 데이터 중 가장 마지막 날(영업일)의 종가
                past_df = df[df.index <= target_date]
                if past_df.empty: return current_price
                return past_df['Close'].iloc[-1]
            
            price_1m = get_past_price(1)
            price_3m = get_past_price(3)
            price_6m = get_past_price(6)
            price_12m = get_past_price(12)
            
            # 수익률 계산 (%)
            ret_1m = (current_price - price_1m) / price_1m * 100
            ret_3m = (current_price - price_3m) / price_3m * 100
            ret_6m = (current_price - price_6m) / price_6m * 100
            ret_12m = (current_price - price_12m) / price_12m * 100
            
            # 평균 모멘텀 스코어 (단순 평균)
            avg_momentum = (ret_1m + ret_3m + ret_6m + ret_12m) / 4
            
            results.append({
                '종목명': name,
                '종목코드': code,
                '현재가': current_price,
                '1개월(%)': round(ret_1m, 2),
                '3개월(%)': round(ret_3m, 2),
                '6개월(%)': round(ret_6m, 2),
                '12개월(%)': round(ret_12m, 2),
                '평균모멘텀(%)': round(avg_momentum, 2)
            })
        except:
            pass # 데이터 오류가 나는 종목은 무시
        
        # 진행률 표시
        progress_bar.progress((i + 1) / total_stocks, text=f"{name} 처리 중... ({i+1}/{total_stocks})")
        
    progress_bar.empty() # 작업 끝나면 진행바 숨기기
    
    # 데이터프레임으로 변환 후 평균모멘텀 기준 내림차순 정렬
    result_df = pd.DataFrame(results)
    result_df = result_df.sort_values('평균모멘텀(%)', ascending=False).reset_index(drop=True)
    result_df.index = result_df.index + 1 # 순위를 1번부터 표시
    
    return result_df

# 화면 버튼 및 결과 출력
if st.button('🚀 최신 모멘텀 순위 계산하기'):
    with st.spinner('상위 150개 종목의 과거 데이터를 수집하고 있습니다. 잠시만 기다려주세요...'):
        df_momentum = load_data()
    st.success("계산 완료! 아래 표에서 순위를 확인하세요.")
    # 보기 좋게 표 그리기 (엑셀처럼 다운로드 버튼도 자동 생성됨)
    st.dataframe(df_momentum, use_container_width=True)
else:
    st.info("버튼을 눌러 계산을 시작하세요. (실시간 데이터를 가져오므로 최초 실행 시 약 1분 정도 소요됩니다.)")
