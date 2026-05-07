# 订单同步系统

> 告别手动复制粘贴订单 — 把 CSV 往文件夹一丢，一键同步到企业微信智能表格

## 它解决了什么痛苦？

每次从电商平台导出订单后，还得手动复制粘贴到企业微信表格里，订单多了容易漏、容易错、还费时间。这个工具让你只需要：**把文件丢进文件夹 → 双击运行 → 全自动同步**。

## 3 个典型场景

1. **每日订单录入**：从店铺后台导出 CSV，丢进对应文件夹，双击运行，几百条订单 2 分钟全部同步到企业微信表格
2. **订单状态更新**：买家退款/发货后重新导出文件，工具自动识别变化，只更新有变动的订单，不重复不遗漏
3. **多店铺管理**：Qmaster 和天颐心选各一个文件夹，一次运行全部同步，互不干扰

## 运行方式

| 方式 | 操作 | 适用场景 |
|------|------|---------|
| 双击 BAT | 运行 `运行订单同步.bat` | 命令行模式，自动安装依赖 |
| 双击 PYW | 运行 `订单同步工具.pyw` | 图形界面模式，有日志窗口 |
| 手动命令 | `python main.py` | 开发调试 |
| 便携包 | 解压后双击 `启动订单同步.bat` | **无需安装 Python，给其他人用** |

## 使用步骤

### 首次使用

1. 复制 `.env.example` 为 `.env`
2. 用记事本打开 `.env`，填入各店铺的 Webhook URL

```env
WECOM_WEBHOOK_URL_QMASTER=https://qyapi.weixin.qq.com/cgi-bin/wedoc/smartsheet/webhook?key=你的密钥
WECOM_WEBHOOK_URL_TIANYIXINXUAN=https://qyapi.weixin.qq.com/cgi-bin/wedoc/smartsheet/webhook?key=你的密钥
```

3. 把订单 CSV/Excel 丢进对应店铺文件夹（`Qmaster/` / `tianyixinxuan/`）
4. 双击 `运行订单同步.bat` 或 `python main.py`

### Webhook 获取方式

1. 在企业微信智能表格中，点击右上角「⋯」→「接收外部数据」
2. 获取 Webhook 地址和示例数据格式
3. 将 Webhook 地址填入 `.env` 文件

### 订单文件

- 放入对应店铺文件夹即可，系统自动识别最新文件
- 支持格式：CSV、Excel（.xlsx、.xls）
- 支持编码：utf-8-sig、gbk

## 字段映射

企业微信表格字段 ID 配置在 `.env` 中，如果表格重建导致 ID 变化，在这里修改：

| 配置项 | 字段 ID | 说明 |
|--------|---------|------|
| `FIELD_SUB_ORDER_ID` | fxNwEq | 子订单编号 |
| `FIELD_PRODUCT_ID` | fCNsiv | 商品ID |
| `FIELD_PRODUCT_NAME` | fBK7XT | 商品名称 |
| `FIELD_QUANTITY` | fy3AU0 | 下单数量 |
| `FIELD_MERCHANT_INCOME` | ff2OiF | 商家收入金额 |
| `FIELD_ORDER_STATUS` | fJ0NdH | 订单状态 |
| `FIELD_PAYMENT_TIME` | fNuVBy | 下单时间 |
| `FIELD_ADDRESS` | fWJEK9 | 收货地址 |
| `FIELD_EXPRESS_INFO` | fTMuqw | 快递信息 |
| `FIELD_OUTBOUND_STATUS` | fzFeek | 出库状态 |

## 打包分发

给其他人使用时（对方不需要安装 Python），可以用 Nuitka 或嵌入式 Python 打包：

```bash
# Nuitka 目录模式（需安装 Nuitka + C 编译器）
nuitka --standalone --enable-plugin=tk-inter --output-dir=dist main.py

# 或用打包好的便携版（Python 嵌入式，零报毒）
# 见 portable/ 目录下的打包脚本
```

便携版解压后约 80MB，压缩包约 30MB，解压即可运行，不需要安装任何环境。

## 项目结构

```
ordersync/
├── main.py                 # 主程序（全部核心逻辑）
├── 订单同步工具.pyw          # GUI 图形界面
├── 运行订单同步.bat          # 启动脚本（自动安装依赖）
├── install.bat              # 一键部署脚本
├── build_exe.bat            # Nuitka 打包脚本
├── requirements.txt        # Python 依赖
├── .env / .env.example     # 配置文件 / 配置模板
├── Qmaster/                # Qmaster 店铺订单文件夹
├── tianyixinxuan/          # 天颐心选店铺订单文件夹
├── portable/               # 便携打包输出目录
└── logs/                   # 同步报告（自动生成）
```

## 常见问题

**双击没反应？**
→ 检查是否安装了 Python 并添加到环境变量，或使用便携版

**提示依赖安装失败？**
→ 检查网络连接，或手动执行 `pip install -r requirements.txt`

**企业微信没收到数据？**
→ 检查 `.env` 中的 Webhook URL 是否正确

**文件读取报错？**
→ 关闭 Excel 后重试（文件可能被占用）

## 商业价值

- 每日节省 30+ 分钟手动录入时间
- 消除人工复制粘贴导致的错漏风险
- 多店铺统一管理，扩展新店铺只需加一个文件夹和一行配置
- 便携版可一键分发给同事，无需安装任何环境

## 技术支持

如遇问题，请联系 苏哥<sulcr@qq.com>
