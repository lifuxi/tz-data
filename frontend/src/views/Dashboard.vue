<template>
  <div class="dashboard">
    <el-row :gutter="20">
      <!-- Summary Cards -->
      <el-col :span="6">
        <el-card class="summary-card">
          <div class="card-content">
            <div class="icon" style="background-color: #409EFF;">
              <el-icon size="30"><List /></el-icon>
            </div>
            <div class="info">
              <div class="label">数据目录</div>
              <div class="value">{{ summary.totalCatalogs }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="summary-card">
          <div class="card-content">
            <div class="icon" style="background-color: #67C23A;">
              <el-icon size="30"><Refresh /></el-icon>
            </div>
            <div class="info">
              <div class="label">今日同步</div>
              <div class="value">{{ summary.syncedToday }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="summary-card">
          <div class="card-content">
            <div class="icon" style="background-color: #E6A23C;">
              <el-icon size="30"><TrendCharts /></el-icon>
            </div>
            <div class="info">
              <div class="label">平均质量分</div>
              <div class="value">{{ summary.avgQualityScore }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="summary-card">
          <div class="card-content">
            <div class="icon" style="background-color: #F56C6C;">
              <el-icon size="30"><Bell /></el-icon>
            </div>
            <div class="info">
              <div class="label">活跃告警</div>
              <div class="value">{{ summary.activeAlerts }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Charts and Tables -->
    <el-row :gutter="20" style="margin-top: 20px;">
      <el-col :span="16">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>数据同步趋势</span>
            </div>
          </template>
          <div ref="syncChartRef" style="height: 300px;"></div>
        </el-card>
      </el-col>
      
      <el-col :span="8">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>最近告警</span>
            </div>
          </template>
          <el-timeline>
            <el-timeline-item
              v-for="alert in recentAlerts"
              :key="alert.timestamp"
              :type="getAlertType(alert.level)"
            >
              <div class="alert-item">
                <div class="alert-title">{{ alert.title }}</div>
                <div class="alert-time">{{ formatTime(alert.timestamp) }}</div>
              </div>
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px;">
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>数据目录状态</span>
              <el-button type="primary" size="small" @click="refreshData">
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
            </div>
          </template>
          
          <el-table :data="catalogs" stripe>
            <el-table-column prop="catalog_name" label="目录名称" />
            <el-table-column prop="exchange_code" label="交易所" width="100" />
            <el-table-column prop="product_code" label="品种" width="100" />
            <el-table-column prop="data_type" label="数据类型" width="120" />
            <el-table-column label="最后同步" width="180">
              <template #default="{ row }">
                {{ formatTime(row.last_sync_at) }}
              </template>
            </el-table-column>
            <el-table-column label="质量评分" width="120">
              <template #default="{ row }">
                <el-tag :type="getQualityType(row.quality_score)">
                  {{ row.quality_score }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button size="small" type="primary" @click="triggerSync(row.id)">
                  同步
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { List, Refresh, TrendCharts, Bell } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { catalogAPI, syncAPI, alertAPI } from '@/api'

// Summary data
const summary = ref({
  totalCatalogs: 0,
  syncedToday: 0,
  avgQualityScore: 0,
  activeAlerts: 0
})

// Catalogs
const catalogs = ref([])

// Recent alerts
const recentAlerts = ref([])

// Chart ref
const syncChartRef = ref(null)
let syncChart = null

// Load data
const loadData = async () => {
  try {
    // Load catalogs
    const catalogRes = await catalogAPI.list()
    catalogs.value = catalogRes.data || []
    summary.value.totalCatalogs = catalogs.value.length
    
    // Calculate average quality score
    if (catalogs.value.length > 0) {
      const avgScore = catalogs.value.reduce((sum, cat) => sum + (cat.quality_score || 0), 0) / catalogs.value.length
      summary.value.avgQualityScore = avgScore.toFixed(1)
    }
    
    // Load recent alerts
    const alertRes = await alertAPI.getRecent(5)
    recentAlerts.value = alertRes.data || []
    summary.value.activeAlerts = recentAlerts.value.filter(a => a.level === 'error' || a.level === 'critical').length
    
    // Initialize chart
    initChart()
  } catch (error) {
    console.error('Failed to load data:', error)
  }
}

// Initialize sync trend chart
const initChart = () => {
  if (!syncChartRef.value) return
  
  syncChart = echarts.init(syncChartRef.value)
  
  const option = {
    title: {
      text: '近7天同步记录数',
      left: 'center'
    },
    tooltip: {
      trigger: 'axis'
    },
    xAxis: {
      type: 'category',
      data: ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        data: [120, 200, 150, 80, 70, 110, 130],
        type: 'line',
        smooth: true,
        areaStyle: {}
      }
    ]
  }
  
  syncChart.setOption(option)
}

// Trigger sync
const triggerSync = async (catalogId) => {
  try {
    await syncAPI.trigger(catalogId, 'incremental')
    ElMessage.success('同步任务已触发')
    loadData() // Refresh data
  } catch (error) {
    ElMessage.error('触发同步失败')
  }
}

// Refresh data
const refreshData = () => {
  loadData()
  ElMessage.success('数据已刷新')
}

// Format time
const formatTime = (timestamp) => {
  if (!timestamp) return '-'
  const date = new Date(timestamp)
  return date.toLocaleString('zh-CN')
}

// Get alert type
const getAlertType = (level) => {
  const types = {
    info: 'info',
    warning: 'warning',
    error: 'danger',
    critical: 'danger'
  }
  return types[level] || 'info'
}

// Get quality tag type
const getQualityType = (score) => {
  if (score >= 90) return 'success'
  if (score >= 70) return ''
  if (score >= 50) return 'warning'
  return 'danger'
}

// Lifecycle
onMounted(() => {
  loadData()
  
  // Resize chart on window resize
  window.addEventListener('resize', () => {
    syncChart?.resize()
  })
})
</script>

<style scoped lang="scss">
.dashboard {
  .summary-card {
    margin-bottom: 0;
    
    .card-content {
      display: flex;
      align-items: center;
      gap: 15px;
      
      .icon {
        width: 60px;
        height: 60px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
      }
      
      .info {
        flex: 1;
        
        .label {
          font-size: 14px;
          color: #909399;
          margin-bottom: 5px;
        }
        
        .value {
          font-size: 24px;
          font-weight: bold;
          color: #303133;
        }
      }
    }
  }
  
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .alert-item {
    .alert-title {
      font-size: 14px;
      margin-bottom: 5px;
    }
    
    .alert-time {
      font-size: 12px;
      color: #909399;
    }
  }
}
</style>
