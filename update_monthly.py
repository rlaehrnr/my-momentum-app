import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# 1. 폴더 생성
folders = ['data', 'archive', 'archive_us', 'archive_sp500']
for d in folders:
    if not os.path.exists(d): os.makedirs(d)

def get_target_ref_date():
    """실행 시점 기준 '전월 말일' 날짜 반환"""
    today = datetime.today()
    return (today.replace(day=1) - timedelta(days=1)).strftime('%Y-%m-%d')

def get_top_stocks(market, limit=150):
    """시가총액 상위 종목 추출 (미국 ADR 및 특수 티커 대응 강화)"""
    try:
        if market in ['KOSPI', 'KOSDAQ']:
            df = fdr.StockListing('KRX')
            if df.empty: df = fdr.StockListing(market)
            else:
                mkt_col = [c for c in df.columns if 'market' in c.lower() or '시장' in c][0]
                df = df[df[mkt_col].astype(str).str.upper().str.contains(market.upper())]
        else:
            df = fdr.StockListing(market)

        if df.empty: return pd.DataFrame()
        if market == 'S&P500': return df.drop_duplicates(subset=['Symbol']).head(limit)

        cap_col = [c for c in df.columns if '시가총액' in c or ('mar' in c.lower() and 'cap' in c.lower())]
        if cap_col:
            target_col = cap_col[0]
            # 숫자와 마침표만 추출
            df[target_col] = pd.to_numeric(df[target_col].astype(str).str.replace(r'[^0-9.]', '', regex=True), errors='coerce')
            df = df.sort_values(target_col, ascending=False)

        if market in ['KOSPI', 'KOSDAQ']:
            name_col = [c for c in df.columns if 'name' in c.lower() or '종목명' in c]
            if name_col:
                col = name_col[0]
                df = df[~df[col].astype(str).str.endswith(('우', '우B', '우C'))]
                df = df[~df[col].astype(str).str.contains('스팩')]
        
        # 미국 시장 티커 중복 제거
        symbol_col = 'Symbol' if 'Symbol' in df.columns else 'Code'
        if symbol_col in df.columns:
            df = df.drop_duplicates(subset=[symbol_col])
            
        return df.head(limit)
    except Exception as e:
        print(f"❌ {market} 리스트 가져오기 실패: {e}")
        return pd.DataFrame()

def process_monthly_stock(row, mkt_name, market_type, target_date_dt, target_date_str, mkt_map, prev_rank_map):
    try:
        code = str(row.get('Code', row.get('Symbol', '')))
        
        # 미국/S&P500 티커 정제
        if market_type in ['US', 'SP500']:
            clean_code = code.replace('.', '-')
        else:
            clean_code = code.split('.')[0]
        
        df = fdr.DataReader(clean_code, target_date_dt - pd.DateOffset(months=16), target_date_dt)
        if df.empty: return None
        
        base_price = df['Close'].iloc[-1]
        
        def get_ret(m):
            ref = (target_date_dt.replace(day=1) - pd.DateOffset(months=m-1)) - timedelta(days=1)
            past = df[df.index <= ref]
            return (base_price - past['Close'].iloc[-1]) / past['Close'].iloc[-1] * 100 if not past.empty else 0.0
        
        r1, r3, r6, r12 = get_ret(1), get_ret(3), get_ret(6), get_ret(12)
        
        score = round((r1 * -0.5) + (r3 * 0.8) + (r6 * 0.5) + (r12 * 0.2), 2)
        
        display_mkt = mkt_map.get(code.upper(), 'NYSE') if market_type == 'SP500' else mkt_name

        return {
            '기준일(월말)': target_date_str, '시장': display_mkt,
            '종목명': row['Name'], '종목코드': code, '기준가': round(base_price, 2),
            '1개월(%)': round(r1, 2), '3개월(%)': round(r3, 2), '6개월(%)': round(r6, 2),
            '12개월(%)': round(r12, 2), '모멘텀스코어': score, 
            '전달순위': prev_rank_map.get(code.upper(), None),
            '다음달수익률(%)': 0.0
        }
    except: return None

