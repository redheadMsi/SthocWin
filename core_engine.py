import pandas as pd
import vectorbt as vbt
import datetime
from typing import List, Dict

# 새로운 데이터 파이프라인에서 헬퍼 함수 가져오기
from data_pipeline import (
    get_kospi200_kosdaq150,
    get_top100_market_cap,
    get_top_trading_volume,
    get_stock_name,
    fetch_stock_data_parallel
)

def run_vectorbt_backtest(dfs_dict: Dict[str, pd.DataFrame], param_combinations: List[tuple], signal_logic: str) -> pd.DataFrame:
    """
    VectorBT를 이용한 다중 파라미터 백테스트 병렬 처리.
    dfs_dict: { '005930': df, '000660': df, ... } 형태
    param_combinations: [(ma_tuple, rsi_tuple, macd_tuple), ...]
    signal_logic: "AND..." 또는 "OR..."
    """
    if not dfs_dict:
        return pd.DataFrame()
        
    # 1. 모든 종목의 종가를 하나로 합치기
    close_df = pd.DataFrame()
    valid_tickers = []
    
    for ticker, df in dfs_dict.items():
        if df is None or df.empty:
            continue
        if 'Close' not in df.columns:
            continue
            
        # 데이터가 너무 적은 경우(예: 신규상장주) 스킵
        if len(df) < 30: # MACD를 위해 최소 데이터 증가
            continue
            
        close_df[ticker] = df['Close']
        valid_tickers.append(ticker)
            
    # 누락 데이터 앞의 값으로 채우고 완전히 빈 행(주말 등) 제거
    if close_df.empty:
        return pd.DataFrame()
        
    close_df = close_df.ffill().dropna(how='all')
    if close_df.empty:
        return pd.DataFrame()

    results = []

    # 파라미터별 VectorBT 백테스트
    for ma_params, rsi_params, macd_params in param_combinations:
        entries_list = []
        exits_list = []
        
        # 1. MA 시그널
        if ma_params:
            short_w, long_w = ma_params
            fast_ma = vbt.MA.run(close_df, short_w)
            slow_ma = vbt.MA.run(close_df, long_w)
            ma_entries = fast_ma.ma_crossed_above(slow_ma)
            ma_exits = fast_ma.ma_crossed_below(slow_ma)
            
            # 컬럼 MultiIndex 평탄화 (단일 티커 인덱스로 변경)
            ma_entries.columns = [col[-1] if isinstance(col, tuple) else col for col in ma_entries.columns]
            ma_exits.columns = [col[-1] if isinstance(col, tuple) else col for col in ma_exits.columns]
            
            entries_list.append(ma_entries)
            exits_list.append(ma_exits)
            
        # 2. RSI 시그널
        if rsi_params:
            window, oversold, overbought = rsi_params
            rsi = vbt.RSI.run(close_df, window=window)
            rsi_entries = rsi.rsi_crossed_below(oversold) # 과매도선 아래로 갈 때 매수 (역추세)
            rsi_exits = rsi.rsi_crossed_above(overbought) # 과매수선 위로 갈 때 매도
            
            rsi_entries.columns = [col[-1] if isinstance(col, tuple) else col for col in rsi_entries.columns]
            rsi_exits.columns = [col[-1] if isinstance(col, tuple) else col for col in rsi_exits.columns]
            
            entries_list.append(rsi_entries)
            exits_list.append(rsi_exits)
            
        # 3. MACD 시그널
        if macd_params:
            fast_w, slow_w, sig_w = macd_params
            macd = vbt.MACD.run(close_df, fast_window=fast_w, slow_window=slow_w, signal_window=sig_w)
            macd_entries = macd.macd_crossed_above(macd.signal)
            macd_exits = macd.macd_crossed_below(macd.signal)
            
            macd_entries.columns = [col[-1] if isinstance(col, tuple) else col for col in macd_entries.columns]
            macd_exits.columns = [col[-1] if isinstance(col, tuple) else col for col in macd_exits.columns]
            
            entries_list.append(macd_entries)
            exits_list.append(macd_exits)

        if not entries_list:
            continue

        # AND / OR 로직 병합
        is_and = signal_logic.startswith("AND")
        
        final_entries = entries_list[0]
        final_exits = exits_list[0]
        
        for i in range(1, len(entries_list)):
            if is_and:
                final_entries = final_entries & entries_list[i]
                final_exits = final_exits & exits_list[i] # 매수도 보수적으로, 매도도 보수적으로
            else:
                final_entries = final_entries | entries_list[i]
                final_exits = final_exits | exits_list[i]
        
        # 포트폴리오 생성 (여기서 수수료, 슬리피지 추가 가능 - 0.1% 수수료 예시)
        pf = vbt.Portfolio.from_signals(
            close_df,
            final_entries,
            final_exits,
            fees=0.001,
            freq='D'
        )
        
        # 결과 통계 가져오기
        returns = pf.total_return() * 100
        win_rates = pf.trades.win_rate() * 100
        total_trades = pf.trades.count()
        
        # MultiIndex 처리 방어
        returns_dict = {idx[-1] if isinstance(idx, tuple) else idx: val for idx, val in returns.items()}
        win_rates_dict = {idx[-1] if isinstance(idx, tuple) else idx: val for idx, val in win_rates.items()}
        trades_dict = {idx[-1] if isinstance(idx, tuple) else idx: val for idx, val in total_trades.items()}
        
        param_str_label = f"MA:{ma_params} RSI:{rsi_params} MACD:{macd_params}"
        
        # 결과 정리
        for ticker in close_df.columns:
            results.append({
                "Ticker": ticker,
                "Name": get_stock_name(ticker),
                "Params": param_str_label,
                "Return (%)": round(returns_dict.get(ticker, 0.0), 2),
                "Win Rate (%)": round(win_rates_dict.get(ticker, 0.0), 2) if not pd.isna(win_rates_dict.get(ticker, 0.0)) else 0.0,
                "Trades": trades_dict.get(ticker, 0)
            })

    return pd.DataFrame(results)

# 3. 전체 파이프라인 (UI에서 호출)
def run_universe_backtest(tickers: List[str], param_combinations: List[tuple], signal_logic: str, start_date: str, end_date: str) -> pd.DataFrame:
    """UI에서 호출되는 진입점 - 데이터 병렬 수집 후 VectorBT 엔진 호출"""
    # 데이터 파이프라인을 통해 병렬로 데이터 로드
    dfs_dict = fetch_stock_data_parallel(tickers, start_date, end_date, max_workers=10)
    
    # VectorBT 연산 엔진 호출
    return run_vectorbt_backtest(dfs_dict, param_combinations, signal_logic)
