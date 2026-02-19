<template>
  <el-container class="dashboard-container" style="height: 100vh">
    <el-header height="60px">
      <div class="header">
        <div class="title">声纹门禁系统 · 后台仪表盘</div>
      </div>
    </el-header>
    <el-main class="dashboard-main">
      <el-scrollbar style="height: 100%">
        <div class="dashboard-content">
          <div class="dashboard-hero">
            <div class="hero-text">
              <div class="hero-title">管理员控制台</div>
              <div class="hero-subtitle">
                统一查看验证趋势、阈值策略与系统运行状态
              </div>
            </div>
            <div class="hero-actions">
              <el-button type="primary" @click="refreshAll" :loading="loading">
                刷新数据
              </el-button>
              <el-button plain @click="handleLogout">退出登录</el-button>
            </div>
          </div>
          <el-tabs
            v-model="activeTab"
            class="apple-tabs"
            @tab-change="handleTabChange"
          >
            <el-tab-pane label="概览" name="overview">
              <AdminOverviewTab
                :summary-cards="summaryCards"
                :line-chart-ref="setLineChartRef"
                :pie-chart-ref="setPieChartRef"
              />
            </el-tab-pane>
            <el-tab-pane label="验证日志" name="logs">
              <AdminLogsTab
                :logs="logs"
                :log-total="logTotal"
                :log-page="logPage"
                :log-page-size="logPageSize"
                :log-table-height="logTableHeight"
                :log-table-wrap-ref="setLogTableWrapRef"
                :log-filters="logFilters"
                :format-date-time="formatDateTime"
                :on-log-search="handleLogSearch"
                :on-log-reset="handleLogReset"
                :on-delete-selected-logs="handleDeleteSelectedLogs"
                :on-log-selection-change="handleLogSelectionChange"
                :on-log-page-change="handleLogPageChange"
              />
            </el-tab-pane>
            <el-tab-pane label="用户管理" name="users">
              <AdminUsersTab
                :users="users"
                :users-total="usersTotal"
                :users-page="usersPage"
                :users-page-size="usersPageSize"
                :users-loading="usersLoading"
                :user-filters="userFilters"
                :selected-user-ids="selectedUserIds"
                :format-date-time="formatDateTime"
                :on-user-refresh="handleUserRefresh"
                :on-create-user="openCreateUser"
                :on-user-search="handleUserSearch"
                :on-user-reset="handleUserReset"
                :on-batch-toggle="handleBatchToggle"
                :on-batch-clear-voiceprint="handleBatchClearVoiceprint"
                :on-batch-reset-password="openBatchResetPassword"
                :on-batch-delete="handleBatchDelete"
                :on-user-selection-change="handleUserSelectionChange"
                :on-user-page-change="handleUserPageChange"
                :on-edit-user="openEditUser"
                :on-reset-password="openResetPassword"
                :on-reset-voiceprint="handleResetVoiceprint"
                :on-delete-user="handleDeleteUser"
              />
            </el-tab-pane>
            <el-tab-pane label="模型评估" name="model">
              <AdminModelTab
                :model-metrics="modelMetrics"
                :model-metrics-model="modelMetricsModel"
                :model-current="modelCurrent"
                :model-evaluating="modelEvaluating"
                :model-metrics-loading="modelMetricsLoading"
                :model-metrics-error="modelMetricsError"
                :roc-derived="rocDerived"
                :format-metric="formatMetric"
                :format-percent="formatPercent"
                :roc-chart-ref="setRocChartRef"
                :model-switching="modelSwitching"
                :model-list="modelList"
                :model-target="modelTarget"
                :active-eval="activeEval"
                :active-eval-has-data="activeEvalHasData"
                :active-eval-key="activeEvalKey"
                :eval-items="evalItems"
                :eval-detail-chart-ref="setEvalDetailChartRef"
                :set-eval-thumb-ref="setEvalThumbRef"
                :has-eval-data="hasEvalData"
                :on-load-model-metrics="loadModelMetrics"
                :on-model-evaluate="handleModelEvaluate"
                :on-load-model-list="loadModelList"
                :on-model-target-change="handleModelTargetChange"
                :on-model-switch="handleModelSwitch"
                :on-eval-collapse="handleEvalCollapse"
                :on-eval-card-click="handleEvalCardClick"
              />
            </el-tab-pane>
            <el-tab-pane label="系统设置" name="settings">
              <AdminSettingsTab
                :admin-access-logs="adminAccessLogs"
                :admin-access-logs-loading="adminAccessLogsLoading"
                :format-date-time="formatDateTime"
                :threshold="threshold"
                :threshold-draft="thresholdDraft"
                :saving-threshold="savingThreshold"
                :maintenance-logs-loading="maintenanceLogsLoading"
                :maintenance-models-loading="maintenanceModelsLoading"
                :maintenance-cache-loading="maintenanceCacheLoading"
                :maintenance-logs-result="maintenanceLogsResult"
                :maintenance-models-result="maintenanceModelsResult"
                :maintenance-cache-result="maintenanceCacheResult"
                :on-load-admin-access-logs="loadAdminAccessLogs"
                :on-threshold-draft-change="handleThresholdDraftChange"
                :on-save-threshold="handleSaveThreshold"
                :on-clean-verify-logs="handleCleanVerifyLogs"
                :on-check-models="handleCheckModels"
                :on-clean-cache="handleCleanCache"
              />
            </el-tab-pane>
            <el-tab-pane label="管理员列表" name="admins">
              <AdminAdminsTab
                :admin-list-unlocked="adminListUnlocked"
                :admin-filters="adminFilters"
                :selected-admin-ids="selectedAdminIds"
                :admin-list="adminList"
                :admin-list-loading="adminListLoading"
                :format-date-time="formatDateTime"
                :on-admin-list-refresh="handleAdminListRefresh"
                :on-create-admin="openCreateAdmin"
                :on-admin-search="handleAdminSearch"
                :on-admin-reset="handleAdminReset"
                :on-admin-batch-toggle="handleAdminBatchToggle"
                :on-admin-batch-reset-password="openAdminBatchResetPassword"
                :on-admin-selection-change="handleAdminSelectionChange"
                :on-edit-admin="openEditAdmin"
                :on-reset-admin-password="openAdminResetPassword"
                :on-admin-toggle="handleAdminToggle"
              />
            </el-tab-pane>
          </el-tabs>
          <el-dialog
            v-model="userDialogVisible"
            :title="userDialogTitle"
            width="420px"
          >
            <el-form :model="userForm" label-width="90px">
              <el-form-item label="用户名" v-if="userDialogMode === 'create'">
                <el-input v-model="userForm.username" autocomplete="off" />
              </el-form-item>
              <el-form-item label="用户名" v-else>
                <el-input v-model="userForm.username" disabled />
              </el-form-item>
              <el-form-item label="姓名">
                <el-input v-model="userForm.full_name" autocomplete="off" />
              </el-form-item>
              <el-form-item label="联系电话">
                <el-input v-model="userForm.phone" autocomplete="off" />
              </el-form-item>
              <el-form-item label="邮箱">
                <el-input v-model="userForm.email" autocomplete="off" />
              </el-form-item>
              <el-form-item label="部门">
                <el-input v-model="userForm.department" autocomplete="off" />
              </el-form-item>
              <el-form-item label="状态">
                <el-switch
                  v-model="userForm.is_active"
                  active-text="启用"
                  inactive-text="禁用"
                />
              </el-form-item>
              <el-form-item label="密码" v-if="userDialogMode === 'create'">
                <el-input
                  v-model="userForm.password"
                  type="password"
                  show-password
                  autocomplete="new-password"
                />
              </el-form-item>
            </el-form>
            <template #footer>
              <el-button @click="userDialogVisible = false">取消</el-button>
              <el-button type="primary" :loading="userSaving" @click="handleUserSubmit">
                保存
              </el-button>
            </template>
          </el-dialog>
          <el-dialog
            v-model="passwordDialogVisible"
            title="重置密码"
            width="420px"
          >
            <el-form :model="passwordForm" label-width="90px">
              <el-form-item label="新密码">
                <el-input
                  v-model="passwordForm.password"
                  type="password"
                  show-password
                  autocomplete="new-password"
                />
              </el-form-item>
            </el-form>
            <template #footer>
              <el-button @click="passwordDialogVisible = false">取消</el-button>
              <el-button
                type="primary"
                :loading="passwordSaving"
                @click="handlePasswordSubmit"
              >
                确认
              </el-button>
            </template>
          </el-dialog>
          <el-dialog
            v-model="batchPasswordDialogVisible"
            title="批量重置密码"
            width="420px"
          >
            <el-form :model="batchPasswordForm" label-width="90px">
              <el-form-item label="新密码">
                <el-input
                  v-model="batchPasswordForm.password"
                  type="password"
                  show-password
                  autocomplete="new-password"
                />
              </el-form-item>
            </el-form>
            <template #footer>
              <el-button @click="batchPasswordDialogVisible = false">取消</el-button>
              <el-button
                type="primary"
                :loading="batchPasswordSaving"
                @click="handleBatchPasswordSubmit"
              >
                确认
              </el-button>
            </template>
          </el-dialog>
          <el-dialog
            v-model="adminDialogVisible"
            :title="adminDialogTitle"
            width="420px"
          >
            <el-form :model="adminForm" label-width="90px">
              <el-form-item label="用户名" v-if="adminDialogMode === 'create'">
                <el-input v-model="adminForm.username" autocomplete="off" />
              </el-form-item>
              <el-form-item label="用户名" v-else>
                <el-input v-model="adminForm.username" disabled />
              </el-form-item>
              <el-form-item label="姓名">
                <el-input v-model="adminForm.full_name" autocomplete="off" />
              </el-form-item>
              <el-form-item label="联系电话">
                <el-input v-model="adminForm.phone" autocomplete="off" />
              </el-form-item>
              <el-form-item label="邮箱">
                <el-input v-model="adminForm.email" autocomplete="off" />
              </el-form-item>
              <el-form-item label="部门">
                <el-input v-model="adminForm.department" autocomplete="off" />
              </el-form-item>
              <el-form-item label="状态">
                <el-switch
                  v-model="adminForm.is_active"
                  active-text="启用"
                  inactive-text="禁用"
                />
              </el-form-item>
              <el-form-item label="密码" v-if="adminDialogMode === 'create'">
                <el-input
                  v-model="adminForm.password"
                  type="password"
                  show-password
                  autocomplete="new-password"
                />
              </el-form-item>
            </el-form>
            <template #footer>
              <el-button @click="adminDialogVisible = false">取消</el-button>
              <el-button type="primary" :loading="adminSaving" @click="handleAdminSubmit">
                保存
              </el-button>
            </template>
          </el-dialog>
          <el-dialog
            v-model="adminPasswordDialogVisible"
            title="重置管理员密码"
            width="420px"
          >
            <el-form :model="adminPasswordForm" label-width="90px">
              <el-form-item label="新密码">
                <el-input
                  v-model="adminPasswordForm.password"
                  type="password"
                  show-password
                  autocomplete="new-password"
                />
              </el-form-item>
            </el-form>
            <template #footer>
              <el-button @click="adminPasswordDialogVisible = false">取消</el-button>
              <el-button
                type="primary"
                :loading="adminPasswordSaving"
                @click="handleAdminPasswordSubmit"
              >
                确认
              </el-button>
            </template>
          </el-dialog>
          <el-dialog
            v-model="adminBatchPasswordDialogVisible"
            title="批量重置管理员密码"
            width="420px"
          >
            <el-form :model="adminBatchPasswordForm" label-width="90px">
              <el-form-item label="新密码">
                <el-input
                  v-model="adminBatchPasswordForm.password"
                  type="password"
                  show-password
                  autocomplete="new-password"
                />
              </el-form-item>
            </el-form>
            <template #footer>
              <el-button @click="adminBatchPasswordDialogVisible = false">取消</el-button>
              <el-button
                type="primary"
                :loading="adminBatchPasswordSaving"
                @click="handleAdminBatchPasswordSubmit"
              >
                确认
              </el-button>
            </template>
          </el-dialog>
          <el-dialog
            v-model="adminAccessDialogVisible"
            title="高层密码验证"
            width="420px"
          >
            <el-form :model="adminAccessForm" label-width="90px">
              <el-form-item label="高层密码">
                <el-input
                  v-model="adminAccessForm.secret_password"
                  type="password"
                  show-password
                  autocomplete="current-password"
                />
              </el-form-item>
            </el-form>
            <template #footer>
              <el-button @click="adminAccessDialogVisible = false">取消</el-button>
              <el-button
                type="primary"
                :loading="adminListLoading"
                @click="handleAdminAccessSubmit"
              >
                确认
              </el-button>
            </template>
          </el-dialog>
        </div>
      </el-scrollbar>
    </el-main>
  </el-container>
