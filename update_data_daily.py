import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import os

def get_top_stocks(market_code, limit=150):
    try:
        df = fdr.StockListing(market_code)
        cap_cols = [c for c in df.columns if 'market' in c.lower() and 'cap' in c.lower()]
        if not cap_cols: cap_cols = [c for c in df.columns if 'mar' in c.lower() and 'cap' in c.lower()]
        return df.sort_values(cap_cols[0], ascending=False).head(limit) if cap_cols else df.head(limit)
    except: return pd.DataFrame()

# ⭐ 날짜 로직 수정: m개월 전의 '정확한' 월말일을 계산
def get_ref_day_ret(df, curr_price, m):
    today = datetime.today()
    # m=1이면 이번달 1일에서 하루를 빼서 '지난달 말일'을 만듦
    first_day_of_target_month = today.replace(day=1) - pd.DateOffset(months=m-1)
    ref_date = first_day_of_target_month - timedelta(days=1)
    
    past = df[df.index <= ref_date]
    if past.empty: return 0.0
    return (curr_price - past['Close'].iloc[-1]) / past['Close'].iloc[-1] * 100

def run_daily_kr():
    print("🇰🇷 한국 데일리 수집 중...")
    target = pd.concat([get_top_stocks('KOSPI'), get_top_stocks('KOSDAQ')])
    today = datetime.today()
    res = []
    for _, row in target.iterrows():
        try:
            code, name = (row['Code'] if 'Code' in row else row['Symbol']), row['Name']
            df = fdr.DataReader(code, today - pd.DateOffset(months=16), today)
            curr = df['Close'].iloc[-1]
            # 수정된 날짜 함수 사용
            r1, r3, r6, r12 = get_ref_day_ret(df, curr, 1), get_ref_day_ret(df, curr, 3), get_ref_day_ret(df, curr, 6), get_ref_day_ret(df, curr, 12)
            score = (r1*-0.2) + (r3*0.8) + (r6*0.5) + (r12*0.2)
            res.append({'기준일': today.strftime('%Y-%m-%d'), '시장': 'KOSPI' if len(code)==6 and code[0]!='U' else 'KOSDAQ', '종목명': name, '종목코드': code, '기준가': int(curr), '1개월(%)': round(r1, 1), '3개월(%)': round(r3, 1), '6개월(%)': round(r6, 1), '12개월(%)': round(r12, 1), '모멘텀스코어': round(score, 1)})
        except: continue
    if res: pd.DataFrame(res).sort_values('모멘텀스코어', ascending=False).to_csv('momentum_data_daily.csv', index=False)

def run_daily_us():
    print("🇺🇸 미국 데일리 수집 중...")
    target = pd.concat([get_top_stocks('NYSE'), get_top_stocks('NASDAQ')])
    today = datetime.today()
    res = []
    for _, row in target.iterrows():
        try:
            symbol, name = row['Symbol'], row['Name']
            df = fdr.DataReader(symbol.replace('.', '-'), today - pd.DateOffset(months=16), today)
            curr = df['Close'].iloc[-1]
            r1, r3, r6, r12 = get_ref_day_ret(df, curr, 1), get_ref_day_ret(df, curr, 3), get_ref_day_ret(df, curr, 6), get_ref_day_ret(df, curr, 12)
            score = (r1*-0.2) + (r3*0.8) + (r6*0.5) + (r12*0.2)
            res.append({'기준일': today.strftime('%Y-%m-%d'), '시장': 'US', '종목명': name, '종목코드': symbol, '기준가': round(curr, 2), '1개월(%)': round(r1, 1), '3개월(%)': round(r3, 1), '6개월(%)': round(r6, 1), '12개월(%)': round(r12, 1), '모멘텀스코어': round(score, 1)})
        except: continue
    if res: pd.DataFrame(res).sort_values('모멘텀스코어', ascending=False).to_csv('momentum_data_daily_us.csv', index=False)

if __name__ == "__main__":
    run_daily_kr()
    run_daily_us()
