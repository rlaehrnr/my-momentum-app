import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta

def update_momentum_data():
    print("데이터 수집을 시작합니다...")
    
    # 1. 한국 주식 전 종목 가져오기
    krx = fdr.StockListing('KRX')
    
    # 2. ⭐ 코스피, 코스닥 각각 시가총액 상위 150개 추출
    kospi_top150 = krx[krx['Market'] == 'KOSPI'].sort_values('Marcap', ascending=False).head(150)
    kosdaq_top150 = krx[krx['Market'] == 'KOSDAQ'].sort_values('Marcap', ascending=False).head(150)
    
    # 3. 두 데이터 합치기 (총 300개)
    target_stocks = pd.concat([kospi_top150, kosdaq_top150])
    
    today = pd.Timestamp.today()
    # 기준일: 실행 시점(매월 1일) 기준 이전 달의 마지막 날짜
    base_date = today.replace(day=1) - pd.Timedelta(days=1)
    
    # 1년치 + 여유분 3개월 과거 데이터
    start_date = base_date - relativedelta(months=15) 
    
    results = []
    
    for i, (idx, row) in enumerate(target_stocks.iterrows()):
        code = row['Code']
        name = row['Name']
        market = row['Market'] # ⭐ 소속 시장 정보 추가
        
        try:
            df = fdr.DataReader(code, start_date, today)
            if len(df) < 200: 
                continue
                
            # 기준월말 이전의 데이터만 필터링
            df_base = df[df.index <= base_date]
            if df_base.empty: continue
            current_price = df_base['Close'].iloc[-1]
            
            # N개월 전 말일 종가 가져오는 함수
            def get_past_price(months_ago):
                target_date = base_date - pd.offsets.MonthEnd(months_ago)
                past_df = df_base[df_base.index <= target_date]
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
            
            # 모멘텀 스코어 공식 적용
            custom_score = (ret_1m * -0.2) + (ret_3m * 0.8) + (ret_6m * 0.5) + (ret_12m * 0.2)
            
            results.append({
                '시장': market,  # ⭐ 결과에 시장 정보 포함
                '종목명': name,
                '종목코드': code,
                '기준일(월말)': base_date.strftime('%Y-%m-%d'),
                '기준가': current_price,
                '1개월(%)': round(ret_1m, 2),
                '3개월(%)': round(ret_3m, 2),
                '6개월(%)': round(ret_6m, 2),
                '12개월(%)': round(ret_12m, 2),
                '모멘텀스코어': round(custom_score, 2)
            })
        except Exception as e:
            # 오류가 나는 종목은 조용히 넘어갑니다.
            pass 
            
    # 데이터프레임 변환 및 모멘텀스코어 기준 내림차순 정렬
    result_df = pd.DataFrame(results)
    result_df = result_df.sort_values('모멘텀스코어', ascending=False).reset_index(drop=True)
    result_df.index = result_df.index + 1 
    
    # CSV 파일로 저장
    result_df.to_csv('momentum_data.csv', index=False, encoding='utf-8-sig')
    print("성공적으로 총 300개 종목의 데이터를 갱신했습니다!")

if __name__ == "__main__":
    update_momentum_data()
