<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>健康快照</span>
          <div>
            <el-button type="success" @click="generateSnapshot">
              <el-icon><Plus /></el-icon>
              生成快照
            </el-button>
            <el-button type="primary" @click="loadSnapshots">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </div>
      </template>

      <!-- 最新快照概览 -->
      <el-alert
        v-if="latestSnapshot"
        title="最新健康快照"
        type="info"
        :closable="false"
        style="margin-bottom: 20px;"
      >
        <template #default>
          <el-descriptions :column="4" size="small">
            <el-descriptions-item label="生成时间">{{ latestSnapshot.summary?.generated_at || '-' }}</el-descriptions-item>
            <el-descriptions-item label="目录总数">{{ latestSnapshot.summary?.total_catalogs || 0 }}</el-descriptions-item>
            <el-descriptions-item label="今日同步">{{ latestSnapshot.summary?.synced_today || 0 }}</el-descriptions-item>
            <el-descriptions-item label="平均质量分">
              <el-tag :type="getQualityType(latestSnapshot.summary?.avg_quality_score)">
                {{ latestSnapshot.summary?.avg_quality_score || 0 }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </template>
      </el-alert>

      <!-- 快照列表 -->
      <el-table :data="snapshots" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="catalog_name" label="目录名称" />
        <el-table-column prop="snapshot_date" label="快照日期" width="120" />
        <el-table-column prop="quality_score" label="质量分" width="100">
          <template #default="{ row }">
            <el-tag :type="getQualityType(row.quality_score)">
              {{ row.quality_score }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="completeness_pct" label="完整度" width="100">
          <template #default="{ row }">
            {{ row.completeness_pct }}%
          </template>
        </el-table-column>
        <el-table-column prop="missing_days" label="缺失天数" width="100" />
        <el-table-column prop="last_sync_status" label="同步状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getSyncStatusType(row.last_sync_status)" size="small">
              {{ getSyncStatusLabel(row.last_sync_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="viewDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadSnapshots"
        @current-change="loadSnapshots"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>

    <!-- 快照详情对话框 -->
    <el-dialog v-model="detailVisible" title="快照详情" width="700px">
      <el-descriptions :column="2" border v-if="currentSnapshot">
        <el-descriptions-item label="快照ID">{{ currentSnapshot.id }}</el-descriptions-item>
        <el-descriptions-item label="目录名称">{{ currentSnapshot.catalog_name }}</el-descriptions-item>
        <el-descriptions-item label="快照日期">{{ currentSnapshot.snapshot_date }}</el-descriptions-item>
        <el-descriptions-item label="质量分">
          <el-tag :type="getQualityType(currentSnapshot.quality_score)">
            {{ currentSnapshot.quality_score }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="完整度">{{ currentSnapshot.completeness_pct }}%</el-descriptions-item>
        <el-descriptions-item label="缺失天数">{{ currentSnapshot.missing_days }}</el-descriptions-item>
        <el-descriptions-item label="一致性">
          {{ getConsistencyLabel(currentSnapshot.consistency_status) }}
        </el-descriptions-item>
        <el-descriptions-item label="同步状态">
          <el-tag :type="getSyncStatusType(currentSnapshot.last_sync_status)" size="small">
            {{ getSyncStatusLabel(currentSnapshot.last_sync_status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="2">
          {{ formatTime(currentSnapshot.created_at) }}
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { healthAPI } from '@/api'

const snapshots = ref([])
const latestSnapshot = ref(null)
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const detailVisible = ref(false)
const currentSnapshot = ref(null)

// Load snapshots
const loadSnapshots = async () => {
  loading.value = true
  try {
    const res = await healthAPI.list({
      page: currentPage.value,
      page_size: pageSize.value
    })
    snapshots.value = res.data || []
    total.value = res.total || 0
  } catch (error) {
    ElMessage.error('加载快照列表失败')
  } finally {
    loading.value = false
  }
}

// Load latest snapshot
const loadLatestSnapshot = async () => {
  try {
    const res = await healthAPI.getLatest()
    const summary = res.data
    latestSnapshot.value = {
      summary: {
        generated_at: summary?.generated_at ? new Date(summary.generated_at).toLocaleString('zh-CN') : '-',
        total_catalogs: summary?.summary?.total_catalogs || 0,
        synced_today: summary?.summary?.synced_today || 0,
        avg_quality_score: summary?.summary?.avg_quality_score || 0,
        catalogs_with_issues: summary?.summary?.catalogs_with_issues || 0
      },
      by_exchange: summary?.by_exchange || {},
      catalogs_with_issues: summary?.catalogs_with_issues || []
    }
  } catch (error) {
    console.error('Failed to load latest snapshot:', error)
  }
}

// Generate new snapshot
const generateSnapshot = async () => {
  try {
    await healthAPI.generate()
    ElMessage.success('快照生成成功')
    loadSnapshots()
    loadLatestSnapshot()
  } catch (error) {
    ElMessage.error('生成快照失败')
  }
}

// View snapshot detail
const viewDetail = (snapshot) => {
  currentSnapshot.value = snapshot
  detailVisible.value = true
}

// Quality tag type
const getQualityType = (score) => {
  if (score >= 90) return 'success'
  if (score >= 70) return ''
  if (score >= 50) return 'warning'
  return 'danger'
}

// Sync status label
const getSyncStatusLabel = (status) => {
  const map = { completed: '已完成', running: '同步中', failed: '失败', never_synced: '未同步', unknown: '未知' }
  return map[status] || status
}

// Sync status tag type
const getSyncStatusType = (status) => {
  const map = { completed: 'success', running: 'warning', failed: 'danger', never_synced: 'info', unknown: 'info' }
  return map[status] || 'info'
}

// Consistency label
const getConsistencyLabel = (status) => {
  const map = { consistent: '一致', minor_issues: '轻微异常', inconsistent: '不一致' }
  return map[status] || status
}

// Format time
const formatTime = (timestamp) => {
  if (!timestamp) return '-'
  const date = new Date(timestamp)
  return date.toLocaleString('zh-CN')
}

onMounted(() => {
  loadSnapshots()
  loadLatestSnapshot()
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
