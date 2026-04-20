import unittest
import sqlite3
import os
import pandas as pd
from unittest.mock import patch, Mock
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(__file__))
import main


class TestOrderSync(unittest.TestCase):
    def setUp(self):
        self.test_db = tempfile.mktemp(suffix='.db')
        self.test_webhook = 'https://test.example.com/webhook'

        main.init_db(self.test_db)

        self.base_df = pd.DataFrame({
            '订单状态': ['待发货', '待发货', '待发货'],
            '主订单编号': ['M001', 'M002', 'M003'],
            '子订单编号': ['S001', 'S002', 'S003'],
            '支付完成时间': ['2024-01-01 12:00:00', '2024-01-02 12:00:00', '2024-01-03 12:00:00'],
            '选购商品': ['商品A', '商品B', '商品C'],
            '商品数量': [1, 2, 3],
            '商家收入金额': [100.0, 200.0, 300.0],
            '省': ['广东省', '浙江省', '江苏省'],
            '市': ['深圳市', '杭州市', '南京市'],
            '区': ['南山区', '西湖区', '鼓楼区'],
            '详细地址': ['xxx街道1号', 'yyy街道2号', 'zzz街道3号'],
            '快递信息': ['SF1234567890', 'YT9876543210', 'ZTO111222333'],
            '商品ID': ['P001', 'P002', 'P003']
        })

        self.cleaned_df = main.clean_data(self.base_df.copy())

    def tearDown(self):
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except PermissionError:
                time.sleep(0.1)
                try:
                    os.remove(self.test_db)
                except:
                    pass

    def test_scenario1_api_success(self):
        print("\n" + "="*50)
        print("测试场景1：API同步成功，验证本地数据库已更新")
        print("="*50)

        with patch('main.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'errcode': 0,
                'errmsg': 'ok',
                'add_records': [{'record_id': 'RECORD_001'}]
            }
            mock_post.return_value = mock_response

            item = {'action': 'add', 'data': self.cleaned_df.iloc[0], 'record_id': None}
            result = main.send_data(self.test_webhook, self.test_db, item, 0, 1)

            self.assertTrue(result, "API返回成功，send_data应返回True")

            time.sleep(0.1)
            with sqlite3.connect(self.test_db) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM orders WHERE sub_order_id = ?", ('001',))
                row = cursor.fetchone()

            self.assertIsNotNone(row, "数据库中应该有记录")
            self.assertEqual(row[0], '001', "子订单编号应为 '001'")
            self.assertEqual(row[16], 'RECORD_001', "wecom_record_id 应被保存")
            print("✓ 数据库已正确更新，wecom_record_id 已保存")

    def test_scenario2_api_failure_timeout(self):
        print("\n" + "="*50)
        print("测试场景2：API同步失败（网络超时），验证本地数据库保持原样")
        print("="*50)

        with sqlite3.connect(self.test_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM orders")
            count_before = cursor.fetchone()[0]
        print(f"同步前数据库记录数: {count_before}")

        with patch('main.requests.post') as mock_post:
            mock_post.side_effect = Exception("Connection timeout")

            item = {'action': 'add', 'data': self.cleaned_df.iloc[0], 'record_id': None}
            result = main.send_data(self.test_webhook, self.test_db, item, 0, 1)

            self.assertFalse(result, "API失败，send_data应返回False")

        time.sleep(0.1)
        with sqlite3.connect(self.test_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM orders")
            count_after = cursor.fetchone()[0]

            cursor.execute("SELECT * FROM orders WHERE sub_order_id = ?", ('001',))
            row = cursor.fetchone()

        print(f"同步失败后数据库记录数: {count_after}")
        self.assertEqual(count_before, count_after, "数据库记录数不应变化")
        self.assertIsNone(row, "数据库中不应该有该记录")
        print("✓ 数据库保持原样，未添加任何记录，下次运行将自动重试")

    def test_scenario3_api_failure_500_error(self):
        print("\n" + "="*50)
        print("测试场景3：API同步失败（500错误），验证本地数据库保持原样")
        print("="*50)

        with sqlite3.connect(self.test_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM orders")
            count_before = cursor.fetchone()[0]
        print(f"同步前数据库记录数: {count_before}")

        with patch('main.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.json.return_value = {
                'errcode': -1,
                'errmsg': 'system error'
            }
            mock_post.return_value = mock_response

            item = {'action': 'add', 'data': self.cleaned_df.iloc[0], 'record_id': None}
            result = main.send_data(self.test_webhook, self.test_db, item, 0, 1)

            self.assertFalse(result, "API返回500错误，send_data应返回False")

        time.sleep(0.1)
        with sqlite3.connect(self.test_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM orders")
            count_after = cursor.fetchone()[0]

            cursor.execute("SELECT * FROM orders WHERE sub_order_id = ?", ('001',))
            row = cursor.fetchone()

        print(f"同步失败后数据库记录数: {count_after}")
        self.assertEqual(count_before, count_after, "数据库记录数不应变化")
        self.assertIsNone(row, "数据库中不应该有该记录")
        print("✓ 数据库保持原样，未添加任何记录，下次运行将自动重试")

    def test_get_pending_updates_new_record(self):
        print("\n" + "="*50)
        print("测试：get_pending_updates 能正确识别新增记录")
        print("="*50)

        to_push = main.get_pending_updates(self.test_db, self.cleaned_df)

        self.assertEqual(len(to_push), 3, "应该有3条新增记录")
        self.assertTrue(all(item['action'] == 'add' for item in to_push), "所有记录都是新增")
        print(f"✓ 正确识别了 3 条新增记录")

    def test_get_pending_updates_no_duplicate_sync(self):
        print("\n" + "="*50)
        print("测试：已同步记录不会重复推送")
        print("="*50)

        with patch('main.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'errcode': 0,
                'errmsg': 'ok',
                'add_records': [{'record_id': 'RECORD_001'}]
            }
            mock_post.return_value = mock_response

            item = {'action': 'add', 'data': self.cleaned_df.iloc[0], 'record_id': None}
            main.send_data(self.test_webhook, self.test_db, item, 0, 1)

        time.sleep(0.1)
        to_push_second = main.get_pending_updates(self.test_db, self.cleaned_df)

        self.assertEqual(len(to_push_second), 2, "再次检查时只有2条新增记录")
        self.assertTrue(all(item['action'] == 'add' for item in to_push_second), "新记录仍是新增")
        print(f"✓ 已同步的记录不会被重复推送")

    def test_time_to_timestamp_various_formats(self):
        print("\n" + "="*50)
        print("测试：time_to_timestamp 能处理各种日期格式")
        print("="*50)

        test_cases = [
            ('2024-01-01 12:00:00', True),
            ('2024/01/01 12:00:00', True),
            ('2024-1-1 12:00:00', True),
            ('2024/01/01', True),
            ('invalid date', False),
        ]

        for time_str, should_work in test_cases:
            result = main.time_to_timestamp(time_str)
            if should_work:
                self.assertTrue(result.isdigit() and len(result) == 13,
                              f"时间 {time_str} 应该能被解析")
                print(f"  ✓ '{time_str}' -> {result}")
            else:
                self.assertEqual(result, main.time_to_timestamp(''),
                               f"无效时间 {time_str} 应降级为当前时间")
                print(f"  ✓ '{time_str}' -> 降级为当前时间")

    def test_clean_data_filters_invalid_sub_order_id(self):
        print("\n" + "="*50)
        print("测试：clean_data 能过滤无效的子订单编号")
        print("="*50)

        df_with_invalid = self.base_df.copy()
        new_row = pd.DataFrame([{
            '订单状态': '待发货',
            '主订单编号': 'M004',
            '子订单编号': 'invalid!@#',
            '支付完成时间': '2024-01-04 12:00:00',
            '选购商品': '商品D',
            '商品数量': 4,
            '商家收入金额': 400.0,
            '省': '广东省',
            '市': '深圳市',
            '区': '南山区',
            '详细地址': 'xxx街道4号',
            '快递信息': '',
            '商品ID': 'P004'
        }])
        df_with_invalid = pd.concat([df_with_invalid, new_row], ignore_index=True)

        cleaned = main.clean_data(df_with_invalid)

        self.assertEqual(len(cleaned), 3, "无效子订单编号应被过滤")
        print(f"✓ 4条记录清洗后剩余3条，无效编号已过滤")


class TestInsertOrUpdate(unittest.TestCase):
    def setUp(self):
        self.test_db = tempfile.mktemp(suffix='.db')
        main.init_db(self.test_db)

    def tearDown(self):
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except PermissionError:
                time.sleep(0.1)
                try:
                    os.remove(self.test_db)
                except:
                    pass

    def test_insert_new_record(self):
        print("\n" + "="*50)
        print("测试：insert_or_update_db 能正确插入新记录")
        print("="*50)

        df = pd.DataFrame({
            '子订单编号': ['S001'],
            '订单状态': ['待发货'],
            '主订单编号': ['M001'],
            '支付完成时间': ['2024-01-01 12:00:00'],
            '选购商品': ['商品A'],
            '商品数量': [1],
            '商家收入金额': [100.0],
            '省': ['广东省'],
            '市': ['深圳市'],
            '区': ['南山区'],
            '详细地址': ['xxx街道1号'],
            '合并收货地址': ['广东省深圳市南山区'],
            '提取后的快递信息': ['SF1234567890'],
            '商品ID': ['P001'],
            '发货时间': ['']
        })

        result = main.insert_or_update_db(self.test_db, df.iloc[0], 'add', 'REC_001')

        self.assertTrue(result)

        time.sleep(0.1)
        with sqlite3.connect(self.test_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE sub_order_id = ?", ('001',))
            row = cursor.fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row[16], 'REC_001')
        print("✓ 新记录插入成功，wecom_record_id 正确保存")

    def test_update_existing_record(self):
        print("\n" + "="*50)
        print("测试：insert_or_update_db 能正确更新已有记录")
        print("="*50)

        df = pd.DataFrame({
            '子订单编号': ['S001'],
            '订单状态': ['待发货'],
            '主订单编号': ['M001'],
            '支付完成时间': ['2024-01-01 12:00:00'],
            '选购商品': ['商品A'],
            '商品数量': [1],
            '商家收入金额': [100.0],
            '省': ['广东省'],
            '市': ['深圳市'],
            '区': ['南山区'],
            '详细地址': ['xxx街道1号'],
            '合并收货地址': ['广东省深圳市南山区'],
            '提取后的快递信息': ['SF1234567890'],
            '商品ID': ['P001'],
            '发货时间': ['']
        })

        main.insert_or_update_db(self.test_db, df.iloc[0], 'add', 'REC_001')

        df.loc[0, '订单状态'] = '已发货'
        df.loc[0, '发货时间'] = '2024-01-02 12:00:00'

        result = main.insert_or_update_db(self.test_db, df.iloc[0], 'update', 'REC_001')

        self.assertTrue(result)

        time.sleep(0.1)
        with sqlite3.connect(self.test_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT order_status, shipping_time FROM orders WHERE sub_order_id = ?", ('001',))
            row = cursor.fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], '已发货')
        self.assertEqual(row[1], '2024-01-02 12:00:00')
        print("✓ 记录更新成功，状态和发货时间已更新")


if __name__ == '__main__':
    print("\n" + "="*60)
    print("订单同步系统 - 自动化测试")
    print("="*60)

    unittest.main(verbosity=2)