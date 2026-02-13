<template>
  <el-container style="height: 100vh">
    <el-header height="60px">
      <div class="header">
        <div class="title">声纹门禁系统 · 后台仪表盘</div>
        <div class="header-actions">
          <el-button type="primary" @click="refreshAll" :loading="loading">
            刷新数据
          </el-button>
          <el-button @click="handleLogout">退出登录</el-button>
        </div>
      </div>
    </el-header>
    <el-main>
      <el-scrollbar style="height: 100%">
        <el-row :gutter="16">
          <el-col :span="4" v-for="card in summaryCards" :key="card.key">
            <el-card shadow="hover">
              <div class="card-label">{{ card.label }}</div>
              <div class="card-value">{{ card.value }}</div>
            </el-card>
          </el-col>
        </el-row>

        <el-row :gutter="16" style="margin-top: 16px">
          <el-col :span="18">
            <el-card shadow="never">
              <template #header>验证 / 注册趋势</template>
              <div ref="lineChartRef" style="width: 100%; height: 340px"></div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="never">
              <template #header>验证结果分布</template>
              <div ref="pieChartRef" style="width: 100%; height: 260px"></div>
            </el-card>
            <el-card shadow="never" style="margin-top: 16px">
              <template #header>识别阈值</template>
              <div class="threshold-box">
                <div class="threshold-row">
                  <span class="threshold-label">当前</span>
                  <span class="threshold-text">{{ threshold.toFixed(2) }}</span>
                </div>
                <el-slider
                  v-model="thresholdDraft"
                  :min="0.3"
                  :max="0.9"
                  :step="0.01"
                  style="margin-top: 8px"
                />
                <div class="threshold-row">
                  <span class="threshold-label">新值</span>
                  <span class="threshold-text">{{ thresholdDraft.toFixed(2) }}</span>
                </div>
                <el-button
                  type="primary"
                  size="small"
                  style="margin-top: 10px"
                  :loading="savingThreshold"
                  @click="handleSaveThreshold"
                >
                  保存阈值
                </el-button>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <el-row :gutter="16" style="margin-top: 16px">
          <el-col :span="24">
            <el-card shadow="never">
              <template #header>
                <div class="log-header">
                  <span>验证日志</span>
                  <el-form
                    :inline="true"
                    :model="logFilters"
                    size="small"
                    class="log-filter-form"
                  >
                    <el-form-item label="预测用户">
                      <el-input
                        v-model="logFilters.predicted"
                        placeholder="predicted"
                        clearable
                      />
                    </el-form-item>
                    <el-form-item label="结果">
                      <el-select
                        v-model="logFilters.result"
                        placeholder="全部"
                        clearable
                        style="width: 110px"
                      >
                        <el-option label="ACCEPT" value="ACCEPT" />
                        <el-option label="REJECT" value="REJECT" />
                      </el-select>
                    </el-form-item>
                    <el-form-item label="日期">
                      <el-date-picker
                        v-model="logFilters.dates"
                        type="daterange"
                        range-separator="至"
                        start-placeholder="开始日期"
                        end-placeholder="结束日期"
                        value-format="YYYY-MM-DD"
                      />
                    </el-form-item>
                    <el-form-item>
                      <el-button type="primary" @click="handleLogSearch">
                        查询
                      </el-button>
                      <el-button @click="handleLogReset">重置</el-button>
                      <el-button
                        type="danger"
                        plain
                        @click="handleDeleteSelectedLogs"
                      >
                        删除选中
                      </el-button>
                    </el-form-item>
                  </el-form>
                </div>
              </template>
              <el-table
                :data="logs"
                border
                style="width: 100%"
                size="small"
                row-key="id"
                @selection-change="handleLogSelectionChange"
              >
                <el-table-column type="selection" width="44" />
                <el-table-column prop="timestamp" label="时间" width="180" />
                <el-table-column
                  prop="predicted_user"
                  label="预测用户"
                  width="140"
                />
                <el-table-column prop="score" label="得分" width="100" />
                <el-table-column prop="threshold" label="阈值" width="80" />
                <el-table-column prop="result" label="结果" width="90" />
                <el-table-column prop="door_state" label="门状态" width="90" />
                <el-table-column
                  prop="client_ip"
                  label="客户端IP"
                  width="140"
                />
                <el-table-column
                  prop="error_msg"
                  label="错误信息"
                  min-width="200"
                  show-overflow-tooltip
                />
              </el-table>
            </el-card>
          </el-col>
        </el-row>
        <el-row style="margin-top: 8px">
          <el-col :span="24" style="text-align: right">
            <el-pagination
              layout="prev, pager, next, jumper"
              background
              :page-size="logPageSize"
              :current-page="logPage"
              :total="logTotal"
              @current-change="handleLogPageChange"
            />
          </el-col>
        </el-row>
      </el-scrollbar>
    </el-main>
  </el-container>
</template>

<script setup>
import { onMounted, onUnmounted, ref, computed } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import * as echarts from "echarts";
import {
  fetchDashboard,
  fetchStatsEcharts,
  fetchLogs,
  deleteLogs,
  fetchThreshold,
  updateThreshold,
  setAuthToken
} from "../api";

const router = useRouter();

const loading = ref(false);
const summary = ref(null);
const stats = ref(null);
const logs = ref([]);
const logTotal = ref(0);
const logPage = ref(1);
const logPageSize = ref(20);
const logSelectedIds = ref([]);
const logFilters = ref({
  actor: "",
  predicted: "",
  result: "",
  dates: []
});

const threshold = ref(0.7);
const thresholdDraft = ref(0.7);
const savingThreshold = ref(false);

const lineChartRef = ref(null);
const pieChartRef = ref(null);
let lineChart;
let pieChart;

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

function initCharts() {
  if (lineChartRef.value && !lineChart) {
    lineChart = echarts.init(lineChartRef.value);
  }
  if (pieChartRef.value && !pieChart) {
    pieChart = echarts.init(pieChartRef.value);
  }
}

function updateCharts() {
  if (!stats.value) return;
  const xAxis = stats.value.xAxis || [];
  const s = stats.value.series || {};
  const totals = s.verify_total || [];
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
    pieChart.setOption({
      tooltip: { trigger: "item" },
      legend: { orient: "vertical", left: "left" },
      series: [
        {
          type: "pie",
          radius: "70%",
          data: stats.value.pie || []
        }
      ]
    });
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

function handleLogout() {
  localStorage.removeItem("token");
  setAuthToken(null);
  router.push("/login");
}

function handleResize() {
  if (lineChart) lineChart.resize();
  if (pieChart) pieChart.resize();
}

onMounted(() => {
  initCharts();
  refreshAll();
  window.addEventListener("resize", handleResize);
});

onUnmounted(() => {
  window.removeEventListener("resize", handleResize);
  if (lineChart) {
    lineChart.dispose();
    lineChart = null;
  }
  if (pieChart) {
    pieChart.dispose();
    pieChart = null;
  }
});
</script>

<style scoped>
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.title {
  font-size: 18px;
  font-weight: 600;
}

.card-label {
  font-size: 13px;
  color: #666;
}

.card-value {
  margin-top: 8px;
  font-size: 20px;
  font-weight: 600;
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
}

.log-filter-form {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px 8px;
}
</style>
