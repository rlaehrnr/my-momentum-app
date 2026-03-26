import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime
import os

# 1. 기존 데이터(지난달 명단) 채점 및 아카이브 저장
def archive_last_month():
    file_path = 'momentum_data.csv'
    archive_dir = 'archive'
    if not os.path.exists(archive_dir):
        os.makedirs(archive_dir)

    if os.path.exists(file_path):
        try:
            df_old = pd.read_csv(file_path, dtype={'종목코드': str})
            # 파일 안에 기록된 기준일(예: 2026-02-28) 가져오기
            last_base_date = df_old['기준일(월말)'].iloc[0]
            year_month = datetime.strptime(last_base_date, '%Y-%m-%d').strftime('%Y_%m')
            
            print(f"📊 {last_base_date} 명단의 한 달 수익률을 채점하여 보관함으로 보냅니다...")

            today = datetime.today()
            forward_returns = []
            
            for idx, row in df_old.iterrows():
                code = str(row['종목코드']).zfill(6)
                base_price = row['기준가']
                try:
                    # 현재(한 달 뒤) 주가 가져오기
                    df_now = fdr.DataReader(code, today - pd.Timedelta(days=7), today)
                    if not df_now.empty:
                        curr_price = df_now['Close'].iloc[-1]
                        ret = round((curr_price - base_price) / base_price * 100, 2)
                        forward_returns.append(ret)
                    else:
                        forward_returns.append(0.0)
                except:
                    forward_returns.append(0.0)
            
            df_old['다음달수익률(%)'] = forward_returns
            # archive/momentum_2026_02.csv 형식으로 저장
            archive_path = os.path.join(archive_dir, f'momentum_{year_month}.csv')
            df_old.to_csv(archive_path, index=False)
            print(f"✅ 보관 완료: {archive_path}")
        except Exception as e:
            print(f"❌ 아카이브 과정 중 오류: {e}")

# 2. 새로운 이번 달 모멘텀 데이터 생성
def update_current_momentum():
    print("🚀 이번 달(새 기준일) 모멘텀 데이터를 새로 계산합니다...")
    # (이 부분은 기존에 작성했던 300위 계산 코드를 그대로 넣으시면 됩니다.)
    # 여기에 fdr.StockListing('KRX') 부터 momentum_data.csv 저장까지의 기존 로직 포함
    
    # ... [기존 계산 로직 생략 - 실제 파일에는 기존 코드를 이어서 넣으세요] ...
    # 마지막에 df.to_csv('momentum_data.csv', index=False) 로 마무리

if __name__ == "__main__":
    # 순서가 중요합니다!
    archive_last_month()     # 1. 옛날 데이터 채점해서 창고에 넣고
    update_current_momentum() # 2. 새 데이터로 메인 화면 갈아끼우기
