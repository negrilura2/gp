<template>
  <el-container style="height: 100vh">
    <el-main>
      <div class="me-wrapper">
        <el-card class="me-card">
          <div class="me-header">
            <div class="me-title">个人主页</div>
          </div>
          <div v-if="loading" class="me-loading">
            <span>加载中...</span>
          </div>
          <div v-else>
            <div v-if="!user">
              <el-alert
                type="warning"
                title="当前未登录，将跳转到登录页面"
                show-icon
              />
            </div>
            <template v-else>
              <el-tabs v-model="activeTab">
                <el-tab-pane label="基础信息" name="basic">
                  <el-descriptions title="基本信息" :column="1" border>
                    <el-descriptions-item label="用户名">
                      {{ user.username }}
                    </el-descriptions-item>
                    <el-descriptions-item label="是否管理员">
                      {{ user.is_staff ? "是" : "否" }}
                    </el-descriptions-item>
                    <el-descriptions-item label="是否已录入声纹">
                      {{ user.has_voiceprint ? "是" : "否" }}
                    </el-descriptions-item>
                    <el-descriptions-item label="注册时间">
                      {{ user.date_joined }}
                    </el-descriptions-item>
                  </el-descriptions>
                </el-tab-pane>
                <el-tab-pane label="声纹管理" name="voice">
                  <el-card class="me-section" shadow="never">
                    <template #header>
                      <div class="section-header">
                        <span>
                          {{ user.has_voiceprint ? "重新录制声纹" : "首次录制声纹" }}
                        </span>
                      </div>
                    </template>
                    <div class="voiceprint-summary">
                      <div class="voiceprint-header">
                        <span>当前声纹</span>
                        <el-button
                          v-if="user.has_voiceprint"
                          size="small"
                          type="danger"
                          plain
                          :loading="voiceprintDeleting"
                          @click="confirmDeleteVoiceprint"
                        >
                          删除声纹
                        </el-button>
                      </div>
                      <div v-if="voiceprintLoading" class="card-subtitle">
                        正在加载声纹概览...
                      </div>
                      <template v-else>
                        <div v-if="!user.has_voiceprint" class="card-subtitle">
                          暂无已注册声纹
                        </div>
                        <div v-else class="voiceprint-body">
                          <div class="voiceprint-meta">
                            <span>特征维度 {{ voiceprintMeta?.embedding_dim || 0 }}</span>
                            <span>样本数 {{ voiceprintMeta?.embedding_count || 0 }}</span>
                            <span>更新时间 {{ voiceprintMeta?.updated_at || "-" }}</span>
                          </div>
                          <div class="voiceprint-chart">
                            <div
                              v-for="(v, idx) in voiceprintPreview"
                              :key="idx"
                              class="voiceprint-bar"
                              :style="{ height: `${Math.max(6, v * 100)}%` }"
                            ></div>
                          </div>
                        </div>
                      </template>
                    </div>
                    <div class="record-main">
                      <div class="wave-header">
                        <span class="wave-title">声波图</span>
                        <span class="wave-subtitle">播放时走过区域会高亮</span>
                      </div>
                      <canvas ref="waveCanvasRef" class="wave-canvas"></canvas>
                      <div class="record-actions">
                        <el-button
                          :type="recording ? 'danger' : 'primary'"
                          @click="toggleRecording"
                        >
                          {{ recording ? "停止录音" : "开始录音一条语音" }}
                        </el-button>
                        <el-button
                          type="success"
                          :loading="enrolling"
                          :disabled="!enrollFiles.length"
                          @click="handleEnroll"
                        >
                          提交声纹（当前 {{ enrollFiles.length }} 条）
                        </el-button>
                        <el-button
                          type="info"
                          plain
                          :disabled="!enrollFiles.length && !playbackUrl"
                          @click="confirmClearVoice"
                        >
                          清空全部录音/上传
                        </el-button>
                        <span class="record-hint">
                          建议录制 3~5 条不同内容的语音，用于提高鲁棒性
                        </span>
                      </div>
                      <div class="upload-row">
                        <input
                          ref="uploadInputRef"
                        class="upload-input"
                          type="file"
                          accept=".wav"
                          multiple
                          @change="onUploadChange"
                        />
                      <el-button size="small" @click="triggerUpload">选择文件</el-button>
                      <span class="upload-hint">{{ uploadLabel }}</span>
                      </div>
                      <div v-if="audioItems.length" class="file-list">
                        <div v-if="recordItems.length" class="file-group">
                          <div class="file-group-title">录制语音</div>
                          <div class="file-chips">
                            <el-tag
                              v-for="item in recordItems"
                              :key="item.id"
                              class="file-chip"
                              :type="item.id === selectedAudioId ? 'success' : 'info'"
                              effect="plain"
                              closable
                              @close="handleDeleteAudio(item.id)"
                              @click="handleSelectAudio(item.id)"
                            >
                              {{ item.name }}
                            </el-tag>
                          </div>
                        </div>
                        <div v-if="uploadItems.length" class="file-group">
                          <div class="file-group-title">上传语音</div>
                          <div class="file-chips">
                            <el-tag
                              v-for="item in uploadItems"
                              :key="item.id"
                              class="file-chip"
                              :type="item.id === selectedAudioId ? 'success' : 'info'"
                              effect="plain"
                              closable
                              @close="handleDeleteAudio(item.id)"
                              @click="handleSelectAudio(item.id)"
                            >
                              {{ item.name }}
                            </el-tag>
                          </div>
                        </div>
                      </div>
                      <div v-if="playbackUrl" class="playback">
                        <audio
                          ref="audioRef"
                          :src="playbackUrl"
                          controls
                          @play="handleAudioPlay"
                          @pause="handleAudioPause"
                          @ended="handleAudioEnded"
                          @timeupdate="handleAudioTimeUpdate"
                          @loadedmetadata="handleAudioLoaded"
                        />
                      </div>
                    </div>
                  </el-card>
                </el-tab-pane>
                <el-tab-pane label="验证记录" name="logs">
                  <el-card class="me-section" shadow="never">
                    <template #header>
                      <div class="section-header">
                        <span>最近验证记录</span>
                        <span class="log-hint">仅显示最近 100 条记录</span>
                      </div>
                    </template>
                    <div class="log-toolbar">
                      <el-date-picker
                        v-model="logDateRange"
                        type="daterange"
                        range-separator="至"
                        start-placeholder="开始日期"
                        end-placeholder="结束日期"
                        value-format="YYYY-MM-DD"
                        size="small"
                      />
                    </div>
                    <el-table
                      :data="pagedLogs"
                      size="small"
                      border
                      style="width: 100%"
                    >
                      <el-table-column prop="timestamp" label="时间" width="180" />
                      <el-table-column
                        prop="predicted_user"
                        label="预测用户"
                        width="140"
                      />
                      <el-table-column prop="score" label="得分" width="100" />
                      <el-table-column prop="threshold" label="阈值" width="80" />
                      <el-table-column prop="result" label="结果" width="90" />
                      <el-table-column
                        prop="door_state"
                        label="门状态"
                        width="90"
                      />
                    </el-table>
                    <div class="log-pagination">
                      <el-pagination
                        layout="prev, pager, next, jumper"
                        background
                        :page-size="logPageSize"
                        :current-page="logPage"
                        :total="filteredLogs.length"
                        @current-change="handleLogPageChange"
                      />
                    </div>
                  </el-card>
                </el-tab-pane>
                <el-tab-pane label="账号设置" name="account">
                  <el-card class="me-section" shadow="never">
                    <template #header>
                      <div class="section-header">
                        <span>账号设置</span>
                      </div>
                    </template>
                    <el-descriptions :column="1" border>
                      <el-descriptions-item label="当前账号">
                        {{ user.username }}
                      </el-descriptions-item>
                      <el-descriptions-item label="账号角色">
                        {{ user.is_staff ? "管理员" : "普通用户" }}
                      </el-descriptions-item>
                      <el-descriptions-item label="声纹状态">
                        {{ user.has_voiceprint ? "已录入" : "未录入" }}
                      </el-descriptions-item>
                    </el-descriptions>
                  <div class="record-actions" style="margin-top: 12px">
                    <el-button type="danger" @click="handleLogout">退出登录</el-button>
                  </div>
                  </el-card>
                </el-tab-pane>
              </el-tabs>
            </template>
          </div>
        </el-card>
      </div>
    </el-main>
  </el-container>
