# ECAgent - 微信小店智能电商管理系统

基于 AI 的微信小店运营管理系统，支持商品管理、数据分析、竞品监控和智能决策。

## 功能模块

### 🛒 商品管理
- 微信小店商品同步与管理
- 批量上传商品（图片 + 信息）
- Excel 批量导入
- 商品上架/下架

### 📊 数据分析
- 店铺经营数据概览
- 价格区间分析
- 销量排行榜
- 运营建议智能生成

### 🔍 竞品监控
- 京东商品数据爬取
- 竞品价格对比
- 市场缺口分析
- 决策分析报告

### 💡 智能决策助手
- AI 驱动的电商运营顾问
- 店铺问题诊断
- 提升销量方案
- 工作规划建议

## 技术栈

- **后端**: Flask + SQLAlchemy
- **前端**: Bootstrap 5 + Jinja2
- **数据**: SQLite
- **AI**: 支持对接大模型 API

## 快速开始

### 1. 安装依赖

```bash
cd ecommerce_agent
pip install -r requirements.txt
```

### 2. 配置

编辑 `config.yaml`：
```yaml
wechat:
  appid: "你的AppID"
  secret: "你的AppSecret"
```

### 3. 启动

```bash
python app.py
```

访问 http://127.0.0.1:5000

### 4. 登录

默认账号：`admin`
默认密码：`admin123`

## 项目结构

```
ecommerce_agent/
├── app.py                 # Flask 主应用
├── models.py              # 数据库模型
├── config.yaml            # 配置文件
├── requirements.txt       # Python 依赖
│
├── wechat_shop_api.py     # 微信小店 API 封装
├── wechat_uploader.py     # 商品上传核心逻辑
├── routes_shop.py        # 商品管理路由
├── routes_uploader.py     # 上架相关路由
├── routes_strategy.py     # 决策助手路由
│
├── templates/             # 前端模板
│   ├── base.html          # 基础模板
│   ├── dashboard.html     # 仪表盘
│   ├── analysis.html      # 数据分析
│   ├── strategy.html      # 决策助手
│   └── ...
│
├── competitor_analysis/    # 竞品分析数据
└── venv/                  # Python 虚拟环境
```

## 主要功能

### 微信小店 API

```python
from wechat_shop_api import WechatShopAPI

api = WechatShopAPI()

# 获取商品列表
products = api.get_product_list(limit=10)

# 获取商品详情
detail = api.get_product_detail(product_id)

# 上架商品
api.list_product(product_id)

# 下架商品
api.delist_product(product_id)
```

### 批量上传

```bash
# 从文件夹上传
python upload_from_folder.py /path/to/images

# 从 Excel 导入
python upload_from_excel.py products.xlsx
```

### AI 决策助手

访问 `/strategy` 页面，与 AI 助手对话获取运营建议。

## API 接口

| 接口 | 说明 |
|------|------|
| `/api/shop/products` | 获取商品列表 |
| `/api/shop/product/<id>` | 获取商品详情 |
| `/api/shop/upload` | 上传商品 |
| `/api/strategy/chat` | AI 对话 |

## 注意事项

1. 首次使用需要在微信公众平台添加服务器 IP 到白名单
2. access_token 有效期 2 小时，程序自动刷新
3. 图片建议不超过 2MB

## License

MIT