import streamlit as st
import datetime
from src.data_fetcher import fetch_top_volume_tickers, fetch_stock_data_with_validation
from src.backtest_engine import generate_ma_crossover_signals, run_vectorbt_backtest

st.set_page_config(page_title="파이썬 퀀트 백테스트", layout="wide")

st.title("📈 거래량 상위 종목 백테스트 대시보드")
st.write("한국 주식 시장 거래량 상위 10개 종목에 대한 이동평균선 교차 전략 백테스트")

# 사이드바 설정
st.sidebar.header("파라미터 설정")
fast_ma = st.sidebar.slider("단기 이동평균선 (일)", min_value=3, max_value=20, value=5)
slow_ma = st.sidebar.slider("장기 이동평균선 (일)", min_value=20, max_value=120, value=20)
fees = st.sidebar.number_input("수수료 및 세금 (%)", min_value=0.0, max_value=1.0, value=0.25, step=0.01)

# @st.cache_data 데코레이터 적용 (TTL 3600초)
@st.cache_data(ttl=3600)
def load_data():
    with st.spinner("데이터를 수집 중입니다... (약 10~20초 소요)"):
        target_date = datetime.datetime.today()
        # 1. 상위 10개 티커 확보
        ticker_dict = fetch_top_volume_tickers(target_date, top_n=10)
        # 2. 주가 데이터 확보 및 방어 로직
        df_close = fetch_stock_data_with_validation(ticker_dict, years=2)
        return ticker_dict, df_close

try:
    ticker_dict, df_close = load_data()
    
    st.success("데이터 로드 완료! (캐싱됨)")
    
    # 3. 백테스트 시그널 및 엔진 구동
    entries, exits = generate_ma_crossover_signals(df_close, fast_window=fast_ma, slow_window=slow_ma)
    
    # fees는 백분율이므로 소수로 변환
    pf = run_vectorbt_backtest(df_close, entries, exits, fees=fees / 100.0)
    
    # 4. 종목 선택 및 차트 시각화
    selected_ticker = st.selectbox("종목 선택", options=list(ticker_dict.keys()), format_func=lambda x: f"{ticker_dict[x]} ({x})")
    
    if selected_ticker:
        st.subheader(f"{ticker_dict[selected_ticker]} 백테스트 결과")
        
        # vectorbt는 개별 컬럼(종목)에 대한 포트폴리오 정보를 제공합니다.
        pf_selected = pf[selected_ticker]
        
        col1, col2, col3 = st.columns(3)
        # stats()를 이용하면 깔끔하게 모든 지표를 가져올 수 있습니다.
        try:
            # vectorbt stat extraction
            tot_return = float(pf_selected.total_return()) * 100.0 # type: ignore
            
            stats_df = pf_selected.stats()
            if stats_df is not None:
                stats_dict = stats_df.to_dict() # type: ignore
                win_rate = float(stats_dict.get('Win Rate [%]', 0.0))
                mdd = float(stats_dict.get('Max Drawdown [%]', 0.0))
            else:
                win_rate = 0.0
                mdd = 0.0
        except Exception:
            tot_return = pf_selected.total_return() * 100
            win_rate = 0
            mdd = 0
            
        col1.metric("총 수익률 (%)", f"{tot_return:.2f}%")
        col2.metric("승률 (%)", f"{win_rate:.2f}%")
        col3.metric("Max Drawdown (%)", f"{mdd:.2f}%")
        
        # Plotly 차트 렌더링
        fig = pf_selected.plot()
        st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"오류가 발생했습니다: {e}")
