import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import os

def get_last_day_ret(df, curr_price, months):
    # 오늘 기준 m개월 전의 '말일' 가격 찾기
    today = datetime.today()
    ref_date = today - pd.DateOffset(months=months)
    ref_date = ref_date.replace(day=1) - timedelta(days=1)
    past = df[df.index <= ref_date]
    if past.empty: return 0.0
    return (curr_price - past['Close'].iloc[-1]) / past['Close'].iloc[-1] * 100

def run_daily_kr():
    print("🇰🇷 한국 데일리 수집 중...")
    df_ks = fdr.StockListing('KOSPI').sort_values('MarCap', ascending=False).head(150)
    df_kq = fdr.StockListing('KOSDAQ').sort_values('MarCap', ascending=False).head(150)
    df_ks['시장'], df_kq['시장'] = 'KOSPI', 'KOSDAQ'
    target = pd.concat([df_ks, df_kq])
    
    today = datetime.today()
    res = []
    for _, row in target.iterrows():
        try:
            df = fdr.DataReader(row['Code'], today - pd.DateOffset(months=15), today)
            curr = df['Close'].iloc[-1]
            r1, r3, r6, r12 = get_last_day_ret(df, curr, 1), get_last_day_ret(df, curr, 3), get_last_day_ret(df, curr, 6), get_last_day_ret(df, curr, 12)
            score = (r1*-0.2) + (r3*0.8) + (r6*0.5) + (r12*0.2)
            res.append({'시장': row['시장'], '종목명': row['Name'], '종목코드': row['Code'], '기준가': int(curr), '1개월(%)': round(r1, 1), '3개월(%)': round(r3, 1), '6개월(%)': round(r6, 1), '12개월(%)': round(r12, 1), '모멘텀스코어': round(score, 1)})
        except: continue
    pd.DataFrame(res).sort_values('모멘텀스코어', ascending=False).to_csv('momentum_data_daily.csv', index=False)

def run_daily_us():
    print("🇺🇸 미국 데일리 수집 중...")
    df_ny = fdr.StockListing('NYSE').head(150) # 실제론 시총순 정렬 로직이 필요하나 간단히 구성
    df_nd = fdr.StockListing('NASDAQ').head(150)
    df_ny['시장'], df_nd['시장'] = 'NYSE', 'NASDAQ'
    target = pd.concat([df_ny, df_nd])
    
    today = datetime.today()
    res = []
    for _, row in target.iterrows():
        symbol = str(row['Symbol']).replace('.', '-')
        try:
            df = fdr.DataReader(symbol, today - pd.DateOffset(months=15), today)
            curr = df['Close'].iloc[-1]
            r1, r3, r6, r12 = get_last_day_ret(df, curr, 1), get_last_day_ret(df, curr, 3), get_last_day_ret(df, curr, 6), get_last_day_ret(df, curr, 12)
            score = (r1*-0.2) + (r3*0.8) + (r6*0.5) + (r12*0.2)
            res.append({'시장': row['시장'], '종목명': row['Name'], '종목코드': row['Symbol'], '기준가': round(curr, 2), '1개월(%)': round(r1, 1), '3개월(%)': round(r3, 1), '6개월(%)': round(r6, 1), '12개월(%)': round(r12, 1), '모멘텀스코어': round(score, 1)})
        except: continue
    pd.DataFrame(res).sort_values('모멘텀스코어', ascending=False).to_csv('momentum_data_daily_us.csv', index=False)

if __name__ == "__main__":
    run_daily_kr()
    run_daily_us()
    print("✅ 한/미 데일리 업데이트 완료!")
