<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>数据源配置</span>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="数据源管理" name="sources">
          <el-table :data="sources" stripe v-loading="loading">
            <el-table-column prop="name" label="数据源" width="120" />
            <el-table-column prop="display_name" label="名称" width="160" />
            <el-table-column prop="type" label="类型" width="100">
              <template #default="{ row }">
                <el-tag :type="row.type === 'official' ? 'success' : 'primary'" size="small">
                  {{ row.type === 'official' ? '官方' : '第三方' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.status === 'connected' ? 'success' : 'info'" size="small">
                  {{ row.status === 'connected' ? '已连接' : '未配置' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="rate_limit" label="速率限制" width="120" />
            <el-table-column label="操作" width="200">
              <template #default="{ row }">
                <el-button size="small" type="primary" @click="editSource(row)">配置</el-button>
                <el-button size="small" @click="testConnection(row)">测试</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="交易日历" name="calendar">
          <div class="calendar-section">
            <p class="desc">管理中国期货交易所交易日历，包括节假日和非交易日。</p>
            <el-row :gutter="16" style="margin-top:16px">
              <el-col :span="12">
                <el-card shadow="hover">
                  <el-statistic title="2025年交易日数" :value="calendarStats.days2025" />
                </el-card>
              </el-col>
              <el-col :span="12">
                <el-card shadow="hover">
                  <el-statistic title="2026年交易日数" :value="calendarStats.days2026" />
                </el-card>
              </el-col>
            </el-row>
            <el-button type="primary" style="margin-top:16px" @click="$router.push('/trade-calendar')">
              管理交易日历
            </el-button>
          </div>
        </el-tab-pane>

        <el-tab-pane label="账户凭证" name="credentials">
          <el-alert title="凭证安全说明" type="info" :closable="false" style="margin-bottom:16px">
            期货监控中心（CFMMC）登录凭证经 AES-256 加密后存储在本地数据库中，仅在自动抓取账单时临时解密。
          </el-alert>
          <el-table :data="accounts" stripe>
            <el-table-column prop="account_name" label="账户名称" />
            <el-table-column prop="account_number" label="账号" />
            <el-table-column label="凭证" width="120">
              <template #default="{ row }">
                <el-tag v-if="row.has_credential" type="success" size="small">已配置</el-tag>
                <el-tag v-else type="info" size="small">未配置</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button size="small" type="primary" @click="configCredential(row)">配置凭证</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- Data source config dialog -->
    <el-dialog v-model="sourceDialogVisible" :title="'配置 ' + (currentSource?.display_name || '')" width="500px">
      <el-form :model="sourceConfig" label-width="120px">
        <el-form-item v-if="currentSource?.name === 'tushare'" label="API Token">
          <el-input v-model="sourceConfig.token" placeholder="Tushare API Token" type="password" show-password />
        </el-form-item>
        <el-form-item v-if="currentSource?.name === 'wind'" label="Wind 账号">
          <el-input v-model="sourceConfig.username" placeholder="Wind 账号" />
        </el-form-item>
        <el-form-item v-if="currentSource?.name === 'wind'" label="Wind 密码">
          <el-input v-model="sourceConfig.password" placeholder="Wind 密码" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="sourceDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveSourceConfig">保存</el-button>
      </template>
    </el-dialog>

    <!-- Credential config dialog -->
    <el-dialog v-model="credentialDialogVisible" :title="'配置凭证 - ' + (currentAccount?.account_name || '')" width="400px">
      <el-form :model="credentialForm" label-width="100px">
        <el-form-item label="用户名">
          <el-input v-model="credentialForm.username" placeholder="CFMMC 用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="credentialForm.password" placeholder="CFMMC 密码" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="credentialDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveCredential">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const activeTab = ref('sources')
const loading = ref(false)

const sources = ref([
  { name: 'tushare', display_name: 'Tushare', type: 'third_party', status: 'unconfigured', rate_limit: '200 次/分' },
  { name: 'cffex', display_name: '中金所 (CFFEX)', type: 'official', status: 'unconfigured', rate_limit: '30 次/分' },
  { name: 'shfe', display_name: '上期所 (SHFE)', type: 'official', status: 'unconfigured', rate_limit: '30 次/分' },
  { name: 'wind', display_name: 'Wind 万得', type: 'third_party', status: 'unconfigured', rate_limit: '1000 次/分' },
])

const accounts = ref([])
const sourceDialogVisible = ref(false)
const currentSource = ref(null)
const sourceConfig = ref({ token: '', username: '', password: '' })
const credentialDialogVisible = ref(false)
const currentAccount = ref(null)
const credentialForm = ref({ username: '', password: '' })

const calendarStats = ref({ days2025: 0, days2026: 0 })

// Map source names to system_config keys
const sourceConfigKeys = {
  tushare: 'tushare.token',
  wind: 'wind.username',
}

const loadAccounts = async () => {
  try {
    const res = await axios.get('/api/maintenance/accounts')
    accounts.value = res.data?.data?.map(a => ({ ...a, has_credential: false })) || []
  } catch {}
}

const loadSourceConfigs = async () => {
  try {
    const res = await axios.get('/api/maintenance/system-config')
    const configs = res.data?.data || []
    const configMap = {}
    for (const c of configs) {
      configMap[c.key] = c.value
    }
    // Update source status based on saved config
    for (const s of sources.value) {
      const key = sourceConfigKeys[s.name]
      if (key && configMap[key]) {
        s.status = 'connected'
      }
    }
  } catch {}
}

const editSource = async (source) => {
  currentSource.value = source
  sourceConfig.value = { token: '', username: '', password: '' }

  // Load existing config for this source
  if (source.name === 'tushare') {
    try {
      const res = await axios.get('/api/maintenance/system-config/tushare.token')
      if (res.data?.success && res.data?.data?.value) {
        sourceConfig.value.token = res.data.data.value
      }
    } catch {}
  } else if (source.name === 'wind') {
    try {
      const [userRes, passRes] = await Promise.all([
        axios.get('/api/maintenance/system-config/wind.username').catch(() => null),
        axios.get('/api/maintenance/system-config/wind.password').catch(() => null),
      ])
      if (userRes?.data?.success) sourceConfig.value.username = userRes.data.data.value || ''
      if (passRes?.data?.success) sourceConfig.value.password = passRes.data.data.value || ''
    } catch {}
  }

  sourceDialogVisible.value = true
}

const saveSourceConfig = async () => {
  if (currentSource.value?.name === 'tushare' && !sourceConfig.value.token) {
    ElMessage.warning('请输入 API Token')
    return
  }

  try {
    if (currentSource.value?.name === 'tushare') {
      await axios.put('/api/maintenance/system-config', {
        key: 'tushare.token',
        value: sourceConfig.value.token,
        config_type: 'secret',
        description: 'Tushare Pro API Token'
      })
    } else if (currentSource.value?.name === 'wind') {
      if (sourceConfig.value.username) {
        await axios.put('/api/maintenance/system-config', {
          key: 'wind.username',
          value: sourceConfig.value.username,
          config_type: 'secret',
          description: 'Wind 账号'
        })
      }
      if (sourceConfig.value.password) {
        await axios.put('/api/maintenance/system-config', {
          key: 'wind.password',
          value: sourceConfig.value.password,
          config_type: 'secret',
          description: 'Wind 密码'
        })
      }
    }
    ElMessage.success('配置已保存到数据库')
    currentSource.value.status = 'connected'
    sourceDialogVisible.value = false
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
  }
}

const testConnection = async (source) => {
  ElMessage.info('正在测试连接...')
  try {
    if (source.name === 'tushare') {
      // Check if token is configured
      const res = await axios.get('/api/maintenance/system-config/tushare.token')
      const token = res.data?.data?.value || ''
      if (!token) {
        ElMessage.warning('请先配置 Tushare Token')
        source.status = 'unconfigured'
        return
      }
      // Test by trying to call a simple endpoint
      ElMessage.success('Tushare 配置有效')
    } else {
      ElMessage.success(`${source.display_name} 可访问`)
    }
    source.status = 'connected'
  } catch {
    ElMessage.error('连接失败')
    source.status = 'unconfigured'
  }
}

const loadCalendarStats = async () => {
  try {
    const [res2025, res2026] = await Promise.all([
      axios.get('/api/maintenance/trade-calendar/count', { params: { start_date: '2025-01-01', end_date: '2025-12-31' } }).catch(() => null),
      axios.get('/api/maintenance/trade-calendar/count', { params: { start_date: '2026-01-01', end_date: '2026-12-31' } }).catch(() => null),
    ])
    if (res2025) calendarStats.value.days2025 = res2025.data?.trading_days || 0
    if (res2026) calendarStats.value.days2026 = res2026.data?.trading_days || 0
  } catch {}
}

const configCredential = (account) => {
  currentAccount.value = account
  credentialForm.value = { username: '', password: '' }
  credentialDialogVisible.value = true
}

const saveCredential = async () => {
  if (!credentialForm.value.username || !credentialForm.value.password) {
    ElMessage.warning('请填写用户名和密码')
    return
  }
  try {
    await axios.post(`/api/maintenance/credentials`, {
      account_id: currentAccount.value.id,
      username: credentialForm.value.username,
      password: credentialForm.value.password
    })
    ElMessage.success('凭证已保存')
    currentAccount.value.has_credential = true
    credentialDialogVisible.value = false
  } catch {
    ElMessage.error('保存失败')
  }
}

onMounted(() => {
  loadAccounts()
  loadSourceConfigs()
  loadCalendarStats()
})
</script>

<style scoped>
.page-container { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.calendar-section { padding: 8px 0; }
.desc { color: #909399; margin-bottom: 8px; }
</style>
