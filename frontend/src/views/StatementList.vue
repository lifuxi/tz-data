<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>账单管理</span>
          <el-upload
            action="/api/maintenance/statements/upload"
            :on-success="handleUploadSuccess"
            :on-error="handleUploadError"
            :before-upload="beforeUpload"
            accept=".csv,.txt"
          >
            <el-button type="primary">
              <el-icon><Upload /></el-icon>
              上传账单
            </el-button>
          </el-upload>
        </div>
      </template>
      
      <!-- 筛选器 -->
      <el-form :inline="true" class="filter-form">
        <el-form-item label="账户">
          <el-select v-model="filterAccount" placeholder="全部" clearable @change="loadStatements">
            <el-option label="全部" value="" />
            <el-option v-for="acc in accounts" :key="acc.id" :label="acc.account_name" :value="acc.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filterStatus" placeholder="全部" clearable @change="loadStatements">
            <el-option label="全部" value="" />
            <el-option label="待解析" value="pending" />
            <el-option label="已解析" value="parsed" />
            <el-option label="解析失败" value="failed" />
          </el-select>
        </el-form-item>
      </el-form>
      
      <!-- 账单列表 -->
      <el-table :data="statements" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="account_name" label="账户" />
        <el-table-column prop="file_name" label="文件名" />
        <el-table-column prop="statement_date" label="账单日期" width="120">
          <template #default="{ row }">
            {{ formatDate(row.statement_date) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="parsed_at" label="解析时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.parsed_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="parseStatement(row)" v-if="row.status === 'pending'">解析</el-button>
            <el-button size="small" type="success" @click="viewResult(row)" v-if="row.status === 'parsed'">查看结果</el-button>
            <el-button size="small" type="danger" @click="deleteStatement(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 分页 -->
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadStatements"
        @current-change="loadStatements"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>
    
    <!-- 解析结果对话框 -->
    <el-dialog v-model="resultVisible" title="解析结果" width="800px">
      <el-tabs v-if="currentStatement">
        <el-tab-pane label="摘要">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="账户">{{ currentStatement.account_name }}</el-descriptions-item>
            <el-descriptions-item label="账单日期">{{ formatDate(currentStatement.statement_date) }}</el-descriptions-item>
            <el-descriptions-item label="期初权益">{{ currentStatement.summary?.opening_balance }}</el-descriptions-item>
            <el-descriptions-item label="期末权益">{{ currentStatement.summary?.closing_balance }}</el-descriptions-item>
            <el-descriptions-item label="入金">{{ currentStatement.summary?.deposit }}</el-descriptions-item>
            <el-descriptions-item label="出金">{{ currentStatement.summary?.withdrawal }}</el-descriptions-item>
            <el-descriptions-item label="盈亏">{{ currentStatement.summary?.pnl }}</el-descriptions-item>
            <el-descriptions-item label="手续费">{{ currentStatement.summary?.commission }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>
        <el-tab-pane label="交易记录">
          <el-table :data="currentStatement.trades || []" stripe max-height="400">
            <el-table-column prop="trade_date" label="日期" width="120" />
            <el-table-column prop="contract" label="合约" />
            <el-table-column prop="direction" label="方向" width="80" />
            <el-table-column prop="volume" label="手数" width="80" />
            <el-table-column prop="price" label="价格" width="100" />
            <el-table-column prop="pnl" label="盈亏" width="100" />
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import { statementAPI, accountAPI } from '@/api'

const statements = ref([])
const accounts = ref([])
const loading = ref(false)
const filterAccount = ref('')
const filterStatus = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const resultVisible = ref(false)
const currentStatement = ref(null)

// Load statements
const loadStatements = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value
    }
    if (filterAccount.value) params.account_id = filterAccount.value
    if (filterStatus.value) params.status = filterStatus.value
    
    const res = await statementAPI.list(params)
    statements.value = res.data || []
    total.value = res.total || 0
  } catch (error) {
    ElMessage.error('加载账单列表失败')
  } finally {
    loading.value = false
  }
}

// Load accounts
const loadAccounts = async () => {
  try {
    const res = await accountAPI.list()
    accounts.value = res.data || []
  } catch (error) {
    console.error('Failed to load accounts:', error)
  }
}

// Before upload
const beforeUpload = (file) => {
  const isValid = file.type === 'text/csv' || file.name.endsWith('.csv') || file.name.endsWith('.txt')
  if (!isValid) {
    ElMessage.error('只支持 CSV 或 TXT 文件')
  }
  return isValid
}

// Handle upload success
const handleUploadSuccess = (response) => {
  ElMessage.success('上传成功')
  loadStatements()
}

// Handle upload error
const handleUploadError = () => {
  ElMessage.error('上传失败')
}

// Parse statement
const parseStatement = async (statement) => {
  try {
    await statementAPI.parse(statement.id)
    ElMessage.success('解析成功')
    loadStatements()
  } catch (error) {
    ElMessage.error('解析失败')
  }
}

// View parse result
const viewResult = (statement) => {
  currentStatement.value = statement
  resultVisible.value = true
}

// Delete statement
const deleteStatement = async (id) => {
  try {
    await ElMessageBox.confirm('确定要删除该账单吗？', '警告', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    // Note: API method needs to be added
    ElMessage.info('删除功能待实现')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// Get status type
const getStatusType = (status) => {
  const types = {
    pending: 'warning',
    parsed: 'success',
    failed: 'danger'
  }
  return types[status] || 'info'
}

// Get status text
const getStatusText = (status) => {
  const texts = {
    pending: '待解析',
    parsed: '已解析',
    failed: '解析失败'
  }
  return texts[status] || status
}

// Format date
const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

// Format time
const formatTime = (timestamp) => {
  if (!timestamp) return '-'
  return new Date(timestamp).toLocaleString('zh-CN')
}

onMounted(() => {
  loadStatements()
  loadAccounts()
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
