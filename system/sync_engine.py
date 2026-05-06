import time
import re
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

from .config import setup_logging, SHOP_CONFIGS, MAX_CONSECUTIVE_FAILURES
from .db import init_db, insert_or_update_db, get_pending_updates
from .utils import (
    time_to_timestamp, get_column_with_alias, clean_numeric_value,
    get_order_status_filter, calc_outbound_status
)

logger = setup_logging()


def get_latest_file(folder_path, extensions=None):
    if extensions is None:
        extensions = ['.csv', '.xlsx']

    folder = Path(folder_path)
    logger.info(f"正在扫描文件夹: {folder.name}")

    if not folder.exists():
        return None, None

    files = []
    for file in folder.iterdir():
        if file.is_file() and any(file.suffix.lower() == ext for ext in extensions):
            files.append((file, file.stat().st_mtime))

    if not files:
        return None, None

    files.sort(key=lambda x: x[1], reverse=True)
    latest_file = files[0][0]
    mtime = files[0][1]
    formatted_time = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')

    logger.info(
        f"已自动锁定最新文件: [{latest_file.name}] (创建时间: {formatted_time})"
    )
    return str(latest_file), latest_file.suffix.lower()


def read_file(file_path, file_ext):
    encodings = ['utf-8-sig', 'gbk']

    if file_ext == '.csv':
        for encoding in encodings:
            try:
                df = pd.read_csv(file_path, encoding=encoding)
                logger.info(f"成功读取CSV文件，使用编码: {encoding}")
                return df
            except PermissionError:
                raise Exception(
                    "文件正在被 Excel 占用，请关闭 Excel 后重试，"
                    "或将文件复制一份再运行。"
                )
            except Exception:
                continue
        raise Exception("无法读取CSV文件，请检查文件编码")

    elif file_ext in ['.xlsx', '.xls']:
        try:
            try:
                df = pd.read_excel(file_path, engine='openpyxl')
                logger.info("成功读取Excel文件(openpyxl引擎)")
                return df
            except PermissionError:
                raise Exception(
                    "文件正在被 Excel 占用，请关闭 Excel 后重试，"
                    "或将文件复制一份再运行。"
                )
            except Exception:
                pass

            try:
                df = pd.read_excel(file_path, engine='xlrd')
                logger.info("成功读取Excel文件(xlrd引擎)")
                return df
            except PermissionError:
                raise Exception(
                    "文件正在被 Excel 占用，请关闭 Excel 后重试，"
                    "或将文件复制一份再运行。"
                )
            except Exception:
                pass

            raise Exception(
                "无法读取Excel文件，请确保已安装 openpyxl 或 xlrd 库"
            )
        except Exception as e:
            if "文件正在被 Excel 占用" in str(e):
                raise
            raise Exception(
                f"无法读取Excel文件，请确保已安装 openpyxl 或 xlrd 库: {e}"
            )

    raise Exception(f"不支持的文件格式: {file_ext}")


def clean_data(df):
    df.columns = df.columns.str.strip()

    required_columns_map = {
        '订单状态': ['订单状态'],
        '主订单编号': ['主订单编号', '主订单号'],
        '子订单编号': ['子订单编号', '子订单号'],
        '支付完成时间': ['支付完成时间', '付款时间', '支付时间'],
        '选购商品': ['选购商品', '商品名称', '商品'],
        '商品数量': ['商品数量', '数量'],
        '商家收入金额': ['商家收入金额', '商家收入', '收入金额', '商家实收'],
        '省': ['省', '省份'],
        '市': ['市', '城市'],
        '区': ['区', '区县'],
        '详细地址': ['详细地址', '地址'],
        '快递信息': ['快递信息', '物流信息', '快递'],
        '商品ID': ['商品ID', '商品id', '商品编码', '商家编码']
    }
    optional_columns_map = {
        '发货时间': ['发货时间', '出库时间', 'shipping time', 'ship_time'],
        '售后状态': ['售后状态', '售后']
    }

    actual_columns = {}
    for key, aliases in required_columns_map.items():
        col = get_column_with_alias(df, aliases)
        if col is None:
            raise Exception(f"文件缺少必需列: {key}，请检查列名是否匹配")
        actual_columns[key] = col

    for key, aliases in optional_columns_map.items():
        col = get_column_with_alias(df, aliases)
        if col is not None:
            actual_columns[key] = col

    df = df[[actual_columns[key] for key in actual_columns.keys()]].copy()
    df = df.rename(columns={v: k for k, v in actual_columns.items()})

    if hasattr(df, 'map'):
        df = df.map(lambda x: x.replace('\t', '') if isinstance(x, str) else x)
    else:
        df = df.applymap(lambda x: x.replace('\t', '') if isinstance(x, str) else x)

    df['子订单编号'] = df['子订单编号'].astype(str).apply(clean_numeric_value)
    df['主订单编号'] = df['主订单编号'].astype(str).apply(clean_numeric_value)
    df['商品ID'] = df['商品ID'].astype(str).apply(clean_numeric_value)

    empty_sub_order_ids = df[df['子订单编号'] == '0']
    if not empty_sub_order_ids.empty:
        logger.warning(
            f"发现 {len(empty_sub_order_ids)} 条子订单编号为空或无效的记录，已过滤"
        )
        df = df[df['子订单编号'] != '0']

    df = df.fillna('')
    df['支付完成时间'] = df['支付完成时间'].astype(str).apply(lambda x: x.strip())

    def combine_address(row):
        parts = [row['省'], row['市'], row['区']]
        return ''.join([str(part) for part in parts if part and str(part) != 'nan'])

    df['合并收货地址'] = df.apply(combine_address, axis=1)
    df = df.drop_duplicates(subset=['子订单编号'], keep='last')
    logger.info(f"清理后剩余唯一子订单数: {len(df)}")

    def extract_express_info(info):
        if not info or info == '':
            return '无'
        parts = re.split(r'[;,，；]', str(info))
        for part in parts:
            if re.search(r'[a-zA-Z0-9]{6,}', part):
                return part.strip()
        return str(info).strip()

    df['提取后的快递信息'] = df['快递信息'].apply(extract_express_info)

    def to_float(value):
        try:
            return float(str(value).replace(',', ''))
        except (ValueError, TypeError):
            return 0.0

    def to_int(value):
        try:
            return int(float(str(value).replace(',', '')))
        except (ValueError, TypeError):
            return 0

    df['商家收入金额'] = df['商家收入金额'].apply(to_float)
    df['商品数量'] = df['商品数量'].apply(to_int)

    return df


