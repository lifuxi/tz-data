<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>账户管理</span>
          <el-button type="primary" @click="showCreateDialog">
            <el-icon><Plus /></el-icon>
            新建账户
          </el-button>
        </div>
      </template>
      
      <!-- 账户列表 -->
      <el-table :data="accounts" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="account_name" label="账户名称" />
        <el-table-column prop="account_number" label="账户号" width="150" />
        <el-table-column prop="futures_company" label="期货公司" width="150" />
        <el-table-column prop="exchanges_supported" label="支持交易所" width="200">
          <template #default="{ row }">
            <el-tag v-for="exchange in row.exchanges_supported" :key="exchange" size="small" style="margin-right: 5px;">
              {{ exchange }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="tracking_start_date" label="跟踪起始日期" width="150">
          <template #default="{ row }">
            {{ formatDate(row.tracking_start_date) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'">
              {{ row.status === 'active' ? '活跃' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="editAccount(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteAccount(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    
    <!-- 创建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px">
        <el-form-item label="账户名称" prop="account_name">
          <el-input v-model="form.account_name" placeholder="请输入账户名称" />
        </el-form-item>
        <el-form-item label="账户号" prop="account_number">
          <el-input v-model="form.account_number" placeholder="请输入账户号" />
        </el-form-item>
        <el-form-item label="期货公司" prop="futures_company">
          <el-input v-model="form.futures_company" placeholder="请输入期货公司" />
        </el-form-item>
        <el-form-item label="监控中心用户名">
          <el-input v-model="form.cfmmc_username" placeholder="可选" />
        </el-form-item>
        <el-form-item label="监控中心密码">
          <el-input v-model="form.cfmmc_password" type="password" placeholder="可选，将加密存储" show-password />
        </el-form-item>
        <el-form-item label="支持交易所">
          <el-checkbox-group v-model="form.exchanges_supported">
            <el-checkbox label="CFFEX">中金所</el-checkbox>
            <el-checkbox label="SHFE">上期所</el-checkbox>
            <el-checkbox label="DCE">大商所</el-checkbox>
            <el-checkbox label="CZCE">郑商所</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="跟踪起始日期">
          <el-date-picker
            v-model="form.tracking_start_date"
            type="date"
            placeholder="选择日期"
            style="width: 100%;"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { accountAPI } from '@/api'

const accounts = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新建账户')
const submitting = ref(false)
const formRef = ref(null)

const form = reactive({
  id: null,
  account_name: '',
  account_number: '',
  futures_company: '',
  cfmmc_username: '',
  cfmmc_password: '',
  exchanges_supported: [],
  tracking_start_date: null,
  status: 'active'
})

const rules = {
  account_name: [{ required: true, message: '请输入账户名称', trigger: 'blur' }],
  account_number: [{ required: true, message: '请输入账户号', trigger: 'blur' }],
  futures_company: [{ required: true, message: '请输入期货公司', trigger: 'blur' }]
}

// Load accounts
const loadAccounts = async () => {
  loading.value = true
  try {
    const res = await accountAPI.list()
    accounts.value = res.data || []
  } catch (error) {
    ElMessage.error('加载账户列表失败')
  } finally {
    loading.value = false
  }
}

// Show create dialog
const showCreateDialog = () => {
  dialogTitle.value = '新建账户'
  resetForm()
  dialogVisible.value = true
}

// Edit account
const editAccount = (account) => {
  dialogTitle.value = '编辑账户'
  Object.assign(form, account)
  dialogVisible.value = true
}

// Submit form
const submitForm = async () => {
  if (!formRef.value) return
  
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    
    submitting.value = true
    try {
      if (form.id) {
        await accountAPI.update(form.id, form)
        ElMessage.success('更新成功')
      } else {
        await accountAPI.create(form)
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      loadAccounts()
    } catch (error) {
      ElMessage.error(form.id ? '更新失败' : '创建失败')
    } finally {
      submitting.value = false
    }
  })
}

// Delete account
const deleteAccount = async (id) => {
  try {
    await ElMessageBox.confirm('确定要删除该账户吗？', '警告', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    await accountAPI.delete(id)
    ElMessage.success('删除成功')
    loadAccounts()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// Reset form
const resetForm = () => {
  form.id = null
  form.account_name = ''
  form.account_number = ''
  form.futures_company = ''
  form.cfmmc_username = ''
  form.cfmmc_password = ''
  form.exchanges_supported = []
  form.tracking_start_date = null
  form.status = 'active'
}

// Format date
const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

onMounted(() => {
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
</style>
