<template>
  <div class="section-stack">
    <el-row :gutter="16">
      <el-col :span="4" v-for="card in summaryCards" :key="card.key">
        <el-card shadow="hover" class="stat-card">
          <div class="card-label">{{ card.label }}</div>
          <div class="card-value">{{ card.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :span="18">
        <el-card shadow="never" class="panel-card">
          <template #header>
            <div class="card-header">
              <div>验证趋势</div>
              <div class="card-subtitle">柱状为验证次数，折线为通过率</div>
            </div>
          </template>
          <div :ref="lineChartRef" style="width: 100%; height: 340px"></div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="panel-card">
          <template #header>
            <div class="card-header">
              <div>验证结果分布</div>
              <div class="card-subtitle">通过与拒绝的占比</div>
            </div>
          </template>
          <div :ref="pieChartRef" style="width: 100%; height: 340px"></div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
defineProps({
  summaryCards: { type: Array, required: true },
  lineChartRef: { type: Function, required: true },
  pieChartRef: { type: Function, required: true }
});
</script>