</template>

<script setup>
import { onMounted, onUnmounted, ref, computed, watch, nextTick } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  fetchCurrentUser,
  enrollVoice,
  fetchMyLogs,
  setAuthToken,
  fetchMyVoiceprint,
  deleteMyVoiceprint
} from "../api";

const router = useRouter();

const user = ref(null);
const logs = ref([]);
const loading = ref(true);
const activeTab = ref("basic");
const enrolling = ref(false);
const logPage = ref(1);
const logPageSize = ref(10);
const logDateRange = ref([]);

const waveCanvasRef = ref(null);
const recording = ref(false);
const recordFiles = ref([]);
const uploadFiles = ref([]);
const enrollFiles = ref([]);
const playbackUrl = ref("");
const uploadInputRef = ref(null);
const audioRef = ref(null);
const audioItems = ref([]);
const selectedAudioId = ref("");
const staticWaveValues = ref([]);
const playProgress = ref(0);
const voiceprintLoading = ref(false);
const voiceprintDeleting = ref(false);
const voiceprintPreview = ref([]);
const voiceprintMeta = ref(null);

let mediaStream = null;
let mediaRecorder = null;
let audioChunks = [];
let audioContext = null;
let analyser = null;
let animationId = null;
let lastRenderedBuffer = null;
let staticCanvas = null;
let playAnimationId = null;
let lastStaticValues = null;
const WAVE_HISTORY_POINTS = 2048;
let waveHistory = [];

