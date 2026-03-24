<template>
  <div class="dashboard-container">
    <!-- Grok-style Navigation Bar -->
    <nav class="grok-nav">
      <div class="nav-left">
        <div class="nav-logo">
          <span class="logo-symbol">///</span>
          <span class="logo-text">VOICE ACCESS</span>
        </div>
      </div>
      
      <div class="nav-center">
        <button 
          v-for="tab in tabs" 
          :key="tab.key"
          class="nav-item" 
          :class="{ active: activeTab === tab.key }"
          @click="handleNavChange(tab.key)"
        >
          {{ tab.label }}
        </button>
      </div>

      <div class="nav-right">
        <el-button class="grok-btn-action" @click="refreshAll" :loading="loading">
          REFRESH
        </el-button>
        <el-button class="grok-btn-ghost" @click="handleLogout">
          LOGOUT
        </el-button>
      </div>
    </nav>

    <!-- Main Content Area -->
    <div class="dashboard-main">
      <div class="content-wrapper">
        
        <!-- Overview Tab -->
        <div v-show="activeTab === 'overview'" class="tab-content fade-in">
            <div class="overview-grid">
              <!-- 1. Core Metrics Cards -->
              <div class="stat-cards">
                <el-card v-for="card in summaryCards" :key="card.title" shadow="hover" class="stat-card">
                  <div class="stat-value">{{ card.value }}</div>
                  <div class="stat-title">{{ card.title }}</div>
                  <div class="stat-desc" v-if="card.desc">{{ card.desc }}</div>
                </el-card>
              </div>

              <!-- 2. Charts Area -->
              <div class="charts-grid">
                <div class="chart-col">
                  <el-card shadow="hover" header="AI INTENT DISTRIBUTION">
                    <div ref="pieChartRef" style="height: 300px;"></div>
                  </el-card>
                </div>
                <div class="chart-col">
                   <el-card shadow="hover" header="DECISION SOURCE (EDGE vs CLOUD)">
                     <div ref="sourceChartRef" style="height: 300px;"></div>
                   </el-card>
                </div>
              </div>
              
              <div class="chart-row">
                <el-card shadow="hover" header="DAILY AI INTERACTIONS">
                  <div ref="lineChartRef" style="height: 350px;"></div>
                </el-card>
              </div>

              <div class="chart-row">
                 <el-card shadow="hover" header="SYSTEM LATENCY HEATMAP (LAST 50)">
                    <div ref="latencyChartRef" style="height: 300px;"></div>
                 </el-card>
              </div>
           </div>
        </div>

        <!-- Logs Tab -->
        <div v-show="activeTab === 'logs'" class="tab-content fade-in">
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
        </div>

        <!-- Users Tab -->
        <div v-show="activeTab === 'users'" class="tab-content fade-in">
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
        </div>

        <!-- Model Tab -->
        <div v-show="activeTab === 'model'" class="tab-content fade-in">
          <AdminModelTab
            :model-metrics="modelMetrics"
            :model-metrics-model="modelMetricsModel"
            :model-current="modelCurrent"
            :model-evaluating="modelEvaluating"
            :model-metrics-loading="modelMetricsLoading"
            :model-metrics-error="modelMetricsError"
            :eval-norm-method="evalNormMethod"
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
            :on-eval-norm-method-change="handleEvalNormMethodChange"
            :on-eval-collapse="handleEvalCollapse"
            :on-eval-card-click="handleEvalCardClick"
            :tsne-image-url="tsneImageUrl"
          />
        </div>

        <!-- Settings Tab -->
        <div v-show="activeTab === 'settings'" class="tab-content fade-in">
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
        </div>

        <!-- Admins Tab -->
        <div v-show="activeTab === 'admins'" class="tab-content fade-in">
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
            :on-admin-batch-reset-password="handleAdminBatchResetPassword"
            :on-admin-selection-change="handleAdminSelectionChange"
            :on-edit-admin="onEditAdmin"
            :on-reset-admin-password="onResetAdminPassword"
            :on-admin-toggle="handleAdminToggle"
          />
        </div>
        
      </div>
    </div>

    <!-- Dialogs (Keep existing) -->
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
  setAuthToken,
  fetchEmbeddingImage
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

