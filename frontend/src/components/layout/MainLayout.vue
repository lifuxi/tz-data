<template>
  <el-container class="layout-container">
    <!-- Sidebar -->
    <el-aside width="220px" class="sidebar">
      <div class="logo">
        <h2>📊 tz-data</h2>
        <p>数据维护系统</p>
      </div>
      
      <el-menu
        :default-active="activeMenu"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
      >
        <template v-for="group in groupedMenuRoutes" :key="group.name">
          <el-menu-item-group :title="group.name">
            <el-menu-item
              v-for="route in group.items"
              :key="route.path"
              :index="route.path"
            >
              <el-icon><component :is="route.meta.icon" /></el-icon>
              <span>{{ route.meta.title }}</span>
            </el-menu-item>
          </el-menu-item-group>
        </template>
      </el-menu>
    </el-aside>

    <!-- Main Content -->
    <el-container>
      <!-- Header -->
      <el-header class="header">
        <div class="header-left">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item>{{ currentRoute.meta.title }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        
        <div class="header-right">
          <el-badge :value="alertCount" class="alert-badge">
            <el-button type="link" @click="goToAlerts">
              <el-icon><Bell /></el-icon>
            </el-button>
          </el-badge>
          
          <el-dropdown>
            <span class="user-info">
              <el-icon><User /></el-icon>
              <span>管理员</span>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item>个人设置</el-dropdown-item>
                <el-dropdown-item divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- Content -->
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Bell, User } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

// Menu routes sorted by order
const menuRoutes = computed(() => {
  const routes = route.matched[0]?.children?.filter(r => r.meta && r.meta.title) || []
  return routes.sort((a, b) => (a.meta.order || 999) - (b.meta.order || 999))
})

// Grouped menu routes
const groupedMenuRoutes = computed(() => {
  const groups = []
  let currentGroup = null

  for (const r of menuRoutes.value) {
    const groupName = r.meta.group || '其他'
    if (!currentGroup || currentGroup.name !== groupName) {
      currentGroup = { name: groupName, items: [] }
      groups.push(currentGroup)
    }
    currentGroup.items.push(r)
  }

  return groups
})

// Active menu
const activeMenu = computed(() => route.path)

// Current route
const currentRoute = computed(() => route)

// Alert count (mock)
const alertCount = computed(() => 3)

// Navigate to alerts
const goToAlerts = () => {
  router.push('/alerts')
}
</script>

<style scoped lang="scss">
.layout-container {
  height: 100vh;
}

.sidebar {
  background-color: #304156;
  
  .logo {
    padding: 20px;
    text-align: center;
    color: #fff;
    border-bottom: 1px solid #3d4a5f;
    
    h2 {
      margin: 0;
      font-size: 20px;
    }
    
    p {
      margin: 5px 0 0;
      font-size: 12px;
      color: #bfcbd9;
    }
  }
  
  .el-menu {
    border-right: none;
  }
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #fff;
  border-bottom: 1px solid #e6e6e6;
  padding: 0 20px;
  
  .header-right {
    display: flex;
    align-items: center;
    gap: 20px;
    
    .alert-badge {
      cursor: pointer;
    }
    
    .user-info {
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      
      &:hover {
        color: #409EFF;
      }
    }
  }
}

.main-content {
  background-color: #f0f2f5;
  padding: 20px;
}
</style>