function getCanvasMetrics() {
  const canvas = waveCanvasRef.value;
  if (!canvas) return null;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight || 120;
  const ratio = window.devicePixelRatio || 1;
  return { canvas, width, height, ratio };
}

function setupHiDpiCanvas(canvas, width, height, ratio) {
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  return ctx;
}

function ensureCanvasReady() {
  const metrics = getCanvasMetrics();
  if (!metrics) return null;
  const { canvas, width, height, ratio } = metrics;
  const ctx = setupHiDpiCanvas(canvas, width, height, ratio);
  return { canvas, ctx, width, height, ratio };
}

function initCanvas() {
  ensureCanvasReady();
}

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

function drawWave() {
  if (!analyser) return;
  const metrics = ensureCanvasReady();
  if (!metrics) return;
  const { canvas, ctx, width, height } = metrics;
  const bufferLength = analyser.fftSize;
  const dataArray = new Uint8Array(bufferLength);

  function draw() {
    animationId = requestAnimationFrame(draw);
    analyser.getByteTimeDomainData(dataArray);
    let sumSquares = 0;
    for (let i = 0; i < bufferLength; i++) {
      const x = (dataArray[i] - 128) / 128.0;
      sumSquares += x * x;
    }
    let rms = Math.sqrt(sumSquares / bufferLength);
    rms = Math.min(1, rms * 8);
    waveHistory.push(rms);
    if (waveHistory.length > WAVE_HISTORY_POINTS) {
      waveHistory.shift();
    }

    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "#000000";
    ctx.fillRect(0, 0, width, height);
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = "#67E8A9";
    const centerY = height / 2;

    if (waveHistory.length > 0) {
      ctx.beginPath();
      const denom =
        WAVE_HISTORY_POINTS > 1 ? WAVE_HISTORY_POINTS - 1 : WAVE_HISTORY_POINTS;
      for (let i = 0; i < waveHistory.length; i++) {
        const x = (i / (denom || 1)) * width;
        const y = centerY - waveHistory[i] * centerY * 0.9;
        if (i === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.stroke();
    }
  }

  draw();
}

const recordItems = computed(() =>
  audioItems.value.filter((item) => item.source === "record")
);
const uploadItems = computed(() =>
  audioItems.value.filter((item) => item.source === "upload")
);
const uploadLabel = computed(() =>
  uploadFiles.value.length ? `已选择 ${uploadFiles.value.length} 条` : "未选择文件"
);

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

watch(activeTab, (tab) => {
  if (tab === "voice") {
    nextTick(() => {
      initCanvas();
    });
  }
});

function handleLogPageChange(page) {
  logPage.value = page;
}

function handleDeleteAudio(id) {
  const item = audioItems.value.find((i) => i.id === id);
  if (!item) return;
  if (item.url) {
    URL.revokeObjectURL(item.url);
  }
  audioItems.value = audioItems.value.filter((i) => i.id !== id);
  if (item.source === "record") {
    recordFiles.value = recordFiles.value.filter(
      (f) => buildAudioId(f, "record") !== id
    );
  } else {
    uploadFiles.value = uploadFiles.value.filter(
      (f) => buildAudioId(f, "upload") !== id
    );
  }
  enrollFiles.value = [...recordFiles.value, ...uploadFiles.value];
  if (selectedAudioId.value === id) {
    selectedAudioId.value = "";
    playbackUrl.value = "";
    staticWaveValues.value = [];
    playProgress.value = 0;
    if (playAnimationId) {
      cancelAnimationFrame(playAnimationId);
      playAnimationId = null;
    }
    if (audioRef.value) {
      audioRef.value.pause();
      audioRef.value.currentTime = 0;
    }
    clearWaveCanvas();
    if (audioItems.value.length) {
      handleSelectAudio(audioItems.value[0].id);
    }
  }
}

function buildAudioId(file, source) {
  return `${source}-${file.name}-${file.size}-${file.lastModified}`;
}

function ensureStaticCanvas() {
  if (!staticCanvas) {
    staticCanvas = document.createElement("canvas");
  }
  return staticCanvas;
}

function buildWaveValuesFromBuffer(buffer) {
  const metrics = getCanvasMetrics();
  if (!metrics) return [];
  const { width } = metrics;
  const data = buffer.getChannelData(0);
  const samplesPerPoint = Math.max(1, Math.floor(data.length / width));
  const values = [];
  for (let x = 0; x < width; x++) {
    const start = x * samplesPerPoint;
    if (start >= data.length) break;
    let sumSquares = 0;
    let count = 0;
    for (let i = 0; i < samplesPerPoint && start + i < data.length; i++) {
      const v = data[start + i];
      sumSquares += v * v;
      count++;
    }
    if (!count) break;
    let rms = Math.sqrt(sumSquares / count);
    rms = Math.min(1, rms * 8);
    values.push(rms);
  }
  return values;
}

function drawWavePath(ctx, values, width, height, color, lineWidth) {
  if (!values.length) return;
  const centerY = height / 2;
  ctx.beginPath();
  const denom = values.length > 1 ? values.length - 1 : values.length;
  for (let i = 0; i < values.length; i++) {
    const x = (i / (denom || 1)) * width;
    const y = centerY - values[i] * centerY * 0.9;
    if (i === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  }
  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;
  ctx.stroke();
}

function renderBaseWave(values) {
  const metrics = getCanvasMetrics();
  if (!metrics) return;
  const { width, height, ratio } = metrics;
  const base = ensureStaticCanvas();
  const ctx = setupHiDpiCanvas(base, width, height, ratio);

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#000000";
  ctx.fillRect(0, 0, width, height);
  drawWavePath(ctx, values, width, height, "#67E8A9", 1.5);
}

function renderStaticWave(values, progress = 0) {
  const metrics = ensureCanvasReady();
  if (!metrics) return;
  const { ctx, width, height } = metrics;
  if (
    values.length &&
    (!staticCanvas ||
      staticCanvas.width !== width ||
      staticCanvas.height !== height ||
      lastStaticValues !== values)
  ) {
    renderBaseWave(values);
    lastStaticValues = values;
  }

  ctx.clearRect(0, 0, width, height);
  if (staticCanvas) {
    ctx.drawImage(staticCanvas, 0, 0);
  }

  const clamped = Math.max(0, Math.min(1, progress));
  const lineX = clamped * width;
  if (values.length && lineX > 0) {
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, lineX, height);
    ctx.clip();
    ctx.shadowColor = "rgba(255, 193, 77, 0.5)";
    ctx.shadowBlur = 6;
    drawWavePath(ctx, values, width, height, "#FFC14D", 2);
    ctx.restore();
  }
  ctx.save();
  ctx.strokeStyle = "rgba(245, 108, 108, 0.65)";
  ctx.lineWidth = 1;
  ctx.shadowColor = "rgba(245, 108, 108, 0.6)";
  ctx.shadowBlur = 4;
  ctx.beginPath();
  ctx.moveTo(lineX, 0);
  ctx.lineTo(lineX, height);
  ctx.stroke();
  ctx.restore();
}

async function decodeToTargetBuffer(arrayBuffer) {
  const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
  const ctx = new AudioContextCtor();
  const decoded = await ctx.decodeAudioData(arrayBuffer.slice(0));
  const targetSampleRate = 16000;
  const OfflineContextCtor =
    window.OfflineAudioContext || window.webkitOfflineAudioContext;
  const offlineCtx = new OfflineContextCtor(
    decoded.numberOfChannels,
    Math.ceil((decoded.length * targetSampleRate) / decoded.sampleRate),
    targetSampleRate
  );
  const bufferSource = offlineCtx.createBufferSource();
  bufferSource.buffer = decoded;
  bufferSource.connect(offlineCtx.destination);
  bufferSource.start(0);
  return offlineCtx.startRendering();
}

async function loadWaveValuesForItem(item) {
  try {
    const arrayBuffer = await item.file.arrayBuffer();
    const renderedBuffer = await decodeToTargetBuffer(arrayBuffer);
    const values = buildWaveValuesFromBuffer(renderedBuffer);
    item.waveValues = values;
    if (selectedAudioId.value === item.id) {
      staticWaveValues.value = values;
      renderBaseWave(values);
      renderStaticWave(values, 0);
    }
  } catch (e) {
    ElMessage.error("解析音频文件失败");
  }
}

function addAudioItem(file, source, values) {
  const id = buildAudioId(file, source);
  const existing = audioItems.value.find((item) => item.id === id);
  if (existing) return existing;
  const item = {
    id,
    name: file.name,
    file,
    source,
    waveValues: values || [],
    url: ""
  };
  audioItems.value = [...audioItems.value, item];
  return item;
}

function handleSelectAudio(id) {
  const item = audioItems.value.find((i) => i.id === id);
  if (!item) return;
  selectedAudioId.value = id;
  if (audioRef.value) {
    audioRef.value.pause();
    audioRef.value.currentTime = 0;
  }
  playProgress.value = 0;
  if (playAnimationId) {
    cancelAnimationFrame(playAnimationId);
    playAnimationId = null;
  }
  if (!item.url) {
    item.url = URL.createObjectURL(item.file);
  }
  playbackUrl.value = item.url;
  if (item.waveValues && item.waveValues.length) {
    staticWaveValues.value = item.waveValues;
    renderBaseWave(item.waveValues);
    renderStaticWave(item.waveValues, 0);
  } else {
    staticWaveValues.value = [];
    clearWaveCanvas();
    loadWaveValuesForItem(item);
  }
}

async function startRecording() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    ElMessage.error("当前浏览器不支持录音，请使用现代浏览器");
    return;
  }
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (e) {
    ElMessage.error("无法访问麦克风，请检查浏览器权限设置");
    return;
  }

  const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
  audioContext = new AudioContextCtor();
  const source = audioContext.createMediaStreamSource(mediaStream);
  analyser = audioContext.createAnalyser();
  analyser.fftSize = 2048;
  source.connect(analyser);
  waveHistory = [];
  lastRenderedBuffer = null;
  staticWaveValues.value = [];
  playProgress.value = 0;
  if (playAnimationId) {
    cancelAnimationFrame(playAnimationId);
    playAnimationId = null;
  }
  if (audioRef.value) {
    audioRef.value.pause();
    audioRef.value.currentTime = 0;
  }
  drawWave();

  const mimeType =
    MediaRecorder.isTypeSupported &&
    MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : "";
  mediaRecorder = new MediaRecorder(mediaStream, mimeType ? { mimeType } : {});
  audioChunks = [];
  mediaRecorder.ondataavailable = (e) => {
    if (e.data && e.data.size > 0) {
      audioChunks.push(e.data);
    }
  };
  mediaRecorder.onstop = async () => {
    const blob = new Blob(audioChunks, { type: mimeType || "audio/webm" });
    await handleRecordedBlob(blob);
  };
  mediaRecorder.start();
  recording.value = true;
}

