# 前端页面指南

> 版本：v0.7.0 | 最后更新：2026-05-15

## 启动方式

```bash
cd C:\myspace\tz-data\frontend

# 首次安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端运行在 `http://localhost:3000`，自动代理 API 请求到后端 `http://localhost:8000`。

## 技术栈

| 组件 | 版本 | 用途 |
|------|------|------|
| Vue | 3.4 | 前端框架 |
| Vite | 5 | 构建工具 |
| Element Plus | 2.5 | UI 组件库 |
| Vue Router | 4 | 路由 |
| Pinia | 2 | 状态管理 |
| ECharts | 5 | 图表 |
| Axios | 1.6 | HTTP 客户端 |
| dayjs | 1.11 | 日期处理 |

## 菜单结构

前端侧边栏菜单按功能分为 4 组：

### 数据维护

| 页面 | 路径 | 说明 |
|------|------|------|
| 数据维护看板 | `/dashboard` | 总览同步状态、质量评分 |
| 数据目录 | `/catalogs` | 管理跟踪的数据项 |
| 健康快照 | `/health-snapshots` | 历史健康数据 |

### 基础数据

| 页面 | 路径 | 说明 |
|------|------|------|
| 交易所管理 | `/exchanges` | 交易所配置 |
| 品种管理 | `/products` | 品种配置（乘数/最小变动/保证金率/期权类型） |
| 合约管理 | `/contracts` | 合约信息维护 |
| 交易日历 | `/trade-calendar` | 节假日管理、特殊日期 |
| 主力合约 | `/main-contracts` | 主力合约序列查看与设置 |
| 交易时间模板 | `/trading-hours` | 日盘/夜盘/集合竞价时段配置 |
| 特殊日期 | `/special-dates` | 补市/休市覆盖 |

### 账单与账户

| 页面 | 路径 | 说明 |
|------|------|------|
| 账户管理 | `/accounts` | 期货账户 + CFMMC 凭证 |
| 账单管理 | `/statements` | 账单上传/解析/导入 |

### 系统

| 页面 | 路径 | 说明 |
|------|------|------|
| 数据源配置 | `/data-source-config` | 数据源 + 日历 + 凭证统一管理 |
| 告警历史 | `/alerts` | 系统告警记录 |

## 各页面功能

### 数据维护看板

- 显示所有数据目录的同步状态
- 平均质量评分、有问题目录数量
- 一键生成健康快照

### 数据目录

- 创建目录：选择交易所 × 品种 × 数据类型 × 数据源
- 同步模式：incremental（增量）或 full（全量）
- 按交易所、产品筛选
- 启用/禁用目录

### 交易所/品种/合约管理

- CRUD 操作（创建/查询/更新/删除）
- 品种配置包含：合约乘数、最小变动价位、保证金率、期权类型
- 合约支持从 Tushare 批量导入

### 交易日历

- 按交易所查看交易日/非交易日统计
- 添加节假日和非交易日
- 系统初始化（覆盖 1990-2026 年）
- 特殊日期覆盖（补市/休市）

### 主力合约

- 选择品种 + 日期范围 → 展示主力合约序列
- 支持自动填充（持仓量驱动）和手动设置
- 展示换月日期

### 交易时间模板

- 模板列表，按交易所筛选
- 创建/编辑模板（日盘/夜盘/集合竞价时段）
- 时段定义支持多个时间区间

### 账户与账单

- 添加期货账户，配置 CFMMC 登录凭证（AES-256 加密存储）
- 上传账单文件（`.txt` 格式）
- 查看解析状态：uploaded / parsing / parsed / error
- 余额平衡校验（复式记账方程）
- 滑点对账（账单价格 vs 市场价格）

### 数据源配置

统一管理入口，包含 3 个 Tab：
- **数据源管理**：查看 tushare/cffex/shfe/wind 状态，测试连接
- **交易日历**：初始化日历、添加节假日、查看日历统计
- **账户凭证**：管理各账户的 CFMMC 凭据

### 告警历史

- 查看所有系统告警
- 按级别（info/warning/error/critical）筛选
- 按类别（sync/quality/other）筛选

## 金额格式化规范

**所有前端页面显示金额类型数据，必须使用千分位格式（`1,234,567.89`），禁止直接使用 `.toFixed()` 显示金额。**

### 实现方式

- 统一使用 `frontend/src/utils/format.js` 中的工具函数
- `formatMoney(value)` — 千分位 + 万/亿缩写（`123.45 万`）
- `formatMoneyFull(value)` — 千分位不缩写（`1,234,567.89`）
- `formatNumber(value, decimals)` — 通用千分位格式化
- `formatPnl(value)` — 带正负号的千分位金额

### 不需要格式化的场景

- 百分比数据（`.toFixed(1) + '%'`）
- 交易笔数/手数等整数计数
- 比率值（如盈亏比、夏普比率等）

## 前端文件结构

```
frontend/src/
├── main.js                 # 应用入口
├── App.vue                 # 根组件
├── api/index.js            # API 封装（Axios）
├── router/index.js         # 路由配置
├── utils/format.js         # 金额格式化工具
├── components/layout/
│   └── MainLayout.vue      # 主布局（侧边栏 + 内容区）
└── views/                  # 页面组件
    ├── Dashboard.vue
    ├── AccountList.vue
    ├── AlertList.vue
    ├── CatalogList.vue
    ├── ContractList.vue
    ├── DataSourceConfig.vue
    ├── ExchangeList.vue
    ├── HealthSnapshotList.vue
    ├── MainContractList.vue
    ├── ProductList.vue
    ├── SpecialDateList.vue
    ├── StatementList.vue
    ├── TradeCalendarList.vue
    └── TradingHoursList.vue
```

## 下一页

- [数据库表结构](12-database-schema.md) — 表结构和字段
- [部署与运维](13-deployment.md) — 启动脚本和 FAQ
