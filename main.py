import pandas as pd
import requests
import time
import re
import os
import sqlite3
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

LOG_FILE = os.getenv('LOG_FILE', 'sync_log.txt')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

EXCLUDE_ORDER_STATUSES = [
    status.strip() for status in os.getenv('EXCLUDE_ORDER_STATUSES', '已关闭,已取消,未付款,待付款,交易关闭,取消订单').split(',')
    if status.strip()
]

MAX_CONSECUTIVE_FAILURES = int(os.getenv('MAX_CONSECUTIVE_FAILURES', '10'))

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

logger = setup_logging()

WEBHOOK_URLS = {
    'Qmaster': os.getenv('WECOM_WEBHOOK_URL_QMASTER', ''),
    'tianyixinxuan': os.getenv('WECOM_WEBHOOK_URL_TIANYIXINXUAN', '')
}

DB_FILES = {
    'Qmaster': os.getenv('DB_FILE_QMASTER', 'orders_qmaster.db'),
    'tianyixinxuan': os.getenv('DB_FILE_TIANYIXINXUAN', 'orders_tianyixinxuan.db')
}

SHOP_CONFIGS = {
    'Qmaster': {'folder': 'Qmaster', 'db': DB_FILES['Qmaster'], 'webhook': WEBHOOK_URLS['Qmaster']},
    'tianyixinxuan': {'folder': 'tianyixinxuan', 'db': DB_FILES['tianyixinxuan'], 'webhook': WEBHOOK_URLS['tianyixinxuan']}
}


def get_latest_file(folder_path, extensions=['.csv', '.xlsx']):
    if not folder_path:
        folder_path = os.path.dirname(os.path.abspath(__file__))

    logger.info(f"正在扫描文件夹: {folder_path}")
    if not os.path.exists(folder_path):
        return None, None

    files = []
    for file in os.listdir(folder_path):
        if any(file.lower().endswith(ext) for ext in extensions):
            file_path = os.path.join(folder_path, file)
            mtime = os.path.getmtime(file_path)
            files.append((file_path, mtime))

    if not files:
        return None, None

    files.sort(key=lambda x: x[1], reverse=True)
    latest_file = files[0][0]

    mtime = os.path.getmtime(latest_file)
    formatted_time = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')

    logger.info(f"已自动锁定最新文件: [{os.path.basename(latest_file)}] (创建时间: {formatted_time})")
    return latest_file, os.path.splitext(latest_file)[1].lower()


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


def init_db(db_file):
    db_dir = os.path.dirname(db_file)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)

    try:
        with sqlite3.connect(db_file) as conn:
            cursor = conn.cursor()

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                sub_order_id TEXT PRIMARY KEY,
                order_status TEXT,
                main_order_id TEXT,
                payment_time TEXT,
                shipping_time TEXT,
                product_name TEXT,
                quantity INTEGER,
                merchant_income REAL,
                province TEXT,
                city TEXT,
                district TEXT,
                address TEXT,
                full_address TEXT,
                express_info TEXT,
                product_id TEXT,
                last_sync_time TIMESTAMP,
                wecom_record_id TEXT
            )
            ''')

            try:
                cursor.execute("ALTER TABLE orders ADD COLUMN wecom_record_id TEXT")
                logger.info("已升级数据库表结构，新增 wecom_record_id 字段")
            except sqlite3.OperationalError:
                pass

            conn.commit()
        logger.info(f"数据库 {db_file} 初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise


def update_db_record_id(db_file, sub_order_id, record_id):
    try:
        with sqlite3.connect(db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE orders SET wecom_record_id = ? WHERE sub_order_id = ?", (record_id, sub_order_id))
            conn.commit()
    except Exception as e:
        logger.error(f"保存企业微信 record_id 失败: {e}")


def insert_or_update_db(db_file, row, action, record_id=None):
    try:
        with sqlite3.connect(db_file) as conn:
            try:
                cursor = conn.cursor()
                current_time = datetime.now().isoformat()
                shipping_time = row.get('发货时间', '')

                if action == 'add':
                    cursor.execute('''
                    INSERT OR REPLACE INTO orders (
                        sub_order_id, order_status, main_order_id, payment_time,
                        shipping_time, product_name, quantity, merchant_income,
                        province, city, district, address, full_address, express_info,
                        product_id, last_sync_time, wecom_record_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        row['子订单编号'], row['订单状态'], row['主订单编号'], row['支付完成时间'],
                        shipping_time, row['选购商品'], int(row['商品数量']), float(row['商家收入金额']),
                        row['省'], row['市'], row['区'], row['详细地址'], row['合并收货地址'],
                        row['提取后的快递信息'], row['商品ID'], current_time, record_id
                    ))
                elif action == 'update':
                    cursor.execute('''UPDATE orders SET
                        order_status=?, main_order_id=?, payment_time=?, shipping_time=?,
                        product_name=?, quantity=?, merchant_income=?, province=?, city=?,
                        district=?, address=?, full_address=?, express_info=?, product_id=?,
                        last_sync_time=?, wecom_record_id=?
                        WHERE sub_order_id=?''',
                        (row['订单状态'], row['主订单编号'], row['支付完成时间'], shipping_time,
                         row['选购商品'], int(row['商品数量']), float(row['商家收入金额']),
                         row['省'], row['市'], row['区'], row['详细地址'], row['合并收货地址'],
                         row['提取后的快递信息'], row['商品ID'], current_time, record_id,
                         row['子订单编号'])
                    )
                conn.commit()
                return True
            except Exception as e:
                conn.rollback()
                raise e
    except Exception as e:
        logger.error(f"数据库操作失败: {e}")
        return False


