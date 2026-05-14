<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>品种管理</span>
          <el-button type="primary" @click="showCreateDialog">
            <el-icon><Plus /></el-icon>
            新建品种
          </el-button>
        </div>
      </template>

      <el-table :data="list" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="exchange_code" label="交易所" width="100" />
        <el-table-column prop="product_code" label="品种代码" width="120" />
        <el-table-column prop="product_name" label="品种名称" />
        <el-table-column prop="product_type" label="类型" width="140" />
        <el-table-column label="跟踪" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_tracked ? 'success' : 'info'" size="small">
              {{ row.is_tracked ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="editItem(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteItem(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px" @closed="resetForm">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="交易所" prop="exchange_code">
          <el-select v-model="form.exchange_code" placeholder="选择交易所" style="width:100%">
            <el-option v-for="ex in exchanges" :key="ex.exchange_code" :label="`${ex.exchange_code} - ${ex.exchange_name}`" :value="ex.exchange_code" />
          </el-select>
        </el-form-item>
        <el-form-item label="品种代码" prop="product_code">
          <el-input v-model="form.product_code" placeholder="如：MO、IM、AU" />
        </el-form-item>
        <el-form-item label="品种名称" prop="product_name">
          <el-input v-model="form.product_name" placeholder="如：中证1000股指期权" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.product_type" placeholder="选择类型" style="width:100%">
            <el-option label="股指期货" value="index_future" />
            <el-option label="商品期货" value="commodity_future" />
            <el-option label="期权" value="option" />
          </el-select>
        </el-form-item>
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
import { Plus } from '@element-plus/icons-vue'
import { productAPI, exchangeAPI } from '@/api'

const list = ref([])
const exchanges = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref(null)
const isEdit = ref(false)

const form = ref({
  exchange_code: '',
  product_code: '',
  product_name: '',
  product_type: 'index_future',
  is_tracked: true
})

const rules = {
  exchange_code: [{ required: true, message: '请选择交易所', trigger: 'change' }],
  product_code: [{ required: true, message: '请输入品种代码', trigger: 'blur' }],
  product_name: [{ required: true, message: '请输入品种名称', trigger: 'blur' }],
}

const dialogTitle = ref('')

const loadList = async () => {
  loading.value = true
  try {
    const res = await productAPI.list()
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

const showCreateDialog = () => {
  isEdit.value = false
  dialogTitle.value = '新建品种'
  dialogVisible.value = true
}

const editItem = (item) => {
  isEdit.value = true
  dialogTitle.value = '编辑品种'
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
        await productAPI.update(form.value.id, form.value)
        ElMessage.success('更新成功')
      } else {
        await productAPI.create(form.value)
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
    await productAPI.delete(id)
    ElMessage.success('删除成功')
    loadList()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

const resetForm = () => {
  form.value = { exchange_code: '', product_code: '', product_name: '', product_type: 'index_future', is_tracked: true }
}

onMounted(() => { loadList(); loadExchanges() })
</script>

<style scoped>
.page-container { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
