📊 订单同步系统 · 企业级智能解决方案

从 CSV 到企业微信智能表格 —— 全自动订单同步引擎
告别手动录入 · 零错误 · 极速处理

---

🚀 产品定位

订单同步系统 是一款轻量化数据集成工具。将电商平台导出的 CSV/Excel 订单文件，一键自动同步至企业微信智能表格，实现订单数据的自动化流转与集中管理。

---

💼 解决的核心痛点

痛点 传统方式 我们的方案
⏱️ 效率低下 手动复制粘贴，200条订单需30分钟 2分钟 完成全量同步

❌ 数据错误 人工操作易漏、易错、格式混乱 自动映射字段，零误差

🔄 状态滞后 订单状态变更需重新录入 智能识别变化，增量更新

🏢 多店铺管理 多个后台来回切换，管理困难 统一入口，分店隔离

---

🎯 典型应用场景

场景 解决的问题 效率提升
每日订单录入 店铺后台导出 → 丢进文件夹 → 双击运行 90%+
订单状态更新 退款/发货后重新导出，自动识别变更订单 95%+
多店铺管理 不同店铺分文件夹存放，一次运行全部同步 80%+


---

⚙️ 运行方式对比

方式 操作 适用人群 技术门槛
🖱️ 双击 BAT 运行订单同步.bat 普通用户（推荐） 
⭐ 无
🪟 图形界面 订单同步工具.pyw 需要可视日志的用户
⭐ 无
💻 命令行 python main.py 开发调试
 ⭐⭐⭐
📦 便携版 解压后双击 启动订单同步.bat 无需安装 Python 的任何人 
⭐ 无

---

📋 快速上手（3 分钟）

第一步：配置 Webhook

```bash
# 复制配置模板
cp .env.example .env

# 填入企业微信智能表格的 Webhook 地址

WECOM_WEBHOOK_URL_SHOP1=https://qyapi.weixin.qq.com/cgi-bin/wedoc/smartsheet/webhook?key=你的密钥1

WECOM_WEBHOOK_URL_SHOP2=https://qyapi.weixin.qq.com/cgi-bin/wedoc/smartsheet/webhook?key=你的密钥2
```

📌 获取 Webhook：企业微信智能表格 → 右上角「⋯」→「接收外部数据」→ 复制地址

第二步：配置店铺文件夹

系统按文件夹名称区分不同店铺，你只需：

1. 在项目根目录下新建店铺文件夹（如 店铺A/、店铺B/）

2. 在 .env 中配置对应的 Webhook，格式为：
   ```
   WECOM_WEBHOOK_URL_店铺文件夹名=你的Webhook地址
   ```

💡 示例：文件夹名为 mystore，则配置项为 WECOM_WEBHOOK_URL_MYSTORE=xxx

第三步：放入订单文件

```
店铺A/           ← 放店铺A的订单 CSV/Excel

店铺B/           ← 放店铺B的订单 CSV/Excel
```

系统自动识别文件夹内的最新文件，支持 .csv / .xlsx / .xls

第四步：双击运行

· 有 Python 环境 → 双击 运行订单同步.bat

· 无 Python 环境 → 使用便携版，双击 启动订单同步.bat

✅ 完成！订单已同步至企业微信智能表格

---

🔗 字段映射表

企业微信表格字段 ID 可在 .env 中自定义配置：


配置项 字段 ID 业务含义
FIELD_SUB_ORDER_ID fxNwEq 子订单编号
FIELD_PRODUCT_ID fCNsiv 商品 ID
FIELD_PRODUCT_NAME fBK7XT 商品名称
FIELD_QUANTITY fy3AU0 下单数量
FIELD_MERCHANT_INCOME ff2OiF 商家收入金额
FIELD_ORDER_STATUS fJ0NdH 订单状态
FIELD_PAYMENT_TIME fNuVBy 下单时间
FIELD_ADDRESS fWJEK9 收货地址
FIELD_EXPRESS_INFO fTMuqw 快递信息
FIELD_OUTBOUND_STATUS fzFeek 出库状态

💡 表格重建导致 ID 变化？只需修改 .env 中的对应值即可，无需改动代码。

---

📦 分发方案 · 零依赖便携版

给没有 Python 环境的同事使用？ 我们提供了两种打包方案：

方案 命令 压缩包大小 特点
Nuitka 打包 nuitka --standalone main.py ~30MB 高性能，启动快

嵌入式 Python portable/ 目录脚本 ~30MB 零报毒，解压即用

✅ 便携版解压后约 80MB，压缩包约 30MB，无需安装任何环境，双击即可运行。

---

📁 项目结构

```
ordersync/
├── 🚀 main.py                 # 核心同步引擎
├── 🖥️ 订单同步工具.pyw         # GUI 图形界面
├── ⚡ 运行订单同步.bat          # 一键启动（自动装依赖）
├── 🔧 install.bat              # 部署脚本
├── 📦 build_exe.bat            # Nuitka 打包脚本
├── 📄 requirements.txt        # Python 依赖清单
├── 🔐 .env / .env.example     # 配置文件 / 模板
├── 📂 店铺A/                  # 店铺订单目录（按需新建）
├── 📂 店铺B/                  # 店铺订单目录（按需新建）
├── 📂 portable/               # 便携版输出目录
└── 📂 logs/                   # 同步报告（自动生成）
```

📌 店铺文件夹无需预置，按实际需要创建即可，系统会自动识别。

---

❓ 常见问题

问题 解决方案
❌ 双击没反应？ 检查 Python 环境，或直接使用便携版

❌ 依赖安装失败？ 检查网络，或手动执行 pip install -r requirements.txt

❌ 企业微信没收到数据？ 检查 .env 中的 Webhook URL 是否正确

❌ 文件读取报错？ 关闭 Excel 后重试（文件被占用）

❌ 想加新店铺？ 新建文件夹 + .env 加一行 Webhook 配置

---

💰 商业价值

维度 价值体现

⏰ 时间成本 每日节省 30+ 分钟 手动录入时间

🎯 准确性 消除人工复制粘贴导致的错漏风险（降至 0）

📈 可扩展性 新增店铺只需加一个文件夹 + 一行配置

👥 团队协作 便携版可一键分发给所有人，无需培训

🔧 维护成本 单文件架构，零数据库、零服务器

---

⚡ 从今天开始，让订单同步自动化 —— 把时间留给更有价值的事情。