const emptyModelMetrics = () => ({
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
const modelMetricsRaw = ref(emptyModelMetrics());
const modelMetricsNorm = ref(null);
const evalNormMethod = ref("none");

const modelMetrics = computed(() => {
  // Logic:
  // 1. If evalNormMethod is 'none', show raw.
  // 2. If evalNormMethod is not 'none', try to show norm.
  //    But check if the available norm data actually matches the selected method?
  //    The backend only stores ONE score_norm result (the latest one).
  //    So if modelMetricsNorm exists, we should check its method.
  //    However, for simplicity and better UX as requested:
  //    "If Z/T/S-Norm is selected, show normalized data (if not evaluated, show raw or hint)"
  //    Let's just show norm if it exists, otherwise fallback to raw (or empty).
  
  if (evalNormMethod.value !== "none" && modelMetricsNorm.value) {
     // Ideally we should check modelMetricsNorm.value.metrics.method === evalNormMethod.value
     // But let's just return it for now, user will see the data.
     // If they selected S-Norm but data is Z-Norm, it might be confusing, but
     // usually they will click "Evaluate" immediately after selecting.
     return modelMetricsNorm.value;
  }
  return modelMetricsRaw.value;
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

const tabs = [
  { key: "overview", label: "OVERVIEW" },
  { key: "logs", label: "LOGS" },
  { key: "users", label: "USERS" },
  { key: "model", label: "MODEL" },
  { key: "settings", label: "SETTINGS" },
  { key: "admins", label: "ADMINS" }
];

function handleNavChange(key) {
  activeTab.value = key;
  handleTabChange();
}

// const lineChartRef = ref(null); // Removed redundant declaration
// const pieChartRef = ref(null); // Removed redundant declaration
// let lineChart; // Removed redundant declaration
// let pieChart; // Removed redundant declaration

// const setLineChartRef = (el) => {
//   lineChartRef.value = el;
// };
// const setPieChartRef = (el) => {
//   pieChartRef.value = el;
// };
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
    { 
      title: "用户总数", 
      value: sum.users_total,
      desc: "已注册系统并完成声纹录入的用户"
    },
    { 
      title: "已注册用户", 
      value: sum.users_enrolled,
      desc: "声纹库中活跃的身份ID"
    },
    { 
      title: "验证总次数", 
      value: sum.verify_total,
      desc: "历史所有声纹验证请求"
    },
    {
      title: "验证通过率",
      value: sum.verify_total ? ((sum.verify_accept_rate || 0) * 100).toFixed(1) + "%" : "0%",
      desc: "系统接受的合法访问请求比例"
    },
    {
      title: "默认阈值",
      value: sum.threshold_default,
      desc: "当前系统的全局安全判定阈值"
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
  },
  {
    key: "tsne",
    title: "t-SNE 聚类",
    subtitle: "嵌入空间可视化",
    detail: "将高维声纹特征降维至 2D 平面，展示不同说话人的聚类效果。需运行 plot_embedding.py。",
    note: "不同颜色的点代表不同说话人，簇的分离度越高，模型区分能力越强。",
    placeholder: "暂无 t-SNE 图片",
    thumb: "t-SNE 缩略图"
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

const tsneImageUrl = ref("");

async function loadTsneImage() {
  try {
    const res = await fetchEmbeddingImage("tsne", evalNormMethod.value || "none");
    if (tsneImageUrl.value) {
      URL.revokeObjectURL(tsneImageUrl.value);
    }
    tsneImageUrl.value = URL.createObjectURL(res.data);
  } catch (e) {
    tsneImageUrl.value = "";
  }
}

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
      await loadModelMetrics({ autoDetect: false });
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

async function handleEvalNormMethodChange(value) {
  evalNormMethod.value = value;
  await loadModelMetrics({ autoDetect: false });
  nextTick(() => {
    updateRocChart();
    updateEvalThumbCharts();
    updateEvalDetailChart();
  });
}

function updateCharts() {
  if (!stats.value) return;
  
  // New API Structure:
  // stats.value.daily_trends = [{date, total, avg_score, ai_interactions}, ...]
  // stats.value.intent_distribution = [{intent, count}, ...]
  // stats.value.source_distribution = [{source, count}, ...]
  // stats.value.latency_history = [{timestamp, latency_ms, source, intent}, ...]

  const daily = stats.value.daily_trends || [];
  const xAxis = daily.map(d => d.date);
  const totalSeries = daily.map(d => d.total);
  const aiSeries = daily.map(d => d.ai_interactions || 0);

  // 1. Line Chart: Daily Trends (Total vs AI Interactions)
  if (lineChart) {
    lineChart.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: "axis" },
      legend: { data: ["总交互次数", "AI 智能交互"], bottom: 0, textStyle: { color: '#94a3b8' } },
      grid: { left: 40, right: 40, top: 40, bottom: 40 },
      xAxis: {
        type: "category",
        data: xAxis,
        boundaryGap: true,
        axisLine: { lineStyle: { color: "#334155" } },
        axisLabel: { color: "#94a3b8" }
      },
      yAxis: {
        type: "value",
        minInterval: 1,
        splitLine: { lineStyle: { type: "dashed", color: "#1e293b" } },
        axisLabel: { color: "#94a3b8" }
      },
      series: [
        {
          name: "总交互次数",
          type: "line",
          smooth: true,
          symbol: "circle",
          symbolSize: 8,
          data: totalSeries,
          itemStyle: { color: "#3b82f6" },
          areaStyle: {
            color: {
              type: "linear",
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(59, 130, 246, 0.3)" },
                { offset: 1, color: "rgba(59, 130, 246, 0.05)" }
              ]
            }
          }
        },
        {
          name: "AI 智能交互",
          type: "bar",
          barMaxWidth: 30,
          data: aiSeries,
          itemStyle: { 
            color: "#10b981",
            borderRadius: [4, 4, 0, 0]
          }
        }
      ]
    });
  }

  // 2. Pie Chart: Intent Distribution
  if (pieChart) {
    const intentData = (stats.value.intent_distribution || [])
      .filter(item => item.intent !== "verify_only")
      .map(item => ({
        name: formatIntentLabel(item.intent),
        value: item.count
      }));
    
    pieChart.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: "item" },
      legend: { bottom: 0, textStyle: { color: '#94a3b8' } },
      series: [
        {
          name: "意图分布",
          type: "pie",
          radius: ["40%", "70%"],
          center: ["50%", "45%"],
          itemStyle: {
            borderRadius: 5,
            borderColor: "#0f172a",
            borderWidth: 2
          },
          label: { color: '#94a3b8' },
          data: intentData
        }
      ]
    });
  }

  // 3. Source Chart (New): Edge vs Cloud
  if (sourceChart) {
    const sourceData = (stats.value.source_distribution || []).map(item => ({
      name: formatSourceLabel(item.source),
      value: item.count
    }));

    sourceChart.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: "item" },
      legend: { bottom: 0, textStyle: { color: '#94a3b8' } },
      series: [
        {
          name: "决策来源",
          type: "pie",
          radius: "60%",
          center: ["50%", "45%"],
          data: sourceData,
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)',
            borderColor: "#0f172a",
            borderWidth: 1
          },
          label: { color: '#94a3b8' }
        }
      ]
    });
  }

  // 4. Latency Chart (New): Heatmap/Scatter
  if (latencyChart) {
    const latencyData = (stats.value.latency_history || []).reverse(); // Oldest first
    const xTime = latencyData.map(d => d.timestamp.substring(11, 19)); // HH:MM:SS
    const yLatency = latencyData.map(d => d.latency_ms);
    
    latencyChart.setOption({
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        formatter: function (params) {
          const idx = params[0].dataIndex;
          const item = latencyData[idx];
          return `${item.timestamp}<br/>
                  耗时: ${item.latency_ms}ms<br/>
                  来源: ${formatSourceLabel(item.source)}<br/>
                  意图: ${formatIntentLabel(item.intent)}`;
        }
      },
      grid: { left: 50, right: 20, top: 30, bottom: 30 },
      xAxis: {
        type: 'category',
        data: xTime,
        boundaryGap: false,
        axisLine: { lineStyle: { color: "#334155" } },
        axisLabel: { color: "#94a3b8" }
      },
      yAxis: {
        type: 'value',
        name: '耗时 (ms)',
        nameTextStyle: { color: '#94a3b8' },
        splitLine: { lineStyle: { type: 'dashed', color: "#1e293b" } },
        axisLabel: { color: "#94a3b8" }
      },
      visualMap: {
        show: false,
        min: 0,
        max: 3000,
        inRange: { color: ['#10b981', '#f59e0b', '#ef4444'] }
      },
      series: [{
        type: 'line',
        data: yLatency,
        symbolSize: 6,
        lineStyle: { width: 1 },
        areaStyle: { opacity: 0.2 }
      }]
    });
  }
}

