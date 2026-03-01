<template>
  <div class="user-profile-container">
    <nav class="grok-nav">
      <div class="nav-left">
        <div class="nav-logo">
          <span class="logo-symbol">///</span>
          <span class="logo-text">VOICE ACCESS</span>
        </div>
      </div>
      <div class="nav-center">
        <!-- Optional: Profile specific nav if needed -->
      </div>
      <div class="nav-right">
        <button class="grok-btn-ghost" @click="router.push('/')">HOME</button>
        <button class="grok-btn-action" @click="handleLogout">LOGOUT</button>
      </div>
    </nav>

    <div class="profile-main">
      <div class="me-wrapper">
        <el-card class="me-card">
          <template #header>
            <div class="me-header">
              <div class="me-title">USER PROFILE</div>
              <div class="me-subtitle">Manage your identity and voiceprint</div>
            </div>
          </template>
          
          <div v-if="loading" class="me-loading">
            <span>Loading profile...</span>
          </div>
          <div v-else>
            <div v-if="!user">
              <el-alert type="warning" title="Not logged in" show-icon />
            </div>
            <template v-else>
              <el-tabs v-model="activeTab" class="grok-tabs">
                <el-tab-pane label="IDENTITY" name="basic">
                  <div class="info-grid">
                    <div class="info-item">
                      <label>USERNAME</label>
                      <div class="value">{{ user.username }}</div>
                    </div>
                    <div class="info-item">
                      <label>ROLE</label>
                      <div class="value">{{ user.is_staff ? "Administrator" : "User" }}</div>
                    </div>
                    <div class="info-item">
                      <label>VOICEPRINT STATUS</label>
                      <div class="value">
                        <el-tag :type="user.has_voiceprint ? 'success' : 'info'" effect="dark">
                          {{ user.has_voiceprint ? "ENROLLED" : "NOT ENROLLED" }}
                        </el-tag>
                      </div>
                    </div>
                    <div class="info-item">
                      <label>JOINED</label>
                      <div class="value">{{ user.date_joined }}</div>
                    </div>
                  </div>
                </el-tab-pane>
                
                <el-tab-pane label="VOICEPRINT" name="voice">
                  <div class="voice-section">
                    <div class="section-header">
                      <span>{{ user.has_voiceprint ? "Re-enroll Voiceprint" : "Enroll Voiceprint" }}</span>
                      <el-button
                        v-if="user.has_voiceprint"
                        size="small"
                        type="danger"
                        plain
                        :loading="voiceprintDeleting"
                        @click="confirmDeleteVoiceprint"
                      >
                        DELETE
                      </el-button>
                    </div>
                    
                    <div class="voiceprint-summary" v-if="user.has_voiceprint">
                      <div class="voiceprint-meta">
                        <span>DIM: {{ voiceprintMeta?.embedding_dim || 0 }}</span>
                        <span>SAMPLES: {{ voiceprintMeta?.embedding_count || 0 }}</span>
                        <span>UPDATED: {{ voiceprintMeta?.updated_at || "-" }}</span>
                      </div>
                      <WaveformVisualizer :values="voiceprintPreview" />
                    </div>
                    <div v-else class="empty-state">
                      No voiceprint enrolled. Please record your voice below.
                    </div>

                    <div class="record-box">
                      <VoiceRecorder @enrolled="handleEnrolled" />
                    </div>
                  </div>
                </el-tab-pane>
                
                <el-tab-pane label="LOGS" name="logs">
                  <div class="logs-section">
                    <div class="log-toolbar">
                      <el-date-picker
                        v-model="logDateRange"
                        type="daterange"
                        range-separator="-"
                        start-placeholder="Start"
                        end-placeholder="End"
                        value-format="YYYY-MM-DD"
                        size="small"
                        style="background: transparent;"
                      />
                    </div>
                    <el-table :data="pagedLogs" size="small" style="width: 100%">
                      <el-table-column prop="timestamp" label="TIME" width="180" />
                      <el-table-column prop="score" label="SCORE" width="100">
                        <template #default="{ row }">
                          {{ row.score ? row.score.toFixed(4) : '-' }}
                        </template>
                      </el-table-column>
                      <el-table-column prop="result" label="RESULT" width="100">
                        <template #default="{ row }">
                          <span :class="row.result === 'ACCEPT' ? 'text-success' : 'text-warning'">
                            {{ row.result }}
                          </span>
                        </template>
                      </el-table-column>
                    </el-table>
                    <div class="log-pagination">
                      <el-pagination
                        layout="prev, pager, next"
                        :page-size="logPageSize"
                        :current-page="logPage"
                        :total="filteredLogs.length"
                        @current-change="handleLogPageChange"
                      />
                    </div>
                  </div>
                </el-tab-pane>
              </el-tabs>
            </template>
          </div>
        </el-card>
      </div>
    </div>
  </div>
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
/* Profile Container */
.user-profile-container {
  min-height: 100vh;
  background-color: var(--bg-primary);
  color: var(--text-primary);
  font-family: var(--font-body);
}

.profile-main {
  padding-top: 88px;
  padding-bottom: 48px;
  display: flex;
  justify-content: center;
}

.me-wrapper {
  width: 100%;
  max-width: 1000px;
  padding: 0 24px;
}

/* Card Overrides */
.me-card {
  /* Inherits global el-card styles from theme.css */
  min-height: 600px;
}

.me-header {
  display: flex;
  flex-direction: column;
}

.me-title {
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 0.02em;
}

.me-subtitle {
  font-size: 13px;
  color: var(--text-tertiary);
  margin-top: 4px;
}

.me-loading {
  padding: 40px;
  text-align: center;
  color: var(--text-secondary);
}

/* Info Grid */
.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 32px;
  padding: 24px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-item label {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-tertiary);
  letter-spacing: 0.05em;
}

.info-item .value {
  font-size: 16px;
  color: var(--text-primary);
  font-weight: 500;
}

/* Voice Section */
.voice-section {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-family: var(--font-display);
  font-weight: 600;
  font-size: 16px;
}

.voiceprint-summary {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 16px;
}

.voiceprint-meta {
  display: flex;
  gap: 24px;
  margin-bottom: 16px;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-secondary);
}

.empty-state {
  padding: 40px;
  text-align: center;
  color: var(--text-tertiary);
  border: 1px dashed var(--border-color);
  border-radius: 8px;
}

.record-box {
  margin-top: 16px;
}

/* Logs Section */
.logs-section {
  padding: 24px;
}

.log-toolbar {
  margin-bottom: 16px;
  display: flex;
  justify-content: flex-end;
}

.text-success {
  color: var(--accent-success);
  font-weight: 600;
}

.text-warning {
  color: var(--accent-warning);
  font-weight: 600;
}

.log-pagination {
  margin-top: 24px;
  display: flex;
  justify-content: flex-end;
}
</style>
