<template>
  <el-container style="height: 100vh">
    <el-main>
      <div class="me-wrapper">
        <el-card class="me-card">
          <div class="me-header">
            <div class="me-title">个人主页</div>
          </div>
          <div v-if="loading" class="me-loading">
            <span>加载中...</span>
          </div>
          <div v-else>
            <div v-if="!user">
              <el-alert
                type="warning"
                title="当前未登录，将跳转到登录页面"
                show-icon
              />
            </div>
            <template v-else>
              <el-tabs v-model="activeTab">
                <el-tab-pane label="基础信息" name="basic">
                  <el-descriptions title="基本信息" :column="1" border>
                    <el-descriptions-item label="用户名">
                      {{ user.username }}
                    </el-descriptions-item>
                    <el-descriptions-item label="是否管理员">
                      {{ user.is_staff ? "是" : "否" }}
                    </el-descriptions-item>
                    <el-descriptions-item label="是否已录入声纹">
                      {{ user.has_voiceprint ? "是" : "否" }}
                    </el-descriptions-item>
                    <el-descriptions-item label="注册时间">
                      {{ user.date_joined }}
                    </el-descriptions-item>
                  </el-descriptions>
                </el-tab-pane>
                <el-tab-pane label="声纹管理" name="voice">
                  <el-card class="me-section" shadow="never">
                    <template #header>
                      <div class="section-header">
                        <span>
                          {{ user.has_voiceprint ? "重新录制声纹" : "首次录制声纹" }}
                        </span>
                      </div>
                    </template>
                    <div class="voiceprint-summary">
                      <div class="voiceprint-header">
                        <span>当前声纹</span>
                        <el-button
                          v-if="user.has_voiceprint"
                          size="small"
                          type="danger"
                          plain
                          :loading="voiceprintDeleting"
                          @click="confirmDeleteVoiceprint"
                        >
                          删除声纹
                        </el-button>
                      </div>
                      <div v-if="voiceprintLoading" class="card-subtitle">
                        正在加载声纹概览...
                      </div>
                      <template v-else>
                        <div v-if="!user.has_voiceprint" class="card-subtitle">
                          暂无已注册声纹
                        </div>
                        <div v-else class="voiceprint-body">
                          <div class="voiceprint-meta">
                            <span>特征维度 {{ voiceprintMeta?.embedding_dim || 0 }}</span>
                            <span>样本数 {{ voiceprintMeta?.embedding_count || 0 }}</span>
                            <span>更新时间 {{ voiceprintMeta?.updated_at || "-" }}</span>
                          </div>
                          <!-- 使用新组件展示声纹条形图 -->
                          <WaveformVisualizer :values="voiceprintPreview" />
                        </div>
                      </template>
                    </div>

                    <div class="record-main">
                      <div class="wave-header">
                        <span class="wave-title">录制/上传</span>
                      </div>
                      <!-- 使用新组件处理录音与提交 -->
                      <VoiceRecorder
                        @enrolled="handleEnrolled"
                        :max-records="5"
                      />
                    </div>
                  </el-card>
                </el-tab-pane>
                <el-tab-pane label="验证记录" name="logs">
                  <el-card class="me-section" shadow="never">
                    <template #header>
                      <div class="section-header">
                        <span>最近验证记录</span>
                        <span class="log-hint">仅显示最近 100 条记录</span>
                      </div>
                    </template>
                    <div class="log-toolbar">
                      <el-date-picker
                        v-model="logDateRange"
                        type="daterange"
                        range-separator="至"
                        start-placeholder="开始日期"
                        end-placeholder="结束日期"
                        value-format="YYYY-MM-DD"
                        size="small"
                      />
                    </div>
                    <el-table
                      :data="pagedLogs"
                      size="small"
                      border
                      style="width: 100%"
                    >
                      <el-table-column prop="timestamp" label="时间" width="180" />
                      <el-table-column
                        prop="predicted_user"
                        label="预测用户"
                        width="140"
                      />
                      <el-table-column prop="score" label="得分" width="100" />
                      <el-table-column prop="threshold" label="阈值" width="80" />
                      <el-table-column prop="result" label="结果" width="90" />
                      <el-table-column
                        prop="door_state"
                        label="门状态"
                        width="90"
                      />
                    </el-table>
                    <div class="log-pagination">
                      <el-pagination
                        layout="prev, pager, next, jumper"
                        background
                        :page-size="logPageSize"
                        :current-page="logPage"
                        :total="filteredLogs.length"
                        @current-change="handleLogPageChange"
                      />
                    </div>
                  </el-card>
                </el-tab-pane>
                <el-tab-pane label="账号设置" name="account">
                  <el-card class="me-section" shadow="never">
                    <template #header>
                      <div class="section-header">
                        <span>账号设置</span>
                      </div>
                    </template>
                    <el-descriptions :column="1" border>
                      <el-descriptions-item label="当前账号">
                        {{ user.username }}
                      </el-descriptions-item>
                      <el-descriptions-item label="账号角色">
                        {{ user.is_staff ? "管理员" : "普通用户" }}
                      </el-descriptions-item>
                      <el-descriptions-item label="声纹状态">
                        {{ user.has_voiceprint ? "已录入" : "未录入" }}
                      </el-descriptions-item>
                    </el-descriptions>
                    <div class="record-actions" style="margin-top: 12px">
                      <el-button type="danger" @click="handleLogout">退出登录</el-button>
                    </div>
                  </el-card>
                </el-tab-pane>
              </el-tabs>
            </template>
          </div>
        </el-card>
      </div>
    </el-main>
  </el-container>
