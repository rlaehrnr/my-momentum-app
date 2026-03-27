import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import os
import time

def archive_and_score_us():
    file_path = 'momentum_data_us.csv'
    archive_dir = 'archive_us'
    if not os.path.exists(archive_dir): os.makedirs(archive_dir)
    if os.path.exists(file_path):
        try:
            df_old = pd.read_csv(file_path)
            last_date_str = df_old['기준일(월말)'].iloc[0]
            year_month = datetime.strptime(last_date_str, '%Y-%m-%d').strftime('%Y_%m')
            today = datetime.today()
            forward_returns = []
            for idx, row in df_old.iterrows():
                symbol = str(row['종목코드'])
                base_price = row['기준가']
                try:
                    # 미국 주식은 . 형식인 경우가 있어 수정 (예: BRK.B)
                    symbol = symbol.replace('.', '-')
                    df_now = fdr.DataReader(symbol, today - timedelta(days=7), today)
                    if not df_now.empty:
                        ret = round((df_now['Close'].iloc[-1] - base_price) / base_price * 100, 2)
                        forward_returns.append(ret)
                    else: forward_returns.append(0.0)
                except: forward_returns.append(0.0)
                if idx % 50 == 0: time.sleep(0.5)
            df_old['다음달수익률(%)'] = forward_returns
            df_old.to_csv(os.path.join(archive_dir, f'momentum_us_{year_month}.csv'), index=False)
            print(f"✅ 미국 {year_month} 성적표 채점 완료!")
        except: pass

def get_us_momentum():
    print("🚀 미국 시장(NYSE/NASDAQ) 상위 300위 계산 시작...")
    
    # 데이터 가져오기
    df_ny = fdr.StockListing('NYSE')
    df_nd = fdr.StockListing('NASDAQ')
    
    # ⭐ [핵심 수정] 시가총액 컬럼 이름 찾기 (MarketCap 혹은 Market Cap)
    def sort_by_cap(df, market_name):
        # 대소문자 구분 없이 'market'과 'cap'이 들어간 컬럼 찾기
        cap_col = [c for c in df.columns if 'market' in c.lower() and 'cap' in c.lower()]
        if cap_col:
            return df.sort_values(cap_col[0], ascending=False).head(150)
        else:
            # 못 찾으면 그냥 상위 150개 가져오기
            return df.head(150)

    df_ny_top = sort_by_cap(df_ny, 'NYSE')
    df_nd_top = sort_by_cap(df_nd, 'NASDAQ')
    
    df_ny_top['Market'] = 'NYSE'
    df_nd_top['Market'] = 'NASDAQ'
    target_stocks = pd.concat([df_ny_top, df_nd_top])
    
    today = datetime.today()
    start_date = today - timedelta(days=450)
    results = []
    
    for i, (idx, row) in enumerate(target_stocks.iterrows()):
        symbol, name, market = row['Symbol'], row['Name'], row['Market']
        try:
            # 티커 기호 정제 (예: BRK.B -> BRK-B)
            fetch_symbol = symbol.replace('.', '-')
            df = fdr.DataReader(fetch_symbol, start_date, today)
            if len(df) < 150: continue
            
            curr = df['Close'].iloc[-1]
            
            def get_ret(m):
                target = df.index[-1] - pd.DateOffset(months=m)
                past = df[df.index <= target]
                if past.empty: return 0.0
                return (curr - past['Close'].iloc[-1]) / past['Close'].iloc[-1] * 100
            
            r1, r3, r6, r12 = get_ret(1), get_ret(3), get_ret(6), get_ret(12)
            score = (r1*-0.2) + (r3*0.8) + (r6*0.5) + (r12*0.2)
            
            results.append({
                '기준일(월말)': today.strftime('%Y-%m-%d'), '시장': market, '종목명': name,
                '종목코드': symbol, '기준가': round(curr, 2), '1개월(%)': round(r1, 2),
                '3개월(%)': round(r3, 2), '6개월(%)': round(r6, 2), '12개월(%)': round(r12, 2),
                '모멘텀스코어': round(score, 2), '다음달수익률(%)': None
            })
        except: pass
        if i % 50 == 0: print(f"진행 중... ({i}/300)")
    
    if results:
        final_df = pd.DataFrame(results).sort_values('모멘텀스코어', ascending=False)
        final_df.to_csv('momentum_data_us.csv', index=False)
        print("✅ 미국 모멘텀 데이터 업데이트 완료!")

if __name__ == "__main__":
    archive_and_score_us()
    get_us_momentum()
