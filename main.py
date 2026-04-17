import pandas as pd
import requests
import time
import re
import os
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# Webhook URL
WEBHOOK_URL = os.getenv('WECOM_WEBHOOK_URL')

# 数据库文件
DB_FILE = os.getenv('DB_FILE', 'orders_storage_v5.db')

# CSV文件夹路径
CSV_FOLDER_PATH = os.getenv('CSV_FOLDER_PATH', '')


def get_latest_csv(folder_path):
    """获取文件夹中最新的CSV文件"""
    if not folder_path:
        folder_path = os.path.dirname(os.path.abspath(__file__))
    
    print(f"正在扫描文件夹: {folder_path}")
    if not os.path.exists(folder_path):
        raise Exception(f"错误：指定的文件夹不存在，请检查路径。")
    
    csv_files = []
    for file in os.listdir(folder_path):
        if file.endswith('.csv'):
            file_path = os.path.join(folder_path, file)
            mtime = os.path.getmtime(file_path)
            csv_files.append((file_path, mtime))
    
    if not csv_files:
        raise Exception("错误：在指定文件夹中未找到任何 CSV 文件，请检查路径。")
    
    csv_files.sort(key=lambda x: x[1], reverse=True)
    latest_file = csv_files[0][0]
    
    mtime = os.path.getmtime(latest_file)
    formatted_time = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
    
    print(f"已自动锁定最新订单文件: [{os.path.basename(latest_file)}] (创建时间: {formatted_time})")
    return latest_file


def time_to_timestamp(time_str):
    """将时间字符串转换为13位毫秒级Unix时间戳"""
    try:
        cleaned_time = str(time_str).strip()
        dt = datetime.strptime(cleaned_time, '%Y-%m-%d %H:%M:%S')
        timestamp = int(dt.timestamp() * 1000)
        return str(timestamp)
    except Exception as e:
        timestamp = int(datetime.now().timestamp() * 1000)
        return str(timestamp)


def init_db():
    """初始化数据库"""
    db_dir = os.path.dirname(DB_FILE)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 创建orders表（新增 wecom_record_id 字段）
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
    
    # 兼容旧数据库：尝试追加 wecom_record_id 列
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN wecom_record_id TEXT")
        print("已升级数据库表结构，新增 wecom_record_id 字段")
    except sqlite3.OperationalError:
        # 列已存在，直接忽略
        pass
        
    conn.commit()
    conn.close()
    print("数据库初始化完成")


