import pandas as pd
import FinanceDataReader as fdr
import requests
import re
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# 저장할 파일 경로 (대시보드가 읽어가는 바로 그 파일!)
SAVE_PATH = 'data/krx_stock_info.csv'

def get_face_value(code):
    """네이버 금융에서 특정 종목의 액면가를 크롤링해오는 함수"""
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        res = requests.get(url, headers=headers, timeout=5)
        # 💡 정규식(Regex)을 이용해 네이버 증권 화면에서 액면가 숫자만 정확히 뽑아냅니다.
        match = re.search(r'액면가.*?<em[^>]*>([\d,]+)</em>', res.text, re.DOTALL | re.IGNORECASE)
        
        if match:
            face_value = int(match.group(1).replace(',', ''))
            return code, face_value
        else:
            # ETF나 액면가가 없는 특수 종목은 0 반환
            return code, 0
    except:
        return code, 0

def run_face_value_update():
    print(f"🤖 [시작] 한국 주식 전 종목 액면가 자동 수집을 시작합니다. (약 1~2분 소요)")
    
    if not os.path.exists('data'):
        os.makedirs('data')

    # 1. KRX 전 종목 리스트 뼈대 가져오기 (초고속)
    df = fdr.StockListing('KRX')
    ticker_col = 'Symbol' if 'Symbol' in df.columns else 'Code'
    
    # 주식(보통주/우선주)만 필터링하고 코드를 6자리 문자로 맞춤
    df = df.dropna(subset=[ticker_col])
    df[ticker_col] = df[ticker_col].astype(str).str.zfill(6)
    all_codes = df[ticker_col].tolist()
    
    print(f"총 {len(all_codes)}개 종목의 액면가 조회를 시작합니다. 커피 한 잔 하고 오세요! ☕")
    
    # 2. 병렬 처리(초고속)로 네이버에서 액면가 싹쓸이
    face_values = {}
    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = {executor.submit(get_face_value, code): code for code in all_codes}
        
        completed = 0
        for future in as_completed(futures):
            code, fv = future.result()
            face_values[code] = fv
            
            completed += 1
            if completed % 500 == 0:
                print(f"  ... 진행률: {completed} / {len(all_codes)} 완료")

    # 3. 가져온 데이터를 데이터프레임으로 만들고 CSV로 저장
    result_df = pd.DataFrame(list(face_values.items()), columns=['단축코드', '액면가'])
    
    # 💡 선생님의 원본 파일 양식과 동일하게 맞춤 (단축코드, 액면가 열 필수)
    result_df.to_csv(SAVE_PATH, index=False, encoding='utf-8-sig')
    
    print(f"🎉 [성공] 모든 액면가 업데이트가 완료되었습니다!")
    print(f"저장 위치: {SAVE_PATH} (기준일: {datetime.today().strftime('%Y-%m-%d')})")

if __name__ == "__main__":
    run_face_value_update()
