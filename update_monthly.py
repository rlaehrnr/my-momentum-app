import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

folders = ['data', 'archive', 'archive_us', 'archive_sp500']
for d in folders:
    if not os.path.exists(d): os.makedirs(d)

def get_top_stocks(market, limit=150):
    try:
        if market in ['KOSPI', 'KOSDAQ']:
            df = fdr.StockListing('KRX')
            mkt_col = [c for c in df.columns if 'market' in c.lower() or '시장' in c][0]
            df = df[df[mkt_col].astype(str).str.upper().str.contains(market.upper())]
            code_col = 'Code' if 'Code' in df.columns else 'Symbol'
            df = df[df[code_col].astype(str).str.endswith('0')]
            df[code_col] = df[code_col].astype(str).str.zfill(6)
        else:
            df = fdr.StockListing(market)

        if df.empty: return pd.DataFrame()
        
        cap_col = [c for c in df.columns if '시가총액' in c or ('mar' in c.lower() and 'cap' in c.lower())]
        if cap_col:
            target_col = cap_col[0]
            df['시가총액_raw'] = pd.to_numeric(df[target_col].astype(str).str.replace(r'[^0-9.eE+-]', '', regex=True), errors='coerce').fillna(0)
            if market in ['KOSPI', 'KOSDAQ']:
                df['시가총액'] = (df['시가총액_raw'] / 100000000).astype(int)
            else:
                df['시가총액'] = df['시가총액_raw']
            df = df.sort_values('시가총액_raw', ascending=False)

        symbol_col = 'Symbol' if 'Symbol' in df.columns else 'Code'
        df = df.drop_duplicates(subset=[symbol_col])
        return df.head(limit)
    except Exception as e:
        print(f"❌ {market} 리스트 가져오기 실패: {e}")
        return pd.DataFrame()

def process_stock_monthly(row, mkt_name, market_type, ref_date, next_month_end, prev_rank_map):
    try:
        code = str(row.get('Code', row.get('Symbol', '')))
        if market_type == 'KR': code = code.zfill(6)
        clean_code = code.replace('.', '-') if market_type in ['US', 'SP500'] else code
        
        df = fdr.DataReader(clean_code, ref_date - pd.DateOffset(months=16), next_month_end)
        if df.empty: return None
        df_base = df[df.index <= ref_date]
        if df_base.empty: return None
        
        curr_price = df_base['Close'].iloc[-1]
        
        def get_ret(m):
            ref = (ref_date.replace(day=1) - pd.DateOffset(months=m-1)) - timedelta(days=1)
            past = df_base[df_base.index <= ref]
            if past.empty: return 0.0
            return (curr_price - past['Close'].iloc[-1]) / past['Close'].iloc[-1] * 100
        
        r1, r3, r6, r12 = get_ret(1), get_ret(3), get_ret(6), get_ret(12)
        denom = (1 + r1 / 100) + 1e-9
        r3_1 = round(((1 + r3/100) / denom - 1) * 100, 2)
        r6_1 = round(((1 + r6/100) / denom - 1) * 100, 2)
        r12_1 = round(((1 + r12/100) / denom - 1) * 100, 2)
        
        score = round((r1 * -0.5) + (r3 * 0.8) + (r6 * 0.5) + (r12 * 0.2), 1)
        df_next = df[(df.index > ref_date) & (df.index <= next_month_end)]
        next_ret = round(((df_next['Close'].iloc[-1] / curr_price) - 1) * 100, 2) if not df_next.empty else 0.0

        return {
            '기준일(월말)': ref_date.strftime('%Y-%m-%d'), 
            '시장': mkt_name, '종목명': row['Name'], '종목코드': code, 
            '시가총액': row.get('시가총액', 0), '기준가': round(curr_price, 2),
            '1개월(%)': round(r1, 1), '3개월(%)': round(r3, 1), '6개월(%)': round(r6, 1), '12개월(%)': round(r12, 1),
            '3-1개월(%)': r3_1, '6-1개월(%)': r6_1, '12-1개월(%)': r12_1,
            '모멘텀스코어': score, '다음달수익률(%)': next_ret,
            '전달순위': prev_rank_map.get(code.upper(), None) # 💡 이제 정상적인 맵퍼가 들어갑니다.
        }
    except Exception: return None

def run_monthly(market_type='KR'):
    conf = {
        'KR': ("한국", 'data/momentum_data.csv', 'archive', ['KOSPI', 'KOSDAQ'], 200),
        'US': ("미국", 'data/momentum_data_us.csv', 'archive_us', ['NYSE', 'NASDAQ'], 200),
        'SP500': ("S&P 500", 'data/momentum_data_sp500.csv', 'archive_sp500', ['S&P500'], 505)
    }
    name_tag, main_file, arch_dir, market_list, limit = conf[market_type]

    today = datetime.today()
    ref_date = today.replace(day=1) - timedelta(days=1)
    next_month_end = today 
    
    # 💡 [핵심 수정] 두 달 전 아카이브 파일을 찾아서 '전달순위'를 미리 계산합니다.
    prev_ref_date = ref_date.replace(day=1) - timedelta(days=1)
    archive_prefix = 'us_' if market_type=='US' else ('sp500_' if market_type=='SP500' else '')
    prev_arch_name = f"momentum_{archive_prefix}{prev_ref_date.strftime('%Y_%m')}.csv"
    prev_arch_path = os.path.join(arch_dir, prev_arch_name)
    
    prev_rank_map = {}
    if os.path.exists(prev_arch_path):
        try:
            df_p = pd.read_csv(prev_arch_path, dtype={'종목코드': str})
            df_p = df_p.sort_values('모멘텀스코어', ascending=False).reset_index(drop=True)
            for i, r in df_p.iterrows():
                # 한국 종목은 6자리 0채움 처리, 미국은 그대로 대문자화
                c_key = str(r['종목코드']).zfill(6) if market_type == 'KR' else str(r['종목코드']).upper()
                prev_rank_map[c_key] = i + 1
        except: pass

    archive_name = f"momentum_{archive_prefix}{ref_date.strftime('%Y_%m')}.csv"
    arch_path = os.path.join(arch_dir, archive_name)

    print(f"📅 {name_tag} 월간 업데이트 시작... (기준일: {ref_date.strftime('%Y-%m-%d')})")
    
    res = []
    for mkt_name in market_list:
        target_stocks = get_top_stocks(mkt_name, limit)
        if target_stocks.empty: continue
            
        print(f"🔎 {mkt_name} 분석 중...")
        with ThreadPoolExecutor(max_workers=10) as executor:
            # 💡 {} 하드코딩 대신 prev_rank_map 을 전달!
            futures = [executor.submit(process_stock_monthly, row, mkt_name, market_type, ref_date, next_month_end, prev_rank_map) for _, row in target_stocks.iterrows()]
            for future in as_completed(futures):
                result = future.result()
                if result: res.append(result)

    if res:
        final_df = pd.DataFrame(res).sort_values('모멘텀스코어', ascending=False)
        final_df.to_csv(main_file, index=False, encoding='utf-8-sig')
        final_df.to_csv(arch_path, index=False, encoding='utf-8-sig')
        print(f"✅ {name_tag} 업데이트 완료! (전달순위 정상 복구됨)")

if __name__ == "__main__":
    for m in ['KR', 'US', 'SP500']:
        run_monthly(m)