</template>

<script setup>
import { onMounted, onUnmounted, ref, computed, nextTick } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import * as echarts from "echarts";
import AdminOverviewTab from "./admin/AdminOverviewTab.vue";
import AdminLogsTab from "./admin/AdminLogsTab.vue";
import AdminUsersTab from "./admin/AdminUsersTab.vue";
import AdminModelTab from "./admin/AdminModelTab.vue";
import AdminSettingsTab from "./admin/AdminSettingsTab.vue";
import AdminAdminsTab from "./admin/AdminAdminsTab.vue";
import {
  fetchDashboard,
  fetchStatsEcharts,
  fetchLogs,
  deleteLogs,
  fetchThreshold,
  updateThreshold,
  fetchCurrentUser,
  fetchUsers,
  createUser,
  updateUser,
  deleteUser,
  resetUserPassword,
  resetUserVoiceprint,
  fetchAdminList,
  fetchAdminAccessLogs,
  fetchAdminUsers,
  createAdminUser,
  updateAdminUser,
  bulkUpdateAdminStatus,
  bulkResetAdminPassword,
  fetchRocMetrics,
  evaluateRocMetrics,
  fetchRocEvaluateStatus,
  fetchModels,
  switchModel,
  cleanVerifyLogs,
  checkModelFiles,
  cleanCacheFiles,
  setAuthToken
} from "../api";

const router = useRouter();

const loading = ref(false);
const summary = ref(null);
const stats = ref(null);
const logs = ref([]);
const logTotal = ref(0);
const logPage = ref(1);
const logPageSize = ref(12);
const logTableHeight = ref(520);
const logTableWrapRef = ref(null);
const setLogTableWrapRef = (el) => {
  logTableWrapRef.value = el;
};
const logSelectedIds = ref([]);
const logFilters = ref({
  actor: "",
  predicted: "",
  result: "",
  dates: []
});

const currentUser = ref(null);
const users = ref([]);
const usersTotal = ref(0);
const usersPage = ref(1);
const usersPageSize = ref(20);
const usersLoading = ref(false);
const usersLoaded = ref(false);
const selectedUserIds = ref([]);
const userFilters = ref({
  q: "",
  is_active: "",
  has_voiceprint: ""
});
const userDialogVisible = ref(false);
const userDialogMode = ref("create");
const userSaving = ref(false);
const userForm = ref({
  username: "",
  password: "",
  full_name: "",
  phone: "",
  email: "",
  department: "",
  is_active: true
});
const passwordDialogVisible = ref(false);
const passwordSaving = ref(false);
const passwordForm = ref({ password: "" });
const passwordTarget = ref(null);
const batchPasswordDialogVisible = ref(false);
const batchPasswordSaving = ref(false);
const batchPasswordForm = ref({ password: "" });

const adminAccessDialogVisible = ref(false);
const adminAccessForm = ref({ secret_password: "" });
const adminListUnlocked = ref(false);
const adminListLoading = ref(false);
const adminList = ref([]);
const adminFilters = ref({
  q: "",
  is_active: ""
});
const selectedAdminIds = ref([]);
const adminDialogVisible = ref(false);
const adminDialogMode = ref("create");
const adminSaving = ref(false);
const adminForm = ref({
  username: "",
  password: "",
  full_name: "",
  phone: "",
  email: "",
  department: "",
  is_active: true
});
const adminPasswordDialogVisible = ref(false);
const adminPasswordSaving = ref(false);
const adminPasswordForm = ref({ password: "" });
const adminPasswordTarget = ref(null);
const adminBatchPasswordDialogVisible = ref(false);
const adminBatchPasswordSaving = ref(false);
const adminBatchPasswordForm = ref({ password: "" });
const adminAccessLogs = ref([]);
const adminAccessLogsLoading = ref(false);
const maintenanceLogsLoading = ref(false);
const maintenanceModelsLoading = ref(false);
const maintenanceCacheLoading = ref(false);
const maintenanceLogsResult = ref(null);
const maintenanceModelsResult = ref(null);
const maintenanceCacheResult = ref(null);

const modelMetrics = ref({
  auc: null,
  eer: null,
  threshold: null,
  threshold_eer: null,
  threshold_mindcf: null,
  mindcf: null,
  p_target: null,
  c_miss: null,
  c_fa: null,
  threshold_default: null,
  threshold_diff: null,
  fpr: null,
  tpr: null,
  thresholds: null,
  det: null,
  mindcf_data: null,
  score_dist: null,
  calibration: null
});
const modelMetricsError = ref("");
const modelMetricsLoading = ref(false);
const modelEvaluating = ref(false);
const modelEvaluatingStatus = ref("");
const modelMetricsModel = ref("");
const modelList = ref([]);
const modelCurrent = ref("");
const modelTarget = ref("");
const modelSwitching = ref(false);
const rocChartRef = ref(null);
let rocChart;
let evalPollingTimer = null;

