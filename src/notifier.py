import requests
import json
import streamlit as st
from .config import (
    NOTIFICATION_CHANNELS,
    DISCORD_WEBHOOK_URL,
    SLACK_WEBHOOK_URL,
    LINE_NOTIFY_TOKEN,
    KAKAO_REST_API_KEY,
    KAKAO_REFRESH_TOKEN
)
from src.logger import get_logger

logger = get_logger("notifier")

def _send_discord(content: str, username: str):
    if not DISCORD_WEBHOOK_URL: return False
    try:
        data = {"content": content, "username": username}
        res = requests.post(DISCORD_WEBHOOK_URL, json=data, timeout=10)
        return res.status_code == 204
    except Exception as e:
        logger.error(f"[Discord Error] {e}")
        return False

def _send_slack(content: str, username: str):
    if not SLACK_WEBHOOK_URL: return False
    try:
        data = {"text": content, "username": username}
        res = requests.post(SLACK_WEBHOOK_URL, json=data, timeout=10)
        return res.status_code == 200
    except Exception as e:
        logger.error(f"[Slack Error] {e}")
        return False

def _send_line(content: str):
    if not LINE_NOTIFY_TOKEN: return False
    try:
        headers = {"Authorization": f"Bearer {LINE_NOTIFY_TOKEN}"}
        data = {"message": f"\n{content}"} # 라인은 첫 줄이 붙어 나오는 경향이 있어 줄바꿈 추가
        res = requests.post("https://notify-api.line.me/api/notify", headers=headers, data=data, timeout=10)
        return res.status_code == 200
    except Exception as e:
        logger.error(f"[Line Error] {e}")
        return False

def _refresh_kakao_token():
    """카카오톡 Refresh Token으로 Access Token 재발급"""
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": KAKAO_REST_API_KEY,
        "refresh_token": KAKAO_REFRESH_TOKEN
    }
    try:
        res = requests.post(url, data=data, timeout=10)
        if res.status_code == 200:
            return res.json().get("access_token")
    except Exception as e:
        logger.error(f"[Kakao Token Error] {e}")
    return None

def _send_kakao(content: str):
    if not KAKAO_REST_API_KEY or not KAKAO_REFRESH_TOKEN: return False
    
    access_token = _refresh_kakao_token()
    if not access_token: return False
    
    try:
        url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # 카카오톡 텍스트 템플릿 양식
        template = {
            "object_type": "text",
            "text": content,
            "link": {
                "web_url": "https://finance.naver.com",
                "mobile_web_url": "https://finance.naver.com"
            },
            "button_title": "자세히 보기"
        }
        data = {"template_object": json.dumps(template)}
        
        res = requests.post(url, headers=headers, data=data, timeout=10)
        return res.status_code == 200
    except Exception as e:
        logger.error(f"[Kakao Error] {e}")
        return False


def send_notification(content: str, title: str = "QuantBot"):
    """
    설정된 여러 채널(DISCORD, SLACK, LINE, KAKAO)로 알림을 라우팅하여 전송합니다.
    """
    # 환경변수에 어떤 설정도 제대로 되어있지 않으면 화면 출력 (모의 동작)
    is_any_configured = False
    
    if "DISCORD" in NOTIFICATION_CHANNELS and DISCORD_WEBHOOK_URL:
        _send_discord(content, title)
        is_any_configured = True
        
    if "SLACK" in NOTIFICATION_CHANNELS and SLACK_WEBHOOK_URL:
        _send_slack(content, title)
        is_any_configured = True
        
    if "LINE" in NOTIFICATION_CHANNELS and LINE_NOTIFY_TOKEN:
        _send_line(content)
        is_any_configured = True
        
    if "KAKAO" in NOTIFICATION_CHANNELS and KAKAO_REST_API_KEY and KAKAO_REFRESH_TOKEN:
        _send_kakao(content)
        is_any_configured = True

    # 설정된 채널이 없으면 (또는 URL/Token이 비어있으면) 콘솔 및 Streamlit 화면에 출력
    if not is_any_configured:
        logger.info(f"[알림 모의 출력] {content}")
        try:
            st.info(f"📣 **[알림 모의 출력]**\n\n{content}")
        except:
            pass
        return False
        
    return True
