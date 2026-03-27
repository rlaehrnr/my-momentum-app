import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import os
import time

# 폴더 생성
if not os.path.exists('data'): os.makedirs('data')

def get_top_stocks(market, limit=150):
    try:
        df = fdr.StockListing(market)
        cap_col = [c for c in df.columns if 'market' in c.lower() and 'cap' in c.lower()]
        if not cap_col: cap_col = [c for c in df.columns if 'mar' in c.lower() and 'cap' in c.lower()]
        return df.sort_values(cap_col[0], ascending=False).head(limit) if cap_col else df.head(limit)
    except: return pd.DataFrame()

def run_daily(market_type='KR'):
    # 1. 마켓 타입에 따른 변수 자동 할당
    if market_type == 'KR':
        name_tag, file_path, market_list, limit = "한국", 'data/momentum_data_daily.csv', ['KOSPI', 'KOSDAQ'], 150
    elif market_type == 'US':
        name_tag, file_path, market_list, limit = "미국(시총상위)", 'data/momentum_data_daily_us.csv', ['NYSE', 'NASDAQ'], 150
    elif market_type == 'SP500':
        name_tag, file_path, market_list, limit = "S&P 500", 'data/momentum_data_daily_sp500.csv', ['S&P500'], 505 # S&P 500 전체

    # 한국은 전월 말일, 미국은 (시차 고려) 어제 기준
    today = datetime.today()
    ref_date = (today.replace(day=1) - timedelta(days=1))
    
    print(f"\n🕒 {name_tag} 데일리 데이터 수집 시작...")
    res = []

    for mkt_name in market_list:
        print(f"📡 {mkt_name} 데일리 데이터 수집 중...")
        target_stocks = get_top_stocks(mkt_name, limit)
        
        for i, (_, row) in enumerate(target_stocks.iterrows()):
            try:
                code = row['Code'] if 'Code' in row else row['Symbol']
                # 최근 16개월치 데이터
                df = fdr.DataReader(code.replace('.', '-'), today - pd.DateOffset(months=16), today)
                if df.empty: continue
                
                curr_price = df['Close'].iloc[-1] # 오늘(어제) 가격
                
                def get_ret(m):
                    # m개월 전 말일 대비 수익률
                    ref = (today.replace(day=1) - pd.DateOffset(months=m-1)) - timedelta(days=1)
                    past = df[df.index <= ref]
                    return (curr_price - past['Close'].iloc[-1]) / past['Close'].iloc[-1] * 100 if not past.empty else 0.0
                
                r1, r3, r6, r12 = get_ret(1), get_ret(3), get_ret(6), get_ret(12)
                score = round((r1*-0.2) + (r3*0.8) + (r6*0.5) + (r12*0.2), 1)
                
                # ⭐ 중요: S&P500 종목도 스트림릿에서 지수 비교 색상칠이 적용되도록 'NYSE'로 통일해서 저장
                display_mkt = 'NYSE' if market_type == 'SP500' else mkt_name

                res.append({
                    '기준일': today.strftime('%Y-%m-%d'),
                    '시장': display_mkt,
                    '종목명': row['Name'], '종목코드': code, 
                    '기준가': round(curr_price, 2), '1개월(%)': round(r1, 1), '3개월(%)': round(r3, 1), 
                    '6개월(%)': round(r6, 1), '12개월(%)': round(r12, 1), '모멘텀스코어': score
                })
            except: continue
            
    if res:
        pd.DataFrame(res).sort_values('모멘텀스코어', ascending=False).to_csv(file_path, index=False, encoding='utf-8-sig')
        print(f"✅ {name_tag} 데일리 갱신 완료! ({file_path})")

if __name__ == "__main__":
    run_daily('KR')
    run_daily('US')
    run_daily('SP500')
