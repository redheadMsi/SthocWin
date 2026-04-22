import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.data_fetcher import get_latest_business_day, fetch_top_volume_tickers, fetch_stock_data_with_validation

def test_get_latest_business_day():
    # 날짜 입력 시 포맷이 올바르게 나오는지 검증
    # 휴일 테스트보다는 형식과 반환값이 str인지 확인
    test_date = datetime(2023, 10, 1)
    res = get_latest_business_day(test_date)
    assert isinstance(res, str)
    assert len(res) == 8

def test_fetch_stock_data_with_validation():
    # 가상의 종목 리스트로 테스트하기에는 pykrx 외부 API 의존성이 큼.
    # 하지만 빈 데이터가 반환될 때의 에러 핸들링을 테스트할 수 있음.
    # 유효하지 않은 티커를 강제로 넘겨서 에러가 발생하는지 확인.
    bad_dict = {"999999": "유령주식"}
    with pytest.raises(ValueError, match="유효한 종목 데이터가 하나도 없습니다"):
        fetch_stock_data_with_validation(bad_dict, years=1)
