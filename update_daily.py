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
        # 💡 [필살기] KOSPI, KOSDAQ 개별 조회 대신 '전체 시가총액 전용 순위' 데이터를 불러와서 필터링
        if market in ['KOSPI', 'KOSDAQ']:
            df = fdr.StockListing('KRX-MARCAP') # KRX 전체 시가총액 순위 데이터
            if not df.empty:
                # 'Market' 컬럼에서 KOSPI 또는 KOSDAQ만 걸러내기
                mkt_col = [c for c in df.columns if 'market' in c.lower() or '시장' in c]
                if mkt_col:
                    target_mkt_col = mkt_col[0]
                    # MarketId(STK 등)가 섞일 수 있으니 정확한 Market 컬럼을 우선 찾음
                    exact_mkt = [c for c in mkt_col if c.lower() == 'market' or c == '시장구분']
                    if exact_mkt: target_mkt_col = exact_mkt[0]
                    
                    df = df[df[target_mkt_col].astype(str).str.upper() == market.upper()]
            else:
                df = fdr.StockListing(market) # 만약 실패 시 기존 방식으로 우회
        else:
            df = fdr.StockListing(market)

        if df.empty: return pd.DataFrame()
        
        if market == 'S&P500': 
            return df.drop_duplicates(subset=['Symbol']).head(limit)

        # 시가총액 컬럼 찾기 및 내림차순 정렬
        cap_col = [c for c in df.columns if '시가총액' in c or ('mar' in c.lower() and 'cap' in c.lower())]
        
        if cap_col:
            target_col = cap_col[0]
            # 콤마 제거 및 숫자로 강제 변환
            df[target_col] = pd.to_numeric(df[target_col].astype(str).str.replace(',', ''), errors='coerce')
            
            # 🚨 시가총액이 전부 0이나 빈 값인지 검증
            if df[target_col].sum() == 0:
                print(f"🚨 [경고] {market} 시가총액 데이터가 API 서버에서 0으로 넘어오고 있습니다!")
            else:
                df = df.sort_values(target_col, ascending=False)
        else:
            print(f"⚠️ {market} 시가총액 컬럼을 찾을 수 없습니다. 컬럼명: {df.columns.tolist()}")

        # 우선주 및 스팩주 필터링 (가장 안전한 방법)
        if market in ['KOSPI', 'KOSDAQ']:
            name_col = [c for c in df.columns if 'name' in c.lower() or '종목명' in c]
            if name_col:
                col = name_col[0]
                df = df[~df[col].str.endswith(('우', '우B', '우C'))]
                df = df[~df[col].str.contains('스팩')]
        
        result_df = df.head(limit)
        
        # ✅ [눈으로 확인하는 검증 로그] 정상이라면 '삼성전자', 'SK하이닉스'가 출력되어야 함
        if market in ['KOSPI', 'KOSDAQ']:
            name_col = [c for c in df.columns if 'name' in c.lower() or '종목명' in c]
            if name_col:
                top_3 = result_df[name_col[0]].tolist()[:3]
                print(f"✅ {market} 시총 상위 3개 확인: {top_3}")

        return result_df

    except Exception as e:
        print(f"❌ {market} 리스트 가져오기 실패: {e}")
        return pd.DataFrame()

def process_stock(row, mkt_name, market_type, today):
    """개별 종목의 데이터를 다운로드하고 모멘텀 스코어를 계산하는 함수 (병렬 처리용)"""
    try:
        code = row['Code'] if 'Code' in row else row['Symbol']
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
        score = round((r1*-0.2) + (r3*0.8) + (r6*0.5) + (r12*0.2), 1)
        
        display_mkt = mkt_name
        if market_type == 'SP500':
            display_mkt = row.get('Exchange', 'NYSE')

        return {
            '기준일': last_date,
            '시장': display_mkt,
            '종목명': row['Name'], 
            '종목코드': code, 
            '기준가': round(curr_price, 2),
            '전일거래량': curr_volume,
            '1개월(%)': round(r1, 1), 
            '3개월(%)': round(r3, 1), 
            '6개월(%)': round(r6, 1),
            '12개월(%)': round(r12, 1), 
            '모멘텀스코어': score
        }
    except Exception:
        return None

def run_daily(market_type='KR'):
    """시장별로 데일리 데이터를 수집하는 메인 함수"""
    if market_type == 'KR':
        name_tag, file_path, market_list, limit = "한국", 'data/momentum_data_daily.csv', ['KOSPI', 'KOSDAQ'], 150
    elif market_type == 'US':
        name_tag, file_path, market_list, limit = "미국(시총상위)", 'data/momentum_data_daily_us.csv', ['NYSE', 'NASDAQ'], 150
    elif market_type == 'SP500':
        name_tag, file_path, market_list, limit = "S&P 500", 'data/momentum_data_daily_sp500.csv', ['S&P500'], 505

    today = datetime.today()
    print(f"🕒 {name_tag} 데일리 데이터 수집 시작... (기준일: {today.strftime('%Y-%m-%d')})")
    res = []

    for mkt_name in market_list:
        # 💡 코스피는 200위, 그 외는 150위(또는 505위)로 제한 설정
        current_limit = 200 if mkt_name == 'KOSPI' else limit
        target_stocks = get_top_stocks(mkt_name, current_limit)
        
        if target_stocks.empty:
            print(f"⚠️ {mkt_name} 종목 리스트가 비어있습니다. 건너뜁니다.")
            continue
            
        print(f"🔎 {mkt_name} 총 {len(target_stocks)}개 종목 분석 중 (🚀 속도 향상 병렬 처리 적용)...")
        
        # 💡 일꾼(스레드) 10개를 동원해 10개 종목씩 동시에 다운로드 및 계산 진행
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(process_stock, row, mkt_name, market_type, today) for _, row in target_stocks.iterrows()]
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    res.append(result)
                    
        time.sleep(1) # 시장(거래소) 하나가 끝날 때마다 아주 잠시 휴식

    if res:
        final_df = pd.DataFrame(res).sort_values('모멘텀스코어', ascending=False)
        final_df.to_csv(file_path, index=False, encoding='utf-8-sig')
        print(f"✅ {name_tag} 완료! (최종 수집: {len(res)}개 종목)")
    else:
        print(f"❌ {name_tag} 수집된 데이터가 없습니다.")

if __name__ == "__main__":
    # 한국 -> 미국 -> S&P500 순서대로 실행
    for m_type in ['KR', 'US', 'SP500']:
        try:
            run_daily(m_type)
        except Exception as e:
            print(f"🔥 {m_type} 실행 중 치명적 오류: {e}")
