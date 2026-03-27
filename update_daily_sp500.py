import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import os

def update_daily_sp500():
    print("🇺🇸 S&P 500 데일리 데이터 업데이트 시작...")
    sp500 = fdr.StockListing('S&P500')
    os.makedirs('data', exist_ok=True)
    today = datetime.today()
    start_date = today - pd.DateOffset(months=15)
    results = []
    
    for _, row in sp500.iterrows():
        sym, name = row['Symbol'], row['Name']
        try:
            df = fdr.DataReader(sym, start_date, today)
            if len(df) < 200: continue
            curr_p, last_date = df['Close'].iloc[-1], df.index[-1]
            
            def get_ret(m):
                ref_dt = (last_date.replace(day=1) - pd.DateOffset(months=m-1)) - timedelta(days=1)
                past_df = df[df.index <= ref_dt]
                return round((curr_p - past_df['Close'].iloc[-1]) / past_df['Close'].iloc[-1] * 100, 1) if not past_df.empty else 0.0

            r1, r3, r6, r12 = get_ret(1), get_ret(3), get_ret(6), get_ret(12)
            score = round((r1 * -0.2) + (r3 * 0.8) + (r6 * 0.5) + (r12 * 0.2), 1)
            
            results.append({
                '기준일': last_date.strftime('%Y-%m-%d'),
                '시장': 'NYSE', # 비교 하이라이트를 위해 NYSE로 통일
                '종목명': name, '종목코드': sym, '기준가': round(curr_p, 2),
                '1개월(%)': r1, '3개월(%)': r3, '6개월(%)': r6, '12개월(%)': r12, '모멘텀스코어': score
            })
        except: pass

    res_df = pd.DataFrame(results).sort_values(by='모멘텀스코어', ascending=False).reset_index(drop=True)
    res_df.to_csv('data/momentum_data_daily_sp500.csv', index=False, encoding='utf-8-sig') # 파일명 다름!
    print("✅ 데일리 완료: data/momentum_data_daily_sp500.csv")

if __name__ == "__main__":
    update_daily_sp500()
