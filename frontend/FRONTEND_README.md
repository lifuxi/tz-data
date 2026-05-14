# tz-data 前端项目

基于 Vue3 + Element Plus + Vite 构建的数据维护系统前端应用。

## 🚀 快速开始

### 1. 安装依赖

```bash
cd frontend
npm install
```

### 2. 启动开发服务器

```bash
npm run dev
```

访问 http://localhost:3000

### 3. 构建生产版本

```bash
npm run build
```

## 📁 项目结构

```
frontend/
├── src/
│   ├── api/              # API 客户端
│   │   └── index.js      # Axios 配置和 API 方法
│   ├── components/       # 公共组件
│   │   ├── common/       # 通用组件
│   │   └── layout/       # 布局组件
│   ├── views/            # 页面视图
│   │   ├── Dashboard.vue          # 数据维护看板
│   │   ├── CatalogList.vue        # 数据目录列表
│   │   ├── SyncTaskList.vue       # 同步任务列表
│   │   ├── HealthSnapshotList.vue # 健康快照列表
│   │   ├── AccountList.vue        # 账户管理
│   │   ├── StatementList.vue      # 账单管理
│   │   └── AlertList.vue          # 告警历史
│   ├── router/           # 路由配置
│   │   └── index.js
│   ├── stores/           # Pinia 状态管理
│   ├── App.vue           # 根组件
│   └── main.js           # 入口文件
├── index.html            # HTML 模板
├── vite.config.js        # Vite 配置
├── package.json          # 依赖配置
└── README.md             # 项目说明
```

## 🎨 UI/UX 规范

遵循 [UI_UX_DESIGN_SPEC.md](../UI_UX_DESIGN_SPEC.md) 中的设计规范：

- **主色调**: #409EFF (Element Plus Blue)
- **成功色**: #67C23A
- **警告色**: #E6A23C
- **错误色**: #F56C6C
- **字体**: Helvetica Neue, PingFang SC, Microsoft YaHei
- **间距**: 8px 基准网格系统

## 🔌 API 集成

前端通过 Axios 与后端 FastAPI 通信：

- **Base URL**: `/api/maintenance` (开发环境代理到 `http://localhost:8000`)
- **认证**: Bearer Token (存储在 localStorage)
- **错误处理**: 统一的响应拦截器，自动显示错误消息

## 📦 主要依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| vue | ^3.4.0 | 核心框架 |
| vue-router | ^4.2.5 | 路由管理 |
| pinia | ^2.1.7 | 状态管理 |
| element-plus | ^2.5.0 | UI 组件库 |
| axios | ^1.6.0 | HTTP 客户端 |
| echarts | ^5.4.3 | 图表库 |
| dayjs | ^1.11.10 | 日期处理 |

## 🛠️ 开发指南

### 添加新页面

1. 在 `src/views/` 创建 Vue 组件
2. 在 `src/router/index.js` 添加路由
3. 在 `MainLayout.vue` 的菜单中添加导航项

### 调用 API

```javascript
import { catalogAPI } from '@/api'

// 列出数据目录
const catalogs = await catalogAPI.list()

// 创建数据目录
const newCatalog = await catalogAPI.create({
  catalog_name: '中金所-IM-日线',
  exchange_code: 'CFFEX',
  product_code: 'IM',
  data_type: 'daily'
})
```

### 使用 Element Plus 组件

所有 Element Plus 组件已全局注册，可直接使用：

```vue
<template>
  <el-button type="primary">按钮</el-button>
  <el-table :data="tableData">
    <el-table-column prop="name" label="名称" />
  </el-table>
</template>
```

## 📝 待完成页面

以下页面需要实现具体业务逻辑：

- [ ] CatalogList.vue - 数据目录管理（CRUD）
- [ ] SyncTaskList.vue - 同步任务监控
- [ ] HealthSnapshotList.vue - 健康快照查看
- [ ] AccountList.vue - 账户管理
- [ ] StatementList.vue - 账单上传和解析
- [ ] AlertList.vue - 告警历史查看

可以参考 Dashboard.vue 的实现模式。

## 🔧 配置

### 环境变量

创建 `.env` 文件：

```env
VITE_API_BASE_URL=http://localhost:8000/api/maintenance
```

### Vite 代理

在 `vite.config.js` 中配置了 API 代理：

```javascript
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    },
  },
}
```

## 📊 性能优化

- **代码分割**: 路由懒加载
- **组件缓存**: KeepAlive 缓存常用组件
- **图片优化**: 使用 WebP 格式
- **Tree Shaking**: 按需导入 Element Plus 图标

## 🧪 测试

（待添加单元测试和 E2E 测试）

## 📄 License

MIT
