import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 한국투자증권 API 설정
KIS_APP_KEY = os.getenv("KIS_APP_KEY", "")
KIS_APP_SECRET = os.getenv("KIS_APP_SECRET", "")
KIS_ACCOUNT_NO = os.getenv("KIS_ACCOUNT_NO", "")
KIS_ACCOUNT_PR = os.getenv("KIS_ACCOUNT_PR", "01") # 계좌상품코드 (보통 01)
KIS_MODE = os.getenv("KIS_MODE", "VIRTUAL") # VIRTUAL or REAL

# 도메인 설정 (모의투자 vs 실전투자)
if KIS_MODE == "REAL":
    KIS_URL = "https://openapi.koreainvestment.com:9443"
else:
    KIS_URL = "https://openapivts.koreainvestment.com:29443"

# 자동 매매 허용 여부 (False면 알림만 전송)
AUTO_TRADING = os.getenv("AUTO_TRADING", "True").lower() in ('true', '1', 't')

# 알림 설정
raw_channels = os.getenv("NOTIFICATION_CHANNELS", "DISCORD")
NOTIFICATION_CHANNELS = [c.strip().upper() for c in raw_channels.split(",") if c.strip()]

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
LINE_NOTIFY_TOKEN = os.getenv("LINE_NOTIFY_TOKEN", "")
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "")
KAKAO_REFRESH_TOKEN = os.getenv("KAKAO_REFRESH_TOKEN", "")
