import pandas as pd
import os

input_file = 'data/한국 코스피 2014년부터 200위까지 자료.csv' # 선생님의 파일 경로
output_dir = 'archive_kospi'

if not os.path.exists(output_dir):
    os.makedirs(output_dir)

print("1. 데이터를 읽어오는 중...")
df = pd.read_csv(input_file)
df.columns = df.columns.str.replace(' ', '') # 공백 제거

# 💡 나중을 위해 컬럼명을 다른 폴더들과 동일하게 '기준일(월말)'로 통일합니다.
df.rename(columns={'기준일': '기준일(월말)'}, inplace=True)
df['기준일(월말)'] = pd.to_datetime(df['기준일(월말)'])
df['종목코드'] = df['종목코드'].astype(str).str.zfill(6)

print("2. 월별 파일로 쪼개는 중...")
df['Year'] = df['기준일(월말)'].dt.year
df['Month'] = df['기준일(월말)'].dt.month

count = 0
for (year, month), group in df.groupby(['Year', 'Month']):
    filename = f"momentum_kospi_{year}_{month:02d}.csv"
    # 불필요한 연/월 임시 컬럼 제거 후 저장
    group = group.drop(columns=['Year', 'Month'])
    group.to_csv(os.path.join(output_dir, filename), index=False, encoding='utf-8-sig')
    count += 1

print(f"🎉 완료! 총 {count}개의 파일이 '{output_dir}' 폴더에 깔끔하게 생성되었습니다.")
