# 订单同步系统

> 告别手动复制粘贴订单 — 把 CSV 往文件夹一丢，一键同步到企业微信智能表格

## 它解决了什么痛苦？

每次从电商平台导出订单后，还得手动复制粘贴到企业微信表格里，订单多了容易漏、容易错、还费时间。这个工具让你只需要：**把文件丢进文件夹 → 点一下按钮 → 全自动同步**。

## 3 个典型场景

1. **每日订单录入**：从店铺后台导出 CSV，丢进对应文件夹，双击运行，几百条订单 2 分钟全部同步到企业微信表格
2. **订单状态更新**：买家退款/发货后重新导出文件，工具自动识别变化，只更新有变动的订单，不重复不遗漏
3. **多店铺管理**：Qmaster 和天颐心选各一个文件夹，一次运行全部同步，互不干扰

## 极简使用（3 步）

1. **配置**：复制 `.env.example` 为 `.env`，填入你的 Webhook 地址
2. **放文件**：把订单 CSV/Excel 丢进对应店铺文件夹（Qmaster / tianyixinxuan）
3. **运行**：双击 `运行订单同步.bat` 或 `订单同步工具.pyw`

## 配置说明

### 首次使用

1. 复制 `.env.example` 为 `.env`
2. 用记事本打开 `.env`，填入各店铺的 Webhook URL

```env
WECOM_WEBHOOK_URL_QMASTER=https://qyapi.weixin.qq.com/cgi-bin/wedoc/smartsheet/webhook?key=你的密钥
WECOM_WEBHOOK_URL_TIANYIXINXUAN=https://qyapi.weixin.qq.com/cgi-bin/wedoc/smartsheet/webhook?key=你的密钥
```

### Webhook 获取方式

1. 在企业微信智能表格中，点击右上角「⋯」→「接收外部数据」
2. 获取 Webhook 地址和示例数据格式
3. 将 Webhook 地址填入 `.env` 文件

### 订单文件

- 放入对应店铺文件夹即可，系统自动识别最新文件
- 支持格式：CSV、Excel（.xlsx、.xls）
- 支持编码：utf-8-sig、gbk

## 运行方式

| 方式 | 操作 | 适用场景 |
|------|------|---------|
| 双击 BAT | 运行 `运行订单同步.bat` | 命令行模式，自动安装依赖 |
| 双击 PYW | 运行 `订单同步工具.pyw` | 图形界面模式，有日志窗口 |
| 手动命令 | `python main.py` | 开发调试 |

## 项目结构

```
ordersync/
├── main.py                 # 入口文件
├── 订单同步工具.pyw          # GUI 入口
├── 运行订单同步.bat          # 启动脚本（自动安装依赖）
├── requirements.txt        # Python 依赖
├── .env.example            # 配置模板（首次使用需复制为 .env）
├── system/                 # 核心逻辑（勿手动修改）
│   ├── config.py           # 配置加载
│   ├── sync_engine.py      # 同步引擎
│   ├── db.py               # 数据库操作
│   └── utils.py            # 工具函数
├── Qmaster/                # Qmaster 店铺订单文件夹
└── tianyixinxuan/          # 天颐心选店铺订单文件夹
```

## 常见问题

**双击没反应？**
→ 检查是否安装了 Python 并添加到环境变量

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

## 技术支持

如遇问题，请联系 <sulcr@qq.com>