const threshold = ref(0.7);
const thresholdDraft = ref(0.7);
const savingThreshold = ref(false);
const activeTab = ref("overview");

const lineChartRef = ref(null);
const pieChartRef = ref(null);
let lineChart;
let pieChart;

const setLineChartRef = (el) => {
  lineChartRef.value = el;
};
const setPieChartRef = (el) => {
  pieChartRef.value = el;
};
const setRocChartRef = (el) => {
  rocChartRef.value = el;
};
const setEvalDetailChartRef = (el) => {
  evalDetailChartRef.value = el;
};

const summaryCards = computed(() => {
  const s = summary.value;
  if (!s) return [];
  const sum = s.summary;
  return [
    { key: "users_total", label: "用户总数", value: sum.users_total },
    { key: "users_enrolled", label: "已注册用户", value: sum.users_enrolled },
    { key: "verify_total", label: "验证总次数", value: sum.verify_total },
    {
      key: "verify_accept_rate",
      label: "验证通过率",
      value: (sum.verify_accept_rate * 100).toFixed(1) + "%"
    },
    {
      key: "threshold_default",
      label: "默认阈值",
      value: sum.threshold_default
    }
  ];
});

const userDialogTitle = computed(() =>
  userDialogMode.value === "create" ? "新建用户" : "编辑用户"
);
const adminDialogTitle = computed(() =>
  adminDialogMode.value === "create" ? "新建管理员" : "编辑管理员"
);
const evalItems = [
  {
    key: "det",
    title: "DET 曲线",
    subtitle: "低误识区表现",
    detail: "在低误识区域更直观反映模型区分能力，常用于安全场景。",
    note: "横轴为 FPR，纵轴为 FNR，曲线越靠左下越优。",
    placeholder: "暂无数据",
    thumb: "DET 缩略图"
  },
  {
    key: "mindcf",
    title: "minDCF",
    subtitle: "工程决策指标",
    detail: "结合先验概率与误识/漏识成本，辅助阈值与上线决策。",
    note: "横轴为阈值，纵轴为 DCF，最低点对应推荐阈值。",
    placeholder: "暂无数据",
    thumb: "minDCF 缩略图"
  },
  {
    key: "score",
    title: "评分分布",
    subtitle: "同人 / 异人分布",
    detail: "展示同人/异人评分分布与重叠区，判断可分性。",
    note: "横轴为相似度得分，纵轴为样本数量。同人分布应更偏高分，异人分布应更偏低分；两者重叠越少，误识/漏识越少，区分能力越强。",
    placeholder: "暂无数据",
    thumb: "分布缩略图"
  },
  {
    key: "calib",
    title: "校准指标",
    subtitle: "ECE / 可靠性曲线",
    detail: "衡量分数概率校准程度，便于阈值稳定性评估。",
    note: "横轴为置信度，纵轴为准确率，曲线越贴近对角线越好。",
    placeholder: "暂无数据",
    thumb: "校准缩略图"
  }
];
const activeEvalKey = ref("");
const activeEval = computed(
  () => evalItems.find((item) => item.key === activeEvalKey.value) || null
);
const evalDetailChartRef = ref(null);
const evalThumbRefs = ref({});
const evalThumbCharts = {};
let evalDetailChart = null;

function canInitChart(el) {
  return el && el.clientWidth > 0 && el.clientHeight > 0;
}

function ensureChart(el, chart) {
  if (!canInitChart(el)) return chart;
  if (!chart) return echarts.init(el);
  return chart;
}

const activeEvalHasData = computed(() => {
  if (!activeEvalKey.value) return false;
  return hasEvalData(activeEvalKey.value);
});
const rocDerived = computed(() => {
  const thresholds = modelMetrics.value.thresholds || [];
  const fpr = modelMetrics.value.fpr || [];
  const tpr = modelMetrics.value.tpr || [];
  const thresholdDefault = modelMetrics.value.threshold_default;
  if (!thresholds.length || !fpr.length || !tpr.length || typeof thresholdDefault !== "number") {
    return {
      far: null,
      frr: null,
      tpr: null,
      threshold: null
    };
  }
  let bestIdx = 0;
  let bestDiff = Infinity;
  thresholds.forEach((thr, idx) => {
    if (fpr[idx] === undefined || tpr[idx] === undefined) return;
    const diff = Math.abs(thr - thresholdDefault);
    if (diff < bestDiff) {
      bestDiff = diff;
      bestIdx = idx;
    }
  });
  const far = fpr[bestIdx];
  const tprVal = tpr[bestIdx];
  return {
    far,
    frr: tprVal === null || tprVal === undefined ? null : 1 - tprVal,
    tpr: tprVal,
    threshold: thresholds[bestIdx]
  };
});

function initCharts() {
  lineChart = ensureChart(lineChartRef.value, lineChart);
  pieChart = ensureChart(pieChartRef.value, pieChart);
  rocChart = ensureChart(rocChartRef.value, rocChart);
}

function stopEvalPolling() {
  if (evalPollingTimer) {
    clearInterval(evalPollingTimer);
    evalPollingTimer = null;
  }
}

async function pollEvalStatus() {
  try {
    const res = await fetchRocEvaluateStatus();
    const statusValue = res.data?.status || "idle";
    modelEvaluatingStatus.value = statusValue;
    if (statusValue === "ok") {
      if (res.data?.model) {
        modelMetricsModel.value = res.data.model;
      }
      stopEvalPolling();
      modelEvaluating.value = false;
      await loadModelMetrics();
      ElMessage.success("评估完成");
    } else if (statusValue === "failed") {
      stopEvalPolling();
      modelEvaluating.value = false;
      const msg = res.data?.error || "评估失败";
      modelMetricsError.value = msg;
      ElMessage.error(msg);
    }
  } catch (e) {
    stopEvalPolling();
    modelEvaluating.value = false;
    const msg = e.response?.data?.error || "评估状态获取失败";
    modelMetricsError.value = msg;
    ElMessage.error(msg);
  }
}

function startEvalPolling() {
  stopEvalPolling();
  evalPollingTimer = setInterval(pollEvalStatus, 1500);
}

function formatDateTime(value) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(
    date.getHours()
  )}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function formatMetric(value) {
  if (value === null || value === undefined || value === "") return "--";
  if (typeof value === "number") {
    return Number.isFinite(value) ? value.toFixed(4) : "--";
  }
  return value;
}

function formatPercent(value) {
  if (value === null || value === undefined || value === "") return "--";
  if (typeof value === "number") {
    return Number.isFinite(value) ? `${(value * 100).toFixed(2)}%` : "--";
  }
  return value;
}

function updateCharts() {
  if (!stats.value) return;
  const xAxis = stats.value.xAxis || [];
  const s = stats.value.series || {};
  const totals = s.verify_total || [];
  const pieData = stats.value.pie || [];
  const maxTotal = totals.length ? Math.max(...totals) : 0;
  const yMax = maxTotal ? Math.ceil(maxTotal * 1.4) : 5;

  if (lineChart) {
    lineChart.setOption({
      tooltip: { trigger: "axis" },
      legend: { data: ["验证次数", "通过率"] },
      grid: { left: 40, right: 50, top: 40, bottom: 40 },
      xAxis: {
        type: "category",
        data: xAxis,
        boundaryGap: true,
        axisLine: { lineStyle: { color: "#dcdfe6" } },
        axisTick: { show: false }
      },
      yAxis: [
        {
          type: "value",
          name: "次数",
          min: 0,
          max: yMax,
          minInterval: 1,
          axisLine: { show: false },
          splitLine: { lineStyle: { type: "dashed", color: "#ebeef5" } }
        },
        {
          type: "value",
          name: "通过率",
          min: 0,
          max: 1,
          axisLabel: {
            formatter: (v) => `${Math.round(v * 100)}%`
          },
          axisLine: { show: false },
          splitLine: { show: false }
        }
      ],
      series: [
        {
          name: "验证次数",
          type: "bar",
          data: totals,
          barMaxWidth: 26,
          itemStyle: {
            color: "#409EFF",
            borderRadius: [4, 4, 0, 0]
          }
        },
        {
          name: "通过率",
          type: "line",
          smooth: true,
          symbol: "circle",
          symbolSize: 6,
          lineStyle: { width: 2, color: "#67C23A" },
          itemStyle: { color: "#67C23A" },
          yAxisIndex: 1,
          data: s.accept_rate || []
        }
      ]
    });
  }

  if (pieChart) {
    const totalCount = pieData.reduce((acc, item) => acc + (item.value || 0), 0);
    pieChart.setOption({
      color: ["#3B82F6", "#10B981", "#F97316"],
      tooltip: { trigger: "item" },
      legend: {
        orient: "horizontal",
        left: "center",
        bottom: 0,
        formatter: (name) => {
          const target = pieData.find((item) => item.name === name);
          const value = target ? target.value : 0;
          const percent = totalCount ? Math.round((value / totalCount) * 100) : 0;
          return `${name}  ${value} (${percent}%)`;
        }
      },
      series: [
        {
          type: "pie",
          radius: "62%",
          center: ["50%", "45%"],
          avoidLabelOverlap: true,
          label: { show: false },
          labelLine: { show: false },
          data: pieData
        }
      ]
    });
  }
}