function stopRecording() {
  if (mediaRecorder && recording.value) {
    mediaRecorder.stop();
  }
  recording.value = false;
  if (animationId) {
    cancelAnimationFrame(animationId);
    animationId = null;
  }
  if (audioContext) {
    audioContext.close();
    audioContext = null;
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach((t) => t.stop());
    mediaStream = null;
  }
}

async function handleRecordedBlob(blob) {
  try {
    const arrayBuffer = await blob.arrayBuffer();
    const renderedBuffer = await decodeToTargetBuffer(arrayBuffer);
    lastRenderedBuffer = renderedBuffer;
    const values = buildWaveValuesFromBuffer(renderedBuffer);
    staticWaveValues.value = values;
    renderBaseWave(values);
    renderStaticWave(values, 0);
    const wavBlob = audioBufferToWavBlob(renderedBuffer);
    const f = new File(
      [wavBlob],
      `me_record_${Date.now()}.wav`,
      { type: "audio/wav" }
    );
    recordFiles.value = [...recordFiles.value, f];
    enrollFiles.value = [...recordFiles.value, ...uploadFiles.value];
    const item = addAudioItem(f, "record", values);
    handleSelectAudio(item.id);
    ElMessage.success(`已录制第 ${recordFiles.value.length} 条语音`);
  } catch (e) {
    ElMessage.error("处理录音数据失败，请重试");
  }
}

