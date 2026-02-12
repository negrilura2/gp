<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getMe, fetchMyLogs } from '../services/api'

const me = ref(null)
const logs = ref([])
const loading = ref(false)

function resultLabel(value) {
  if (value === 'ACCEPT') return '通过'
  if (value === 'REJECT') return '拒绝'
  return value || ''
}

async function loadData() {
  loading.value = true
  try {
    me.value = await getMe()
    const data = await fetchMyLogs()
    logs.value = data.results || data
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<template>
  <div class="card-panel">
    <div class="section-title">个人中心</div>
    <el-skeleton v-if="loading" animated></el-skeleton>
    <div v-else>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="用户名">{{ me?.username }}</el-descriptions-item>
        <el-descriptions-item label="角色">{{ me?.is_staff ? '管理员' : '普通用户' }}</el-descriptions-item>
        <el-descriptions-item label="是否已注册声纹">{{ me?.has_voiceprint ? '是' : '否' }}</el-descriptions-item>
        <el-descriptions-item label="注册时间">{{ me?.date_joined }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <div class="mt-24">
      <div class="section-title">验证历史</div>
      <el-table :data="logs" style="width: 100%">
        <el-table-column prop="timestamp_display" label="时间" width="180" />
        <el-table-column prop="predicted_user" label="预测用户" />
        <el-table-column prop="score" label="分数" />
        <el-table-column prop="result" label="结果">
          <template #default="{ row }">
            <span>{{ resultLabel(row.result) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="client_ip" label="IP" />
      </el-table>
      <el-empty v-if="!logs.length" description="暂无验证记录"></el-empty>
    </div>
  </div>
</template>
