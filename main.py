import os
import sys
import re
import time
import sqlite3
import logging
import shutil
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
import requests

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / '.env'
ENV_EXAMPLE = BASE_DIR / '.env.example'

if not ENV_FILE.exists():
    if ENV_EXAMPLE.exists():
        shutil.copy(str(ENV_EXAMPLE), str(ENV_FILE))
        print("=" * 50)
        print("  [!] 检测到首次运行，已自动生成 .env 配置文件")
        print("  [!] 请用记事本打开 .env 文件")
        print("  [!] 在等号后面填入你的企业微信 Webhook 地址")
        print("  [!] 完成后重新运行本程序")
        print("=" * 50)
        os.system(f'start notepad "{ENV_FILE}"')
        sys.exit(0)
    else:
        print("=" * 50)
        print("  [错误] 找不到配置文件模板")
        print("  请从 GitHub 重新下载完整项目")
        print("=" * 50)
        sys.exit(1)

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


logger = setup_logging()


def time_to_timestamp(time_str):
    try:
        cleaned_time = str(time_str).strip()
        if not cleaned_time:
            raise ValueError("时间字符串为空")
        dt = pd.to_datetime(cleaned_time, errors='coerce')
        if pd.isna(dt):
            raise ValueError(f"无法解析时间: {cleaned_time}")
        return str(int(dt.timestamp() * 1000))
    except Exception:
        return str(int(datetime.now().timestamp() * 1000))


def get_column_with_alias(df, column_names):
    for col in column_names:
        if col in df.columns:
            return col
    return None


def clean_numeric_value(value):
    cleaned = str(value).strip()
    return cleaned if cleaned else '0'


def get_order_status_filter():
    return {'exclude_statuses': EXCLUDE_ORDER_STATUSES, 'include_statuses': []}


