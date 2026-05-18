<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>账单管理</span>
          <el-button type="primary" @click="openUploadDialog">
            <el-icon><Upload /></el-icon>
            上传账单
          </el-button>
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

    <!-- 3步上传向导对话框 -->
    <el-dialog v-model="uploadDialogVisible" title="上传账单" width="900px" :close-on-click-modal="false" @close="resetUpload">
      <el-steps :active="currentStep" finish-status="success" style="margin-bottom: 24px;">
        <el-step title="上传文件" description="选择账单文件" />
        <el-step title="解析预览" description="核对解析结果" />
        <el-step title="确认提交" description="写入数据库" />
      </el-steps>

      <!-- Step 1: 上传文件 -->
      <div v-show="currentStep === 0">
        <el-upload
          ref="uploadRef"
          drag
          action=""
          :auto-upload="false"
          :on-change="handleFileSelect"
          :limit="1"
          accept=".csv,.txt"
          style="text-align: center;"
        >
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">
            拖拽文件到此处，或 <em>点击上传</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">仅支持 CSV / TXT 格式的账单文件</div>
          </template>
        </el-upload>
        <div v-if="selectedFile" class="file-info">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="文件名">{{ selectedFile.name }}</el-descriptions-item>
            <el-descriptions-item label="大小">{{ formatFileSize(selectedFile.size) }}</el-descriptions-item>
          </el-descriptions>
        </div>
        <div style="text-align: right; margin-top: 16px;">
          <el-button type="primary" :disabled="!selectedFile" @click="goToPreview">
            下一步：解析预览
          </el-button>
        </div>
      </div>

      <!-- Step 2: 解析预览 -->
      <div v-show="currentStep === 1" v-loading="previewLoading">
        <el-alert v-if="previewData" title="解析成功" type="success" :closable="false" style="margin-bottom: 16px;">
          <template #default>
            共解析 <strong>{{ previewData.trade_count }}</strong> 条成交记录，
            <strong>{{ previewData.position_count }}</strong> 条持仓记录
          </template>
        </el-alert>
        <el-alert v-if="!previewData && !previewLoading" title="解析失败或文件为空" type="error" :closable="false" style="margin-bottom: 16px;" />

        <el-tabs v-if="previewData">
          <el-tab-pane label="成交记录 ({{ previewData.trades.length }})">
            <el-table :data="previewData.trades" stripe max-height="350" size="small">
              <el-table-column prop="trade_date" label="日期" width="100" />
              <el-table-column prop="contract" label="合约" width="100" />
              <el-table-column prop="direction" label="方向" width="70" />
              <el-table-column prop="volume" label="手数" width="60" />
              <el-table-column prop="price" label="价格" width="90" />
              <el-table-column prop="turnover" label="成交额" width="100" />
              <el-table-column prop="commission" label="手续费" width="90" />
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="持仓记录 ({{ previewData.positions.length }})">
            <el-table :data="previewData.positions" stripe max-height="350" size="small">
              <el-table-column prop="contract" label="合约" />
              <el-table-column prop="direction" label="方向" width="70" />
              <el-table-column prop="volume" label="手数" width="60" />
              <el-table-column prop="avg_price" label="均价" width="90" />
              <el-table-column prop="market_value" label="市值" width="100" />
              <el-table-column prop="float_pnl" label="浮动盈亏" width="100" />
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="资金流水 ({{ previewData.funds.length }})">
            <el-table :data="previewData.funds" stripe max-height="350" size="small">
              <el-table-column prop="date" label="日期" width="100" />
              <el-table-column prop="type" label="类型" width="100" />
              <el-table-column prop="amount" label="金额" width="120" />
              <el-table-column prop="balance" label="余额" width="120" />
              <el-table-column prop="note" label="备注" />
            </el-table>
          </el-tab-pane>
        </el-tabs>

        <div style="text-align: right; margin-top: 16px;">
          <el-button @click="currentStep = 0">上一步</el-button>
          <el-button type="primary" :disabled="!previewData" @click="goToConfirm">
            下一步：确认提交
          </el-button>
        </div>
      </div>

      <!-- Step 3: 确认提交 -->
      <div v-show="currentStep === 2" v-loading="submitLoading">
        <el-alert title="确认提交" type="info" :closable="false" style="margin-bottom: 16px;">
          <template #default>
            即将将 <strong>{{ selectedFile?.name }}</strong> 的解析结果写入数据库。
            <br />成交记录: <strong>{{ previewData?.trade_count || 0 }}</strong> 条
            &nbsp;|&nbsp; 持仓记录: <strong>{{ previewData?.position_count || 0 }}</strong> 条
          </template>
        </el-alert>

        <el-form label-width="100px" size="small">
          <el-form-item label="关联账户">
            <el-select v-model="confirmAccountId" placeholder="请选择账户（可选）" clearable style="width: 240px;">
              <el-option v-for="acc in accounts" :key="acc.id" :label="acc.account_name" :value="acc.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="confirmNotes" type="textarea" :rows="2" placeholder="可选备注信息" style="width: 400px;" />
          </el-form-item>
        </el-form>

        <div style="text-align: right; margin-top: 16px;">
          <el-button @click="currentStep = 1">上一步</el-button>
          <el-button type="success" :loading="submitLoading" @click="confirmSubmit">
            确认提交
          </el-button>
        </div>
      </div>
    </el-dialog>

    <!-- 解析结果对话框 -->
    <el-dialog v-model="resultVisible" title="账单详情" width="800px">
      <el-tabs v-if="currentStatement">
        <el-tab-pane label="摘要">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="账户">{{ currentStatement.account_name }}</el-descriptions-item>
            <el-descriptions-item label="账单日期">{{ formatDate(currentStatement.statement_date) }}</el-descriptions-item>
            <el-descriptions-item label="期初权益">{{ currentStatement.balance_bf ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="期末权益">{{ currentStatement.balance_cf ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="客户权益">{{ currentStatement.client_equity ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="币种">{{ currentStatement.currency }}</el-descriptions-item>
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
import { Upload, UploadFilled } from '@element-plus/icons-vue'
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

// Upload dialog state
const uploadDialogVisible = ref(false)
const currentStep = ref(0)
const selectedFile = ref(null)
const previewData = ref(null)
const previewLoading = ref(false)
const submitLoading = ref(false)
const confirmAccountId = ref('')
const confirmNotes = ref('')
const uploadedFilePath = ref('')

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

// Open upload dialog
const openUploadDialog = () => {
  uploadDialogVisible.value = true
  currentStep.value = 0
}

// Reset upload state
const resetUpload = () => {
  selectedFile.value = null
  previewData.value = null
  previewLoading.value = false
  submitLoading.value = false
  confirmAccountId.value = ''
  confirmNotes.value = ''
  uploadedFilePath.value = ''
}

// Handle file selection
const handleFileSelect = (file) => {
  selectedFile.value = file.raw
}

// Step 1 -> Step 2: Upload and preview
const goToPreview = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }

  previewLoading.value = true
  currentStep.value = 1

  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)

    const res = await statementAPI.preview(formData)
    if (res.success) {
      previewData.value = res.preview
      uploadedFilePath.value = res.file_path
    } else {
      ElMessage.error('解析失败')
    }
  } catch (error) {
    ElMessage.error('解析失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    previewLoading.value = false
  }
}

// Step 2 -> Step 3: Go to confirm
const goToConfirm = () => {
  currentStep.value = 2
}

// Step 3: Confirm and submit
const confirmSubmit = async () => {
  if (!uploadedFilePath.value) {
    ElMessage.error('文件路径不存在')
    return
  }

  submitLoading.value = true
  try {
    const res = await statementAPI.confirm({
      file_path: uploadedFilePath.value,
      file_name: selectedFile.value?.name || '',
      account_id: confirmAccountId.value || null,
      notes: confirmNotes.value || null,
    })

    if (res.success) {
      ElMessage.success(`提交成功！账单已写入数据库 (ID: ${res.bill_id})`)
      uploadDialogVisible.value = false
      loadStatements()
    } else {
      ElMessage.error('提交失败')
    }
  } catch (error) {
    ElMessage.error('提交失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    submitLoading.value = false
  }
}

// Parse statement (legacy)
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

// Format file size
const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let size = bytes
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024
    i++
  }
  return `${size.toFixed(1)} ${units[i]}`
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

.file-info {
  margin-top: 16px;
}

.el-icon--upload {
  font-size: 64px;
  color: #409eff;
}
</style>
