import streamlit as st
import time
import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from core_engine import (
    get_kospi200_kosdaq150, 
    get_top100_market_cap, 
    get_top_trading_volume,
    run_universe_backtest
)
from data_pipeline import fetch_stock_data_parallel

# --- 캐싱을 활용한 데이터 수집 함수 ---
@st.cache_data(ttl=3600)
def fetch_and_filter_universe(universe_choice):
    if universe_choice == "KOSPI 200 / KOSDAQ 150":
        tickers = get_kospi200_kosdaq150()
    else:
        tickers = get_top100_market_cap()
        
    top10_tickers = get_top_trading_volume(tickers, top_n=10)
    return top10_tickers

st.set_page_config(page_title="파이썬 퀀트 투자 대시보드", layout="wide")
st.title("📈 파이썬 퀀트 투자 대시보드 (통합 시뮬레이터)")
st.markdown("사용자가 유니버스와 다중 파라미터를 설정하여 백테스트를 실행하고 결과를 비교 분석할 수 있습니다.")

# 세션 상태 초기화
if 'results_df' not in st.session_state:
    st.session_state.results_df = None
    st.session_state.parsed_params = []
    st.session_state.target_tickers = []
    st.session_state.start_date = None
    st.session_state.end_date = None
    st.session_state.universe_option = None

# --- UI 레이아웃 구성 ---
col1, col2 = st.columns([1, 2])

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
    
    # 2. 파라미터 다중 입력
    st.subheader("2. 이평선 파라미터 조합")
    st.markdown("비교할 단기/장기 이평선 쌍을 쉼표(,)로 구분하여 입력하세요. (예: 5/20, 10/60, 20/120)")
    
    params_input = st.text_area(
        "파라미터 입력", 
        value="5/20, 10/60, 20/120"
    )

    st.markdown("---")
    run_button = st.button("🚀 실행 (Run Backtest)", type="primary")

    if run_button:
        # 날짜 범위 유효성 체크
        if len(date_range) != 2:
            st.warning("시작일과 종료일을 모두 선택해주세요.")
            st.stop()
            
        if not params_input.strip():
            st.warning("파라미터를 하나 이상 입력해주세요.")
            st.stop()
            
        selected_start_date, selected_end_date = date_range
        
        with st.spinner('선택한 유니버스의 거래대금 상위 10개 종목에 대한 백테스트를 진행 중입니다... (약 10~20초 소요)'):
            # 유니버스에서 종목을 필터링 (최신 데이터 기준)
            target_tickers = fetch_and_filter_universe(universe_option)
            
            parsed_params = []
            for p in params_input.split(','):
                try:
                    s, l = map(int, p.strip().split('/'))
                    parsed_params.append((s, l))
                except:
                    st.error(f"파라미터 형식이 잘못되었습니다: {p}. (예: 5/20)")
                    st.stop()
                    
            start_date = datetime.datetime.combine(selected_start_date, datetime.time.min)
            end_date = datetime.datetime.combine(selected_end_date, datetime.time.min)
            
            results_df = run_universe_backtest(
                target_tickers, 
                parsed_params, 
                start_date.strftime("%Y-%m-%d"), 
                end_date.strftime("%Y-%m-%d")
            )
            
            st.session_state.results_df = results_df
            st.session_state.parsed_params = [p.strip() for p in params_input.split(',')]
            st.session_state.target_tickers = target_tickers
            st.session_state.start_date = start_date
            st.session_state.end_date = end_date
            st.session_state.universe_option = universe_option
                
with col2:
    st.header("📊 백테스트 결과 (Results)")
    
    if st.session_state.results_df is not None:
        results_df = st.session_state.results_df
        param_pairs_str = st.session_state.parsed_params
        start_date = st.session_state.start_date
        end_date = st.session_state.end_date
        
        st.write(f"**백테스트 기간:** {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
        st.write(f"**선택된 유니버스:** {st.session_state.universe_option}")
        if not results_df.empty:
            st.write(f"**테스트 대상 종목 (해당 기간 종료일 거래대금 Top 10):** {', '.join(results_df['Name'].unique())}")
        
        st.markdown("### 결과 요약 (Actual Backtest)")
        
        for pair_str in param_pairs_str:
            with st.expander(f"파라미터 {pair_str} 결과", expanded=True):
                sub_df = results_df[results_df['Params'] == pair_str]
                
                if not sub_df.empty:
                    avg_return = round(sub_df['Return (%)'].mean(), 2)
                    avg_win_rate = round(sub_df['Win Rate (%)'].mean(), 2)
                    
                    cols = st.columns(2)
                    cols[0].metric(label="10종목 평균 누적 수익률", value=f"{avg_return}%", delta=f"{avg_return}%")
                    cols[1].metric(label="평균 승률", value=f"{avg_win_rate}%")
                    
                    st.dataframe(sub_df[['Name', 'Ticker', 'Return (%)', 'Win Rate (%)', 'Trades']].set_index('Name'), width=None)
                    
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
                                short_w, long_w = map(int, pair_str.split('/'))
                                df_stock[f'MA_{short_w}'] = df_stock['Close'].rolling(window=short_w).mean()
                                df_stock[f'MA_{long_w}'] = df_stock['Close'].rolling(window=long_w).mean()
                                
                                line_fig = go.Figure()
                                line_fig.add_trace(go.Scatter(x=df_stock.index, y=df_stock['Close'], mode='lines', name='종가', line=dict(color='black', width=1.5)))
                                line_fig.add_trace(go.Scatter(x=df_stock.index, y=df_stock[f'MA_{short_w}'], mode='lines', name=f'{short_w}일 이평선', line=dict(color='orange', width=1)))
                                line_fig.add_trace(go.Scatter(x=df_stock.index, y=df_stock[f'MA_{long_w}'], mode='lines', name=f'{long_w}일 이평선', line=dict(color='blue', width=1)))
                                
                                line_fig.update_layout(
                                    title=f"{selected_name} 주가 및 이동평균선 ({start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')})",
                                    xaxis_title="날짜",
                                    yaxis_title="주가 (원)",
                                    hovermode='x unified'
                                )
                                st.plotly_chart(line_fig)
                else:
                    st.write('결과가 없습니다.')
    else:
        st.info('좌측 설정 창에서 옵션을 선택하고 실행 버튼을 눌러주세요.')
