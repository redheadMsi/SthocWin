import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta

from data_pipeline import (
    get_kospi200_kosdaq150, 
    get_top100_market_cap, 
    get_top_n_by_criteria,
    fetch_stock_data_parallel
)
from core_engine import run_universe_backtest

# 데이터 로딩/캐싱 최적화를 위해 universe 선택에 따른 함수 분리
@st.cache_data(ttl=3600)
def fetch_and_filter_universe(universe_choice, filter_criteria, top_n):
    if universe_choice == "KOSPI 200 / KOSDAQ 150":
        tickers = get_kospi200_kosdaq150()
    else:
        tickers = get_top100_market_cap()
        
    criteria_map = {
        "거래대금 (Amount)": "Amount",
        "거래량 (Volume)": "Volume",
        "시가총액 (Marcap)": "Marcap",
        "등락률 (ChagesRatio)": "ChagesRatio"
    }
    col_name = criteria_map.get(filter_criteria, "Amount")
    
    top_tickers = get_top_n_by_criteria(tickers, criteria=col_name, top_n=top_n)
    return top_tickers

st.set_page_config(page_title="파이썬 퀀트 투자 대시보드", layout="wide")
st.title("📈 파이썬 퀀트 투자 대시보드 (통합 시뮬레이터)")
st.markdown("사용자가 유니버스와 다중 파라미터를 설정하여 백테스트를 실행하고, 실전 투자 봇을 구동할 수 있습니다.")

tab_backtest, tab_live = st.tabs(["📊 백테스트 (Backtest)", "🤖 실전 투자 봇 (Live Trading)"])

