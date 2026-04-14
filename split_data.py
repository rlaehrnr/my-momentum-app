import pandas as pd
import os

# 1. 파일 이름 설정
input_file = 'sp500_퀀트데이터_2000_2025_Final_Cleaned.csv'
output_dir = 'archive_sp500'

# 출력 폴더가 없으면 생성
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

print("데이터를 불러오는 중입니다...")
# 2. 마스터 데이터 불러오기
df = pd.read_csv(input_file)

# Date 컬럼을 datetime 형식으로 변환
df['Date'] = pd.to_datetime(df['Date'])

# 💡 3. 부족했던 파생 변수(12-1, 6-1, 3-1, 모멘텀 스코어) 완벽하게 계산해서 채워넣기!
print("모멘텀 파생 변수 및 스코어를 계산 중입니다...")

# 결측치 0.0 처리 (계산 에러 방지)
for c in ['Past_1M_Return(%)', 'Past_3M_Return(%)', 'Past_6M_Return(%)', 'Past_12M_Return(%)', 'Forward_1M_Return(%)']:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)

# (1+과거N개월) / (1+최근1개월) - 1 공식 적용
df['12-1개월(%)'] = ((1 + df['Past_12M_Return(%)']/100) / (1 + df['Past_1M_Return(%)']/100) - 1) * 100
df['6-1개월(%)'] = ((1 + df['Past_6M_Return(%)']/100) / (1 + df['Past_1M_Return(%)']/100) - 1) * 100
df['3-1개월(%)'] = ((1 + df['Past_3M_Return(%)']/100) / (1 + df['Past_1M_Return(%)']/100) - 1) * 100

# 모멘텀 스코어 (세 지표의 평균)
df['모멘텀스코어'] = (df['12-1개월(%)'] + df['6-1개월(%)'] + df['3-1개월(%)']) / 3

# 앱에서 사용하는 한글 컬럼명으로 예쁘게 변경
df.rename(columns={
    'Ticker': '종목코드',
    'Close_Price': '기준가',
    'Past_1M_Return(%)': '1개월(%)',
    'Past_3M_Return(%)': '3개월(%)',
    'Past_6M_Return(%)': '6개월(%)',
    'Past_12M_Return(%)': '12개월(%)',
    'Forward_1M_Return(%)': '다음달수익률(%)',
    'Date': '기준일(월말)'
}, inplace=True)

# 4. 연도와 월을 기준으로 그룹화하여 파일 쪼개기
grouped = df.groupby([df['기준일(월말)'].dt.year, df['기준일(월말)'].dt.month])

print("파일을 월별로 쪼개어 저장합니다...")
count = 0
for (year, month), group in grouped:
    # 파일 이름 포맷: momentum_sp500_YYYY_MM.csv (예: momentum_sp500_2018_05.csv)
    file_name = f"momentum_sp500_{year}_{month:02d}.csv"
    file_path = os.path.join(output_dir, file_name)
    
    # 해당 월의 데이터만 저장 (인덱스 제외)
    group.to_csv(file_path, index=False)
    count += 1

print(f"🎉 성공! 총 {count}개의 월별 파일이 '{output_dir}' 폴더에 생성되었습니다.")
print("이제 마스터 파일(sp500_퀀트데이터_2000_2025_Final_Cleaned.csv)은 지우셔도 됩니다!")
