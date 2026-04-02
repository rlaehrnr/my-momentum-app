import streamlit as st
import pandas as pd
import os
import glob

# 1. 페이지 설정
st.set_page_config(page_title="미국 모멘텀 기록보관소", layout="wide")

# CSS: 가독성 및 레이아웃 최적화 
st.markdown("""
    <style>
    .block-container { padding-top: 2.5rem !important; }
    h1 { font-size: 2.2rem !important; font-weight: 800; margin-bottom: 10px; }
    
    /* 섹션 제목 스타일 */
    .section-header {
        background-color: #1F2937;
        color: #FFFFFF;
        padding: 10px 12px;
        border-radius: 8px 8px 0 0;
        font-size: 1.1rem;
        font-weight: 700;
        border-bottom: 4px solid #EF4444;
        margin-top: 20px;
    }
    .overlap-header {
        background-color: #1E3A8A;
        color: white;
        padding: 10px 12px;
        border-radius: 8px 8px 0 0;
        font-size: 1.1rem;
        font-weight: 700;
        border-bottom: 4px solid #F59E0B;
    }
    /* 요약 메트릭 카드 스타일 */
    div[data-testid="metric-container"] {
        background-color: #F8F9FA;
        border-radius: 8px;
        padding: 15px;
        border-left: 5px solid #1E3A8A;
    }
    </style>
    """, unsafe_allow_html=True)

# ⭐ 겹치는 종목 하이라이트 + 다음달 수익률 색상 동시 적용
def style_archive_dataframe(row, common_tickers):
    styles = [''] * len(row)
    
    if row.get('종목코드') in common_tickers:
        if '종목명_L' in row.index:
            name_idx = row.index.get_loc('종목명_L')
            styles[name_idx] = 'background-color: #FFF9C4; color: #1F2937; font-weight: bold; border-radius: 4px;'
            
    if '다음달수익률(%)' in row.index:
        ret_idx = row.index.get_loc('다음달수익률(%)')
        val = row['다음달수익률(%)']
        if pd.notnull(val):
            if val > 0:
                styles[ret_idx] = 'color: #EF4444; font-weight: bold;'
            elif val < 0:
                styles[ret_idx] = 'color: #1E3A8A; background-color: #EFF6FF; font-weight: bold;'
                
    return styles

# 컬럼 너비 밸런스 설정
base_config = {
    "순위": st.column_config.NumberColumn("순위", format="%d", width=40),
    "통합티커": st.column_config.TextColumn("티커", width=105),
    "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)", width=None), 
    "기준가": st.column_config.NumberColumn("현재가", format="$ %,.2f", width=95),
    "1개월(%)": st.column_config.NumberColumn("1M", format="%.1f%%", width=75),
    "3개월(%)": st.column_config.NumberColumn("3M", format="%.1f%%", width=75),
    "6개월(%)": st.column_config.NumberColumn("6M", format="%.1f%%", width=75),
    "12개월(%)": st.column_config.NumberColumn("12M", format="%.1f%%", width=75),
    "3-1개월(%)": st.column_config.NumberColumn("3-1M", format="%.1f%%", width=85),
    "6-1개월(%)": st.column_config.NumberColumn("6-1M", format="%.1f%%", width=85),
    "12-1개월(%)": st.column_config.NumberColumn("12-1M", format="%.1f%%", width=85),
    "모멘텀스코어": st.column_config.NumberColumn("스코어", format="%.2f", width=80),
    "다음달수익률(%)": st.column_config.NumberColumn("다음달수익", format="%.1f%%", width=90), 
}

st.title("📁 미국 월별 모멘텀 기록보관소")

folder, prefix = "archive_us", "momentum_us_"
files = sorted(glob.glob(f"{folder}/{prefix}*.csv"), reverse=True)

if not files:
    st.info("미국 시장 기록이 없습니다.")
