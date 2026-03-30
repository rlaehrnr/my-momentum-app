import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import os

# 폴더 생성
for d in ['data', 'archive', 'archive_us', 'archive_sp500']:
    if not os.path.exists(d): os.makedirs(d)

def get_target_ref_date():
    today = datetime.today()
    return (today.replace(day=1) - timedelta(days=1)).strftime('%Y-%m-%d')

def get_top_stocks(market, limit=150):
    try:
        df = fdr.StockListing(market)
        if market == 'S&P500': return df.drop_duplicates('Symbol')
        cap_col = [c for c in df.columns if 'market' in c.lower() and 'cap' in c.lower()]
        if not cap_col: cap_col = [c for c in df.columns if 'mar' in c.lower() and 'cap' in c.lower()]
        return df.sort_values(cap_col[0], ascending=False).head(limit) if cap_col else df.head(limit)
    except: return pd.DataFrame()

def run_monthly(market_type='KR'):
    if market_type == 'KR':
        name_tag, file_path, folder, prefix = "한국", 'data/momentum_data.csv', 'archive', 'momentum_'
        market_list, limit = ['KOSPI', 'KOSDAQ'], 150
    elif market_type == 'US':
        name_tag, file_path, folder, prefix = "미국(시총상위)", 'data/momentum_data_us.csv', 'archive_us', 'momentum_us_'
        market_list, limit = ['NYSE', 'NASDAQ'], 150
    elif market_type == 'SP500':
        name_tag, file_path, folder, prefix = "S&P 500", 'data/momentum_data_sp500.csv', 'archive_sp500', 'momentum_sp500_'
        market_list, limit = ['S&P500'], 505
        # 시장 구분용 매핑
        nyse = fdr.StockListing('NYSE')[['Symbol']]
        nasdaq = fdr.StockListing('NASDAQ')[['Symbol']]
        mkt_map = {s: 'NYSE' for s in nyse['Symbol']}
        mkt_map.update({s: 'NASDAQ' for s in nasdaq['Symbol']})

    target_date_str = get_target_ref_date()
    target_date_dt = pd.to_datetime(target_date_str)
    print(f"🔍 {name_tag} 월말 데이터 업데이트 시작...")

    # 1. 아카이브 보관 로직
    if os.path.exists(file_path):
        df_old = pd.read_csv(file_path)
        existing_date = str(df_old['기준일(월말)'].iloc[0])
        if existing_date != target_date_str:
            # 다음달 수익률(성적표) 계산
            forward_returns = []
            today = datetime.today()
            for _, row in df_old.iterrows():
                try:
                    df_now = fdr.DataReader(str(row['종목코드']).replace('.', '-'), today - timedelta(days=7), today)
                    curr_p = df_now['Close'].iloc[-1]
                    forward_returns.append(round((curr_p - row['기준가']) / row['기준가'] * 100, 1))
                except: forward_returns.append(0.0)
            df_old['다음달수익률(%)'] = forward_returns
            
            ym = (datetime.strptime(existing_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y_%m')
            df_old.to_csv(f'{folder}/{prefix}{ym}.csv', index=False, encoding='utf-8-sig')

    # 2. 신규 월말 데이터 수집
    res = []
    for mkt_name in market_list:
        target_stocks = get_top_stocks(mkt_name, limit)
        for _, row in target_stocks.iterrows():
            try:
                code = row['Code'] if 'Code' in row else row['Symbol']
                df = fdr.DataReader(code.replace('.', '-'), target_date_dt - pd.DateOffset(months=16), target_date_dt)
                if df.empty: continue
                
                base_price = df['Close'].iloc[-1]
                def get_ret(m):
                    ref = (target_date_dt.replace(day=1) - pd.DateOffset(months=m-1)) - timedelta(days=1)
                    past = df[df.index <= ref]
                    return (base_price - past['Close'].iloc[-1]) / past['Close'].iloc[-1] * 100 if not past.empty else 0.0
                
                r1, r3, r6, r12 = get_ret(1), get_ret(3), get_ret(6), get_ret(12)
                score = round((r1*-0.2) + (r3*0.8) + (r6*0.5) + (r12*0.2), 1)
                
                display_mkt = mkt_map.get(code, 'NYSE') if market_type == 'SP500' else mkt_name

                res.append({
                    '기준일(월말)': target_date_str, '시장': display_mkt,
                    '종목명': row['Name'], '종목코드': code, '기준가': round(base_price, 2),
                    '1개월(%)': round(r1, 1), '3개월(%)': round(r3, 1), '6개월(%)': round(r6, 1),
                    '12개월(%)': round(r12, 1), '모멘텀스코어': score, '다음달수익률(%)': 0.0
                })
            except: continue
    
    if res:
        pd.DataFrame(res).sort_values('모멘텀스코어', ascending=False).to_csv(file_path, index=False, encoding='utf-8-sig')
        print(f"✨ {name_tag} 월말 저장 완료!")

if __name__ == "__main__":
    run_monthly('KR')
    run_monthly('US')
    run_monthly('SP500')
