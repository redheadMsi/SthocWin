import os
import time
import datetime
import tempfile
import pandas as pd
import duckdb
import FinanceDataReader as fdr
from filelock import FileLock, Timeout
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict

# 설정
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(DATA_DIR, exist_ok=True)
META_FILE = os.path.join(DATA_DIR, 'krx_metadata.parquet')
META_LOCK = os.path.join(DATA_DIR, 'krx_metadata.lock')

# DuckDB 인메모리 연결 (쓰레드당 개별 연결 권장, 여기서는 I/O용으로 임시 생성 후 사용)
def get_duckdb_conn():
    return duckdb.connect(database=':memory:')

def _fetch_krx_metadata() -> pd.DataFrame:
    """FDR에서 KRX 메타데이터를 다운로드 (Lock 내부에서만 호출됨)"""
    return fdr.StockListing('KRX')

def get_metadata() -> pd.DataFrame:
    """메타데이터(StockListing)를 반환. 캐시가 없거나 하루 지났으면 업데이트 (Reader-Writer 분리)"""
    # 1. 만료 검사 (Cache Validity Check) - Lock 없이 읽기 시도
    need_update = True
    if os.path.exists(META_FILE):
        file_mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(META_FILE))
        # 오늘 생성/수정된 파일이면 유효
        if file_mod_time.date() == datetime.date.today():
            need_update = False
            
    if not need_update:
        # 캐시 히트: DuckDB로 초고속 읽기
        conn = get_duckdb_conn()
        try:
            return conn.execute(f"SELECT * FROM read_parquet('{META_FILE}')").df()
        except Exception:
            need_update = True # 읽기 실패시 다시 업데이트 시도
            
    if need_update:
        # 쓰기 Lock 획득 (Cache Miss)
        lock = FileLock(META_LOCK, timeout=30) # 30초 대기
        with lock:
            # Double check: 다른 스레드가 방금 받아왔는지 확인
            if os.path.exists(META_FILE):
                file_mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(META_FILE))
                if file_mod_time.date() == datetime.date.today():
                    conn = get_duckdb_conn()
                    return conn.execute(f"SELECT * FROM read_parquet('{META_FILE}')").df()
            
            # 실제 다운로드 수행
            df = _fetch_krx_metadata()
            
            # Atomic Write: .tmp 파일에 먼저 쓰고 rename
            tmp_fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, suffix='.parquet.tmp')
            os.close(tmp_fd) # pandas가 쓸 수 있게 fd 닫기
            
            try:
                df.to_parquet(tmp_path)
                os.replace(tmp_path, META_FILE) # Atomic rename (기존 파일 덮어쓰기)
            except Exception as e:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                raise e
            
            return df

def get_stock_name(ticker: str) -> str:
    """티커로 종목명 가져오기 (캐시된 메타데이터 사용)"""
    df = get_metadata()
    try:
        # Pandas df에서 바로 검색 (데이터가 크지 않아 DuckDB 쿼리보다 빠름)
        return df[df['Code'] == ticker]['Name'].values[0]
    except IndexError:
        return ticker

def get_kospi200_kosdaq150() -> List[str]:
    """KOSPI 200 / KOSDAQ 150 종목 코드 대체 (시가총액 상위 350개로 근사)"""
    df = get_metadata()
    return df.sort_values(by='Marcap', ascending=False).head(350)['Code'].tolist()

def get_top100_market_cap() -> List[str]:
    """현재 기준 시가총액 상위 100개 종목 반환"""
    df = get_metadata()
    return df.sort_values(by='Marcap', ascending=False).head(100)['Code'].tolist()

def get_top_trading_volume(tickers: List[str], top_n: int = 10) -> List[str]:
    """(Deprecated) 주어진 티커 목록 중 현재 기준 거래대금 상위 N개 추출"""
    return get_top_n_by_criteria(tickers, criteria='Amount', top_n=top_n)

def get_top_n_by_criteria(tickers: List[str], criteria: str = 'Amount', top_n: int = 10, ascending: bool = False) -> List[str]:
    """주어진 티커 목록 중 특정 기준 상위 N개 추출"""
    df = get_metadata()
    filtered_df = df[df['Code'].isin(tickers)]
    return filtered_df.sort_values(by=criteria, ascending=ascending).head(top_n)['Code'].tolist()

# --- 일봉 데이터 캐싱 파이프라인 ---

def _get_stock_cache_path(ticker: str) -> str:
    return os.path.join(DATA_DIR, f"{ticker}.parquet")

