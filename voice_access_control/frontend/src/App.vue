<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getAuth, clearAuth } from './services/auth'
import { getMe } from './services/api'

const router = useRouter()
const route = useRoute()
const auth = ref(getAuth())
const currentUser = ref(null)
const loading = ref(false)

async function refreshUser() {
  auth.value = getAuth()
  if (!auth.value?.token) {
    currentUser.value = null
    return
  }
  loading.value = true
  try {
    currentUser.value = await getMe()
  } catch (e) {
    ElMessage.error(e.message || '获取用户信息失败')
  } finally {
    loading.value = false
  }
}

function logout() {
  clearAuth()
  auth.value = null
  currentUser.value = null
  router.push('/login')
}

function onAuthChanged() {
  refreshUser()
}

onMounted(() => {
  refreshUser()
  window.addEventListener('auth-changed', onAuthChanged)
})

onBeforeUnmount(() => {
  window.removeEventListener('auth-changed', onAuthChanged)
})
</script>

<template>
  <el-container class="app-shell">
    <el-aside width="220px" class="app-aside">
      <div class="brand">Voice Access</div>
      <el-menu :default-active="route.path" router class="menu">
        <el-menu-item index="/verify">声纹验证</el-menu-item>
        <el-menu-item index="/enroll" v-if="auth?.token">声纹注册</el-menu-item>
        <el-menu-item index="/profile" v-if="auth?.token">个人中心</el-menu-item>
        <el-menu-item index="/admin" v-if="auth?.is_staff">管理后台</el-menu-item>
        <el-menu-item index="/login" v-if="!auth?.token">登录/注册</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="app-header">
        <div class="header-left">
          <span v-if="loading">加载中...</span>
          <span v-else-if="currentUser">你好，{{ currentUser.username }}</span>
          <span v-else>未登录</span>
        </div>
        <div class="header-right">
          <el-button v-if="auth?.token" type="primary" plain @click="logout">退出登录</el-button>
          <el-button v-else type="primary" @click="router.push('/login')">登录/注册</el-button>
        </div>
      </el-header>
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>
