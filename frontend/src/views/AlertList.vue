<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>告警历史</span>
          <el-button type="primary" @click="loadAlerts">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>
      
      <!-- 筛选器 -->
      <el-form :inline="true" class="filter-form">
        <el-form-item label="级别">
          <el-select v-model="filterLevel" placeholder="全部" clearable @change="loadAlerts">
            <el-option label="全部" value="" />
            <el-option label="信息" value="info" />
            <el-option label="警告" value="warning" />
            <el-option label="错误" value="error" />
            <el-option label="严重" value="critical" />
          </el-select>
        </el-form-item>
        <el-form-item label="类别">
          <el-select v-model="filterCategory" placeholder="全部" clearable @change="loadAlerts">
            <el-option label="全部" value="" />
            <el-option label="系统" value="system" />
            <el-option label="同步" value="sync" />
            <el-option label="规则触发" value="rule_trigger" />
            <el-option label="异常" value="exception" />
          </el-select>
        </el-form-item>
      </el-form>
      
      <!-- 告警列表 -->
      <el-table :data="alerts" stripe v-loading="loading">
        <el-table-column prop="timestamp" label="时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.timestamp) }}
          </template>
        </el-table-column>
        <el-table-column prop="level" label="级别" width="100">
          <template #default="{ row }">
            <el-tag :type="getLevelType(row.level)">
              {{ getLevelText(row.level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="类别" width="120" />
        <el-table-column prop="title" label="标题" />
        <el-table-column prop="message" label="消息" show-overflow-tooltip />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="viewDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 分页 -->
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadAlerts"
        @current-change="loadAlerts"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>
    
    <!-- 告警详情对话框 -->
    <el-dialog v-model="detailVisible" title="告警详情" width="600px">
      <el-descriptions :column="1" border v-if="currentAlert">
        <el-descriptions-item label="时间">{{ formatTime(currentAlert.timestamp) }}</el-descriptions-item>
        <el-descriptions-item label="级别">
          <el-tag :type="getLevelType(currentAlert.level)">
            {{ getLevelText(currentAlert.level) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="类别">{{ currentAlert.category }}</el-descriptions-item>
        <el-descriptions-item label="标题">{{ currentAlert.title }}</el-descriptions-item>
        <el-descriptions-item label="消息">
          <div style="white-space: pre-wrap;">{{ currentAlert.message }}</div>
        </el-descriptions-item>
        <el-descriptions-item label="额外数据" v-if="currentAlert.extra_data">
          <pre>{{ JSON.stringify(currentAlert.extra_data, null, 2) }}</pre>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { alertAPI } from '@/api'

const alerts = ref([])
const loading = ref(false)
const filterLevel = ref('')
const filterCategory = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const detailVisible = ref(false)
const currentAlert = ref(null)

// Load alerts
const loadAlerts = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value
    }
    if (filterLevel.value) params.level = filterLevel.value
    if (filterCategory.value) params.category = filterCategory.value
    
    const res = await alertAPI.list(params)
    alerts.value = res.data || []
    total.value = res.total || 0
  } catch (error) {
    ElMessage.error('加载告警列表失败')
  } finally {
    loading.value = false
  }
}

// View alert detail
const viewDetail = (alert) => {
  currentAlert.value = alert
  detailVisible.value = true
}

// Get level type
const getLevelType = (level) => {
  const types = {
    info: 'info',
    warning: 'warning',
    error: 'danger',
    critical: 'danger'
  }
  return types[level] || 'info'
}

// Get level text
const getLevelText = (level) => {
  const texts = {
    info: '信息',
    warning: '警告',
    error: '错误',
    critical: '严重'
  }
  return texts[level] || level
}

// Format time
const formatTime = (timestamp) => {
  if (!timestamp) return '-'
  return new Date(timestamp).toLocaleString('zh-CN')
}

onMounted(() => {
  loadAlerts()
})
</script>

<style scoped lang="scss">
.page-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.filter-form {
  margin-bottom: 20px;
}
</style>
