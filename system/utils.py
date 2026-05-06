import re
import logging
from datetime import datetime

import pandas as pd

from .config import EXCLUDE_ORDER_STATUSES

logger = logging.getLogger(__name__)


def time_to_timestamp(time_str):
    try:
        cleaned_time = str(time_str).strip()
        if not cleaned_time:
            raise ValueError("时间字符串为空")

        dt = pd.to_datetime(cleaned_time, errors='coerce')
        if pd.isna(dt):
            raise ValueError(f"无法解析时间: {cleaned_time}")

        timestamp = int(dt.timestamp() * 1000)
        return str(timestamp)
    except Exception:
        timestamp = int(datetime.now().timestamp() * 1000)
        return str(timestamp)


def get_column_with_alias(df, column_names):
    for col in column_names:
        if col in df.columns:
            return col
    return None


def clean_numeric_value(value):
    cleaned = str(value).strip()
    return cleaned if cleaned else '0'


def get_order_status_filter():
    return {
        'exclude_statuses': EXCLUDE_ORDER_STATUSES,
        'include_statuses': []
    }


def filter_orders_by_status(df, filter_config):
    exclude_statuses = filter_config.get('exclude_statuses', [])
    include_statuses = filter_config.get('include_statuses', [])

    if exclude_statuses:
        before_count = len(df)
        df = df[~df['订单状态'].isin(exclude_statuses)]
        filtered_count = before_count - len(df)
        if filtered_count > 0:
            logger.info(f"已过滤 {filtered_count} 条无效订单（订单状态: {', '.join(exclude_statuses)}）")

    if include_statuses:
        before_count = len(df)
        df = df[df['订单状态'].isin(include_statuses)]
        filtered_count = before_count - len(df)
        if filtered_count > 0:
            logger.info(f"已过滤 {filtered_count} 条非目标订单（保留: {', '.join(include_statuses)}）")

    return df


def calc_outbound_status(row):
    order_status = str(row.get('订单状态', '')).replace('\t', '').strip()
    after_sales_status = str(row.get('售后状态', '')).replace('\t', '').strip()
    shipping_time = str(row.get('发货时间', '')).replace('\t', '').strip()

    if any(kw in order_status for kw in ["退款", "取消", "关闭"]) or "退款" in after_sales_status:
        return "已关闭"
    elif any(kw in order_status for kw in ["已发货", "已签收"]) or (
        shipping_time and shipping_time != 'nan' and shipping_time.strip()
    ):
        return "已出库"
    else:
        return "待出库"
