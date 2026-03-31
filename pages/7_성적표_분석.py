import streamlit as st
import pandas as pd
import os
import glob

# 1. 페이지 설정
st.set_page_config(page_title="모멘텀 구간 최적화", layout="wide")

st.title("🎯 모멘텀 최적 수익 구간(Range) 분석")
st.info("차트보다는 정밀한 표 데이터를 통해 '몇 위부터 몇 위까지' 사는 것이 유리한지 분석합니다.")

# 2. 데이터 로드 함수 (모든 아카이브 통합)
def load_total_archive(folder, prefix):
    files = glob.glob(os.path.join(folder, f"{prefix}*.csv"))
    if not files: return pd.DataFrame()
    
    all_data = []
    for f in sorted(files):
        try:
            df = pd.read_csv(f)
            if '다음달수익률(%)' in df.columns:
                # 스코어 기준 재정렬 및 순위 부여
                df = df.sort_values('모멘텀스코어', ascending=False).reset_index(drop=True)
                df['순위'] = df.index + 1
                all_data.append(df)
        except: continue
    return pd.concat(all_data) if all_data else pd.DataFrame()

# 3. 마켓 선택
tabs = st.tabs(["🇰🇷 한국", "🇺🇸 미국(150위)", "🇺🇸 S&P 500"])
configs = [("archive", "momentum_"), ("archive_us", "momentum_us_"), ("archive_sp500", "momentum_sp500_")]

for tab, (folder, prefix) in zip(tabs, configs):
    with tab:
        df_master = load_total_archive(folder, prefix)
        if df_master.empty:
            st.warning("데이터가 부족합니다. 월말 성적표(monthly)가 아카이브에 쌓여야 분석이 가능합니다.")
            continue

        # --- [분석 1: 10위 단위 블록 성적표] ---
        st.subheader("📊 1. 순위권별 '블록' 성적표 (어느 구간이 가장 강한가?)")
        st.write("1~10위, 11~20위 등 10개 단위 묶음의 역대 평균 수익률입니다.")
        
        block_res = []
        for start in range(1, 101, 10):
            end = start + 9
            block_df = df_master[(df_master['순위'] >= start) & (df_master['순위'] <= end)]
            if not block_df.empty:
                block_res.append({
                    "순위 구간": f"{start}위 ~ {end}위",
                    "평균 수익률": f"{block_df['다음달수익률(%)'].mean():.2f}%",
                    "상승 종목 비중": f"{(block_df['다음달수익률(%)'] > 0).mean()*100:.1f}%",
                    "최고 수익률": f"{block_df['다음달수익률(%)'].max():.1f}%",
                    "최저 수익률": f"{block_df['다음달수익률(%)'].min():.1f}%"
                })
        st.table(pd.DataFrame(block_res))

        # --- [분석 2: 최적의 시작점(Sweet Spot) 찾기] ---
        st.markdown("---")
        st.subheader("💡 2. 최적의 '시작 순위' 탐색 (표로 비교)")
        st.write("똑같이 20개를 사더라도, 몇 위부터 시작하느냐에 따라 성적이 달라집니다.")
        
        test_size = st.selectbox("가상 매수 종목 수 선택", [10, 20, 30], index=1, key=f"size_{prefix}")
        
        range_res = []
        # 시작 지점을 1위, 11위, 21위, 31위, 41위, 51위로 테스트
        for start_pos in [1, 11, 21, 31, 41, 51]:
            end_pos = start_pos + test_size - 1
            test_df = df_master[(df_master['순위'] >= start_pos) & (df_master['순위'] <= end_pos)]
            
            if not test_df.empty:
                # 월별로 다시 그룹화하여 복리 누적 수익률 계산
                monthly_avg = test_df.groupby('기준일(월말)')['다음달수익률(%)'].mean()
                cum_ret = ((1 + monthly_avg/100).cumprod() - 1) * 100
                
                range_res.append({
                    "전략 명칭": f"{start_pos}위부터 {test_size}개 매수",
                    "대상 구간": f"{start_pos}위 ~ {end_pos}위",
                    "월평균 수익률": f"{monthly_avg.mean():.2f}%",
                    "역대 누적 수익률": f"{cum_ret.iloc[-1]:.2f}%",
                    "월간 승률": f"{(monthly_avg > 0).mean()*100:.1f}%"
                })
        
        # 성적순으로 정렬하여 표 표시
        range_final = pd.DataFrame(range_res).sort_values("월평균 수익률", ascending=False)
        st.table(range_final)

        # --- [분석 3: 사용자 맞춤형 구간 계산기] ---
        st.markdown("---")
        st.subheader("🔍 3. 내 맘대로 구간 테스트")
        col1, col2 = st.columns(2)
        with col1:
            u_start = st.number_input("시작 순위", min_value=1, max_value=200, value=1, key=f"u_s_{prefix}")
        with col2:
            u_count = st.number_input("매수 종목 수", min_value=1, max_value=100, value=20, key=f"u_c_{prefix}")
        
        u_end = u_start + u_count - 1
        u_df = df_master[(df_master['순위'] >= u_start) & (df_master['순위'] <= u_end)]
        
        if not u_df.empty:
            u_avg = u_df['다음달수익률(%)'].mean()
            u_plus = (u_df['다음달수익률(%)'] > 0).mean() * 100
            
            st.success(f"✅ **{u_start}위 ~ {u_end}위** 구간 분석 결과")
            res_col1, res_col2 = st.columns(2)
            res_col1.metric("구간 평균 수익률", f"{u_avg:.2f}%")
            res_col2.metric("상승 종목 확률", f"{u_plus:.1f}%")
