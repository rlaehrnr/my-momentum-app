import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import os
import time

# 1. 기존 데이터를 보관소(archive_us)로 옮기고 수익률 채점하는 함수
def archive_and_score_us():
    file_path = 'momentum_data_us.csv'
    archive_dir = 'archive_us'
    
    if not os.path.exists(archive_dir):
        os.makedirs(archive_dir)
        
    if os.path.exists(file_path):
        try:
            df_old = pd.read_csv(file_path)
            last_date_str = df_old['기준일(월말)'].iloc[0]
            # 파일명에 쓸 연_월 추출 (예: 2026_02)
            year_month = datetime.strptime(last_date_str, '%Y-%m-%d').strftime('%Y_%m')
            
            today = datetime.today()
            forward_returns = []
            
            print(f"📊 {year_month} 미국 데이터 성적표 채점 시작...")
            
            for idx, row in df_old.iterrows():
                symbol = str(row['종목코드']).replace('.', '-')
                base_price = row['기준가']
                try:
                    # 현재 가격 가져와서 한 달 수익률 계산
                    df_now = fdr.DataReader(symbol, today - timedelta(days=7), today)
                    if not df_now.empty:
                        ret = round((df_now['Close'].iloc[-1] - base_price) / base_price * 100, 1)
                        forward_returns.append(ret)
                    else:
                        forward_returns.append(0.0)
                except:
                    forward_returns.append(0.0)
                
                if idx % 50 == 0: time.sleep(0.2) # 과부하 방지
            
            df_old['다음달수익률(%)'] = forward_returns
            # 보관소 폴더에 저장
            archive_file = os.path.join(archive_dir, f'momentum_us_{year_month}.csv')
            df_old.to_csv(archive_file, index=False)
            print(f"✅ {archive_file} 저장 완료!")
        except Exception as e:
            print(f"❌ 보관 처리 중 에러: {e}")

# 2. 전월 말일 기준일 구하기
def get_last_day_of_prev_month():
    today = datetime.today()
    first_day_of_this_month = today.replace(day=1)
    last_day_of_prev_month = first_day_of_this_month - timedelta(days=1)
    return last_day_of_prev_month.strftime('%Y-%m-%d')

# 3. 새로운 달의 모멘텀 데이터 수집 함수
def get_us_momentum():
    print("🚀 미국 시장 신규 데이터 수집 시작...")
    base_date = get_last_day_of_prev_month()
    
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
            symbol, name, market = str(row[sym_col]), str(row[name_col]), row['Market']
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
                    '기준일(월말)': base_date, '시장': market, '종목명': name, '종목코드': symbol, 
                    '기준가': round(curr, 2), '1개월(%)': round(r1, 1), '3개월(%)': round(r3, 1), 
                    '6개월(%)': round(r6, 1), '12개월(%)': round(r12, 1), '모멘텀스코어': round(score, 2), 
                    '다음달수익률(%)': 0.0
                })
            except: continue
            if i % 50 == 0: print(f"진행 중... {i}/300")
            
        if results:
            final_df = pd.DataFrame(results).sort_values('모멘텀스코어', ascending=False)
            final_df.to_csv('momentum_data_us.csv', index=False)
            print(f"✅ 미국 데이터 업데이트 완료! (기준일: {base_date})")
            
    except Exception as e:
        print(f"❌ 데이터 수집 에러: {e}")

if __name__ == "__main__":
    # 1. 보관 먼저 하고 (archive_us 폴더로 이동)
    archive_and_score_us()
    # 2. 새로 뽑기
    get_us_momentum()
