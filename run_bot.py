import os
import sys
from dotenv import load_dotenv

# 현재 경로를 sys.path에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from src.bot_engine import run_daily_bot
from data_pipeline import get_kospi200_kosdaq150, get_top_n_by_criteria

def main():
    print("--- 종가 매매 봇 스케줄러 실행 ---")
    # 예시 설정 (앱 UI와 동일한 기본값)
    tickers = get_kospi200_kosdaq150()
    top_tickers = get_top_n_by_criteria(tickers, criteria="Amount", top_n=5)
    
    # MA(5,20) AND RSI(14,30,70) 조건으로 예시 실행
    params = ((5, 20), (14, 30, 70), None)
    
    run_daily_bot(top_tickers, params, "AND", investment_amount_per_stock=1000000)

if __name__ == "__main__":
    main()
