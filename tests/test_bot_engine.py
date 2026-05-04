import pytest
from unittest.mock import patch, MagicMock
from src.bot_engine import run_daily_bot
import pandas as pd

@patch('src.bot_engine.send_notification')
@patch('src.bot_engine.fetch_stock_data_parallel')
def test_zero_division_guard(mock_fetch, mock_send):
    # 가격이 0인 Mock 데이터 생성
    mock_df = pd.DataFrame({
        'Close': [100, 100, 100, 100, 0] # 마지막 날 가격 0
    })
    
    mock_fetch.return_value = {'005930': mock_df}
    
    # 예외가 발생하지 않고 조용히 처리되는지 검증
    # 만약 예외가 터지면 테스트 실패
    try:
        run_daily_bot(['005930'], ((5,20), None, None), "AND")
    except ZeroDivisionError:
        pytest.fail("ZeroDivisionError가 방어되지 않았습니다.")
