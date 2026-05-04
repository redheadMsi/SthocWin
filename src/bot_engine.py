import datetime
import pandas as pd
from typing import List, Tuple

from data_pipeline import fetch_stock_data_parallel, get_stock_name
from core_engine import run_vectorbt_backtest
from src.broker_kis import KISBroker
from src.notifier import send_notification
from src.config import AUTO_TRADING

def run_daily_bot(
    tickers: List[str], 
    param_combination: Tuple[tuple, tuple, tuple], 
    signal_logic: str,
    investment_amount_per_stock: int = 1000000
):
    """
    매일 종가 무렵(15:20) 실행되어 당일 시그널을 확인하고 
    자동 매매 또는 알림을 전송하는 봇 엔진
    
    param_combination: (ma_tuple, rsi_tuple, macd_tuple)
    """
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    # 최소 1년치 데이터가 있어야 이평선, MACD 등이 정상 계산됨
    start_str = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    
    send_notification("🤖 **종가 매매 봇 실행 시작** 데이터 수집 및 시그널 계산 중...")
    
    dfs_dict = fetch_stock_data_parallel(tickers, start_str, today_str, max_workers=10)
    
    # 전략은 단일 파라미터 조합으로 돌림 (리스트로 감싸서 전달)
    result_df = run_vectorbt_backtest(dfs_dict, [param_combination], signal_logic)
    
    if result_df.empty:
        send_notification("❌ **에러:** 데이터 수집 또는 연산 실패로 봇을 종료합니다.")
        return
        
    # VectorBT 연산 시 사용된 전체 DataFrame 재구성
    # 코어 엔진의 로직을 활용해 당일(마지막 행)의 entries/exits 신호를 파악해야 합니다.
    # 이를 위해선 core_engine.py 의 함수를 직접 활용하는 것보다,
    # 해당 종목별로 오늘 Buy/Sell이 떴는지 확인해야 함.
    
    # result_df에는 누적 수익률, 승률만 있으므로, 여기서는 신호를 직접 계산하겠습니다.
    import pandas_ta as ta
    
    buy_signals = []
    sell_signals = []
    
    ma_param, rsi_param, macd_param = param_combination
    is_and = signal_logic.startswith("AND")
    
    for ticker, df in dfs_dict.items():
        if df is None or len(df) < 30: continue
        
        name = get_stock_name(ticker)
        current_price = int(df['Close'].iloc[-1])
        
        cond_buy = []
        cond_sell = []
        
        # MA
        if ma_param:
            short_w, long_w = ma_param
            ma_s = df['Close'].rolling(window=short_w).mean()
            ma_l = df['Close'].rolling(window=long_w).mean()
            # Golden cross (어제는 작고 오늘은 큼)
            buy_ma = (ma_s.iloc[-2] <= ma_l.iloc[-2]) and (ma_s.iloc[-1] > ma_l.iloc[-1])
            sell_ma = (ma_s.iloc[-2] >= ma_l.iloc[-2]) and (ma_s.iloc[-1] < ma_l.iloc[-1])
            cond_buy.append(buy_ma)
            cond_sell.append(sell_ma)
            
        # RSI
        if rsi_param:
            w, os_val, ob_val = rsi_param
            rsi = ta.rsi(df['Close'], length=w)
            buy_rsi = (rsi.iloc[-2] < os_val) and (rsi.iloc[-1] >= os_val)
            sell_rsi = (rsi.iloc[-2] > ob_val) and (rsi.iloc[-1] <= ob_val)
            cond_buy.append(buy_rsi)
            cond_sell.append(sell_rsi)
            
        # MACD
        if macd_param:
            f, s, sig = macd_param
            macd_df = ta.macd(df['Close'], fast=f, slow=s, signal=sig)
            macd_line = macd_df.iloc[:, 0]
            signal_line = macd_df.iloc[:, 2]
            buy_macd = (macd_line.iloc[-2] <= signal_line.iloc[-2]) and (macd_line.iloc[-1] > signal_line.iloc[-1])
            sell_macd = (macd_line.iloc[-2] >= signal_line.iloc[-2]) and (macd_line.iloc[-1] < signal_line.iloc[-1])
            cond_buy.append(buy_macd)
            cond_sell.append(sell_macd)
            
        # 최종 로직 평가
        if not cond_buy: continue
        
        if is_and:
            final_buy = all(cond_buy)
            final_sell = all(cond_sell)
        else:
            final_buy = any(cond_buy)
            final_sell = any(cond_sell)
            
        if final_buy:
            buy_signals.append({"ticker": ticker, "name": name, "price": current_price})
        if final_sell:
            sell_signals.append({"ticker": ticker, "name": name, "price": current_price})
            
    # 알림 전송 및 매매 실행
    msg_lines = [f"📊 **금일 종가 시그널 요약** (로직: {signal_logic})"]
    msg_lines.append(f"🟢 **매수 신호 ({len(buy_signals)}건):** " + ", ".join([s['name'] for s in buy_signals]))
    msg_lines.append(f"🔴 **매도 신호 ({len(sell_signals)}건):** " + ", ".join([s['name'] for s in sell_signals]))
    
    send_notification("\n".join(msg_lines))
    
    if AUTO_TRADING:
        broker = KISBroker()
        
        # 키가 설정되지 않은 경우 방어 로직 (모의 테스트 시 에러 방지)
        if not broker.access_token:
            send_notification("⚠️ **[시스템 경고]** 한국투자증권 API 키 또는 토큰 발급에 실패하여 가상 시뮬레이션(알림 전송)으로 대체합니다.")
            return

        # 매도 먼저 실행 (현금 확보)
        for s in sell_signals:
            # 잔고 확인 후 전량 매도 (예시)
            balance_info = broker.get_balance()
            if balance_info:
                holdings = balance_info['holdings']
                qty_to_sell = 0
                for h in holdings:
                    if h['pdno'] == s['ticker']: # KIS API 종목코드는 보통 앞 0 패딩
                        qty_to_sell = int(h['hldg_qty'])
                        break
                        
                if qty_to_sell > 0:
                    success, msg = broker.create_order(s['ticker'], "sell", qty_to_sell, 0)
                    send_notification(f"📉 **매도 체결 요청:** {s['name']} {qty_to_sell}주 (결과: {msg})")
        
        # 매수 실행
        for s in buy_signals:
            if s['price'] <= 0:
                send_notification(f"⚠️ **[경고]** {s['name']}의 당일 종가가 0원이라 매수를 보류합니다.")
                continue
                
            qty_to_buy = investment_amount_per_stock // s['price']
            if qty_to_buy > 0:
                success, msg = broker.create_order(s['ticker'], "buy", qty_to_buy, 0)
                send_notification(f"📈 **매수 체결 요청:** {s['name']} {qty_to_buy}주 (결과: {msg})")
    else:
        send_notification("⚠️ **자동매매가 비활성화되어 있습니다.** 수동으로 HTS/MTS에서 주문을 처리해주세요.")

