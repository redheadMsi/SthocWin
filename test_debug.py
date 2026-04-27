import pandas as pd
import vectorbt as vbt
from data_pipeline import fetch_stock_data_parallel

test_tickers = ['005930', '000660']
dfs_dict = fetch_stock_data_parallel(test_tickers, '2023-01-01', '2024-01-01')

close_df = pd.DataFrame()
for ticker, df in dfs_dict.items():
    if not df.empty and 'Close' in df.columns:
        close_df[ticker] = df['Close']
        
close_df = close_df.ffill().dropna(how='all')

fast_ma = vbt.MA.run(close_df, 5)
slow_ma = vbt.MA.run(close_df, 20)

entries = fast_ma.ma_crossed_above(slow_ma)
exits = fast_ma.ma_crossed_below(slow_ma)

pf = vbt.Portfolio.from_signals(
    close_df,
    entries,
    exits,
    fees=0.001,
    freq='D'
)

returns = pf.total_return() * 100
print(returns)
print(type(returns))
print(returns.index)
