<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>采集事件日志</span>
          <div>
            <el-button @click="loadData">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </div>
      </template>

      <!-- Filters -->
      <el-form :inline="true" class="filter-bar">
        <el-form-item label="严重程度">
          <el-select v-model="filterSeverity" placeholder="全部" clearable @change="loadData">
            <el-option label="Info" value="info" />
            <el-option label="Warning" value="warning" />
            <el-option label="Error" value="error" />
            <el-option label="Critical" value="critical" />
          </el-select>
        </el-form-item>
        <el-form-item label="数据源">
          <el-input v-model="filterSource" placeholder="数据源名称" clearable @change="loadData" />
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="filterDate"
            type="date"
            placeholder="选择日期"
            value-format="YYYY-MM-DD"
            @change="loadData"
          />
        </el-form-item>
      </el-form>

      <el-table :data="events" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="event_type" label="事件类型" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="eventTypeTag(row.event_type)">
              {{ eventTypeLabel(row.event_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source_name" label="数据源" width="100" />
        <el-table-column prop="symbol" label="Symbol" width="130">
          <template #default="{ row }">
            {{ row.symbol || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="severity" label="级别" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="severityTagType(row.severity)">
              {{ severityLabel(row.severity) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="消息" min-width="250" show-overflow-tooltip />
        <el-table-column prop="created_at" label="时间" width="170">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button size="small" @click="showDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-bar">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @current-change="loadData"
          @size-change="loadData"
        />
      </div>
    </el-card>

    <!-- Detail Dialog -->
    <el-dialog v-model="detailVisible" title="事件详情" width="600px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="事件类型">{{ selectedEvent.event_type }}</el-descriptions-item>
        <el-descriptions-item label="数据源">{{ selectedEvent.source_name }}</el-descriptions-item>
        <el-descriptions-item label="Symbol">{{ selectedEvent.symbol || '-' }}</el-descriptions-item>
        <el-descriptions-item label="级别">{{ selectedEvent.severity }}</el-descriptions-item>
        <el-descriptions-item label="消息">{{ selectedEvent.message }}</el-descriptions-item>
        <el-descriptions-item label="详细信息">
          <pre class="json-block">{{ formatJson(selectedEvent.details) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="时间">{{ selectedEvent.created_at }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const events = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(50)
const total = ref(0)

const filterSeverity = ref('')
const filterSource = ref('')
const filterDate = ref('')

const detailVisible = ref(false)
const selectedEvent = ref({})

async function loadData() {
  loading.value = true
  try {
    // TODO: Replace with real API call
    // const res = await api.get('/api/v1/market/events', {
    //   params: { severity: filterSeverity.value, source: filterSource.value, date: filterDate.value, page: page.value, page_size: pageSize.value }
    // })
    // events.value = res.items
    // total.value = res.total
    events.value = [
      { id: 1, event_type: 'connect', source_name: 'tushare', symbol: null, severity: 'info', message: 'Tushare 数据源连接成功', details: '{"latency_ms": 850}', created_at: new Date().toISOString() },
      { id: 2, event_type: 'subscribe', source_name: 'tushare', symbol: 'IM2506', severity: 'info', message: '订阅 IM2506 行情', details: '{}', created_at: new Date().toISOString() },
      { id: 3, event_type: 'gap', source_name: 'akshare', symbol: 'MO2506C3900', severity: 'warning', message: '检测到 30 秒数据缺口', details: '{"start": "14:30:00", "end": "14:30:30", "missing_bars": 6}', created_at: new Date().toISOString() },
      { id: 4, event_type: 'backfill', source_name: 'akshare', symbol: 'MO2506C3900', severity: 'info', message: '回补 6 根缺失 K 线', details: '{"bars_backfilled": 6}', created_at: new Date().toISOString() },
      { id: 5, event_type: 'switch', source_name: 'ctp', symbol: 'IM2506', severity: 'error', message: 'CTP 主源断开，切换至备用源', details: '{"primary": "ctp", "backup": "qq_finance", "reason": "timeout"}', created_at: new Date().toISOString() },
    ]
    total.value = events.value.length
  } catch (e) {
    ElMessage.error('加载失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

function showDetail(row) {
  selectedEvent.value = row
  detailVisible.value = true
}

function formatTime(t) {
  if (!t) return '-'
  return new Date(t).toLocaleString('zh-CN')
}

function formatJson(s) {
  if (!s) return '-'
  try { return JSON.stringify(JSON.parse(s), null, 2) } catch { return s }
}

function eventTypeLabel(type) {
  return { connect: '连接', disconnect: '断开', reconnect: '重连', switch: '切换', backfill: '回补', gap: '缺口', snapshot: '快照', subscribe: '订阅' }[type] || type
}
function eventTypeTag(type) {
  return { connect: 'success', disconnect: 'info', reconnect: 'warning', switch: 'danger', backfill: '', gap: 'warning', snapshot: 'info', subscribe: '' }[type] || 'info'
}
function severityTagType(sev) {
  return { info: 'info', warning: 'warning', error: 'danger', critical: 'danger' }[sev] || 'info'
}
function severityLabel(sev) {
  return { info: 'Info', warning: 'Warning', error: 'Error', critical: 'Critical' }[sev] || sev
}

onMounted(loadData)
</script>

<style scoped>
.page-container { padding: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.filter-bar { margin-bottom: 16px; }
.pagination-bar { margin-top: 16px; display: flex; justify-content: flex-end; }
.json-block { background: #f5f7fa; padding: 8px; border-radius: 4px; font-size: 12px; max-height: 300px; overflow: auto; white-space: pre-wrap; }
</style>