// Helpers
function formatIntentLabel(key) {
  const map = {
    'open_door': '开门指令',
    'turn_on_light': '开灯指令',
    'query_knowledge': '知识问答',
    'verify_only': '门禁验证（传统接口）',
    'chat': '闲聊',
    'agent_action': '智能体动作',
    'command': '本地指令'
  };
  return map[key] || key;
}

function formatSourceLabel(key) {
  const map = {
    'local_nlu': '边缘端 (Edge)',
    'cloud_agent': '云端 (Cloud)',
    'legacy': '传统接口'
  };
  return map[key] || key;
}

let lineChart = null;
let pieChart = null;
let sourceChart = null;
let latencyChart = null;
const lineChartRef = ref(null);
const pieChartRef = ref(null);
const sourceChartRef = ref(null);
const latencyChartRef = ref(null);

function setLineChartRef(el) { lineChartRef.value = el; }
function setPieChartRef(el) { pieChartRef.value = el; }
// source/latency refs are bound directly in template via ref="sourceChartRef"

function initCharts() {
  const theme = 'dark';
  if (lineChartRef.value && !lineChart) {
    lineChart = echarts.init(lineChartRef.value, theme, { renderer: 'svg' });
  }
  if (pieChartRef.value && !pieChart) {
    pieChart = echarts.init(pieChartRef.value, theme, { renderer: 'svg' });
  }
  if (sourceChartRef.value && !sourceChart) {
    sourceChart = echarts.init(sourceChartRef.value, theme, { renderer: 'svg' });
  }
  if (latencyChartRef.value && !latencyChart) {
    latencyChart = echarts.init(latencyChartRef.value, theme, { renderer: 'svg' });
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
  if (key === "tsne") {
    return !!tsneImageUrl.value;
  }
  return false;
}

function getEvalChartOption(key, compact = false) {
  const metrics = modelMetrics.value;
  // xAI Style Constants
  const xAI = {
    bg: compact ? 'transparent' : '#050505', // Deep black
    grid: '#1a1a1a', // Very subtle grid
    textMain: '#e5e7eb', // Cool white
    textSub: '#6b7280', // Cool gray
    accent: '#00FFAA', // Cyan/Green glow
    accentGlow: 'rgba(0, 255, 170, 0.25)',
    secondary: '#7B5EFF', // Purple glow
    secondaryGlow: 'rgba(123, 94, 255, 0.25)',
    font: 'Inter, system-ui, sans-serif'
  };

  if (key === "det") {
    const fpr = metrics.det?.fpr || [];
    const fnr = metrics.det?.fnr || [];
    const data = fpr.map((x, idx) => [x, fnr[idx] ?? 0]);
    return {
      backgroundColor: xAI.bg,
      grid: compact ? { left: 0, right: 0, top: 0, bottom: 0 } : { left: 60, right: 40, top: 40, bottom: 60 },
      tooltip: {
         trigger: 'axis',
         backgroundColor: 'rgba(0,0,0,0.8)',
         borderColor: '#333',
         textStyle: { color: xAI.textMain }
      },
      xAxis: {
        type: "log",
        name: compact ? "" : "FPR (False Positive Rate)",
        min: 1e-4,
        max: 1,
        logBase: 10,
        axisLabel: compact ? { show: false } : { 
            color: xAI.textSub, 
            formatter: (v) => v < 0.01 ? v.toExponential(0) : `${v*100}%` 
        },
        nameLocation: "middle",
        nameGap: 35,
        nameTextStyle: { color: xAI.textSub },
        axisLine: { show: false },
        splitLine: { show: !compact, lineStyle: { color: xAI.grid } }
      },
      yAxis: {
        type: "log",
        name: compact ? "" : "FNR (False Negative Rate)",
        min: 1e-4,
        max: 1,
        logBase: 10,
        axisLabel: compact ? { show: false } : { 
            color: xAI.textSub,
            formatter: (v) => v < 0.01 ? v.toExponential(0) : `${v*100}%`
        },
        nameLocation: "middle",
        nameGap: 45,
        nameTextStyle: { color: xAI.textSub },
        axisLine: { show: false },
        splitLine: { show: !compact, lineStyle: { color: xAI.grid } }
      },
      series: [
        {
          type: "line",
          smooth: true,
          symbol: "none",
          lineStyle: { 
             color: xAI.accent, 
             width: compact ? 1.5 : 2.5,
             shadowColor: xAI.accent,
             shadowBlur: compact ? 0 : 10
          },
          data
        },
        // Reference line
        {
            type: "line",
            data: [[1e-4, 1e-4], [1, 1]],
            lineStyle: { type: 'dashed', color: '#333', width: 1 },
            symbol: 'none'
        }
      ]
    };
  }
  if (key === "mindcf") {
    const thresholds = metrics.mindcf_data?.thresholds || [];
    const dcf = metrics.mindcf_data?.dcf || [];
    // Downsample for visual clarity if too many points
    const step = Math.max(1, Math.floor(thresholds.length / 200));
    const data = [];
    for(let i=0; i<thresholds.length; i+=step) {
        if(Number.isFinite(thresholds[i]) && Number.isFinite(dcf[i])) {
            data.push([thresholds[i], dcf[i]]);
        }
    }
    
    return {
      backgroundColor: xAI.bg,
      grid: compact ? { left: 0, right: 0, top: 0, bottom: 0 } : { left: 60, right: 40, top: 40, bottom: 60 },
      tooltip: {
         trigger: 'axis',
         backgroundColor: 'rgba(0,0,0,0.8)',
         borderColor: '#333',
         textStyle: { color: xAI.textMain }
      },
      xAxis: {
        type: "value",
        name: compact ? "" : "Threshold",
        axisLabel: compact ? { show: false } : { color: xAI.textSub },
        nameLocation: "middle",
        nameGap: 30,
        nameTextStyle: { color: xAI.textSub },
        axisLine: { show: false },
        splitLine: { show: false }
      },
      yAxis: {
        type: "value",
        name: compact ? "" : "minDCF",
        axisLabel: compact ? { show: false } : { color: xAI.textSub },
        nameLocation: "middle",
        nameGap: 40,
        nameTextStyle: { color: xAI.textSub },
        axisLine: { show: false },
        splitLine: { show: !compact, lineStyle: { color: xAI.grid } }
      },
      series: [
        {
          type: "line",
          smooth: true,
          symbol: "none",
          lineStyle: { 
              color: xAI.secondary, 
              width: compact ? 1.5 : 2.5,
              shadowColor: xAI.secondary,
              shadowBlur: compact ? 0 : 8
          },
          areaStyle: compact ? null : {
              color: {
                  type: 'linear',
                  x: 0, y: 0, x2: 0, y2: 1,
                  colorStops: [{offset: 0, color: xAI.secondaryGlow}, {offset: 1, color: 'transparent'}]
              }
          },
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
    
    return {
      backgroundColor: xAI.bg,
      grid: compact ? { left: 0, right: 0, top: 0, bottom: 0 } : { left: 60, right: 40, top: 40, bottom: 60 },
      legend: compact ? { show: false } : { top: 10, textStyle: { color: xAI.textSub } },
      tooltip: {
         trigger: 'axis',
         backgroundColor: 'rgba(0,0,0,0.8)',
         borderColor: '#333',
         textStyle: { color: xAI.textMain }
      },
      xAxis: {
        type: "category",
        name: compact ? "" : "Score",
        data: centers.map((v) => v.toFixed(2)),
        axisLabel: compact ? { show: false } : { 
            color: xAI.textSub,
            interval: 'auto'
        },
        nameLocation: "middle",
        nameGap: 35,
        nameTextStyle: { color: xAI.textSub },
        axisLine: { show: false },
        splitLine: { show: false }
      },
      yAxis: {
        type: "value",
        name: compact ? "" : "Count",
        axisLabel: compact ? { show: false } : { show: false },
        nameLocation: "middle",
        nameGap: 30,
        axisLine: { show: false },
        splitLine: { show: !compact, lineStyle: { color: xAI.grid } }
      },
      series: [
        {
          name: 'Target (Same)',
          type: "line",
          smooth: true,
          symbol: 'none',
          lineStyle: { color: xAI.accent, width: 2 },
          areaStyle: { opacity: 0.3, color: xAI.accent },
          data: same
        },
        {
          name: 'Non-Target (Diff)',
          type: "line",
          smooth: true,
          symbol: 'none',
          lineStyle: { color: xAI.secondary, width: 2 },
          areaStyle: { opacity: 0.3, color: xAI.secondary },
          data: diff
        }
      ]
    };
  }
  if (key === "calib") {
    const bins = metrics.calibration?.bins || [];
    const acc = metrics.calibration?.accuracy || [];
    const centers = bins.length > 1 ? bins.slice(0, -1).map((b, i) => (b + bins[i + 1]) / 2) : [];
    return {
      backgroundColor: xAI.bg,
      grid: compact ? { left: 0, right: 0, top: 0, bottom: 0 } : { left: 60, right: 40, top: 40, bottom: 60 },
      xAxis: {
        type: "value",
        name: compact ? "" : "Confidence",
        min: 0,
        max: 1,
        axisLabel: compact ? { show: false } : { color: xAI.textSub },
        nameLocation: "middle",
        nameGap: 30,
        axisLine: { show: false },
        splitLine: { show: false }
      },
      yAxis: {
        type: "value",
        name: compact ? "" : "Accuracy",
        min: 0,
        max: 1,
        axisLabel: compact ? { show: false } : { color: xAI.textSub },
        nameLocation: "middle",
        nameGap: 40,
        axisLine: { show: false },
        splitLine: { show: !compact, lineStyle: { color: xAI.grid } }
      },
      series: [
        {
          type: "line",
          symbol: "circle",
          symbolSize: compact ? 0 : 6,
          lineStyle: { color: xAI.textMain, width: 2 },
          itemStyle: { color: xAI.textMain, borderColor: xAI.bg, borderWidth: 2 },
          data: centers.map((x, i) => [x, acc[i] ?? 0])
        },
        {
          type: "line",
          symbol: "none",
          lineStyle: { color: '#333', type: "dashed" },
          data: [[0, 0], [1, 1]]
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

function buildRawMetrics(data) {
  return {
    auc: data.auc,
    eer: data.eer,
    threshold: data.threshold,
    threshold_eer: data.threshold_eer,
    threshold_mindcf: data.threshold_mindcf,
    mindcf: data.mindcf,
    p_target: data.p_target,
    c_miss: data.c_miss,
    c_fa: data.c_fa,
    threshold_default: data.threshold_default,
    threshold_diff: data.threshold_diff,
    fpr: data.fpr,
    tpr: data.tpr,
    thresholds: data.thresholds,
    det: data.det,
    mindcf_data: data.mindcf_data,
    score_dist: data.score_dist,
    calibration: data.calibration
  };
}

function buildNormMetrics(data) {
  const normPayload = data.score_norm;
  if (!normPayload) return null;
  return {
    auc: normPayload.metrics?.auc,
    eer: normPayload.metrics?.eer,
    threshold: normPayload.metrics?.threshold,
    threshold_eer: normPayload.metrics?.threshold_eer,
    threshold_mindcf: normPayload.metrics?.threshold_mindcf,
    mindcf: normPayload.metrics?.mindcf,
    p_target: normPayload.metrics?.p_target,
    c_miss: normPayload.metrics?.c_miss,
    c_fa: normPayload.metrics?.c_fa,
    threshold_default: data.threshold_default,
    threshold_diff: data.threshold_diff,
    fpr: normPayload.fpr,
    tpr: normPayload.tpr,
    thresholds: normPayload.thresholds,
    det: normPayload.det,
    mindcf_data: normPayload.mindcf_data,
    score_dist: normPayload.score_dist,
    calibration: normPayload.calibration
  };
}

async function loadModelMetrics({ autoDetect = true } = {}) {
  modelMetricsLoading.value = true;
  // Always try to load t-SNE image regardless of metrics success
  // Pass current norm method
  loadTsneImage();
  try {
    const methodsToTry =
      autoDetect && evalNormMethod.value === "none"
        ? ["snorm", "tnorm", "znorm", "none"]
        : [evalNormMethod.value];
    let res = null;
    let lastError = null;
    let usedMethod = null;
    for (const method of methodsToTry) {
      try {
        res = await fetchRocMetrics(method);
        usedMethod = method;
        break;
      } catch (e) {
        lastError = e;
        if (e.response?.status !== 404) {
          throw e;
        }
      }
    }
    if (!res) {
      throw lastError || new Error("模型指标未生成");
    }
    if (autoDetect && evalNormMethod.value === "none" && usedMethod && usedMethod !== "none") {
      evalNormMethod.value = usedMethod;
    }
    modelMetricsRaw.value = buildRawMetrics(res.data);
    modelMetricsNorm.value = buildNormMetrics(res.data);
    nextTick(() => {
      updateRocChart();
      updateEvalThumbCharts();
      updateEvalDetailChart();
    });
  } catch (e) {
    modelMetricsError.value = e.response?.data?.error || "模型指标未生成";
    modelMetricsRaw.value = emptyModelMetrics();
    modelMetricsNorm.value = null;
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
    const res = await evaluateRocMetrics(name, { norm_method: evalNormMethod.value });
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
    await loadModelMetrics({ autoDetect: false });
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
  if (key === "tsne") {
    loadTsneImage();
  }
  // FIX: Ensure data is passed and chart is updated
  nextTick(() => {
    // Reset detail chart first to ensure clean state
    resetEvalDetailChart();
    // Re-initialize
    const el = evalDetailChartRef.value;
    if (el) {
       evalDetailChart = ensureChart(el, evalDetailChart);
       updateEvalDetailChart();
    }
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
  if (sourceChart) sourceChart.resize();
  if (latencyChart) latencyChart.resize();
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
/* Dashboard Container - The Void */
.dashboard-container {
  min-height: 100vh;
  background-color: var(--bg-primary);
  color: var(--text-primary);
  font-family: var(--font-body);
}

/* Grok Navigation Bar */
.grok-nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border-color);
  z-index: 1000;
}

.nav-left {
  display: flex;
  align-items: center;
  width: 200px;
}

.nav-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 18px;
  letter-spacing: 0.05em;
  color: var(--text-primary);
}

.logo-symbol {
  font-size: 20px;
  color: var(--text-primary);
}

.nav-center {
  display: flex;
  align-items: center;
  gap: 8px;
}

.nav-item {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 500;
  padding: 8px 16px;
  cursor: pointer;
  transition: all 0.2s;
  border-radius: 4px;
  letter-spacing: 0.05em;
}

.nav-item:hover {
  color: var(--text-primary);
  background: var(--bg-surface-hover);
}

.nav-item.active {
  color: var(--text-primary);
  background: var(--bg-surface);
  box-shadow: 0 0 0 1px var(--border-color);
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 16px;
  width: 200px;
  justify-content: flex-end;
}

.grok-btn-action {
  background: var(--text-primary) !important;
  color: var(--bg-primary) !important;
  border: none !important;
  font-family: var(--font-mono) !important;
  font-weight: 600 !important;
  font-size: 12px !important;
  padding: 8px 16px !important;
  height: 32px !important;
  border-radius: 4px !important;
  letter-spacing: 0.05em !important;
}

.grok-btn-action:hover {
  background: #e4e4e7 !important;
  transform: translateY(-1px);
}

.grok-btn-ghost {
  background: transparent !important;
  color: var(--text-secondary) !important;
  border: 1px solid var(--border-color) !important;
  font-family: var(--font-mono) !important;
  font-weight: 500 !important;
  font-size: 12px !important;
  padding: 8px 16px !important;
  height: 32px !important;
  border-radius: 4px !important;
}

.grok-btn-ghost:hover {
  border-color: var(--text-primary) !important;
  color: var(--text-primary) !important;
}

/* Main Content */
.dashboard-main {
  padding-top: 88px; /* 64px nav + 24px padding */
  padding-left: 32px;
  padding-right: 32px;
  padding-bottom: 48px;
  min-height: 100vh;
}

.content-wrapper {
  max-width: 1600px;
  margin: 0 auto;
}

.fade-in {
  animation: fadeIn 0.4s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Grid Layouts */
.overview-grid {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.stat-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
}

.stat-card {
  display: flex;
  flex-direction: column;
  justify-content: center;
  /* Styles handled by theme.css overrides for el-card */
}

.stat-value {
  font-family: var(--font-display);
  font-size: 36px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: -0.02em;
  line-height: 1.1;
  margin-bottom: 8px;
}

.stat-title {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.stat-desc {
  font-size: 13px;
  color: var(--text-tertiary);
  margin-top: 4px;
}

.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.chart-col {
  display: flex;
  flex-direction: column;
}

.chart-row {
  width: 100%;
}

/* Thumbnails Fix */
/* Eval Tab Group (Button-like) */
.eval-tab-group {
  display: flex;
  gap: 12px;
  margin-top: 24px;
  margin-bottom: 24px;
}

.eval-tab-btn {
  padding: 8px 16px;
  background: transparent;
  border: 1px solid #333;
  border-radius: 20px; /* Pill shape */
  color: #6b7280;
  font-family: 'Inter', system-ui, sans-serif;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.eval-section-title {
  font-family: 'Inter', system-ui, sans-serif;
  font-size: 18px; /* 加大 */
  font-weight: 700; /* 加粗 */
  color: #e5e7eb;
  letter-spacing: -0.02em;
  margin-top: 32px;
  margin-bottom: 16px;
}

.metric-hint-title {
  font-family: 'Inter', system-ui, sans-serif;
  font-size: 18px; /* 加大 */
  font-weight: 700; /* 加粗 */
  color: #e5e7eb;
  letter-spacing: -0.02em;
  margin-bottom: 16px;
}

.eval-tab-btn:hover {
  border-color: #666;
  color: #e5e7eb;
}

.eval-tab-btn.is-active {
  background: #1a1a1a;
  border-color: #00FFAA;
  color: #00FFAA;
  box-shadow: 0 0 10px rgba(0, 255, 170, 0.15);
}

/* Eval Detail Inline View */
.eval-detail-inline {
  background: #0A0A0A;
  border: 1px solid #1a1a1a;
  border-radius: 8px;
  padding: 24px;
  margin-top: 24px;
}

.eval-detail-header-inline {
  margin-bottom: 24px;
}

.eval-detail-title-inline {
  font-family: 'Inter', system-ui, sans-serif;
  font-size: 18px;
  font-weight: 600;
  color: #e5e7eb;
  margin-bottom: 4px;
}

.eval-detail-subtitle-inline {
  font-size: 13px;
  color: #6b7280;
}

.eval-detail-canvas {
  width: 100%;
  height: 400px; /* Height for inline charts */
  background: transparent;
}

/* Override Element Plus Card for Dark Mode */
.panel-card {
  background: #0A0A0A !important;
  border: 1px solid #1a1a1a !important;
  color: #e5e7eb !important;
}

.panel-card .el-card__header {
  border-bottom: 1px solid #1a1a1a !important;
  padding: 24px 32px !important;
}

.panel-card .el-card__body {
  padding: 32px !important;
}

/* Metric Items */
.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 24px;
  margin-bottom: 32px;
}

.metric-item {
  display: flex;
  flex-direction: column;
}

.metric-label {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #6b7280;
  margin-bottom: 8px;
}

.metric-value {
  font-family: 'Inter', monospace;
  font-size: 24px;
  color: #e5e7eb;
  font-weight: 500;
}

.metric-value.highlight {
  color: #00FFAA;
  text-shadow: 0 0 10px rgba(0, 255, 170, 0.3);
}

/* Settings & Other Panels */
.settings-header, .model-header, .log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0; /* Header padding handles this */
}

.settings-title, .eval-title, .log-title {
  font-family: 'Inter', system-ui, sans-serif;
  font-size: 20px; /* 加大标题 */
  font-weight: 600;
  color: #e5e7eb;
  letter-spacing: -0.02em;
  margin-bottom: 6px;
}

.threshold-box {
  padding: 32px;
  background: var(--bg-surface);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
}

.threshold-text {
  font-family: var(--font-display);
  font-size: 32px;
  font-weight: 600;
  color: var(--text-primary);
}

/* Scrollbar within content */
.el-scrollbar__wrap {
  overflow-x: hidden;
}
</style>
