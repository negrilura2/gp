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
            <div>
              <div>清理旧验证日志</div>
              <div class="card-subtitle">默认清理 30 天前的验证与注册日志</div>
            </div>
            <div class="settings-actions">
              <el-button size="small" :loading="maintenanceLogsLoading" @click="onCleanVerifyLogs">
                执行
              </el-button>
            </div>
          </div>
          <div v-if="maintenanceLogsResult" class="card-subtitle">
            已清理验证日志 {{ maintenanceLogsResult.verify_deleted }} 条，注册日志
            {{ maintenanceLogsResult.enroll_deleted }} 条
          </div>
          <div class="maintenance-item">
            <div>
              <div>模型文件完整性检查</div>
              <div class="card-subtitle">检查模型文件是否存在、是否为空</div>
            </div>
            <div class="settings-actions">
              <el-button size="small" :loading="maintenanceModelsLoading" @click="onCheckModels">
                检查
              </el-button>
            </div>
          </div>
          <div v-if="maintenanceModelsResult" class="card-subtitle">
            当前模型 {{ maintenanceModelsResult.current || "未设置" }}，
            {{ maintenanceModelsResult.current_exists ? "可用" : "不可用" }}，
            无效文件 {{ maintenanceModelsResult.invalid_count }} 个
          </div>
          <div class="maintenance-item">
            <div>
              <div>缓存与临时文件整理</div>
              <div class="card-subtitle">默认清理 7 天前录音与报告文件</div>
            </div>
            <div class="settings-actions">
              <el-button size="small" :loading="maintenanceCacheLoading" @click="onCleanCache">
                执行
              </el-button>
            </div>
          </div>
          <div v-if="maintenanceCacheResult" class="card-subtitle">
            已清理 {{ maintenanceCacheResult.deleted }} 个文件，释放
            {{ maintenanceCacheResult.freed_bytes }} 字节
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
  maintenanceLogsLoading: { type: Boolean, required: true },
  maintenanceModelsLoading: { type: Boolean, required: true },
  maintenanceCacheLoading: { type: Boolean, required: true },
  maintenanceLogsResult: { type: Object, default: null },
  maintenanceModelsResult: { type: Object, default: null },
  maintenanceCacheResult: { type: Object, default: null },
  onLoadAdminAccessLogs: { type: Function, required: true },
  onThresholdDraftChange: { type: Function, required: true },
  onSaveThreshold: { type: Function, required: true },
  onCleanVerifyLogs: { type: Function, required: true },
  onCheckModels: { type: Function, required: true },
  onCleanCache: { type: Function, required: true }
});
</script>
