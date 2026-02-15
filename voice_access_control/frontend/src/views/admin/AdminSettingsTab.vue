<template>
  <el-row :gutter="16">
    <el-col :span="24">
      <el-card shadow="never" class="panel-card">
        <template #header>
          <div class="settings-header">
            <div>
              <div class="settings-title">日志与审计</div>
              <div class="card-subtitle">记录管理员列表访问与安全事件</div>
            </div>
            <div class="settings-actions">
              <el-button @click="onLoadAdminAccessLogs">刷新</el-button>
            </div>
          </div>
        </template>
        <el-table :data="adminAccessLogs" size="small" stripe :loading="adminAccessLogsLoading">
          <el-table-column prop="user_username" label="操作者" min-width="120" />
          <el-table-column label="结果" min-width="100">
            <template #default="{ row }">
              <el-tag :type="row.success ? 'success' : 'danger'">
                {{ row.success ? "成功" : "失败" }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="client_ip" label="IP" min-width="140" />
          <el-table-column label="时间" min-width="160">
            <template #default="{ row }">
              {{ row.created_at ? formatDateTime(row.created_at) : "--" }}
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </el-col>
    <el-col :span="24">
      <el-card shadow="never" class="panel-card">
        <template #header>
          <div class="settings-header">
            <div>
              <div class="settings-title">验证策略</div>
              <div class="card-subtitle">阈值策略与规则提示</div>
            </div>
          </div>
        </template>
        <div class="threshold-box">
          <div class="threshold-row">
            <span class="threshold-label">当前阈值</span>
            <span class="threshold-text">{{ threshold.toFixed(2) }}</span>
          </div>
          <el-slider
            :model-value="thresholdDraft"
            :min="0.3"
            :max="0.9"
            :step="0.01"
            style="margin-top: 8px"
            @update:model-value="onThresholdDraftChange"
          />
          <div class="threshold-row">
            <span class="threshold-label">新阈值</span>
            <span class="threshold-text">{{ thresholdDraft.toFixed(2) }}</span>
          </div>
          <div class="settings-actions" style="margin-top: 10px">
            <el-button type="primary" size="small" :loading="savingThreshold" @click="onSaveThreshold">
              保存阈值
            </el-button>
          </div>
        </div>
      </el-card>
    </el-col>
    <el-col :span="24">
      <el-card shadow="never" class="panel-card">
        <template #header>
          <div class="settings-header">
            <div>
              <div class="settings-title">数据维护</div>
              <div class="card-subtitle">缓存、日志与模型文件维护</div>
            </div>
          </div>
        </template>
        <div class="maintenance-list">
          <div class="maintenance-item">
            <span>清理旧验证日志</span>
            <el-tag type="info">待接入</el-tag>
          </div>
          <div class="maintenance-item">
            <span>模型文件完整性检查</span>
            <el-tag type="info">待接入</el-tag>
          </div>
          <div class="maintenance-item">
            <span>缓存与临时文件整理</span>
            <el-tag type="info">待接入</el-tag>
          </div>
        </div>
      </el-card>
    </el-col>
  </el-row>
</template>

<script setup>
defineProps({
  adminAccessLogs: { type: Array, required: true },
  adminAccessLogsLoading: { type: Boolean, required: true },
  formatDateTime: { type: Function, required: true },
  threshold: { type: Number, required: true },
  thresholdDraft: { type: Number, required: true },
  savingThreshold: { type: Boolean, required: true },
  onLoadAdminAccessLogs: { type: Function, required: true },
  onThresholdDraftChange: { type: Function, required: true },
  onSaveThreshold: { type: Function, required: true }
});
</script>
