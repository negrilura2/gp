<template>
  <div class="voiceprint-chart" :style="{ height: `${height}px`, background }">
    <div
      v-for="(v, idx) in values"
      :key="idx"
      class="voiceprint-bar"
      :style="{ height: `${Math.max(6, v * 100)}%`, background: barColor }"
    />
  </div>
</template>

<script setup>
defineProps({
  values: {
    type: Array,
    default: () => [],
  },
  height: {
    type: Number,
    default: 72,
  },
  background: {
    type: String,
    default: "#0f172a",
  },
  barColor: {
    type: String,
    default: "linear-gradient(180deg, #67e8a9, #3b82f6)",
  },
});
</script>

<style scoped>
.voiceprint-chart {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  border-radius: 8px;
  overflow: hidden;
  padding: 0 4px;
}

.voiceprint-bar {
  flex: 1;
  margin: 0 1px;
  border-radius: 2px 2px 0 0;
  transition: height 0.3s ease;
  min-height: 4px;
}
</style>
