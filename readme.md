# 订单同步系统使用说明

## 系统功能

- 支持多店铺订单同步，多个店铺就多个文件夹，只需要把订单导出的表格放入不同的表格，点运行就自动进入到企业微信/钉钉/飞书/erp等系统里面，需要自己拿webhook和示例修改。
- 自动读取 CSV 和 Excel 订单文件
- 清洗和处理订单数据
- 同步数据到企业微信智能表格
- 自动记录和更新订单状态

## 快速开始

1. 在企业微信-智能表格/飞书/钉钉创建智能/多维表格
2. 通过右上角三横-接收外部数据，把 webhook 地址和示例数据都提交给 Python，让 Python 匹配清洗原来的订单和需要同步到订单即可
3. 在项目文件夹下创建两个店铺文件夹：
   - **Qmaster** - 存放 Qmaster 店铺的订单文件
   - **tianyixinxuan** - 存放天颐心选店铺的订单文件

### 方法一：双击运行（推荐）

1. 找到并双击 `运行订单同步.bat` 文件
2. 系统会自动执行同步操作
3. 操作完成后会显示结果，按任意键关闭窗口

### 方法二：手动运行

1. 打开命令提示符（CMD）
2. 切换到脚本所在目录
3. 执行命令：`python main.py`

## 配置说明

### 1. 配置文件（.env）

用记事本打开 `.env` 文件，修改以下配置：

```env
# Qmaster 店铺配置
WECOM_WEBHOOK_URL_QMASTER=https://qyapi.weixin.qq.com/cgi-bin/wedoc/smartsheet/webhook?key=你的Qmaster店铺Webhook密钥
DB_FILE_QMASTER=orders_qmaster.db

# 天颐心选店铺配置
WECOM_WEBHOOK_URL_TIANYIXINXUAN=https://qyapi.weixin.qq.com/cgi-bin/wedoc/smartsheet/webhook?key=你的天颐心选店铺Webhook密钥
DB_FILE_TIANYIXINXUAN=orders_tianyixinxuan.db
```

### 2. 订单文件

- 将订单 CSV 或 Excel 文件放入对应的店铺文件夹
- Qmaster 店铺订单放入 `Qmaster` 文件夹
- 天颐心选店铺订单放入 `tianyixinxuan` 文件夹
- 系统会自动识别最新的文件
- 支持的文件格式：CSV、Excel（.xlsx、.xls）
- 支持的编码格式：utf-8-sig、gbk

## 常见问题

### 问题1：双击批处理文件没有反应

- 检查是否已安装 Python
- 检查 Python 是否添加到系统环境变量
- 检查 `.env` 文件配置是否正确

### 问题2：运行时出现错误

- 查看命令窗口中的错误信息
- 检查 CSV/Excel 文件格式是否正确
- 检查网络连接是否正常
- 确认文件列名是否符合要求

### 问题3：企业微信没有收到数据

- 检查 Webhook URL 是否正确
- 检查网络连接是否正常
- 查看命令窗口中的错误信息

## 示例数据

```json
{
  "schema": {
    "fxNwEq": "子订单编号",
    "fCNsiv": "商品ID",
    "fBK7XT": "商品名称",
    "fy3AU0": "下单数量",
    "ff2OiF": "商家收入金额",
    "fJ0NdH": "订单状态",
    "fNuVBy": "下单时间",
    "fWJEK9": "收货地址",
    "fTMuqw": "快递信息",
    "fzFeek": "出库状态"
  },
  "add_records": [
    {
      "values": {
        "fxNwEq": "测试文本",
        "fCNsiv": "测试文本",
        "fBK7XT": "测试文本",
        "fy3AU0": 1,
        "ff2OiF": 10,
        "fJ0NdH": [{"text": "待发货"}],
        "fNuVBy": "1735660800000",
        "fWJEK9": "测试文本",
        "fTMuqw": "测试文本",
        "fzFeek": [{"text": "待出库"}]
      }
    }
  ]
}
```

## 技术支持

如遇问题，请联系系统管理员 <sulcr@qq.com>。
