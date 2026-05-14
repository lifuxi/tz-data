<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>交易时间模板</span>
          <el-button type="primary" @click="showCreateDialog">
            <el-icon><Plus /></el-icon>
            新建模板
          </el-button>
        </div>
      </template>

      <!-- 模板列表 -->
      <el-table :data="templates" stripe v-loading="loading">
        <el-table-column prop="template_id" label="模板ID" width="180" />
        <el-table-column prop="template_name" label="名称" width="160" />
        <el-table-column prop="exchange_code" label="交易所" width="100" />
        <el-table-column prop="product_type" label="产品类型" width="140" />
        <el-table-column label="日盘时段">
          <template #default="{ row }">
            <span v-for="(s, i) in parseSchedule(row.normal_schedule)" :key="i">
              {{ s.start }}-{{ s.end }}<br>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="夜盘时段">
          <template #default="{ row }">
            <span v-if="row.night_schedule">
              <span v-for="(s, i) in parseSchedule(row.night_schedule)" :key="i">
                {{ s.start }}-{{ s.end }}<br>
              </span>
            </span>
            <span v-else class="text-muted">无</span>
          </template>
        </el-table-column>
        <el-table-column label="集合竞价" width="160">
          <template #default="{ row }">
            <div v-if="row.pre_open">开: {{ row.pre_open.start }}-{{ row.pre_open.end }}</div>
            <div v-if="row.pre_close">收: {{ row.pre_close.start }}-{{ row.pre_close.end }}</div>
          </template>
        </el-table-column>
        <el-table-column label="默认" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_default ? 'success' : 'info'" size="small">
              {{ row.is_default ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="viewSessions(row)">查看时段</el-button>
            <el-button size="small" type="primary" @click="editItem(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建/编辑模板对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px" @closed="resetForm">
      <el-form :model="form" label-width="120px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="模板ID">
              <el-input v-model="form.template_id" placeholder="如 cffex_index_futures" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="模板名称">
              <el-input v-model="form.template_name" placeholder="如 中金所股指期货" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="交易所">
              <el-select v-model="form.exchange_code" style="width:100%">
                <el-option label="CFFEX" value="CFFEX" />
                <el-option label="SHFE" value="SHFE" />
                <el-option label="DCE" value="DCE" />
                <el-option label="CZCE" value="CZCE" />
                <el-option label="INE" value="INE" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="产品类型">
              <el-select v-model="form.product_type" style="width:100%">
                <el-option label="股指期货" value="index_future" />
                <el-option label="股指期权" value="index_option" />
                <el-option label="商品期货" value="commodity_future" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 日盘时段 -->
        <el-divider>日盘时段</el-divider>
        <el-form-item v-for="(item, i) in form.normal_schedule" :key="i" :label="`时段 ${i + 1}`">
          <el-row :gutter="10" style="width:100%">
            <el-col :span="10">
              <el-time-picker v-model="item.start" value-format="HH:mm" style="width:100%" />
            </el-col>
            <el-col :span="2" style="text-align:center">至</el-col>
            <el-col :span="10">
              <el-time-picker v-model="item.end" value-format="HH:mm" style="width:100%" />
            </el-col>
            <el-col :span="2">
              <el-button size="small" type="danger" @click="removeNormalSlot(i)" :disabled="form.normal_schedule.length <= 1">
                <el-icon><Delete /></el-icon>
              </el-button>
            </el-col>
          </el-row>
        </el-form-item>
        <el-form-item>
          <el-button size="small" @click="addNormalSlot">+ 添加时段</el-button>
        </el-form-item>

        <!-- 夜盘时段 -->
        <el-divider>夜盘时段</el-divider>
        <el-form-item v-for="(item, i) in form.night_schedule" :key="i" :label="`时段 ${i + 1}`">
          <el-row :gutter="10" style="width:100%">
            <el-col :span="10">
              <el-time-picker v-model="item.start" value-format="HH:mm" style="width:100%" />
            </el-col>
            <el-col :span="2" style="text-align:center">至</el-col>
            <el-col :span="10">
              <el-time-picker v-model="item.end" value-format="HH:mm" style="width:100%" />
            </el-col>
            <el-col :span="2">
              <el-button size="small" type="danger" @click="removeNightSlot(i)" :disabled="form.night_schedule.length <= 1">
                <el-icon><Delete /></el-icon>
              </el-button>
            </el-col>
          </el-row>
        </el-form-item>
        <el-form-item>
          <el-button size="small" @click="addNightSlot">+ 添加夜盘时段</el-button>
        </el-form-item>

        <!-- 集合竞价 -->
        <el-divider>集合竞价</el-divider>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="开盘集合竞价">
              <el-time-picker v-model="form.pre_open_start" value-format="HH:mm" style="width:100%" clearable placeholder="如 09:25" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="收盘集合竞价">
              <el-time-picker v-model="form.pre_close_start" value-format="HH:mm" style="width:100%" clearable placeholder="如 14:57" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="设为默认">
          <el-switch v-model="form.is_default" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 查看时段对话框 -->
    <el-dialog v-model="sessionDialogVisible" :title="`交易时段 - ${currentTemplate?.template_name || ''}`" width="400px">
      <el-table :data="sessions" stripe>
        <el-table-column prop="type" label="类型">
          <template #default="{ row }">
            <el-tag :type="row.type === 'day' ? 'primary' : 'warning'" size="small">
              {{ row.type === 'day' ? '日盘' : '夜盘' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="start" label="开始" />
        <el-table-column prop="end" label="结束" />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'
import { tradingHoursAPI } from '@/api'

const templates = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const sessionDialogVisible = ref(false)
const currentTemplate = ref(null)
const sessions = ref([])
const isEdit = ref(false)

const form = ref({
  template_id: '',
  template_name: '',
  exchange_code: 'CFFEX',
  product_type: 'index_future',
  normal_schedule: [{ start: '09:30', end: '11:30' }, { start: '13:00', end: '15:00' }],
  night_schedule: [],
  pre_open_start: '',
  pre_open_end: '',
  pre_close_start: '',
  pre_close_end: '',
  is_default: false,
})

const dialogTitle = ref('新建模板')

// Built-in template definitions (since there's no list endpoint)
const builtInTemplates = [
  {
    template_id: 'cffex_index_futures',
    template_name: '中金所股指期货',
    exchange_code: 'CFFEX',
    product_type: 'index_future',
    normal_schedule: [{ start: '09:30', end: '11:30' }, { start: '13:00', end: '15:00' }],
    night_schedule: null,
    pre_open: { start: '09:25', end: '09:30' },
    pre_close: { start: '14:57', end: '15:00' },
    is_default: 1,
  },
  {
    template_id: 'cffex_index_options',
    template_name: '中金所股指期权',
    exchange_code: 'CFFEX',
    product_type: 'index_option',
    normal_schedule: [{ start: '09:30', end: '11:30' }, { start: '13:00', end: '15:00' }],
    night_schedule: null,
    pre_open: { start: '09:25', end: '09:30' },
    pre_close: null,
    is_default: 0,
  },
]

const parseSchedule = (schedule) => {
  if (!schedule) return []
  try {
    return typeof schedule === 'string' ? JSON.parse(schedule) : schedule
  } catch {
    return []
  }
}

const loadTemplates = async () => {
  loading.value = true
  const results = []
  for (const tmpl of builtInTemplates) {
    try {
      const res = await tradingHoursAPI.get(tmpl.template_id)
      if (res.data?.success) {
        results.push(res.data.data)
      } else {
        results.push(tmpl)
      }
    } catch {
      results.push(tmpl)
    }
  }
  templates.value = results
  loading.value = false
}

const showCreateDialog = () => {
  isEdit.value = false
  dialogTitle.value = '新建模板'
  resetForm()
  dialogVisible.value = true
}

const editItem = (item) => {
  isEdit.value = true
  dialogTitle.value = '编辑模板'
  const normal = parseSchedule(item.normal_schedule)
  const night = parseSchedule(item.night_schedule)
  form.value = {
    template_id: item.template_id,
    template_name: item.template_name,
    exchange_code: item.exchange_code,
    product_type: item.product_type,
    normal_schedule: normal.length ? normal : [{ start: '09:30', end: '11:30' }],
    night_schedule: night.length ? night : [],
    pre_open_start: item.pre_open?.start || '',
    pre_open_end: item.pre_open?.end || '',
    pre_close_start: item.pre_close?.start || '',
    pre_close_end: item.pre_close?.end || '',
    is_default: !!item.is_default,
  }
  dialogVisible.value = true
}

const addNormalSlot = () => {
  form.value.normal_schedule.push({ start: '', end: '' })
}

const removeNormalSlot = (i) => {
  if (form.value.normal_schedule.length > 1) {
    form.value.normal_schedule.splice(i, 1)
  }
}

const addNightSlot = () => {
  form.value.night_schedule.push({ start: '', end: '' })
}

const removeNightSlot = (i) => {
  if (form.value.night_schedule.length > 1) {
    form.value.night_schedule.splice(i, 1)
  }
}

const submitForm = async () => {
  if (!form.value.template_id || !form.value.template_name) {
    ElMessage.warning('请填写模板ID和名称')
    return
  }
  loading.value = true
  try {
    const params = {
      template_id: form.value.template_id,
      template_name: form.value.template_name,
      exchange_code: form.value.exchange_code,
      product_type: form.value.product_type,
      normal_schedule: JSON.stringify(form.value.normal_schedule),
      night_schedule: form.value.night_schedule.length ? JSON.stringify(form.value.night_schedule) : null,
      is_default: form.value.is_default ? 1 : 0,
    }
    if (form.value.pre_open_start) {
      params.pre_open = JSON.stringify({ start: form.value.pre_open_start, end: form.value.pre_open_end || form.value.pre_open_start })
    }
    if (form.value.pre_close_start) {
      params.pre_close = JSON.stringify({ start: form.value.pre_close_start, end: form.value.pre_close_end || form.value.pre_close_start })
    }
    await tradingHoursAPI.create(params)
    ElMessage.success('保存成功')
    dialogVisible.value = false
    loadTemplates()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    loading.value = false
  }
}

const viewSessions = async (item) => {
  currentTemplate.value = item
  try {
    const res = await tradingHoursAPI.getSessions(item.template_id)
    sessions.value = res.data?.sessions || []
  } catch {
    // Show from local data
    const normal = parseSchedule(item.normal_schedule).map(s => ({ ...s, type: 'day' }))
    const night = (parseSchedule(item.night_schedule) || []).map(s => ({ ...s, type: 'night' }))
    sessions.value = [...normal, ...night]
  }
  sessionDialogVisible.value = true
}

const resetForm = () => {
  form.value = {
    template_id: '',
    template_name: '',
    exchange_code: 'CFFEX',
    product_type: 'index_future',
    normal_schedule: [{ start: '09:30', end: '11:30' }, { start: '13:00', end: '15:00' }],
    night_schedule: [],
    pre_open_start: '',
    pre_open_end: '',
    pre_close_start: '',
    pre_close_end: '',
    is_default: false,
  }
}

onMounted(() => { loadTemplates() })
</script>

<style scoped>
.page-container { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.text-muted { color: #c0c4cc; }
</style>
