import pandas as pd
import FinanceDataReader as fdr
import datetime
from typing import List

# 1. 유니버스 추출 (FinanceDataReader로 교체 - pykrx 에러 방지)
def get_kospi200_kosdaq150() -> List[str]:
    """KOSPI 200 / KOSDAQ 150 종목 코드 대체 (시가총액 상위 350개로 근사)"""
    # pykrx의 get_index_portfolio_deposit_file가 KRX 서버 개편으로 동작하지 않으므로 FDR 사용
    df = fdr.StockListing('KRX')
    return df.sort_values(by='Marcap', ascending=False).head(350)['Code'].tolist()

def get_top100_market_cap(date_str: str) -> List[str]:
    """현재 기준 시가총액 상위 100개 종목 반환"""
    df = fdr.StockListing('KRX')
    return df.sort_values(by='Marcap', ascending=False).head(100)['Code'].tolist()

def get_top_trading_volume(tickers: List[str], date_str: str, top_n: int = 10) -> List[str]:
    """주어진 티커 목록 중 현재 기준 거래대금 상위 N개 추출"""
    df = fdr.StockListing('KRX')
    filtered_df = df[df['Code'].isin(tickers)]
    top_trading = filtered_df.sort_values(by='Amount', ascending=False).head(top_n)['Code'].tolist()
    return top_trading

def get_stock_name(ticker: str) -> str:
    """티커로 종목명 가져오기"""
    try:
        df = fdr.StockListing('KRX')
        name = df[df['Code'] == ticker]['Name'].values[0]
        return name
    except:
        return ticker

# 2. 개별 종목 데이터 수집 및 시그널 계산
def fetch_stock_data(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """FinanceDataReader를 사용하여 일봉 데이터 수집"""
    df = fdr.DataReader(ticker, start_date, end_date)
    return df

def run_moving_average_backtest(df: pd.DataFrame, short_window: int, long_window: int) -> dict:
    """단일 종목에 대한 이동평균선 교차 백테스트 수행 (간단한 버전)"""
    if len(df) < long_window:
        return {"return_rate": 0.0, "win_rate": 0.0, "trades": 0}

    # 복사본 사용
    data = df.copy()
    data['Short_MA'] = data['Close'].rolling(window=short_window).mean()
    data['Long_MA'] = data['Close'].rolling(window=long_window).mean()
    
    # 시그널: Short MA > Long MA 이면 매수 (1), 아니면 매도/관망 (0)
    data['Signal'] = 0.0
    # iloc로 처리하여 SettingWithCopyWarning 방지
    data.iloc[long_window:, data.columns.get_loc('Signal')] = \
        (data['Short_MA'][long_window:] > data['Long_MA'][long_window:]).astype(float)
    
    # 포지션 변화 (1: 매수 진입, -1: 매도 청산)
    data['Position'] = data['Signal'].diff()
    
    trades = []
    buy_price = 0.0
    wins = 0

    # 포지션 기반 수익률 계산 시뮬레이션
    for i in range(len(data)):
        if data['Position'].iloc[i] == 1:
            buy_price = data['Close'].iloc[i]
        elif data['Position'].iloc[i] == -1 and buy_price > 0:
            sell_price = data['Close'].iloc[i]
            ret = (sell_price - buy_price) / buy_price
            trades.append(ret)
            if ret > 0:
                wins += 1
            buy_price = 0.0
            
    # 백테스트 종료 시점까지 들고 있는 경우 (Mark to market)
    if buy_price > 0:
        sell_price = data['Close'].iloc[-1]
        ret = (sell_price - buy_price) / buy_price
        trades.append(ret)
        if ret > 0:
            wins += 1

    total_return = sum(trades) * 100 if trades else 0.0
    win_rate = (wins / len(trades) * 100) if trades else 0.0
    
    return {
        "return_rate": round(total_return, 2),
        "win_rate": round(win_rate, 2),
        "trades": len(trades)
    }

# 3. 전체 파이프라인 (UI에서 호출)
def run_universe_backtest(tickers: List[str], param_pairs: List[tuple], start_date: str, end_date: str) -> pd.DataFrame:
    """여러 종목에 대해 다중 파라미터 백테스트를 수행하고 결과 통합"""
    results = []
    
    # 캐싱용으로 StockListing 한번만 호출
    krx_list = fdr.StockListing('KRX')
    
    for ticker in tickers:
        try:
            # 종목명 가져오기
            try:
                stock_name = krx_list[krx_list['Code'] == ticker]['Name'].values[0]
            except:
                stock_name = ticker
                
            df = fetch_stock_data(ticker, start_date, end_date)
            
            for short_w, long_w in param_pairs:
                res = run_moving_average_backtest(df, short_w, long_w)
                results.append({
                    "Ticker": ticker,
                    "Name": stock_name,
                    "Params": f"{short_w}/{long_w}",
                    "Return (%)": res["return_rate"],
                    "Win Rate (%)": res["win_rate"],
                    "Trades": res["trades"]
                })
        except Exception as e:
            continue
            
    return pd.DataFrame(results)
