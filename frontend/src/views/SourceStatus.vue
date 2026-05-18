<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>数据源状态</span>
          <el-button @click="loadData">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <el-row :gutter="16" v-loading="loading">
        <el-col :xs="24" :sm="12" :md="8" v-for="source in sources" :key="source.source_name">
          <el-card shadow="hover" class="source-card">
            <template #header>
              <div class="source-header">
                <span class="source-name">{{ source.source_name }}</span>
                <el-tag :type="statusType(source.status)" size="small">
                  {{ statusLabel(source.status) }}
                </el-tag>
              </div>
            </template>

            <div class="source-type">
              <el-tag size="small" effect="plain">{{ typeLabel(source.source_type) }}</el-tag>
            </div>

            <el-descriptions :column="1" size="small" border class="source-info">
              <el-descriptions-item label="P50 延迟">
                <span :class="{ 'text-danger': source.latency_ms > 3000 }">
                  {{ source.latency_ms }} ms
                </span>
              </el-descriptions-item>
              <el-descriptions-item label="P99 延迟">
                <span :class="{ 'text-danger': source.latency_p99_ms > 10000 }">
                  {{ source.latency_p99_ms }} ms
                </span>
              </el-descriptions-item>
              <el-descriptions-item label="错误数">
                <span :class="{ 'text-danger': source.error_count > 0 }">
                  {{ source.error_count }}
                </span>
              </el-descriptions-item>
              <el-descriptions-item label="订阅 Symbol 数">
                {{ source.symbols_subscribed }}
              </el-descriptions-item>
              <el-descriptions-item label="最后心跳">
                {{ formatTime(source.last_heartbeat) }}
              </el-descriptions-item>
              <el-descriptions-item label="最后错误" v-if="source.last_error">
                <el-tooltip :content="source.last_error" placement="top">
                  <span class="text-ellipsis">{{ source.last_error }}</span>
                </el-tooltip>
              </el-descriptions-item>
            </el-descriptions>

            <div class="source-actions">
              <el-button
                v-if="source.status !== 'connected'"
                size="small"
                type="primary"
                @click="connectSource(source)"
              >
                连接
              </el-button>
              <el-button
                v-if="source.status === 'connected'"
                size="small"
                type="danger"
                @click="disconnectSource(source)"
              >
                断开
              </el-button>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-empty v-if="!loading && sources.length === 0" description="暂无数据源（待后端接入）" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const sources = ref([])
const loading = ref(false)

async function loadData() {
  loading.value = true
  try {
    // TODO: Replace with real API call when backend implements source status API
    // const res = await api.get('/api/v1/market/sources')
    // sources.value = res.items
    // Placeholder data
    sources.value = [
      { source_name: 'tushare', source_type: 'historical', status: 'connected', latency_ms: 850, latency_p99_ms: 2100, error_count: 0, symbols_subscribed: 15, last_heartbeat: new Date().toISOString(), last_error: null },
      { source_name: 'akshare', source_type: 'historical', status: 'connected', latency_ms: 1200, latency_p99_ms: 3500, error_count: 2, symbols_subscribed: 10, last_heartbeat: new Date().toISOString(), last_error: null },
      { source_name: 'qq_finance', source_type: 'transition', status: 'disconnected', latency_ms: 0, latency_p99_ms: 0, error_count: 0, symbols_subscribed: 0, last_heartbeat: null, last_error: null },
      { source_name: 'ctp', source_type: 'realtime', status: 'disconnected', latency_ms: 0, latency_p99_ms: 0, error_count: 0, symbols_subscribed: 0, last_heartbeat: null, last_error: null },
      { source_name: 'itick', source_type: 'realtime', status: 'disconnected', latency_ms: 0, latency_p99_ms: 0, error_count: 0, symbols_subscribed: 0, last_heartbeat: null, last_error: null },
    ]
  } catch (e) {
    ElMessage.error('加载失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

async function connectSource(source) {
  try {
    await ElMessageBox.confirm(`确认连接 ${source.source_name}？`, '确认')
    // TODO: POST /api/v1/market/sources/{name}/connect
    ElMessage.success('连接请求已发送（功能待后端实现）')
  } catch { /* cancelled */ }
}

async function disconnectSource(source) {
  try {
    await ElMessageBox.confirm(`确认断开 ${source.source_name}？`, '确认')
    // TODO: POST /api/v1/market/sources/{name}/disconnect
    ElMessage.success('断开请求已发送（功能待后端实现）')
  } catch { /* cancelled */ }
}

function statusType(status) {
  return { connected: 'success', disconnected: 'info', degraded: 'warning', error: 'danger' }[status] || 'info'
}
function statusLabel(status) {
  return { connected: '已连接', disconnected: '未连接', degraded: '降级中', error: '错误' }[status] || status
}
function typeLabel(type) {
  return { realtime: '实时', historical: '历史', transition: '过渡' }[type] || type
}
function formatTime(t) {
  if (!t) return '-'
  const d = new Date(t)
  return d.toLocaleTimeString('zh-CN')
}

onMounted(loadData)
</script>

<style scoped>
.page-container { padding: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.source-card { margin-bottom: 16px; }
.source-header { display: flex; justify-content: space-between; align-items: center; }
.source-name { font-weight: 600; font-size: 16px; }
.source-type { margin-bottom: 12px; }
.source-info { margin-bottom: 12px; }
.source-actions { display: flex; gap: 8px; justify-content: flex-end; }
.text-danger { color: #f56c6c; font-weight: 600; }
.text-ellipsis { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: block; }
</style>
