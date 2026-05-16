<template>
  <div class="data-dashboard">
    <!-- Summary Cards -->
    <el-row :gutter="16" class="summary-row">
      <el-col :span="4">
        <el-card shadow="hover">
          <el-statistic title="数据库表总数" :value="summary.total_tables" />
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover">
          <el-statistic title="总记录数" :value="summary.total_records" :formatter="formatBigNumber" />
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover">
          <el-statistic title="数据目录数" :value="summary.total_catalogs" />
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover">
          <el-statistic title="今日同步目录" :value="summary.catalogs_synced_today" />
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover">
          <el-statistic title="平均质量分" :value="summary.avg_quality_score" suffix="分" :precision="1" />
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover">
          <el-statistic title="今日任务执行" :value="summary.tasks_today">
            <template #suffix>
              <span v-if="summary.tasks_failed_today" class="fail-count">
                / {{ summary.tasks_failed_today }} 失败
              </span>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
    </el-row>

    <!-- Tabs -->
    <el-card style="margin-top: 16px;">
      <template #header>
        <div class="card-header">
          <span>数据大盘</span>
          <el-button type="primary" size="small" @click="loadData" :loading="loading">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <!-- Tab 1: 数据库概览 -->
        <el-tab-pane label="数据库概览" name="databases">
          <el-row :gutter="16">
            <el-col :span="24" v-for="db in databases" :key="db.name" style="margin-bottom: 16px;">
              <el-card>
                <template #header>
                  <div class="db-header">
                    <span class="db-name">{{ db.name }}</span>
                    <el-tag size="small">{{ db.size_mb }} MB</el-tag>
                    <el-tag size="small" type="info">{{ db.tables.length }} 张表</el-tag>
                    <el-tag size="small" type="success">{{ formatBigNumber(db.tables.reduce((s, t) => s + t.rows, 0)) }} 条记录</el-tag>
                  </div>
                </template>
                <el-table :data="db.tables" stripe size="small" max-height="400">
                  <el-table-column prop="name" label="表名" width="220" />
                  <el-table-column prop="description" label="说明" width="160" />
                  <el-table-column label="行数" width="120">
                    <template #default="{ row }">
                      {{ formatNumber(row.rows) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="source" label="来源" width="100">
                    <template #default="{ row }">
                      <el-tag size="small" type="info">{{ row.source }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="最早日期" width="120">
                    <template #default="{ row }">
                      {{ row.earliest_date || '-' }}
                    </template>
                  </el-table-column>
                  <el-table-column label="最新日期" width="120">
                    <template #default="{ row }">
                      {{ row.latest_date || '-' }}
                    </template>
                  </el-table-column>
                </el-table>
              </el-card>
            </el-col>
          </el-row>
        </el-tab-pane>

        <!-- Tab 2: 数据目录 -->
        <el-tab-pane label="数据目录" name="catalogs">
          <el-table :data="catalogs" stripe max-height="500">
            <el-table-column prop="name" label="目录名称" width="200" />
            <el-table-column prop="exchange" label="交易所" width="90" />
            <el-table-column prop="product" label="品种" width="80" />
            <el-table-column prop="data_type" label="数据类型" width="100" />
            <el-table-column prop="source" label="来源" width="100">
              <template #default="{ row }">
                <el-tag size="small" type="info">{{ row.source }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="最新同步" width="160">
              <template #default="{ row }">
                {{ row.last_sync_at || '-' }}
              </template>
            </el-table-column>
            <el-table-column label="同步状态" width="120">
              <template #default="{ row }">
                <el-tag :type="getSyncTagType(row.sync_status)" size="small">
                  {{ row.sync_status || '未知' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="质量评分" width="140">
              <template #default="{ row }">
                <el-progress
                  v-if="row.quality_score"
                  :percentage="Math.round(row.quality_score)"
                  :stroke-width="14"
                  :color="getQualityColor(row.quality_score)"
                />
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="完整性" width="100">
              <template #default="{ row }">
                {{ row.completeness_pct != null ? row.completeness_pct.toFixed(1) + '%' : '-' }}
              </template>
            </el-table-column>
            <el-table-column label="缺失天数" width="90">
              <template #default="{ row }">
                <el-tag v-if="row.missing_days > 0" type="danger" size="small">{{ row.missing_days }}</el-tag>
                <span v-else>0</span>
              </template>
            </el-table-column>
            <el-table-column label="数据范围" width="200">
              <template #default="{ row }">
                <span v-if="row.earliest_date && row.latest_date">
                  {{ row.earliest_date }} ~ {{ row.latest_date }}
                </span>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="记录数" width="100">
              <template #default="{ row }">
                {{ row.total_records ? formatNumber(row.total_records) : '-' }}
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- Tab 3: 定时任务 -->
        <el-tab-pane label="定时任务" name="tasks">
          <el-table :data="tasks" stripe max-height="500">
            <el-table-column prop="name" label="任务名称" width="220" />
            <el-table-column prop="schedule" label="调度时间" width="140" />
            <el-table-column label="最近执行" width="160">
              <template #default="{ row }">
                {{ row.last_run || '-' }}
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag v-if="row.last_status" :type="row.last_status === 'success' ? 'success' : 'danger'" size="small">
                  {{ row.last_status === 'success' ? '成功' : '失败' }}
                </el-tag>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="最近记录数" width="120">
              <template #default="{ row }">
                {{ row.last_records ? formatNumber(row.last_records) : '-' }}
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- Tab 4: 数据消费 -->
        <el-tab-pane label="数据消费" name="consumption">
          <el-table :data="consumption" stripe max-height="500">
            <el-table-column prop="data_type" label="数据类型" width="120" />
            <el-table-column prop="tables" label="底层表" width="200" />
            <el-table-column prop="api_endpoint" label="API 端点" width="260">
              <template #default="{ row }">
                <code class="api-code">{{ row.api_endpoint }}</code>
              </template>
            </el-table-column>
            <el-table-column prop="consumers" label="消费者" />
          </el-table>
        </el-tab-pane>

        <!-- Tab 5: 数据质量 -->
        <el-tab-pane label="数据质量" name="quality">
          <!-- Quality Summary Cards -->
          <el-row :gutter="16" style="margin-bottom: 16px;">
            <el-col :span="6">
              <el-card shadow="hover">
                <el-statistic title="数据目录总数" :value="qualitySummary.total_catalogs" />
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="hover">
                <el-statistic title="存在缺失数据" :value="qualitySummary.catalogs_missing">
                  <template #suffix>
                    <span class="stat-suffix">个目录</span>
                  </template>
                </el-statistic>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="hover">
                <el-statistic title="记录漂移" :value="qualitySummary.catalogs_with_drift">
                  <template #suffix>
                    <span class="stat-suffix">个目录</span>
                  </template>
                </el-statistic>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="hover">
                <el-statistic title="平均完整性" :value="qualitySummary.avg_completeness" suffix="%" :precision="1" />
              </el-card>
            </el-col>
          </el-row>

          <!-- Quality Table -->
          <el-table :data="qualityData" stripe max-height="500">
            <el-table-column prop="name" label="目录名称" width="200" />
            <el-table-column prop="exchange" label="交易所" width="90" />
            <el-table-column prop="product" label="品种" width="80" />
            <el-table-column prop="data_type" label="数据类型" width="100" />
            <el-table-column label="记录总数" width="140">
              <template #default="{ row }">
                <div class="record-cell">
                  <span class="record-actual">{{ formatNumber(row.actual_total || 0) }}</span>
                  <span v-if="row.drift > 0" class="record-drift">
                    / {{ formatNumber(row.recorded_total || 0) }}
                    <el-tag :type="row.drift_status === 'error' ? 'danger' : 'warning'" size="small">
                      漂移 {{ formatNumber(row.drift) }}
                    </el-tag>
                  </span>
                  <span v-else class="record-ok">
                    <el-tag type="success" size="small">一致</el-tag>
                  </span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="交易日历" width="120">
              <template #default="{ row }">
                <span v-if="row.expected_days > 0">
                  {{ row.actual_days }}/{{ row.expected_days }}天
                </span>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="缺失天数" width="90">
              <template #default="{ row }">
                <el-tag v-if="row.missing_days > 0" type="danger" size="small">{{ row.missing_days }}</el-tag>
                <span v-else>0</span>
              </template>
            </el-table-column>
            <el-table-column label="缺失日期" width="200">
              <template #default="{ row }">
                <span v-if="row.missing_dates && row.missing_dates.length" class="missing-dates">
                  <el-tag v-for="d in row.missing_dates" :key="d" type="info" size="small" style="margin-right: 4px;">{{ d }}</el-tag>
                  <span v-if="row.missing_days > 5" class="missing-more">+{{ row.missing_days - 5 }}...</span>
                </span>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="完整性" width="100">
              <template #default="{ row }">
                <el-progress
                  :percentage="Math.round(row.completeness_pct || 0)"
                  :stroke-width="14"
                  :color="getCompletenessColor(row.completeness_pct)"
                />
              </template>
            </el-table-column>
            <el-table-column label="质量评分" width="140">
              <template #default="{ row }">
                <el-progress
                  v-if="row.quality_score"
                  :percentage="Math.round(row.quality_score)"
                  :stroke-width="14"
                  :color="getQualityColor(row.quality_score)"
                />
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="一致性" width="90">
              <template #default="{ row }">
                <el-tag :type="getConsistencyType(row.consistency_status)" size="small">
                  {{ row.consistency_status || '-' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="数据范围" width="200">
              <template #default="{ row }">
                <span v-if="row.earliest_date && row.earliest_date !== '-'">
                  {{ row.earliest_date }} ~ {{ row.latest_date }}
                </span>
                <span v-else>-</span>
              </template>
            </el-table-column>
          </el-table>

          <!-- Sync Failure Alerts -->
          <el-divider content-position="left">同步失败告警</el-divider>

          <el-row :gutter="16" style="margin-bottom: 16px;">
            <el-col :span="8">
              <el-card shadow="hover">
                <el-statistic title="今日失败次数" :value="failureStats.total" />
              </el-card>
            </el-col>
            <el-col :span="8">
              <el-card shadow="hover">
                <el-statistic title="最近失败任务" :value="failureStats.topTask || '-'" />
              </el-card>
            </el-col>
            <el-col :span="8">
              <el-card shadow="hover">
                <el-statistic title="最近失败时间" :value="failureStats.lastTime || '-'" />
              </el-card>
            </el-col>
          </el-row>

          <el-table :data="syncFailures" stripe max-height="400">
            <el-table-column prop="task_name" label="任务名称" width="280" />
            <el-table-column prop="error_type" label="错误类型" width="150" />
            <el-table-column prop="error_message" label="错误信息" />
            <el-table-column label="失败时间" width="180">
              <template #default="{ row }">
                {{ row.failed_at || '-' }}
              </template>
            </el-table-column>
            <el-table-column label="已通知" width="80">
              <template #default="{ row }">
                <el-tag v-if="row.notified" type="success" size="small">是</el-tag>
                <el-tag v-else type="info" size="small">否</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { formatNumber } from '../utils/format'

const loading = ref(false)
const activeTab = ref('databases')
const rawData = ref(null)

const summary = ref({
  total_tables: 0,
  total_records: 0,
  total_catalogs: 0,
  catalogs_synced_today: 0,
  avg_quality_score: 0,
  tasks_today: 0,
  tasks_failed_today: 0,
})

const databases = ref([])
const catalogs = ref([])
const tasks = ref([])
const consumption = ref([])
const qualityData = ref([])
const qualitySummary = ref({
  total_catalogs: 0,
  catalogs_missing: 0,
  catalogs_with_drift: 0,
  avg_completeness: 0,
})
const syncFailures = ref([])
const failureStats = ref({
  total: 0,
  topTask: '-',
  lastTime: '-',
})

const loadData = async () => {
  loading.value = true
  try {
    const res = await fetch('/api/maintenance/dashboard')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    rawData.value = await res.json()

    const d = rawData.value
    summary.value = d.summary || summary.value
    databases.value = d.databases || []
    catalogs.value = d.catalogs || []
    tasks.value = d.tasks || []
    consumption.value = d.consumption || []

    // Load quality data
    await loadQualityData()
  } catch (error) {
    ElMessage.error('加载数据大盘失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

const loadQualityData = async () => {
  try {
    const res = await fetch('/api/maintenance/quality/overview')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    if (data.success) {
      qualityData.value = data.data || []
      qualitySummary.value = data.summary || qualitySummary.value
    }

    // Load sync failures
    await loadSyncFailures()
  } catch (error) {
    // Quality endpoint may not be available yet, silently ignore
    console.warn('Failed to load quality data:', error.message)
  }
}

const loadSyncFailures = async () => {
  try {
    const res = await fetch('/api/maintenance/sync-failures?hours=24&limit=50')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    if (data.success) {
      syncFailures.value = data.data || []
      failureStats.value.total = data.summary.total_failures || 0

      // Load stats for top task
      const statsRes = await fetch('/api/maintenance/sync-failures/stats?hours=24')
      if (statsRes.ok) {
        const statsData = await statsRes.json()
        if (statsData.success && statsData.data.by_task.length > 0) {
          const top = statsData.data.by_task[0]
          failureStats.value.topTask = top.task_name.split('.').pop() || top.task_name
          failureStats.value.lastTime = top.last_failure || '-'
        }
      }
    }
  } catch (error) {
    console.warn('Failed to load sync failures:', error.message)
  }
}

const formatBigNumber = (value) => {
  if (value == null) return '0'
  if (value >= 100000000) return (value / 100000000).toFixed(2) + ' 亿'
  if (value >= 10000) return (value / 10000).toFixed(1) + ' 万'
  return value.toLocaleString()
}

const getSyncTagType = (status) => {
  const map = { completed: 'success', success: 'success', failed: 'danger', running: 'warning', never_synced: 'info', unknown: 'info' }
  return map[status] || 'info'
}

const getQualityColor = (score) => {
  if (score >= 90) return '#67C23A'
  if (score >= 70) return '#E6A23C'
  if (score >= 50) return '#F56C6C'
  return '#909399'
}

const getCompletenessColor = (pct) => {
  if (pct >= 95) return '#67C23A'
  if (pct >= 80) return '#E6A23C'
  return '#F56C6C'
}

const getConsistencyType = (status) => {
  const map = { ok: 'success', warning: 'warning', error: 'danger', unknown: 'info' }
  return map[status] || 'info'
}

onMounted(() => {
  loadData()
})
</script>

<style scoped lang="scss">
.data-dashboard {
  .summary-row {
    .el-card {
      text-align: center;
    }
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .db-header {
    display: flex;
    align-items: center;
    gap: 10px;

    .db-name {
      font-weight: 600;
      font-size: 15px;
    }
  }

  .fail-count {
    color: #F56C6C;
    font-size: 12px;
  }

  .api-code {
    font-size: 12px;
    color: #409EFF;
    background: #ecf5ff;
    padding: 2px 6px;
    border-radius: 3px;
  }

  .stat-suffix {
    font-size: 12px;
    color: #909399;
  }

  .record-cell {
    display: flex;
    align-items: center;
    gap: 6px;

    .record-actual {
      font-weight: 500;
    }

    .record-drift {
      display: flex;
      align-items: center;
      gap: 4px;
      color: #909399;
      font-size: 12px;
    }

    .record-ok {
      font-size: 12px;
    }
  }

  .missing-dates {
    display: flex;
    flex-wrap: wrap;
    gap: 2px;

    .missing-more {
      font-size: 12px;
      color: #909399;
    }
  }
}
</style>
