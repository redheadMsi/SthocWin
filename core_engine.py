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

def run_vectorbt_backtest(dfs_dict: Dict[str, pd.DataFrame], param_pairs: List[tuple]) -> pd.DataFrame:
    """
    VectorBT를 이용한 다중 파라미터 백테스트 병렬 처리.
    dfs_dict: { '005930': df, '000660': df, ... } 형태
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
        if len(df) < 5: 
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
    for short_w, long_w in param_pairs:
        # 단기/장기 이동평균선 계산
        fast_ma = vbt.MA.run(close_df, short_w)
        slow_ma = vbt.MA.run(close_df, long_w)
        
        # 교차(Crossover) 시그널 생성
        entries = fast_ma.ma_crossed_above(slow_ma)
        exits = fast_ma.ma_crossed_below(slow_ma)
        
        # 포트폴리오 생성 (여기서 수수료, 슬리피지 추가 가능 - 0.1% 수수료 예시)
        pf = vbt.Portfolio.from_signals(
            close_df,
            entries,
            exits,
            fees=0.001,
            freq='D'
        )
        
        # 결과 통계 가져오기 (VectorBT가 파라미터를 인덱스로 추가하므로 컬럼 이름만으로 접근할 수 있도록 셋팅)
        returns = pf.total_return() * 100
        win_rates = pf.trades.win_rate() * 100
        total_trades = pf.trades.count()
        
        # MultiIndex에서 실제 티커 이름만 매핑하기 위한 딕셔너리 변환 (최종 레벨이 티커)
        returns_dict = {idx[-1] if isinstance(idx, tuple) else idx: val for idx, val in returns.items()}
        win_rates_dict = {idx[-1] if isinstance(idx, tuple) else idx: val for idx, val in win_rates.items()}
        trades_dict = {idx[-1] if isinstance(idx, tuple) else idx: val for idx, val in total_trades.items()}
        
        # 결과 정리
        for ticker in close_df.columns:
            results.append({
                "Ticker": ticker,
                "Name": get_stock_name(ticker),
                "Params": f"{short_w}/{long_w}",
                "Return (%)": round(returns_dict.get(ticker, 0.0), 2),
                "Win Rate (%)": round(win_rates_dict.get(ticker, 0.0), 2) if not pd.isna(win_rates_dict.get(ticker, 0.0)) else 0.0,
                "Trades": trades_dict.get(ticker, 0)
            })

    return pd.DataFrame(results)

# 3. 전체 파이프라인 (UI에서 호출)
def run_universe_backtest(tickers: List[str], param_pairs: List[tuple], start_date: str, end_date: str) -> pd.DataFrame:
    """UI에서 호출되는 진입점 - 데이터 병렬 수집 후 VectorBT 엔진 호출"""
    # 데이터 파이프라인을 통해 병렬로 데이터 로드
    # 최대 워커 수를 10으로 제한하여 Rate Limit 방어
    dfs_dict = fetch_stock_data_parallel(tickers, start_date, end_date, max_workers=10)
    
    # VectorBT 연산 엔진 호출
    return run_vectorbt_backtest(dfs_dict, param_pairs)
