<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>行情数据目录</span>
          <el-button type="primary" @click="showCreateDialog">
            <el-icon><Plus /></el-icon>
            添加 Symbol
          </el-button>
        </div>
      </template>

      <!-- Filters -->
      <el-form :inline="true" class="filter-bar">
        <el-form-item label="资产类型">
          <el-select v-model="filterAsset" placeholder="全部" clearable @change="loadData">
            <el-option label="期货" value="FUTURE" />
            <el-option label="期权" value="OPTION" />
            <el-option label="指数" value="INDEX" />
          </el-select>
        </el-form-item>
        <el-form-item label="交易所">
          <el-select v-model="filterExchange" placeholder="全部" clearable @change="loadData">
            <el-option label="CFFEX" value="CFFEX" />
            <el-option label="SHFE" value="SHFE" />
            <el-option label="DCE" value="DCE" />
            <el-option label="CZCE" value="CZCE" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filterActive" placeholder="全部" clearable @change="loadData">
            <el-option label="启用" :value="1" />
            <el-option label="停用" :value="0" />
          </el-select>
        </el-form-item>
      </el-form>

      <el-table :data="catalogs" stripe v-loading="loading">
        <el-table-column prop="symbol" label="Symbol" min-width="140" />
        <el-table-column prop="product_id" label="品种" width="100" />
        <el-table-column prop="exchange" label="交易所" width="80" />
        <el-table-column prop="asset_type" label="类型" width="80">
          <template #default="{ row }">
            <el-tag size="small" :type="assetTypeTag(row.asset_type)">
              {{ assetTypeLabel(row.asset_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="real_time_source" label="实时源" width="90" />
        <el-table-column prop="backup_source" label="备源" width="90">
          <template #default="{ row }">
            {{ row.backup_source || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="启用" width="70">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="subscribe_until" label="订阅至" width="110" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="toggleActive(row)">
              {{ row.is_active ? '停用' : '启用' }}
            </el-button>
            <el-button size="small" type="primary" @click="editCatalog(row)">编辑</el-button>
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

    <!-- Create/Edit Dialog -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="550px" @closed="resetForm">
      <el-form ref="formRef" :model="form" label-width="120px">
        <el-form-item label="Symbol" required>
          <el-input v-model="form.symbol" :disabled="!!editingId" placeholder="如 IM2506" />
        </el-form-item>
        <el-form-item label="品种" required>
          <el-input v-model="form.product_id" placeholder="如 IM_FUT" />
        </el-form-item>
        <el-form-item label="交易所" required>
          <el-select v-model="form.exchange">
            <el-option label="CFFEX" value="CFFEX" />
            <el-option label="SHFE" value="SHFE" />
            <el-option label="DCE" value="DCE" />
            <el-option label="CZCE" value="CZCE" />
          </el-select>
        </el-form-item>
        <el-form-item label="资产类型" required>
          <el-select v-model="form.asset_type">
            <el-option label="期货" value="FUTURE" />
            <el-option label="期权" value="OPTION" />
            <el-option label="指数" value="INDEX" />
          </el-select>
        </el-form-item>
        <el-form-item label="实时数据源">
          <el-select v-model="form.real_time_source" clearable>
            <el-option label="CTP" value="ctp" />
            <el-option label="iTick" value="itick" />
          </el-select>
        </el-form-item>
        <el-form-item label="备用数据源">
          <el-select v-model="form.backup_source" clearable>
            <el-option label="腾讯财经" value="qq_finance" />
            <el-option label="iTick" value="itick" />
          </el-select>
        </el-form-item>
        <el-form-item label="历史数据源">
          <el-select v-model="form.historical_source">
            <el-option label="Tushare" value="tushare" />
            <el-option label="AKShare" value="akshare" />
          </el-select>
        </el-form-item>
        <el-form-item label="订阅开始">
          <el-date-picker v-model="form.subscribe_from" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="订阅结束">
          <el-date-picker v-model="form.subscribe_until" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const catalogs = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const filterAsset = ref('')
const filterExchange = ref('')
const filterActive = ref('')

const dialogVisible = ref(false)
const editingId = ref(null)
const dialogTitle = ref('添加 Symbol')
const formRef = ref(null)

const form = ref({
  symbol: '',
  product_id: '',
  exchange: '',
  asset_type: '',
  real_time_source: '',
  backup_source: '',
  historical_source: 'tushare',
  subscribe_from: '',
  subscribe_until: '',
})

async function loadData() {
  loading.value = true
  try {
    // TODO: Replace with real API call when tz-data backend implements market catalog API
    // const res = await api.get('/api/v1/market/catalog', {
    //   params: { is_active: filterActive.value, exchange: filterExchange.value, asset_type: filterAsset.value }
    // })
    // catalogs.value = res.items
    // total.value = res.total
    catalogs.value = []
    total.value = 0
  } catch (e) {
    ElMessage.error('加载数据失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

function showCreateDialog() {
  editingId.value = null
  dialogTitle.value = '添加 Symbol'
  dialogVisible.value = true
}

function editCatalog(row) {
  editingId.value = row.id
  dialogTitle.value = '编辑 Symbol'
  form.value = { ...row }
  dialogVisible.value = true
}

async function toggleActive(row) {
  try {
    await ElMessageBox.confirm(`确认${row.is_active ? '停用' : '启用'} ${row.symbol}？`, '确认')
    // TODO: API call to PUT /api/v1/market/catalog/{symbol}
    ElMessage.success('操作成功（功能待后端实现）')
  } catch { /* cancelled */ }
}

async function submitForm() {
  if (!form.value.symbol || !form.value.product_id) {
    ElMessage.warning('Symbol 和品种为必填项')
    return
  }
  // TODO: API call POST/PUT /api/v1/market/catalog
  ElMessage.success('保存成功（功能待后端实现）')
  dialogVisible.value = false
  loadData()
}

function resetForm() {
  form.value = {
    symbol: '', product_id: '', exchange: '', asset_type: '',
    real_time_source: '', backup_source: '', historical_source: 'tushare',
    subscribe_from: '', subscribe_until: '',
  }
  editingId.value = null
}

function assetTypeLabel(type) {
  return { FUTURE: '期货', OPTION: '期权', INDEX: '指数' }[type] || type
}
function assetTypeTag(type) {
  return { FUTURE: '', OPTION: 'warning', INDEX: 'info' }[type] || 'info'
}

onMounted(loadData)
</script>

<style scoped>
.page-container { padding: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.filter-bar { margin-bottom: 16px; }
.pagination-bar { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
