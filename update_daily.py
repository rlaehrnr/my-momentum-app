import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# 1. 폴더 생성
folders = ['data', 'archive', 'archive_us', 'archive_sp500']
for d in folders:
    if not os.path.exists(d): os.makedirs(d)

def get_top_stocks(market, limit=150):
    """시가총액 상위 종목 추출 (KRX, KOSPI, KOSDAQ 대응)"""
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

# 💡 수정 1: 데일리 프로세스 함수 (prev_rank_map 추가)
def process_stock(row, mkt_name, market_type, today, prev_rank_map):
    """개별 종목 데일리 데이터 수집 및 스코어 계산"""
    try:
        code = str(row.get('Code', row.get('Symbol', '')))
        clean_code = code.split('.')[0].replace('.', '-')
        
        # 데이터 로드 (최근 16개월)
        df = fdr.DataReader(clean_code, today - pd.DateOffset(months=16), today)
        if df.empty: return None
        
        curr_price = df['Close'].iloc[-1]
        curr_volume = int(df['Volume'].iloc[-1]) if 'Volume' in df.columns else 0
        last_date = df.index[-1].strftime('%Y-%m-%d')
        
        def get_ret(m):
            ref = (today.replace(day=1) - pd.DateOffset(months=m-1)) - timedelta(days=1)
            past = df[df.index <= ref]
            if past.empty: return 0.0
            return (curr_price - past['Close'].iloc[-1]) / past['Close'].iloc[-1] * 100
        
        r1, r3, r6, r12 = get_ret(1), get_ret(3), get_ret(6), get_ret(12)
        score = round((r1*-0.5) + (r3*0.8) + (r6*0.5) + (r12*0.2), 1)
        
        display_mkt = row.get('Exchange', 'NYSE') if market_type == 'SP500' else mkt_name

        # 💡 수정 2: 전달순위 매핑 (숫자로 저장)
        return {
            '기준일': last_date, '시장': display_mkt, '종목명': row['Name'], 
            '종목코드': code, '기준가': round(curr_price, 2), '전일거래량': curr_volume,
            '1개월(%)': round(r1, 1), '3개월(%)': round(r3, 1), '6개월(%)': round(r6, 1),
            '12개월(%)': round(r12, 1), '모멘텀스코어': score, 
            '전달순위': prev_rank_map.get(code, None) # 숫자 1, 2, 3... 혹은 None
        }
    except Exception:
        return None

def run_daily(market_type='KR'):
    """데일리 데이터 수집 메인 로직"""
    conf = {
        'KR': ("한국", 'data/momentum_data_daily.csv', 'data/momentum_data.csv', ['KOSPI', 'KOSDAQ'], 150),
        'US': ("미국", 'data/momentum_data_daily_us.csv', 'data/momentum_data_us.csv', ['NYSE', 'NASDAQ'], 150),
        'SP500': ("S&P 500", 'data/momentum_data_daily_sp500.csv', 'data/momentum_data_sp500.csv', ['S&P500'], 505)
    }
    
    # 설정값 풀기
    name_tag, file_path, p_path, market_list, limit = conf[market_type]

    # 💡 [들여쓰기 주의!] 지난달 월말 데이터를 읽어 전달 순위표 생성
    prev_rank_map = {}
    if os.path.exists(p_path):
        try:
            df_p = pd.read_csv(p_path, dtype={'종목코드': str})
            # 스코어 기준 내림차순 정렬 후 인덱스로 순위 부여
            df_p = df_p.sort_values('모멘텀스코어', ascending=False).reset_index(drop=True)
            for i, r in df_p.iterrows():
                prev_rank_map[str(r['종목코드'])] = i + 1
        except Exception as e:
            print(f"⚠️ {name_tag} 이전 순위 로드 실패: {e}")

    today = datetime.today()
    print(f"🕒 {name_tag} 데일리 데이터 수집 시작... (기준일: {today.strftime('%Y-%m-%d')})")
    res = []

    for mkt_name in market_list:
        current_limit = 200 if mkt_name == 'KOSPI' else limit
        target_stocks = get_top_stocks(mkt_name, current_limit)
        
        if target_stocks.empty: 
            continue
            
        print(f"🔎 {mkt_name} {len(target_stocks)}개 종목 분석 중 (병렬 처리)...")
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(process_stock, row, mkt_name, market_type, today, prev_rank_map) for _, row in target_stocks.iterrows()]
            for future in as_completed(futures):
                result = future.result()
                if result: 
                    res.append(result)
                    
    if res:
        final_df = pd.DataFrame(res).sort_values('모멘텀스코어', ascending=False)
        final_df.to_csv(file_path, index=False, encoding='utf-8-sig')
        print(f"✅ {name_tag} 데일리 업데이트 완료!")
