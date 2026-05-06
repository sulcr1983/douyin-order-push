# 技术债务归档

> 最后更新: 2026-04-22

## 已解决项

| 事项 | 解决方案 | 版本 |
|------|----------|------|
| 字段 ID 硬编码 | 提取到 FIELD_MAPPING 配置，可通过 .env 覆盖 | v3.0 |
| 新增店铺需改源码 | 改为从 .env 的 SHOP_NAMES 自动发现 | v3.0 |
| 多数据库文件分散 | 合并为统一 orders.db，自动迁移旧数据 | v3.0 |
| 启动前无自检 | 新增 health_check() 功能 | v3.0 |
| GUI 无统计和日志管理 | 新增店铺选择、统计看板、日志文件夹、文本报告 | v3.0 |
| `ALTER TABLE` 迁移死代码 | `shop_name` 字段改为在表结构中声明，不再依赖 ALTER | v3.0 |

## 保留的兼容性代码

| 位置 | 代码 | 说明 |
|------|------|------|
| `system/db.py` | `ALTER TABLE orders ADD COLUMN wecom_record_id` | 兼容旧数据库存在但字段缺失的情况 |
| `system/sync_engine.py` | `hasattr(df, 'map')` 分支 | 兼容 pandas < 2.0 |

## 待改进清单

1. **自动化测试**：核心业务逻辑无单元测试覆盖，代码变更依赖手动验证
2. **命名一致性**：`calc_outbound_status` → `compute_outbound_status`（低优先级）
3. **Webhook 校验**：启动时可增加轻量级 Webhook URL 格式校验
