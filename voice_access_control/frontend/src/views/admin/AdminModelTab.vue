<template>
  <el-row :gutter="16">
    <el-col :span="12">
      <el-card shadow="never" class="panel-card">
        <template #header>
          <div class="model-header">
            <div>
              <div class="settings-title">模型指标</div>
              <div class="card-subtitle">
                评估模型：{{ modelMetricsModel || modelCurrent || "--" }}
                <span v-if="modelEvaluating">（评估中）</span>
              </div>
            </div>
            <div class="settings-actions">
              <span class="norm-label">选择归一化策略：</span>
              <el-select
                :model-value="evalNormMethod"
                @update:model-value="onEvalNormMethodChange"
                size="small"
                style="width: 110px; margin-right: 8px"
              >
                <el-option label="无 (None)" value="none" />
                <el-option label="Z-Norm" value="znorm" />
                <el-option label="T-Norm" value="tnorm" />
                <el-option label="S-Norm" value="snorm" />
              </el-select>
              <el-button :loading="modelMetricsLoading" @click="onLoadModelMetrics">刷新</el-button>
              <el-button type="primary" :loading="modelEvaluating" @click="onModelEvaluate">
                立即评估
              </el-button>
            </div>
          </div>
        </template>
        <div v-if="modelMetricsError" class="model-empty">
          {{ modelMetricsError }}
        </div>
        <div v-else class="metric-grid">
          <div class="metric-card">
            <div class="metric-card-label">AUC</div>
            <div class="metric-card-value">{{ formatMetric(modelMetrics.auc) }}</div>
          </div>
          <div class="metric-card">
            <div class="metric-card-label">EER</div>
            <div class="metric-card-value">{{ formatMetric(modelMetrics.eer) }}</div>
          </div>
          <div class="metric-card">
            <div class="metric-card-label">推荐阈值</div>
            <div class="metric-card-value">{{ formatMetric(modelMetrics.threshold) }}</div>
          </div>
          <div class="metric-card">
            <div class="metric-card-label">当前阈值</div>
            <div class="metric-card-value">{{ formatMetric(modelMetrics.threshold_default) }}</div>
          </div>
          <div class="metric-card">
            <div class="metric-card-label">FAR@当前阈值</div>
            <div class="metric-card-value">{{ formatPercent(rocDerived.far) }}</div>
          </div>
          <div class="metric-card">
            <div class="metric-card-label">FRR@当前阈值</div>
            <div class="metric-card-value">{{ formatPercent(rocDerived.frr) }}</div>
          </div>
        </div>
        <div class="metric-hint">
          <div class="metric-hint-title">指标说明</div>
          <div class="metric-hint-item">AUC：ROC 曲线下面积，越接近 1 越好</div>
          <div class="metric-hint-item">EER：等错误率，越低越好</div>
          <div class="metric-hint-item">TPR：通过率（真正率），越高越好</div>
          <div class="metric-hint-item">FPR：误识率（假接受率），越低越好</div>
          <div class="metric-hint-item">FAR：误识率（在当前阈值下的假接受率）</div>
          <div class="metric-hint-item">FRR：漏识率（在当前阈值下的假拒绝率）</div>
          <div class="metric-hint-item">虚线为随机猜测基线，曲线越靠左上越优</div>
        </div>
        <div class="roc-chart" :ref="rocChartRef"></div>
      </el-card>
    </el-col>
    <el-col :span="12">
      <div class="model-right-stack">
        <el-card shadow="never" class="panel-card">
          <template #header>
            <div class="model-header">
              <div>
                <div class="settings-title">模型切换</div>
                <div class="card-subtitle">切换后立即用于新的验证请求</div>
              </div>
              <el-button :loading="modelSwitching" @click="onLoadModelList">刷新</el-button>
            </div>
          </template>
          <div class="model-switch">
            <div class="metric-row">
              <span class="metric-label">当前模型</span>
              <span class="metric-value">{{ modelCurrent || "--" }}</span>
            </div>
            <el-select
              :model-value="modelTarget"
              placeholder="选择模型"
              style="width: 100%"
              @update:model-value="onModelTargetChange"
            >
              <el-option v-for="item in modelList" :key="item.name" :label="item.name" :value="item.name" />
            </el-select>
            <el-button
              type="primary"
              style="margin-top: 12px"
              :loading="modelSwitching"
              :disabled="!modelTarget"
              @click="onModelSwitch"
            >
              切换模型
            </el-button>
          </div>
        </el-card>
        <transition name="eval-expand" mode="out-in">
          <el-card v-if="activeEval" shadow="never" class="panel-card eval-detail-card">
            <template #header>
              <div class="model-header">
                <div>
                  <div class="settings-title">{{ activeEval.title }}</div>
                  <div class="card-subtitle">{{ activeEval.subtitle }}</div>
                </div>
                <el-button text @click="onEvalCollapse">收起</el-button>
              </div>
            </template>
            <div class="eval-detail-body">
              <div class="eval-detail-text">{{ activeEval.detail }}</div>
              <div class="eval-detail-chart">
                <div v-if="!activeEvalHasData" class="eval-detail-empty">
                  {{ activeEval.placeholder }}
                </div>
                <div v-else :ref="evalDetailChartRef" class="eval-detail-canvas"></div>
              </div>
              <div class="eval-detail-note">{{ activeEval.note }}</div>
            </div>
          </el-card>
        </transition>
      </div>
    </el-col>
  </el-row>
  <el-row :gutter="16" style="margin-top: 16px">
    <el-col :span="24">
      <el-card shadow="never" class="panel-card">
        <template #header>
          <div class="model-header">
            <div>
              <div class="settings-title">扩展评估</div>
              <div class="card-subtitle">新增指标与图表</div>
            </div>
          </div>
        </template>
        <div class="eval-grid">
          <div
            v-for="item in evalItems"
            :key="item.key"
            class="eval-panel"
            :class="{ 'is-active': activeEvalKey === item.key }"
            @click="onEvalCardClick(item.key)"
          >
            <div class="eval-title">{{ item.title }}</div>
            <div class="eval-subtitle">{{ item.subtitle }}</div>
            <div class="eval-thumb">
              <div v-if="hasEvalData(item.key)" class="eval-thumb-canvas" :ref="setEvalThumbRef(item.key)"></div>
              <div v-else class="eval-thumb-empty">暂无数据</div>
            </div>
          </div>
        </div>
      </el-card>
    </el-col>
  </el-row>
