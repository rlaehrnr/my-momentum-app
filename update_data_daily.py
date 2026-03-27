import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import os

def get_daily_momentum_kr():
    print("🚀 한국 시장 데일리 모멘텀 계산 시작...")
    
    # 1. 대상 선정 (시총 상위 각 150개)
    df_ks = fdr.StockListing('KOSPI').sort_values('MarCap', ascending=False).head(150)
    df_kq = fdr.StockListing('KOSDAQ').sort_values('MarCap', ascending=False).head(150)
    df_ks['시장'] = 'KOSPI'; df_kq['시장'] = 'KOSDAQ'
    target_stocks = pd.concat([df_ks, df_kq])
    
    today = datetime.today()
    results = []
    
    for i, (idx, row) in enumerate(target_stocks.iterrows()):
        symbol, name = row['Code'], row['Name']
        try:
            # 15개월치 데이터 확보
            df = fdr.DataReader(symbol, today - pd.DateOffset(months=15), today)
            if df.empty: continue
            
            curr_price = df['Close'].iloc[-1]
            
            def get_ret(m):
                # 오늘 기준 m개월 전의 '말일' 가격 찾기
                ref_date = today - pd.DateOffset(months=m)
                ref_date = ref_date.replace(day=1) - timedelta(days=1)
                past = df[df.index <= ref_date]
                if past.empty: return 0.0
                return (curr_price - past['Close'].iloc[-1]) / past['Close'].iloc[-1] * 100
            
            r1, r3, r6, r12 = get_ret(1), get_ret(3), get_ret(6), get_ret(12)
            score = (r1*-0.2) + (r3*0.8) + (r6*0.5) + (r12*0.2)
            
            results.append({
                '기준일': today.strftime('%Y-%m-%d'),
                '시장': row['시장'], '종목명': name, '종목코드': symbol, 
                '기준가': int(curr_price),
                '1개월(%)': round(r1, 1), '3개월(%)': round(r3, 1), 
                '6개월(%)': round(r6, 1), '12개월(%)': round(r12, 1),
                '모멘텀스코어': round(score, 2)
            })
        except: continue
        
    if results:
        final_df = pd.DataFrame(results).sort_values('모멘텀스코어', ascending=False)
        final_df.to_csv('momentum_data_daily.csv', index=False)
        print(f"✅ 데일리 데이터 업데이트 완료! (기준일: {today.strftime('%Y-%m-%d')})")

if __name__ == "__main__":
    get_daily_momentum_kr()
