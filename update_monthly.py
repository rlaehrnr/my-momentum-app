import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import os
import time

# 1. 폴더 생성 (더 깔끔하게 정리)
folders = ['data', 'archive', 'archive_us', 'archive_sp500']
for d in folders:
    if not os.path.exists(d): os.makedirs(d)

def get_target_ref_date():
    """실행 시점 기준 '전월 말일' 날짜 반환"""
    today = datetime.today()
    # 예: 오늘이 4월 1일이면 3월 31일 반환
    return (today.replace(day=1) - timedelta(days=1)).strftime('%Y-%m-%d')

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

def run_monthly(market_type='KR'):
    # 초기 설정
    mkt_map = {} # 변수 미정의 에러 방지용 초기화
    
    if market_type == 'KR':
        name_tag, file_path, folder, prefix = "한국", 'data/momentum_data.csv', 'archive', 'momentum_'
        market_list, limit = ['KOSPI', 'KOSDAQ'], 150
    elif market_type == 'US':
        name_tag, file_path, folder, prefix = "미국(시총상위)", 'data/momentum_data_us.csv', 'archive_us', 'momentum_us_'
        market_list, limit = ['NYSE', 'NASDAQ'], 150
    elif market_type == 'SP500':
        name_tag, file_path, folder, prefix = "S&P 500", 'data/momentum_data_sp500.csv', 'archive_sp500', 'momentum_sp500_'
        market_list, limit = ['S&P500'], 505
        # 💡 [최적화] S&P 500 전용 거래소 매핑
        try:
            print("🌐 S&P 500 거래소 매핑 데이터 로드 중...")
            nyse = fdr.StockListing('NYSE')[['Symbol']]
            nasdaq = fdr.StockListing('NASDAQ')[['Symbol']]
            mkt_map = {s: 'NYSE' for s in nyse['Symbol']}
            mkt_map.update({s: 'NASDAQ' for s in nasdaq['Symbol']})
        except: print("⚠️ 거래소 매핑 실패 (NYSE 기본값 사용)")

    target_date_str = get_target_ref_date()
    target_date_dt = pd.to_datetime(target_date_str)
    print(f"\n🚀 {name_tag} 월말 데이터 업데이트 시작 (기준일: {target_date_str})")

    # --- 1. 아카이브 보관 로직 (지난달 성적표 작성) ---
    if os.path.exists(file_path):
        df_old = pd.read_csv(file_path)
        existing_date = str(df_old['기준일(월말)'].iloc[0])
        
        if existing_date != target_date_str:
            print(f"📦 기존 데이터({existing_date}) 성적표 작성 및 아카이브 이동 중...")
            forward_returns = []
            today = datetime.today()
            
            for i, row in df_old.iterrows():
                try:
                    # 티커 세척 및 최신가 수집
                    code = str(row['종목코드']).split('.')[0].replace('.', '-')
                    df_now = fdr.DataReader(code, today - timedelta(days=10), today)
                    curr_p = df_now['Close'].iloc[-1]
                    ret = round((curr_p - row['기준가']) / row['기준가'] * 100, 2)
                    forward_returns.append(ret)
                except: forward_returns.append(0.0)
            
            df_old['다음달수익률(%)'] = forward_returns
            ym = (datetime.strptime(existing_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y_%m')
            archive_name = f'{folder}/{prefix}{ym}.csv'
            df_old.to_csv(archive_name, index=False, encoding='utf-8-sig')
            print(f"✅ 아카이브 완료: {archive_name}")

    
    # --- 2. 신규 월말 데이터 수집 ---
    res = []
    for mkt_name in market_list:
        # 💡 [핵심 수정] KOSPI는 200위까지, 그 외(KOSDAQ 등)는 기존 limit(150) 적용
        current_limit = 200 if mkt_name == 'KOSPI' else limit
        target_stocks = get_top_stocks(mkt_name, current_limit)
        print(f"📊 {mkt_name} {len(target_stocks)}개 종목 분석 시작...")
        
        for i, row in target_stocks.iterrows():
            try:
                code = row['Code'] if 'Code' in row else row['Symbol']
                # 데이터 로드
                df = fdr.DataReader(code.replace('.', '-'), target_date_dt - pd.DateOffset(months=16), target_date_dt)
                if df.empty: continue
                
                base_price = df['Close'].iloc[-1]
                
                def get_ret(m):
                    ref = (target_date_dt.replace(day=1) - pd.DateOffset(months=m-1)) - timedelta(days=1)
                    past = df[df.index <= ref]
                    return (base_price - past['Close'].iloc[-1]) / past['Close'].iloc[-1] * 100 if not past.empty else 0.0
                
                r1, r3, r6, r12 = get_ret(1), get_ret(3), get_ret(6), get_ret(12)
                score = round((r1*-0.2) + (r3*0.8) + (r6*0.5) + (r12*0.2), 2)
                
                # 시장 이름 결정
                display_mkt = mkt_map.get(code, 'NYSE') if market_type == 'SP500' else mkt_name

                res.append({
                    '기준일(월말)': target_date_str, '시장': display_mkt,
                    '종목명': row['Name'], '종목코드': code, '기준가': round(base_price, 2),
                    '1개월(%)': round(r1, 2), '3개월(%)': round(r3, 2), '6개월(%)': round(r6, 2),
                    '12개월(%)': round(r12, 2), '모멘텀스코어': score, '다음달수익률(%)': 0.0
                })
                time.sleep(0.05) # 서버 부하 방지
            except: continue
    
    if res:
        pd.DataFrame(res).sort_values('모멘텀스코어', ascending=False).to_csv(file_path, index=False, encoding='utf-8-sig')
        print(f"✨ {name_tag} 월말 업데이트 완료!")

if __name__ == "__main__":
    # 순차적 실행
    for m in ['KR', 'US', 'SP500']:
        run_monthly(m)
