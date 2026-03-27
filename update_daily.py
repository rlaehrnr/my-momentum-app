import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import os

# 0. 데이터 저장용 폴더가 없으면 생성
if not os.path.exists('data'):
    os.makedirs('data')

# 헬퍼 함수: 시가총액 상위 종목 가져오기 (에러 방지용)
def get_top_stocks(market_code, limit=150):
    try:
        df = fdr.StockListing(market_code)
        # 시가총액 컬럼 후보들 (MarCap, MarketCap, Market Cap 등) 자동 검색
        cap_cols = [c for c in df.columns if 'market' in c.lower() and 'cap' in c.lower()]
        if not cap_cols:
            cap_cols = [c for c in df.columns if 'mar' in c.lower() and 'cap' in c.lower()]
        
        if cap_cols:
            return df.sort_values(cap_cols[0], ascending=False).head(limit)
        else:
            return df.head(limit)
    except Exception as e:
        print(f"⚠️ {market_code} 목록 수집 중 오류: {e}")
        return pd.DataFrame()

# ⭐ 날짜 로직: m개월 전의 '정확한' 월말 종가와 비교
def get_ref_day_ret(df, curr_price, m):
    today = datetime.today()
    # m=1 이면 이번 달 1일에서 하루를 빼서 '지난달 말일' 가격을 찾음
    first_day_of_target_month = today.replace(day=1) - pd.DateOffset(months=m-1)
    ref_date = first_day_of_target_month - timedelta(days=1)
    
    past = df[df.index <= ref_date]
    if past.empty: return 0.0
    return (curr_price - past['Close'].iloc[-1]) / past['Close'].iloc[-1] * 100

def run_daily_kr():
    print("🇰🇷 한국 데일리 데이터 수집 중 (data/ 폴더 저장)...")
    # 시총 상위 150개씩 총 300개
    df_ks = get_top_stocks('KOSPI', 150)
    df_kq = get_top_stocks('KOSDAQ', 150)
    df_ks['시장'], df_kq['시장'] = 'KOSPI', 'KOSDAQ'
    target = pd.concat([df_ks, df_kq])
    
    today = datetime.today()
    res = []
    
    for i, (_, row) in enumerate(target.iterrows()):
        code = row['Code'] if 'Code' in row else row['Symbol']
        name = row['Name']
        try:
            # 16개월치 데이터를 가져와서 넉넉하게 비교
            df = fdr.DataReader(code, today - pd.DateOffset(months=16), today)
            if df.empty: continue
            curr = df['Close'].iloc[-1]
            
            r1 = get_ref_day_ret(df, curr, 1)
            r3 = get_ref_day_ret(df, curr, 3)
            r6 = get_ref_day_ret(df, curr, 6)
            r12 = get_ref_day_ret(df, curr, 12)
            
            score = (r1*-0.2) + (r3*0.8) + (r6*0.5) + (r12*0.2)
            
            res.append({
                '기준일': today.strftime('%Y-%m-%d'),
                '시장': row['시장'], '종목명': name, '종목코드': code, 
                '기준가': int(curr),
                '1개월(%)': round(r1, 1), '3개월(%)': round(r3, 1), 
                '6개월(%)': round(r6, 1), '12개월(%)': round(r12, 1),
                '모멘텀스코어': round(score, 1)
            })
        except: continue
        if i % 50 == 0: print(f"진행 중... {i}/300")
    
    if res:
        final_df = pd.DataFrame(res).sort_values('모멘텀스코어', ascending=False)
        # ⭐ 경로 수정: data/ 폴더 안에 저장
        final_df.to_csv('data/momentum_data_daily.csv', index=False)
        print("✅ 한국 데일리 업데이트 완료!")

def run_daily_us():
    print("🇺🇸 미국 데일리 데이터 수집 중 (data/ 폴더 저장)...")
    df_ny = get_top_stocks('NYSE', 150)
    df_nd = get_top_stocks('NASDAQ', 150)
    df_ny['시장'], df_nd['시장'] = 'NYSE', 'NASDAQ'
    target = pd.concat([df_ny, df_nd])
    
    today = datetime.today()
    res = []
    
    for i, (_, row) in enumerate(target.iterrows()):
        symbol = row['Symbol']
        name = row['Name']
        try:
            fetch_symbol = symbol.replace('.', '-')
            df = fdr.DataReader(fetch_symbol, today - pd.DateOffset(months=16), today)
            if df.empty: continue
            curr = df['Close'].iloc[-1]
            
            r1 = get_ref_day_ret(df, curr, 1)
            r3 = get_ref_day_ret(df, curr, 3)
            r6 = get_ref_day_ret(df, curr, 6)
            r12 = get_ref_day_ret(df, curr, 12)
            
            score = (r1*-0.2) + (r3*0.8) + (r6*0.5) + (r12*0.2)
            
            res.append({
                '기준일': today.strftime('%Y-%m-%d'),
                '시장': row['시장'], '종목명': name, '종목코드': symbol, 
                '기준가': round(curr, 2),
                '1개월(%)': round(r1, 1), '3개월(%)': round(r3, 1), 
                '6개월(%)': round(r6, 1), '12개월(%)': round(r12, 1),
                '모멘텀스코어': round(score, 1)
            })
        except: continue
        if i % 50 == 0: print(f"진행 중... {i}/300")
        
    if res:
        final_df = pd.DataFrame(res).sort_values('모멘텀스코어', ascending=False)
        # ⭐ 경로 수정: data/ 폴더 안에 저장
        final_df.to_csv('data/momentum_data_daily_us.csv', index=False)
        print("✅ 미국 데일리 업데이트 완료!")

if __name__ == "__main__":
    run_daily_kr()
    run_daily_us()
