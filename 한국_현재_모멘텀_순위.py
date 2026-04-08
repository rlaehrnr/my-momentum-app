import streamlit as st
import pandas as pd
import os

# --- 기존 CSS 및 기본 설정 등은 유지 ---
# ... (기존 코드) ...

# 💡 [핵심 1] 표 스타일링 함수 (퍼펙트 상승/달리는 말 색상 칠하기)
def apply_k200_styling(row, highlight_codes=None, overlap_codes=None):
    styles = [''] * len(row)
    code = row.get('종목코드')
    
    if code and '종목명_L' in row.index:
        name_idx = row.index.get_loc('종목명_L')
        if overlap_codes and code in overlap_codes:
            # 양쪽 모두 탑 5 (노란 배경, 빨간 글씨)
            styles[name_idx] = 'background-color: #FFF59D; color: #D84315; font-weight: bold;'
        elif highlight_codes and code in highlight_codes:
            # 한 쪽에만 탑 5 (연두 배경, 초록 글씨)
            styles[name_idx] = 'background-color: #E8F5E9; color: #2E7D32; font-weight: bold;'
            
    return styles

# 💡 [핵심 2] 화면을 그리는 메인 엔진 (이 함수 하나로 월간/데일리 모두 처리!)
def render_kospi200_bull(df_raw, target_date_str):
    st.markdown(f"**기준일: {target_date_str}**")
    
    # KOSPI 종목만 필터링 후 시총 상위 200개 추출
    df_k200 = df_raw[df_raw['시장'] == 'KOSPI'].copy() if '시장' in df_raw.columns else df_raw.copy()
    if '시가총액' in df_k200.columns:
        df_k200 = df_k200.sort_values(by='시가총액', ascending=False).head(200)

    # 네이버 링크 생성
    df_k200['통합티커_L'] = df_k200.apply(lambda r: f"https://finance.naver.com/item/main.naver?code={str(r['종목코드']).zfill(6)}#KOSPI:{str(r['종목코드']).zfill(6)}", axis=1)
    df_k200['종목명_L'] = df_k200.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{str(r['종목코드']).zfill(6)}#{r['종목명']}", axis=1)

    # 숫자 데이터 안전 변환
    for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
        if c in df_k200.columns:
            df_k200[c] = pd.to_numeric(df_k200[c], errors='coerce').fillna(0)

    # 하락 종목 수 계산
    neg_1m_cnt = (df_k200['1개월(%)'] < 0).sum()
    neg_3m_cnt = (df_k200['3개월(%)'] < 0).sum()

    # 상위 퍼센트 기준점 계산
    q30 = {c: df_k200[c].quantile(0.7) for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']}
    t10_1m = df_k200['1개월(%)'].quantile(0.9)

    # 1. 퍼펙트 상승 조건
    cond_perf = (df_k200['1개월(%)']>=q30['1개월(%)'])&(df_k200['3개월(%)']>=q30['3개월(%)'])&(df_k200['6개월(%)']>=q30['6개월(%)'])&(df_k200['12개월(%)']>=q30['12개월(%)']) & \
                (df_k200['1개월(%)']>0)&(df_k200['3개월(%)']>0)&(df_k200['6개월(%)']>0)&(df_k200['12개월(%)']>0)
    df_perf = df_k200[cond_perf].sort_values('3개월(%)', ascending=False).copy()

    # 2. 달리는 말 조건
    df_spec = df_k200[(df_k200['12개월(%)']>=q30['12개월(%)']) & (df_k200['1개월(%)']>=t10_1m)].sort_values('1개월(%)', ascending=False).copy()

    # 중복 하이라이트 계산
    top5_perf = df_perf.head(5)['종목코드'].tolist()
    top5_spec = df_spec.head(5)['종목코드'].tolist()
    overlap_top5 = set(top5_perf).intersection(set(top5_spec))

    # 요약 박스 (하락장 경고)
    col1, col2 = st.columns(2)
    with col1: st.metric(label="📉 KOSPI 200 내 1개월 하락", value=f"{neg_1m_cnt}개")
    with col2: st.metric(label="📉 KOSPI 200 내 3개월 하락", value=f"{neg_3m_cnt}개")

    if neg_1m_cnt >= 100 and neg_3m_cnt >= 100:
        st.error("🛑 시장 하락장 경고: 1개월 & 3개월 하락 종목이 모두 100개 이상입니다. 보수적으로 접근하세요.")
    else:
        st.success("✅ 시장 양호: 하락 종목 개수가 안정적인 수준입니다.")

    # 컬럼 포맷 설정
    main_cfg = {
        "통합티커_L": st.column_config.LinkColumn("티커", display_text=r"#(.+)"),
        "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"),
        "1개월(%)": st.column_config.NumberColumn(format="%.1f"),
        "3개월(%)": st.column_config.NumberColumn(format="%.1f"),
        "6개월(%)": st.column_config.NumberColumn(format="%.1f"),
        "12개월(%)": st.column_config.NumberColumn(format="%.1f")
    }

    # 표 출력
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 🔥 퍼펙트 상승")
        if not df_perf.empty:
            st.dataframe(df_perf.style.apply(apply_k200_styling, highlight_codes=top5_perf, overlap_codes=overlap_top5, axis=1),
                         use_container_width=True, hide_index=True,
                         column_order=['통합티커_L', '종목명_L', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)'],
                         column_config=main_cfg)
        else: st.info("조건을 만족하는 종목이 없습니다.")
    with c2:
        st.markdown("### 🐎 달리는 말")
        if not df_spec.empty:
            st.dataframe(df_spec.style.apply(apply_k200_styling, highlight_codes=top5_spec, overlap_codes=overlap_top5, axis=1),
                         use_container_width=True, hide_index=True,
                         column_order=['통합티커_L', '종목명_L', '1개월(%)', '12개월(%)'],
                         column_config=main_cfg)
        else: st.info("조건을 만족하는 종목이 없습니다.")

# =========================================================
# 💡 [핵심 3] 실제 화면에 탭(Tab) 띄우기
# =========================================================
st.title("🇰🇷 KOSPI 200 강세 종목 분석")

t1, t2 = st.tabs(["📅 전월 말일 기준", "🕒 오늘(데일리) 기준"])

f_monthly = 'data/momentum_data.csv'
f_daily = 'data/momentum_data_daily.csv'

with t1:
    if os.path.exists(f_monthly):
        df_m = pd.read_csv(f_monthly, dtype={'종목코드': str})
        df_m.columns = df_m.columns.str.replace(' ', '')
        date_str = df_m['기준일(월말)'].iloc[0] if '기준일(월말)' in df_m.columns else "N/A"
        render_kospi200_bull(df_m, date_str)
    else:
        st.error(f"월간 데이터 파일({f_monthly})이 없습니다. 월간 업데이트를 실행해주세요.")

with t2:
    if os.path.exists(f_daily):
        df_d = pd.read_csv(f_daily, dtype={'종목코드': str})
        df_d.columns = df_d.columns.str.replace(' ', '')
        date_str = df_d['기준일'].iloc[0] if '기준일' in df_d.columns else "오늘"
        render_kospi200_bull(df_d, date_str)
    else:
        st.error(f"데일리 데이터 파일({f_daily})이 없습니다. 데일리 업데이트를 실행해주세요.")
