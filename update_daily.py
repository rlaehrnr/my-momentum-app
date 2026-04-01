import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import os
import time

# 폴더 생성
if not os.path.exists('data'): os.makedirs('data')

def get_top_stocks(market, limit=150):
    try:
        df = fdr.StockListing(market)
        if df.empty: return pd.DataFrame()

        if market == 'S&P500': 
            return df.drop_duplicates(subset=['Symbol']).head(limit)
        
        # 💡 [수정] 한글 '시가총액' 컬럼 추가 및 찾기
        cap_col = [c for c in df.columns if '시가총액' in c or ('mar' in c.lower() and 'cap' in c.lower())]
        
        if cap_col:
            target_col = cap_col[0]
            # 💡 [수정] 시가총액 콤마 제거 후 숫자로 변환하여 내림차순 정렬
            df[target_col] = pd.to_numeric(df[target_col].astype(str).str.replace(',', ''), errors='coerce')
            df = df.sort_values(target_col, ascending=False)
        else:
            print(f"⚠️ {market} 시가총액 컬럼을 찾을 수 없습니다. (알파벳 순 정렬됨)")
            
        # 💡 [추가] KOSPI, KOSDAQ인 경우 우선주 및 스팩주 필터링
        if market in ['KOSPI', 'KOSDAQ']:
            name_col = [c for c in df.columns if 'name' in c.lower() or '종목명' in c]
            if name_col:
                col = name_col[0]
                df = df[~df[col].str.endswith(('우', '우B', '우C'))]
                df = df[~df[col].str.contains('스팩')]

        return df.head(limit)
    except Exception as e:
        print(f"❌ {market} 리스트 가져오기 실패: {e}")
        return pd.DataFrame()

def run_daily(market_type='KR'):
    if market_type == 'KR':
        name_tag, file_path, market_list, limit = "한국", 'data/momentum_data_daily.csv', ['KOSPI', 'KOSDAQ'], 150
        mkt_map = {}
    elif market_type == 'US':
        name_tag, file_path, market_list, limit = "미국(시총상위)", 'data/momentum_data_daily_us.csv', ['NYSE', 'NASDAQ'], 150
        mkt_map = {}
    elif market_type == 'SP500':
        name_tag, file_path, market_list, limit = "S&P 500", 'data/momentum_data_daily_sp500.csv', ['S&P500'], 505
        # 💡 [최적화] 매번 전체 리스트를 받지 않고 빈 딕셔너리로 시작 (필요 시에만 조회)
        mkt_map = {} 

    today = datetime.today()
    print(f"🕒 {name_tag} 데일리 데이터 수집 시작... (기준일: {today.strftime('%Y-%m-%d')})")
    res = []

    for mkt_name in market_list:
        # 💡 [핵심 수정] 코스피는 200위, 그 외(코스닥, 미국 등)는 기본 limit(150 등) 적용
        current_limit = 200 if mkt_name == 'KOSPI' else limit
        target_stocks = get_top_stocks(mkt_name, current_limit)
        
        if target_stocks.empty:
            print(f"⚠️ {mkt_name} 종목 리스트가 비어있습니다. 건너뜁니다.")
            continue
            
        print(f"🔎 {mkt_name} 총 {len(target_stocks)}개 종목 분석 중...")
        
        for i, row in target_stocks.iterrows():
            try:
                code = row['Code'] if 'Code' in row else row['Symbol']
                # 데이터 로드 (최근 16개월)
                # 💡 나스닥 종목은 티커 뒤에 .O, NYSE는 .N 등이 붙는 경우가 있어 세척
                clean_code = code.split('.')[0].replace('.', '-')
                
                df = fdr.DataReader(clean_code, today - pd.DateOffset(months=16), today)
                if df.empty: continue
                
                curr_price = df['Close'].iloc[-1]
                curr_volume = int(df['Volume'].iloc[-1]) if 'Volume' in df.columns else 0
                
                # 데이터 기준일 확인 (오늘 날짜와 데이터 마지막 날짜가 너무 다르면 경고)
                last_date = df.index[-1].strftime('%Y-%m-%d')
                
                def get_ret(m):
                    ref = (today.replace(day=1) - pd.DateOffset(months=m-1)) - timedelta(days=1)
                    past = df[df.index <= ref]
                    if past.empty: return 0.0
                    return (curr_price - past['Close'].iloc[-1]) / past['Close'].iloc[-1] * 100
                
                r1, r3, r6, r12 = get_ret(1), get_ret(3), get_ret(6), get_ret(12)
                score = round((r1*-0.2) + (r3*0.8) + (r6*0.5) + (r12*0.2), 1)
                
                display_mkt = mkt_name
                # S&P500의 경우 데이터프레임의 'Exchange' 컬럼 활용 (없으면 NYSE 기본)
                if market_type == 'SP500':
                    display_mkt = row.get('Exchange', 'NYSE')

                res.append({
                    '기준일': last_date, # 💡 실제 데이터의 마지막 날짜를 기록
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
                })
                
                # 💡 너무 빠른 요청으로 인한 차단 방지 (0.05초 대기)
                time.sleep(0.05)
                
            except Exception as e:
                # 에러 발생 시 로그 출력
                if i % 50 == 0: print(f"  - {code} 수집 중 오류 발생: {e}")
                continue
            
    if res:
        final_df = pd.DataFrame(res).sort_values('모멘텀스코어', ascending=False)
        final_df.to_csv(file_path, index=False, encoding='utf-8-sig')
        print(f"✅ {name_tag} 완료! (최종 수집: {len(res)}개 종목)")
    else:
        print(f"❌ {name_tag} 수집된 데이터가 없습니다.")

if __name__ == "__main__":
    # 실행 순서 조정 및 에러 시 중단 방지
    for m_type in ['KR', 'US', 'SP500']:
        try:
            run_daily(m_type)
        except Exception as e:
            print(f"🔥 {m_type} 실행 중 치명적 오류: {e}")
