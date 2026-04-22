import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime
from dateutil.relativedelta import relativedelta
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)

def get_latest_business_day(date: datetime) -> str:
    """최근 영업일을 가져옵니다. (FinanceDataReader 사용)"""
    start_date = date - relativedelta(days=15)
    
    try:
        # 코스피 지수(KS11) 데이터를 이용해 최근 영업일 확인
        df = fdr.DataReader("KS11", start_date, date)
        if not df.empty:
            latest_date = df.index[-1]
            if isinstance(latest_date, pd.Timestamp):
                return latest_date.strftime("%Y%m%d")
            else:
                return pd.to_datetime(str(latest_date)).strftime("%Y%m%d")
    except Exception as e:
        print(f"영업일 조회 오류: {e}")
        
    return date.strftime("%Y%m%d")

def fetch_top_volume_tickers(target_date: datetime, top_n: int = 10) -> dict:
    """
    현재 기준 거래량 상위 N개의 티커와 종목명을 반환합니다.
    (FinanceDataReader의 StockListing을 이용해 현재 거래량 상위 종목을 가져옵니다.)
    return: { "005930": "삼성전자", ... }
    """
    df = fdr.StockListing('KRX')
    if df.empty:
        raise ValueError("데이터를 불러올 수 없습니다.")
        
    # Volume(거래량) 기준 내림차순 정렬
    df_top = df.sort_values(by="Volume", ascending=False).head(top_n)
    
    ticker_dict = {}
    for _, row in df_top.iterrows():
        ticker_dict[row['Code']] = row['Name']
        
    return ticker_dict

def fetch_stock_data_with_validation(ticker_dict: dict, years: int = 2) -> pd.DataFrame:
    """
    주어진 티커 목록에 대해 N년치 데이터를 가져오고,
    데이터 길이가 부족한 종목(상장 2년 미만, 거래 정지 등)은 필터링(방어적 프로그래밍)합니다.
    """
    end_date = datetime.today()
    start_date = end_date - relativedelta(years=years)
    
    df_dict = {}
    max_len = 0
    
    # 데이터 다운로드
    for ticker, name in ticker_dict.items():
        try:
            # OHLCV 가져오기
            df = fdr.DataReader(ticker, start_date, end_date)
            if df.empty:
                print(f"Warning: {name}({ticker}) 데이터가 존재하지 않습니다. 제외합니다.")
                continue
                
            # 종가(Close) 데이터만 가져오기
            if 'Close' not in df.columns:
                print(f"Warning: {name}({ticker}) 종가 데이터가 없습니다.")
                continue
                
            df_close = df[['Close']].copy()
            df_close.columns = [ticker]
            df_dict[ticker] = df_close
            
            # 정상적인 데이터의 최대 길이를 가늠
            if len(df_close) > max_len:
                max_len = len(df_close)
                
        except Exception as e:
            print(f"Warning: {name}({ticker}) 다운로드 중 에러 발생 - {e}")
            continue

    if not df_dict:
        raise ValueError("유효한 종목 데이터가 하나도 없습니다.")
        
    # 방어 로직: 정상 영업일 수(최대 길이) 대비 90% 이상 존재하는 종목만 편입
    valid_threshold = max_len * 0.90
    valid_dfs = []
    
    for ticker, df in df_dict.items():
        if len(df) < valid_threshold:
            name = ticker_dict[ticker]
            print(f"Warning: {name}({ticker})의 데이터 길이({len(df)}일)가 기준치({int(valid_threshold)}일)에 미달하여 제외합니다.")
        else:
            valid_dfs.append(df)
            
    if not valid_dfs:
        raise ValueError("필터링 후 유효한 종목이 없습니다.")

    # 병합
    merged_df = pd.concat(valid_dfs, axis=1)
    # 중간중간 비어있는 휴장일/거래정지일은 ffill 로 앞의 가격을 채움
    merged_df = merged_df.fillna(method='ffill').fillna(method='bfill')
    
    return merged_df