def send_data(webhook_url, db_file, item, index, total):
    row = item['data']
    action = item['action']
    record_id = item['record_id']

    logger.info(
        f"[{index+1}/{total}] 正在处理子订单: {row['子订单编号']}，动作: {action}"
    )

    payment_time_timestamp = time_to_timestamp(row['支付完成时间'])
    outbound_status = calc_outbound_status(row)

    try:
        quantity = int(row['商品数量']) if pd.notna(row['商品数量']) else 0
        merchant_income = (
            float(row['商家收入金额']) if pd.notna(row['商家收入金额']) else 0.0
        )
    except (ValueError, TypeError) as e:
        logger.error(
            f"[{index+1}/{total}] 数据格式错误: "
            f"子订单编号={row['子订单编号']}, 错误={e}"
        )
        return False

    values = {
        "fxNwEq": str(row['子订单编号']),
        "fCNsiv": str(row['商品ID']),
        "fBK7XT": str(row['选购商品']),
        "fy3AU0": quantity,
        "ff2OiF": merchant_income,
        "fJ0NdH": [{"text": str(row['订单状态'])}],
        "fNuVBy": payment_time_timestamp,
        "fWJEK9": str(row['合并收货地址']),
        "fTMuqw": str(row['提取后的快递信息']),
        "fzFeek": [{"text": outbound_status}]
    }

    if action == 'add':
        payload = {
            "schema": {
                "fxNwEq": "子订单编号", "fCNsiv": "商品ID",
                "fBK7XT": "商品名称", "fy3AU0": "下单数量",
                "ff2OiF": "商家收入金额", "fJ0NdH": "订单状态",
                "fNuVBy": "下单时间", "fWJEK9": "收货地址",
                "fTMuqw": "快递信息", "fzFeek": "出库状态"
            },
            "add_records": [{"values": values}]
        }
    else:
        payload = {
            "update_records": [{
                "record_id": record_id,
                "values": values
            }]
        }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(webhook_url, json=payload, timeout=10)

            try:
                resp_data = response.json()
                error_code = resp_data.get('errcode', 0)
            except Exception:
                resp_data = {}
                error_code = -1

            if response.status_code == 200 and error_code == 0:
                action_text = "新增" if action == 'add' else "更新"
                logger.info(
                    f"[{index+1}/{total}] ✓ 成功{action_text}子订单: "
                    f"{row['子订单编号']}"
                )

                new_record_id = None
                if action == 'add' and 'add_records' in resp_data:
                    records = resp_data['add_records']
                    if records and len(records) > 0:
                        new_record_id = records[0].get('record_id')

                db_action = (
                    'update' if action == 'update' and new_record_id is None else action
                )
                db_record_id = new_record_id if new_record_id else record_id

                if insert_or_update_db(db_file, row, db_action, db_record_id):
                    logger.info(f"[{index+1}/{total}] ✓ 本地数据库已更新")
                else:
                    logger.warning(
                        f"[{index+1}/{total}] ⚠ 本地数据库更新失败，但API同步成功"
                    )

                return True
            else:
                logger.error(
                    f"[{index+1}/{total}] ✗ 同步失败 API报错: "
                    f"errcode={error_code}, errmsg={resp_data.get('errmsg', '')}"
                )
                if attempt < max_retries - 1:
                    logger.info(f"[{index+1}/{total}] 等待 2 秒后重试...")
                    time.sleep(2)
        except requests.exceptions.Timeout:
            logger.error(f"[{index+1}/{total}] ✗ 请求超时，正在重试...")
            if attempt < max_retries - 1:
                time.sleep(2)
        except requests.exceptions.RequestException as e:
            logger.error(f"[{index+1}/{total}] ✗ 网络异常: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
        except Exception as e:
            logger.error(f"[{index+1}/{total}] ✗ 发送异常: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)

    logger.error(
        f"[{index+1}/{total}] ✗ 子订单 {row['子订单编号']} "
        f"同步失败，已跳过（本地数据库未更新）"
    )
    return False


def sync_shop(shop_name, config):
    folder = config['folder']
    db_file = config['db']
    webhook_url = config['webhook']

    logger.info(f"{'='*50}")
    logger.info(f"开始同步店铺: {shop_name}")
    logger.info(f"{'='*50}")

    if not webhook_url or not webhook_url.strip():
        logger.error(
            f"错误：{shop_name} 的 Webhook URL 未配置，"
            f"请在 .env 文件中设置 WECOM_WEBHOOK_URL_{shop_name.upper()}"
        )
        return

    folder_path = Path(folder)
    if not folder_path.exists():
        logger.warning(f"文件夹不存在，跳过: {folder}")
        return

    file_path, file_ext = get_latest_file(folder)
    if not file_path:
        logger.warning(f"在 {folder} 文件夹中未找到任何 CSV 或 Excel 文件，跳过")
        return

    try:
        logger.info(f"正在读取文件: {file_path}")
        init_db(db_file)
        df = read_file(file_path, file_ext)
        cleaned_df = clean_data(df)

        if cleaned_df.empty:
            logger.warning(f"警告：{shop_name} 清洗后没有有效订单数据")
            return

        sub_order_ids = cleaned_df['子订单编号'].tolist()
        if sub_order_ids:
            placeholders = ','.join(['?'] * len(sub_order_ids))
            with sqlite3.connect(db_file) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT sub_order_id FROM orders WHERE sub_order_id IN ({placeholders})",
                    sub_order_ids
                )
                existing_ids = {row[0] for row in cursor.fetchall()}

            exclude_statuses = get_order_status_filter()['exclude_statuses']
            if exclude_statuses:
                mask_new_exclude = (
                    ~cleaned_df['子订单编号'].isin(existing_ids)
                    & cleaned_df['订单状态'].isin(exclude_statuses)
                )
                before_count = len(cleaned_df)
                cleaned_df = cleaned_df[~mask_new_exclude]
                filtered_count = before_count - len(cleaned_df)
                if filtered_count > 0:
                    logger.info(
                        f"已过滤 {filtered_count} 条新订单中的无效状态"
                        f"（订单状态: {', '.join(exclude_statuses)}）"
                    )

        to_push = get_pending_updates(db_file, cleaned_df)

        if not to_push:
            logger.info("没有需要同步的订单数据")
            return

        total = len(to_push)
        logger.info(f"开始同步，共 {total} 条数据待处理")
        success_count = fail_count = 0
        consecutive_failures = 0

        for index, item in enumerate(to_push):
            if send_data(webhook_url, db_file, item, index, total):
                success_count += 1
                consecutive_failures = 0
            else:
                fail_count += 1
                consecutive_failures += 1

                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    logger.error(
                        f"检测到连续 {consecutive_failures} 次同步失败，"
                        f"已中断当前店铺同步。请检查网络或API状态。"
                    )
                    break

            time.sleep(0.5)

        logger.info(f"\n=== {shop_name} 同步完成 ===")
        logger.info(f"总处理订单数: {len(cleaned_df)}")
        logger.info(f"实际发生变动数: {total}")
        logger.info(f"成功数: {success_count}")
        logger.info(f"失败数: {fail_count}")

        if fail_count > 0:
            logger.warning(
                f"注意：有 {fail_count} 条数据同步失败，"
                f"本地数据库未更新，下次运行将自动重试"
            )

    except Exception as e:
        logger.error(f"\n错误: {e}")


def main():
    start_time = time.time()
    logger.info("=" * 50)
    logger.info("订单同步系统启动")
    logger.info("=" * 50)

    for shop_name, config in SHOP_CONFIGS.items():
        sync_shop(shop_name, config)

    elapsed_time = time.time() - start_time
    logger.info(f"\n{'='*50}")
    logger.info(f"所有店铺同步完成！总耗时: {elapsed_time:.2f} 秒")
    logger.info(f"{'='*50}")
