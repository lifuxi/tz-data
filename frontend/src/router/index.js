import { createRouter, createWebHistory } from 'vue-router'
import Layout from '@/components/layout/MainLayout.vue'

const routes = [
  {
    path: '/',
    component: Layout,
    redirect: '/dashboard',
    children: [
      // ===== 数据维护 =====
      {
        path: '/dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '数据维护看板', icon: 'DataLine', group: '数据维护', order: 10 }
      },
      {
        path: '/catalogs',
        name: 'Catalogs',
        component: () => import('@/views/CatalogList.vue'),
        meta: { title: '数据目录', icon: 'List', group: '数据维护', order: 20 }
      },
      {
        path: '/health-snapshots',
        name: 'HealthSnapshots',
        component: () => import('@/views/HealthSnapshotList.vue'),
        meta: { title: '健康快照', icon: 'Monitor', group: '数据维护', order: 40 }
      },
      // ===== 基础数据 =====
      {
        path: '/exchanges',
        name: 'Exchanges',
        component: () => import('@/views/ExchangeList.vue'),
        meta: { title: '交易所管理', icon: 'OfficeBuilding', group: '基础数据', order: 50 }
      },
      {
        path: '/products',
        name: 'Products',
        component: () => import('@/views/ProductList.vue'),
        meta: { title: '品种管理', icon: 'Box', group: '基础数据', order: 60 }
      },
      // ===== 交易日历 =====
      {
        path: '/trade-calendar',
        name: 'TradeCalendar',
        component: () => import('@/views/TradeCalendarList.vue'),
        meta: { title: '交易日历', icon: 'Calendar', group: '交易日历', order: 80 }
      },
      {
        path: '/product-calendar',
        name: 'ProductCalendar',
        component: () => import('@/views/TradeCalendarList.vue'),
        meta: { title: '商品日历', icon: 'Box', group: '交易日历', order: 85 }
      },
      {
        path: '/contracts',
        name: 'Contracts',
        component: () => import('@/views/ContractList.vue'),
        meta: { title: '合约管理', icon: 'Files', group: '交易日历', order: 90 }
      },
      {
        path: '/main-contracts',
        name: 'MainContracts',
        component: () => import('@/views/MainContractList.vue'),
        meta: { title: '主力合约', icon: 'TrendCharts', group: '交易日历', order: 91 }
      },
      {
        path: '/special-dates',
        name: 'SpecialDates',
        component: () => import('@/views/SpecialDateList.vue'),
        meta: { title: '特殊日期', icon: 'Calendar', group: '交易日历', order: 92 }
      },
      {
        path: '/trading-hours',
        name: 'TradingHours',
        component: () => import('@/views/TradingHoursList.vue'),
        meta: { title: '交易时间', icon: 'Clock', group: '交易日历', order: 93 }
      },
      // ===== 账单与账户 =====
      {
        path: '/accounts',
        name: 'Accounts',
        component: () => import('@/views/AccountList.vue'),
        meta: { title: '账户管理', icon: 'User', group: '账单与账户', order: 90 }
      },
      {
        path: '/statements',
        name: 'Statements',
        component: () => import('@/views/StatementList.vue'),
        meta: { title: '账单管理', icon: 'Document', group: '账单与账户', order: 100 }
      },
      // ===== 系统 =====
      {
        path: '/docs',
        name: 'Docs',
        component: () => import('@/views/DocsViewer.vue'),
        meta: { title: '在线文档', icon: 'Reading', group: '系统', order: 5 }
      },
      {
        path: '/data-dashboard',
        name: 'DataDashboard',
        component: () => import('@/views/DataDashboard.vue'),
        meta: { title: '数据大盘', icon: 'DataAnalysis', group: '系统', order: 6 }
      },
      {
        path: '/data-sources',
        name: 'DataSources',
        component: () => import('@/views/DataSourceConfig.vue'),
        meta: { title: '数据源配置', icon: 'Connection', group: '系统', order: 110 }
      },
      {
        path: '/alerts',
        name: 'Alerts',
        component: () => import('@/views/AlertList.vue'),
        meta: { title: '告警历史', icon: 'Bell', group: '系统', order: 120 }
      },
      {
        path: '/notification-config',
        name: 'NotificationConfig',
        component: () => import('@/views/NotificationConfig.vue'),
        meta: { title: '通知配置', icon: 'ChatDotRound', group: '系统', order: 125 }
      },
      // ===== 实时行情采集 =====
      {
        path: '/market-catalog',
        name: 'MarketCatalog',
        component: () => import('@/views/MarketCatalogList.vue'),
        meta: { title: '数据目录', icon: 'List', group: '实时行情采集', order: 200 }
      },
      {
        path: '/source-status',
        name: 'SourceStatus',
        component: () => import('@/views/SourceStatus.vue'),
        meta: { title: '数据源状态', icon: 'Connection', group: '实时行情采集', order: 210 }
      },
      {
        path: '/quality-dashboard',
        name: 'QualityDashboard',
        component: () => import('@/views/QualityDashboard.vue'),
        meta: { title: '质量看板', icon: 'DataAnalysis', group: '实时行情采集', order: 220 }
      },
      {
        path: '/event-log',
        name: 'MarketEventLog',
        component: () => import('@/views/MarketEventLog.vue'),
        meta: { title: '采集日志', icon: 'Document', group: '实时行情采集', order: 230 }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