function updateRocChart() {
  rocChart = ensureChart(rocChartRef.value, rocChart);
  if (!rocChart) return;
  const fpr = modelMetrics.value.fpr || [];
  const tpr = modelMetrics.value.tpr || [];
  if (!fpr.length || !tpr.length) {
    rocChart.clear();
    return;
  }
  const seriesData = fpr.map((x, idx) => [x, tpr[idx] ?? 0]);
  let eerPoint = null;
  let eerValue = null;
  if (seriesData.length) {
    let bestIdx = 0;
    let bestDiff = Infinity;
    seriesData.forEach((item, idx) => {
      const fprVal = item[0];
      const tprVal = item[1];
      const fnrVal = 1 - tprVal;
      const diff = Math.abs(fprVal - fnrVal);
      if (diff < bestDiff) {
        bestDiff = diff;
        bestIdx = idx;
      }
    });
    eerPoint = seriesData[bestIdx];
    if (eerPoint) {
      eerValue = Math.min(1, Math.max(0, eerPoint[0]));
    }
  }
  rocChart.setOption({
    title: {
      text: "ROC 曲线",
      left: 0,
      top: 2,
      textStyle: { fontSize: 13, fontWeight: 600, color: "#111827" },
    },
    tooltip: {
      trigger: "axis",
      formatter: (params) => {
        const point = params[0]?.data || [0, 0];
        const fprVal = (point[0] * 100).toFixed(2);
        const tprVal = (point[1] * 100).toFixed(2);
        return `FPR: ${fprVal}%<br/>TPR: ${tprVal}%`;
      }
    },
    legend: {
      top: 28,
      right: 6,
      itemGap: 10,
      textStyle: { fontSize: 11, color: "#6b7280" },
      data: ["ROC", "随机基线", "EER 点"]
    },
    grid: { left: 55, right: 24, top: 64, bottom: 48 },
    xAxis: {
      type: "value",
      name: "FPR",
      min: 0,
      max: 1,
      axisLine: { lineStyle: { color: "#dcdfe6" } },
      nameLocation: "middle",
      nameGap: 24,
      axisLabel: { formatter: (v) => `${Math.round(v * 100)}%` }
    },
    yAxis: {
      type: "value",
      name: "TPR",
      min: 0,
      max: 1,
      axisLine: { show: false },
      nameLocation: "middle",
      nameGap: 32,
      axisLabel: { formatter: (v) => `${Math.round(v * 100)}%` },
      splitLine: { lineStyle: { type: "dashed", color: "#ebeef5" } }
    },
    series: [
      {
        name: "ROC",
        type: "line",
        smooth: true,
        symbol: "none",
        lineStyle: { width: 2, color: "#409EFF" },
        data: seriesData
      },
      {
        name: "随机基线",
        type: "line",
        symbol: "none",
        lineStyle: { width: 1, type: "dashed", color: "#9ca3af" },
        data: [
          [0, 0],
          [1, 1]
        ]
      },
      {
        name: "EER 点",
        type: "scatter",
        symbolSize: 8,
        itemStyle: { color: "#F97316" },
        data: eerPoint ? [eerPoint] : [],
        tooltip: {
          formatter: () =>
            eerValue !== null ? `EER ≈ ${(eerValue * 100).toFixed(2)}%` : "EER"
        }
      }
    ]
  });
}

function setEvalThumbRef(key) {
  return (el) => {
    if (el) {
      evalThumbRefs.value[key] = el;
    }
  };
}

function hasEvalData(key) {
  const metrics = modelMetrics.value;
  if (key === "det") {
    return Array.isArray(metrics.det?.fpr) && metrics.det.fpr.length > 0;
  }
  if (key === "mindcf") {
    return Array.isArray(metrics.mindcf_data?.dcf) && metrics.mindcf_data.dcf.length > 0;
  }
  if (key === "score") {
    return Array.isArray(metrics.score_dist?.bins) && metrics.score_dist.bins.length > 1;
  }
  if (key === "calib") {
    return Array.isArray(metrics.calibration?.bins) && metrics.calibration.bins.length > 1;
  }
  return false;
}

function getEvalChartOption(key, compact = false) {
  const metrics = modelMetrics.value;
  if (key === "det") {
    const fpr = metrics.det?.fpr || [];
    const fnr = metrics.det?.fnr || [];
    const data = fpr.map((x, idx) => [x, fnr[idx] ?? 0]);
    return {
      grid: compact ? { left: 6, right: 6, top: 6, bottom: 6 } : { left: 58, right: 28, top: 34, bottom: 52 },
      xAxis: {
        type: "value",
        name: compact ? "" : "FPR",
        min: 0,
        max: 1,
        axisLabel: compact ? { show: false } : { formatter: (v) => `${Math.round(v * 100)}%`, margin: 10 },
        nameLocation: "middle",
        nameGap: 30,
        axisLine: { lineStyle: { color: "#e5e7eb" } },
        axisTick: { show: !compact }
      },
      yAxis: {
        type: "value",
        name: compact ? "" : "FNR",
        min: 0,
        max: 1,
        axisLabel: compact ? { show: false } : { formatter: (v) => `${Math.round(v * 100)}%`, margin: 10 },
        nameLocation: "middle",
        nameGap: 38,
        axisLine: { show: false },
        axisTick: { show: !compact },
        splitLine: { lineStyle: { color: "#f3f4f6" } }
      },
      series: [
        {
          type: "line",
          smooth: true,
          symbol: "none",
          lineStyle: { color: "#3B82F6", width: 2 },
          data
        }
      ]
    };
  }
  if (key === "mindcf") {
    const thresholds = metrics.mindcf_data?.thresholds || [];
    const dcf = metrics.mindcf_data?.dcf || [];
    const data = thresholds
      .map((x, idx) => [x, dcf[idx] ?? 0])
      .filter((item) => Number.isFinite(item[0]) && Number.isFinite(item[1]))
      .sort((a, b) => a[0] - b[0]);
    return {
      grid: compact ? { left: 6, right: 6, top: 6, bottom: 6 } : { left: 58, right: 28, top: 34, bottom: 52 },
      xAxis: {
        type: "value",
        name: compact ? "" : "阈值",
        axisLabel: compact ? { show: false } : { formatter: (v) => v.toFixed(2), margin: 10 },
        nameLocation: "middle",
        nameGap: 30,
        axisLine: { lineStyle: { color: "#e5e7eb" } },
        axisTick: { show: !compact }
      },
      yAxis: {
        type: "value",
        name: compact ? "" : "DCF",
        axisLabel: compact ? { show: false } : { formatter: (v) => v.toFixed(2), margin: 10 },
        nameLocation: "middle",
        nameGap: 38,
        axisLine: { show: false },
        axisTick: { show: !compact },
        splitLine: { lineStyle: { color: "#f3f4f6" } }
      },
      series: [
        {
          type: "line",
          smooth: true,
          symbol: "none",
          lineStyle: { color: "#10B981", width: 2 },
          data
        }
      ]
    };
  }
  if (key === "score") {
    const bins = metrics.score_dist?.bins || [];
    const same = metrics.score_dist?.same || [];
    const diff = metrics.score_dist?.diff || [];
    const centers = bins.length > 1 ? bins.slice(0, -1).map((b, i) => (b + bins[i + 1]) / 2) : [];
    const labelInterval = centers.length > 12 ? Math.max(0, Math.ceil(centers.length / 10) - 1) : 0;
    return {
      grid: compact ? { left: 6, right: 6, top: 6, bottom: 6 } : { left: 58, right: 28, top: 34, bottom: 60 },
      xAxis: {
        type: "category",
        name: compact ? "" : "得分",
        data: centers.map((v) => v.toFixed(2)),
        axisLabel: compact ? { show: false } : { rotate: 30, interval: labelInterval, margin: 12 },
        nameLocation: "middle",
        nameGap: 40,
        axisLine: { lineStyle: { color: "#e5e7eb" } },
        axisTick: { show: !compact }
      },
      yAxis: {
        type: "value",
        name: compact ? "" : "数量",
        axisLabel: compact ? { show: false } : { margin: 10 },
        nameLocation: "middle",
        nameGap: 38,
        axisLine: { show: false },
        splitLine: { lineStyle: { color: "#f3f4f6" } }
      },
      series: [
        {
          type: "bar",
          stack: "dist",
          barMaxWidth: compact ? 6 : 16,
          itemStyle: { color: "rgba(59, 130, 246, 0.6)" },
          data: same
        },
        {
          type: "bar",
          stack: "dist",
          barMaxWidth: compact ? 6 : 16,
          itemStyle: { color: "rgba(244, 114, 182, 0.6)" },
          data: diff
        }
      ]
    };
  }
  if (key === "calib") {
    const bins = metrics.calibration?.bins || [];
    const acc = metrics.calibration?.accuracy || [];
    const conf = metrics.calibration?.confidence || [];
    const centers = bins.length > 1 ? bins.slice(0, -1).map((b, i) => (b + bins[i + 1]) / 2) : [];
    return {
      grid: compact ? { left: 6, right: 6, top: 6, bottom: 6 } : { left: 58, right: 28, top: 34, bottom: 52 },
      xAxis: {
        type: "value",
        name: compact ? "" : "置信度",
        min: 0,
        max: 1,
        axisLabel: compact ? { show: false } : { formatter: (v) => `${Math.round(v * 100)}%`, margin: 10 },
        nameLocation: "middle",
        nameGap: 30,
        axisLine: { lineStyle: { color: "#e5e7eb" } },
        axisTick: { show: !compact }
      },
      yAxis: {
        type: "value",
        name: compact ? "" : "准确率",
        min: 0,
        max: 1,
        axisLabel: compact ? { show: false } : { formatter: (v) => `${Math.round(v * 100)}%`, margin: 10 },
        nameLocation: "middle",
        nameGap: 38,
        axisLine: { show: false },
        splitLine: { lineStyle: { color: "#f3f4f6" } }
      },
      series: [
        {
          type: "line",
          symbol: "circle",
          symbolSize: compact ? 2 : 6,
          lineStyle: { color: "#6366F1" },
          data: centers.map((x, i) => [x, acc[i] ?? 0])
        },
        {
          type: "line",
          symbol: "none",
          lineStyle: { color: "rgba(17, 24, 39, 0.35)", type: "dashed" },
          data: [
            [0, 0],
            [1, 1]
          ]
        }
      ]
    };
  }
  return null;
}

