<template>
  <el-container style="height: 100vh">
    <el-main>
      <div class="me-wrapper">
        <el-card class="me-card">
          <div class="me-header">
            <div class="me-title">个人主页</div>
            <el-button size="small" @click="handleLogout">退出登录</el-button>
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

              <el-card class="me-section" shadow="never">
                <template #header>
                  <div class="section-header">
                    <span>
                      {{ user.has_voiceprint ? "重新录制声纹" : "首次录制声纹" }}
                    </span>
                  </div>
                </template>
                <div class="record-main">
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
                      @click="handleClearVoice"
                    >
                      清空当前录音/上传
                    </el-button>
                    <span class="record-hint">
                      建议录制 3~5 条不同内容的语音，用于提高鲁棒性
                    </span>
                  </div>
                  <div class="upload-row">
                    <input type="file" accept=".wav" multiple @change="onUploadChange" />
                  </div>
                  <div v-if="playbackUrl" class="playback">
                    <audio :src="playbackUrl" controls />
                  </div>
                </div>
              </el-card>

              <el-card class="me-section" shadow="never">
                <template #header>
                  <div class="section-header">
                    <span>最近验证记录</span>
                  </div>
                </template>
                <el-table
                  :data="logs"
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
              </el-card>
            </template>
          </div>
        </el-card>
      </div>
    </el-main>
  </el-container>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { fetchCurrentUser, enrollVoice, fetchMyLogs, setAuthToken } from "../api";

const router = useRouter();

const user = ref(null);
const logs = ref([]);
const loading = ref(true);
const enrolling = ref(false);

const waveCanvasRef = ref(null);
const recording = ref(false);
const recordFiles = ref([]);
const uploadFiles = ref([]);
const enrollFiles = ref([]);
const playbackUrl = ref("");

let mediaStream = null;
let mediaRecorder = null;
let audioChunks = [];
let audioContext = null;
let analyser = null;
let animationId = null;
let lastRenderedBuffer = null;
const WAVE_HISTORY_POINTS = 2048;
let waveHistory = [];

function initCanvas() {
  if (waveCanvasRef.value) {
    const canvas = waveCanvasRef.value;
    canvas.width = canvas.clientWidth;
    canvas.height = canvas.clientHeight || 120;
  }
}

async function loadUserAndLogs() {
  loading.value = true;
  try {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
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
  } catch (e) {
    router.push("/login");
  } finally {
    loading.value = false;
  }
}

function drawWave() {
  if (!analyser || !waveCanvasRef.value) return;
  const canvas = waveCanvasRef.value;
  const ctx = canvas.getContext("2d");
  const bufferLength = analyser.fftSize;
  const dataArray = new Uint8Array(bufferLength);

  function draw() {
    animationId = requestAnimationFrame(draw);
    analyser.getByteTimeDomainData(dataArray);
    const width = canvas.width;
    const height = canvas.height;
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
    const renderedBuffer = await offlineCtx.startRendering();
    lastRenderedBuffer = renderedBuffer;
    drawStaticWaveFromBuffer(renderedBuffer);
    const wavBlob = audioBufferToWavBlob(renderedBuffer);
    const f = new File(
      [wavBlob],
      `me_record_${Date.now()}.wav`,
      { type: "audio/wav" }
    );
    recordFiles.value = [...recordFiles.value, f];
    enrollFiles.value = [...recordFiles.value, ...uploadFiles.value];
    if (playbackUrl.value) {
      URL.revokeObjectURL(playbackUrl.value);
    }
    playbackUrl.value = URL.createObjectURL(f);
    ElMessage.success(`已录制第 ${recordFiles.value.length} 条语音`);
  } catch (e) {
    ElMessage.error("处理录音数据失败，请重试");
  }
}

function drawStaticWaveFromBuffer(buffer) {
  if (!waveCanvasRef.value || !buffer) return;
  const canvas = waveCanvasRef.value;
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  const data = buffer.getChannelData(0);
  const centerY = height / 2;

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#000000";
  ctx.fillRect(0, 0, width, height);
  ctx.lineWidth = 1.5;
  ctx.strokeStyle = "#67E8A9";

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

  if (!values.length) return;

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
  ctx.stroke();
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
  if (!waveCanvasRef.value) return;
  const canvas = waveCanvasRef.value;
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
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
    recordFiles.value = [];
    uploadFiles.value = [];
    enrollFiles.value = [];
    await loadUserAndLogs();
  } catch (e) {
    const data = e.response && e.response.data;
    const msg = data && data.error ? data.error : "声纹更新失败";
    ElMessage.error(msg);
  } finally {
    enrolling.value = false;
  }
}

function onUploadChange(e) {
  const files = Array.from(e.target.files || []);
  uploadFiles.value = files;
  enrollFiles.value = [...recordFiles.value, ...uploadFiles.value];
  if (files.length) {
    ElMessage.success(`已选择 ${files.length} 条本地音频用于声纹注册`);
    if (playbackUrl.value) {
      URL.revokeObjectURL(playbackUrl.value);
    }
    playbackUrl.value = URL.createObjectURL(files[0]);
  }
}

onMounted(() => {
  initCanvas();
  loadUserAndLogs();
});

onUnmounted(() => {
  stopRecording();
  if (playbackUrl.value) {
    URL.revokeObjectURL(playbackUrl.value);
  }
});

function handleClearVoice() {
  stopRecording();
  recordFiles.value = [];
  uploadFiles.value = [];
  enrollFiles.value = [];
  waveHistory = [];
  lastRenderedBuffer = null;
  if (playbackUrl.value) {
    URL.revokeObjectURL(playbackUrl.value);
    playbackUrl.value = "";
  }
  clearWaveCanvas();
}

function handleLogout() {
  localStorage.removeItem("token");
  setAuthToken(null);
  router.push("/login");
}
</script>

<style scoped>
.me-wrapper {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.me-card {
  width: 900px;
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

.record-main {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 12px;
}

.wave-canvas {
  width: 100%;
  height: 120px;
  display: block;
  background: #f5f7fa;
  border-radius: 4px;
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

.upload-hint {
  font-size: 12px;
  color: #909399;
}

.playback {
  margin-top: 10px;
}
</style>
