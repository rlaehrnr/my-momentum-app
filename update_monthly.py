import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import os
import time

# 0. 필요한 폴더 자동 생성
for d in ['data', 'archive', 'archive_us']:
    if not os.path.exists(d):
        os.makedirs(d)

# 헬퍼: 시가총액 상위 종목 수집 (에러 방지용)
def get_top_stocks(market, limit=150):
    try:
        df = fdr.StockListing(market)
        cap_col = [c for c in df.columns if 'market' in c.lower() and 'cap' in c.lower()]
        if not cap_col: 
            cap_col = [c for c in df.columns if 'mar' in c.lower() and 'cap' in c.lower()]
        return df.sort_values(cap_col[0], ascending=False).head(limit) if cap_col else df.head(limit)
    except:
        return pd.DataFrame()

# 헬퍼: 현재 시점에서 '마땅히 있어야 할' 전월 말일 구하기
def get_target_ref_date():
    today = datetime.today()
    # 오늘이 4월 1일이면 3월 31일을, 오늘이 3월 27일이면 2월 28일을 반환
    return (today.replace(day=1) - timedelta(days=1)).strftime('%Y-%m-%d')

def run_monthly(market_type='KR'):
    name_tag = "한국" if market_type == 'KR' else "미국"
    file_path = f'data/momentum_data{"_us" if market_type=="US" else ""}.csv'
    target_date = get_target_ref_date()
    
    print(f"🔍 {name_tag} 월말 업데이트 체크 시작...")

    # 1. 보관 및 채점 로직 (달이 바뀌었을 때만 실행)
    if os.path.exists(file_path):
        df_old = pd.read_csv(file_path)
        existing_date = str(df_old['기준일(월말)'].iloc[0])
        
        # ⭐ [안전장치] 기존 파일의 기준일이 '마땅히 있어야 할 날짜'와 다를 때만 보관 진행
        if existing_date != target_date:
            print(f"📢 달이 바뀌었습니다! {existing_date} 데이터를 성적표와 함께 보관소로 이동합니다.")
            
            # 투자 월(Investment Month) 계산: 기준일 + 1일 (예: 2/28 -> 3월 기록)
            base_dt_obj = datetime.strptime(existing_date, '%Y-%m-%d')
            investment_month = base_dt_obj + timedelta(days=1)
            ym = investment_month.strftime('%Y_%m')
            
            # --- 실시간 채점 구간 ---
            print(f"📊 {ym} 성적표 채점 중 (현재 주가와 비교)...")
            forward_returns = []
            today = datetime.today()
            
            for idx, row in df_old.iterrows():
                code = str(row['종목코드']).replace('.', '-')
                base_price = row['기준가']
                try:
                    # 보관하는 시점의 최신 종가(즉, 전월 말 종가)를 가져옴
                    df_now = fdr.DataReader(code, today - timedelta(days=7), today)
                    if not df_now.empty:
                        curr_price = df_now['Close'].iloc[-1]
                        ret = round((curr_price - base_price) / base_price * 100, 1)
                        forward_returns.append(ret)
                    else: forward_returns.append(0.0)
                except: forward_returns.append(0.0)
                if idx % 30 == 0: time.sleep(0.05)
            
            df_old['다음달수익률(%)'] = forward_returns
            
            # 보관 파일 저장
            folder = 'archive_us' if market_type == 'US' else 'archive'
            prefix = 'us_' if market_type == 'US' else ''
            archive_file = f'{folder}/momentum_{prefix}{ym}.csv'
            df_old.to_csv(archive_file, index=False)
            print(f"✅ {archive_file} 보관 완료.")
        else:
            print(f"✅ 현재 {target_date} 기준 데이터가 최신입니다. 보관을 건너뜁니다.")
            return # 달이 안 바뀌었으면 여기서 종료

    # 2. 신규 데이터 수집 (달이 바뀌었을 때만 이 아래가 실행됨)
    print(f"🚀 {name_tag} 새로운 {target_date} 기준 데이터 수집 시작...")
    markets = ['KOSPI', 'KOSDAQ'] if market_type == 'KR' else ['NYSE', 'NASDAQ']
    target_stocks = pd.concat([get_top_stocks(m) for m in markets])
    
    today = datetime.today()
    res = []
    for i, (_, row) in enumerate(target_stocks.iterrows()):
        try:
            code = row['Code'] if 'Code' in row else row['Symbol']
            # 신규 데이터 수집 시에도 '정확한 월말' 수익률 계산
            df = fdr.DataReader(code.replace('.', '-'), today - pd.DateOffset(months=16), today)
            if df.empty: continue
            curr = df['Close'].iloc[-1]
            
            def get_ret(m):
                # 오늘 시점 기준 m개월 전의 정확한 월말일
                ref = (today.replace(day=1) - pd.DateOffset(months=m-1)) - timedelta(days=1)
                p = df[df.index <= ref]
                return (curr - p['Close'].iloc[-1]) / p['Close'].iloc[-1] * 100 if not p.empty else 0.0
            
            r1, r3, r6, r12 = get_ret(1), get_ret(3), get_ret(6), get_ret(12)
            score = round((r1*-0.2) + (r3*0.8) + (r6*0.5) + (r12*0.2), 1)
            res.append({
                '기준일(월말)': target_date, '시장': row.get('Market', market_type), '종목명': row['Name'], '종목코드': code, 
                '기준가': curr, '1개월(%)': round(r1, 1), '3개월(%)': round(r3, 1), 
                '6개월(%)': round(r6, 1), '12개월(%)': round(r12, 1), '모멘텀스코어': score, '다음달수익률(%)': 0.0
            })
        except: continue
    
    if res:
        pd.DataFrame(res).sort_values('모멘텀스코어', ascending=False).to_csv(file_path, index=False)
        print(f"✨ {name_tag} 새로운 월간 데이터 갱신 완료!")

if __name__ == "__main__":
    run_monthly('KR')
    run_monthly('US')