def _get_stock_lock_path(ticker: str) -> str:
    return os.path.join(DATA_DIR, f"{ticker}.lock")

def _fetch_stock_single(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """단일 종목 데이터 다운로드 및 캐싱 (Lock 내부 로직)"""
    cache_file = _get_stock_cache_path(ticker)
    lock_file = _get_stock_lock_path(ticker)
    
    # 1. 만료 검사 (Cache Validity Check) - 당일 데이터면 유효
    need_update = True
    if os.path.exists(cache_file):
        file_mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(cache_file))
        if file_mod_time.date() == datetime.date.today():
            need_update = False
            
    if not need_update:
        # 캐시 히트: DuckDB로 읽기
        conn = get_duckdb_conn()
        try:
            # 특정 기간 필터링은 호출하는 곳에서 DuckDB SQL로 하거나 Pandas로 함
            df = conn.execute(f"SELECT * FROM read_parquet('{cache_file}')").df()
            # start_date, end_date 필터링
            df.index = pd.to_datetime(df.index) if not isinstance(df.index, pd.DatetimeIndex) else df.index
            # FinanceDataReader는 Date를 index로 반환함
            if 'Date' in df.columns:
                 df['Date'] = pd.to_datetime(df['Date'])
                 df.set_index('Date', inplace=True)
            return df
        except Exception:
            need_update = True
            
    if need_update:
        lock = FileLock(lock_file, timeout=60)
        with lock:
            # Double check
            if os.path.exists(cache_file):
                file_mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(cache_file))
                if file_mod_time.date() == datetime.date.today():
                     conn = get_duckdb_conn()
                     df = conn.execute(f"SELECT * FROM read_parquet('{cache_file}')").df()
                     if 'Date' in df.columns:
                         df['Date'] = pd.to_datetime(df['Date'])
                         df.set_index('Date', inplace=True)
                     return df
            
            # API 다운로드 (여기서는 전체 기간을 다 가져와서 저장하는 것이 좋음, 나중에 다른 기간 요구시 또 다운받지 않게)
            # 일단 요구된 시작일의 1년 전부터 넉넉하게 받아 캐싱하는 전략 또는 아예 2010년부터 다 받기
            # FDR 특성상 시작일을 안주면 1990년부터 다 가져오는데 시간이 더 걸림.
            # 실전에서는 과거 5년치 정도를 고정으로 가져오는게 좋음.
            fetch_start = "2018-01-01" # 넉넉히 과거 데이터 수집
            df = fdr.DataReader(ticker, fetch_start)
            
            if df.empty:
                return df # 데이터 없음
                
            # Date index를 column으로 빼서 parquet 저장 (DuckDB 호환성)
            save_df = df.copy()
            save_df.reset_index(inplace=True)
            
            tmp_fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, suffix=f'_{ticker}.parquet.tmp')
            os.close(tmp_fd)
            
            try:
                save_df.to_parquet(tmp_path)
                os.replace(tmp_path, cache_file)
            except Exception as e:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                raise e
            
            return df

def fetch_stock_data_parallel(tickers: List[str], start_date: str, end_date: str, max_workers: int = 5) -> Dict[str, pd.DataFrame]:
    """여러 종목을 병렬로 다운로드/캐시에서 로드"""
    results = {}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # submit tasks
        future_to_ticker = {executor.submit(_fetch_stock_single, t, start_date, end_date): t for t in tickers}
        
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                df = future.result()
                if not df.empty:
                    # 요청된 기간으로 필터링
                    mask = (df.index >= pd.to_datetime(start_date)) & (df.index <= pd.to_datetime(end_date))
                    results[ticker] = df.loc[mask]
            except Exception as exc:
                print(f"{ticker} generated an exception: {exc}")
                
    return results

# 테스트용 코드
if __name__ == "__main__":
    print("Testing Metadata Cache...")
    meta_df = get_metadata()
    print(f"Metadata rows: {len(meta_df)}")
    
    print("\nTesting Parallel Stock Data Fetch...")
    start_t = time.time()
    # 삼성전자, SK하이닉스, 네이버
    test_tickers = ['005930', '000660', '035420']
    dfs = fetch_stock_data_parallel(test_tickers, "2023-01-01", "2024-01-01")
    print(f"Time taken: {time.time() - start_t:.2f} seconds")
    for t, df in dfs.items():
        print(f"{t}: {len(df)} rows")