</template>

<script setup>
defineProps({
  modelMetrics: { type: Object, required: true },
  modelMetricsModel: { type: String, required: true },
  modelCurrent: { type: String, required: true },
  modelEvaluating: { type: Boolean, required: true },
  modelMetricsLoading: { type: Boolean, required: true },
  modelMetricsError: { type: String, required: true },
  evalNormMethod: { type: String, required: true },
  rocDerived: { type: Object, required: true },
  formatMetric: { type: Function, required: true },
  formatPercent: { type: Function, required: true },
  rocChartRef: { type: Function, required: true },
  modelSwitching: { type: Boolean, required: true },
  modelList: { type: Array, required: true },
  modelTarget: { type: String, required: true },
  activeEval: { type: Object, default: null },
  activeEvalHasData: { type: Boolean, required: true },
  activeEvalKey: { type: String, required: true },
  evalItems: { type: Array, required: true },
  evalDetailChartRef: { type: Function, required: true },
  setEvalThumbRef: { type: Function, required: true },
  hasEvalData: { type: Function, required: true },
  onLoadModelMetrics: { type: Function, required: true },
  onModelEvaluate: { type: Function, required: true },
  onLoadModelList: { type: Function, required: true },
  onModelTargetChange: { type: Function, required: true },
  onModelSwitch: { type: Function, required: true },
  onEvalNormMethodChange: { type: Function, required: true },
  onEvalCollapse: { type: Function, required: true },
  onEvalCardClick: { type: Function, required: true }
});
</script>

<style scoped>
.model-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.norm-label {
  font-size: 13px;
  color: #606266;
  margin-right: 4px;
}
.settings-title {
  font-weight: 600;
  font-size: 16px;
}
</style>