function audioBufferToWavBlob(buffer) {
  const numChannels = buffer.numberOfChannels;
  const sampleRate = buffer.sampleRate;
  const format = 1;
  const bitDepth = 16;
  const numSamples = buffer.length * numChannels;
  const blockAlign = (numChannels * bitDepth) / 8;
  const byteRate = (sampleRate * blockAlign) | 0;
  const dataSize = numSamples * (bitDepth / 8);
  const bufferSize = 44 + dataSize;
  const arrayBuffer = new ArrayBuffer(bufferSize);
  const view = new DataView(arrayBuffer);

  function writeString(offset, str) {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  }

  let offset = 0;
  writeString(offset, "RIFF");
  offset += 4;
  view.setUint32(offset, 36 + dataSize, true);
  offset += 4;
  writeString(offset, "WAVE");
  offset += 4;
  writeString(offset, "fmt ");
  offset += 4;
  view.setUint32(offset, 16, true);
  offset += 4;
  view.setUint16(offset, format, true);
  offset += 2;
  view.setUint16(offset, numChannels, true);
  offset += 2;
  view.setUint32(offset, sampleRate, true);
  offset += 4;
  view.setUint32(offset, byteRate, true);
  offset += 4;
  view.setUint16(offset, blockAlign, true);
  offset += 2;
  view.setUint16(offset, bitDepth, true);
  offset += 2;
  writeString(offset, "data");
  offset += 4;
  view.setUint32(offset, dataSize, true);
  offset += 4;

  const channels = [];
  for (let ch = 0; ch < numChannels; ch++) {
    channels.push(buffer.getChannelData(ch));
  }
  let sampleIndex = 0;
  while (sampleIndex < buffer.length) {
    for (let ch = 0; ch < numChannels; ch++) {
      const sample = channels[ch][sampleIndex];
      const s = Math.max(-1, Math.min(1, sample));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
      offset += 2;
    }
    sampleIndex++;
  }

  return new Blob([arrayBuffer], { type: "audio/wav" });
}

