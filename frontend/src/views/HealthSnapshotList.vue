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
            <el-descriptions-item label="生成时间">{{ formatTime(latestSnapshot.generated_at) }}</el-descriptions-item>
            <el-descriptions-item label="目录总数">{{ latestSnapshot.summary?.total_catalogs || 0 }}</el-descriptions-item>
            <el-descriptions-item label="今日同步">{{ latestSnapshot.summary?.synced_today || 0 }}</el-descriptions-item>
            <el-descriptions-item label="平均质量分">{{ latestSnapshot.summary?.avg_quality_score || 0 }}</el-descriptions-item>
          </el-descriptions>
        </template>
      </el-alert>
      
      <!-- 快照列表 -->
      <el-table :data="snapshots" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="generated_at" label="生成时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.generated_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="total_catalogs" label="目录总数" width="120" />
        <el-table-column prop="synced_today" label="今日同步" width="120" />
        <el-table-column prop="avg_quality_score" label="平均质量分" width="120">
          <template #default="{ row }">
            <el-tag :type="getQualityType(row.avg_quality_score)">
              {{ row.avg_quality_score }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="catalogs_with_issues" label="异常目录" width="120">
          <template #default="{ row }">
            <el-badge :value="row.catalogs_with_issues || 0" :max="99" type="danger" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="viewDetail(row)">查看详情</el-button>
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
    <el-dialog v-model="detailVisible" title="快照详情" width="800px">
      <el-tabs v-if="currentSnapshot">
        <el-tab-pane label="概览">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="快照ID">{{ currentSnapshot.id }}</el-descriptions-item>
            <el-descriptions-item label="生成时间">{{ formatTime(currentSnapshot.generated_at) }}</el-descriptions-item>
            <el-descriptions-item label="目录总数">{{ currentSnapshot.summary?.total_catalogs }}</el-descriptions-item>
            <el-descriptions-item label="启用目录">{{ currentSnapshot.summary?.enabled_catalogs }}</el-descriptions-item>
            <el-descriptions-item label="今日同步">{{ currentSnapshot.summary?.synced_today }}</el-descriptions-item>
            <el-descriptions-item label="平均质量分">{{ currentSnapshot.summary?.avg_quality_score }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>
        
        <el-tab-pane label="按交易所">
          <el-table :data="Object.values(currentSnapshot.by_exchange || {})" stripe>
            <el-table-column prop="exchange_code" label="交易所" />
            <el-table-column prop="catalog_count" label="目录数" />
            <el-table-column prop="avg_quality" label="平均质量分">
              <template #default="{ row }">
                <el-tag :type="getQualityType(row.avg_quality)">{{ row.avg_quality }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="synced_count" label="今日同步" />
          </el-table>
        </el-tab-pane>
        
        <el-tab-pane label="异常目录">
          <el-empty v-if="!currentSnapshot.catalogs_with_issues || currentSnapshot.catalogs_with_issues.length === 0" description="暂无异常目录" />
          <el-table v-else :data="currentSnapshot.catalogs_with_issues" stripe>
            <el-table-column prop="catalog_name" label="目录名称" />
            <el-table-column prop="quality_score" label="质量分" />
            <el-table-column prop="issues" label="问题描述" />
          </el-table>
        </el-tab-pane>
      </el-tabs>
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
    latestSnapshot.value = res.data
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

// Get quality tag type
const getQualityType = (score) => {
  if (score >= 90) return 'success'
  if (score >= 70) return ''
  if (score >= 50) return 'warning'
  return 'danger'
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
