<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>数据目录管理</span>
          <el-button type="primary" @click="showCreateDialog">
            <el-icon><Plus /></el-icon>
            新建目录
          </el-button>
        </div>
      </template>

      <el-table :data="catalogs" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="catalog_name" label="目录名称" />
        <el-table-column prop="exchange_code" label="交易所" width="100" />
        <el-table-column prop="product_code" label="品种" width="100" />
        <el-table-column prop="data_type" label="数据类型" width="120" />
        <el-table-column prop="sync_mode" label="同步模式" width="120" />
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_enabled ? 'success' : 'info'" size="small">
              {{ row.is_enabled ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="editCatalog(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteCatalog(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Create/Edit Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="500px"
      @closed="resetForm"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="100px"
        label-position="right"
      >
        <el-form-item label="目录名称" prop="catalog_name">
          <el-input v-model="form.catalog_name" placeholder="如：中金所-MO-日线" />
        </el-form-item>

        <el-form-item label="交易所" prop="exchange_code">
          <el-select v-model="form.exchange_code" placeholder="选择交易所" style="width: 100%">
            <el-option label="CFFEX (中金所)" value="CFFEX" />
            <el-option label="SHFE (上期所)" value="SHFE" />
            <el-option label="DCE (大商所)" value="DCE" />
            <el-option label="CZCE (郑商所)" value="CZCE" />
            <el-option label="INE (能源中心)" value="INE" />
          </el-select>
        </el-form-item>

        <el-form-item label="品种" prop="product_code">
          <el-input v-model="form.product_code" placeholder="如：MO、IM、AU" />
        </el-form-item>

        <el-form-item label="合约代码">
          <el-input v-model="form.contract_code" placeholder="可选，如：MO2505" />
        </el-form-item>

        <el-form-item label="数据类型" prop="data_type">
          <el-select v-model="form.data_type" placeholder="选择数据类型" style="width: 100%">
            <el-option label="daily" value="daily" />
            <el-option label="minute" value="minute" />
            <el-option label="position" value="position" />
            <el-option label="option" value="option" />
            <el-option label="settlement" value="settlement" />
          </el-select>
        </el-form-item>

        <el-form-item label="数据源" prop="data_source">
          <el-select v-model="form.data_source" placeholder="选择数据源" style="width: 100%">
            <el-option label="Tushare" value="tushare" />
            <el-option label="CFFEX" value="cffex" />
            <el-option label="SHFE" value="shfe" />
            <el-option label="CFMMC" value="cfmmc" />
            <el-option label="AkShare" value="akshare" />
          </el-select>
        </el-form-item>

        <el-form-item label="同步模式" prop="sync_mode">
          <el-radio-group v-model="form.sync_mode">
            <el-radio label="incremental">增量同步</el-radio>
            <el-radio label="full">全量同步</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="频率">
          <el-select v-model="form.frequency" placeholder="选择同步频率" style="width: 100%">
            <el-option label="每日" value="daily" />
            <el-option label="每分钟" value="minutely" />
            <el-option label="每周" value="weekly" />
            <el-option label="手动" value="manual" />
          </el-select>
        </el-form-item>

        <el-form-item label="启用">
          <el-switch v-model="form.is_enabled" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">
          {{ dialogTitle }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { catalogAPI } from '@/api'

const catalogs = ref([])
const loading = ref(false)

const dialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref(null)
const isEdit = ref(false)

const form = ref({
  catalog_name: '',
  exchange_code: '',
  product_code: '',
  contract_code: '',
  data_type: 'daily',
  data_source: 'tushare',
  frequency: 'daily',
  sync_mode: 'incremental',
  is_enabled: true
})

const rules = {
  catalog_name: [{ required: true, message: '请输入目录名称', trigger: 'blur' }],
  exchange_code: [{ required: true, message: '请选择交易所', trigger: 'change' }],
  product_code: [{ required: true, message: '请输入品种代码', trigger: 'blur' }],
  data_type: [{ required: true, message: '请选择数据类型', trigger: 'change' }],
  data_source: [{ required: true, message: '请选择数据源', trigger: 'change' }],
  sync_mode: [{ required: true, message: '请选择同步模式', trigger: 'change' }],
}

const dialogTitle = ref('')

const loadCatalogs = async () => {
  loading.value = true
  try {
    const res = await catalogAPI.list()
    catalogs.value = res.data || []
  } catch (error) {
    ElMessage.error('加载数据目录失败')
  } finally {
    loading.value = false
  }
}

const showCreateDialog = () => {
  isEdit.value = false
  dialogTitle.value = '新建目录'
  dialogVisible.value = true
}

const editCatalog = (catalog) => {
  isEdit.value = true
  dialogTitle.value = '编辑目录'
  form.value = {
    id: catalog.id,
    catalog_name: catalog.catalog_name,
    exchange_code: catalog.exchange_code,
    product_code: catalog.product_code,
    contract_code: catalog.contract_code || '',
    data_type: catalog.data_type,
    data_source: catalog.data_source,
    frequency: catalog.frequency || '',
    sync_mode: catalog.sync_mode,
    is_enabled: catalog.is_enabled
  }
  dialogVisible.value = true
}

const submitForm = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return

    submitting.value = true
    try {
      if (isEdit.value) {
        await catalogAPI.update(form.value.id, form.value)
        ElMessage.success('更新成功')
      } else {
        await catalogAPI.create(form.value)
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      loadCatalogs()
    } catch (error) {
      ElMessage.error(isEdit.value ? '更新失败' : '创建失败')
    } finally {
      submitting.value = false
    }
  })
}

const deleteCatalog = async (id) => {
  try {
    await ElMessageBox.confirm('确定要删除该数据目录吗？', '确认删除', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await catalogAPI.delete(id)
    ElMessage.success('删除成功')
    loadCatalogs()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const resetForm = () => {
  form.value = {
    catalog_name: '',
    exchange_code: '',
    product_code: '',
    contract_code: '',
    data_type: 'daily',
    data_source: 'tushare',
    frequency: 'daily',
    sync_mode: 'incremental',
    is_enabled: true
  }
}

onMounted(() => {
  loadCatalogs()
})
</script>

<style scoped>
.page-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