function toggleRecording() {
  if (recording.value) {
    stopRecording();
  } else {
    startRecording();
  }
}

function clearWaveCanvas() {
  const metrics = ensureCanvasReady();
  if (!metrics) return;
  const { ctx, width, height } = metrics;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#000000";
  ctx.fillRect(0, 0, width, height);
}

async function handleEnroll() {
  if (!enrollFiles.value.length) {
    ElMessage.error("请先录制或上传至少一条语音");
    return;
  }
  enrolling.value = true;
  try {
    const form = new FormData();
    enrollFiles.value.forEach((f) => form.append("files", f));
    await enrollVoice(form);
    ElMessage.success("声纹已更新");
    handleClearVoice();
    await loadVoiceprintPreview();
    await loadUserAndLogs();
  } catch (e) {
    const data = e.response && e.response.data;
    const msg = data && data.error ? data.error : "声纹更新失败";
    ElMessage.error(msg);
  } finally {
    enrolling.value = false;
  }
}

function triggerUpload() {
  if (uploadInputRef.value) {
    uploadInputRef.value.click();
  }
}

function onUploadChange(e) {
  const files = Array.from(e.target.files || []);
  if (!files.length) {
    if (uploadInputRef.value) {
      uploadInputRef.value.value = "";
    }
    return;
  }
  const existingIds = new Set(
    audioItems.value
      .filter((item) => item.source === "upload")
      .map((item) => item.id)
  );
  const newItems = [];
  files.forEach((file) => {
    const id = buildAudioId(file, "upload");
    if (existingIds.has(id)) {
      return;
    }
    uploadFiles.value = [...uploadFiles.value, file];
    const item = addAudioItem(file, "upload");
    newItems.push(item);
  });
  enrollFiles.value = [...recordFiles.value, ...uploadFiles.value];
  if (newItems.length) {
    ElMessage.success(`已添加 ${newItems.length} 条本地音频`);
    newItems.forEach((item) => loadWaveValuesForItem(item));
    handleSelectAudio(newItems[0].id);
  }
  if (uploadInputRef.value) {
    uploadInputRef.value.value = "";
  }
}