function updateEvalThumbCharts() {
  evalItems.forEach((item) => {
    const el = evalThumbRefs.value[item.key];
    if (!el) return;
    if (!canInitChart(el)) return;
    const hasData = hasEvalData(item.key);
    if (!hasData) {
      if (evalThumbCharts[item.key]) {
        evalThumbCharts[item.key].clear();
      }
      return;
    }
    evalThumbCharts[item.key] = ensureChart(el, evalThumbCharts[item.key]);
    if (!evalThumbCharts[item.key]) return;
    const option = getEvalChartOption(item.key, true);
    if (option) {
      evalThumbCharts[item.key].setOption(option, { notMerge: true, lazyUpdate: true });
    } else {
      evalThumbCharts[item.key].clear();
    }
  });
}

function updateEvalDetailChart() {
  if (!activeEvalKey.value) return;
  const el = evalDetailChartRef.value;
  if (!el) return;
  if (!canInitChart(el)) return;
  evalDetailChart = ensureChart(el, evalDetailChart);
  if (!evalDetailChart) return;
  const option = hasEvalData(activeEvalKey.value) ? getEvalChartOption(activeEvalKey.value, false) : null;
  if (option) {
    evalDetailChart.setOption(option, { notMerge: true, lazyUpdate: true });
  } else {
    evalDetailChart.clear();
  }
}

function resetEvalDetailChart() {
  if (evalDetailChart) {
    evalDetailChart.dispose();
    evalDetailChart = null;
  }
}

async function loadDashboard() {
  const res = await fetchDashboard();
  summary.value = res.data;
  if (res.data && res.data.summary && typeof res.data.summary.threshold_default === "number") {
    threshold.value = res.data.summary.threshold_default;
    thresholdDraft.value = threshold.value;
  }
}

async function loadStats() {
  const res = await fetchStatsEcharts();
  stats.value = res.data;
  updateCharts();
}

async function loadCurrentUser() {
  try {
    const res = await fetchCurrentUser();
    currentUser.value = res.data;
  } catch (e) {
    currentUser.value = null;
  }
}

async function loadLogs() {
  const params = { page: logPage.value };
  const f = logFilters.value;
  if (f.actor) params.actor = f.actor;
  if (f.predicted) params.predicted = f.predicted;
  if (f.result) params.result = f.result;
  if (Array.isArray(f.dates) && f.dates.length === 2) {
    params.start_date = f.dates[0];
    params.end_date = f.dates[1];
  }
  const res = await fetchLogs(params);
  if (Array.isArray(res.data.results)) {
    logs.value = res.data.results;
    logTotal.value = res.data.count || 0;
  } else if (Array.isArray(res.data)) {
    logs.value = res.data;
    logTotal.value = res.data.length;
  } else {
    logs.value = [];
    logTotal.value = 0;
  }
}

async function loadUsers() {
  usersLoading.value = true;
  try {
    const params = { page: usersPage.value };
    const f = userFilters.value;
    if (f.q) params.q = f.q;
    params.is_staff = "false";
    if (f.is_active !== "") params.is_active = f.is_active;
    if (f.has_voiceprint !== "") params.has_voiceprint = f.has_voiceprint;
    const res = await fetchUsers(params);
    if (Array.isArray(res.data.results)) {
      users.value = res.data.results;
      usersTotal.value = res.data.count || 0;
    } else if (Array.isArray(res.data)) {
      users.value = res.data;
      usersTotal.value = res.data.length;
    } else {
      users.value = [];
      usersTotal.value = 0;
    }
    usersLoaded.value = true;
  } catch (e) {
    ElMessage.error("加载用户失败");
  } finally {
    usersLoading.value = false;
  }
}

function handleUserSelectionChange(rows) {
  selectedUserIds.value = rows.map((r) => r.id);
}

function handleUserRefresh() {
  loadUsers();
}

async function handleUserSearch() {
  usersPage.value = 1;
  await loadUsers();
}

async function handleUserReset() {
  userFilters.value = {
    q: "",
    is_active: "",
    has_voiceprint: ""
  };
  usersPage.value = 1;
  await loadUsers();
}

async function handleUserPageChange(page) {
  usersPage.value = page;
  await loadUsers();
}

function openCreateUser() {
  userDialogMode.value = "create";
  userForm.value = {
    username: "",
    password: "",
    full_name: "",
    phone: "",
    email: "",
    department: "",
    is_active: true
  };
  userDialogVisible.value = true;
}

function openEditUser(row) {
  userDialogMode.value = "edit";
  userForm.value = {
    username: row.username,
    password: "",
    full_name: row.full_name || "",
    phone: row.phone || "",
    email: row.email || "",
    department: row.department || "",
    is_active: row.is_active !== false
  };
  userDialogVisible.value = true;
}

async function handleUserSubmit() {
  if (userDialogMode.value === "create" && !userForm.value.username) {
    ElMessage.warning("请输入用户名");
    return;
  }
  if (userDialogMode.value === "create" && !userForm.value.password) {
    ElMessage.warning("请输入密码");
    return;
  }
  userSaving.value = true;
  try {
    if (userDialogMode.value === "create") {
      await createUser({
        username: userForm.value.username,
        password: userForm.value.password,
        full_name: userForm.value.full_name,
        phone: userForm.value.phone,
        email: userForm.value.email,
        department: userForm.value.department,
        is_active: userForm.value.is_active
      });
      ElMessage.success("用户已创建");
    } else {
      const user = users.value.find((item) => item.username === userForm.value.username);
      if (!user) {
        ElMessage.error("用户不存在");
        return;
      }
      await updateUser(user.id, {
        full_name: userForm.value.full_name,
        phone: userForm.value.phone,
        email: userForm.value.email,
        department: userForm.value.department,
        is_active: userForm.value.is_active
      });
      ElMessage.success("用户已更新");
      if (currentUser.value && user.id === currentUser.value.user_id && !userForm.value.is_active) {
        ElMessage.warning("账号已禁用，将退出登录");
        handleLogout();
        return;
      }
    }
    userDialogVisible.value = false;
    await loadUsers();
  } catch (e) {
    ElMessage.error("操作失败");
  } finally {
    userSaving.value = false;
  }
}

function openResetPassword(row) {
  passwordTarget.value = row;
  passwordForm.value = { password: "" };
  passwordDialogVisible.value = true;
}

async function handlePasswordSubmit() {
  if (!passwordTarget.value) return;
  if (!passwordForm.value.password) {
    ElMessage.warning("请输入新密码");
    return;
  }
  passwordSaving.value = true;
  try {
    await resetUserPassword(passwordTarget.value.id, passwordForm.value.password);
    ElMessage.success("密码已重置");
    passwordDialogVisible.value = false;
  } catch (e) {
    ElMessage.error("重置失败");
  } finally {
    passwordSaving.value = false;
  }
}

