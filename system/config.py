from pathlib import Path
from dotenv import load_dotenv
import os
import logging

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

LOG_FILE = os.getenv('LOG_FILE', str(BASE_DIR / 'sync_log.txt'))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

EXCLUDE_ORDER_STATUSES = [
    status.strip() for status in os.getenv(
        'EXCLUDE_ORDER_STATUSES',
        '已关闭,已取消,未付款,待付款,交易关闭,取消订单'
    ).split(',')
    if status.strip()
]

MAX_CONSECUTIVE_FAILURES = int(os.getenv('MAX_CONSECUTIVE_FAILURES', '10'))

WEBHOOK_URLS = {
    'Qmaster': os.getenv('WECOM_WEBHOOK_URL_QMASTER', ''),
    'tianyixinxuan': os.getenv('WECOM_WEBHOOK_URL_TIANYIXINXUAN', '')
}

DB_FILES = {
    'Qmaster': os.getenv('DB_FILE_QMASTER', str(BASE_DIR / 'orders_qmaster.db')),
    'tianyixinxuan': os.getenv('DB_FILE_TIANYIXINXUAN', str(BASE_DIR / 'orders_tianyixinxuan.db'))
}

SHOP_CONFIGS = {
    'Qmaster': {
        'folder': str(BASE_DIR / 'Qmaster'),
        'db': DB_FILES['Qmaster'],
        'webhook': WEBHOOK_URLS['Qmaster']
    },
    'tianyixinxuan': {
        'folder': str(BASE_DIR / 'tianyixinxuan'),
        'db': DB_FILES['tianyixinxuan'],
        'webhook': WEBHOOK_URLS['tianyixinxuan']
    }
}


def setup_logging():
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger
