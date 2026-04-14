import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os
import glob
import numpy as np
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="S&P 500 모멘텀 기록보관소", layout="wide")

# CSS: 가독성 및 레이아웃 최적화
st.markdown("""
    <style>
    .block-container { padding-top: 2.5rem !important; }
    h1 { font-size: 2.2rem !important; font-weight: 800; margin-bottom: 10px; }
    
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
        margin-top: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- [2. 헬퍼 함수] ---
@st.cache_data(ttl=3600, show_spinner=False)
def get_index_ma_status(target_date_str):
    indices = {'S&P 500': 'US500', 'NASDAQ': 'IXIC'}
    target_date = pd.to_datetime(target_date_str)
    start_date = target_date - timedelta(days=400) 
    
    fetch_end_date = target_date + timedelta(days=2)
    
    res = []
    for name, code in indices.items():
        try:
            df = fdr.DataReader(code, start_date, fetch_end_date)
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
                    if val < price: styles[i] = 'color: #EF4444; font-weight: bold;' 
                    elif val > price: styles[i] = 'color: #3B82F6; font-weight: bold;' 
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

def highlight_target_codes(row, target_codes, bg_color="#E8F5E9", text_color="#2E7D32"):
    styles = [''] * len(row)
    code = row.get('종목코드')
    
    if code in target_codes:
        if '종목명_L' in row.index:
            name_idx = row.index.get_loc('종목명_L')
            styles[name_idx] = f'background-color: {bg_color}; color: {text_color}; font-weight: bold; border-radius: 4px;'
            
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

# 💡 [백테스트 엔진] S&P 500 전용 데이터 전처리 (200일선 타이밍 포함)
@st.cache_data
def prep_sp500_backtest_data(files):
    monthly_data = []
    
    dates = []
    file_map = {}
    for f in files:
        fname = os.path.basename(f)
        date_part = fname.replace("momentum_sp500_", "").replace(".csv", "")
        dates.append(date_part)
        file_map[date_part] = f
        
    dates.sort()
    
    all_dfs = {}
    min_date = "2099-01-01"
    max_date = "1900-01-01"
    
    for d_str in dates:
        df = pd.read_csv(file_map[d_str], dtype={'종목코드': str})
        df.columns = df.columns.str.replace(' ', '')
        for c in ['12-1개월(%)', '6-1개월(%)', '3-1개월(%)', '다음달수익률(%)']:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
                
        ref_col = '기준일(월말)' if '기준일(월말)' in df.columns else '기준일'
        base_date = df[ref_col].iloc[0]
        
        if base_date < min_date: min_date = base_date
        if base_date > max_date: max_date = base_date
        
        all_dfs[d_str] = {'base_date': base_date, 'df': df}
        
    # S&P 500 (US500) 200일 이동평균선 계산용 데이터 로드
    start_dt = pd.to_datetime(min_date) - timedelta(days=400)
    end_dt = pd.to_datetime(max_date) + timedelta(days=30)
    try:
        sp500 = fdr.DataReader('US500', start_dt, end_dt)
        sp500['200MA'] = sp500['Close'].rolling(200).mean()
    except:
        sp500 = pd.DataFrame()
        
    for d_str in dates:
        data = all_dfs[d_str]
        base_date = pd.to_datetime(data['base_date'])
        df = data['df']
        
        is_bad = False
        if not sp500.empty:
            sp_sub = sp500[sp500.index <= base_date]
            if not sp_sub.empty:
                curr_p = sp_sub['Close'].iloc[-1]
                ma200 = sp_sub['200MA'].iloc[-1]
                if pd.notna(ma200) and curr_p < ma200:
                    is_bad = True
                    
        top10_12_1 = df.sort_values('12-1개월(%)', ascending=False).head(10)
        top10_6_1 = df.sort_values('6-1개월(%)', ascending=False).head(10)
        top10_3_1 = df.sort_values('3-1개월(%)', ascending=False).head(10)

        overlap_12_6 = top10_12_1[top10_12_1['종목코드'].isin(top10_6_1['종목코드'])].sort_values('6-1개월(%)', ascending=False)
        overlap_6_3 = top10_6_1[top10_6_1['종목코드'].isin(top10_3_1['종목코드'])].sort_values('6-1개월(%)', ascending=False)
        
        ret_dict = dict(zip(df['종목코드'], df['다음달수익률(%)']))
        
        inv_dt = base_date + pd.DateOffset(months=1)
        
        monthly_data.append({
            '투자월': f"{inv_dt.year}-{inv_dt.month:02d}",
            'is_bad': is_bad,
            'o_12_6_codes': overlap_12_6['종목코드'].tolist(),
            'o_6_3_codes': overlap_6_3['종목코드'].tolist(),
            'ret_dict': ret_dict
        })
        
    return monthly_data


# --- [3. 메인 화면 구성] ---
st.title("📁 S&P 500 모멘텀 기록보관소")

folder, prefix = "archive_sp500", "momentum_sp500_"
files = glob.glob(f"{folder}/{prefix}*.csv")

if not files:
    st.info("데이터가 없습니다. archive_sp500 폴더를 확인해주세요.")
else:
    # 💡 탭 구성
    tab_detail, tab_summary = st.tabs(["📅 월별 상세 분석", "📈 전략 누적 성과 (백테스트)"])

    with tab_detail:
        data_struct = {}
        for f in files:
            fname = os.path.basename(f)
            try:
                date_part = fname.replace(prefix, "").replace(".csv", "")
                year, month = date_part.split('_')
                if year not in data_struct: data_struct[year] = []
                data_struct[year].append(month)
            except: continue

        sorted_years = sorted(data_struct.keys(), reverse=True)
        
        col_y, col_m, _ = st.columns([1, 1, 4])
        with col_y:
            selected_year = st.selectbox("📅 연도", sorted_years)
        with col_m:
            available_months = sorted(data_struct[selected_year], key=lambda x: int(x))
            selected_month = st.selectbox("🌙 월", available_months)

        target_file = f"{folder}/{prefix}{selected_year}_{selected_month}.csv"
        df = pd.read_csv(target_file, dtype={'종목코드': str})
        df.columns = df.columns.str.replace(' ', '')
        
        ref_col = '기준일(월말)' if '기준일(월말)' in df.columns else '기준일'
        target_date_str = df[ref_col].iloc[0]
        st.success(f"✅ 이 리스트는 **{selected_year}년 {selected_month}월 ({target_date_str})** 종가를 기준으로 추출되었으며, **다음달 실제 투자 수익률**을 보여줍니다.")

        ma_df = get_index_ma_status(target_date_str)
        if not ma_df.empty:
            sp500_row = ma_df.iloc[0]
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

        top8_momentum_codes = df.sort_values('모멘텀스코어', ascending=False).head(8)['종목코드'].tolist()

        if '시장' not in df.columns: df['시장'] = 'S&P 500'
        df['통합티커'] = df['시장'].astype(str) + ":" + df['종목코드'].astype(str)
        df['종목명_L'] = df.apply(lambda r: f"https://finance.yahoo.com/chart/{str(r['종목코드']).replace('.', '-')}#{r['종목명']}", axis=1)

        top10_12_1 = df.sort_values('12-1개월(%)', ascending=False).head(10)
        top10_6_1 = df.sort_values('6-1개월(%)', ascending=False).head(10)
        top10_3_1 = df.sort_values('3-1개월(%)', ascending=False).head(10)

        overlap_12_6 = top10_12_1[top10_12_1['종목코드'].isin(top10_6_1['종목코드'])].sort_values('6-1개월(%)', ascending=False).copy()
        overlap_6_3 = top10_6_1[top10_6_1['종목코드'].isin(top10_3_1['종목코드'])].sort_values('6-1개월(%)', ascending=False).copy()

        c_over1, c_over2 = st.columns(2)
        
        with c_over1:
            if not overlap_12_6.empty:
                avg_all_12_6 = overlap_12_6['다음달수익률(%)'].mean()
                avg_t5_12_6 = overlap_12_6.head(5)['다음달수익률(%)'].mean()
                avg_t10_12_6 = overlap_12_6.head(10)['다음달수익률(%)'].mean()
            else: avg_all_12_6 = avg_t5_12_6 = avg_t10_12_6 = np.nan
                
            header_html_12_6 = f'<div class="overlap-header">🔥 12-1M & 6-1M 중복<br><div style="font-size: 0.9rem; font-weight: normal; margin-top: 4px; padding-bottom: 2px;">Top5: {fmt_ret_html(avg_t5_12_6)} | Top10: {fmt_ret_html(avg_t10_12_6)} | 전체: {fmt_ret_html(avg_all_12_6)}</div></div>'
            st.markdown(header_html_12_6, unsafe_allow_html=True)
            if not overlap_12_6.empty:
                overlap_12_6['순위'] = range(1, len(overlap_12_6) + 1)
                st.dataframe(overlap_12_6.style.apply(highlight_target_codes, target_codes=top8_momentum_codes, axis=1), 
                             use_container_width=True, hide_index=True,
                             column_order=['순위', '통합티커', '종목명_L', '12-1개월(%)', '6-1개월(%)', '다음달수익률(%)'], column_config=base_config)
            else: st.info("중복 없음")

        with c_over2:
            if not overlap_6_3.empty:
                avg_all_6_3 = overlap_6_3['다음달수익률(%)'].mean()
                avg_t5_6_3 = overlap_6_3.head(5)['다음달수익률(%)'].mean()
                avg_t10_6_3 = overlap_6_3.head(10)['다음달수익률(%)'].mean()
            else: avg_all_6_3 = avg_t5_6_3 = avg_t10_6_3 = np.nan
                
            header_html_6_3 = f'<div class="overlap-header">⚡ 6-1M & 3-1M 중복<br><div style="font-size: 0.9rem; font-weight: normal; margin-top: 4px; padding-bottom: 2px;">Top5: {fmt_ret_html(avg_t5_6_3)} | Top10: {fmt_ret_html(avg_t10_6_3)} | 전체: {fmt_ret_html(avg_all_6_3)}</div></div>'
            st.markdown(header_html_6_3, unsafe_allow_html=True)
            if not overlap_6_3.empty:
                overlap_6_3['순위'] = range(1, len(overlap_6_3) + 1)
                st.dataframe(overlap_6_3.style.apply(highlight_target_codes, target_codes=top8_momentum_codes, axis=1), 
                             use_container_width=True, hide_index=True,
                             column_order=['순위', '통합티커', '종목명_L', '6-1개월(%)', '3-1개월(%)', '다음달수익률(%)'], column_config=base_config)
            else: st.info("중복 없음")

        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        
        sub_config = base_config.copy()
        sub_config["순위"] = st.column_config.NumberColumn("순위", format="%d", width=35)
        sub_config["종목명_L"] = st.column_config.LinkColumn("종목명", display_text=r"#(.+)", width=110) 

        for col, title, sort_col in zip([col1, col2, col3], 
                                       ["🏆 12-1개월 상위 30", "🏆 6-1개월 상위 30", "🏆 3-1개월 상위 30"], 
                                       ["12-1개월(%)", "6-1개월(%)", "3-1개월(%)"]):
            with col:
                df_sub = df.sort_values(sort_col, ascending=False).head(30).copy()
                df_sub['순위'] = range(1, 31)
                
                t10_ret = df_sub.head(10)['다음달수익률(%)'].mean()
                t20_ret = df_sub.head(20)['다음달수익률(%)'].mean()
                t30_ret = df_sub.head(30)['다음달수익률(%)'].mean()
                
                header_html = f'<div class="section-header">{title}<br><div style="font-size: 0.9rem; font-weight: normal; margin-top: 4px; padding-bottom: 2px;">Top10: {fmt_ret_html(t10_ret)} | Top20: {fmt_ret_html(t20_ret)} | Top30: {fmt_ret_html(t30_ret)}</div></div>'
                st.markdown(header_html, unsafe_allow_html=True)
                
                sub_order = ['순위', '통합티커', '종목명_L', sort_col, '다음달수익률(%)']
                st.dataframe(df_sub.style.apply(highlight_target_codes, target_codes=top8_momentum_codes, axis=1), 
                             use_container_width=True, height=450, hide_index=True,
                             column_order=sub_order, column_config=sub_config)

        st.markdown("---")
        st.markdown(f"### 📊 S&P 500 전체 기록 (기준: {target_date_str})")
        
        df['순위'] = range(1, len(df) + 1)
        full_order = ['순위', '통합티커', '종목명_L', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '3-1개월(%)', '6-1개월(%)', '12-1개월(%)', '모멘텀스코어', '다음달수익률(%)']
        
        st.dataframe(df.style.apply(highlight_target_codes, target_codes=top8_momentum_codes, axis=1), 
                     use_container_width=True, height=600, hide_index=True,
                     column_order=full_order, column_config=base_config)

    # 💡 [백테스트 탭]
    with tab_summary:
        st.markdown("### 📈 S&P 500 중복 모멘텀 전략 백테스트 시뮬레이터")
        
        with st.spinner("백테스트 엔진을 구동 중입니다... (최초 1회만 수 초 소요)"):
            monthly_data = prep_sp500_backtest_data(files)
            
        c1, c2, c3 = st.columns([1, 1, 1.2])
        with c1:
            top_n_1 = st.slider("🔥 12-1 & 6-1 매수 종목 수", min_value=1, max_value=10, value=5)
        with c2:
            top_n_2 = st.slider("⚡ 6-1 & 3-1 매수 종목 수", min_value=1, max_value=10, value=5)
        with c3:
            st.markdown("<div style='margin-top: 35px;'></div>", unsafe_allow_html=True)
            apply_timing = st.checkbox("🛑 마켓타이밍 적용 (S&P500 200일선 이탈 시 현금 100%)", value=True)
        
        records = []
        for m in monthly_data:
            mult = 0.0 if (apply_timing and m['is_bad']) else 1.0
            is_invested = mult > 0.0  
            
            c1_codes = m['o_12_6_codes'][:top_n_1]
            c2_codes = m['o_6_3_codes'][:top_n_2]
            
            r1 = [m['ret_dict'].get(c, 0.0) for c in c1_codes]
            r2 = [m['ret_dict'].get(c, 0.0) for c in c2_codes]
            
            avg_r1 = (sum(r1) / len(r1) * mult) if r1 else 0.0
            avg_r2 = (sum(r2) / len(r2) * mult) if r2 else 0.0
            
            combined_codes = list(set(c1_codes + c2_codes))
            rc = [m['ret_dict'].get(c, 0.0) for c in combined_codes]
            avg_rc = (sum(rc) / len(rc) * mult) if rc else 0.0
            
            ret_ensemble = (avg_r1 + avg_r2) / 2
            
            records.append({
                '투자월': m['투자월'],
                'invested': is_invested,
                f'🔥 12-1 & 6-1 (Top {top_n_1})': avg_r1,
                f'⚡ 6-1 & 3-1 (Top {top_n_2})': avg_r2,
                '앙상블 (전략 50:50)': ret_ensemble,
                '통합 (모든종목 1/N)': avg_rc
            })
            
        df_summary = pd.DataFrame(records)
        strategy_cols = [c for c in df_summary.columns if c not in ['투자월', 'invested']]
        
        df_cum = (1 + df_summary.set_index('투자월')[strategy_cols] / 100).cumprod() * 100
        
        first_month = pd.to_datetime(df_summary['투자월'].iloc[0]) - pd.DateOffset(months=1)
        first_month_str = f"{first_month.year}-{first_month.month:02d}"
        df_cum.loc[first_month_str] = 100
        df_cum = df_cum.sort_index()

        df_melt = df_cum.reset_index().melt(id_vars='투자월', var_name='전략', value_name='누적수익률')
        
        fig = px.line(df_melt, x='투자월', y='누적수익률', color='전략')
        fig.update_layout(
            hovermode="x unified",
            dragmode="pan", 
            xaxis_title="투자 기준 월",
            yaxis_title="누적 자산 (초기 자본 = 100)",
            legend_title_text="투자 전략",
            margin=dict(l=0, r=0, t=20, b=0)
        )
        fig.update_xaxes(fixedrange=False)
        fig.update_yaxes(fixedrange=False)
        fig.update_traces(hovertemplate="<b>%{data.name}</b><br>누적수익률: %{y:.2f}<extra></extra>")
        
        st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True, 'displayModeBar': True})
        
        st.markdown("#### 📊 전략별 핵심 통계 (초기 자본 100 기준)")
        
        stats = []
        total_months = len(df_summary)
        invested_months = df_summary['invested'].sum()
        invest_ratio = (invested_months / total_months) * 100 if total_months > 0 else 0

        for col in strategy_cols:
            total_ret = df_cum[col].iloc[-1] - 100
            
            if invested_months > 0:
                win_months = (df_summary.loc[df_summary['invested'], col] > 0).sum()
                win_rate = (win_months / invested_months) * 100
                avg_ret = df_summary.loc[df_summary['invested'], col].mean()
            else:
                win_months = 0
                win_rate = 0.0
                avg_ret = 0.0
            
            roll_max = df_cum[col].cummax()
            drawdown = (df_cum[col] / roll_max) - 1.0
            mdd = drawdown.min() * 100
            
            stats.append({
                "전략명": col,
                "총 누적수익률": f"{total_ret:,.1f}%",
                "MDD (최대낙폭)": f"{mdd:.1f}%",
                "투자월 비율": f"{invest_ratio:.1f}% ({invested_months}/{total_months}개월)", 
                "월별 승률": f"{win_rate:.1f}% ({win_months}승 / {invested_months}개월)", 
                "평균 수익률(투자월)": f"{avg_ret:.2f}%"
            })
            
        df_stats = pd.DataFrame(stats)
        
        def style_stats(x):
            if isinstance(x, str) and '%' in x:
                if '-' in x: return 'color: #1976D2; font-weight:bold;'
                elif x != '0.0%': return 'color: #D32F2F; font-weight:bold;'
            return ''
            
        try:
            styled_stats = df_stats.style.map(style_stats, subset=['총 누적수익률', 'MDD (최대낙폭)'])
        except AttributeError:
            styled_stats = df_stats.style.applymap(style_stats, subset=['총 누적수익률', 'MDD (최대낙폭)'])
            
        st.dataframe(styled_stats, use_container_width=True, hide_index=True)
        
        with st.expander("📝 월별 수익률 상세 기록 보기"):
            display_df = df_summary.drop(columns=['invested']).set_index('투자월')
            st.dataframe(display_df.style.format("{:.2f}%"), use_container_width=True)
