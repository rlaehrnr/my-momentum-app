import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

# 폴더 생성 (기록보관소용 포함)
folders = ['data', 'archive', 'archive_us', 'archive_sp500']
for d in folders:
    if not os.path.exists(d): os.makedirs(d)

def get_top_stocks(market, limit=150):
    """시가총액 상위 종목 추출 및 시가총액 데이터 미리 확보"""
    try:
        if market in ['KOSPI', 'KOSDAQ']:
            # KRX 전체 리스트를 가져와서 시가총액 정보 확보
            df = fdr.StockListing('KRX')
            mkt_col = [c for c in df.columns if 'market' in c.lower() or '시장' in c][0]
            df = df[df[mkt_col].astype(str).str.upper().str.contains(market.upper())]
            
            # 한국 시장 우선주 차단 및 코드 6자리 유지
            code_col = 'Code' if 'Code' in df.columns else 'Symbol'
            df = df[df[code_col].astype(str).str.endswith('0')]
            df[code_col] = df[code_col].astype(str).str.zfill(6)
        else:
            # 미국 시장 시가총액 포함 리스트
            df = fdr.StockListing(market)

        if df.empty: return pd.DataFrame()
        
        # 시가총액 컬럼 표준화
        cap_col = [c for c in df.columns if '시가총액' in c or ('mar' in c.lower() and 'cap' in c.lower())]
        if cap_col:
            target_col = cap_col[0]
            df['시가총액_raw'] = pd.to_numeric(df[target_col].astype(str).str.replace(r'[^0-9.eE+-]', '', regex=True), errors='coerce').fillna(0)
            
            # 한국 시장이면 '억' 단위로 미리 변환
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
    """월말 기준 데이터 분석 및 다음달 수익률 계산"""
    try:
        code = str(row.get('Code', row.get('Symbol', '')))
        if market_type == 'KR': code = code.zfill(6)
        
        clean_code = code.replace('.', '-') if market_type in ['US', 'SP500'] else code
        
        # 분석을 위해 충분한 기간의 데이터 로드
        df = fdr.DataReader(clean_code, ref_date - pd.DateOffset(months=16), next_month_end)
        if df.empty: return None
        
        # 기준일(월말) 데이터 필터링
        df_base = df[df.index <= ref_date]
        if df_base.empty: return None
        
        curr_price = df_base['Close'].iloc[-1]
        
        # 1, 3, 6, 12개월 전 수익률 계산 로직
        def get_ret(m):
            ref = (ref_date.replace(day=1) - pd.DateOffset(months=m-1)) - timedelta(days=1)
            past = df_base[df_base.index <= ref]
            if past.empty: return 0.0
            return (curr_price - past['Close'].iloc[-1]) / past['Close'].iloc[-1] * 100
        
        r1, r3, r6, r12 = get_ret(1), get_ret(3), get_ret(6), get_ret(12)
        score = round((r1 * -0.5) + (r3 * 0.8) + (r6 * 0.5) + (r12 * 0.2), 1)
        
        # 💡 다음달 수익률 계산 (백테스팅용 실제 성적)
        df_next = df[(df.index > ref_date) & (df.index <= next_month_end)]
        next_ret = round(((df_next['Close'].iloc[-1] / curr_price) - 1) * 100, 2) if not df_next.empty else 0.0

        return {
            '기준일(월말)': ref_date.strftime('%Y-%m-%d'), 
            '시장': mkt_name, '종목명': row['Name'], '종목코드': code, 
            '시가총액': row.get('시가총액', 0), '기준가': round(curr_price, 2),
            '1개월(%)': round(r1, 1), '3개월(%)': round(r3, 1), '6개월(%)': round(r6, 1),
            '12개월(%)': round(r12, 1), '모멘텀스코어': score,
            '다음달수익률(%)': next_ret,
            '전달순위': prev_rank_map.get(code.upper(), None)
        }
    except Exception:
        return None

def run_monthly(market_type='KR'):
    # 설정값 로드
    conf = {
        'KR': ("한국", 'data/momentum_data.csv', 'archive', ['KOSPI', 'KOSDAQ'], 200),
        'US': ("미국", 'data/momentum_data_us.csv', 'archive_us', ['NYSE', 'NASDAQ'], 200),
        'SP500': ("S&P 500", 'data/momentum_data_sp500.csv', 'archive_sp500', ['S&P500'], 505)
    }
    name_tag, main_file, arch_dir, market_list, limit = conf[market_type]

    # 오늘 날짜 기준으로 '지난달 말일'을 기준일로 설정
    today = datetime.today()
    ref_date = today.replace(day=1) - timedelta(days=1)
    # 다음달 성적을 위해 '이번달 현재'까지의 데이터를 봄
    next_month_end = today 
    
    archive_name = f"momentum_{'us_' if market_type=='US' else ('sp500_' if market_type=='SP500' else '')}{ref_date.strftime('%Y_%m')}.csv"
    arch_path = os.path.join(arch_dir, archive_name)

    print(f"📅 {name_tag} 월간 업데이트 및 아카이브 시작... (기준일: {ref_date.strftime('%Y-%m-%d')})")
    
    res = []
    for mkt_name in market_list:
        target_stocks = get_top_stocks(mkt_name, limit)
        if target_stocks.empty: continue
            
        print(f"🔎 {mkt_name} 분석 중...")
        with ThreadPoolExecutor(max_workers=10) as executor:
            # 전달 순위 맵은 편의상 생략하거나 필요시 daily 로직 이식 가능
            futures = [executor.submit(process_stock_monthly, row, mkt_name, market_type, ref_date, next_month_end, {}) for _, row in target_stocks.iterrows()]
            for future in as_completed(futures):
                result = future.result()
                if result: res.append(result)

    if res:
        final_df = pd.DataFrame(res).sort_values('모멘텀스코어', ascending=False)
        
        # 메인 데이터 갱신
        final_df.to_csv(main_file, index=False, encoding='utf-8-sig')
        # 아카이브 저장
        final_df.to_csv(arch_path, index=False, encoding='utf-8-sig')
        
        print(f"✅ {name_tag} 월간 업데이트 완료! -> {arch_path} 저장됨")

if __name__ == "__main__":
    for m in ['KR', 'US', 'SP500']:
        run_monthly(m)
