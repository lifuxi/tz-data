<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>特殊日期管理</span>
          <el-button type="primary" @click="showCreateDialog">
            <el-icon><Plus /></el-icon>
            添加特殊日期
          </el-button>
        </div>
      </template>

      <!-- 筛选区域 -->
      <el-form :inline="true" :model="filterForm" class="query-form">
        <el-form-item label="交易所">
          <el-select v-model="filterForm.exchangeCode" placeholder="全部" clearable style="width:120px">
            <el-option label="ALL (全部)" value="ALL" />
            <el-option label="CFFEX" value="CFFEX" />
            <el-option label="SHFE" value="SHFE" />
            <el-option label="DCE" value="DCE" />
            <el-option label="CZCE" value="CZCE" />
            <el-option label="INE" value="INE" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始日期">
          <el-date-picker v-model="filterForm.startDate" value-format="YYYY-MM-DD" style="width:160px" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker v-model="filterForm.endDate" value-format="YYYY-MM-DD" style="width:160px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadList" :loading="loading">筛选</el-button>
        </el-form-item>
      </el-form>

      <!-- 列表 -->
      <el-table :data="list" stripe v-loading="loading" style="margin-top:16px">
        <el-table-column prop="exchange_code" label="交易所" width="100" />
        <el-table-column prop="trade_date" label="日期" width="140" />
        <el-table-column prop="override_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="typeTag(row.override_type)" size="small">
              {{ typeLabel(row.override_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="原因" />
        <el-table-column prop="operator" label="操作人" width="100" />
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-popconfirm title="确定删除该特殊日期？" @confirm="deleteItem(row)">
              <template #reference>
                <el-button size="small" type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 添加对话框 -->
    <el-dialog v-model="dialogVisible" title="添加特殊日期" width="450px" @closed="resetForm">
      <el-form :model="form" label-width="100px">
        <el-form-item label="交易所">
          <el-select v-model="form.exchange_code" style="width:100%">
            <el-option label="ALL (全部交易所)" value="ALL" />
            <el-option label="CFFEX" value="CFFEX" />
            <el-option label="SHFE" value="SHFE" />
            <el-option label="DCE" value="DCE" />
            <el-option label="CZCE" value="CZCE" />
            <el-option label="INE" value="INE" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期">
          <el-date-picker v-model="form.trade_date" value-format="YYYY-MM-DD" style="width:100%" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.override_type" style="width:100%">
            <el-option label="节假日 (holiday)" value="holiday" />
            <el-option label="工作日 (workday)" value="workday" />
            <el-option label="半日 (half_day)" value="half_day" />
          </el-select>
        </el-form-item>
        <el-form-item label="原因">
          <el-input v-model="form.reason" type="textarea" :rows="3" placeholder="如：突发休市、调休补班等" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { specialDateAPI } from '@/api'

const list = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const filterForm = ref({ exchangeCode: '', startDate: '', endDate: '' })
const form = ref({ exchange_code: 'ALL', trade_date: '', override_type: 'holiday', reason: '' })

const typeTag = (type) => {
  const map = { holiday: 'danger', workday: 'success', half_day: 'warning' }
  return map[type] || 'info'
}

const typeLabel = (type) => {
  const map = { holiday: '节假日', workday: '工作日', half_day: '半日' }
  return map[type] || type
}

const loadList = async () => {
  loading.value = true
  try {
    const params = {}
    if (filterForm.value.exchangeCode) params.exchange_code = filterForm.value.exchangeCode
    if (filterForm.value.startDate) params.start_date = filterForm.value.startDate
    if (filterForm.value.endDate) params.end_date = filterForm.value.endDate
    const res = await specialDateAPI.list(params)
    list.value = res.data?.data || []
  } catch {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

const showCreateDialog = () => {
  dialogVisible.value = true
}

const submitForm = async () => {
  if (!form.value.trade_date || !form.value.override_type) {
    ElMessage.warning('请填写日期和类型')
    return
  }
  try {
    await specialDateAPI.create(form.value)
    ElMessage.success('添加成功')
    dialogVisible.value = false
    loadList()
  } catch {
    ElMessage.error('添加失败')
  }
}

const deleteItem = async (row) => {
  try {
    await specialDateAPI.delete(row.exchange_code, row.trade_date)
    ElMessage.success('删除成功')
    loadList()
  } catch {
    ElMessage.error('删除失败')
  }
}

const resetForm = () => {
  form.value = { exchange_code: 'ALL', trade_date: '', override_type: 'holiday', reason: '' }
}

onMounted(() => { loadList() })
</script>

<style scoped>
.page-container { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.query-form { margin-bottom: 0; }
</style>
