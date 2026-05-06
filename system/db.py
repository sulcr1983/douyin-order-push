import sqlite3
import logging
from datetime import datetime
from pathlib import Path

from .utils import calc_outbound_status

logger = logging.getLogger(__name__)


def init_db(db_file):
    db_path = Path(db_file)
    db_dir = db_path.parent
    if str(db_dir) and not db_dir.exists():
        db_dir.mkdir(parents=True, exist_ok=True)

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
            cursor.execute(
                "UPDATE orders SET wecom_record_id = ? WHERE sub_order_id = ?",
                (record_id, sub_order_id)
            )
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
                        row['子订单编号'], row['订单状态'], row['主订单编号'],
                        row['支付完成时间'], shipping_time, row['选购商品'],
                        int(row['商品数量']), float(row['商家收入金额']),
                        row['省'], row['市'], row['区'], row['详细地址'],
                        row['合并收货地址'], row['提取后的快递信息'],
                        row['商品ID'], current_time, record_id
                    ))
                elif action == 'update':
                    cursor.execute('''UPDATE orders SET
                        order_status=?, main_order_id=?, payment_time=?, shipping_time=?,
                        product_name=?, quantity=?, merchant_income=?, province=?, city=?,
                        district=?, address=?, full_address=?, express_info=?, product_id=?,
                        last_sync_time=?, wecom_record_id=?
                        WHERE sub_order_id=?''',
                        (row['订单状态'], row['主订单编号'], row['支付完成时间'],
                         shipping_time, row['选购商品'], int(row['商品数量']),
                         float(row['商家收入金额']), row['省'], row['市'], row['区'],
                         row['详细地址'], row['合并收货地址'],
                         row['提取后的快递信息'], row['商品ID'], current_time,
                         record_id, row['子订单编号'])
                    )
                conn.commit()
                return True
            except Exception as e:
                conn.rollback()
                raise e
    except Exception as e:
        logger.error(f"数据库操作失败: {e}")
        return False


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
        current_merchant_income = round(float(row['商家收入金额']), 2)

        outbound_status = calc_outbound_status(row)

        db_row = db_dict.get(sub_order_id)

        if not db_row:
            to_push.append({'action': 'add', 'data': row, 'record_id': None})
            new_count += 1
        else:
            db_wecom_record_id = db_row[-1]
            db_order_status = str(db_row[1])
            db_merchant_income = round(float(db_row[7]), 2)
            current_values = (
                str(order_status), str(row['主订单编号']),
                str(row['支付完成时间']), str(shipping_time),
                str(row['选购商品']), int(row['商品数量']),
                current_merchant_income, str(row['省']), str(row['市']),
                str(row['区']), str(row['详细地址']),
                str(row['合并收货地址']), str(row['提取后的快递信息']),
                str(row['商品ID'])
            )

            db_compare_values = (
                str(db_order_status), str(db_row[2]), str(db_row[3]),
                str(db_row[4]), str(db_row[5]), int(db_row[6]),
                db_merchant_income, str(db_row[8]), str(db_row[9]),
                str(db_row[10]), str(db_row[11]), str(db_row[12]),
                str(db_row[13]), str(db_row[14])
            )

            db_status_has_close = any(
                kw in db_order_status for kw in ["退款", "取消", "关闭"]
            )
            db_outbound_status = calc_outbound_status({
                '订单状态': db_order_status,
                '售后状态': '',
                '发货时间': db_row[4]
            })
            force_update_refund = (
                outbound_status == "已关闭" and not db_status_has_close
            )

            if not db_wecom_record_id:
                to_push.append({'action': 'add', 'data': row, 'record_id': None})
                new_count += 1
            elif (
                force_update_refund
                or str(current_values) != str(db_compare_values)
                or db_outbound_status != outbound_status
            ):
                to_push.append({
                    'action': 'update', 'data': row, 'record_id': db_wecom_record_id
                })
                update_count += 1
            else:
                skip_count += 1

    logger.info(
        f"数据对比完成：{new_count} 条需新增，"
        f"{update_count} 条需更新，{skip_count} 条已同步过无需处理。"
    )
    return to_push
