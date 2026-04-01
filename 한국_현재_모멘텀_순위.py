import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import os

st.set_page_config(page_title="한국 모멘텀 순위", layout="wide")

# CSS: 레이아웃 설정
st.markdown("""<style>.block-container { padding-top: 2.5rem !important; } h1 { font-size: 2rem !important; } .stTabs [data-baseweb="tab"] { font-size: 18px; font-weight: bold; }</style>""", unsafe_allow_html=True)

# 공통 스타일 함수 (탭 1, 2용)
def apply_custom_styling(row, idx_df):
    styles = [''] * len(row)
    if '시장' in row and row['시장'] in idx_df.index:
        idx_r = idx_df.loc[row['시장']]
        for col_name in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
            if col_name in row.index:
                col_idx = row.index.get_loc(col_name)
                if row[col_name] < idx_r[col_name]:
                    styles[col_idx] = 'background-color: #E3F2FD; color: #0047AB;'
    if '전일거래량' in row.index:
        vol_idx = row.index.get_loc('전일거래량')
        if row['전일거래량'] >= 10000000:
            styles[vol_idx] = 'background-color: #FFEBEE; color: #B71C1C; font-weight: bold;'
    return styles

# ⭐ 탭 3 전용 스타일 함수 (교집합 하이라이트 포함)
def apply_k200_styling(row, idx_df, common_codes):
    styles = [''] * len(row)
    # 1. 지수 비교 하이라이트 (파란색)
    if '시장' in row and row['시장'] in idx_df.index:
        idx_r = idx_df.loc[row['시장']]
        for col_name in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
            if col_name in row.index:
                col_idx = row.index.get_loc(col_name)
                if row[col_name] < idx_r[col_name]:
                    styles[col_idx] = 'background-color: #E3F2FD; color: #0047AB;'
                    
    # 2. 교집합(양쪽 표에 모두 있는 종목) 종목명 하이라이트 (노란색)
    if '종목명_L' in row.index and '종목코드' in row.index:
        if row['종목코드'] in common_codes:
            name_idx = row.index.get_loc('종목명_L')
            styles[name_idx] = 'background-color: #FFF59D; color: #D84315; font-weight: bold;'
    return styles

@st.cache_data(ttl=3600)
def get_idx_kr(target_date=None):
    indices = {'KOSPI': 'KS11', 'KOSDAQ': 'KQ11'}
    today = datetime.today()
    res = []
    for name, code in indices.items():
        try:
            df = fdr.DataReader(code, today - pd.DateOffset(months=16), today)
            curr_val = df.loc[df.index <= target_date]['Close'].iloc[-1] if target_date else df['Close'].iloc[-1]
            last_idx_date = df.index[df.index <= (target_date if target_date else today)][-1]
            def get_ret(m):
                ref_day = (last_idx_date.replace(day=1) - pd.DateOffset(months=m-1)) - timedelta(days=1)
                p_df = df[df.index <= ref_day]
                return round((curr_val - p_df['Close'].iloc[-1]) / p_df['Close'].iloc[-1] * 100, 1) if not p_df.empty else 0.0
            res.append({'시장': name, '현재가': curr_val, '1개월(%)': get_ret(1), '3개월(%)': get_ret(3), '6개월(%)': get_ret(6), '12개월(%)': get_ret(12)})
        except: pass
    return pd.DataFrame(res).set_index('시장')

tab1, tab2, tab3 = st.tabs(["📅 전월 말일 기준", "🕒 오늘(데일리) 기준", "🎯 KOSPI 200 강세 종목"])

