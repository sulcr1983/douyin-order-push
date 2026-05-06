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

UNIFIED_DB = os.getenv('UNIFIED_DB', str(BASE_DIR / 'orders.db'))

SHOP_NAMES = [
    s.strip() for s in os.getenv('SHOP_NAMES', 'Qmaster,tianyixinxuan').split(',')
    if s.strip()
]

SHOP_CONFIGS = {}
for name in SHOP_NAMES:
    key = name.upper()
    SHOP_CONFIGS[name] = {
        'folder': str(BASE_DIR / name),
        'db': UNIFIED_DB,
        'webhook': os.getenv(f'WECOM_WEBHOOK_URL_{key}', '')
    }

FIELD_MAPPING = {
    'sub_order_id': os.getenv('FIELD_SUB_ORDER_ID', 'fxNwEq'),
    'product_id': os.getenv('FIELD_PRODUCT_ID', 'fCNsiv'),
    'product_name': os.getenv('FIELD_PRODUCT_NAME', 'fBK7XT'),
    'quantity': os.getenv('FIELD_QUANTITY', 'fy3AU0'),
    'merchant_income': os.getenv('FIELD_MERCHANT_INCOME', 'ff2OiF'),
    'order_status': os.getenv('FIELD_ORDER_STATUS', 'fJ0NdH'),
    'payment_time': os.getenv('FIELD_PAYMENT_TIME', 'fNuVBy'),
    'address': os.getenv('FIELD_ADDRESS', 'fWJEK9'),
    'express_info': os.getenv('FIELD_EXPRESS_INFO', 'fTMuqw'),
    'outbound_status': os.getenv('FIELD_OUTBOUND_STATUS', 'fzFeek'),
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
