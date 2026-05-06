# 技术债务归档

> 最后更新: 2026-05-06

## 未引用的工具函数

| 位置 | 函数 | 状态 | 说明 |
|------|------|------|------|
| `system/db.py` | `update_db_record_id()` | 保留 | 可用于手动修复 record_id，暂无调用方 |
| `system/utils.py` | `filter_orders_by_status()` | 保留 | 通用订单状态过滤器，当前同步逻辑内联处理了过滤 |

## 兼容性 Hack

| 位置 | 代码 | 说明 |
|------|------|------|
| `system/sync_engine.py` `clean_data()` | `hasattr(df, 'map')` 分支 | pandas < 2.0 使用 `applymap`，>= 2.0 使用 `map`。当最低依赖升至 pandas 2.0 后可移除 |
| `system/db.py` `init_db()` | `ALTER TABLE ... ADD COLUMN wecom_record_id` | 数据库迁移兼容代码，新部署环境无需此分支 |

## 命名一致性建议

| 当前命名 | 建议命名 | 原因 |
|----------|----------|------|
| `calc_outbound_status()` | `compute_outbound_status()` | 与其他函数命名风格统一（避免缩写） |
| `to_push` (变量) | `pending_updates` | 与函数名 `get_pending_updates` 保持一致 |
| `SHOP_CONFIGS` 键名混合 | 统一为小写或大写 | 当前 `Qmaster`/`tianyixinxuan` 大小写不一致 |

## 架构改进建议

1. **新增店铺流程**：当前需手动修改 `system/config.py` 添加 `SHOP_CONFIGS` 条目，可改为从 `.env` 自动发现
2. **Webhook 通用化**：当前硬编码企业微信 API 格式，可抽象为适配器模式支持飞书/钉钉
3. **GUI 增强**：`订单同步工具.pyw` 可增加店铺选择下拉框和同步进度条
