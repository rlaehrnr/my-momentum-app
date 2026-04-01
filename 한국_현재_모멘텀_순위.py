# --- 탭 3: KOSPI 200 집중 분석 (KeyError 방어판) ---
with tab3:
    if os.path.exists(f_kr):
        df_raw = pd.read_csv(f_kr, dtype={'종목코드': str})
        
        # 1. 컬럼명 유연하게 잡기 (에러 방지 핵심)
        # 파일에 '시가'나 'mar'가 들어간 컬럼이 있는지 찾습니다.
        m_col = next((c for c in df_raw.columns if '시가' in c or 'mar' in c.lower()), None)
        c_1m = next((c for c in df_raw.columns if '1개월' in c), '1개월(%)')
        c_3m = next((c for c in df_raw.columns if '3개월' in c), '3개월(%)')
        c_6m = next((c for c in df_raw.columns if '6개월' in c), '6개월(%)')
        c_12m = next((c for c in df_raw.columns if '12개월' in c), '12개월(%)')

        # 기초 필터링
        df_k200 = df_raw[(df_raw['시장'] == 'KOSPI') & (df_raw['종목코드'].str.endswith('0'))].copy()
        
        # ⭐ [수정] m_col이 실제 df_k200에 있을 때만 정렬 실행 (KeyError 방지)
        if m_col and m_col in df_k200.columns:
            df_k200 = df_k200.sort_values(by=m_col, ascending=False).head(200)
        else:
            df_k200 = df_k200.head(200)

        b_date_str = df_k200['기준일(월말)'].iloc[0] if '기준일(월말)' in df_k200.columns else "날짜정보없음"
        st.title(f"🎯 KOSPI 200 집중 분석 (기준: {b_date_str})")
        
        # 지수 정보 표시
        idx_now_k200 = get_idx_kr(pd.to_datetime(b_date_str))
        if not idx_now_k200.empty:
            idx_disp = idx_now_k200.reset_index().copy()
            idx_disp['현재가'] = idx_disp['현재가'].map('{:,.0f}'.format)
            for c in ['1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)']:
                idx_disp[c] = idx_disp[c].map('{:+.1f}%'.format)
            st.table(idx_disp)

        st.markdown("---")

        # 전처리: 링크 생성 및 소수점 고정
        df_k200['통합티커'] = "KOSPI:" + df_k200['종목코드'].str.zfill(6)
        df_k200['종목명_L'] = df_k200.apply(lambda r: f"https://m.stock.naver.com/fchart/domestic/stock/{r['종목코드'].zfill(6)}#{r['종목명']}", axis=1)

        for c in [c_1m, c_3m, c_6m, c_12m]:
            if c in df_k200.columns:
                df_k200[c] = pd.to_numeric(df_k200[c], errors='coerce').round(1)

        # 사용자 로직 (상위 30%, 10%)
        q30 = {c: df_k200[c].quantile(0.7) for c in [c_1m, c_3m, c_6m, c_12m] if c in df_k200.columns}
        t10_1m = df_k200[c_1m].quantile(0.9) if c_1m in df_k200.columns else 0

        # 필터링 조건
        cond_perf = (df_k200[c_1m]>=q30.get(c_1m, 0)) & (df_k200[c_12m]>=q30.get(c_12m, 0)) & (df_k200[c_1m]>0)
        df_perfect = df_k200[cond_perf].copy()
        
        cond_spec = (df_k200[c_12m]>=q30.get(c_12m, 0)) & (df_k200[c_1m]>=t10_1m)
        df_special = df_k200[cond_spec].copy()
        
        common_codes = set(df_perfect['종목코드']).intersection(set(df_special['종목코드']))

        # 화면 출력 설정 (소수점 1자리 고정)
        k200_cfg = {
            "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"), 
            "기준가": st.column_config.NumberColumn("현재가", format="%,d"), 
            m_col: st.column_config.NumberColumn("시가총액", format="%,d"),
            c_1m: st.column_config.NumberColumn(format="%.1f"), c_3m: st.column_config.NumberColumn(format="%.1f"),
            c_6m: st.column_config.NumberColumn(format="%.1f"), c_12m: st.column_config.NumberColumn(format="%.1f")
        }

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🔥 퍼펙트 상승")
            st.dataframe(df_perfect.style.apply(apply_k200_styling, idx_df=idx_now_k200, common_codes=common_codes, axis=1), 
                         use_container_width=True, column_order=['통합티커', '종목명_L', c_1m, c_3m, c_6m, c_12m], column_config=k200_cfg)
        with col2:
            st.subheader("🚀 장기 주도 & 단기 급등")
            st.dataframe(df_special.style.apply(apply_k200_styling, idx_df=idx_now_k200, common_codes=common_codes, axis=1), 
                         use_container_width=True, column_order=['통합티커', '종목명_L', c_1m, c_12m], column_config=k200_cfg)

        st.markdown("---")
        st.subheader("🏆 KOSPI 200 시가총액 전체 순위")
        df_k200['순위'] = range(1, len(df_k200) + 1)
        st.dataframe(df_k200.set_index('순위').style.apply(apply_k200_styling, idx_df=idx_now_k200, common_codes=common_codes, axis=1), 
                     use_container_width=True, height=600, column_order=['통합티커', '종목명_L', m_col, '기준가', c_1m, c_3m, c_6m, c_12m], column_config=k200_cfg)
