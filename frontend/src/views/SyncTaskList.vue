<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>同步任务监控</span>
          <el-button type="primary" @click="refreshTasks">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>
      
      <!-- 筛选器 -->
      <el-form :inline="true" class="filter-form">
        <el-form-item label="状态">
          <el-select v-model="filterStatus" placeholder="全部" clearable @change="loadTasks">
            <el-option label="全部" value="" />
            <el-option label="待执行" value="pending" />
            <el-option label="执行中" value="running" />
            <el-option label="成功" value="success" />
            <el-option label="失败" value="failed" />
          </el-select>
        </el-form-item>
        <el-form-item label="目录">
          <el-select v-model="filterCatalog" placeholder="全部" clearable @change="loadTasks">
            <el-option label="全部" value="" />
            <el-option v-for="cat in catalogs" :key="cat.id" :label="cat.catalog_name" :value="cat.id" />
          </el-select>
        </el-form-item>
      </el-form>
      
      <!-- 任务列表 -->
      <el-table :data="tasks" stripe v-loading="loading">
        <el-table-column prop="id" label="任务ID" width="100" />
        <el-table-column prop="catalog_name" label="数据目录" />
        <el-table-column prop="mode" label="同步模式" width="120">
          <template #default="{ row }">
            <el-tag :type="row.mode === 'full' ? 'warning' : 'success'">
              {{ row.mode === 'full' ? '全量' : '增量' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress_pct" label="进度" width="150">
          <template #default="{ row }">
            <el-progress :percentage="row.progress_pct || 0" :status="getProgressStatus(row)" />
          </template>
        </el-table-column>
        <el-table-column prop="records_fetched" label="获取记录" width="120" />
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="viewDetail(row)">详情</el-button>
            <el-button size="small" type="danger" v-if="row.status === 'failed'" @click="retryTask(row)">重试</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 分页 -->
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadTasks"
        @current-change="loadTasks"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>
    
    <!-- 任务详情对话框 -->
    <el-dialog v-model="detailVisible" title="任务详情" width="600px">
      <el-descriptions :column="2" border v-if="currentTask">
        <el-descriptions-item label="任务ID">{{ currentTask.id }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(currentTask.status)">
            {{ getStatusText(currentTask.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="数据目录">{{ currentTask.catalog_name }}</el-descriptions-item>
        <el-descriptions-item label="同步模式">{{ currentTask.mode }}</el-descriptions-item>
        <el-descriptions-item label="进度">{{ currentTask.progress_pct }}%</el-descriptions-item>
        <el-descriptions-item label="获取记录">{{ currentTask.records_fetched }}</el-descriptions-item>
        <el-descriptions-item label="存储记录">{{ currentTask.records_stored }}</el-descriptions-item>
        <el-descriptions-item label="开始时间">{{ formatTime(currentTask.start_time) }}</el-descriptions-item>
        <el-descriptions-item label="结束时间">{{ formatTime(currentTask.end_time) }}</el-descriptions-item>
        <el-descriptions-item label="错误信息" :span="2" v-if="currentTask.error_message">
          <el-alert :title="currentTask.error_message" type="error" :closable="false" />
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { syncAPI, catalogAPI } from '@/api'

const tasks = ref([])
const catalogs = ref([])
const loading = ref(false)
const filterStatus = ref('')
const filterCatalog = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const detailVisible = ref(false)
const currentTask = ref(null)

// Load tasks
const loadTasks = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value
    }
    if (filterStatus.value) params.status = filterStatus.value
    if (filterCatalog.value) params.catalog_id = filterCatalog.value
    
    const res = await syncAPI.list(params)
    tasks.value = res.data || []
    total.value = res.total || 0
  } catch (error) {
    ElMessage.error('加载任务列表失败')
  } finally {
    loading.value = false
  }
}

// Load catalogs for filter
const loadCatalogs = async () => {
  try {
    const res = await catalogAPI.list()
    catalogs.value = res.data || []
  } catch (error) {
    console.error('Failed to load catalogs:', error)
  }
}

// Refresh tasks
const refreshTasks = () => {
  loadTasks()
  ElMessage.success('已刷新')
}

// View task detail
const viewDetail = async (task) => {
  try {
    const res = await syncAPI.getStatus(task.id)
    currentTask.value = res.data
    detailVisible.value = true
  } catch (error) {
    ElMessage.error('获取任务详情失败')
  }
}

// Retry failed task
const retryTask = async (task) => {
  try {
    await syncAPI.trigger(task.catalog_id, task.mode)
    ElMessage.success('任务已重新触发')
    loadTasks()
  } catch (error) {
    ElMessage.error('重试失败')
  }
}

// Get status type
const getStatusType = (status) => {
  const types = {
    pending: 'info',
    running: 'warning',
    success: 'success',
    failed: 'danger'
  }
  return types[status] || 'info'
}

// Get status text
const getStatusText = (status) => {
  const texts = {
    pending: '待执行',
    running: '执行中',
    success: '成功',
    failed: '失败'
  }
  return texts[status] || status
}

// Get progress status
const getProgressStatus = (task) => {
  if (task.status === 'success') return 'success'
  if (task.status === 'failed') return 'exception'
  return undefined
}

// Format time
const formatTime = (timestamp) => {
  if (!timestamp) return '-'
  const date = new Date(timestamp)
  return date.toLocaleString('zh-CN')
}

onMounted(() => {
  loadTasks()
  loadCatalogs()
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
