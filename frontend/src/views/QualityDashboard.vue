<template>
  <div class="page-container">
    <!-- Summary Cards -->
    <el-row :gutter="16" class="summary-row">
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="今日推送总量" :value="stats.total_pushes">
            <template #suffix>条</template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="缺失次数" :value="stats.gap_count">
            <template #suffix>
              <el-tag size="small" :type="stats.gap_count > 0 ? 'danger' : 'success'">
                {{ stats.gap_count > 0 ? '异常' : '正常' }}
              </el-tag>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="回补次数" :value="stats.backfill_count" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="平均延迟" :value="stats.avg_latency">
            <template #suffix>ms</template>
          </el-statistic>
        </el-card>
      </el-col>
    </el-row>

    <!-- Latency Chart -->
    <el-card class="chart-card">
      <template #header>
        <div class="card-header">
          <span>延迟趋势（最近 24 小时）</span>
          <el-radio-group v-model="latencyRange" size="small" @change="loadLatencyData">
            <el-radio-button label="1h">1小时</el-radio-button>
            <el-radio-button label="6h">6小时</el-radio-button>
            <el-radio-button label="24h">24小时</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      <div ref="latencyChartRef" class="chart-container" />
    </el-card>

    <!-- Symbol Health Heatmap Placeholder -->
    <el-card class="chart-card">
      <template #header><span>Symbol 健康热力图</span></template>
      <el-empty description="热力图数据待后端接入" :image-size="80" />
    </el-card>

    <!-- Per-Source Quality Table -->
    <el-card>
      <template #header><span>各数据源质量详情</span></template>
      <el-table :data="qualityTable" stripe v-loading="loading">
        <el-table-column prop="source_name" label="数据源" width="120" />
        <el-table-column prop="symbol_count" label="活跃 Symbol" width="110" />
        <el-table-column prop="avg_delay" label="平均延迟(ms)" width="130" />
        <el-table-column prop="p99_delay" label="P99 延迟(ms)" width="130" />
        <el-table-column prop="gap_count" label="缺口次数" width="100" />
        <el-table-column prop="missing_bars" label="缺失 Bar 数" width="120" />
        <el-table-column prop="suspect_count" label="异常标记" width="100" />
        <el-table-column prop="quality_score" label="质量得分" width="100">
          <template #default="{ row }">
            <el-tag :type="scoreType(row.quality_score)">{{ row.quality_score }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import * as echarts from 'echarts'

const stats = ref({ total_pushes: 0, gap_count: 0, backfill_count: 0, avg_latency: 0 })
const latencyRange = ref('24h')
const latencyChartRef = ref(null)
const loading = ref(false)
const qualityTable = ref([])
let latencyChart = null

function loadLatencyData() {
  // TODO: Replace with real API call
  // Generate placeholder data for visualization
  const points = latencyRange.value === '1h' ? 60 : latencyRange.value === '6h' ? 72 : 96
  const times = []
  const p50 = []
  const p99 = []
  const now = new Date()
  for (let i = points; i >= 0; i--) {
    const t = new Date(now - i * (latencyRange.value === '1h' ? 60000 : latencyRange.value === '6h' ? 300000 : 900000))
    times.push(t.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }))
    p50.push(Math.floor(50 + Math.random() * 200))
    p99.push(Math.floor(200 + Math.random() * 1500))
  }

  if (!latencyChart) {
    latencyChart = echarts.init(latencyChartRef.value)
  }
  latencyChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['P50', 'P99'], bottom: 0 },
    grid: { top: 10, right: 30, bottom: 40, left: 50 },
    xAxis: { type: 'category', data: times, axisLabel: { rotate: 45, interval: Math.floor(points / 10) } },
    yAxis: { type: 'value', name: 'ms', splitLine: { lineStyle: { type: 'dashed' } } },
    series: [
      { name: 'P50', type: 'line', data: p50, smooth: true, lineStyle: { width: 2 }, itemStyle: { color: '#409eff' } },
      { name: 'P99', type: 'line', data: p99, smooth: true, lineStyle: { width: 2 }, itemStyle: { color: '#e6a23c' }, areaStyle: { opacity: 0.1 } },
    ],
  })
}

function scoreType(score) {
  if (score >= 90) return 'success'
  if (score >= 70) return 'warning'
  return 'danger'
}

onMounted(() => {
  loading.value = true
  // Placeholder stats
  stats.value = { total_pushes: 45230, gap_count: 3, backfill_count: 2, avg_latency: 185 }
  qualityTable.value = [
    { source_name: 'tushare', symbol_count: 15, avg_delay: 850, p99_delay: 2100, gap_count: 1, missing_bars: 5, suspect_count: 0, quality_score: 96 },
    { source_name: 'akshare', symbol_count: 10, avg_delay: 1200, p99_delay: 3500, gap_count: 2, missing_bars: 12, suspect_count: 1, quality_score: 88 },
    { source_name: 'qq_finance', symbol_count: 0, avg_delay: 0, p99_delay: 0, gap_count: 0, missing_bars: 0, suspect_count: 0, quality_score: 0 },
  ]
  loading.value = false
  loadLatencyData()

  window.addEventListener('resize', () => latencyChart?.resize())
})
</script>

<style scoped>
.page-container { padding: 16px; }
.summary-row { margin-bottom: 16px; }
.chart-card { margin-bottom: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.chart-container { height: 300px; }
</style>
