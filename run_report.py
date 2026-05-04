import os
import sys
from dotenv import load_dotenv

# 현재 경로를 sys.path에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from src.bot_engine import run_daily_report

def main():
    print("--- 일일 장 마감 리포트 발송 스크립트 실행 ---")
    run_daily_report()

if __name__ == "__main__":
    main()
