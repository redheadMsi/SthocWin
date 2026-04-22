import pandas as pd
import vectorbt as vbt

def generate_ma_crossover_signals(df_close: pd.DataFrame, fast_window: int = 5, slow_window: int = 20) -> tuple:
    """
    종가 데이터프레임을 받아 단기/장기 이동평균선을 계산하고
    매수(entries) 및 매도(exits) 시그널을 boolean DataFrame으로 반환합니다.
    """
    # 이동평균선 계산
    fast_ma = df_close.rolling(window=fast_window).mean()
    slow_ma = df_close.rolling(window=slow_window).mean()
    
    fast_ma_df = pd.DataFrame(fast_ma, index=df_close.index, columns=df_close.columns)
    slow_ma_df = pd.DataFrame(slow_ma, index=df_close.index, columns=df_close.columns)
    
    # 골든크로스: 단기 이평선이 장기 이평선을 상향 돌파 (이전에는 낮거나 같았다가, 현재는 커짐)
    fast_ma_shifted = fast_ma_df.shift(1)
    slow_ma_shifted = slow_ma_df.shift(1)
    
    entries = (fast_ma_df > slow_ma_df) & (fast_ma_shifted <= slow_ma_shifted)
    
    # 데드크로스: 단기 이평선이 장기 이평선을 하향 돌파
    exits = (fast_ma_df < slow_ma_df) & (fast_ma_shifted >= slow_ma_shifted)
    
    return entries, exits

def run_vectorbt_backtest(df_close: pd.DataFrame, entries: pd.DataFrame, exits: pd.DataFrame, fees: float = 0.0025) -> vbt.Portfolio:
    """
    종가와 시그널을 바탕으로 vectorbt Portfolio 객체를 생성합니다.
    수수료(fees)의 기본값은 0.25% (한국 주식 시장 평균 세금 및 수수료 고려)입니다.
    """
    # vectorbt 포트폴리오 생성
    pf = vbt.Portfolio.from_signals(
        df_close,
        entries,
        exits,
        fees=fees,
        freq='D' # 일별 데이터
    )
    return pf