def update_db_record_id(sub_order_id, record_id):
    """将企业微信返回的 record_id 保存到本地数据库"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE orders SET wecom_record_id = ? WHERE sub_order_id = ?", (record_id, sub_order_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"保存企业微信 record_id 失败: {e}")


def read_csv_file(file_path):
    encodings = ['utf-8-sig', 'gbk']
    for encoding in encodings:
        try:
            df = pd.read_csv(file_path, encoding=encoding)
            print(f"成功读取CSV文件，使用编码: {encoding}")
            return df
        except Exception:
            continue
    raise Exception("无法读取CSV文件，请检查文件编码")


def get_column_with_alias(df, column_names):
    for col in column_names:
        if col in df.columns:
            return col
    return None


def clean_data(df):
    """清洗数据(逻辑保持不变)"""
    required_columns_map = {
        '订单状态': ['订单状态'], '主订单编号': ['主订单编号', '主订单号'], '子订单编号': ['子订单编号', '子订单号'],
        '支付完成时间': ['支付完成时间', '付款时间', '支付时间'], '选购商品': ['选购商品', '商品名称', '商品'],
        '商品数量': ['商品数量', '数量'], '商家收入金额': ['商家收入金额', '商家收入', '收入金额', '商家实收'],
        '省': ['省', '省份'], '市': ['市', '城市'], '区': ['区', '区县'],
        '详细地址': ['详细地址', '地址'], '快递信息': ['快递信息', '物流信息', '快递'], '商品ID': ['商品ID', '商品id', '商品编码', '商家编码']
    }
    optional_columns_map = {'发货时间': ['发货时间', '出库时间', ' shipping time', 'ship_time']}
    
    actual_columns = {}
    for key, aliases in required_columns_map.items():
        col = get_column_with_alias(df, aliases)
        if col is None: raise Exception(f"CSV文件缺少必需列: {key}")
        actual_columns[key] = col
    
    for key, aliases in optional_columns_map.items():
        col = get_column_with_alias(df, aliases)
        if col is not None: actual_columns[key] = col
    
    df = df[[actual_columns[key] for key in actual_columns.keys()]].copy()
    df = df.rename(columns={v: k for k, v in actual_columns.items()})
    
    def clean_numeric_column(col):
        return df[col].astype(str).apply(lambda x: re.sub(r'\D', '', x))
    
    df['子订单编号'] = clean_numeric_column('子订单编号')
    df['主订单编号'] = clean_numeric_column('主订单编号')
    df['商品ID'] = clean_numeric_column('商品ID')
    df = df.fillna('')
    df['支付完成时间'] = df['支付完成时间'].astype(str).apply(lambda x: x.strip())
    
    def combine_address(row):
        parts = [row['省'], row['市'], row['区']]
        return ''.join([str(part) for part in parts if part and str(part) != 'nan'])
    
    df['合并收货地址'] = df.apply(combine_address, axis=1)
    df = df.drop_duplicates(subset=['子订单编号'], keep='last')
    print(f"清理后剩余唯一子订单数: {len(df)}")
    
    def extract_express_info(info):
        if not info or info == '': return '无'
        parts = re.split(r'[;,，；]', str(info))
        for part in parts:
            if re.search(r'[a-zA-Z0-9]{6,}', part): return part.strip()
        return str(info).strip()
    
    df['提取后的快递信息'] = df['快递信息'].apply(extract_express_info)
    
    def to_float(value):
        try: return float(str(value).replace(',', ''))
        except: return 0.0
    df['商家收入金额'] = df['商家收入金额'].apply(to_float)
    
    return df


def check_and_update_db(df):
    """检查并更新数据库，返回包含动作策略(add/update)的数据集"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    to_push = []
    new_count = update_count = skip_count = 0
    
    for _, row in df.iterrows():
        sub_order_id = row['子订单编号']
        order_status = row['订单状态']
        
        # 获取所有相关字段，注意提取我们新增的 wecom_record_id
        cursor.execute('''
        SELECT order_status, main_order_id, payment_time, shipping_time, 
               product_name, quantity, merchant_income, 
               province, city, district, address, full_address, express_info, product_id,
               wecom_record_id
        FROM orders WHERE sub_order_id = ?
        ''', (sub_order_id,))
        db_row = cursor.fetchone()
        
        current_time = datetime.now().isoformat()
        shipping_time = row.get('发货时间', '')
        
        if not db_row:
            # 1. 纯新订单，插入数据库
            cursor.execute('''
            INSERT INTO orders (
                sub_order_id, order_status, main_order_id, payment_time, 
                shipping_time, product_name, quantity, merchant_income, 
                province, city, district, address, full_address, express_info, 
                product_id, last_sync_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                sub_order_id, order_status, row['主订单编号'], row['支付完成时间'],
                shipping_time, row['选购商品'], row['商品数量'], row['商家收入金额'],
                row['省'], row['市'], row['区'], row['详细地址'], row['合并收货地址'],
                row['提取后的快递信息'], row['商品ID'], current_time
            ))
            to_push.append({'action': 'add', 'data': row, 'record_id': None})
            new_count += 1
            
        else:
            db_wecom_record_id = db_row[-1]
            # 构建比对值 (排除最后一个元素 wecom_record_id)
            current_values = (
                order_status, row['主订单编号'], row['支付完成时间'], shipping_time, 
                row['选购商品'], row['商品数量'], row['商家收入金额'], 
                row['省'], row['市'], row['区'], row['详细地址'], row['合并收货地址'], 
                row['提取后的快递信息'], row['商品ID']
            )
            
            # 2. 如果库里有，但没有 record_id (可能是之前推送企微失败的遗留数据)
            if not db_wecom_record_id:
                cursor.execute('''UPDATE orders SET order_status=?, main_order_id=?, payment_time=?, shipping_time=?, product_name=?, quantity=?, merchant_income=?, province=?, city=?, district=?, address=?, full_address=?, express_info=?, product_id=?, last_sync_time=? WHERE sub_order_id=?''', (order_status, row['主订单编号'], row['支付完成时间'], shipping_time, row['选购商品'], row['商品数量'], row['商家收入金额'], row['省'], row['市'], row['区'], row['详细地址'], row['合并收货地址'], row['提取后的快递信息'], row['商品ID'], current_time, sub_order_id))
                to_push.append({'action': 'add', 'data': row, 'record_id': None})
                new_count += 1
                
            # 3. 数据有变化，且有企微的 record_id，执行真实更新
            elif current_values != db_row[:-1]:
                cursor.execute('''UPDATE orders SET order_status=?, main_order_id=?, payment_time=?, shipping_time=?, product_name=?, quantity=?, merchant_income=?, province=?, city=?, district=?, address=?, full_address=?, express_info=?, product_id=?, last_sync_time=? WHERE sub_order_id=?''', (order_status, row['主订单编号'], row['支付完成时间'], shipping_time, row['选购商品'], row['商品数量'], row['商家收入金额'], row['省'], row['市'], row['区'], row['详细地址'], row['合并收货地址'], row['提取后的快递信息'], row['商品ID'], current_time, sub_order_id))
                to_push.append({'action': 'update', 'data': row, 'record_id': db_wecom_record_id})
                update_count += 1
                
            # 4. 无变化，跳过
            else:
                skip_count += 1
                
    conn.commit()
    conn.close()
    
    print(f"检测到 {new_count} 条需新增，{update_count} 条需更新，{skip_count} 条已同步过无需处理。")
    return to_push


def send_data(item, index, total):
    """发送数据到Webhook，支持 新增(add) 与 更新(update) 动作分流"""
    row = item['data']
    action = item['action']
    record_id = item['record_id']
    
    payment_time_timestamp = time_to_timestamp(row['支付完成时间'])
    shipping_time = row.get('发货时间', '')
    outbound_status = "已出库" if shipping_time else "待出库"
    
    # 统一提取 values，新增和更新的内部格式要求一致
    values = {
        "fxNwEq": row['子订单编号'],
        "fCNsiv": row['商品ID'],
        "fBK7XT": row['选购商品'],
        "fy3AU0": int(row['商品数量']),
        "ff2OiF": float(row['商家收入金额']),
        "fJ0NdH": [{"text": row['订单状态']}],
        "fNuVBy": payment_time_timestamp,
        "fWJEK9": row['合并收货地址'],
        "fTMuqw": row['提取后的快递信息'],
        "fzFeek": [{"text": outbound_status}]
    }
    
    # 根据动作分发载荷结构
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
    else:  # 'update'
        payload = {
            "update_records": [{
                "record_id": record_id,
                "values": values
            }]
        }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(WEBHOOK_URL, json=payload, timeout=10)
            
            # 企业微信即便遇到业务错误也会返回200，需检查JSON内的 errcode
            try:
                resp_data = response.json()
                error_code = resp_data.get('errcode', 0)
            except:
                resp_data = {}
                error_code = -1
                
            if response.status_code == 200 and error_code == 0:
                action_text = "新增" if action == 'add' else "更新"
                print(f"[{index+1}/{total}] 成功{action_text}子订单: {row['子订单编号']}")
                
                # 新增成功后，拦截企微返回的 record_id 存进数据库，为将来的“更新”做准备
                if action == 'add' and 'add_records' in resp_data:
                    records = resp_data['add_records']
                    if records and len(records) > 0:
                        new_record_id = records[0].get('record_id')
                        if new_record_id:
                            update_db_record_id(row['子订单编号'], new_record_id)
                            
                return True
            else:
                print(f"[{index+1}/{total}] 同步失败 API报错: errcode={error_code}, errmsg={resp_data.get('errmsg', '')}")
                if attempt < max_retries - 1:
                    time.sleep(2)
        except Exception as e:
            print(f"[{index+1}/{total}] 发送异常: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
    return False


def main():
    start_time = time.time()
    try:
        init_db()
        csv_file = get_latest_csv(CSV_FOLDER_PATH)
        df = read_csv_file(csv_file)
        cleaned_df = clean_data(df)
        
        # to_push 变成了一个包含执行策略的列表
        to_push = check_and_update_db(cleaned_df)
        
        total = len(to_push)
        success_count = fail_count = 0
        
        # 迭代处理
        for index, item in enumerate(to_push):
            if send_data(item, index, total):
                success_count += 1
            else:
                fail_count += 1
            time.sleep(0.5)
            
        elapsed_time = time.time() - start_time
        print("\n=== 同步完成 ===")
        print(f"总处理订单数: {len(cleaned_df)}")
        print(f"实际发生变动数: {total}")
        print(f"成功数: {success_count}")
        print(f"失败数: {fail_count}")
        print(f"耗时: {elapsed_time:.2f} 秒")
        
    except Exception as e:
        print(f"\n错误: {e}")

if __name__ == "__main__":
    main()