def read_file(file_path, file_ext):
    encodings = ['utf-8-sig', 'gbk']

    if file_ext == '.csv':
        for encoding in encodings:
            try:
                df = pd.read_csv(file_path, encoding=encoding)
                logger.info(f"成功读取CSV文件，使用编码: {encoding}")
                return df
            except PermissionError:
                raise Exception("文件正在被 Excel 占用，请关闭 Excel 后重试，或将文件复制一份再运行。")
            except Exception:
                continue
        raise Exception("无法读取CSV文件，请检查文件编码")

    elif file_ext in ['.xlsx', '.xls']:
        try:
            try:
                df = pd.read_excel(file_path, engine='openpyxl')
                logger.info(f"成功读取Excel文件(openpyxl引擎)")
                return df
            except PermissionError:
                raise Exception("文件正在被 Excel 占用，请关闭 Excel 后重试，或将文件复制一份再运行。")
            except Exception:
                pass

            try:
                df = pd.read_excel(file_path, engine='xlrd')
                logger.info(f"成功读取Excel文件(xlrd引擎)")
                return df
            except PermissionError:
                raise Exception("文件正在被 Excel 占用，请关闭 Excel 后重试，或将文件复制一份再运行。")
            except Exception:
                pass

            raise Exception(f"无法读取Excel文件，请确保已安装 openpyxl 或 xlrd 库")

        except Exception as e:
            if "文件正在被 Excel 占用" in str(e):
                raise
            raise Exception(f"无法读取Excel文件，请确保已安装 openpyxl 或 xlrd 库: {e}")

    raise Exception(f"不支持的文件格式: {file_ext}")


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


def clean_data(df):
    df.columns = df.columns.str.strip()

    required_columns_map = {
        '订单状态': ['订单状态'], '主订单编号': ['主订单编号', '主订单号'], '子订单编号': ['子订单编号', '子订单号'],
        '支付完成时间': ['支付完成时间', '付款时间', '支付时间'], '选购商品': ['选购商品', '商品名称', '商品'],
        '商品数量': ['商品数量', '数量'], '商家收入金额': ['商家收入金额', '商家收入', '收入金额', '商家实收'],
        '省': ['省', '省份'], '市': ['市', '城市'], '区': ['区', '区县'],
        '详细地址': ['详细地址', '地址'], '快递信息': ['快递信息', '物流信息', '快递'], '商品ID': ['商品ID', '商品id', '商品编码', '商家编码']
    }
    optional_columns_map = {'发货时间': ['发货时间', '出库时间', 'shipping time', 'ship_time']}

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

    df['子订单编号'] = df['子订单编号'].astype(str).apply(clean_numeric_value)
    df['主订单编号'] = df['主订单编号'].astype(str).apply(clean_numeric_value)
    df['商品ID'] = df['商品ID'].astype(str).apply(clean_numeric_value)

    empty_sub_order_ids = df[df['子订单编号'] == '0']
    if not empty_sub_order_ids.empty:
        logger.warning(f"发现 {len(empty_sub_order_ids)} 条子订单编号为空或无效的记录，已过滤")
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

    df = filter_orders_by_status(df, get_order_status_filter())

    return df


