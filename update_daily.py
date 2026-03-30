import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import os

# 폴더 생성
if not os.path.exists('data'): os.makedirs('data')

def get_top_stocks(market, limit=150):
    try:
        df = fdr.StockListing(market)
        # S&P 500의 경우 Symbol 컬럼의 중복을 확실히 제거
        if market == 'S&P500': 
            df = df.drop_duplicates(subset=['Symbol'])
        
        cap_col = [c for c in df.columns if 'market' in c.lower() and 'cap' in c.lower()]
        if not cap_col: cap_col = [c for c in df.columns if 'mar' in c.lower() and 'cap' in c.lower()]
        
        return df.sort_values(cap_col[0], ascending=False).head(limit) if cap_col else df.head(limit)
    except: return pd.DataFrame()

def run_daily(market_type='KR'):
    # 시장별 설정
    if market_type == 'KR':
        name_tag, file_path, market_list, limit = "한국", 'data/momentum_data_daily.csv', ['KOSPI', 'KOSDAQ'], 150
        mkt_map = {} # 한국은 리스트 자체로 구분
    elif market_type == 'US':
        name_tag, file_path, market_list, limit = "미국(시총상위)", 'data/momentum_data_daily_us.csv', ['NYSE', 'NASDAQ'], 150
        mkt_map = {}
    elif market_type == 'SP500':
        name_tag, file_path, market_list, limit = "S&P 500", 'data/momentum_data_daily_sp500.csv', ['S&P500'], 505
        # S&P 500 상세 거래소 구분을 위한 매핑
        try:
            nyse = fdr.StockListing('NYSE')[['Symbol']]
            nasdaq = fdr.StockListing('NASDAQ')[['Symbol']]
            mkt_map = {s: 'NYSE' for s in nyse['Symbol']}
            mkt_map.update({s: 'NASDAQ' for s in nasdaq['Symbol']})
        except: mkt_map = {}

    today = datetime.today()
    print(f"🕒 {name_tag} 데일리 데이터 수집 시작...")
    res = []

    for mkt_name in market_list:
        target_stocks = get_top_stocks(mkt_name, limit)
        for _, row in target_stocks.iterrows():
            try:
                code = row['Code'] if 'Code' in row else row['Symbol']
                # 데이터 로드 (최근 16개월)
                df = fdr.DataReader(code.replace('.', '-'), today - pd.DateOffset(months=16), today)
                if df.empty: continue
                
                curr_price = df['Close'].iloc[-1]
                # ⭐ 전일 거래량 추출 (가장 최근 영업일)
                curr_volume = int(df['Volume'].iloc[-1]) if 'Volume' in df.columns else 0
                
                def get_ret(m):
                    ref = (today.replace(day=1) - pd.DateOffset(months=m-1)) - timedelta(days=1)
                    past = df[df.index <= ref]
                    return (curr_price - past['Close'].iloc[-1]) / past['Close'].iloc[-1] * 100 if not past.empty else 0.0
                
                r1, r3, r6, r12 = get_ret(1), get_ret(3), get_ret(6), get_ret(12)
                # 모멘텀 스코어 계산 공식
                score = round((r1*-0.2) + (r3*0.8) + (r6*0.5) + (r12*0.2), 1)
                
                # 시장 이름 결정
                display_mkt = mkt_map.get(code, 'NYSE') if market_type == 'SP500' else mkt_name

                res.append({
                    '기준일': today.strftime('%Y-%m-%d'), 
                    '시장': display_mkt,
                    '종목명': row['Name'], 
                    '종목코드': code, 
                    '기준가': round(curr_price, 2),
                    '전일거래량': curr_volume, # ⭐ 추가된 컬럼
                    '1개월(%)': round(r1, 1), 
                    '3개월(%)': round(r3, 1), 
                    '6개월(%)': round(r6, 1),
                    '12개월(%)': round(r12, 1), 
                    '모멘텀스코어': score
                })
            except: continue
            
    if res:
        # 결과 저장 (CSV)
        pd.DataFrame(res).sort_values('모멘텀스코어', ascending=False).to_csv(file_path, index=False, encoding='utf-8-sig')
        print(f"✅ {name_tag} 데일리 완료!")

if __name__ == "__main__":
    # 순차적으로 데이터 업데이트
    run_daily('KR')
    run_daily('US')
    run_daily('SP500')