def run_daily_report():
    """
    장 마감 후(또는 요청 시) 현재 계좌의 잔고 상태와 보유 종목 수익률을 
    알림으로 발송하는 리포트 함수
    """
    broker = KISBroker()
    
    if not broker.access_token:
        send_notification("⚠️ **[시스템 경고]** 한국투자증권 API 연동이 되어있지 않아 계좌 리포트를 생성할 수 없습니다.")
        return
        
    balance_info = broker.get_balance()
    if not balance_info:
        send_notification("❌ **[오류]** 계좌 잔고를 불러오는데 실패했습니다.")
        return
        
    summary = balance_info.get('summary', {})
    holdings = balance_info.get('holdings', [])
    
    # KIS API 응답 필드 매핑
    # tot_evlu_amt: 총 평가 금액 (자산)
    # dnca_tot_amt: 예수금 총액
    # scts_evlu_amt: 유가증권 평가 금액 (주식 총액)
    
    tot_asset = int(summary.get('tot_evlu_amt', 0))
    cash = int(summary.get('dnca_tot_amt', 0))
    stock_value = int(summary.get('scts_evlu_amt', 0))
    
    # 3자리마다 콤마 찍기 위한 포맷팅 함수
    def fmt(val): return f"{val:,}"
    
    msg_lines = [
        "📊 **[장 마감 일일 투자 리포트]**",
        f"💰 **총 자산:** {fmt(tot_asset)}원",
        f"💵 **보유 현금(예수금):** {fmt(cash)}원",
        f"📈 **주식 평가금:** {fmt(stock_value)}원"
    ]
    
    if holdings:
        msg_lines.append("\n📋 **[보유 종목 현황]**")
        for h in holdings:
            name = h.get('prdt_name', '알수없음')
            qty = int(h.get('hldg_qty', 0))
            # evlu_pfls_rt: 평가 손익률 (수익률)
            # pchs_amt: 매입 금액
            # evlu_amt: 평가 금액
            rt = float(h.get('evlu_pfls_rt', 0))
            sign = "+" if rt > 0 else ""
            msg_lines.append(f"- {name}: {fmt(qty)}주 (수익률: {sign}{rt}%)")
    else:
        msg_lines.append("\n📋 **[보유 종목 현황]**\n- 현재 보유중인 주식이 없습니다.")
        
    send_notification("\n".join(msg_lines), title="Daily Report")