with tab1:
    f_kr = 'data/momentum_data.csv'
    if os.path.exists(f_kr):
        df_kr = pd.read_csv(f_kr, dtype={'종목코드': str})
        b_date_str = df_kr['기준일(월말)'].iloc[0]
        st.title(f"📊 한국 모멘텀 (기준: {b_date_str})")
        idx_kr = get_idx_kr(pd.to_datetime(b_date_str))
        if not idx_kr.empty: 
            idx_disp = idx_kr.reset_index().copy()
            idx_disp['현재가'] = idx_disp['현재가'].map('{:,.0f}'.format)
            for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
                idx_disp[c] = idx_disp[c].map('{:+.1f}%'.format)
            st.table(idx_disp)
        
        st.markdown("---")
        try:
            curr_dt = datetime.strptime(b_date_str, '%Y-%m-%d')
            prev_month_dt = curr_dt.replace(day=1) - timedelta(days=1)
            prev_ym = prev_month_dt.strftime('%Y_%m')
            f_prev_archive = f'archive/momentum_{prev_ym}.csv'
            if os.path.exists(f_prev_archive):
                df_prev = pd.read_csv(f_prev_archive, dtype={'종목코드': str})
                prev_rank_map = {code: i+1 for i, code in enumerate(df_prev['종목코드'])}
                df_kr['전달순위'] = df_kr['종목코드'].map(prev_rank_map)
            else: df_kr['전달순위'] = None
        except: df_kr['전달순위'] = None

        df_kr.index = range(1, len(df_kr) + 1)
        df_kr['통합티커'] = df_kr['시장'] + ":" + df_kr['종목코드'].str.zfill(6)
        df_kr['종목명_L'] = df_kr.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)

        st.dataframe(df_kr.style.apply(apply_custom_styling, idx_df=idx_kr, axis=1), use_container_width=True, height=560, 
                     column_order=['통합티커', '종목명_L', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어', '전달순위'], 
                     column_config={
                         "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), 
                         "기준가": st.column_config.NumberColumn("현재가", format="%,d"), 
                         "1개월(%)": st.column_config.NumberColumn(format="%.1f"), 
                         "3개월(%)": st.column_config.NumberColumn(format="%.1f"), 
                         "6개월(%)": st.column_config.NumberColumn(format="%.1f"), 
                         "12개월(%)": st.column_config.NumberColumn(format="%.1f"), 
                         "모멘텀스코어": st.column_config.NumberColumn(format="%.1f"),
                         "전달순위": st.column_config.NumberColumn("전달 순위", format="%d위")
                     })

with tab2:
    f_daily = 'data/momentum_data_daily.csv'
    f_monthly_ref = 'data/momentum_data.csv'
    if os.path.exists(f_daily):
        df_d = pd.read_csv(f_daily, dtype={'종목코드': str})
        if os.path.exists(f_monthly_ref):
            df_m_ref = pd.read_csv(f_monthly_ref, dtype={'종목코드': str})
            rank_map = {code: i+1 for i, code in enumerate(df_m_ref['종목코드'])}
            df_d['전월순위'] = df_d['종목코드'].map(rank_map)
        else: df_d['전월순위'] = None

        st.title(f"🕒 데일리 모멘텀 (기준: {df_d['기준일'].iloc[0]})")
        idx_now = get_idx_kr()
        if not idx_now.empty: 
            idx_disp_now = idx_now.reset_index().copy()
            idx_disp_now['현재가'] = idx_disp_now['현재가'].map('{:,.0f}'.format)
            for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
                idx_disp_now[c] = idx_disp_now[c].map('{:+.1f}%'.format)
            st.table(idx_disp_now)
        
        st.markdown("---")
        if '전일거래량' not in df_d.columns: df_d['전일거래량'] = 0 
        df_d.index = range(1, len(df_d) + 1)
        df_d['통합티커'] = df_d['시장'] + ":" + df_d['종목코드'].str.zfill(6)
        df_d['종목명_L'] = df_d.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)

        st.dataframe(df_d.style.apply(apply_custom_styling, idx_df=idx_now, axis=1), use_container_width=True, height=560, 
                     column_order=['통합티커', '종목명_L', '기준가', '전일거래량', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어', '전월순위'], 
                     column_config={
                         "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), 
                         "기준가": st.column_config.NumberColumn("현재가", format="%,d"), 
                         "전일거래량": st.column_config.NumberColumn("전일거래량", format="%,d"), 
                         "1개월(%)": st.column_config.NumberColumn(format="%.1f"), 
                         "3개월(%)": st.column_config.NumberColumn(format="%.1f"), 
                         "6개월(%)": st.column_config.NumberColumn(format="%.1f"), 
                         "12개월(%)": st.column_config.NumberColumn(format="%.1f"), 
                         "모멘텀스코어": st.column_config.NumberColumn(format="%.1f"),
                         "전월순위": st.column_config.NumberColumn("전월 순위", format="%d위")
                     })



# --- 탭 3: KOSPI 200 집중 분석 ---
with tab3:
    if os.path.exists(f_kr):
        df_k200 = pd.read_csv(f_kr, dtype={'종목코드': str})
        b_date_str = df_k200['기준일(월말)'].iloc[0] if '기준일(월말)' in df_k200.columns else "날짜 정보 없음"
        
        st.title(f"🎯 KOSPI 200 집중 분석 (기준: {b_date_str})")
        
        # ⭐ [해결 포인트] 변수를 여기서 확실하게 생성합니다.
        # 지수 정보를 가져와서 idx_now_k200에 저장합니다.
        target_dt = pd.to_datetime(b_date_str) if b_date_str != "날짜 정보 없음" else None
        idx_now_k200 = get_idx_kr(target_dt) 
        
        # 지수 정보가 있을 때만 화면에 표로 보여줌
        if not idx_now_k200.empty: 
            idx_disp_k200 = idx_now_k200.reset_index().copy()
            idx_disp_k200['현재가'] = idx_disp_k200['현재가'].map('{:,.0f}'.format)
            for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
                idx_disp_k200[c] = idx_disp_k200[c].map('{:+.1f}%'.format)
            st.table(idx_disp_k200)
            
        st.markdown("---")

        # [컬럼 찾기 및 데이터 구성 로직...]
        c_1m = next((c for c in df_k200.columns if '1개월' in c), None)
        c_3m = next((c for c in df_k200.columns if '3개월' in c), None)
        c_6m = next((c for c in df_k200.columns if '6개월' in c), None)
        c_12m = next((c for c in df_k200.columns if '12개월' in c), None)
        m_col = next((c for c in df_k200.columns if 'mar' in c.lower() or '시가' in c), None)

        if not all([c_1m, c_12m]):
            st.error("필수 데이터 컬럼을 찾을 수 없습니다.")
        else:
            # 기초 데이터 필터링 (보통주 & KOSPI 200)
            is_common = df_k200['종목코드'].str.endswith('0')
            is_kospi = (df_k200['시장'] == 'KOSPI') if '시장' in df_k200.columns else True
            df_base = df_k200[is_kospi & is_common].copy()
            
            if m_col: df_base = df_base.sort_values(by=m_col, ascending=False).head(200).copy()
            else: df_base = df_base.head(200).copy()

            # 수치형 변환 및 소수점 1자리 처리
            for c in [c_1m, c_3m, c_6m, c_12m]:
                if c: df_base[c] = pd.to_numeric(df_base[c], errors='coerce').round(1)

            # --- 필터링 로직 (상위 30% 등) ---
            t30_1m = df_base[c_1m].quantile(0.7)
            t30_12m = df_base[c_12m].quantile(0.7)
            t10_1m = df_base[c_1m].quantile(0.9)

            # 퍼펙트 상승/장기 주도 조건
            cond_perf = (df_base[c_1m] >= t30_1m) & (df_base[c_12m] >= t30_12m) & (df_base[c_1m] > 0)
            df_perfect = df_base[cond_perf].copy()
            df_special = df_base[(df_base[c_12m] >= t30_12m) & (df_base[c_1m] >= t10_1m)].copy()

            # 공통 설정
            df_base['통합티커'] = "KOSPI:" + df_base['종목코드'].str.zfill(6)
            df_base['종목명_L'] = df_base.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)
            common_codes = set(df_perfect['종목코드']).intersection(set(df_special['종목코드']))

            k200_config = {
                "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"),
                "기준가": st.column_config.NumberColumn("현재가", format="%,d"),
                c_1m: st.column_config.NumberColumn(format="%.1f"),
                c_12m: st.column_config.NumberColumn(format="%.1f")
            }

            # 표 출력 (여기서 idx_now_k200을 사용합니다)
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("🔥 퍼펙트 상승")
                # 스타일 적용 시 정의된 idx_now_k200을 전달
                st.dataframe(df_perfect.style.apply(apply_k200_styling, idx_df=idx_now_k200, common_codes=common_codes, axis=1), 
                             use_container_width=True, column_order=['통합티커', '종목명_L', c_1m, c_12m], column_config=k200_config)
            
            with col2:
                st.subheader("🚀 장기 주도 & 단기 급등")
                st.dataframe(df_special.style.apply(apply_k200_styling, idx_df=idx_now_k200, common_codes=common_codes, axis=1), 
                             use_container_width=True, column_order=['통합티커', '종목명_L', c_1m, c_12m], column_config=k200_config)

            # 하단 전체 순위
            st.markdown("---")
            st.subheader("🏆 KOSPI 200 시가총액 순위")
            df_full = df_base.copy()
            df_full['순위'] = range(1, len(df_full) + 1)
            df_full = df_full.set_index('순위')
            st.dataframe(df_full.style.apply(apply_k200_styling, idx_df=idx_now_k200, common_codes=common_codes, axis=1),
                         use_container_width=True, height=600, column_order=['통합티커', '종목명_L', m_col, '기준가', c_1m, c_12m], column_config=k200_config)
    else:
        st.warning("데이터 파일을 찾을 수 없습니다.")
