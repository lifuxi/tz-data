# 数据维护系统前端项目

基于 Vue3 + Element Plus + Vite 构建的现代化前端应用。

## 📁 项目结构

```
frontend/
├── src/
│   ├── assets/              # 静态资源
│   │   ├── styles/          # 全局样式
│   │   │   ├── variables.css    # CSS 变量
│   │   │   ├── base.css         # 基础样式
│   │   │   └── main.css         # 主样式文件
│   │   └── images/          # 图片资源
│   ├── components/          # 公共组件
│   │   ├── common/          # 通用组件
│   │   │   ├── DataCard.vue     # 数据卡片
│   │   │   ├── StatusTag.vue    # 状态标签
│   │   │   ├── LoadingMask.vue  # 加载遮罩
│   │   │   └── EmptyState.vue   # 空状态
│   │   ├── layout/          # 布局组件
│   │   │   ├── AppHeader.vue    # 顶部导航
│   │   │   ├── AppSidebar.vue   # 侧边栏
│   │   │   └── AppMain.vue      # 主内容区
│   │   └── business/        # 业务组件
│   │       ├── CatalogTree.vue       # 目录树
│   │       ├── SyncProgress.vue      # 同步进度
│   │       ├── QualityMeter.vue      # 质量仪表
│   │       └── HealthDashboard.vue   # 健康看板
│   ├── views/               # 页面视图
│   │   ├── Dashboard.vue        # 综合看板
│   │   ├── DataSync.vue         # 数据同步
│   │   ├── Statements.vue       # 账单管理
│   │   ├── Holdings.vue         # 机构持仓
│   │   └── Settings.vue         # 系统设置
│   ├── router/              # 路由配置
│   │   └── index.js
│   ├── stores/              # Pinia 状态管理
│   │   ├── catalog.js           # 目录状态
│   │   ├── sync.js              # 同步状态
│   │   └── user.js              # 用户状态
│   ├── api/                 # API 接口
│   │   ├── request.js           # Axios 封装
│   │   ├── maintenance.js       # 维护 API
│   │   └── statements.js        # 账单 API
│   ├── utils/               # 工具函数
│   │   ├── format.js            # 格式化工具
│   │   ├── validate.js          # 验证工具
│   │   └── constants.js         # 常量定义
│   ├── App.vue              # 根组件
│   └── main.js              # 入口文件
├── public/                  # 公共资源
├── index.html               # HTML 模板
├── package.json             # 依赖配置
├── vite.config.js           # Vite 配置
└── README.md                # 项目说明
```

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

访问 http://localhost:5173

### 3. 构建生产版本

```bash
npm run build
```

## 📦 技术栈

- **框架**: Vue 3.3+ (Composition API)
- **UI 库**: Element Plus 2.4+
- **构建工具**: Vite 5.0+
- **状态管理**: Pinia 2.1+
- **路由**: Vue Router 4.2+
- **HTTP 客户端**: Axios 1.6+
- **图表**: ECharts 5.4+
- **CSS 预处理**: SCSS

## 🎨 设计规范

详见 [UI_UX_DESIGN_SPEC.md](./UI_UX_DESIGN_SPEC.md)

## 🔗 API 配置

在 `vite.config.js` 中配置代理：

```javascript
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
```

## 📝 开发规范

### 组件命名
- 使用 PascalCase: `DataCard.vue`
- 文件名与组件名一致

### 代码风格
- 使用 Composition API
- `<script setup>` 语法
- 遵循 ESLint + Prettier 规范

### 样式规范
- 使用 scoped CSS
- 遵循 BEM 命名法
- 使用 CSS 变量

## 🧪 测试

```bash
# 单元测试
npm run test:unit

# 端到端测试
npm run test:e2e
```

## 📄 License

MIT