else:
    file_map = {f"📅 {os.path.basename(f).replace(prefix, '').replace('.csv', '').split('_')[0]}년 {os.path.basename(f).replace(prefix, '').replace('.csv', '').split('_')[1]}월 성적표": f for f in files}
    selected_file = file_map[st.selectbox("조회할 달을 선택하세요", list(file_map.keys()))]

    # 데이터 로드 및 컬럼 공백 제거
    df = pd.read_csv(selected_file)
    df.columns = df.columns.str.replace(' ', '')
    
    st.success(f"✅ 이 리스트는 **{df['기준일(월말)'].iloc[0]}** 종가를 기준으로 추출되었으며, **다음달 실제 투자 수익률**을 보여줍니다.")

    # 문자열 퍼센트 기호를 숫자로 안전하게 변환
    for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '3-1개월(%)', '6-1개월(%)', '12-1개월(%)', '모멘텀스코어', '다음달수익률(%)']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)

    # 💡 [에러 해결 핵심] 과거 파일에 12-1M, 6-1M, 3-1M 데이터가 없을 경우 즉석에서 계산하여 채워 넣음
    if '12-1개월(%)' not in df.columns and '12개월(%)' in df.columns and '1개월(%)' in df.columns:
        df['12-1개월(%)'] = df['12개월(%)'] - df['1개월(%)']
    if '6-1개월(%)' not in df.columns and '6개월(%)' in df.columns and '1개월(%)' in df.columns:
        df['6-1개월(%)'] = df['6개월(%)'] - df['1개월(%)']
    if '3-1개월(%)' not in df.columns and '3개월(%)' in df.columns and '1개월(%)' in df.columns:
        df['3-1개월(%)'] = df['3개월(%)'] - df['1개월(%)']

    # 핵심 요약 메트릭
    if '다음달수익률(%)' in df.columns:
        avg_ret = df['다음달수익률(%)'].mean()
        win_rate = (df['다음달수익률(%)'] > 0).sum() / len(df) * 100 if len(df) > 0 else 0
        c1, c2, c3 = st.columns([1, 1, 2])
        c1.metric("📌 상위 300 평균 수익률", f"{avg_ret:.2f}%")
        c2.metric("📈 상승 종목 비율 (승률)", f"{win_rate:.1f}%")

    # 티커 및 네이버 금융 링크 연결
    df['통합티커'] = df['시장'].astype(str) + ":" + df['종목코드'].astype(str)
    df['종목명_L'] = df.apply(lambda r: f"https://finance.yahoo.com/chart/{str(r['종목코드']).replace('.', '-')}#{r['종목명']}", axis=1)

    # 교집합 데이터 추출
    top10_12_1 = df.sort_values('12-1개월(%)', ascending=False).head(10)
    top10_6_1 = df.sort_values('6-1개월(%)', ascending=False).head(10)
    top10_3_1 = df.sort_values('3-1개월(%)', ascending=False).head(10)

    overlap_12_6 = top10_12_1[top10_12_1['종목코드'].isin(top10_6_1['종목코드'])].copy()
    overlap_6_3 = top10_6_1[top10_6_1['종목코드'].isin(top10_3_1['종목코드'])].copy()
    common_tickers = set(overlap_12_6['종목코드']).intersection(set(overlap_6_3['종목코드']))

    # --- 상단: 교집합 ---
    st.markdown("### 🌟 모멘텀 교집합 다음달 성적표 (TOP 10 중복)")
    c_over1, c_over2 = st.columns(2)
    
    with c_over1:
        st.markdown('<div class="overlap-header">🔥 12-1M & 6-1M 중복</div>', unsafe_allow_html=True)
        if not overlap_12_6.empty:
            overlap_12_6['순위'] = range(1, len(overlap_12_6) + 1)
            st.dataframe(overlap_12_6.style.apply(style_archive_dataframe, common_tickers=common_tickers, axis=1), 
                         use_container_width=True, hide_index=True,
                         column_order=['순위', '통합티커', '종목명_L', '12-1개월(%)', '6-1개월(%)', '다음달수익률(%)'], column_config=base_config)
        else: st.info("중복 없음")

    with c_over2:
        st.markdown('<div class="overlap-header">⚡ 6-1M & 3-1M 중복</div>', unsafe_allow_html=True)
        if not overlap_6_3.empty:
            overlap_6_3['순위'] = range(1, len(overlap_6_3) + 1)
            st.dataframe(overlap_6_3.style.apply(style_archive_dataframe, common_tickers=common_tickers, axis=1), 
                         use_container_width=True, hide_index=True,
                         column_order=['순위', '통합티커', '종목명_L', '6-1개월(%)', '3-1개월(%)', '다음달수익률(%)'], column_config=base_config)
        else: st.info("중복 없음")

    # --- 중단: 상위 30위 ---
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    
    sub_config = base_config.copy()
    sub_config["12-1개월(%)"] = st.column_config.NumberColumn("12-1", format="%.1f%%", width="small")
    sub_config["6-1개월(%)"] = st.column_config.NumberColumn("6-1", format="%.1f%%", width="small")
    sub_config["3-1개월(%)"] = st.column_config.NumberColumn("3-1", format="%.1f%%", width="small")
    sub_config["다음달수익률(%)"] = st.column_config.NumberColumn("다음달수익", format="%.1f%%", width="small")

    for col, title, sort_col in zip([col1, col2, col3], 
                                   ["🏆 12-1개월 상위 30", "🏆 6-1개월 상위 30", "🏆 3-1개월 상위 30"], 
                                   ["12-1개월(%)", "6-1개월(%)", "3-1개월(%)"]):
        with col:
            st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)
            df_sub = df.sort_values(sort_col, ascending=False).head(30).copy()
            df_sub['순위'] = range(1, 31)
            
            sub_order = ['순위', '통합티커', '종목명_L', sort_col, '다음달수익률(%)']
            sub_order = [c for c in sub_order if c in df_sub.columns or c == '순위']
            
            st.dataframe(df_sub.style.apply(style_archive_dataframe, common_tickers=common_tickers, axis=1), 
                         use_container_width=True, height=450, hide_index=True,
                         column_order=sub_order, column_config=sub_config)

    # --- 하단: 전체 ---
    st.markdown("---")
    st.markdown(f"### 📊 미국 상위 300종목 전체 기록 (기준: {df['기준일(월말)'].iloc[0]})")
    
    df['순위'] = range(1, len(df) + 1)
    
    full_order = ['순위', '통합티커', '종목명_L', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '3-1개월(%)', '6-1개월(%)', '12-1개월(%)', '모멘텀스코어', '다음달수익률(%)']
    full_order = [col for col in full_order if col in df.columns or col == '순위']
    
    st.dataframe(df.style.apply(style_archive_dataframe, common_tickers=common_tickers, axis=1), 
                 use_container_width=True, height=600, hide_index=True,
                 column_order=full_order, column_config=base_config)
