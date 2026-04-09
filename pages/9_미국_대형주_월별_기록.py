import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os
import glob
import numpy as np

# 1. 페이지 설정
st.set_page_config(page_title="미국 대형주 모멘텀 기록보관소", layout="wide")

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
        font-size: 1.05rem;
        font-weight: 700;
        border-bottom: 4px solid #EF4444;
        margin-top: 20px;
    }
    .overlap-header {
        background-color: #1E3A8A;
        color: white;
        padding: 10px 12px;
        border-radius: 8px 8px 0 0;
        font-size: 1.05rem;
        font-weight: 700;
        border-bottom: 4px solid #F59E0B;
    }
    </style>
    """, unsafe_allow_html=True)

# ⭐ [업데이트 1] 날짜 오류 해결 (이동평균선 수집 시 2일 넉넉히 가져옴)
@st.cache_data(ttl=3600)
def get_index_ma_status(target_date_str):
    indices = {'S&P 500': 'US500', 'NASDAQ': 'IXIC'}
    target_date = pd.to_datetime(target_date_str)
    start_date = target_date - timedelta(days=400) 
    
    # 💡 라이브러리 누락 방지용 +2일
    fetch_end_date = target_date + timedelta(days=2)
    
    res = []
    for name, code in indices.items():
        try:
            df = fdr.DataReader(code, start_date, fetch_end_date)
            # 💡 원하는 기준일까지만 정확하게 컷!
            df = df[df.index <= target_date]
            
            if df.empty: continue
            
            curr_price = df['Close'].iloc[-1]
            
            if name == 'S&P 500':
                url_name = f"https://m.stock.naver.com/worldstock/index/.INX/total#{name}"
                url_price = f"https://m.stock.naver.com/fchart/foreign/index/.INX#{curr_price:,.2f}"
            else:
                url_name = f"https://m.stock.naver.com/worldstock/index/.IXIC/total#{name}"
                url_price = f"https://m.stock.naver.com/fchart/foreign/index/.IXIC#{curr_price:,.2f}"
            
            ma_values = {
                '지수_L': url_name,
                '현재가_L': url_price,
                'base_price': round(curr_price, 2),
                '20일선': round(df['Close'].rolling(20).mean().iloc[-1], 2),
                '60일선': round(df['Close'].rolling(60).mean().iloc[-1], 2),
                '120일선': round(df['Close'].rolling(120).mean().iloc[-1], 2),
                '150일선': round(df['Close'].rolling(150).mean().iloc[-1], 2),
                '200일선': round(df['Close'].rolling(200).mean().iloc[-1], 2)
            }
            res.append(ma_values)
        except: pass
    return pd.DataFrame(res)

def style_index_ma(df):
    def apply_color(row):
        price = row['base_price']
        styles = [''] * len(row)
        for i, col in enumerate(row.index):
            if '일선' in col:
                val = row[col]
                if pd.notnull(val):
                    if val < price:
                        styles[i] = 'color: #EF4444; font-weight: bold;' 
                    elif val > price:
                        styles[i] = 'color: #3B82F6; font-weight: bold;' 
        return styles
    return df.style.apply(apply_color, axis=1)

ma_config = {
    "지수_L": st.column_config.LinkColumn("지수", display_text=r"#(.+)"),
    "현재가_L": st.column_config.LinkColumn("현재가", display_text=r"#(.+)"),
    "20일선": st.column_config.NumberColumn("20일선", format="%,.2f"),
    "60일선": st.column_config.NumberColumn("60일선", format="%,.2f"),
    "120일선": st.column_config.NumberColumn("120일선", format="%,.2f"),
    "150일선": st.column_config.NumberColumn("150일선", format="%,.2f"),
    "200일선": st.column_config.NumberColumn("200일선", format="%,.2f"),
    "base_price": None
}

# ⭐ [업데이트 3] 모멘텀 상위 8개 종목 초록색 강조 + 다음달 수익률 색상 유지
def style_archive_dataframe(row, target_codes):
    styles = [''] * len(row)
    
    # 모멘텀 상위 8개 종목 초록색 하이라이트
    if row.get('종목코드') in target_codes:
        if '종목명_L' in row.index:
            name_idx = row.index.get_loc('종목명_L')
            styles[name_idx] = 'background-color: #E8F5E9; color: #2E7D32; font-weight: bold; border-radius: 4px;'
            
    # 다음달 수익률 양수/음수 표시
    if '다음달수익률(%)' in row.index:
        ret_idx = row.index.get_loc('다음달수익률(%)')
        val = row['다음달수익률(%)']
        if pd.notnull(val):
            if val >= 0:
                styles[ret_idx] = 'color: #EF4444; font-weight: bold;'
            else:
                styles[ret_idx] = 'color: #3B82F6; background-color: #EFF6FF; font-weight: bold;'
    return styles

def fmt_ret_html(val):
    if pd.isna(val): return "<span style='color:#9CA3AF;'>N/A</span>"
    color = "#EF4444" if val >= 0 else "#3B82F6"
    return f"<span style='color:{color}; font-weight:bold;'>{val:+.1f}%</span>"

base_config = {
    "순위": st.column_config.NumberColumn("순위", format="%d", width=40),
    "통합티커": st.column_config.TextColumn("티커", width=95),
    "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)", width=None), 
    "기준가": st.column_config.NumberColumn("현재가", format="$ %,.2f", width=90),
    "1개월(%)": st.column_config.NumberColumn("1M", format="%.1f%%", width=75),
    "3개월(%)": st.column_config.NumberColumn("3M", format="%.1f%%", width=75),
    "6개월(%)": st.column_config.NumberColumn("6M", format="%.1f%%", width=75),
    "12개월(%)": st.column_config.NumberColumn("12M", format="%.1f%%", width=75),
    "3-1개월(%)": st.column_config.NumberColumn("3-1M", format="%.1f%%", width=85),
    "6-1개월(%)": st.column_config.NumberColumn("6-1M", format="%.1f%%", width=85),
    "12-1개월(%)": st.column_config.NumberColumn("12-1M", format="%.1f%%", width=85),
    "모멘텀스코어": st.column_config.NumberColumn("스코어", format="%.2f", width=80),
    "다음달수익률(%)": st.column_config.NumberColumn("다음달수익", format="%.1f%%", width=85), 
}

st.title("📁 미국 대형주 월별 모멘텀 기록보관소")

folder, prefix = "archive_us", "momentum_us_"
files = sorted(glob.glob(f"{folder}/{prefix}*.csv"), reverse=True)

if not files:
    st.info("미국 시장 기록이 없습니다.")
else:
    file_map = {f"📅 {os.path.basename(f).replace(prefix, '').replace('.csv', '').split('_')[0]}년 {os.path.basename(f).replace(prefix, '').replace('.csv', '').split('_')[1]}월 성적표": f for f in files}
    selected_file = file_map[st.selectbox("조회할 달을 선택하세요", list(file_map.keys()))]

    df = pd.read_csv(selected_file, dtype={'종목코드': str})
    df.columns = df.columns.str.replace(' ', '')
    
    ref_col = '기준일(월말)' if '기준일(월말)' in df.columns else '기준일'
    target_date_str = df[ref_col].iloc[0]
    st.success(f"✅ 이 리스트는 **{target_date_str}** 종가를 기준으로 추출되었으며, **다음달 실제 투자 수익률**을 보여줍니다.")

    # ⭐ [업데이트 2] 지수 이동평균선 현황판 및 투자 신호 배지 표시
    ma_df = get_index_ma_status(target_date_str)
    if not ma_df.empty:
        sp500_row = ma_df.iloc[0] # S&P 500 기준
        sp500_curr = sp500_row['base_price']
        sp500_200ma = sp500_row['200일선']
        
        if sp500_curr >= sp500_200ma:
            status_html = f'<span style="background-color: #E8F5E9; color: #2E7D32; padding: 4px 10px; border-radius: 6px; font-size: 1.1rem; margin-left: 15px; vertical-align: middle;">✅ 투자 진행 (현재가 > 200일선)</span>'
        else:
            status_html = f'<span style="background-color: #FFEBEE; color: #C62828; padding: 4px 10px; border-radius: 6px; font-size: 1.1rem; margin-left: 15px; vertical-align: middle;">🛑 투자 중지 (현재가 < 200일선)</span>'
            
        st.markdown(f"### 📊 주요 지수 이동평균선 현황 (기준일: {target_date_str}){status_html}", unsafe_allow_html=True)
        st.dataframe(
            style_index_ma(ma_df), 
            use_container_width=True, 
            hide_index=True, 
            column_order=["지수_L", "현재가_L", "20일선", "60일선", "120일선", "150일선", "200일선"],
            column_config=ma_config
        )
    else:
        st.markdown(f"### 📊 주요 지수 이동평균선 현황 (기준일: {target_date_str})")
        
    st.markdown("<br>", unsafe_allow_html=True)

    for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '3-1개월(%)', '6-1개월(%)', '12-1개월(%)', '모멘텀스코어', '다음달수익률(%)']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)

    if '12-1개월(%)' not in df.columns and '12개월(%)' in df.columns and '1개월(%)' in df.columns:
        df['12-1개월(%)'] = df['12개월(%)'] - df['1개월(%)']
    if '6-1개월(%)' not in df.columns and '6개월(%)' in df.columns and '1개월(%)' in df.columns:
        df['6-1개월(%)'] = df['6개월(%)'] - df['1개월(%)']
    if '3-1개월(%)' not in df.columns and '3개월(%)' in df.columns and '1개월(%)' in df.columns:
        df['3-1개월(%)'] = df['3개월(%)'] - df['1개월(%)']

    if '시장' not in df.columns: df['시장'] = 'S&P 500'
    df['통합티커'] = df['시장'].astype(str) + ":" + df['종목코드'].astype(str)
    df['종목명_L'] = df.apply(lambda r: f"https://finance.yahoo.com/chart/{str(r['종목코드']).replace('.', '-')}#{r['종목명']}", axis=1)

    # ⭐ 모멘텀 스코어 상위 8개 종목 추출
    top8_momentum_codes = df.sort_values('모멘텀스코어', ascending=False).head(8)['종목코드'].tolist()

    top10_12_1 = df.sort_values('12-1개월(%)', ascending=False).head(10)
    top10_6_1 = df.sort_values('6-1개월(%)', ascending=False).head(10)
    top10_3_1 = df.sort_values('3-1개월(%)', ascending=False).head(10)

    overlap_12_6 = top10_12_1[top10_12_1['종목코드'].isin(top10_6_1['종목코드'])].sort_values('6-1개월(%)', ascending=False).copy()
    overlap_6_3 = top10_6_1[top10_6_1['종목코드'].isin(top10_3_1['종목코드'])].sort_values('6-1개월(%)', ascending=False).copy()

    # --- 상단: 교집합 ---
    c_over1, c_over2 = st.columns(2)
    
    with c_over1:
        if not overlap_12_6.empty:
            avg_all_12_6 = overlap_12_6['다음달수익률(%)'].mean()
            avg_t5_12_6 = overlap_12_6.head(5)['다음달수익률(%)'].mean()
            avg_t10_12_6 = overlap_12_6.head(10)['다음달수익률(%)'].mean()
        else:
            avg_all_12_6 = avg_t5_12_6 = avg_t10_12_6 = np.nan
            
        header_html_12_6 = f"""
        <div class="overlap-header">
            🔥 12-1M & 6-1M 중복<br>
            <div style="font-size: 0.9rem; font-weight: normal; margin-top: 4px; padding-bottom: 2px;">
            Top5: {fmt_ret_html(avg_t5_12_6)} | Top10: {fmt_ret_html(avg_t10_12_6)} | 전체: {fmt_ret_html(avg_all_12_6)}
            </div>
        </div>
        """
        st.markdown(header_html_12_6, unsafe_allow_html=True)
        if not overlap_12_6.empty:
            overlap_12_6['순위'] = range(1, len(overlap_12_6) + 1)
            # 💡 교집합 표 모멘텀 Top8 초록색 반영
            st.dataframe(overlap_12_6.style.apply(style_archive_dataframe, target_codes=top8_momentum_codes, axis=1), 
                         use_container_width=True, hide_index=True,
                         column_order=['순위', '통합티커', '종목명_L', '12-1개월(%)', '6-1개월(%)', '다음달수익률(%)'], column_config=base_config)
        else: st.info("중복 없음")

    with c_over2:
        if not overlap_6_3.empty:
            avg_all_6_3 = overlap_6_3['다음달수익률(%)'].mean()
            avg_t5_6_3 = overlap_6_3.head(5)['다음달수익률(%)'].mean()
            avg_t10_6_3 = overlap_6_3.head(10)['다음달수익률(%)'].mean()
        else:
            avg_all_6_3 = avg_t5_6_3 = avg_t10_6_3 = np.nan
            
        header_html_6_3 = f"""
        <div class="overlap-header">
            ⚡ 6-1M & 3-1M 중복<br>
            <div style="font-size: 0.9rem; font-weight: normal; margin-top: 4px; padding-bottom: 2px;">
            Top5: {fmt_ret_html(avg_t5_6_3)} | Top10: {fmt_ret_html(avg_t10_6_3)} | 전체: {fmt_ret_html(avg_all_6_3)}
            </div>
        </div>
        """
        st.markdown(header_html_6_3, unsafe_allow_html=True)
        if not overlap_6_3.empty:
            overlap_6_3['순위'] = range(1, len(overlap_6_3) + 1)
            # 💡 교집합 표 모멘텀 Top8 초록색 반영
            st.dataframe(overlap_6_3.style.apply(style_archive_dataframe, target_codes=top8_momentum_codes, axis=1), 
                         use_container_width=True, hide_index=True,
                         column_order=['순위', '통합티커', '종목명_L', '6-1개월(%)', '3-1개월(%)', '다음달수익률(%)'], column_config=base_config)
        else: st.info("중복 없음")

    # --- 중단: 상위 30위 ---
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    
    sub_config = base_config.copy()
    sub_config["순위"] = st.column_config.NumberColumn("순위", format="%d", width=35)
    sub_config["통합티커"] = st.column_config.TextColumn("티커", width=90)
    sub_config["종목명_L"] = st.column_config.LinkColumn("종목명", display_text=r"#(.+)", width=110) 
    sub_config["12-1개월(%)"] = st.column_config.NumberColumn("12-1", format="%.1f%%", width=75)
    sub_config["6-1개월(%)"] = st.column_config.NumberColumn("6-1", format="%.1f%%", width=75)
    sub_config["3-1개월(%)"] = st.column_config.NumberColumn("3-1", format="%.1f%%", width=75)
    sub_config["다음달수익률(%)"] = st.column_config.NumberColumn("다음달수익", format="%.1f%%", width=85) 

    for col, title, sort_col in zip([col1, col2, col3], 
                                   ["🏆 12-1개월 상위 30", "🏆 6-1개월 상위 30", "🏆 3-1개월 상위 30"], 
                                   ["12-1개월(%)", "6-1개월(%)", "3-1개월(%)"]):
        with col:
            df_sub = df.sort_values(sort_col, ascending=False).head(30).copy()
            df_sub['순위'] = range(1, 31)
            
            t10_ret = df_sub.head(10)['다음달수익률(%)'].mean()
            t20_ret = df_sub.head(20)['다음달수익률(%)'].mean()
            t30_ret = df_sub.head(30)['다음달수익률(%)'].mean()
            
            header_html = f"""
            <div class="section-header">
                {title}<br>
                <div style="font-size: 0.9rem; font-weight: normal; margin-top: 4px; padding-bottom: 2px;">
                Top10: {fmt_ret_html(t10_ret)} | Top20: {fmt_ret_html(t20_ret)} | Top30: {fmt_ret_html(t30_ret)}
                </div>
            </div>
            """
            st.markdown(header_html, unsafe_allow_html=True)
            
            sub_order = ['순위', '통합티커', '종목명_L', sort_col, '다음달수익률(%)']
            sub_order = [c for c in sub_order if c in df_sub.columns or c == '순위']
            # 💡 30위 표 모멘텀 Top8 초록색 반영
            st.dataframe(df_sub.style.apply(style_archive_dataframe, target_codes=top8_momentum_codes, axis=1), 
                         use_container_width=True, height=450, hide_index=True,
                         column_order=sub_order, column_config=sub_config)

    # --- 하단: 전체 ---
    st.markdown("---")
    st.markdown(f"### 📊 미국 대형주 상위 300종목 전체 기록 (기준: {target_date_str})")
    
    df['순위'] = range(1, len(df) + 1)
    full_order = ['순위', '통합티커', '종목명_L', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '3-1개월(%)', '6-1개월(%)', '12-1개월(%)', '모멘텀스코어', '다음달수익률(%)']
    full_order = [col for col in full_order if col in df.columns or col == '순위']
    
    # 💡 전체 표 모멘텀 Top8 초록색 반영
    st.dataframe(df.style.apply(style_archive_dataframe, target_codes=top8_momentum_codes, axis=1), 
                 use_container_width=True, height=600, hide_index=True,
                 column_order=full_order, column_config=base_config)