with tab_backtest:
    # --- UI 레이아웃 구성 ---
    col1, col2 = st.columns([1, 2])

    # 세션 상태 초기화
    if 'results_df' not in st.session_state:
        st.session_state.results_df = None
        st.session_state.parsed_params = []
        st.session_state.target_tickers = []
        st.session_state.start_date = None
        st.session_state.end_date = None
        st.session_state.universe_option = None
        st.session_state.filter_criteria = None
        st.session_state.top_n = None

    with col1:
        st.header("⚙️ 설정 (Settings)")
        
        # 1. 날짜 및 유니버스 선택
        st.subheader("1. 기준 날짜 및 유니버스 선택")
        
        today = datetime.date.today()
        default_start = today - datetime.timedelta(days=365*2) # 2년 전 기본값
        
        # 날짜 범위(시작일-종료일) 선택 가능하게 변경
        date_range = st.date_input(
            "백테스트 기간 (시작일 - 종료일)", 
            value=(default_start, today),
            max_value=today
        )
        
        universe_option = st.selectbox(
            "테스트할 종목 풀을 선택하세요",
            ("KOSPI 200 / KOSDAQ 150", "당일 시가총액 상위 100개")
        )
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filter_criteria = st.selectbox(
                "추출 기준",
                ("거래대금 (Amount)", "거래량 (Volume)", "시가총액 (Marcap)", "등락률 (ChagesRatio)")
            )
        with col_f2:
            top_n = st.number_input("추출 개수", min_value=1, max_value=50, value=10, step=1)
        
        # 선택된 유니버스에 따른 타겟 종목 리스트 미리보기
        with st.expander(f"👀 현재 선택된 대상 종목 확인 ({filter_criteria} 상위 {top_n}개)", expanded=True):
            preview_tickers = fetch_and_filter_universe(universe_option, filter_criteria, top_n)
            # ticker를 종목명으로 변환하기 위해 임시로 함수 가져옴
            from data_pipeline import get_stock_name
            preview_names = [get_stock_name(t) for t in preview_tickers]
            st.write(", ".join(preview_names))
            
        st.markdown("---")
        
        # 2. 지표 및 파라미터 다중 설정
        st.subheader("2. 지표 설정 및 파라미터 입력")
        
        use_ma = st.checkbox("이동평균선 교차 (MA Crossover)", value=True)
        if use_ma:
            st.markdown("비교할 단기/장기 이평선 쌍을 쉼표(,)로 구분 (예: 5/20, 10/60)")
            ma_params_input = st.text_area("MA 파라미터", value="5/20, 10/60", key="ma_params")
        else:
            ma_params_input = ""

        use_rsi = st.checkbox("RSI 역추세 (Oversold/Overbought)", value=False)
        if use_rsi:
            st.markdown("기간/과매도선/과매수선 쌍을 쉼표(,)로 구분 (예: 14/30/70, 10/25/75)")
            rsi_params_input = st.text_area("RSI 파라미터", value="14/30/70", key="rsi_params")
        else:
            rsi_params_input = ""

        use_macd = st.checkbox("MACD 교차 (MACD/Signal Crossover)", value=False)
        if use_macd:
            st.markdown("단기/장기/시그널 쌍을 쉼표(,)로 구분 (예: 12/26/9, 5/35/5)")
            macd_params_input = st.text_area("MACD 파라미터", value="12/26/9", key="macd_params")
        else:
            macd_params_input = ""
            
        st.markdown("---")
        st.subheader("3. 복합 시그널 로직")
        is_and_logic = st.checkbox("모든 지표의 조건이 동시에 만족될 때만 진입 (AND 로직)", value=True, help="체크를 해제하면 선택한 지표 중 하나라도 신호가 오면 진입하는 OR 로직으로 동작합니다.")
        signal_logic = "AND" if is_and_logic else "OR"

        st.markdown("---")
        run_button = st.button("🚀 실행 (Run Backtest)", type="primary")

        if run_button:
            # 날짜 범위 유효성 체크
            if len(date_range) != 2:
                st.warning("시작일과 종료일을 모두 선택해주세요.")
                st.stop()
                
            if not (use_ma or use_rsi or use_macd):
                st.warning("최소 한 개 이상의 지표를 선택해주세요.")
                st.stop()
                
            selected_start_date, selected_end_date = date_range
            
            with st.spinner(f'선택한 유니버스의 {filter_criteria} 상위 {top_n}개 종목에 대한 백테스트를 진행 중입니다... (약 10~20초 소요)'):
                # 유니버스에서 종목을 필터링 (최신 데이터 기준)
                target_tickers = fetch_and_filter_universe(universe_option, filter_criteria, top_n)
                
                # 파라미터 파싱 로직 변경 (복합 파라미터 객체로 묶기)
                # 여기서는 단순히 여러 전략 조합의 카테시안 곱 혹은 단순 병렬 리스트를 만들지에 대한 결정 필요.
                # 직관성을 위해, 입력된 리스트의 첫번째 값들끼리 묶고 두번째 값들끼리 묶는 방식을 쓰거나,
                # 아니면 단일 조합 테스트로 제한하는 것도 방법이지만, 기존 방식처럼 복수개의 조합을 허용하려면 
                # MA_list x RSI_list x MACD_list 카테시안 곱을 생성해야 함.
                # 복잡도를 줄이기 위해, 각 지표별 첫번째 입력값들을 조합하여 테스트하는 방식으로 우선 구현.
                
                def parse_params(input_str, expected_len):
                    if not input_str.strip(): return []
                    res = []
                    for p in input_str.split(','):
                        parts = p.strip().split('/')
                        if len(parts) == expected_len:
                            res.append(tuple(map(int, parts)))
                        else:
                            st.error(f"파라미터 형식이 잘못되었습니다: {p}")
                            st.stop()
                    return res
                
                ma_list = parse_params(ma_params_input, 2) if use_ma else [None]
                rsi_list = parse_params(rsi_params_input, 3) if use_rsi else [None]
                macd_list = parse_params(macd_params_input, 3) if use_macd else [None]
                
                if not ma_list: ma_list = [None]
                if not rsi_list: rsi_list = [None]
                if not macd_list: macd_list = [None]

                # 카테시안 곱으로 모든 조합 생성
                import itertools
                combined_params = list(itertools.product(ma_list, rsi_list, macd_list))
                
                start_date = datetime.datetime.combine(selected_start_date, datetime.time.min)
                end_date = datetime.datetime.combine(selected_end_date, datetime.time.min)
                
                results_df = run_universe_backtest(
                    target_tickers, 
                    combined_params, 
                    signal_logic,
                    start_date.strftime("%Y-%m-%d"), 
                    end_date.strftime("%Y-%m-%d")
                )
                
                st.session_state.results_df = results_df
                st.session_state.parsed_params = [
                    f"MA:{m} RSI:{r} MACD:{mac}" for m, r, mac in combined_params
                ]
                st.session_state.target_tickers = target_tickers
                st.session_state.start_date = start_date
                st.session_state.end_date = end_date
                st.session_state.universe_option = universe_option
                st.session_state.filter_criteria = filter_criteria
                st.session_state.top_n = top_n
                    
    with col2:
        st.header("📊 백테스트 결과 (Results)")
        
        if st.session_state.results_df is not None:
            results_df = st.session_state.results_df
            param_pairs_str = st.session_state.parsed_params
            start_date = st.session_state.start_date
            end_date = st.session_state.end_date
            res_filter_criteria = st.session_state.filter_criteria
            res_top_n = st.session_state.top_n
            
            st.write(f"**백테스트 기간:** {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
            st.write(f"**선택된 유니버스:** {st.session_state.universe_option}")
            if not results_df.empty:
                st.write(f"**테스트 대상 종목 ({res_filter_criteria} Top {res_top_n}):** {', '.join(results_df['Name'].unique())}")
            
            st.markdown("### 결과 요약 (Actual Backtest)")
            
            for pair_str in param_pairs_str:
                with st.expander(f"파라미터 {pair_str} 결과", expanded=True):
                    sub_df = results_df[results_df['Params'] == pair_str]
                    
                    if not sub_df.empty:
                        avg_return = round(sub_df['Return (%)'].mean(), 2)
                        avg_win_rate = round(sub_df['Win Rate (%)'].mean(), 2)
                        
                        cols = st.columns(2)
                        cols[0].metric(label=f"{res_top_n}종목 평균 누적 수익률", value=f"{avg_return}%", delta=f"{avg_return}%")
                        cols[1].metric(label="평균 승률", value=f"{avg_win_rate}%")
                        
                        st.dataframe(sub_df[['Name', 'Ticker', 'Return (%)', 'Win Rate (%)', 'Trades']].set_index('Name'), use_container_width=True)
                        
                        st.markdown("💡 **아래 막대 그래프에서 종목을 클릭하시면 주가/이평선 차트가 표시됩니다.**")
                        
                        fig = px.bar(
                            sub_df, 
                            x='Name', 
                            y='Return (%)', 
                            title=f"종목별 수익률 차트 ({pair_str})",
                            text='Return (%)',
                            color='Return (%)',
                            color_continuous_scale=px.colors.diverging.RdYlBu[::-1]
                        )
                        fig.update_layout(xaxis_title="종목명", yaxis_title="수익률 (%)", clickmode='event+select')
                        
                        event = st.plotly_chart(fig, on_select="rerun", key=f"chart_{pair_str}")
                        
                        selected_points = event.selection.get("points", []) if hasattr(event, "selection") else []
                        
                        if selected_points:
                            selected_name = selected_points[0]['x']
                            selected_ticker = sub_df[sub_df['Name'] == selected_name]['Ticker'].values[0]
                            st.subheader(f"📈 {selected_name} 주가 차트 ({pair_str})")
                            
                            with st.spinner(f"{selected_name} 주가 데이터 로딩 중..."):
                                dfs = fetch_stock_data_parallel([selected_ticker], start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
                                df_stock = dfs.get(selected_ticker, pd.DataFrame())
                                if not df_stock.empty:
                                    # Parse params from param string e.g. "MA:(5, 20) RSI:None MACD:None"
                                    # Very basic parsing for visualization
                                    import re
                                    ma_match = re.search(r"MA:\((\d+),\s*(\d+)\)", pair_str)
                                    rsi_match = re.search(r"RSI:\((\d+),\s*(\d+),\s*(\d+)\)", pair_str)
                                    macd_match = re.search(r"MACD:\((\d+),\s*(\d+),\s*(\d+)\)", pair_str)
                                    
                                    has_rsi = rsi_match is not None
                                    has_macd = macd_match is not None
                                    
                                    row_count = 1
                                    row_heights = [0.6]
                                    if has_rsi: 
                                        row_count += 1
                                        row_heights.append(0.2)
                                    if has_macd: 
                                        row_count += 1
                                        row_heights.append(0.2)
                                        
                                    # sum to 1.0
                                    row_heights = [h/sum(row_heights) for h in row_heights]
                                    
                                    fig_sub = make_subplots(
                                        rows=row_count, cols=1, 
                                        shared_xaxes=True,
                                        vertical_spacing=0.05,
                                        row_heights=row_heights,
                                    )
                                    
                                    # Main Chart
                                    fig_sub.add_trace(go.Scatter(x=df_stock.index, y=df_stock['Close'], mode='lines', name='종가', line=dict(color='black', width=1.5)), row=1, col=1)
                                    
                                    if ma_match:
                                        short_w, long_w = map(int, ma_match.groups())
                                        df_stock[f'MA_{short_w}'] = df_stock['Close'].rolling(window=short_w).mean()
                                        df_stock[f'MA_{long_w}'] = df_stock['Close'].rolling(window=long_w).mean()
                                        fig_sub.add_trace(go.Scatter(x=df_stock.index, y=df_stock[f'MA_{short_w}'], mode='lines', name=f'{short_w}일 이평선', line=dict(color='orange', width=1)), row=1, col=1)
                                        fig_sub.add_trace(go.Scatter(x=df_stock.index, y=df_stock[f'MA_{long_w}'], mode='lines', name=f'{long_w}일 이평선', line=dict(color='blue', width=1)), row=1, col=1)
                                    
                                    current_row = 2
                                    if has_rsi:
                                        rsi_w, rsi_os, rsi_ob = map(int, rsi_match.groups())
                                        df_stock['RSI'] = ta.rsi(df_stock['Close'], length=rsi_w)
                                        fig_sub.add_trace(go.Scatter(x=df_stock.index, y=df_stock['RSI'], mode='lines', name=f'RSI({rsi_w})', line=dict(color='purple', width=1.5)), row=current_row, col=1)
                                        fig_sub.add_hline(y=rsi_os, line_dash="dash", line_color="green", row=current_row, col=1, annotation_text=f"과매도({rsi_os})")
                                        fig_sub.add_hline(y=rsi_ob, line_dash="dash", line_color="red", row=current_row, col=1, annotation_text=f"과매수({rsi_ob})")
                                        fig_sub.update_yaxes(title_text="RSI", row=current_row, col=1)
                                        current_row += 1
                                        
                                    if has_macd:
                                        fast_w, slow_w, sig_w = map(int, macd_match.groups())
                                        macd_df = ta.macd(df_stock['Close'], fast=fast_w, slow=slow_w, signal=sig_w)
                                        macd_col = f"MACD_{fast_w}_{slow_w}_{sig_w}"
                                        sig_col = f"MACDs_{fast_w}_{slow_w}_{sig_w}"
                                        hist_col = f"MACDh_{fast_w}_{slow_w}_{sig_w}"
                                        
                                        if macd_col in macd_df.columns:
                                            fig_sub.add_trace(go.Scatter(x=df_stock.index, y=macd_df[macd_col], mode='lines', name='MACD', line=dict(color='blue', width=1.5)), row=current_row, col=1)
                                            fig_sub.add_trace(go.Scatter(x=df_stock.index, y=macd_df[sig_col], mode='lines', name='Signal', line=dict(color='orange', width=1.5)), row=current_row, col=1)
                                            fig_sub.add_trace(go.Bar(x=df_stock.index, y=macd_df[hist_col], name='Histogram', marker_color='gray'), row=current_row, col=1)
                                            fig_sub.update_yaxes(title_text="MACD", row=current_row, col=1)

                                    fig_sub.update_layout(
                                        title=f"{selected_name} 주가 및 지표 ({start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')})",
                                        hovermode='x unified',
                                        height=400 + (row_count - 1) * 200
                                    )
                                    st.plotly_chart(fig_sub, use_container_width=True)
                    else:
                        st.write('결과가 없습니다.')
        else:
            st.info('좌측 설정 창에서 옵션을 선택하고 실행 버튼을 눌러주세요.')

with tab_live:
    st.header("🤖 종가 매매 봇 (Live Trading)")
    st.markdown("백테스트에서 검증된 전략을 바탕으로 매일 장 마감 직전(15:20)에 당일 시그널을 계산하고 매매를 수행합니다.")
    
    st.warning("⚠️ **주의:** 실전 투자를 위해서는 `.env` 파일에 한국투자증권 API 키와 계좌 번호가 올바르게 설정되어 있어야 합니다.")
    
    col_live1, col_live2 = st.columns([1, 1])
    
    with col_live1:
        st.subheader("봇 설정")
        bot_universe = st.selectbox("봇 유니버스", ("KOSPI 200 / KOSDAQ 150", "당일 시가총액 상위 100개"), key="bot_univ")
        bot_criteria = st.selectbox("종목 추출 기준", ("거래대금 (Amount)", "거래량 (Volume)", "시가총액 (Marcap)"), key="bot_crit")
        bot_top_n = st.number_input("추출 개수", min_value=1, max_value=20, value=5, key="bot_n")
        
        st.markdown("---")
        st.subheader("지표 선택")

        use_bot_ma = st.checkbox("이동평균선 교차 (MA Crossover)", value=True, key="live_chk_ma")
        bot_ma = st.text_input("MA 파라미터 (단기/장기)", value="5/20", key="live_txt_ma") if use_bot_ma else ""

        use_bot_rsi = st.checkbox("RSI 역추세 (Oversold/Overbought)", value=False, key="live_chk_rsi")
        bot_rsi = st.text_input("RSI 파라미터 (기간/과매도/과매수)", value="14/30/70", key="live_txt_rsi") if use_bot_rsi else ""

        use_bot_macd = st.checkbox("MACD 교차 (MACD/Signal Crossover)", value=False, key="live_chk_macd")
        bot_macd = st.text_input("MACD 파라미터 (단기/장기/시그널)", value="12/26/9", key="live_txt_macd") if use_bot_macd else ""
        
        st.markdown("---")
        
        is_and_logic_bot = st.checkbox("모든 지표 조건 동시 만족시 진입 (AND)", value=True, key="live_logic")
        bot_logic = "AND" if is_and_logic_bot else "OR"
        
        invest_amt = st.number_input("종목당 매수 금액 (원)", min_value=100000, value=1000000, step=100000)
        
    with col_live2:
        st.subheader("시스템 상태 및 수동 실행")
        import os
        if not os.path.exists(".env"):
            st.warning("⚠️ `.env` 설정 파일이 없습니다. 봇을 원활하게 사용하려면 환경변수 파일이 필요합니다.")
            if st.button("📝 기본 `.env` 파일 생성", use_container_width=True):
                try:
                    import shutil
                    if os.path.exists(".env.example"):
                        shutil.copy(".env.example", ".env")
                        st.success("✅ 기본 `.env` 파일이 생성되었습니다. 파일 내용을 본인의 API 정보로 수정해주세요!")
                        st.rerun()
                    else:
                        st.error("`.env.example` 파일이 존재하지 않아 생성할 수 없습니다.")
                except Exception as e:
                    st.error(f"파일 생성 실패: {e}")
        else:
            from src.config import AUTO_TRADING, KIS_MODE, NOTIFICATION_CHANNELS
            
            st.info(f"**현재 모드:** {'실전 투자 (REAL)' if KIS_MODE == 'REAL' else '모의 투자 (VIRTUAL)'}")
            st.info(f"**자동 매매:** {'활성화됨 (주문 전송)' if AUTO_TRADING else '비활성화됨 (알림만 전송)'}")
            st.info(f"**알림 채널:** {', '.join(NOTIFICATION_CHANNELS) if NOTIFICATION_CHANNELS else '화면 모의 출력'}")

        if st.button("🚀 즉시 시그널 확인 및 봇 실행 (수동 트리거)", type="primary", use_container_width=True):
            from src.bot_engine import run_daily_bot
            
            # 파라미터 파싱
            def parse_single(val, expected):
                if not val.strip(): return None
                parts = val.split('/')
                if len(parts) == expected:
                    return tuple(map(int, parts))
                return None
                
            p_ma = parse_single(bot_ma, 2)
            p_rsi = parse_single(bot_rsi, 3)
            p_macd = parse_single(bot_macd, 3)
            
            if not (use_bot_ma or use_bot_rsi or use_bot_macd):
                st.warning("최소 한 개 이상의 지표를 선택해주세요.")
            else:
                with st.spinner("종가 봇을 실행하여 시그널을 분석 중입니다..."):
                    try:
                        targets = fetch_and_filter_universe(bot_universe, bot_criteria, bot_top_n)
                        run_daily_bot(targets, (p_ma, p_rsi, p_macd), bot_logic, invest_amt)
                        st.success("✅ 봇 실행 완료! 디스코드 알림을 확인하세요.")
                    except Exception as e:
                        st.error(f"봇 실행 중 오류 발생: {e}")
                        
            st.markdown("---")
            if st.button("📊 현재 계좌 상태 리포트 발송", type="secondary", use_container_width=True):
                from src.bot_engine import run_daily_report
                with st.spinner("증권사 API에서 계좌 정보를 가져오는 중..."):
                    try:
                        run_daily_report()
                        st.success("✅ 리포트 발송 완료! 알림을 확인하세요.")
                    except Exception as e:
                        st.error(f"리포트 발송 중 오류 발생: {e}")
                    
        st.markdown("---")
        st.markdown("💡 **Tip:** 리눅스 서버에서 `crontab -e` 명령어를 사용하여 매일 자동으로 실행되게 스케줄링하세요.")
        st.code("""# 매일 15:20 시그널 분석 및 매매
20 15 * * 1-5 cd /path/to/SthocWin && source .venv/bin/activate && python run_bot.py

# 매일 15:40 장 마감 투자 리포트 알림
40 15 * * 1-5 cd /path/to/SthocWin && source .venv/bin/activate && python run_report.py""", language="bash")
