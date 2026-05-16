<template>
  <div class="notification-config">
    <div class="page-header">
      <h2 class="page-title">通知配置</h2>
      <p class="page-description">管理 Webhook 通知渠道（企业微信 / 钉钉）</p>
    </div>

    <el-row :gutter="16">
      <!-- Webhook 配置卡片 -->
      <el-col :span="16">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>Webhook 配置</span>
              <el-button type="primary" size="small" @click="saveConfig" :loading="saving">保存</el-button>
            </div>
          </template>

          <el-form :model="form" label-width="120px" label-position="left">
            <el-form-item label="企业微信 Webhook">
              <el-input
                v-model="form.wechatWebhook"
                placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..."
                clearable
              />
              <div class="form-tip">
                企业微信群机器人 Webhook 地址，设置后同步失败告警将推送至该群
              </div>
            </el-form-item>

            <el-form-item label="钉钉 Webhook">
              <el-input
                v-model="form.dingtalkWebhook"
                placeholder="https://oapi.dingtalk.com/robot/send?access_token=..."
                clearable
              />
              <div class="form-tip">
                钉钉群机器人 Webhook 地址，安全设置选择"自定义关键词"，关键词包含：TZ2、tz-data、同步告警
              </div>
            </el-form-item>

            <el-form-item label="Celery Beat 状态">
              <el-tag :type="beatStatus === 'running' ? 'success' : 'danger'">
                {{ beatStatus === 'running' ? '运行中' : '未运行' }}
              </el-tag>
              <div class="form-tip">
                定时任务调度器状态，数据质量检测和同步失败告警依赖 Beat 正常运行
              </div>
            </el-form-item>
          </el-form>

          <el-divider />

          <div style="display: flex; gap: 8px;">
            <el-button type="warning" @click="sendTestNotification('wechat')" :loading="testingWechat" :disabled="!form.wechatWebhook">
              测试企业微信
            </el-button>
            <el-button type="primary" @click="sendTestNotification('dingtalk')" :loading="testingDingtalk" :disabled="!form.dingtalkWebhook">
              测试钉钉
            </el-button>
          </div>
        </el-card>
      </el-col>

      <!-- 通知相关任务状态 -->
      <el-col :span="8">
        <el-card>
          <template #header>
            <span>定时任务状态</span>
          </template>

          <el-table :data="alertTasks" size="small" stripe>
            <el-table-column prop="name" label="任务名" width="140">
              <template #default="{ row }">
                {{ row.name.split('.').pop() || row.name }}
              </template>
            </el-table-column>
            <el-table-column prop="schedule" label="调度时间" />
          </el-table>

          <el-divider />

          <el-descriptions :column="1" size="small" border>
            <el-descriptions-item label="告警冷却">
              同任务 5 分钟内不重复推送
            </el-descriptions-item>
            <el-descriptions-item label="告警范围">
              同步任务、质量检查、对账任务
            </el-descriptions-item>
            <el-descriptions-item label="记录存储">
              market.db / task_failure_log
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

const form = ref({
  wechatWebhook: '',
  dingtalkWebhook: '',
})

const saving = ref(false)
const testingWechat = ref(false)
const testingDingtalk = ref(false)
const beatStatus = ref('unknown')

const alertTasks = ref([
  { name: 'daily-gap-detection', schedule: '18:50' },
  { name: 'daily-reconcile-records', schedule: '18:45' },
  { name: 'daily-completeness-check', schedule: '19:00' },
  { name: 'daily-incremental-sync', schedule: '18:00' },
])

const loadConfig = async () => {
  try {
    const res = await fetch('/api/maintenance/system-config')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    if (data.success) {
      const configs = {}
      for (const c of data.data) {
        configs[c.key] = c.value
      }
      form.value.wechatWebhook = configs['wechat.webhook'] || ''
      form.value.dingtalkWebhook = configs['dingtalk.webhook'] || ''
    }
  } catch (error) {
    console.warn('Failed to load notification config:', error.message)
  }
}

const saveConfig = async () => {
  saving.value = true
  try {
    const entries = [
      { key: 'wechat.webhook', value: form.value.wechatWebhook, type: 'string', description: '企业微信机器人 Webhook URL' },
      { key: 'dingtalk.webhook', value: form.value.dingtalkWebhook, type: 'string', description: '钉钉机器人 Webhook URL' },
    ]

    for (const entry of entries) {
      const res = await fetch('/api/maintenance/system-config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(entry),
      })
      if (!res.ok) throw new Error(`Failed to save ${entry.key}`)
    }

    ElMessage.success('通知配置保存成功')
  } catch (error) {
    ElMessage.error('保存失败: ' + error.message)
  } finally {
    saving.value = false
  }
}

const sendTestNotification = async (channel) => {
  if (channel === 'wechat' && !form.value.wechatWebhook) {
    ElMessage.warning('请先配置企业微信 Webhook')
    return
  }
  if (channel === 'dingtalk' && !form.value.dingtalkWebhook) {
    ElMessage.warning('请先配置钉钉 Webhook')
    return
  }

  if (channel === 'dingtalk') {
    testingDingtalk.value = true
    try {
      const res = await fetch('/api/maintenance/notification/test', { method: 'POST' })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '请求失败')
      if (data.success) {
        ElMessage.success('测试通知发送成功')
      }
    } catch (error) {
      ElMessage.error('测试失败: ' + error.message)
    } finally {
      testingDingtalk.value = false
    }
  } else {
    // WeChat test — use direct webhook POST
    testingWechat.value = true
    try {
      const res = await fetch('/api/maintenance/system-config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: 'wechat.webhook', value: form.value.wechatWebhook, type: 'string', description: '' }),
      })
      if (!res.ok) throw new Error('保存配置失败')

      // WeChat test: direct POST to webhook
      const webhookRes = await fetch('/api/maintenance/notification/test-wechat', { method: 'POST' })
      const data = await webhookRes.json()
      if (!webhookRes.ok) throw new Error(data.detail || '请求失败')
      if (data.success) {
        ElMessage.success('企业微信测试通知发送成功')
      }
    } catch (error) {
      ElMessage.error('测试失败: ' + error.message)
    } finally {
      testingWechat.value = false
    }
  }
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped lang="scss">
.notification-config {
  padding: 16px;

  .page-header {
    margin-bottom: 16px;

    .page-title {
      font-size: 18px;
      font-weight: 600;
      margin: 0 0 4px 0;
    }

    .page-description {
      font-size: 13px;
      color: #909399;
      margin: 0;
    }
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .form-tip {
    font-size: 12px;
    color: #909399;
    line-height: 1.4;
    margin-top: 4px;
  }
}
</style>