def calc_outbound_status(row):
    order_status = str(row.get('订单状态', '')).replace('\t', '').strip()
    after_sales_status = str(row.get('售后状态', '')).replace('\t', '').strip()
    shipping_time = str(row.get('发货时间', '')).replace('\t', '').strip()
    if any(kw in order_status for kw in ["退款", "取消", "关闭"]) or "退款" in after_sales_status:
        return "已关闭"
    elif any(kw in order_status for kw in ["已发货", "已签收"]) or (shipping_time and shipping_time != 'nan' and shipping_time.strip()):
        return "已出库"
    else:
        return "待出库"


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
                sub_order_id TEXT NOT NULL,
                shop_name TEXT NOT NULL DEFAULT '',
                order_status TEXT, main_order_id TEXT, payment_time TEXT, shipping_time TEXT,
                product_name TEXT, quantity INTEGER, merchant_income REAL,
                province TEXT, city TEXT, district TEXT, address TEXT, full_address TEXT,
                express_info TEXT, product_id TEXT, last_sync_time TIMESTAMP, wecom_record_id TEXT,
                PRIMARY KEY (sub_order_id, shop_name)
            )
            ''')
            for col in ['wecom_record_id', 'shop_name']:
                try:
                    cursor.execute(f"ALTER TABLE orders ADD COLUMN {col} TEXT")
                    logger.info(f"已升级数据库表结构，新增 {col} 字段")
                except sqlite3.OperationalError:
                    pass
            conn.commit()
        logger.info(f"数据库 {db_file} 初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise


def migrate_old_dbs(unified_db, shop_configs):
    base_dir = Path(unified_db).parent
    for shop_name in shop_configs:
        old_db = base_dir / f'orders_{shop_name.lower()}.db'
        if not old_db.exists():
            continue
        logger.info(f"检测到旧版数据库: {old_db}，正在迁移至统一数据库...")
        try:
            with sqlite3.connect(str(old_db)) as old_conn:
                old_cur = old_conn.cursor()
                old_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='orders'")
                if not old_cur.fetchone():
                    continue
                old_cur.execute("PRAGMA table_info(orders)")
                columns = [row[1] for row in old_cur.fetchall()]
                old_cur.execute("SELECT * FROM orders")
                rows = old_cur.fetchall()
            with sqlite3.connect(unified_db) as new_conn:
                new_cur = new_conn.cursor()
                migrated = 0
                for row_data in rows:
                    record = dict(zip(columns, row_data))
                    record['shop_name'] = shop_name
                    placeholders = ','.join(['?'] * len(record))
                    new_cur.execute(f"INSERT OR IGNORE INTO orders ({','.join(record.keys())}) VALUES ({placeholders})", list(record.values()))
                    migrated += new_cur.rowcount
                new_conn.commit()
            backup_path = old_db.with_suffix('.db.bak')
            old_db.rename(backup_path)
            logger.info(f"迁移完成: 导入 {migrated} 条记录，旧文件已备份为 {backup_path.name}")
        except Exception as e:
            logger.warning(f"旧数据库迁移失败 ({old_db.name}): {e}")


def insert_or_update_db(db_file, row, action, record_id=None, shop_name=''):
    try:
        with sqlite3.connect(db_file) as conn:
            try:
                cursor = conn.cursor()
                current_time = datetime.now().isoformat()
                shipping_time = row.get('发货时间', '')
                if action == 'add':
                    cursor.execute('''
                    INSERT OR REPLACE INTO orders (
                        sub_order_id, shop_name, order_status, main_order_id, payment_time,
                        shipping_time, product_name, quantity, merchant_income,
                        province, city, district, address, full_address, express_info,
                        product_id, last_sync_time, wecom_record_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        row['子订单编号'], shop_name, row['订单状态'], row['主订单编号'],
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
                        WHERE sub_order_id=? AND shop_name=?''',
                        (row['订单状态'], row['主订单编号'], row['支付完成时间'],
                         shipping_time, row['选购商品'], int(row['商品数量']),
                         float(row['商家收入金额']), row['省'], row['市'], row['区'],
                         row['详细地址'], row['合并收货地址'],
                         row['提取后的快递信息'], row['商品ID'], current_time,
                         record_id, row['子订单编号'], shop_name)
                    )
                conn.commit()
                return True
            except Exception as e:
                conn.rollback()
                raise e
    except Exception as e:
        logger.error(f"数据库操作失败: {e}")
        return False


def get_pending_updates(db_file, df, shop_name):
    to_push = []
    new_count = update_count = skip_count = 0
    logger.info("正在对比本地数据库与文件数据差异...")
    sub_order_ids = df['子订单编号'].tolist()
    if not sub_order_ids:
        logger.info("数据对比完成：0 条需新增，0 条需更新，0 条已同步过无需处理。")
        return to_push

    placeholders = ','.join(['?'] * len(sub_order_ids))
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT sub_order_id, shop_name, order_status, main_order_id, payment_time, shipping_time, "
            f"product_name, quantity, merchant_income, province, city, district, address, full_address, "
            f"express_info, product_id, wecom_record_id FROM orders WHERE sub_order_id IN ({placeholders}) AND shop_name = ?",
            sub_order_ids + [shop_name]
        )
        db_dict = {row[0]: row for row in cursor.fetchall()}

    for _, row in df.iterrows():
        sub_order_id = row['子订单编号']
        order_status = row['订单状态']
        shipping_time = row.get('发货时间', '')
        current_merchant_income = round(float(row['商家收入金额']), 2)
        outs = calc_outbound_status(row)
        db_row = db_dict.get(sub_order_id)
        if not db_row:
            to_push.append({'action': 'add', 'data': row, 'record_id': None})
            new_count += 1
        else:
            db_rcid = db_row[-1]
            db_os = str(db_row[2])
            db_mi = round(float(db_row[7]), 2)
            cv = (str(order_status), str(row['主订单编号']), str(row['支付完成时间']), str(shipping_time),
                  str(row['选购商品']), int(row['商品数量']), current_merchant_income,
                  str(row['省']), str(row['市']), str(row['区']), str(row['详细地址']),
                  str(row['合并收货地址']), str(row['提取后的快递信息']), str(row['商品ID']))
            dv = (str(db_os), str(db_row[3]), str(db_row[4]), str(db_row[5]),
                  str(db_row[6]), int(db_row[7]), db_mi, str(db_row[9]), str(db_row[10]),
                  str(db_row[11]), str(db_row[12]), str(db_row[13]), str(db_row[14]), str(db_row[15]))
            db_has_close = any(kw in db_os for kw in ["退款", "取消", "关闭"])
            db_outs = calc_outbound_status({'订单状态': db_os, '售后状态': '', '发货时间': db_row[5]})
            force_upd = (outs == "已关闭" and not db_has_close)
            if not db_rcid:
                to_push.append({'action': 'add', 'data': row, 'record_id': None})
                new_count += 1
            elif force_upd or str(cv) != str(dv) or db_outs != outs:
                to_push.append({'action': 'update', 'data': row, 'record_id': db_rcid})
                update_count += 1
            else:
                skip_count += 1
    logger.info(f"数据对比完成：{new_count} 条需新增，{update_count} 条需更新，{skip_count} 条已同步过无需处理。")
    return to_push


def health_check():
    any_error = False
    print("=" * 50)
    print("  系统健康检查")
    print("=" * 50)
    print(f"  [1/5] Python版本: {sys.version.split()[0]} ✓")
    print(f"  [2/5] .env配置文件: ", end='')
    if ENV_FILE.exists():
        print("✓")
    else:
        print("✗ (缺失)")
        any_error = True
    print(f"  [3/5] 店铺配置检测 ({len(SHOP_NAMES)} 个店铺):")
    nw = max((len(n) for n in SHOP_NAMES), default=8) + 2
    for name in SHOP_NAMES:
        cfg = SHOP_CONFIGS.get(name, {})
        wh_ok = bool(cfg.get('webhook', ''))
        fd_ok = Path(cfg.get('folder', '')).exists()
        icon = "✓" if (wh_ok and fd_ok) else "⚠"
        print(f"    {name.ljust(nw)}Webhook: {'已配置' if wh_ok else '未配置'}, 文件夹: {'存在' if fd_ok else '不存在'} {icon}")
        if not wh_ok or not fd_ok:
            any_error = True
    has_files = False
    print(f"  [4/5] 订单文件检测:")
    for name in SHOP_NAMES:
        fp = Path(SHOP_CONFIGS.get(name, {}).get('folder', ''))
        if fp.exists():
            flist = [f for f in fp.iterdir() if f.is_file() and f.suffix.lower() in ['.csv', '.xlsx', '.xls']]
            if flist:
                has_files = True
                print(f"    {name.ljust(nw)}最新文件: {max(flist, key=lambda f: f.stat().st_mtime).name}")
            else:
                print(f"    {name.ljust(nw)}无订单文件")
    if not has_files:
        print("  ⚠ 所有店铺文件夹中均未检测到订单文件")
        any_error = True
    print(f"  [5/5] Python依赖检测:")
    for dep in ['pandas', 'requests', 'dotenv', 'openpyxl']:
        try:
            __import__(dep)
            print(f"    {dep.ljust(nw)}✓")
        except ImportError:
            print(f"    {dep.ljust(nw)}✗")
            any_error = True
    print("=" * 50)
    if any_error:
        print("  健康检查完成：存在未通过项，请根据提示修复")
        print("=" * 50)
        return False
    print("  健康检查完成：全部通过，准备开始同步")
    print("=" * 50)
    return True


def get_latest_file(folder_path, extensions=None):
    if extensions is None:
        extensions = ['.csv', '.xlsx']
    folder = Path(folder_path)
    logger.info(f"正在扫描文件夹: {folder.name}")
    if not folder.exists():
        return None, None
    files = [(f, f.stat().st_mtime) for f in folder.iterdir() if f.is_file() and any(f.suffix.lower() == ext for ext in extensions)]
    if not files:
        return None, None
    files.sort(key=lambda x: x[1], reverse=True)
    lf = files[0][0]
    logger.info(f"已自动锁定最新文件: [{lf.name}] (创建时间: {datetime.fromtimestamp(files[0][1]).strftime('%Y-%m-%d %H:%M')})")
    return str(lf), lf.suffix.lower()


def read_file(file_path, file_ext):
    encodings = ['utf-8-sig', 'gbk']
    perm_err = "文件正在被 Excel 占用，请关闭 Excel 后重试，或将文件复制一份再运行。"
    if file_ext == '.csv':
        for enc in encodings:
            try:
                return pd.read_csv(file_path, encoding=enc)
            except PermissionError:
                raise Exception(perm_err)
            except Exception:
                continue
        raise Exception("无法读取CSV文件，请检查文件编码")
    elif file_ext in ['.xlsx', '.xls']:
        for engine in ['openpyxl', 'xlrd']:
            try:
                return pd.read_excel(file_path, engine=engine)
            except PermissionError:
                raise Exception(perm_err)
            except Exception:
                continue
        raise Exception("无法读取Excel文件，请确保已安装 openpyxl 或 xlrd 库")
    raise Exception(f"不支持的文件格式: {file_ext}")


def clean_data(df):
    df.columns = df.columns.str.strip()
    col_map = {
        '订单状态': ['订单状态'], '主订单编号': ['主订单编号', '主订单号'], '子订单编号': ['子订单编号', '子订单号'],
        '支付完成时间': ['支付完成时间', '付款时间', '支付时间'], '选购商品': ['选购商品', '商品名称', '商品'],
        '商品数量': ['商品数量', '数量'], '商家收入金额': ['商家收入金额', '商家收入', '收入金额', '商家实收'],
        '省': ['省', '省份'], '市': ['市', '城市'], '区': ['区', '区县'],
        '详细地址': ['详细地址', '地址'], '快递信息': ['快递信息', '物流信息', '快递'],
        '商品ID': ['商品ID', '商品id', '商品编码', '商家编码']
    }
    opt_map = {'发货时间': ['发货时间', '出库时间', 'shipping time', 'ship_time'], '售后状态': ['售后状态', '售后']}
    actual = {}
    for key, aliases in col_map.items():
        col = get_column_with_alias(df, aliases)
        if col is None:
            raise Exception(f"文件缺少必需列: {key}，请检查列名是否匹配")
        actual[key] = col
    for key, aliases in opt_map.items():
        col = get_column_with_alias(df, aliases)
        if col is not None:
            actual[key] = col
    df = df[[actual[k] for k in actual.keys()]].copy()
    df = df.rename(columns={v: k for k, v in actual.items()})
    fn = df.map if hasattr(df, 'map') else df.applymap
    df = fn(lambda x: x.replace('\t', '') if isinstance(x, str) else x)
    for col in ['子订单编号', '主订单编号', '商品ID']:
        df[col] = df[col].astype(str).apply(clean_numeric_value)
    empty = df[df['子订单编号'] == '0']
    if not empty.empty:
        logger.warning(f"发现 {len(empty)} 条子订单编号为空或无效的记录，已过滤")
        df = df[df['子订单编号'] != '0']
    df = df.fillna('')
    df['支付完成时间'] = df['支付完成时间'].astype(str).apply(lambda x: x.strip())
    df['合并收货地址'] = df.apply(lambda r: ''.join([str(r[c]) for c in ['省', '市', '区'] if str(r.get(c, '')) != 'nan']), axis=1)
    df = df.drop_duplicates(subset=['子订单编号'], keep='last')
    logger.info(f"清理后剩余唯一子订单数: {len(df)}")

    def extract_expr(info):
        if not info:
            return '无'
        parts = re.split(r'[;,，；]', str(info))
        for p in parts:
            if re.search(r'[a-zA-Z0-9]{6,}', p):
                return p.strip()
        return str(info).strip()
    df['提取后的快递信息'] = df['快递信息'].apply(extract_expr)
    df['商家收入金额'] = df['商家收入金额'].apply(lambda v: float(str(v).replace(',', '')) if str(v).replace(',', '').replace('.', '').replace('-', '').isdigit() else 0.0)
    df['商品数量'] = df['商品数量'].apply(lambda v: int(float(str(v).replace(',', ''))) if str(v).replace(',', '').replace('.', '').replace('-', '').isdigit() else 0)
    return df


def send_data(webhook_url, db_file, item, index, total, shop_name):
    row = item['data']
    action = item['action']
    record_id = item['record_id']
    logger.info(f"[{index+1}/{total}] 正在处理子订单: {row['子订单编号']}，动作: {action}")
    ts = time_to_timestamp(row['支付完成时间'])
    outs = calc_outbound_status(row)
    try:
        qty = int(row['商品数量']) if pd.notna(row['商品数量']) else 0
        inc = float(row['商家收入金额']) if pd.notna(row['商家收入金额']) else 0.0
    except (ValueError, TypeError) as e:
        logger.error(f"[{index+1}/{total}] 数据格式错误: {e}")
        return False
    fm = FIELD_MAPPING
    values = {
        fm['sub_order_id']: str(row['子订单编号']), fm['product_id']: str(row['商品ID']),
        fm['product_name']: str(row['选购商品']), fm['quantity']: qty,
        fm['merchant_income']: inc, fm['order_status']: [{"text": str(row['订单状态'])}],
        fm['payment_time']: ts, fm['address']: str(row['合并收货地址']),
        fm['express_info']: str(row['提取后的快递信息']), fm['outbound_status']: [{"text": outs}]
    }
    payload = {"add_records": [{"values": values}], "schema": {fm[k]: v for k, v in {
        'sub_order_id': '子订单编号', 'product_id': '商品ID', 'product_name': '商品名称',
        'quantity': '下单数量', 'merchant_income': '商家收入金额', 'order_status': '订单状态',
        'payment_time': '下单时间', 'address': '收货地址', 'express_info': '快递信息',
        'outbound_status': '出库状态'
    }.items()}} if action == 'add' else {"update_records": [{"record_id": record_id, "values": values}]}
    for attempt in range(3):
        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)
            rd = resp.json() if resp.status_code == 200 else {}
            ec = rd.get('errcode', -1) if rd else -1
            if resp.status_code == 200 and ec == 0:
                nt = "新增" if action == 'add' else "更新"
                logger.info(f"[{index+1}/{total}] ✓ 成功{nt}子订单: {row['子订单编号']}")
                nrid = None
                if action == 'add' and 'add_records' in rd and rd['add_records']:
                    nrid = rd['add_records'][0].get('record_id')
                da = 'update' if action == 'update' and nrid is None else action
                if insert_or_update_db(db_file, row, da, nrid or record_id, shop_name):
                    logger.info(f"[{index+1}/{total}] ✓ 本地数据库已更新")
                else:
                    logger.warning(f"[{index+1}/{total}] ⚠ 本地数据库更新失败")
                return True
            else:
                logger.error(f"[{index+1}/{total}] ✗ 同步失败: errcode={ec}, {rd.get('errmsg', '')}")
                if attempt < 2:
                    time.sleep(2)
        except requests.exceptions.Timeout:
            logger.error(f"[{index+1}/{total}] ✗ 超时")
            if attempt < 2:
                time.sleep(2)
        except requests.exceptions.RequestException as e:
            logger.error(f"[{index+1}/{total}] ✗ 网络异常: {e}")
            if attempt < 2:
                time.sleep(2)
        except Exception as e:
            logger.error(f"[{index+1}/{total}] ✗ 发送异常: {e}")
            if attempt < 2:
                time.sleep(2)
    logger.error(f"[{index+1}/{total}] ✗ 子订单 {row['子订单编号']} 同步失败")
    return False


def sync_shop(shop_name, config):
    folder = config['folder']
    db_file = config['db']
    webhook_url = config['webhook']
    logger.info(f"{'='*50}\n开始同步店铺: {shop_name}\n{'='*50}")
    if not webhook_url or not webhook_url.strip():
        logger.error(f"错误：{shop_name} 的 Webhook URL 未配置")
        return
    if not Path(folder).exists():
        logger.warning(f"文件夹不存在: {folder}")
        return
    file_path, file_ext = get_latest_file(folder)
    if not file_path:
        logger.warning(f"在 {folder} 中未找到文件")
        return
    try:
        logger.info(f"正在读取文件: {file_path}")
        init_db(db_file)
        migrate_old_dbs(db_file, SHOP_NAMES)
        cleaned_df = clean_data(read_file(file_path, file_ext))
        if cleaned_df.empty:
            logger.warning(f"清洗后没有有效订单数据")
            return
        sub_ids = cleaned_df['子订单编号'].tolist()
        if sub_ids:
            ph = ','.join(['?'] * len(sub_ids))
            with sqlite3.connect(db_file) as conn:
                exist_ids = {r[0] for r in conn.cursor().execute(f"SELECT sub_order_id FROM orders WHERE sub_order_id IN ({ph}) AND shop_name = ?", sub_ids + [shop_name]).fetchall()}
            exclude = get_order_status_filter()['exclude_statuses']
            if exclude:
                mask = (~cleaned_df['子订单编号'].isin(exist_ids)) & cleaned_df['订单状态'].isin(exclude)
                cleaned_df = cleaned_df[~mask]
                fc = mask.sum()
                if fc:
                    logger.info(f"已过滤 {fc} 条新订单中的无效状态")
        to_push = get_pending_updates(db_file, cleaned_df, shop_name)
        if not to_push:
            logger.info("没有需要同步的订单数据")
            return
        total = len(to_push)
        logger.info(f"开始同步，共 {total} 条")
        success = fail = 0
        consec = 0
        for idx, item in enumerate(to_push):
            if send_data(webhook_url, db_file, item, idx, total, shop_name):
                success += 1
                consec = 0
            else:
                fail += 1
                consec += 1
                if consec >= MAX_CONSECUTIVE_FAILURES:
                    logger.error(f"连续 {consec} 次失败，中断同步")
                    break
            time.sleep(0.5)
        logger.info(f"\n=== {shop_name} 同步完成 ===")
        logger.info(f"总处理: {len(cleaned_df)}, 变动: {total}, 成功: {success}, 失败: {fail}")
        if fail:
            logger.warning(f"有 {fail} 条失败，下次将重试")
    except Exception as e:
        logger.error(f"\n错误: {e}")


def main():
    start = time.time()
    logger.info("=" * 50)
    logger.info("订单同步系统启动")
    logger.info("=" * 50)
    if not health_check():
        logger.error("健康检查未通过，同步终止")
        return
    for name, cfg in SHOP_CONFIGS.items():
        sync_shop(name, cfg)
    logger.info(f"\n{'='*50}\n所有店铺同步完成！总耗时: {time.time() - start:.2f} 秒\n{'='*50}")


if __name__ == "__main__":
    main()
