import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import os
import time

# 헬퍼 함수: 시가총액 컬럼 자동으로 찾아서 정렬하기
def get_top_stocks(market_code, limit=150):
    try:
        df = fdr.StockListing(market_code)
        # 'market', 'cap', 'mar' 등이 포함된 컬럼 찾기 (대소문자 무시)
        cap_cols = [c for c in df.columns if 'market' in c.lower() and 'cap' in c.lower()]
        if not cap_cols:
            cap_cols = [c for c in df.columns if 'mar' in c.lower() and 'cap' in c.lower()]
        
        if cap_cols:
            return df.sort_values(cap_cols[0], ascending=False).head(limit)
        else:
            return df.head(limit) # 못 찾으면 그냥 상단 종목 사용
    except:
        return pd.DataFrame()

def get_last_day_ret(df, curr_price, months):
    today = datetime.today()
    ref_date = today - pd.DateOffset(months=months)
    ref_date = ref_date.replace(day=1) - timedelta(days=1)
    past = df[df.index <= ref_date]
    if past.empty: return 0.0
    return (curr_price - past['Close'].iloc[-1]) / past['Close'].iloc[-1] * 100

def run_daily_kr():
    print("🇰🇷 한국 데일리 수집 중 (상위 300위)...")
    df_ks = get_top_stocks('KOSPI', 150)
    df_kq = get_top_stocks('KOSDAQ', 150)
    df_ks['시장'], df_kq['시장'] = 'KOSPI', 'KOSDAQ'
    target = pd.concat([df_ks, df_kq])
    
    today = datetime.today()
    res = []
    for i, (_, row) in enumerate(target.iterrows()):
        code = row['Code'] if 'Code' in row else row['Symbol']
        name = row['Name']
        try:
            df = fdr.DataReader(code, today - pd.DateOffset(months=15), today)
            if df.empty: continue
            curr = df['Close'].iloc[-1]
            r1, r3, r6, r12 = get_last_day_ret(df, curr, 1), get_last_day_ret(df, curr, 3), get_last_day_ret(df, curr, 6), get_last_day_ret(df, curr, 12)
            score = (r1*-0.2) + (r3*0.8) + (r6*0.5) + (r12*0.2)
            res.append({
                '기준일': today.strftime('%Y-%m-%d'), '시장': row['시장'], '종목명': name, '종목코드': code, 
                '기준가': int(curr), '1개월(%)': round(r1, 1), '3개월(%)': round(r3, 1), 
                '6개월(%)': round(r6, 1), '12개월(%)': round(r12, 1), '모멘텀스코어': round(score, 1)
            })
        except: continue
        if i % 50 == 0: print(f"진행 중... {i}/300")
    
    if res:
        pd.DataFrame(res).sort_values('모멘텀스코어', ascending=False).to_csv('momentum_data_daily.csv', index=False)
        print("✅ 한국 데일리 파일 저장 완료!")

def run_daily_us():
    print("🇺🇸 미국 데일리 수집 중 (상위 300위)...")
    df_ny = get_top_stocks('NYSE', 150)
    df_nd = get_top_stocks('NASDAQ', 150)
    df_ny['시장'], df_nd['시장'] = 'NYSE', 'NASDAQ'
    target = pd.concat([df_ny, df_nd])
    
    today = datetime.today()
    res = []
    for i, (_, row) in enumerate(target.iterrows()):
        symbol = row['Symbol']
        name = row['Name']
        try:
            fetch_symbol = symbol.replace('.', '-')
            df = fdr.DataReader(fetch_symbol, today - pd.DateOffset(months=15), today)
            if df.empty: continue
            curr = df['Close'].iloc[-1]
            r1, r3, r6, r12 = get_last_day_ret(df, curr, 1), get_last_day_ret(df, curr, 3), get_last_day_ret(df, curr, 6), get_last_day_ret(df, curr, 12)
            score = (r1*-0.2) + (r3*0.8) + (r6*0.5) + (r12*0.2)
            res.append({
                '기준일': today.strftime('%Y-%m-%d'), '시장': row['시장'], '종목명': name, '종목코드': symbol, 
                '기준가': round(curr, 2), '1개월(%)': round(r1, 1), '3개월(%)': round(r3, 1), 
                '6개월(%)': round(r6, 1), '12개월(%)': round(r12, 1), '모멘텀스코어': round(score, 1)
            })
        except: continue
        if i % 50 == 0: print(f"진행 중... {i}/300")
        
    if res:
        pd.DataFrame(res).sort_values('모멘텀스코어', ascending=False).to_csv('momentum_data_daily_us.csv', index=False)
        print("✅ 미국 데일리 파일 저장 완료!")

if __name__ == "__main__":
    run_daily_kr()
    run_daily_us()
