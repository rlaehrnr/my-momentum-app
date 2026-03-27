import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import os
import time

def get_last_day_of_prev_month():
    # 현재 날짜 기준 전월 말일 구하기
    today = datetime.today()
    first_day_of_this_month = today.replace(day=1)
    last_day_of_prev_month = first_day_of_this_month - timedelta(days=1)
    return last_day_of_prev_month.strftime('%Y-%m-%d')

def get_us_momentum():
    print("🚀 미국 시장 상위 300위 수집 시작...")
    
    # ⭐ 전월 말일 기준일 확정 (예: 3월에 돌리면 2월 28일)
    base_date = get_last_day_of_prev_month()
    print(f"📅 데이터 기준일: {base_date}")

    try:
        df_ny = fdr.StockListing('NYSE')
        df_nd = fdr.StockListing('NASDAQ')
        
        def get_col_name(df, target):
            found = [c for c in df.columns if target.lower() in c.lower()]
            return found[0] if found else None

        sym_col = get_col_name(df_ny, 'Symbol')
        name_col = get_col_name(df_ny, 'Name')

        cap_col = [c for c in df_ny.columns if 'market' in c.lower() and 'cap' in c.lower()]
        if cap_col:
            df_ny = df_ny.sort_values(cap_col[0], ascending=False).head(150)
            df_nd = df_nd.sort_values(cap_col[0], ascending=False).head(150)
        else:
            df_ny = df_ny.head(150)
            df_nd = df_nd.head(150)

        df_ny['Market'] = 'NYSE'
        df_nd['Market'] = 'NASDAQ'
        target_stocks = pd.concat([df_ny, df_nd])
        
        today = datetime.today()
        start_date = today - timedelta(days=450)
        results = []
        
        for i, (idx, row) in enumerate(target_stocks.iterrows()):
            symbol = str(row[sym_col])
            name = str(row[name_col])
            market = row['Market']
            
            try:
                fetch_symbol = symbol.replace('.', '-')
                df = fdr.DataReader(fetch_symbol, start_date, today)
                if len(df) < 100: continue
                
                curr = df['Close'].iloc[-1]
                
                def get_ret(m):
                    target = df.index[-1] - pd.DateOffset(months=m)
                    past = df[df.index <= target]
                    if past.empty: return 0.0
                    return (curr - past['Close'].iloc[-1]) / past['Close'].iloc[-1] * 100
                
                r1, r3, r6, r12 = get_ret(1), get_ret(3), get_ret(6), get_ret(12)
                score = (r1*-0.2) + (r3*0.8) + (r6*0.5) + (r12*0.2)
                
                results.append({
                    '기준일(월말)': base_date, # ⭐ 수정된 부분
                    '시장': market, '종목명': name, '종목코드': symbol, 
                    '기준가': round(curr, 2), '1개월(%)': round(r1, 1),
                    '3개월(%)': round(r3, 1), '6개월(%)': round(r6, 1), '12개월(%)': round(r12, 1),
                    '모멘텀스코어': round(score, 2), '다음달수익률(%)': 0.0
                })
            except: continue
            if i % 30 == 0: print(f"진행 중... {i}/300")
            
        if results:
            final_df = pd.DataFrame(results).sort_values('모멘텀스코어', ascending=False)
            final_df.to_csv('momentum_data_us.csv', index=False)
            print(f"✅ 총 {len(results)}개 종목 업데이트 완료!")
            
    except Exception as e:
        print(f"❌ 에러 발생: {e}")

if __name__ == "__main__":
    get_us_momentum()
