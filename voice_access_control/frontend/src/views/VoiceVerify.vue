<template>
  <el-container style="height: 100vh">
    <el-main>
      <div class="verify-wrapper">
        <el-card class="verify-card">
          <div class="verify-title">声纹识别</div>
          <div class="record-section">
            <div class="record-header">实时录音识别</div>
            <div class="record-main">
              <canvas ref="waveCanvasRef" class="wave-canvas"></canvas>
              <div class="record-actions">
                <el-button
                  :type="recording ? 'danger' : 'primary'"
                  @click="toggleRecording"
                >
                  {{ recording ? "停止录音" : "按下开始说话" }}
                </el-button>
                <el-button
                  type="info"
                  plain
                  :disabled="!file && !audioUrl"
                  @click="handleClearRecording"
                >
                  清除录音/文件
                </el-button>
                <span class="record-hint">
                  建议在安静环境下录制 2~3 秒语音
                </span>
              </div>
              <div v-if="audioUrl" class="playback">
                <audio :src="audioUrl" controls />
              </div>
            </div>
          </div>
          <el-divider>或</el-divider>
          <el-form label-width="80px">
            <el-form-item label="音频文件">
              <input
                type="file"
                accept=".wav"
                @change="onFileChange"
              />
            </el-form-item>
            <el-form-item>
              <el-button
                type="primary"
                :loading="loading"
                @click="handleVerify"
              >
                开始识别
              </el-button>
            </el-form-item>
          </el-form>
          <div v-if="result" class="result-block">
            <el-alert
              :title="resultTitle"
              :type="resultType"
              show-icon
            />
            <div class="result-detail">
              <div v-if="resultSubtitle" class="result-subtitle">
                {{ resultSubtitle }}
              </div>
              <div>预测用户：{{ result.predicted_user }}</div>
              <div>得分：{{ result.score }}</div>
              <div>阈值：{{ result.threshold }}</div>
              <div>门状态：{{ result.door_state }}</div>
            </div>
          </div>
        </el-card>
      </div>
    </el-main>
  </el-container>
</template>

<script setup>
import { onMounted, onUnmounted, ref, computed } from "vue";
import { ElMessage } from "element-plus";
import { verifyVoice } from "../api";

const file = ref(null);
const loading = ref(false);
const result = ref(null);
const recording = ref(false);
const waveCanvasRef = ref(null);
const audioUrl = ref("");

let mediaStream = null;
let mediaRecorder = null;
let audioChunks = [];
let audioContext = null;
let analyser = null;
let animationId = null;
let lastRenderedBuffer = null;
const WAVE_HISTORY_POINTS = 2048;
let waveHistory = [];

function onFileChange(e) {
  const f = e.target.files && e.target.files[0];
  file.value = f || null;
  result.value = null;
  if (audioUrl.value) {
    URL.revokeObjectURL(audioUrl.value);
    audioUrl.value = "";
  }
  if (f) {
    audioUrl.value = URL.createObjectURL(f);
  }
}

const resultType = computed(() => {
  if (!result.value) return "info";
  if (result.value.result === "ACCEPT") return "success";
  if (result.value.result === "REJECT") return "warning";
  return "error";
});

const resultTitle = computed(() => {
  if (!result.value) return "";
  if (result.value.result === "ACCEPT") return "识别成功，门已打开";
  if (result.value.result === "REJECT") return "识别失败，未通过当前阈值";
  if (result.value.error) return "识别出错";
  return "识别结果异常";
});

const resultSubtitle = computed(() => {
  if (!result.value) return "";
  if (result.value.result === "ACCEPT") {
    return "如需查看个人信息或管理声纹，请在电脑或手机上使用账号登录系统。";
  }
  if (result.value.result === "REJECT") {
    return "可能未注册声纹或声音不匹配，如需开通或维护声纹，请联系管理员为你开通账号并登录个人页面录入声纹。";
  }
  if (result.value.error) {
    return "如多次出现此错误，请联系管理员检查声纹模板或系统配置。";
  }
  return "";
});

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
    file.value = new File([wavBlob], "recorded.wav", { type: "audio/wav" });
    if (audioUrl.value) {
      URL.revokeObjectURL(audioUrl.value);
    }
    audioUrl.value = URL.createObjectURL(file.value);
    result.value = null;
    ElMessage.success("录音完成，可以点击“开始识别”进行验证");
  } catch (e) {
    ElMessage.error("处理录音数据失败，请重试或改用文件上传");
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

function handleClearRecording() {
  stopRecording();
  file.value = null;
  result.value = null;
  waveHistory = [];
  lastRenderedBuffer = null;
  if (audioUrl.value) {
    URL.revokeObjectURL(audioUrl.value);
    audioUrl.value = "";
  }
  clearWaveCanvas();
}

async function handleVerify() {
  if (!file.value) {
    ElMessage.error("请先选择一个音频文件");
    return;
  }
  const form = new FormData();
  form.append("file", file.value);
  loading.value = true;
  try {
    const res = await verifyVoice(form);
    result.value = res.data;
  } catch (e) {
    const data = e.response && e.response.data;
    const msg = data && data.error ? data.error : "识别失败";
    ElMessage.error(msg);
    result.value = { error: msg, result: "ERROR", door_state: "CLOSED" };
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  if (waveCanvasRef.value) {
    const canvas = waveCanvasRef.value;
    canvas.width = canvas.clientWidth;
    canvas.height = canvas.clientHeight || 120;
  }
});

onUnmounted(() => {
  stopRecording();
  if (audioUrl.value) {
    URL.revokeObjectURL(audioUrl.value);
  }
});
</script>

<style scoped>
.verify-wrapper {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.verify-card {
  width: 520px;
}

.verify-title {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 16px;
}

.result-block {
  margin-top: 16px;
}

.result-detail {
  margin-top: 12px;
  font-size: 14px;
  line-height: 1.6;
}

.result-subtitle {
  margin-bottom: 8px;
  color: #909399;
}

.record-section {
  margin-bottom: 16px;
}

.record-header {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
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

.playback {
  margin-top: 10px;
}
</style>
