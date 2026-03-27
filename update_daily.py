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
    name_tag = "한국" if market_type == 'KR' else "미국"
    file_path = f'data/momentum_data_daily{"_us" if market_type=="US" else ""}.csv'
    
    # 한국은 전월 말일, 미국은 (시차 고려) 어제 기준
    today = datetime.today()
    ref_date = (today.replace(day=1) - timedelta(days=1))
    
    print(f"🕒 {name_tag} 데일리 데이터 수집 시작...")
    
    market_list = ['KOSPI', 'KOSDAQ'] if market_type == 'KR' else ['NYSE', 'NASDAQ']
    res = []

    for mkt_name in market_list:
        print(f"📡 {mkt_name} 데일리 데이터 수집 중...")
        target_stocks = get_top_stocks(mkt_name)
        
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
                
                res.append({
                    '기준일': today.strftime('%Y-%m-%d'),
                    '시장': mkt_name, # ⭐ 'US'가 아닌 'NYSE' 또는 'NASDAQ'으로 기록
                    '종목명': row['Name'], '종목코드': code, 
                    '기준가': curr_price, '1개월(%)': round(r1, 1), '3개월(%)': round(r3, 1), 
                    '6개월(%)': round(r6, 1), '12개월(%)': round(r12, 1), '모멘텀스코어': score
                })
            except: continue
    
    if res:
        pd.DataFrame(res).sort_values('모멘텀스코어', ascending=False).to_csv(file_path, index=False)
        print(f"✅ {name_tag} 데일리 갱신 완료!")

if __name__ == "__main__":
    run_daily('KR')
    run_daily('US')
