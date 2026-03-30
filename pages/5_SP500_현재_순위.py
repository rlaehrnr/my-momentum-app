# --- [탭 1: 월말 고정 데이터] 업데이트 버전 ---
with tab1:
    f_monthly = 'data/momentum_data_sp500.csv'
    if os.path.exists(f_monthly):
        df_m = pd.read_csv(f_monthly, dtype={'종목코드': str})
        b_date_str = df_m['기준일(월말)'].iloc[0]
        st.subheader(f"📅 월말 기준 데이터 (기준일: {b_date_str})")
        
        # --- 지수 데이터 가져오기 ---
        idx_m = get_idx_us(pd.to_datetime(b_date_str))
        if not idx_m.empty:
            st.table(idx_m.reset_index().assign(**{c: idx_m.reset_index()[c].map('{:.1f}'.format) for c in idx_m.columns if c != '시장'}))
        
        # --- [추가] 그 전 달(지지난달) 순위 매칭 로직 ---
        try:
            # 1. 현재 기준일로부터 한 달 전의 연_월 계산
            curr_dt = datetime.strptime(b_date_str, '%Y-%m-%d')
            # 해당 월의 1일에서 하루를 빼면 전월 말일이 나옴
            prev_month_dt = curr_dt.replace(day=1) - timedelta(days=1)
            prev_ym = prev_month_dt.strftime('%Y_%m')
            
            # 2. 아카이브 파일 경로 설정
            f_prev_archive = f'archive_sp500/momentum_sp500_{prev_ym}.csv'
            
            if os.path.exists(f_prev_archive):
                df_prev_m = pd.read_csv(f_prev_archive, dtype={'종목코드': str})
                # 지지난달 순위 맵 생성
                prev_rank_map = {code: i+1 for i, code in enumerate(df_prev_m['종목코드'])}
                df_m['지지난달순위'] = df_m['종목코드'].map(prev_rank_map).fillna("⭐ NEW")
                df_m['지지난달순위'] = df_m['지지난달순위'].apply(lambda x: f"{x}위" if isinstance(x, int) else x)
            else:
                df_m['지지난달순위'] = "기록 없음"
        except Exception as e:
            df_m['지지난달순위'] = "-"
        # --------------------------------------------

        st.markdown("---")
        df_m.index = range(1, len(df_m) + 1)
        df_m['종목명_L'] = df_m.apply(lambda r: f"https://finance.yahoo.com/quote/{r['종목코드']}#{r['종목명']}", axis=1)

        st.dataframe(
            df_m.style.apply(highlight_sp500, idx_df=idx_m, axis=1),
            use_container_width=True, height=600,
            # '지지난달순위' 컬럼을 가장 오른쪽에 추가
            column_order=['시장', '종목명_L', '기준가', '1개월(%)', '3개월(%)', '6개월(%)', '12개월(%)', '모멘텀스코어', '지지난달순위'],
            column_config={
                "시장": st.column_config.TextColumn("거래소"),
                "종목명_L": st.column_config.LinkColumn("종목명", display_text=r"#(.+)"),
                "기준가": st.column_config.NumberColumn(format="$ %.2f"),
                "모멘텀스코어": st.column_config.NumberColumn(format="%.1f"),
                "지지난달순위": st.column_config.TextColumn("전월 순위", help="현재 표시된 기준일보다 한 달 전의 순위입니다.")
            }
        )
    else:
        st.warning("월말 데이터 파일이 없습니다.")
