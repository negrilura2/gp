<template>
  <el-row :gutter="16">
    <el-col :span="24">
      <el-card shadow="never" class="panel-card">
        <template #header>
          <div class="log-header">
            <div class="log-title">
              <div>验证日志</div>
              <div class="card-subtitle">按用户、结果和日期范围筛选</div>
            </div>
            <div class="log-actions">
              <el-button type="primary" @click="onLogSearch">查询</el-button>
              <el-button @click="onLogReset">重置</el-button>
              <el-button type="danger" plain @click="onDeleteSelectedLogs">
                删除选中
              </el-button>
            </div>
          </div>
          <el-form :inline="true" :model="logFilters" size="small" class="log-filter-form">
            <el-form-item label="预测用户">
              <el-input v-model="logFilters.predicted" placeholder="predicted" clearable />
            </el-form-item>
            <el-form-item label="结果">
              <el-select v-model="logFilters.result" placeholder="全部" clearable style="width: 110px">
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
          </el-form>
        </template>
        <div class="log-table-wrap" :ref="logTableWrapRef">
          <el-table
            :data="logs"
            border
            style="width: 100%"
            size="small"
            row-key="id"
            :height="logTableHeight"
            @selection-change="onLogSelectionChange"
          >
            <el-table-column type="selection" width="44" />
            <el-table-column label="时间" width="180">
              <template #default="{ row }">
                <span class="time-text">{{ formatDateTime(row.timestamp) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="predicted_user" label="预测用户" width="140" />
            <el-table-column prop="score" label="得分" width="100" />
            <el-table-column prop="threshold" label="阈值" width="80" />
            <el-table-column prop="result" label="结果" width="90" />
            <el-table-column prop="door_state" label="门状态" width="90" />
            <el-table-column prop="client_ip" label="客户端IP" width="140" />
            <el-table-column prop="error_msg" label="错误信息" min-width="200" show-overflow-tooltip />
          </el-table>
        </div>
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
        @current-change="onLogPageChange"
      />
    </el-col>
  </el-row>
</template>

<script setup>
defineProps({
  logs: { type: Array, required: true },
  logTotal: { type: Number, required: true },
  logPage: { type: Number, required: true },
  logPageSize: { type: Number, required: true },
  logTableHeight: { type: Number, required: true },
  logTableWrapRef: { type: Function, required: true },
  logFilters: { type: Object, required: true },
  formatDateTime: { type: Function, required: true },
  onLogSearch: { type: Function, required: true },
  onLogReset: { type: Function, required: true },
  onDeleteSelectedLogs: { type: Function, required: true },
  onLogSelectionChange: { type: Function, required: true },
  onLogPageChange: { type: Function, required: true }
});
</script>
