import logging
import os
from logging.handlers import RotatingFileHandler

def get_logger(name: str):
    logger = logging.getLogger(name)
    
    # 이미 핸들러가 있으면 그대로 반환 (중복 로깅 방지)
    if logger.handlers:
        return logger
        
    logger.setLevel(logging.INFO)
    
    # logs 디렉토리 생성
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    # 파일 핸들러 (최대 5MB, 3개 백업)
    log_file = os.path.join(log_dir, 'bot_trading.log')
    file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    
    # 포맷 설정
    formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(name)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
