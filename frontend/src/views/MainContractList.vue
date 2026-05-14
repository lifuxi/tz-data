<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>主力合约管理</span>
        </div>
      </template>

      <!-- 查询区域 -->
      <el-form :inline="true" :model="queryForm" class="query-form">
        <el-form-item label="品种">
          <el-select v-model="queryForm.productCode" placeholder="选择品种" style="width:140px">
            <el-option v-for="p in products" :key="p.product_code" :label="`${p.product_code} - ${p.product_name}`" :value="p.product_code" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始日期">
          <el-date-picker v-model="queryForm.startDate" value-format="YYYY-MM-DD" style="width:160px" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker v-model="queryForm.endDate" value-format="YYYY-MM-DD" style="width:160px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadSeries" :loading="loading">查询</el-button>
          <el-button type="success" @click="autoPopulate" :loading="loading">自动填充</el-button>
        </el-form-item>
      </el-form>

      <!-- 主力合约序列 -->
      <el-table :data="seriesList" stripe v-loading="loading" style="margin-top:16px">
        <el-table-column prop="trade_date" label="日期" width="140" />
        <el-table-column prop="contract_code" label="主力合约" width="140" />
        <el-table-column prop="method" label="来源" width="120">
          <template #default="{ row }">
            <el-tag :type="row.method === 'manual' ? 'warning' : 'success'" size="small">
              {{ row.method === 'manual' ? '手动设置' : '持仓量驱动' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="setMainContract(row)">修改</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 换月信息 -->
      <el-divider>换月记录</el-divider>
      <el-table :data="rolloverList" stripe>
        <el-table-column prop="date" label="换月日期" width="140" />
        <el-table-column prop="from_contract" label="原主力合约" width="140" />
        <el-table-column prop="to_contract" label="新主力合约" width="140" />
      </el-table>
    </el-card>

    <!-- 修改主力合约对话框 -->
    <el-dialog v-model="dialogVisible" title="修改主力合约" width="400px">
      <el-form :model="setForm" label-width="100px">
        <el-form-item label="日期">
          <el-input :value="setForm.date" disabled />
        </el-form-item>
        <el-form-item label="主力合约">
          <el-input v-model="setForm.contractCode" placeholder="如 IM2506" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitSetMain">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { mainContractAPI, productAPI } from '@/api'

const products = ref([])
const loading = ref(false)
const queryForm = ref({
  productCode: 'IF',
  startDate: '',
  endDate: '',
})
const seriesList = ref([])
const rolloverList = ref([])
const dialogVisible = ref(false)
const setForm = ref({ date: '', contractCode: '' })

const loadProducts = async () => {
  try {
    const res = await productAPI.list()
    products.value = res.data || []
  } catch {}
}

const loadSeries = async () => {
  if (!queryForm.value.productCode) {
    ElMessage.warning('请选择品种')
    return
  }
  if (!queryForm.value.startDate || !queryForm.value.endDate) {
    ElMessage.warning('请选择日期范围')
    return
  }
  loading.value = true
  try {
    const [seriesRes, rolloverRes] = await Promise.all([
      mainContractAPI.series(queryForm.value.productCode, queryForm.value.startDate, queryForm.value.endDate),
      mainContractAPI.rollovers(queryForm.value.productCode, queryForm.value.startDate, queryForm.value.endDate),
    ])
    seriesList.value = seriesRes.data?.data || []
    rolloverList.value = rolloverRes.data?.data || []
  } catch {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

const autoPopulate = async () => {
  if (!queryForm.value.productCode || !queryForm.value.startDate || !queryForm.value.endDate) {
    ElMessage.warning('请先选择品种和日期范围')
    return
  }
  loading.value = true
  try {
    const res = await mainContractAPI.autoPopulate(
      queryForm.value.productCode,
      queryForm.value.startDate,
      queryForm.value.endDate
    )
    ElMessage.success(`自动填充 ${res.data?.inserted || 0} 条主力合约记录`)
    loadSeries()
  } catch {
    ElMessage.error('自动填充失败')
  } finally {
    loading.value = false
  }
}

const setMainContract = (row) => {
  setForm.value = { date: row.trade_date, contractCode: row.contract_code }
  dialogVisible.value = true
}

const submitSetMain = async () => {
  if (!setForm.value.contractCode) {
    ElMessage.warning('请输入主力合约代码')
    return
  }
  loading.value = true
  try {
    await mainContractAPI.set(queryForm.value.productCode, setForm.value.date, setForm.value.contractCode)
    ElMessage.success('修改成功')
    dialogVisible.value = false
    loadSeries()
  } catch {
    ElMessage.error('修改失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadProducts()
  // 默认查询当前月
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  queryForm.value.startDate = `${year}-${month}-01`
  const lastDay = new Date(year, now.getMonth() + 1, 0).getDate()
  queryForm.value.endDate = `${year}-${month}-${String(lastDay).padStart(2, '0')}`
  loadSeries()
})
</script>

<style scoped>
.page-container { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.query-form { margin-bottom: 0; }
</style>
