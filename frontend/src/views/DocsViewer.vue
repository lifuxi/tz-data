<template>
  <div class="docs-viewer">
    <!-- 左侧导航 -->
    <div class="docs-sidebar">
      <el-input
        v-model="searchQuery"
        placeholder="搜索文档..."
        clearable
        prefix-icon="Search"
        size="small"
        class="search-input"
      />
      <div class="doc-list">
        <div
          v-for="doc in filteredDocs"
          :key="doc.path"
          :class="['doc-item', { active: currentDoc === doc.path }]"
          @click="loadDoc(doc)"
        >
          <el-icon><Document /></el-icon>
          <span>{{ doc.title }}</span>
        </div>
      </div>
    </div>

    <!-- 右侧内容 -->
    <div class="docs-content" v-loading="loading">
      <div v-if="!loading && renderedContent" class="markdown-body" v-html="renderedContent" />
      <el-empty v-else-if="!loading" description="选择左侧文档开始阅读" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Document } from '@element-plus/icons-vue'
import MarkdownIt from 'markdown-it'

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  breaks: true,
})

// 文档目录索引
const docIndex = [
  { title: '项目简介', path: 'README.md' },
  { title: '快速入门', path: '01-getting-started.md' },
  { title: '系统架构', path: '02-architecture.md' },
  { title: 'API 接口文档', path: '03-api-reference.md' },
  { title: 'CLI 使用指南', path: '04-cli-guide.md' },
  { title: 'Python SDK', path: '05-python-sdk.md' },
  { title: '数据维护与同步', path: '06-data-maintenance.md' },
  { title: '账单与交易管理', path: '07-bill-management.md' },
  { title: '交易日历与合约管理', path: '08-trade-calendar.md' },
  { title: 'MO 期权数据同步', path: '09-mo-data-sync.md' },
  { title: 'Celery 任务调度', path: '10-celery-tasks.md' },
  { title: '前端页面指南', path: '11-frontend.md' },
  { title: '数据库表结构', path: '12-database-schema.md' },
  { title: '部署与运维', path: '13-deployment.md' },
]

const searchQuery = ref('')
const currentDoc = ref('')
const loading = ref(false)
const renderedContent = ref('')
const rawContent = ref('')

const filteredDocs = computed(() => {
  if (!searchQuery.value) return docIndex
  const q = searchQuery.value.toLowerCase()
  return docIndex.filter(d => d.title.toLowerCase().includes(q))
})

async function loadDoc(doc) {
  if (currentDoc.value === doc.path && rawContent.value) return

  currentDoc.value = doc.path
  loading.value = true
  rawContent.value = ''

  try {
    const response = await fetch(`/docs-api/${doc.path}`)
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    rawContent.value = await response.text()
    renderedContent.value = md.render(rawContent.value)
  } catch (e) {
    renderedContent.value = `<div class="error">文档加载失败：${e.message}</div>`
  } finally {
    loading.value = false
  }
}

// 默认加载第一篇文档
onMounted(() => {
  loadDoc(docIndex[1])
})
</script>

<style scoped lang="scss">
.docs-viewer {
  display: flex;
  height: calc(100vh - 120px);
  gap: 16px;
}

.docs-sidebar {
  width: 240px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 8px;
  padding: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
}

.search-input {
  margin-bottom: 12px;
}

.doc-list {
  overflow-y: auto;
  flex: 1;
}

.doc-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  cursor: pointer;
  border-radius: 6px;
  font-size: 14px;
  color: #333;
  transition: all 0.2s;

  &:hover {
    background-color: #f0f7ff;
    color: #409eff;
  }

  &.active {
    background-color: #ecf5ff;
    color: #409eff;
    font-weight: 500;
  }
}

.docs-content {
  flex: 1;
  overflow-y: auto;
  background: #fff;
  border-radius: 8px;
  padding: 24px 32px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
}

/* Markdown 渲染样式 */
:deep(.markdown-body) {
  max-width: 900px;
  line-height: 1.8;
  color: #333;

  h1, h2, h3, h4, h5, h6 {
    margin-top: 24px;
    margin-bottom: 16px;
    font-weight: 600;
    color: #1a1a1a;
  }

  h1 { font-size: 28px; border-bottom: 2px solid #eaecef; padding-bottom: 8px; }
  h2 { font-size: 22px; border-bottom: 1px solid #eaecef; padding-bottom: 6px; }
  h3 { font-size: 18px; }
  h4 { font-size: 16px; }

  p { margin-bottom: 16px; }

  a { color: #409eff; text-decoration: none; }
  a:hover { text-decoration: underline; }

  code {
    background-color: #f6f8fa;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 14px;
    font-family: 'Cascadia Code', 'Fira Code', Consolas, monospace;
  }

  pre {
    background-color: #f6f8fa;
    padding: 16px;
    border-radius: 8px;
    overflow-x: auto;
    margin-bottom: 16px;

    code {
      background: none;
      padding: 0;
      font-size: 13px;
    }
  }

  table {
    border-collapse: collapse;
    width: 100%;
    margin-bottom: 16px;
    font-size: 14px;

    th, td {
      border: 1px solid #eaecef;
      padding: 8px 12px;
      text-align: left;
    }

    th {
      background-color: #f6f8fa;
      font-weight: 600;
    }

    tr:nth-child(even) {
      background-color: #fafbfc;
    }
  }

  blockquote {
    border-left: 4px solid #409eff;
    padding: 8px 16px;
    margin: 16px 0;
    background-color: #f0f7ff;
    border-radius: 0 4px 4px 0;
    color: #555;
  }

  ul, ol {
    padding-left: 24px;
    margin-bottom: 16px;
  }

  li {
    margin-bottom: 4px;
  }

  hr {
    border: none;
    border-top: 1px solid #eaecef;
    margin: 24px 0;
  }

  img {
    max-width: 100%;
    border-radius: 4px;
  }

  .error {
    color: #f56c6c;
    font-size: 14px;
    padding: 20px;
    text-align: center;
  }
}
</style>