async function handleResetVoiceprint(row) {
  try {
    await ElMessageBox.confirm(
      `确认清理 ${row.username} 的声纹数据？`,
      "提示",
      { type: "warning" }
    );
    await resetUserVoiceprint(row.id);
    ElMessage.success("声纹已清理");
    await loadUsers();
  } catch (e) {
    if (e !== "cancel" && e !== "close") {
      ElMessage.error("清理失败");
    }
  }
}

async function handleDeleteUser(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除用户 ${row.username}？`,
      "提示",
      { type: "warning" }
    );
    await deleteUser(row.id);
    ElMessage.success("用户已删除");
    await loadUsers();
    if (currentUser.value && row.id === currentUser.value.user_id) {
      handleLogout();
    }
  } catch (e) {
    if (e !== "cancel" && e !== "close") {
      ElMessage.error("删除失败");
    }
  }
}

async function handleBatchToggle(isActive) {
  try {
    await ElMessageBox.confirm(
      `确认批量${isActive ? "启用" : "禁用"}所选用户？`,
      "提示",
      { type: "warning" }
    );
    await Promise.all(
      selectedUserIds.value.map((id) => updateUser(id, { is_active: isActive }))
    );
    ElMessage.success("批量操作完成");
    await loadUsers();
    const currentId = currentUser.value?.user_id;
    if (currentId && selectedUserIds.value.includes(currentId) && !isActive) {
      handleLogout();
    }
  } catch (e) {
    if (e !== "cancel" && e !== "close") {
      ElMessage.error("批量操作失败");
    }
  }
}

function openBatchResetPassword() {
  batchPasswordForm.value = { password: "" };
  batchPasswordDialogVisible.value = true;
}

async function handleBatchPasswordSubmit() {
  if (!batchPasswordForm.value.password) {
    ElMessage.warning("请输入新密码");
    return;
  }
  batchPasswordSaving.value = true;
  try {
    await Promise.all(
      selectedUserIds.value.map((id) =>
        resetUserPassword(id, batchPasswordForm.value.password)
      )
    );
    ElMessage.success("批量重置完成");
    batchPasswordDialogVisible.value = false;
  } catch (e) {
    ElMessage.error("批量重置失败");
  } finally {
    batchPasswordSaving.value = false;
  }
}

async function handleBatchClearVoiceprint() {
  try {
    await ElMessageBox.confirm(
      "确认批量清理所选用户声纹？",
      "提示",
      { type: "warning" }
    );
    await Promise.all(selectedUserIds.value.map((id) => resetUserVoiceprint(id)));
    ElMessage.success("批量清理完成");
    await loadUsers();
  } catch (e) {
    if (e !== "cancel" && e !== "close") {
      ElMessage.error("批量清理失败");
    }
  }
}

async function handleBatchDelete() {
  try {
    await ElMessageBox.confirm(
      "确认批量删除所选用户？",
      "提示",
      { type: "warning" }
    );
    await Promise.all(selectedUserIds.value.map((id) => deleteUser(id)));
    ElMessage.success("批量删除完成");
    await loadUsers();
    const currentId = currentUser.value?.user_id;
    if (currentId && selectedUserIds.value.includes(currentId)) {
      handleLogout();
    }
  } catch (e) {
    if (e !== "cancel" && e !== "close") {
      ElMessage.error("批量删除失败");
    }
  }
}

function openAdminListAccess() {
  adminAccessForm.value = { secret_password: "" };
  adminAccessDialogVisible.value = true;
}

async function loadAdminUsers() {
  adminListLoading.value = true;
  try {
    const res = await fetchAdminUsers({
      q: adminFilters.value.q || undefined,
      is_active: adminFilters.value.is_active || undefined
    });
    if (Array.isArray(res.data.results)) {
      adminList.value = res.data.results;
    } else if (Array.isArray(res.data)) {
      adminList.value = res.data;
    } else {
      adminList.value = [];
    }
    selectedAdminIds.value = [];
  } catch (e) {
    ElMessage.error("加载管理员列表失败");
  } finally {
    adminListLoading.value = false;
  }
}

async function handleAdminAccessSubmit() {
  if (!adminAccessForm.value.secret_password) {
    ElMessage.warning("请输入高层密码");
    return;
  }
  adminListLoading.value = true;
  try {
    await fetchAdminList(adminAccessForm.value.secret_password);
    adminListUnlocked.value = true;
    adminAccessDialogVisible.value = false;
    await loadAdminAccessLogs();
    await loadAdminUsers();
  } catch (e) {
    const msg = e.response?.data?.error || "验证失败";
    ElMessage.error(msg);
  } finally {
    adminListLoading.value = false;
  }
}

function handleAdminListRefresh() {
  if (!adminListUnlocked.value) {
    openAdminListAccess();
    return;
  }
  loadAdminUsers();
}

function handleAdminSearch() {
  loadAdminUsers();
}

function handleAdminReset() {
  adminFilters.value = { q: "", is_active: "" };
  loadAdminUsers();
}

function handleAdminSelectionChange(rows) {
  selectedAdminIds.value = rows.map((row) => row.id);
}

function openCreateAdmin() {
  adminDialogMode.value = "create";
  adminForm.value = {
    username: "",
    password: "",
    full_name: "",
    phone: "",
    email: "",
    department: "",
    is_active: true
  };
  adminDialogVisible.value = true;
}

function openEditAdmin(row) {
  adminDialogMode.value = "edit";
  adminForm.value = {
    id: row.id,
    username: row.username,
    password: "",
    full_name: row.full_name || "",
    phone: row.phone || "",
    email: row.email || "",
    department: row.department || "",
    is_active: row.is_active
  };
  adminDialogVisible.value = true;
}

async function handleAdminSubmit() {
  if (!adminForm.value.username) {
    ElMessage.warning("请输入用户名");
    return;
  }
  if (adminDialogMode.value === "create" && !adminForm.value.password) {
    ElMessage.warning("请输入密码");
    return;
  }
  adminSaving.value = true;
  try {
    if (adminDialogMode.value === "create") {
      await createAdminUser({
        username: adminForm.value.username,
        password: adminForm.value.password,
        full_name: adminForm.value.full_name,
        phone: adminForm.value.phone,
        email: adminForm.value.email,
        department: adminForm.value.department,
        is_active: adminForm.value.is_active
      });
      ElMessage.success("管理员已创建");
    } else {
      await updateAdminUser(adminForm.value.id, {
        full_name: adminForm.value.full_name,
        phone: adminForm.value.phone,
        email: adminForm.value.email,
        department: adminForm.value.department,
        is_active: adminForm.value.is_active
      });
      ElMessage.success("管理员已更新");
    }
    adminDialogVisible.value = false;
    await loadAdminUsers();
  } catch (e) {
    const msg = e.response?.data?.error || "保存失败";
    ElMessage.error(msg);
  } finally {
    adminSaving.value = false;
  }
}

async function handleAdminToggle(row) {
  try {
    await updateAdminUser(row.id, { is_active: !row.is_active });
    ElMessage.success("状态已更新");
    await loadAdminUsers();
  } catch (e) {
    ElMessage.error("状态更新失败");
  }
}

function openAdminResetPassword(row) {
  adminPasswordTarget.value = row;
  adminPasswordForm.value = { password: "" };
  adminPasswordDialogVisible.value = true;
}

async function handleAdminPasswordSubmit() {
  if (!adminPasswordForm.value.password) {
    ElMessage.warning("请输入新密码");
    return;
  }
  if (!adminPasswordTarget.value) return;
  adminPasswordSaving.value = true;
  try {
    await resetUserPassword(adminPasswordTarget.value.id, adminPasswordForm.value.password);
    ElMessage.success("密码已重置");
    adminPasswordDialogVisible.value = false;
  } catch (e) {
    ElMessage.error("重置失败");
  } finally {
    adminPasswordSaving.value = false;
  }
}

function openAdminBatchResetPassword() {
  adminBatchPasswordForm.value = { password: "" };
  adminBatchPasswordDialogVisible.value = true;
}

async function handleAdminBatchPasswordSubmit() {
  if (!adminBatchPasswordForm.value.password) {
    ElMessage.warning("请输入新密码");
    return;
  }
  adminBatchPasswordSaving.value = true;
  try {
    await bulkResetAdminPassword(selectedAdminIds.value, adminBatchPasswordForm.value.password);
    ElMessage.success("批量重置完成");
    adminBatchPasswordDialogVisible.value = false;
  } catch (e) {
    ElMessage.error("批量重置失败");
  } finally {
    adminBatchPasswordSaving.value = false;
  }
}

async function handleAdminBatchToggle(isActive) {
  try {
    await bulkUpdateAdminStatus(selectedAdminIds.value, isActive);
    ElMessage.success(isActive ? "已批量启用" : "已批量禁用");
    await loadAdminUsers();
  } catch (e) {
    ElMessage.error("批量操作失败");
  }
}

async function loadAdminAccessLogs() {
  adminAccessLogsLoading.value = true;
  try {
    const res = await fetchAdminAccessLogs();
    if (Array.isArray(res.data.results)) {
      adminAccessLogs.value = res.data.results;
    } else if (Array.isArray(res.data)) {
      adminAccessLogs.value = res.data;
    } else {
      adminAccessLogs.value = [];
    }
  } catch (e) {
    ElMessage.error("加载访问日志失败");
  } finally {
    adminAccessLogsLoading.value = false;
  }
}

async function loadModelMetrics() {
  modelMetricsLoading.value = true;
  try {
    const res = await fetchRocMetrics();
    modelMetrics.value = {
      auc: res.data.auc,
      eer: res.data.eer,
      threshold: res.data.threshold,
      threshold_eer: res.data.threshold_eer,
      threshold_mindcf: res.data.threshold_mindcf,
      mindcf: res.data.mindcf,
      p_target: res.data.p_target,
      c_miss: res.data.c_miss,
      c_fa: res.data.c_fa,
      threshold_default: res.data.threshold_default,
      threshold_diff: res.data.threshold_diff,
      fpr: res.data.fpr,
      tpr: res.data.tpr,
      thresholds: res.data.thresholds,
      det: res.data.det,
      mindcf_data: res.data.mindcf_data,
      score_dist: res.data.score_dist,
      calibration: res.data.calibration
    };
    modelMetricsModel.value = res.data.model || modelMetricsModel.value || modelCurrent.value;
    modelMetricsError.value = "";
    
    // Ensure charts are updated after DOM update
    nextTick(() => {
        updateRocChart();
        updateEvalThumbCharts();
        updateEvalDetailChart();
    });
  } catch (e) {
    modelMetricsError.value = e.response?.data?.error || "模型指标未生成";
    modelMetrics.value = {
      auc: null,
      eer: null,
      threshold: null,
      threshold_eer: null,
      threshold_mindcf: null,
      mindcf: null,
      p_target: null,
      c_miss: null,
      c_fa: null,
      threshold_default: null,
      threshold_diff: null,
      fpr: null,
      tpr: null,
      thresholds: null,
      det: null,
      mindcf_data: null,
      score_dist: null,
      calibration: null
    };
    updateRocChart();
    updateEvalThumbCharts();
    updateEvalDetailChart();
  } finally {
    modelMetricsLoading.value = false;
  }
}

async function handleModelEvaluate() {
  modelEvaluating.value = true;
  modelMetricsError.value = "";
  try {
    if (!modelCurrent.value) {
      await loadModelList();
    }
    const name = modelCurrent.value || modelTarget.value || "";
    modelMetricsModel.value = name || modelMetricsModel.value;
    const res = await evaluateRocMetrics(name);
    const statusValue = res.data?.status || "idle";
    modelEvaluatingStatus.value = statusValue;
    if (statusValue === "running") {
      startEvalPolling();
      return;
    }
    if (statusValue === "failed") {
      const msg = res.data?.error || "评估失败";
      modelMetricsError.value = msg;
      ElMessage.error(msg);
      modelEvaluating.value = false;
      return;
    }
    await loadModelMetrics();
    modelEvaluating.value = false;
    ElMessage.success("评估完成");
  } catch (e) {
    const msg = e.response?.data?.error || "评估失败";
    modelMetricsError.value = msg;
    ElMessage.error(msg);
  } finally {
    if (!evalPollingTimer) {
      modelEvaluating.value = false;
    }
  }
}

function handleEvalCardClick(key) {
  if (activeEvalKey.value === key) {
    resetEvalDetailChart();
    activeEvalKey.value = "";
    return;
  }
  resetEvalDetailChart();
  activeEvalKey.value = key;
  nextTick(() => {
    handleResize();
    updateEvalDetailChart();
  });
}

function handleEvalCollapse() {
  resetEvalDetailChart();
  activeEvalKey.value = "";
}

async function loadModelList() {
  try {
    const res = await fetchModels();
    modelList.value = Array.isArray(res.data.models) ? res.data.models : [];
    modelCurrent.value = res.data.current || "";
    if (!modelTarget.value) {
      modelTarget.value = modelCurrent.value || "";
    }
  } catch (e) {
    modelList.value = [];
    modelCurrent.value = "";
  }
}

function handleModelTargetChange(value) {
  modelTarget.value = value || "";
}

async function handleModelSwitch() {
  if (!modelTarget.value) return;
  modelSwitching.value = true;
  try {
    const res = await switchModel(modelTarget.value);
    modelCurrent.value = res.data.current;
    ElMessage.success("模型切换成功");
  } catch (e) {
    ElMessage.error(e.response?.data?.error || "模型切换失败");
  } finally {
    modelSwitching.value = false;
  }
}

async function handleLogSearch() {
  await loadLogs();
}

async function handleLogReset() {
  logFilters.value = {
    actor: "",
    predicted: "",
    result: "",
    dates: []
  };
  logPage.value = 1;
  await loadLogs();
}

function handleLogSelectionChange(rows) {
  logSelectedIds.value = rows.map((r) => r.id);
}

async function handleLogPageChange(page) {
  logPage.value = page;
  await loadLogs();
}

async function handleDeleteSelectedLogs() {
  if (!logSelectedIds.value.length) {
    ElMessage.warning("请先选择要删除的日志");
    return;
  }
  try {
    await deleteLogs(logSelectedIds.value);
    ElMessage.success("删除成功");
    logSelectedIds.value = [];
    await loadLogs();
  } catch (e) {
    ElMessage.error("删除失败");
  }
}

async function refreshAll() {
  loading.value = true;
  try {
    await Promise.all([loadDashboard(), loadStats(), loadLogs()]);
  } catch (e) {
    ElMessage.error("加载数据失败");
  } finally {
    loading.value = false;
  }
}

async function handleSaveThreshold() {
  savingThreshold.value = true;
  try {
    const res = await updateThreshold(thresholdDraft.value);
    threshold.value = res.data.threshold;
    thresholdDraft.value = threshold.value;
    ElMessage.success("阈值已更新，仅对新的验证请求生效");
  } catch (e) {
    const msg =
      e.response && e.response.data && e.response.data.threshold
        ? e.response.data.threshold.join("; ")
        : "更新阈值失败";
    ElMessage.error(msg);
  } finally {
    savingThreshold.value = false;
  }
}

function handleThresholdDraftChange(value) {
  thresholdDraft.value = value;
}

async function handleCleanVerifyLogs() {
  maintenanceLogsLoading.value = true;
  try {
    const res = await cleanVerifyLogs(30);
    maintenanceLogsResult.value = res.data;
    ElMessage.success("日志清理完成");
  } catch (e) {
    ElMessage.error("日志清理失败");
  } finally {
    maintenanceLogsLoading.value = false;
  }
}

async function handleCheckModels() {
  maintenanceModelsLoading.value = true;
  try {
    const res = await checkModelFiles();
    maintenanceModelsResult.value = res.data;
    ElMessage.success("模型检查完成");
  } catch (e) {
    ElMessage.error("模型检查失败");
  } finally {
    maintenanceModelsLoading.value = false;
  }
}

async function handleCleanCache() {
  maintenanceCacheLoading.value = true;
  try {
    const res = await cleanCacheFiles(7);
    maintenanceCacheResult.value = res.data;
    ElMessage.success("缓存清理完成");
  } catch (e) {
    ElMessage.error("缓存清理失败");
  } finally {
    maintenanceCacheLoading.value = false;
  }
}

function handleLogout() {
  localStorage.removeItem("token");
  setAuthToken(null);
  router.push("/");
}

function handleResize() {
  if (lineChart) lineChart.resize();
  if (pieChart) pieChart.resize();
  if (rocChart) rocChart.resize();
  Object.values(evalThumbCharts).forEach((chart) => chart && chart.resize());
  if (evalDetailChart) evalDetailChart.resize();
  updateLogLayout();
}

function updateLogLayout() {
  nextTick(() => {
    const wrap = logTableWrapRef.value;
    if (!wrap || !wrap.getBoundingClientRect) return;
    const rect = wrap.getBoundingClientRect();
    const viewportHeight = window.innerHeight || 800;
    const paginationHeight = 64;
    const padding = 24;
    const available = Math.max(280, viewportHeight - rect.top - paginationHeight - padding);
    logTableHeight.value = Math.floor(available);
    const rowHeight = 42;
    const headHeight = 44;
    const pageSize = Math.max(6, Math.floor((available - headHeight) / rowHeight));
    if (pageSize !== logPageSize.value) {
      logPageSize.value = pageSize;
      logPage.value = 1;
      loadLogs();
    }
  });
}

function handleTabChange() {
  nextTick(() => {
    handleResize();
    if (activeTab.value === "users" && !usersLoaded.value) {
      loadUsers();
    }
    if (activeTab.value === "settings") {
      loadAdminAccessLogs();
    }
    if (activeTab.value === "admins" && !adminListUnlocked.value) {
      openAdminListAccess();
    }
    if (activeTab.value === "model") {
      initCharts();
      loadModelList();
      loadModelMetrics();
      requestAnimationFrame(() => {
        handleResize();
        updateRocChart();
        updateEvalThumbCharts();
        updateEvalDetailChart();
      });
    }
  });
}

onMounted(() => {
  initCharts();
  refreshAll();
  loadCurrentUser();
  loadUsers();
  loadAdminAccessLogs();
  loadModelList();
  loadModelMetrics();
  updateLogLayout();
  nextTick(() => {
    handleResize();
    updateEvalThumbCharts();
    updateEvalDetailChart();
  });
  fetchRocEvaluateStatus()
    .then((res) => {
      if (res.data?.status === "running") {
        modelEvaluating.value = true;
        startEvalPolling();
      }
    })
    .catch(() => {});
  window.addEventListener("resize", handleResize);
});

onUnmounted(() => {
  window.removeEventListener("resize", handleResize);
  stopEvalPolling();
  if (lineChart) {
    lineChart.dispose();
    lineChart = null;
  }
  if (pieChart) {
    pieChart.dispose();
    pieChart = null;
  }
  if (rocChart) {
    rocChart.dispose();
    rocChart = null;
  }
  Object.values(evalThumbCharts).forEach((chart) => {
    if (chart) chart.dispose();
  });
  if (evalDetailChart) {
    evalDetailChart.dispose();
    evalDetailChart = null;
  }
});
</script>

<style>
.dashboard-container {
  background: #f5f7fb;
  background-image: radial-gradient(
      1200px circle at 0% 0%,
      rgba(64, 158, 255, 0.14),
      transparent 50%
    ),
    radial-gradient(
      1200px circle at 100% 0%,
      rgba(103, 232, 169, 0.12),
      transparent 50%
    );
}

.dashboard-main {
  padding: 16px 24px 32px;
  box-sizing: border-box;
}

.dashboard-container :deep(.el-card) {
  border: 1px solid rgba(15, 23, 42, 0.06);
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(10px);
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.dashboard-container :deep(.el-card:hover) {
  transform: translateY(-2px);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.14);
  border-color: rgba(64, 158, 255, 0.18);
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  font-weight: 600;
  color: #111827;
}

.dashboard-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 8px 0 40px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.dashboard-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px 28px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid rgba(15, 23, 42, 0.08);
  box-shadow: 0 20px 40px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(12px);
}

.hero-title {
  font-size: 22px;
  font-weight: 600;
  color: #111827;
}

.hero-subtitle {
  margin-top: 6px;
  font-size: 13px;
  color: #6b7280;
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.apple-tabs :deep(.el-tabs__header) {
  margin: 0 0 16px;
}

.apple-tabs :deep(.el-tabs__nav-wrap::after) {
  height: 0;
}

.apple-tabs :deep(.el-tabs__nav) {
  display: flex;
  align-items: center;
}

.apple-tabs :deep(.el-tabs__item) {
  height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  padding-top: 0;
  padding-bottom: 0;
  padding: 0 20px;
  box-sizing: border-box;
  margin-right: 10px;
  border-radius: 20px;
  color: #111827;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid rgba(15, 23, 42, 0.08);
  font-weight: 500;
  transition: all 0.2s ease;
}

.apple-tabs :deep(.el-tabs__item.is-active) {
  color: #0f172a;
  background: #ffffff;
  border-color: rgba(15, 23, 42, 0.16);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.12);
}

.apple-tabs :deep(.el-tabs__active-bar) {
  height: 0;
}

.section-stack {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.placeholder-card {
  padding: 16px 12px;
  min-height: 200px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  justify-content: center;
  align-items: center;
  text-align: center;
}

.placeholder-title {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.placeholder-desc {
  font-size: 13px;
  color: #6b7280;
}

.settings-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.settings-title {
  font-size: 15px;
  font-weight: 600;
  color: #1f2937;
}

.settings-form {
  max-width: 520px;
}

.settings-meta {
  margin-top: 8px;
  font-size: 12px;
  color: #9ca3af;
}

.settings-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.maintenance-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.maintenance-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.04);
  font-size: 13px;
  color: #374151;
}

.model-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.model-right-stack {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.metric-card {
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.04);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.metric-card-label {
  font-size: 12px;
  color: #6b7280;
}

.metric-card-value {
  font-size: 16px;
  font-weight: 600;
  color: #111827;
}

.metric-grid :deep(.el-statistic__number) {
  font-weight: 600;
}

.model-metrics {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.metric-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
}

.metric-label {
  color: #6b7280;
}

.metric-value {
  color: #111827;
  font-weight: 600;
}

.metric-hint {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.04);
  font-size: 12px;
  color: #6b7280;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.metric-hint-title {
  font-weight: 600;
  color: #374151;
}

.metric-hint-item {
  line-height: 1.4;
}

.eval-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.eval-panel {
  padding: 12px;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.04);
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 120px;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
  border: 1px solid rgba(15, 23, 42, 0.04);
}

.eval-panel:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.12);
  border-color: rgba(64, 158, 255, 0.18);
}

.eval-panel.is-active {
  border-color: rgba(64, 158, 255, 0.32);
  box-shadow: 0 12px 28px rgba(64, 158, 255, 0.18);
}

.eval-title {
  font-size: 13px;
  font-weight: 600;
  color: #111827;
}

.eval-subtitle {
  font-size: 12px;
  color: #9ca3af;
}

.eval-thumb {
  margin-top: 6px;
  border-radius: 10px;
  background: linear-gradient(145deg, rgba(59, 130, 246, 0.12), rgba(16, 185, 129, 0.12));
  border: 1px dashed rgba(59, 130, 246, 0.25);
  height: 54px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #6b7280;
}

.eval-thumb-canvas {
  width: 100%;
  height: 100%;
}

.eval-thumb-empty {
  font-size: 12px;
  color: #9ca3af;
}

.eval-detail-card {
  overflow: hidden;
}

.eval-detail-body {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}

.eval-detail-text {
  font-size: 13px;
  color: #6b7280;
}

.eval-detail-chart {
  min-height: 250px;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.04);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9ca3af;
  font-size: 13px;
  padding: 8px;
  box-sizing: border-box;
}

.eval-detail-canvas {
  width: 100%;
  height: 100%;
  min-height: 250px;
}

.eval-detail-empty {
  padding: 12px;
  color: #9ca3af;
}

.eval-detail-note {
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.04);
  font-size: 12px;
  color: #6b7280;
}

.model-switch {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.roc-chart {
  width: 100%;
  height: 260px;
  margin-top: 14px;
}

@media (max-width: 1200px) {
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .eval-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.eval-expand-enter-active,
.eval-expand-leave-active {
  transition: all 0.25s ease;
}

.eval-expand-enter-from,
.eval-expand-leave-to {
  opacity: 0;
  transform: translateY(-8px) scale(0.98);
  max-height: 0;
}

.model-empty {
  font-size: 13px;
  color: #9ca3af;
  text-align: center;
  padding: 24px 0;
}

.title {
  font-size: 18px;
  font-weight: 600;
}

.apple-tabs :deep(#tab-overview),
.apple-tabs :deep(#tab-logs),
.apple-tabs :deep(#tab-users),
.apple-tabs :deep(#tab-model),
.apple-tabs :deep(#tab-settings),
.apple-tabs :deep(#tab-admins) {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 68px;
  padding-left: 18px;
  padding-right: 18px;
  line-height: 1;
}

.apple-tabs :deep(#tab-overview) {
  transform: translateX(2px);
}

.apple-tabs :deep(#tab-settings) {
  transform: translateX(-2px);
}

.card-label {
  font-size: 13px;
  color: #6b7280;
}

.card-header {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.card-subtitle {
  font-size: 12px;
  color: #9ca3af;
}

.card-value {
  margin-top: 6px;
  font-size: 22px;
  font-weight: 600;
  color: #111827;
}

.stat-card {
  border-radius: 18px;
  background: linear-gradient(145deg, #ffffff, #f7f9fc);
}

.panel-card {
  border-radius: 18px;
}

.threshold-box {
  font-size: 13px;
}

.threshold-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.threshold-label {
  color: #909399;
}

.threshold-text {
  font-weight: 600;
}

.log-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.log-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.log-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-left: auto;
}

.log-filter-form {
  margin-top: 10px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px 8px;
}

.user-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.user-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.user-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-filter-form {
  margin-top: 12px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px 8px;
}

.user-batch {
  margin-top: 10px;
  padding: 10px 12px;
  background: rgba(15, 23, 42, 0.04);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.user-batch-info {
  font-size: 12px;
  color: #6b7280;
}

.user-batch-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.user-action-stack {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.time-text {
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  color: #111827;
}
</style>
