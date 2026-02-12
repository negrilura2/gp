<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick, watch, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { fetchLogs, fetchEnrollLogs, fetchUsers, deleteUser, fetchStats, fetchRocImage, fetchVoiceTemplates, deleteVoiceTemplate } from '../services/api'

const logs = ref([])
const enrollLogs = ref([])
const users = ref([])
const voiceTemplates = ref([])
const stats = ref(null)
const loading = ref(false)
const chartRef = ref(null)
const rocUrl = ref('')
const chartInstance = ref(null)
const logFilters = reactive({
  result: '',
  user: ''
})

function resultLabel(value) {
  if (value === 'ACCEPT') return '通过'
  if (value === 'REJECT') return '拒绝'
  return value || ''
}

function booleanLabel(value) {
  return value ? '成功' : '失败'
}
const resizeHandler = () => {
  if (chartInstance.value) {
    chartInstance.value.resize()
  }
}

function formatDate(date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function buildDailySeries() {
  const daily = stats.value?.daily || []
  if (daily.length) {
    return {
      dates: daily.map((d) => d.date),
      successRates: daily.map((d) => d.success_rate || 0)
    }
  }
  const dates = []
  const successRates = []
  const today = new Date()
  for (let i = 6; i >= 0; i -= 1) {
    const d = new Date(today)
    d.setDate(today.getDate() - i)
    dates.push(formatDate(d))
    successRates.push(0)
  }
  return { dates, successRates }
}

function renderChart() {
  if (!chartRef.value) return
  if (!chartInstance.value) {
    chartInstance.value = echarts.init(chartRef.value)
  }
  const { dates, successRates } = buildDailySeries()
  chartInstance.value.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['成功率'] },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', name: '成功率', min: 0, max: 1 },
    series: [
      { name: '成功率', type: 'line', data: successRates }
    ]
  })
  chartInstance.value.resize()
}

async function loadData() {
  loading.value = true
  try {
    const results = await Promise.allSettled([
      fetchLogs(logFilters),
      fetchEnrollLogs(),
      fetchUsers(),
      fetchStats(),
      fetchVoiceTemplates()
    ])
    const [logsRes, enrollRes, usersRes, statsRes, templatesRes] = results
    logs.value = logsRes.status === 'fulfilled' ? (logsRes.value.results || logsRes.value) : []
    enrollLogs.value = enrollRes.status === 'fulfilled' ? (enrollRes.value.results || enrollRes.value) : []
    users.value = usersRes.status === 'fulfilled' ? (usersRes.value.results || usersRes.value) : []
    stats.value = statsRes.status === 'fulfilled' ? statsRes.value : { daily: [] }
    voiceTemplates.value = templatesRes.status === 'fulfilled' ? (templatesRes.value.results || templatesRes.value) : []
    if (results.some((r) => r.status === 'rejected')) {
      ElMessage.error('部分数据加载失败')
    }
    try {
      if (rocUrl.value) {
        URL.revokeObjectURL(rocUrl.value)
      }
      rocUrl.value = await fetchRocImage()
    } catch (e) {
      rocUrl.value = ''
    }
    await nextTick()
    renderChart()
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function handleDelete(user) {
  loading.value = true
  try {
    await deleteUser(user.id)
    ElMessage.success('已删除用户')
    await loadData()
  } catch (e) {
    ElMessage.error(e.message || '删除失败')
  } finally {
    loading.value = false
  }
}

async function handleDeleteTemplate(item) {
  loading.value = true
  try {
    await deleteVoiceTemplate(item.id)
    ElMessage.success('已删除声纹模板')
    await loadData()
  } catch (e) {
    ElMessage.error(e.message || '删除失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
onMounted(() => {
  window.addEventListener('resize', resizeHandler)
})
watch(
  () => stats.value,
  async () => {
    await nextTick()
    renderChart()
  },
  { deep: true }
)
onBeforeUnmount(() => {
  if (rocUrl.value) {
    URL.revokeObjectURL(rocUrl.value)
  }
  if (chartInstance.value) {
    chartInstance.value.dispose()
  }
  window.removeEventListener('resize', resizeHandler)
})
</script>

<template>
  <div class="card-panel">
    <div style="display: flex; align-items: center; justify-content: space-between;">
      <div class="section-title">管理员控制台</div>
      <el-button size="small" @click="loadData">刷新</el-button>
    </div>
    <el-skeleton v-if="loading" animated></el-skeleton>
    <div v-else>
      <el-row :gutter="16">
        <el-col :span="8">
          <div class="card-panel">
            <div class="section-title">用户统计</div>
            <div>总用户：{{ stats?.users?.total || 0 }}</div>
            <div>已注册：{{ stats?.users?.enrolled || 0 }}</div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="card-panel">
            <div class="section-title">结果分布</div>
            <div>通过：{{ stats?.result_distribution?.ACCEPT || 0 }}</div>
            <div>拒绝：{{ stats?.result_distribution?.REJECT || 0 }}</div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="card-panel">
            <div class="section-title">ROC 图</div>
            <el-image v-if="rocUrl" :src="rocUrl" :preview-src-list="[rocUrl]" fit="contain" style="width: 100%; height: 240px;" />
            <el-empty v-else description="暂无 ROC 图"></el-empty>
          </div>
        </el-col>
      </el-row>

      <div class="mt-24 card-panel">
        <div class="section-title">识别成功率统计</div>
        <div ref="chartRef" style="width: 100%; height: 320px;"></div>
      </div>

      <div class="mt-24">
        <div class="section-title">用户管理</div>
        <el-table :data="users" style="width: 100%">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column prop="username" label="用户名" />
          <el-table-column prop="is_staff" label="管理员" />
          <el-table-column prop="has_voiceprint" label="已注册" />
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="mt-24">
        <div class="section-title">声纹管理</div>
        <el-table :data="voiceTemplates" style="width: 100%">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column prop="username" label="用户" />
          <el-table-column prop="embedding_count" label="语音条数" width="100" />
          <el-table-column prop="template_path" label="模板路径" />
          <el-table-column prop="created_at_display" label="创建时间" width="180" />
          <el-table-column prop="updated_at_display" label="更新时间" width="180" />
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button size="small" type="danger" @click="handleDeleteTemplate(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="mt-24">
        <div class="section-title">验证日志</div>
        <div class="form-row mt-12">
          <el-input v-model="logFilters.user" placeholder="按预测用户筛选" style="max-width: 220px;" />
          <el-select v-model="logFilters.result" placeholder="结果" style="width: 140px;">
            <el-option label="全部" value="" />
            <el-option label="通过" value="ACCEPT" />
            <el-option label="拒绝" value="REJECT" />
          </el-select>
          <el-button type="primary" @click="loadData">查询</el-button>
        </div>
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
      </div>

      <div class="mt-24">
        <div class="section-title">注册日志</div>
        <el-table :data="enrollLogs" style="width: 100%">
          <el-table-column prop="timestamp_display" label="时间" width="180" />
          <el-table-column prop="username" label="用户" />
          <el-table-column prop="wav_count" label="音频数" />
          <el-table-column prop="success" label="成功">
            <template #default="{ row }">
              <span>{{ booleanLabel(row.success) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="client_ip" label="IP" />
          <el-table-column prop="error_msg" label="错误" />
        </el-table>
      </div>
    </div>
  </div>
</template>
