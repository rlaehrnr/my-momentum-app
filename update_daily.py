import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# 폴더 생성
if not os.path.exists('data'): os.makedirs('data')

def get_top_stocks(market, limit=150):
    try:
        if market in ['KOSPI', 'KOSDAQ']:
            df = fdr.StockListing('KRX')
            if df.empty: df = fdr.StockListing(market)
            else:
                mkt_col = [c for c in df.columns if 'market' in c.lower() or '시장' in c][0]
                df = df[df[mkt_col].astype(str).str.upper().str.contains(market.upper())]
        else:
            df = fdr.StockListing(market)

        if df.empty: return pd.DataFrame()
        if market == 'S&P500': return df.drop_duplicates(subset=['Symbol']).head(limit)
        
        cap_col = [c for c in df.columns if '시가총액' in c or ('mar' in c.lower() and 'cap' in c.lower())]
        if cap_col:
            target_col = cap_col[0]
            df[target_col] = pd.to_numeric(df[target_col].astype(str).str.replace(',', ''), errors='coerce')
            df = df.sort_values(target_col, ascending=False)

        if market in ['KOSPI', 'KOSDAQ']:
            name_col = [c for c in df.columns if 'name' in c.lower() or '종목명' in c]
            if name_col:
                col = name_col[0]
                df = df[~df[col].astype(str).str.endswith(('우', '우B', '우C'))]
                df = df[~df[col].astype(str).str.contains('스팩')]
        return df.head(limit)
    except Exception as e:
        print(f"❌ {market} 리스트 가져오기 실패: {e}")
        return pd.DataFrame()

def process_stock(row, mkt_name, market_type, today, prev_rank_map):
    try:
        code = str(row.get('Code', row.get('Symbol', '')))
        clean_code = code.split('.')[0].replace('.', '-')
        df = fdr.DataReader(clean_code, today - pd.DateOffset(months=16), today)
        if df.empty: return None
        
        curr_p = df['Close'].iloc[-1]
        curr_v = int(df['Volume'].iloc[-1]) if 'Volume' in df.columns else 0
        
        def get_ret(m):
            ref = (today.replace(day=1) - pd.DateOffset(months=m-1)) - timedelta(days=1)
            past = df[df.index <= ref]
            return (curr_p - past['Close'].iloc[-1]) / past['Close'].iloc[-1] * 100 if not past.empty else 0.0
        
        r1, r3, r6, r12 = get_ret(1), get_ret(3), get_ret(6), get_ret(12)
        score = round((r1*-0.2) + (r3*0.8) + (r6*0.5) + (r12*0.2), 1)
        
        # 💡 [핵심] 전달 순위 매핑
        p_rank = prev_rank_map.get(code, '-')

        return {
            '기준일': df.index[-1].strftime('%Y-%m-%d'), '시장': mkt_name, '종목명': row['Name'], 
            '종목코드': code, '기준가': round(curr_p, 2), '전일거래량': curr_v,
            '1개월(%)': round(r1, 1), '3개월(%)': round(r3, 1), '6개월(%)': round(r6, 1),
            '12개월(%)': round(r12, 1), '모멘텀스코어': score, '전달순위': p_rank
        }
    except: return None

def run_daily(m_type='KR'):
    # 설정
    conf = {
        'KR': ('한국', 'data/momentum_data_daily.csv', 'data/momentum_data.csv', ['KOSPI', 'KOSDAQ'], 150),
        'US': ('미국', 'data/momentum_data_daily_us.csv', 'data/momentum_data_us.csv', ['NYSE', 'NASDAQ'], 150),
        'SP500': ('S&P 500', 'data/momentum_data_daily_sp500.csv', 'data/momentum_data_sp500.csv', ['S&P500'], 505)
    }
    name, f_path, p_path, m_list, limit = conf[m_type]
    
    # 💡 [핵심] 지난달 월말 데이터 로드하여 순위 맵 생성
    prev_rank_map = {}
    if os.path.exists(p_path):
        try:
            df_p = pd.read_csv(p_path, dtype={'종목코드': str})
            for i, r in df_p.iterrows():
                prev_rank_map[str(r['종목코드'])] = f"{i+1}위"
        except: print(f"⚠️ {name} 지난달 데이터 로드 실패")

    today = datetime.today()
    res = []
    for mkt in m_list:
        curr_limit = 200 if mkt == 'KOSPI' else limit
        stocks = get_top_stocks(mkt, curr_limit)
        with ThreadPoolExecutor(max_workers=10) as exe:
            futures = [exe.submit(process_stock, row, mkt, m_type, today, prev_rank_map) for _, row in stocks.iterrows()]
            for f in as_completed(futures):
                if f.result(): res.append(f.result())
    
    if res:
        pd.DataFrame(res).sort_values('모멘텀스코어', ascending=False).to_csv(f_path, index=False, encoding='utf-8-sig')
        print(f"✅ {name} 데일리 업데이트 완료!")

if __name__ == "__main__":
    for m in ['KR', 'US', 'SP500']: run_daily(m)
