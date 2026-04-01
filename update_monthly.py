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

def get_target_ref_date():
    """실행 시점 기준 '전월 말일' 날짜 반환"""
    today = datetime.today()
    return (today.replace(day=1) - timedelta(days=1)).strftime('%Y-%m-%d')

def get_top_stocks(market, limit=150):
    """안정적인 KRX 전체 리스트를 사용해 시가총액 상위 종목 추출"""
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

# 💡 수정 1: 매개변수에 prev_rank_map 추가
def process_monthly_stock(row, mkt_name, market_type, target_date_dt, target_date_str, mkt_map, prev_rank_map):
    """개별 종목 데이터 수집 및 스코어 계산 (병렬 처리용)"""
    try:
        code = str(row.get('Code', row.get('Symbol', '')))
        clean_code = code.split('.')[0].replace('.', '-')
        
        df = fdr.DataReader(clean_code, target_date_dt - pd.DateOffset(months=16), target_date_dt)
        if df.empty: return None
        
        base_price = df['Close'].iloc[-1]
        
        def get_ret(m):
            ref = (target_date_dt.replace(day=1) - pd.DateOffset(months=m-1)) - timedelta(days=1)
            past = df[df.index <= ref]
            return (base_price - past['Close'].iloc[-1]) / past['Close'].iloc[-1] * 100 if not past.empty else 0.0
        
        r1, r3, r6, r12 = get_ret(1), get_ret(3), get_ret(6), get_ret(12)
        score = round((r1*-0.2) + (r3*0.8) + (r6*0.5) + (r12*0.2), 2)
        
        display_mkt = mkt_map.get(code, 'NYSE') if market_type == 'SP500' else mkt_name

        # 💡 수정 2: 결과값에 '전달순위' 추가 (숫자로 저장)
        return {
            '기준일(월말)': target_date_str, '시장': display_mkt,
            '종목명': row['Name'], '종목코드': code, '기준가': round(base_price, 2),
            '1개월(%)': round(r1, 2), '3개월(%)': round(r3, 2), '6개월(%)': round(r6, 2),
            '12개월(%)': round(r12, 2), '모멘텀스코어': score, 
            '전달순위': prev_rank_map.get(code, None), # 지난달 순위 매핑
            '다음달수익률(%)': 0.0
        }
    except: return None

def run_monthly(market_type='KR'):
    mkt_map = {} 
    
    if market_type == 'KR':
        name_tag, file_path, folder, prefix = "한국", 'data/momentum_data.csv', 'archive', 'momentum_'
        market_list, limit = ['KOSPI', 'KOSDAQ'], 150
    elif market_type == 'US':
        name_tag, file_path, folder, prefix = "미국(시총상위)", 'data/momentum_data_us.csv', 'archive_us', 'momentum_us_'
        market_list, limit = ['NYSE', 'NASDAQ'], 150
    elif market_type == 'SP500':
        name_tag, file_path, folder, prefix = "S&P 500", 'data/momentum_data_sp500.csv', 'archive_sp500', 'momentum_sp500_'
        market_list, limit = ['S&P500'], 505
        try:
            nyse = fdr.StockListing('NYSE')[['Symbol']]
            nasdaq = fdr.StockListing('NASDAQ')[['Symbol']]
            mkt_map = {s: 'NYSE' for s in nyse['Symbol']}
            mkt_map.update({s: 'NASDAQ' for s in nasdaq['Symbol']})
        except: pass

    # 💡 [중요] 이전 순위표 만들기 (들여쓰기 주의!)
    prev_rank_map = {}
    if os.path.exists(file_path): # 👈 여기 변수 이름을 file_path로 써야 합니다!
        try:
            df_old_for_rank = pd.read_csv(file_path, dtype={'종목코드': str})
            df_old_for_rank = df_old_for_rank.sort_values('모멘텀스코어', ascending=False).reset_index(drop=True)
            for i, r in df_old_for_rank.iterrows():
                prev_rank_map[str(r['종목코드'])] = i + 1
        except Exception as e:
            print(f"⚠️ {name_tag} 이전 순위 로드 실패: {e}")

    target_date_str = get_target_ref_date()
    target_date_dt = pd.to_datetime(target_date_str)
    print(f"\n🚀 {name_tag} 월말 업데이트 시작 (기준일: {target_date_str})")
    

    # --- 1. 아카이브 보관 로직 ---
    if os.path.exists(file_path):
        try:
            df_old = pd.read_csv(file_path)
            existing_date = str(df_old['기준일(월말)'].iloc[0])
            if existing_date != target_date_str:
                print(f"📦 기존 데이터({existing_date}) 성적표 작성 중...")
                ym = (datetime.strptime(existing_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y_%m')
                archive_name = f'{folder}/{prefix}{ym}.csv'
                df_old.to_csv(archive_name, index=False, encoding='utf-8-sig')
        except: pass

    # --- 2. 신규 데이터 수집 ---
    res = []
    for mkt_name in market_list:
        curr_limit = 200 if mkt_name == 'KOSPI' else limit
        target_stocks = get_top_stocks(mkt_name, curr_limit)
        
        if target_stocks.empty: continue

        print(f"📊 {mkt_name} {len(target_stocks)}개 종목 분석 중...")
        with ThreadPoolExecutor(max_workers=10) as executor:
            # 💡 수정 4: executor에 prev_rank_map 전달
            futures = [executor.submit(process_monthly_stock, row, mkt_name, market_type, target_date_dt, target_date_str, mkt_map, prev_rank_map) for _, row in target_stocks.iterrows()]
            for future in as_completed(futures):
                result = future.result()
                if result: res.append(result)
                    
    if res:
        # 결과를 저장할 때도 모멘텀스코어 순으로 정렬해서 저장
        pd.DataFrame(res).sort_values('모멘텀스코어', ascending=False).to_csv(file_path, index=False, encoding='utf-8-sig')
        print(f"✨ {name_tag} 파일 저장 완료!")

if __name__ == "__main__":
    for m in ['KR', 'US', 'SP500']:
        try:
            run_monthly(m)
        except Exception as e:
            print(f"🔥 {m} 실행 중 치명적 오류: {e}")
