<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>交易所管理</span>
          <el-button type="primary" @click="showCreateDialog">
            <el-icon><Plus /></el-icon>
            新建交易所
          </el-button>
        </div>
      </template>

      <el-table :data="list" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="exchange_code" label="代码" width="120" />
        <el-table-column prop="exchange_name" label="名称" />
        <el-table-column prop="timezone" label="时区" width="140" />
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '是' : '否' }}
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
        <el-form-item label="代码" prop="exchange_code">
          <el-input v-model="form.exchange_code" placeholder="如：CFFEX" />
        </el-form-item>
        <el-form-item label="名称" prop="exchange_name">
          <el-input v-model="form.exchange_name" placeholder="如：中金所" />
        </el-form-item>
        <el-form-item label="交易时段">
          <el-input v-model="form.trading_hours" placeholder="JSON 格式，可选" />
        </el-form-item>
        <el-form-item label="时区">
          <el-input v-model="form.timezone" placeholder="Asia/Shanghai" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
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
import { exchangeAPI } from '@/api'

const list = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref(null)
const isEdit = ref(false)

const form = ref({
  exchange_code: '',
  exchange_name: '',
  trading_hours: '',
  timezone: 'Asia/Shanghai',
  is_active: true
})

const rules = {
  exchange_code: [{ required: true, message: '请输入代码', trigger: 'blur' }],
  exchange_name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
}

const dialogTitle = ref('')

const loadList = async () => {
  loading.value = true
  try {
    const res = await exchangeAPI.list()
    list.value = res.data || []
  } catch {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

const showCreateDialog = () => {
  isEdit.value = false
  dialogTitle.value = '新建交易所'
  dialogVisible.value = true
}

const editItem = (item) => {
  isEdit.value = true
  dialogTitle.value = '编辑交易所'
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
        await exchangeAPI.update(form.value.id, form.value)
        ElMessage.success('更新成功')
      } else {
        await exchangeAPI.create(form.value)
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
    await exchangeAPI.delete(id)
    ElMessage.success('删除成功')
    loadList()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

const resetForm = () => {
  form.value = { exchange_code: '', exchange_name: '', trading_hours: '', timezone: 'Asia/Shanghai', is_active: true }
}

onMounted(loadList)
</script>

<style scoped>
.page-container { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