def run_monthly(market_type='KR'):
    mkt_map = {} 
    
    if market_type == 'KR':
        name_tag, file_path, folder, prefix = "한국", 'data/momentum_data.csv', 'archive', 'momentum_'
        market_list, limit = ['KOSPI', 'KOSDAQ'], 150
    elif market_type == 'US':
        name_tag, file_path, folder, prefix = "미국(시총상위)", 'data/momentum_data_us.csv', 'archive_us', 'momentum_us_'
        market_list, limit = ['NYSE', 'NASDAQ'], 150
    elif market_type == 'SP500':
        name_tag, file_path, folder, prefix = "S&P 500", 'data/momentum_data_sp500.csv', 'archive_sp500', 'momentum_sp500_'
        market_list, limit = ['S&P500'], 505
        try:
            nyse = fdr.StockListing('NYSE')[['Symbol']]
            nasdaq = fdr.StockListing('NASDAQ')[['Symbol']]
            mkt_map = {str(s): 'NYSE' for s in nyse['Symbol']}
            mkt_map.update({str(s): 'NASDAQ' for s in nasdaq['Symbol']})
        except: pass

    prev_rank_map = {}
    if os.path.exists(file_path):
        try:
            df_old_for_rank = pd.read_csv(file_path, dtype={'종목코드': str})
            df_old_for_rank = df_old_for_rank.sort_values('모멘텀스코어', ascending=False).reset_index(drop=True)
            for i, r in df_old_for_rank.iterrows():
                prev_rank_map[str(r['종목코드'])] = i + 1
        except Exception as e:
            print(f"⚠️ {name_tag} 이전 순위 로드 실패: {e}")

    target_date_str = get_target_ref_date()
    target_date_dt = pd.to_datetime(target_date_str)
    print(f"\n🚀 {name_tag} 월말 업데이트 시작 (기준일: {target_date_str})")

    # --- 1. 아카이브 보관 및 마스터 파일 자동 누적 로직 ---
    if os.path.exists(file_path):
        try:
            df_old = pd.read_csv(file_path, dtype={'종목코드': str})
            existing_date = str(df_old['기준일(월말)'].iloc[0])
            
            if existing_date != target_date_str:
                print(f"📦 기존 데이터({existing_date}) 성적표 작성 중...")
                
                for idx, row in df_old.iterrows():
                    code = str(row['종목코드'])
                    clean_code = code.replace('.', '-') if market_type in ['US', 'SP500'] else code.split('.')[0]
                    try:
                        df_price = fdr.DataReader(clean_code, existing_date, target_date_str)
                        if len(df_price) >= 2:
                            old_price = df_price['Close'].iloc[0]
                            new_price = df_price['Close'].iloc[-1]
                            df_old.at[idx, '다음달수익률(%)'] = round(((new_price / old_price) - 1) * 100, 2)
                    except: pass
                
                ym = (datetime.strptime(existing_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y_%m')
                archive_name = f'{folder}/{prefix}{ym}.csv'
                df_old.to_csv(archive_name, index=False, encoding='utf-8-sig')

                if market_type == 'KR':
                    master_csv = 'data/한국 코스피 2014년부터 200위까지 자료.csv'
                    if os.path.exists(master_csv):
                        try:
                            df_k200 = df_old[(df_old['시장'] == 'KOSPI') & (df_old['종목코드'].str.endswith('0'))].copy()
                            kospi_info = fdr.StockListing('KOSPI')[['Code', 'Marcap']]
                            df_k200 = df_k200.merge(kospi_info, left_on='종목코드', right_on='Code', how='left')
                            df_k200['시가총액'] = df_k200['Marcap'].fillna(0)
                            df_k200 = df_k200.sort_values(by='시가총액', ascending=False).head(200)
                            df_k200['순위'] = range(1, len(df_k200) + 1)
                            df_k200['기준일'] = existing_date
                            df_append = df_k200[['순위', '종목코드', '종목명', '시가총액', '기준일', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '다음달수익률(%)']]
                            df_append.to_csv(master_csv, mode='a', header=False, index=False, encoding='utf-8-sig')
                            print(f"✅ {existing_date} 실전 데이터를 마스터 과거 기록에 누적 완료!")
                        except Exception as e:
                            print(f"⚠️ 마스터 파일 누적 에러: {e}")
        except Exception as e: 
            print(f"⚠️ 아카이브 에러: {e}")

    # --- 2. 신규 데이터 수집 ---
    res = []
    for mkt_name in market_list:
        curr_limit = 200 if mkt_name == 'KOSPI' else limit
        target_stocks = get_top_stocks(mkt_name, curr_limit)
        
        if target_stocks.empty: continue

        print(f"📊 {mkt_name} {len(target_stocks)}개 종목 분석 중...")
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(process_monthly_stock, row, mkt_name, market_type, target_date_dt, target_date_str, mkt_map, prev_rank_map) for _, row in target_stocks.iterrows()]
            for future in as_completed(futures):
                result = future.result()
                if result: res.append(result)
                    
    # 💡 [핵심: 들여쓰기가 완벽하게 맞춰진 복리 역산 코드]
    if res:
        final_df = pd.DataFrame(res)
        
        # 0 나누기 방지용 안전장치 (1e-9)
        denom = (1 + final_df['1개월(%)'] / 100) + 1e-9
        
        final_df['3-1개월(%)'] = round(((1 + final_df['3개월(%)']/100) / denom - 1) * 100, 2)
        final_df['6-1개월(%)'] = round(((1 + final_df['6개월(%)']/100) / denom - 1) * 100, 2)
        final_df['12-1개월(%)'] = round(((1 + final_df['12개월(%)']/100) / denom - 1) * 100, 2)

        final_df = final_df.sort_values('모멘텀스코어', ascending=False)
        final_df.to_csv(file_path, index=False, encoding='utf-8-sig')
        print(f"✨ {name_tag} 파일 저장 완료!")

if __name__ == "__main__":
    for m in ['KR', 'US', 'SP500']:
        try:
            run_monthly(m)
        except Exception as e:
            print(f"🔥 {m} 실행 중 치명적 오류: {e}")
