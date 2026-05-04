import requests
import json
from .config import KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NO, KIS_ACCOUNT_PR, KIS_URL, KIS_MODE
from src.logger import get_logger

logger = get_logger("broker_kis")

class KISBroker:
    def __init__(self):
        self.app_key = KIS_APP_KEY
        self.app_secret = KIS_APP_SECRET
        self.cano = KIS_ACCOUNT_NO
        self.acnt_prdt_cd = KIS_ACCOUNT_PR
        self.url_base = KIS_URL
        self.access_token = ""
        self._get_access_token()

    def _get_access_token(self):
        headers = {"content-type": "application/json"}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }
        url = f"{self.url_base}/oauth2/tokenP"
        try:
            res = requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
            if res.status_code == 200:
                self.access_token = res.json().get("access_token")
            else:
                try:
                    err_msg = res.json().get("error_description", "Unknown API error")
                except:
                    err_msg = "Unknown JSON format"
                logger.error(f"[KIS API Error] Token 발급 실패: {err_msg}")
        except Exception as e:
            logger.error(f"[KIS API Exception] Token 발급 예외: {e}")

    def hashkey(self, datas):
        url = f"{self.url_base}/uapi/hashkey"
        headers = {
            'content-Type': 'application/json',
            'appKey': self.app_key,
            'appSecret': self.app_secret,
        }
        try:
            res = requests.post(url, headers=headers, data=json.dumps(datas), timeout=5)
            if res.status_code == 200:
                return res.json()["HASH"]
        except Exception as e:
            logger.error(f"[KIS API Exception] Hashkey 발급 예외: {e}")
        return ""

    def get_balance(self):
        """계좌 잔고 조회"""
        if not self.access_token:
            return None
        
        url = f"{self.url_base}/uapi/domestic-stock/v1/trading/inquire-balance"
        headers = {
            "Content-Type": "application/json", 
            "authorization": f"Bearer {self.access_token}",
            "appKey": self.app_key,
            "appSecret": self.app_secret,
            "tr_id": "VTTC8434R" if KIS_MODE == "VIRTUAL" else "TTTC8434R"
        }
        params = {
            "CANO": self.cano,
            "ACNT_PRDT_CD": self.acnt_prdt_cd,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "01",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": ""
        }
        try:
            res = requests.get(url, headers=headers, params=params, timeout=10)
            if res.status_code == 200:
                data = res.json()
                holdings = data.get("output1", [])
                summary = data.get("output2", [{}])[0]
                # 예수금 총액: dnca_tot_amt (실제 주문 가능 금액에 가까움)
                return {"holdings": holdings, "summary": summary}
            else:
                try:
                    err_msg = res.json().get("msg1", "Status code error")
                except:
                    err_msg = "Unknown Error"
                logger.error(f"[KIS API Error] 잔고 조회 실패: {err_msg}")
                return None
        except Exception as e:
            logger.error(f"[KIS API Exception] 잔고 조회 예외: {e}")
            return None

    def create_order(self, ticker: str, side: str, qty: int, price: int = 0):
        """
        주문 전송
        side: "buy" or "sell"
        price: 0이면 시장가(01), 0보다 크면 지정가(00)
        """
        if not self.access_token:
            return False, "Token not available"

        url = f"{self.url_base}/uapi/domestic-stock/v1/trading/order-cash"
        
        # TR_ID 설정 (모의투자와 실전투자 분기)
        if side == "buy":
            tr_id = "VTTC0802U" if KIS_MODE == "VIRTUAL" else "TTTC0802U"
        else:
            tr_id = "VTTC0801U" if KIS_MODE == "VIRTUAL" else "TTTC0801U"
            
        ord_dvsn = "01" if price == 0 else "00" # 01: 시장가, 00: 지정가
        
        body = {
            "CANO": self.cano,
            "ACNT_PRDT_CD": self.acnt_prdt_cd,
            "PDNO": ticker,
            "ORD_DVSN": ord_dvsn,
            "ORD_QTY": str(qty),
            "ORD_UNPR": str(price),
        }

        headers = {
            "Content-Type": "application/json", 
            "authorization": f"Bearer {self.access_token}",
            "appKey": self.app_key,
            "appSecret": self.app_secret,
            "tr_id": tr_id,
            "hashkey": self.hashkey(body)
        }

        try:
            res = requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
            if res.status_code == 200:
                result = res.json()
                success = result.get("rt_cd") == "0"
                msg = result.get("msg1")
                return success, msg
            else:
                try:
                    err_msg = res.json().get("msg1", "Status code error")
                except:
                    err_msg = "Unknown Error"
                logger.error(f"[KIS API Error] 주문 실패: {err_msg}")
                return False, f"API Error: {err_msg}"
        except Exception as e:
            logger.error(f"[KIS API Exception] 주문 예외: {e}")
            return False, f"Request Exception: {e}"

# 전역 브로커 인스턴스 (옵셔널)
# kis_broker = KISBroker() 
