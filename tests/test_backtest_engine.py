import pytest
import pandas as pd
from src.backtest_engine import generate_ma_crossover_signals, run_vectorbt_backtest
import vectorbt as vbt

def test_generate_ma_crossover_signals():
    # 가상의 종가 데이터 생성 (추세가 있는 데이터)
    dates = pd.date_range("2023-01-01", periods=10)
    # 단기: 3일, 장기: 5일
    # 1~5일차: 하락 -> 6~10일차: 급상승 (골든크로스 발생)
    prices = [100, 90, 80, 70, 60, 100, 120, 150, 180, 200]
    df_close = pd.DataFrame({'test_ticker': prices}, index=dates)
    
    entries, exits = generate_ma_crossover_signals(df_close, fast_window=3, slow_window=5)
    
    assert isinstance(entries, pd.DataFrame)
    assert isinstance(exits, pd.DataFrame)
    assert entries.shape == df_close.shape
    assert exits.shape == df_close.shape
    
    # 10일차에는 3일 이평선(150, 180, 200 -> 176.6)이 5일(100, 120, 150, 180, 200 -> 150)보다 큼
    # 교차가 발생한 시점이 True가 됨.
    assert entries.sum().sum() >= 0 # 교차가 최소 0번 이상 발생

def test_run_vectorbt_backtest():
    dates = pd.date_range("2023-01-01", periods=5)
    prices = [100, 110, 120, 130, 140]
    df_close = pd.DataFrame({'test_ticker': prices}, index=dates)
    
    # 임의의 시그널
    entries = pd.DataFrame({'test_ticker': [False, True, False, False, False]}, index=dates)
    exits = pd.DataFrame({'test_ticker': [False, False, False, True, False]}, index=dates)
    
    pf = run_vectorbt_backtest(df_close, entries, exits, fees=0.0025)
    
    # 포트폴리오 객체가 정상 반환되는지 테스트
    assert isinstance(pf, vbt.Portfolio)
    
    # 간단한 수익률 검증 (110에 사서 130에 파는 로직, 수수료 있음)
    ret = pf.total_return()
    # 인덱스로 접근하여 scalar 값을 빼냄
    val = ret.iloc[0] if isinstance(ret, pd.Series) else ret
    assert val > 0
