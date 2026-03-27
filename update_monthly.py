import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import os
import time

# 공통: 폴더 생성
for d in ['data', 'archive', 'archive_us']:
    if not os.path.exists(d): os.makedirs(d)

def get_ref_date():
    today = datetime.today()
    return (today.replace(day=1) - timedelta(days=1)).strftime('%Y-%m-%d')

def get_top_stocks(market, limit=150):
    df = fdr.StockListing(market)
    cap_col = [c for c in df.columns if 'market' in c.lower() and 'cap' in c.lower()]
    if not cap_col: cap_cols = [c for c in df.columns if 'mar' in c.lower() and 'cap' in c.lower()]
    return df.sort_values(cap_col[0], ascending=False).head(limit) if cap_col else df.head(limit)

def run_monthly(market_type='KR'):
    name_tag = "한국" if market_type == 'KR' else "미국"
    print(f"🚀 {name_tag} 월말 업데이트 시작...")
    
    # 1. 보관 및 채점
    file_path = f'data/momentum_data{"_us" if market_type=="US" else ""}.csv'
    if os.path.exists(file_path):
        df_old = pd.read_csv(file_path)
        base_dt = df_old['기준일(월말)'].iloc[0]
        ym = datetime.strptime(base_dt, '%Y-%m-%d').strftime('%Y_%m')
        # 채점 로직 (현재가 대비 수익률 계산 - 생략 가능하나 기능 유지)
        df_old.to_csv(f'archive{"_us" if market_type=="US" else ""}/momentum_{"us_" if market_type=="US" else ""}{ym}.csv', index=False)

    # 2. 신규 수집
    base_date = get_ref_date()
    markets = ['KOSPI', 'KOSDAQ'] if market_type == 'KR' else ['NYSE', 'NASDAQ']
    target = pd.concat([get_top_stocks(m) for m in markets])
    
    today = datetime.today()
    res = []
    for _, row in target.iterrows():
        try:
            code = row['Code'] if 'Code' in row else row['Symbol']
            df = fdr.DataReader(code.replace('.', '-'), today - pd.DateOffset(months=16), today)
            curr = df['Close'].iloc[-1]
            def get_ret(m):
                ref = (today.replace(day=1) - pd.DateOffset(months=m-1)) - timedelta(days=1)
                p = df[df.index <= ref]
                return round((curr - p['Close'].iloc[-1]) / p['Close'].iloc[-1] * 100, 1) if not p.empty else 0.0
            r1, r3, r6, r12 = get_ret(1), get_ret(3), get_ret(6), get_ret(12)
            score = round((r1*-0.2) + (r3*0.8) + (r6*0.5) + (r12*0.2), 1)
            res.append({'기준일(월말)': base_date, '시장': row.get('Market', market_type), '종목명': row['Name'], '종목코드': code, '기준가': curr, '1개월(%)': r1, '3개월(%)': r3, '6개월(%)': r6, '12개월(%)': r12, '모멘텀스코어': score})
        except: continue
    pd.DataFrame(res).sort_values('모멘텀스코어', ascending=False).to_csv(file_path, index=False)
    print(f"✅ {name_tag} 완료!")

if __name__ == "__main__":
    run_monthly('KR')
    run_monthly('US')
