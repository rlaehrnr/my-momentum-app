import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

# 폴더 생성
folders = ['data', 'archive', 'archive_us', 'archive_sp500']
for d in folders:
    if not os.path.exists(d): os.makedirs(d)

# 💡 [새로 추가된 핵심 기능] 소형주 포함 2,500여개 전 종목 시가총액 마스터 파일 생성
def update_krx_master():
    print("📈 KRX 전체 종목 마스터 데이터(시가총액 포함) 업데이트 중...")
    try:
        df = fdr.StockListing('KRX')
        ticker_col = 'Symbol' if 'Symbol' in df.columns else 'Code'
        df[ticker_col] = df[ticker_col].astype(str).str.zfill(6)
        
        if 'Marcap' in df.columns:
            df['시가총액(억)'] = (pd.to_numeric(df['Marcap'], errors='coerce').fillna(0) / 100000000).astype(int)
        else:
            df['시가총액(억)'] = 0
            
        master_df = df[[ticker_col, 'Name', 'Market', '시가총액(억)']].copy()
        master_df.rename(columns={ticker_col: '종목코드', 'Name': '종목명', 'Market': '시장구분'}, inplace=True)
        
        master_df.to_csv('data/krx_stock_master.csv', index=False, encoding='utf-8-sig')
        print("✅ data/krx_stock_master.csv 업데이트 완료! (소형주 포함 전 종목 시가총액 탑재)")
    except Exception as e:
        print(f"❌ 마스터 데이터 업데이트 실패: {e}")

def get_top_stocks(market, limit=150):
    """시가총액 상위 종목 추출 및 시가총액 데이터 포함"""
    try:
        if market in ['KOSPI', 'KOSDAQ']:
            # 💡 KRX 전체 리스트를 가져와서 시가총액 정보 확보
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
        
        # 시가총액 컬럼 찾기 및 표준화
        cap_col = [c for c in df.columns if '시가총액' in c or ('mar' in c.lower() and 'cap' in c.lower())]
        if cap_col:
            target_col = cap_col[0]
            df['시가총액_raw'] = pd.to_numeric(df[target_col].astype(str).str.replace(r'[^0-9.eE+-]', '', regex=True), errors='coerce').fillna(0)
            
            # 한국 시장이면 '억' 단위로 미리 변환하여 저장 (선택 사항, 여기선 원본 유지 후 나중에 처리)
            if market in ['KOSPI', 'KOSDAQ']:
                df['시가총액'] = (df['시가총액_raw'] / 100000000).astype(int)
            else:
                df['시가총액'] = df['시가총액_raw'] # 미국은 보통 달러 단위 그대로 유지
                
            df = df.sort_values('시가총액_raw', ascending=False)

        symbol_col = 'Symbol' if 'Symbol' in df.columns else 'Code'
        # 중복 제거 및 상위 종목 제한
        df = df.drop_duplicates(subset=[symbol_col])
        return df.head(limit)
        
    except Exception as e:
        print(f"❌ {market} 리스트 가져오기 실패: {e}")
        return pd.DataFrame()

def process_stock(row, mkt_name, market_type, today, prev_rank_map):
    """개별 종목 데이터 분석 (시가총액 정보 유지)"""
    try:
        code = str(row.get('Code', row.get('Symbol', '')))
        # 한국 종목 6자리 강제 고정
        if market_type == 'KR': code = code.zfill(6)
        
        clean_code = code.replace('.', '-') if market_type in ['US', 'SP500'] else code
        
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
        score = round((r1 * 0.2) + (r3 * 0.8), 1)
        
        display_mkt = row.get('Exchange', 'NYSE') if market_type == 'SP500' else mkt_name
        
        # 💡 시가총액 정보 결과에 포함
        marcap = row.get('시가총액', 0)

        return {
            '기준일': last_date, '시장': display_mkt, '종목명': row['Name'], 
            '종목코드': code, '시가총액': marcap, '기준가': round(curr_price, 2), '전일거래량': curr_volume,
            '1개월(%)': round(r1, 1), '3개월(%)': round(r3, 1), '6개월(%)': round(r6, 1),
            '12개월(%)': round(r12, 1), '모멘텀스코어': score, 
            '전달순위': prev_rank_map.get(code.upper(), None) 
        }
    except Exception as e:
        return None

def run_daily(market_type='KR'):
    conf = {
        'KR': ("한국", 'data/momentum_data_daily.csv', 'data/momentum_data.csv', ['KOSPI', 'KOSDAQ'], 150),
        'US': ("미국", 'data/momentum_data_daily_us.csv', 'data/momentum_data_us.csv', ['NYSE', 'NASDAQ'], 150),
        'SP500': ("S&P 500", 'data/momentum_data_daily_sp500.csv', 'data/momentum_data_sp500.csv', ['S&P500'], 505)
    }
    
    name_tag, file_path, p_path, market_list, limit = conf[market_type]

    prev_rank_map = {}
    if os.path.exists(p_path):
        try:
            df_p = pd.read_csv(p_path, dtype={'종목코드': str})
            df_p = df_p.sort_values('모멘텀스코어', ascending=False).reset_index(drop=True)
            for i, r in df_p.iterrows():
                prev_rank_map[str(r['종목코드'])] = i + 1
        except Exception: pass

    today = datetime.today()
    print(f"🕒 {name_tag} 데일리 데이터 수집 시작... (기준일: {today.strftime('%Y-%m-%d')})")
    res = []

    for mkt_name in market_list:
        current_limit = 200 if mkt_name == 'KOSPI' else limit
        target_stocks = get_top_stocks(mkt_name, current_limit)
        
        if target_stocks.empty: continue
            
        print(f"🔎 {mkt_name} {len(target_stocks)}개 종목 분석 중 (병렬 처리)...")
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(process_stock, row, mkt_name, market_type, today, prev_rank_map) for _, row in target_stocks.iterrows()]
            for future in as_completed(futures):
                result = future.result()
                if result: res.append(result)
                    
    if res:
        final_df = pd.DataFrame(res)
        
        # 종목코드 문자열 보정 (한국 종목 0 누락 방지)
        if market_type == 'KR':
            final_df['종목코드'] = final_df['종목코드'].astype(str).str.zfill(6)

        denom = (1 + final_df['1개월(%)'] / 100) + 1e-9
        final_df['3-1개월(%)'] = round(((1 + final_df['3개월(%)']/100) / denom - 1) * 100, 2)
        final_df['6-1개월(%)'] = round(((1 + final_df['6개월(%)']/100) / denom - 1) * 100, 2)
        final_df['12-1개월(%)'] = round(((1 + final_df['12개월(%)']/100) / denom - 1) * 100, 2)

        final_df = final_df.sort_values('모멘텀스코어', ascending=False)
        final_df.to_csv(file_path, index=False, encoding='utf-8-sig')
        print(f"✅ {name_tag} 데일리 업데이트 완료! (시가총액 데이터 포함됨)")

if __name__ == "__main__":
    # 💡 최우선 작업: 포트폴리오를 위한 전 종목 시가총액 마스터 파일 만들기
    update_krx_master()
    
    # 데이터 수집 순서: KR -> US -> SP500
    for m in ['KR', 'US', 'SP500']:
        try:
            run_daily(m)
        except Exception as e:
            print(f"🔥 {m} 실행 중 치명적 오류: {e}")
