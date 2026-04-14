import pandas as pd
import os

# 1. 설정
input_file = 'sp500_퀀트데이터_2000_2025_Final_Cleaned.csv'
output_dir = 'archive_sp500'

if not os.path.exists(output_dir):
    os.makedirs(output_dir)

print("1. 데이터를 읽어오는 중...")
df = pd.read_csv(input_file)
df['Date'] = pd.to_datetime(df['Date'])

# 숫자형 변환 및 결측치 처리
cols = ['Past_1M_Return(%)', 'Past_3M_Return(%)', 'Past_6M_Return(%)', 'Past_12M_Return(%)', 'Forward_1M_Return(%)']
for c in cols:
    df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)

print("2. 지정된 가중치로 모멘텀 스코어 계산 중...")
# 💡 선생님의 공식 적용: 1개월(-0.1) + 3개월(0.7) + 6개월(0.4)
df['모멘텀스코어'] = (df['Past_1M_Return(%)'] * -0.1) + \
                     (df['Past_3M_Return(%)'] * 0.7) + \
                     (df['Past_6M_Return(%)'] * 0.4)

# 보조 지표(n-1)도 참고용으로 계산하여 파일에 넣어둡니다.
df['12-1개월(%)'] = df['Past_12M_Return(%)'] - df['Past_1M_Return(%)']
df['6-1개월(%)'] = df['Past_6M_Return(%)'] - df['Past_1M_Return(%)']
df['3-1개월(%)'] = df['Past_3M_Return(%)'] - df['Past_1M_Return(%)']

# 컬럼명 정리
df.rename(columns={
    'Ticker': '종목코드', 'Close_Price': '기준가',
    'Date': '기준일(월말)', 'Forward_1M_Return(%)': '다음달수익률(%)',
    'Past_1M_Return(%)': '1개월(%)', 'Past_3M_Return(%)': '3개월(%)',
    'Past_6M_Return(%)': '6개월(%)', 'Past_12M_Return(%)': '12개월(%)'
}, inplace=True)
df['시장'] = 'S&P500'
df['종목명'] = df['종목코드'] # 이름이 없으므로 코드를 이름으로 사용

print("3. 전달 순위(Previous Rank) 생성 중...")
# 월별로 정렬 후 순위 부여
df = df.sort_values(['기준일(월말)', '모멘텀스코어'], ascending=[True, False])
df['현재순위'] = df.groupby('기준일(월말)')['모멘텀스코어'].rank(ascending=False, method='first')

# 전달 순위 매칭 로직
df_rank = df[['기준일(월말)', '종목코드', '현재순위']].copy()
df_rank['다음기준일'] = df_rank['기준일(월말)'] + pd.DateOffset(months=1)

df = df.merge(
    df_rank[['다음기준일', '종목코드', '현재순위']].rename(columns={'현재순위': '전달순위', '다음기준일': '기준일(월말)'}),
    on=['기준일(월말)', '종목코드'],
    how='left'
)
df['전달순위'] = df['전달순위'].fillna(0).astype(int)

print("4. 월별 파일로 저장 (한글 깨짐 방지)...")
df['Year'] = df['기준일(월말)'].dt.year
df['Month'] = df['기준일(월말)'].dt.month

count = 0
for (year, month), group in df.groupby(['Year', 'Month']):
    filename = f"momentum_sp500_{year}_{month:02d}.csv"
    # 한글 깨짐 방지를 위해 utf-8-sig 사용
    group.to_csv(os.path.join(output_dir, filename), index=False, encoding='utf-8-sig')
    count += 1

print(f"🎉 작업 완료! 총 {count}개의 파일이 생성되었습니다.")
