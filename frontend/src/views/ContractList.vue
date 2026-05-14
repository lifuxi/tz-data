<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>合约管理</span>
          <div>
            <el-button type="success" @click="syncFutures" :loading="syncLoading">
              <el-icon><Refresh /></el-icon>
              同步期货
            </el-button>
            <el-button type="warning" @click="syncOptions" :loading="syncLoading">
              <el-icon><Refresh /></el-icon>
              同步期权
            </el-button>
            <el-button type="info" @click="checkExpired" :loading="syncLoading">
              <el-icon><Warning /></el-icon>
              标记到期
            </el-button>
            <el-button type="primary" @click="showCreateDialog">
              <el-icon><Plus /></el-icon>
              新建合约
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="list" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="contract_code" label="合约代码" width="140" />
        <el-table-column prop="exchange_code" label="交易所" width="100" />
        <el-table-column prop="product_code" label="品种" width="100" />
        <el-table-column prop="contract_type" label="类型" width="100" />
        <el-table-column prop="underlying_contract" label="标的合约" width="120" />
        <el-table-column prop="strike_price" label="行权价" width="100" />
        <el-table-column prop="expiry_date" label="到期日" width="120" />
        <el-table-column prop="last_trade_date" label="最后交易日" width="120" />
        <el-table-column prop="delivery_date" label="交割日" width="120" />
        <el-table-column prop="multiplier" label="乘数" width="80" />
        <el-table-column prop="tick_size" label="最小变动" width="80" />
        <el-table-column label="跟踪" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_tracked ? 'success' : 'info'" size="small">
              {{ row.is_tracked ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="editItem(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteItem(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px" @closed="resetForm">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="合约代码" prop="contract_code">
              <el-input v-model="form.contract_code" placeholder="如：IM2506" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="交易所" prop="exchange_code">
              <el-select v-model="form.exchange_code" placeholder="选择交易所" style="width:100%">
                <el-option v-for="ex in exchanges" :key="ex.exchange_code" :label="`${ex.exchange_code}`" :value="ex.exchange_code" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="品种" prop="product_code">
              <el-select v-model="form.product_code" placeholder="选择品种" style="width:100%">
                <el-option v-for="p in products" :key="p.product_code" :label="`${p.product_code} - ${p.product_name}`" :value="p.product_code" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="类型">
              <el-select v-model="form.contract_type" placeholder="选择类型" style="width:100%">
                <el-option label="期货" value="future" />
                <el-option label="期权" value="option" />
                <el-option label="指数" value="index" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="标的合约">
          <el-input v-model="form.underlying_contract" placeholder="期权标的合约代码" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="行权价">
              <el-input-number v-model="form.strike_price" :precision="2" :step="0.01" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="乘数">
              <el-input-number v-model="form.multiplier" :precision="2" :step="1" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="最小变动价位">
              <el-input-number v-model="form.tick_size" :precision="4" :step="0.0001" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-select v-model="form.status" style="width:100%">
                <el-option label="上市" value="active" />
                <el-option label="停牌" value="suspended" />
                <el-option label="退市" value="delisted" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="上市日期">
              <el-date-picker v-model="form.listing_date" value-format="YYYY-MM-DD" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="到期日">
              <el-date-picker v-model="form.expiry_date" value-format="YYYY-MM-DD" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="跟踪">
          <el-switch v-model="form.is_tracked" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">{{ dialogTitle }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Warning } from '@element-plus/icons-vue'
import { contractAPI, exchangeAPI, productAPI } from '@/api'

const list = ref([])
const exchanges = ref([])
const products = ref([])
const loading = ref(false)
const syncLoading = ref(false)
const dialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref(null)
const isEdit = ref(false)

const form = ref({
  contract_code: '',
  exchange_code: '',
  product_code: '',
  contract_type: 'future',
  underlying_contract: '',
  strike_price: null,
  listing_date: '',
  expiry_date: '',
  multiplier: null,
  tick_size: null,
  status: 'active',
  is_tracked: true
})

const rules = {
  contract_code: [{ required: true, message: '请输入合约代码', trigger: 'blur' }],
  exchange_code: [{ required: true, message: '请选择交易所', trigger: 'change' }],
  product_code: [{ required: true, message: '请选择品种', trigger: 'change' }],
}

const dialogTitle = ref('')

const loadList = async () => {
  loading.value = true
  try {
    const res = await contractAPI.list()
    list.value = res.data || []
  } catch {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

const loadExchanges = async () => {
  try {
    const res = await exchangeAPI.list()
    exchanges.value = res.data || []
  } catch {}
}

const loadProducts = async () => {
  try {
    const res = await productAPI.list()
    products.value = res.data || []
  } catch {}
}

const showCreateDialog = () => {
  isEdit.value = false
  dialogTitle.value = '新建合约'
  dialogVisible.value = true
}

const editItem = (item) => {
  isEdit.value = true
  dialogTitle.value = '编辑合约'
  form.value = { ...item }
  dialogVisible.value = true
}

const submitForm = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      if (isEdit.value) {
        await contractAPI.update(form.value.id, form.value)
        ElMessage.success('更新成功')
      } else {
        await contractAPI.create(form.value)
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      loadList()
    } catch {
      ElMessage.error(isEdit.value ? '更新失败' : '创建失败')
    } finally {
      submitting.value = false
    }
  })
}

const deleteItem = async (id) => {
  try {
    await ElMessageBox.confirm('确定删除？', '确认', { type: 'warning' })
    await contractAPI.delete(id)
    ElMessage.success('删除成功')
    loadList()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

const resetForm = () => {
  form.value = {
    contract_code: '',
    exchange_code: '',
    product_code: '',
    contract_type: 'future',
    underlying_contract: '',
    strike_price: null,
    listing_date: '',
    expiry_date: '',
    multiplier: null,
    tick_size: null,
    status: 'active',
    is_tracked: true
  }
}

const syncFutures = async () => {
  syncLoading.value = true
  try {
    const res = await contractAPI.syncFromTushare('CFFEX', 'futures')
    ElMessage.success(`同步完成，新增 ${res.data?.inserted || 0} 条期货合约`)
    loadList()
  } catch {
    ElMessage.error('同步期货合约失败')
  } finally {
    syncLoading.value = false
  }
}

const syncOptions = async () => {
  syncLoading.value = true
  try {
    const res = await contractAPI.syncFromTushare('CFFEX', 'options')
    ElMessage.success(`同步完成，新增 ${res.data?.inserted || 0} 条期权合约`)
    loadList()
  } catch {
    ElMessage.error('同步期权合约失败')
  } finally {
    syncLoading.value = false
  }
}

const checkExpired = async () => {
  syncLoading.value = true
  try {
    const res = await contractAPI.checkExpired()
    ElMessage.success(`已标记 ${res.data?.expired || 0} 条到期合约`)
    loadList()
  } catch {
    ElMessage.error('标记到期合约失败')
  } finally {
    syncLoading.value = false
  }
}

onMounted(() => { loadList(); loadExchanges(); loadProducts() })
</script>

<style scoped>
.page-container { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