</template>

<script setup>
import { onMounted, ref, computed, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  fetchCurrentUser,
  fetchMyLogs,
  setAuthToken,
  fetchMyVoiceprint,
  deleteMyVoiceprint
} from "../api";
import VoiceRecorder from "../components/VoiceRecorder.vue";
import WaveformVisualizer from "../components/WaveformVisualizer.vue";

const router = useRouter();

const user = ref(null);
const logs = ref([]);
const loading = ref(true);
const activeTab = ref("basic");
const logPage = ref(1);
const logPageSize = ref(10);
const logDateRange = ref([]);

const voiceprintLoading = ref(false);
const voiceprintDeleting = ref(false);
const voiceprintPreview = ref([]);
const voiceprintMeta = ref(null);

async function loadUserAndLogs() {
  loading.value = true;
  try {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/");
      return;
    }
    const [userRes, logRes] = await Promise.all([
      fetchCurrentUser(),
      fetchMyLogs()
    ]);
    user.value = userRes.data;
    const data = logRes.data;
    if (Array.isArray(data?.results)) {
      logs.value = data.results;
    } else if (Array.isArray(data)) {
      logs.value = data;
    } else {
      logs.value = [];
    }
    await loadVoiceprintPreview();
  } catch (e) {
    router.push("/");
  } finally {
    loading.value = false;
  }
}

async function loadVoiceprintPreview() {
  voiceprintLoading.value = true;
  try {
    const res = await fetchMyVoiceprint();
    voiceprintMeta.value = res.data || null;
    voiceprintPreview.value = Array.isArray(res.data?.preview) ? res.data.preview : [];
  } catch (e) {
    voiceprintMeta.value = null;
    voiceprintPreview.value = [];
  } finally {
    voiceprintLoading.value = false;
  }
}

const filteredLogs = computed(() => {
  const items = logs.value || [];
  const range = logDateRange.value;
  if (!Array.isArray(range) || range.length !== 2) {
    return items;
  }
  const [startStr, endStr] = range;
  if (!startStr || !endStr) return items;
  const start = new Date(`${startStr}T00:00:00`);
  const end = new Date(`${endStr}T23:59:59`);
  return items.filter((row) => {
    const t = new Date(row.timestamp);
    return t >= start && t <= end;
  });
});

const pagedLogs = computed(() => {
  const start = (logPage.value - 1) * logPageSize.value;
  return filteredLogs.value.slice(start, start + logPageSize.value);
});

watch(logDateRange, () => {
  logPage.value = 1;
});

watch(logs, () => {
  logPage.value = 1;
});

function handleLogPageChange(page) {
  logPage.value = page;
}

async function confirmDeleteVoiceprint() {
  try {
    await ElMessageBox.confirm("确认删除已注册声纹？", "提示", {
      confirmButtonText: "确定",
      cancelButtonText: "取消",
      type: "warning"
    });
  } catch (e) {
    return;
  }
  voiceprintDeleting.value = true;
  try {
    await deleteMyVoiceprint();
    if (user.value) {
      user.value.has_voiceprint = false;
    }
    voiceprintPreview.value = [];
    voiceprintMeta.value = null;
    ElMessage.success("声纹已删除");
  } catch (e) {
    const data = e.response && e.response.data;
    const msg = data && data.error ? data.error : "删除声纹失败";
    ElMessage.error(msg);
  } finally {
    voiceprintDeleting.value = false;
  }
}

function handleLogout() {
  localStorage.removeItem("token");
  setAuthToken(null);
  router.push("/");
}

// Callback from VoiceRecorder
async function handleEnrolled() {
  await loadVoiceprintPreview();
  // Refresh user info to update has_voiceprint status
  const userRes = await fetchCurrentUser();
  user.value = userRes.data;
}

onMounted(() => {
  loadUserAndLogs();
});
</script>

<style scoped>
.me-wrapper {
  min-height: 100vh;
  padding: 24px;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fb;
  background-image: radial-gradient(
      1200px circle at 0% 0%,
      rgba(64, 158, 255, 0.12),
      transparent 45%
    ),
    radial-gradient(
      1200px circle at 100% 0%,
      rgba(103, 232, 169, 0.12),
      transparent 45%
    );
}

.me-card {
  width: 900px;
  border: 1px solid rgba(64, 158, 255, 0.15);
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(6px);
}

.me-title {
  font-size: 20px;
  font-weight: 600;
}

.me-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.me-loading {
  display: flex;
  align-items: center;
  gap: 8px;
}

.me-section {
  margin-top: 16px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.log-hint {
  font-size: 12px;
  color: #909399;
}

.log-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 8px;
}

.log-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.voiceprint-summary {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 12px;
  margin-bottom: 12px;
  background: #fafcff;
}

.voiceprint-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  margin-bottom: 8px;
}

.voiceprint-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.voiceprint-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #606266;
}

.card-subtitle {
  font-size: 13px;
  color: #909399;
  font-style: italic;
}

.record-main {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 12px;
}

.wave-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 12px;
}

.wave-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.record-actions {
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 12px;
}
</style>