def get_pending_updates(db_file, df):
    to_push = []
    new_count = update_count = skip_count = 0

    logger.info("正在对比本地数据库与文件数据差异...")

    sub_order_ids = df['子订单编号'].tolist()
    if not sub_order_ids:
        logger.info("数据对比完成：0 条需新增，0 条需更新，0 条已同步过无需处理。")
        return to_push

    placeholders = ','.join(['?'] * len(sub_order_ids))
    query = f'''
    SELECT sub_order_id, order_status, main_order_id, payment_time, shipping_time,
           product_name, quantity, merchant_income,
           province, city, district, address, full_address, express_info, product_id,
           wecom_record_id
    FROM orders WHERE sub_order_id IN ({placeholders})
    '''

    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute(query, sub_order_ids)
        db_rows = cursor.fetchall()
        db_dict = {row[0]: row for row in db_rows}

    for _, row in df.iterrows():
        sub_order_id = row['子订单编号']
        order_status = row['订单状态']
        shipping_time = row.get('发货时间', '')

        db_row = db_dict.get(sub_order_id)

        if not db_row:
            to_push.append({'action': 'add', 'data': row, 'record_id': None})
            new_count += 1
        else:
            db_wecom_record_id = db_row[-1]
            current_values = (
                order_status, row['主订单编号'], row['支付完成时间'], shipping_time,
                row['选购商品'], row['商品数量'], row['商家收入金额'],
                row['省'], row['市'], row['区'], row['详细地址'], row['合并收货地址'],
                row['提取后的快递信息'], row['商品ID']
            )

            if not db_wecom_record_id:
                to_push.append({'action': 'add', 'data': row, 'record_id': None})
                new_count += 1
            elif current_values != db_row[1:-1]:
                to_push.append({'action': 'update', 'data': row, 'record_id': db_wecom_record_id})
                update_count += 1
            else:
                skip_count += 1

    logger.info(f"数据对比完成：{new_count} 条需新增，{update_count} 条需更新，{skip_count} 条已同步过无需处理。")
    return to_push


def send_data(webhook_url, db_file, item, index, total):
    row = item['data']
    action = item['action']
    record_id = item['record_id']

    logger.info(f"[{index+1}/{total}] 正在处理子订单: {row['子订单编号']}，动作: {action}")

    payment_time_timestamp = time_to_timestamp(row['支付完成时间'])
    shipping_time = row.get('发货时间', '')
    outbound_status = "已出库" if shipping_time else "待出库"

    try:
        quantity = int(row['商品数量']) if pd.notna(row['商品数量']) else 0
        merchant_income = float(row['商家收入金额']) if pd.notna(row['商家收入金额']) else 0.0
    except (ValueError, TypeError) as e:
        logger.error(f"[{index+1}/{total}] 数据格式错误: 子订单编号={row['子订单编号']}, 错误={e}")
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
                "fxNwEq": "子订单编号", "fCNsiv": "商品ID", "fBK7XT": "商品名称",
                "fy3AU0": "下单数量", "ff2OiF": "商家收入金额", "fJ0NdH": "订单状态",
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
                logger.info(f"[{index+1}/{total}] ✓ 成功{action_text}子订单: {row['子订单编号']}")

                new_record_id = None
                if action == 'add' and 'add_records' in resp_data:
                    records = resp_data['add_records']
                    if records and len(records) > 0:
                        new_record_id = records[0].get('record_id')

                db_action = 'update' if action == 'update' and new_record_id is None else action
                db_record_id = new_record_id if new_record_id else record_id

                if insert_or_update_db(db_file, row, db_action, db_record_id):
                    logger.info(f"[{index+1}/{total}] ✓ 本地数据库已更新")
                else:
                    logger.warning(f"[{index+1}/{total}] ⚠ 本地数据库更新失败，但API同步成功")

                return True
            else:
                logger.error(f"[{index+1}/{total}] ✗ 同步失败 API报错: errcode={error_code}, errmsg={resp_data.get('errmsg', '')}")
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

    logger.error(f"[{index+1}/{total}] ✗ 子订单 {row['子订单编号']} 同步失败，已跳过（本地数据库未更新）")
    return False


def sync_shop(shop_name, config):
    folder = config['folder']
    db_file = config['db']
    webhook_url = config['webhook']

    logger.info(f"{'='*50}")
    logger.info(f"开始同步店铺: {shop_name}")
    logger.info(f"{'='*50}")

    if not webhook_url or not webhook_url.strip():
        logger.error(f"错误：{shop_name} 的 Webhook URL 未配置，请在 .env 文件中设置 WECOM_WEBHOOK_URL_{shop_name.upper()}")
        return

    if not os.path.exists(folder):
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

        to_push = get_pending_updates(db_file, cleaned_df)

        if not to_push:
            logger.info(f"没有需要同步的订单数据")
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
                    logger.error(f"检测到连续 {consecutive_failures} 次同步失败，已中断当前店铺同步。请检查网络或API状态。")
                    break

            time.sleep(0.5)

        logger.info(f"\n=== {shop_name} 同步完成 ===")
        logger.info(f"总处理订单数: {len(cleaned_df)}")
        logger.info(f"实际发生变动数: {total}")
        logger.info(f"成功数: {success_count}")
        logger.info(f"失败数: {fail_count}")

        if fail_count > 0:
            logger.warning(f"注意：有 {fail_count} 条数据同步失败，本地数据库未更新，下次运行将自动重试")

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


if __name__ == "__main__":
    main()