onMounted(() => {
  initCanvas();
  loadUserAndLogs();
});

onUnmounted(() => {
  stopRecording();
  if (playAnimationId) {
    cancelAnimationFrame(playAnimationId);
    playAnimationId = null;
  }
  audioItems.value.forEach((item) => {
    if (item.url) {
      URL.revokeObjectURL(item.url);
    }
  });
});

function handleClearVoice() {
  stopRecording();
  recordFiles.value = [];
  uploadFiles.value = [];
  enrollFiles.value = [];
  waveHistory = [];
  lastRenderedBuffer = null;
  staticWaveValues.value = [];
  playProgress.value = 0;
  if (playAnimationId) {
    cancelAnimationFrame(playAnimationId);
    playAnimationId = null;
  }
  if (audioRef.value) {
    audioRef.value.pause();
    audioRef.value.currentTime = 0;
  }
  audioItems.value.forEach((item) => {
    if (item.url) {
      URL.revokeObjectURL(item.url);
    }
  });
  audioItems.value = [];
  selectedAudioId.value = "";
  playbackUrl.value = "";
  if (uploadInputRef.value) {
    uploadInputRef.value.value = "";
  }
  clearWaveCanvas();
}

async function confirmClearVoice() {
  try {
    await ElMessageBox.confirm("确认清空全部录音/上传？", "提示", {
      confirmButtonText: "确定",
      cancelButtonText: "取消",
      type: "warning"
    });
    handleClearVoice();
  } catch (e) {
    return;
  }
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

function syncProgressFromAudio() {
  if (!audioRef.value || !staticWaveValues.value.length) return;
  const duration = audioRef.value.duration || 0;
  const progress = duration ? audioRef.value.currentTime / duration : 0;
  playProgress.value = progress;
  renderStaticWave(staticWaveValues.value, progress);
}

function startPlayLoop() {
  if (playAnimationId) {
    cancelAnimationFrame(playAnimationId);
  }
  const step = () => {
    if (!audioRef.value || audioRef.value.paused) {
      playAnimationId = null;
      return;
    }
    syncProgressFromAudio();
    playAnimationId = requestAnimationFrame(step);
  };
  playAnimationId = requestAnimationFrame(step);
}

function stopPlayLoop() {
  if (playAnimationId) {
    cancelAnimationFrame(playAnimationId);
    playAnimationId = null;
  }
}

function handleAudioPlay() {
  startPlayLoop();
}

function handleAudioPause() {
  stopPlayLoop();
  if (staticWaveValues.value.length) {
    renderStaticWave(staticWaveValues.value, playProgress.value);
  }
}

function handleAudioEnded() {
  stopPlayLoop();
  playProgress.value = 1;
  if (staticWaveValues.value.length) {
    renderStaticWave(staticWaveValues.value, 1);
  }
}

function handleAudioLoaded() {
  if (staticWaveValues.value.length) {
    renderStaticWave(staticWaveValues.value, 0);
  }
}

function handleAudioTimeUpdate() {
  syncProgressFromAudio();
}
</script>

<style scoped>
.me-wrapper {
  min-height: 100vh;
  padding: 24px;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fb;
  background-image: radial-gradient(
      1200px circle at 0% 0%,
      rgba(64, 158, 255, 0.12),
      transparent 45%
    ),
    radial-gradient(
      1200px circle at 100% 0%,
      rgba(103, 232, 169, 0.12),
      transparent 45%
    );
}

.me-card {
  width: 900px;
  border: 1px solid rgba(64, 158, 255, 0.15);
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(6px);
}

.me-title {
  font-size: 20px;
  font-weight: 600;
}

.me-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.me-loading {
  display: flex;
  align-items: center;
  gap: 8px;
}

.me-section {
  margin-top: 16px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.log-hint {
  font-size: 12px;
  color: #909399;
}

.log-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 8px;
}

.log-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.voiceprint-summary {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 12px;
  margin-bottom: 12px;
  background: #fafcff;
}

.voiceprint-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  margin-bottom: 8px;
}

.voiceprint-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.voiceprint-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #606266;
}

.voiceprint-chart {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(6px, 1fr));
  gap: 2px;
  height: 72px;
  align-items: end;
  background: #0f172a;
  border-radius: 4px;
  padding: 6px;
}

.voiceprint-bar {
  width: 100%;
  background: linear-gradient(180deg, #67e8a9, #3b82f6);
  border-radius: 2px;
  min-height: 6px;
}

.record-main {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 12px;
}

.wave-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 6px;
}

.wave-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.wave-subtitle {
  font-size: 12px;
  color: #909399;
}

.wave-canvas {
  width: 100%;
  height: 120px;
  display: block;
  background: #000000;
  border-radius: 4px;
  border: 1px solid #1f2d3d;
}

.record-actions {
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.record-hint {
  font-size: 12px;
  color: #909399;
}

.upload-row {
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.upload-input {
  display: none;
}

.file-list {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.file-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.file-group-title {
  font-size: 12px;
  color: #606266;
}

.file-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.file-chip {
  cursor: pointer;
}

.upload-hint {
  font-size: 12px;
  color: #909399;
}

.playback {
  margin-top: 10px;
}
</style>
