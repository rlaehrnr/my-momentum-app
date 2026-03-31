import streamlit as st
import pandas as pd
import os
import glob
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(page_title="한국 모멘텀 기록보관소", layout="wide")

# CSS: 레이아웃 초밀착 및 투명 디자인 유지
st.markdown("""
    <style>
    .block-container { padding-top: 2rem !important; }
    h1 { font-size: 1.8rem !important; font-weight: 800; margin-bottom: 20px; }
    [data-testid="stDataFrame"] { margin-bottom: -20px !important; }
    .stMetric { background-color: transparent !important; padding: 0px !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("📁 한국 월별 모멘텀 기록보관소")

folder, prefix = "archive", "momentum_"
files = glob.glob(f"{folder}/{prefix}*.csv")

if not files:
    st.info("데이터가 없습니다. archive 폴더를 확인해주세요.")
else:
    # 1. 데이터 구조 파악 (연도별로 월 리스트 저장)
    data_struct = {}
    for f in files:
        fname = os.path.basename(f)
        try:
            date_part = fname.replace(prefix, "").replace(".csv", "")
            year, month = date_part.split('_')
            if year not in data_struct: data_struct[year] = []
            data_struct[year].append(month)
        except: continue

    # 연도는 최신순 (2026, 2025...)
    sorted_years = sorted(data_struct.keys(), reverse=True)
    
    col_y, col_m, _ = st.columns([1, 1, 4])
    with col_y:
        selected_year = st.selectbox("📅 연도", sorted_years)
    with col_m:
        # 월은 1월부터 순서대로 (01, 02, 03...)
        available_months = sorted(data_struct[selected_year], key=lambda x: int(x))
        selected_month = st.selectbox("🌙 월", available_months)

    # 현재 달 데이터 로드
    target_file = f"{folder}/{prefix}{selected_year}_{selected_month}.csv"
    df = pd.read_csv(target_file, dtype={'종목코드': str})
    
    # ⭐ [수정된 핵심 로직: 전달 순위 대조] ⭐
    try:
        # 1. 현재 선택된 연/월을 datetime 객체로 변환 (예: 2026-03-01)
        curr_dt = datetime(int(selected_year), int(selected_month), 1)
        # 2. 하루 전으로 돌려서 이전 달의 연/월 추출 (예: 2026-02-28 -> 2026_02)
        prev_dt = curr_dt - timedelta(days=1)
        p_year_str = prev_dt.strftime('%Y')
        p_month_str = prev_dt.strftime('%m')
        
        # 3. 이전 달 파일 경로 생성
        prev_file = f"{folder}/{prefix}{p_year_str}_{p_month_str}.csv"
        
        # 4. 이전 달 파일이 존재하면 읽어와서 순위 계산
        if os.path.exists(prev_file):
            df_prev = pd.read_csv(prev_file, dtype={'종목코드': str})
            # 이전 달 데이터를 모멘텀 스코어 기준으로 '내림차순' 정렬
            df_prev = df_prev.sort_values('모멘텀스코어', ascending=False).reset_index(drop=True)
            # 종목코드: 순위(index+1) 형태의 딕셔너리 생성
            prev_rank_dict = {code: idx + 1 for idx, code in enumerate(df_prev['종목코드'])}
            # 현재 달 데이터프레임에 매핑
            df['전달순위'] = df['종목코드'].map(prev_rank_dict)
        else:
            df['전달순위'] = None
    except Exception as e:
        st.write(f"순위 계산 중 오류: {e}") # 디버깅용 (필요시 삭제)
        df['전달순위'] = None

    # 기준일 출력 시 KeyError 방지
    date_col = '기준일(월말)' if '기준일(월말)' in df.columns else '기준일'
    display_date = df[date_col].iloc[0] if date_col in df.columns else f"{selected_year}-{selected_month}"
    
    st.success(f"**{selected_year}년 {selected_month}월** (추출 기준일: {display_date})")

    # 2. 메인 표 출력 (글자색 포인트)
    def style_returns(val):
        try:
            num = float(val)
            if num > 0: return 'color: #FF4B4B; font-weight: bold;'
            elif num < 0: return 'color: #3182CE; font-weight: bold;'
        except: pass
        return ''

    # 현재 달 데이터의 인덱스(현재 순위) 재설정
    df = df.sort_values('모멘텀스코어', ascending=False).reset_index(drop=True)
    df.index = range(1, len(df) + 1)
    
    df['종목명_L'] = df.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)

    # 출력 컬럼 목록 (수익률이 있을 때만 추가)
    display_cols = ['시장', '종목명_L', '기준가', '모멘텀스코어', '전달순위']
    if '다음달수익률(%)' in df.columns:
        display_cols.append('다음달수익률(%)')

    # 컬럼 설정
    config = {
        "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"),
        "기준가": st.column_config.NumberColumn(format="%d"),
        "모멘텀스코어": st.column_config.NumberColumn(format="%.1f"),
        "전달순위": st.column_config.NumberColumn("전달 순위", format="%d위")
    }
    if '다음달수익률(%)' in df.columns:
        config["다음달수익률(%)"] = st.column_config.NumberColumn(format="%.2f %%")

    styled_df = df.style
    if '다음달수익률(%)' in df.columns:
        styled_df = styled_df.map(style_returns, subset=['다음달수익률(%)'])

    st.dataframe(
        styled_df,
        use_container_width=True, height=500,
        column_order=display_cols,
        column_config=config
    )

    # 3. 상위권 포트폴리오 성적 (표 바로 밑 밀착 배치)
    def get_stats(data, n):
        subset = data.head(n)
        if '다음달수익률(%)' not in subset.columns or subset.empty: 
            return "0.00%", "승률 0%"
        avg = subset['다음달수익률(%)'].mean()
        win = (subset['다음달수익률(%)'] > 0).mean() * 100
        win_display = int(win) if win == int(win) else round(win, 1)
        return f"{avg:.2f}%", f"승률 {win_display}%"

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    
    t10_avg, t10_win = get_stats(df, 10)
    c1.metric("🏆 Top 10 성적", t10_avg, t10_win)

    t20_avg, t20_win = get_stats(df, 20)
    c2.metric("🥈 Top 20 성적", t20_avg, t20_win)

    t30_avg, t30_win = get_stats(df, 30)
    c3.metric("🥉 Top 30 성적", t30_avg, t30_win)
