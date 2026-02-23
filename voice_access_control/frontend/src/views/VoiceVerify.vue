<template>
  <el-container style="height: 100vh">
    <el-main>
      <div class="verify-wrapper">
        <el-card class="verify-card">
          <div class="verify-header">
            <div class="verify-title">声纹识别 & 智能助手</div>
            <div class="verify-actions">
              <el-button size="small" @click="handleEntry">
                {{ hasToken ? "个人中心" : "登录" }}
              </el-button>
              <el-button
                v-if="hasToken"
                size="small"
                type="danger"
                plain
                @click="handleLogout"
              >
                退出登录
              </el-button>
            </div>
          </div>
          <div class="record-section">
            <div class="record-header">实时对话 (WebSocket)</div>
            <div class="record-main">
              <div class="wave-header">
                <span class="wave-title">声波图</span>
                <span class="wave-subtitle">请清晰说话，系统将自动识别身份并执行指令</span>
              </div>
              <canvas ref="waveCanvasRef" class="wave-canvas"></canvas>
              <div class="record-actions">
                <el-button
                  :type="isStreaming ? 'danger' : 'primary'"
                  @click="toggleStreaming"
                >
                  {{ isStreaming ? "停止对话" : "开始对话" }}
                </el-button>
                <span class="record-hint">
                  {{ statusMessage }}
                </span>
              </div>
              
              <!-- Agent 交互结果展示 -->
              <div v-if="agentResult" class="agent-result-box">
                <div class="agent-header">
                  <span class="agent-title">助手回复</span>
                  <el-tag size="small" :type="agentResult.identity.status === 'ACCEPT' ? 'success' : 'warning'">
                    {{ agentResult.identity.user }} ({{ agentResult.identity.score?.toFixed(2) }})
                  </el-tag>
                </div>
                <div class="agent-content">
                  <p><strong>你说:</strong> {{ agentResult.text }}</p>
                  <p v-if="agentResult.agent?.response">
                    <strong>助手:</strong> {{ agentResult.agent.response }}
                  </p>
                  <p v-else-if="agentResult.agent?.message" class="error-text">
                    <strong>错误:</strong> {{ agentResult.agent.message }}
                  </p>
                </div>
              </div>

            </div>
          </div>
          
          <el-divider>旧版文件上传</el-divider>
          
          <el-collapse>
            <el-collapse-item title="上传录音文件 (Legacy)" name="1">
              <el-form label-width="80px">
                <el-form-item label="音频文件">
                  <input
                    ref="fileInputRef"
                    class="file-input"
                    type="file"
                    accept=".wav"
                    @change="onFileChange"
                  />
                  <el-button size="small" @click="triggerFileSelect">选择文件</el-button>
                  <span class="file-hint">{{ fileLabel }}</span>
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
                  <div>预测用户：{{ result.predicted_user }}</div>
                  <div>得分：{{ result.score }}</div>
                  <div>阈值：{{ result.threshold }}</div>
                </div>
              </div>
            </el-collapse-item>
          </el-collapse>

        </el-card>
      </div>
    </el-main>
  </el-container>
  <el-dialog v-model="loginVisible" title="登录" width="360px" center>
    <el-form @submit.prevent>
      <el-form-item label="用户名">
        <el-input v-model="loginUsername" autocomplete="username" />
      </el-form-item>
      <el-form-item label="密码">
        <el-input
          v-model="loginPassword"
          type="password"
          show-password
          autocomplete="current-password"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="loginLoading" @click="handleLogin">
          登录
        </el-button>
      </el-form-item>
    </el-form>
  </el-dialog>
</template>

<script setup>
import { onMounted, onUnmounted, ref, computed } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { verifyVoice, login as apiLogin, setAuthToken } from "../api";

const router = useRouter();

const file = ref(null);
const loading = ref(false);
const result = ref(null);
// WebSocket Streaming State
const isStreaming = ref(false);
const statusMessage = ref("点击开始对话以连接系统");
const agentResult = ref(null);
let ws = null;
// Audio Context for Streaming
let streamMediaStream = null;
let streamAudioContext = null;
let streamScriptProcessor = null;

// Legacy Recording State (kept for now)
const recording = ref(false);
const waveCanvasRef = ref(null);
const audioUrl = ref("");
const audioRef = ref(null);
const fileInputRef = ref(null);
const staticWaveValues = ref([]);
const playProgress = ref(0);

const tokenState = ref(localStorage.getItem("token") || "");
const hasToken = computed(() => Boolean(tokenState.value));
const fileLabel = computed(() => (file.value ? file.value.name : "未选择文件"));
const loginVisible = ref(false);
const loginUsername = ref("");
const loginPassword = ref("");
const loginLoading = ref(false);

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

function triggerFileSelect() {
  if (fileInputRef.value) {
    fileInputRef.value.click();
  }
}

async function onFileChange(e) {
  const f = e.target.files && e.target.files[0];
  file.value = f || null;
  result.value = null;
  if (audioRef.value) {
    audioRef.value.pause();
    audioRef.value.currentTime = 0;
  }
  if (audioUrl.value) {
    URL.revokeObjectURL(audioUrl.value);
    audioUrl.value = "";
  }
  staticWaveValues.value = [];
  playProgress.value = 0;
  if (f) {
    audioUrl.value = URL.createObjectURL(f);
    await loadWaveFromFile(f);
  } else {
    clearWaveCanvas();
  }
  if (e.target) {
    e.target.value = "";
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

function handleEntry() {
  if (hasToken.value) {
    router.push("/me");
  } else {
    loginVisible.value = true;
  }
}

async function handleLogin() {
  if (!loginUsername.value || !loginPassword.value) {
    ElMessage.error("请输入用户名和密码");
    return;
  }
  loginLoading.value = true;
  try {
    const res = await apiLogin(loginUsername.value, loginPassword.value);
    const token = res.data.token;
    const isStaff = res.data.is_staff;
    localStorage.setItem("token", token);
    setAuthToken(token);
    tokenState.value = token;
    ElMessage.success("登录成功");
    loginVisible.value = false;
    if (isStaff) {
      router.push("/admin");
    } else {
      router.push("/me");
    }
  } catch (e) {
    const msg =
      e.response && e.response.data && e.response.data.error
        ? e.response.data.error
        : "登录失败";
    ElMessage.error(msg);
  } finally {
    loginLoading.value = false;
  }
}

function handleLogout() {
  localStorage.removeItem("token");
  setAuthToken(null);
  tokenState.value = "";
  ElMessage.success("已退出登录");
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

async function loadWaveFromFile(f) {
  try {
    const arrayBuffer = await f.arrayBuffer();
    const renderedBuffer = await decodeToTargetBuffer(arrayBuffer);
    lastRenderedBuffer = renderedBuffer;
    const values = buildWaveValuesFromBuffer(renderedBuffer);
    staticWaveValues.value = values;
    renderBaseWave(values);
    renderStaticWave(values, 0);
  } catch (e) {
    ElMessage.error("解析音频文件失败");
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
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop());
    mediaStream = null;
  }
  if (animationId) {
    cancelAnimationFrame(animationId);
    animationId = null;
  }
  recording.value = false;
}

// -----------------------------------------------------------------------------
// WebSocket Streaming Logic
// -----------------------------------------------------------------------------
const TARGET_SAMPLE_RATE = 16000;
const BUFFER_SIZE = 4096;

function toggleStreaming() {
  if (isStreaming.value) {
    stopWebSocket();
  } else {
    startWebSocket();
  }
}

async function startWebSocket() {
  try {
    statusMessage.value = "正在连接...";
    // WebSocket URL (adjust if needed, assumes backend on port 9000)
    // Note: If using proxy in vite.config.js, this might need to be ws://localhost:xxxx/api/ws/audio
    // But backend ai_app.py runs on 9000. Let's try direct connection first.
    const wsUrl = "ws://localhost:9000/ws/audio"; 
    ws = new WebSocket(wsUrl);

    ws.onopen = async () => {
      console.log("WebSocket connected");
      statusMessage.value = "已连接，请说话...";
      isStreaming.value = true;
      agentResult.value = null; // Clear previous result
      await startAudioCapture();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'result') {
          agentResult.value = data;
          // Sync with legacy result format for compatibility
          if (data.identity) {
             result.value = {
                predicted_user: data.identity.user,
                score: data.identity.score,
                threshold: "N/A",
                result: data.identity.status,
                door_state: data.identity.status === 'ACCEPT' ? 'OPEN' : 'CLOSED'
             };
          }
        } else if (data.type === 'error') {
          ElMessage.error(data.message);
        }
      } catch (e) {
        console.error("Parse error", e);
      }
    };

    ws.onclose = () => {
      console.log("WebSocket closed");
      if (isStreaming.value) {
        stopWebSocket();
      }
      statusMessage.value = "连接已断开";
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
      statusMessage.value = "连接错误";
    };

  } catch (e) {
    console.error(e);
    ElMessage.error("无法启动 WebSocket");
    isStreaming.value = false;
  }
}

function stopWebSocket() {
  isStreaming.value = false;
  statusMessage.value = "会话结束";
  
  if (ws) {
    ws.close();
    ws = null;
  }
  stopAudioCapture();
}

async function startAudioCapture() {
  try {
    streamMediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamAudioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = streamAudioContext.createMediaStreamSource(streamMediaStream);
    
    // Setup Analyzer for Visualization
    analyser = streamAudioContext.createAnalyser();
    analyser.fftSize = 2048;
    source.connect(analyser);
    
    // Start visualization loop if not already running
    if (!animationId) {
      drawWave();
    }
    
    // Use ScriptProcessor for wide compatibility (deprecated but simple for prototype)
    streamScriptProcessor = streamAudioContext.createScriptProcessor(BUFFER_SIZE, 1, 1);
    
    source.connect(streamScriptProcessor);
    streamScriptProcessor.connect(streamAudioContext.destination);

    streamScriptProcessor.onaudioprocess = (e) => {
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      
      const inputData = e.inputBuffer.getChannelData(0);
      // Downsample and convert to int16
      const pcm16 = downsampleBuffer(inputData, streamAudioContext.sampleRate, TARGET_SAMPLE_RATE);
      ws.send(pcm16);
    };
  } catch (e) {
    console.error("Audio capture error:", e);
    ElMessage.error("无法访问麦克风");
    stopWebSocket();
  }
}

function stopAudioCapture() {
  if (streamMediaStream) {
    streamMediaStream.getTracks().forEach(track => track.stop());
    streamMediaStream = null;
  }
  if (streamScriptProcessor) {
    streamScriptProcessor.disconnect();
    streamScriptProcessor = null;
  }
  if (analyser) {
    analyser.disconnect();
    analyser = null;
  }
  if (streamAudioContext) {
    streamAudioContext.close();
    streamAudioContext = null;
  }
  if (animationId) {
    cancelAnimationFrame(animationId);
    animationId = null;
  }
}

function downsampleBuffer(buffer, sampleRate, outSampleRate) {
    if (outSampleRate == sampleRate) {
        // Convert float32 to int16 directly
        const result = new Int16Array(buffer.length);
        for (let i = 0; i < buffer.length; i++) {
            const s = Math.max(-1, Math.min(1, buffer[i]));
            result[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        return result;
    }
    if (outSampleRate > sampleRate) {
        console.warn("Upsampling not supported");
        return new Int16Array(0);
    }
    var sampleRateRatio = sampleRate / outSampleRate;
    var newLength = Math.round(buffer.length / sampleRateRatio);
    var result = new Int16Array(newLength);
    var offsetResult = 0;
    var offsetBuffer = 0;
    while (offsetResult < result.length) {
        var nextOffsetBuffer = Math.round((offsetResult + 1) * sampleRateRatio);
        var accum = 0, count = 0;
        for (var i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
            accum += buffer[i];
            count++;
        }
        var s = Math.max(-1, Math.min(1, accum / count));
        result[offsetResult] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        offsetResult++;
        offsetBuffer = nextOffsetBuffer;
    }
    return result;
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

function handleClearRecording() {
  stopRecording();
  file.value = null;
  result.value = null;
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
  if (audioUrl.value) {
    URL.revokeObjectURL(audioUrl.value);
    audioUrl.value = "";
  }
  if (fileInputRef.value) {
    fileInputRef.value.value = "";
  }
  clearWaveCanvas();
}

async function confirmClearRecording() {
  try {
    await ElMessageBox.confirm("确认清空全部录音/上传？", "提示", {
      confirmButtonText: "确定",
      cancelButtonText: "取消",
      type: "warning"
    });
    handleClearRecording();
  } catch (e) {
    return;
  }
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
  ensureCanvasReady();
});

onUnmounted(() => {
  stopRecording();
  if (playAnimationId) {
    cancelAnimationFrame(playAnimationId);
    playAnimationId = null;
  }
  if (audioUrl.value) {
    URL.revokeObjectURL(audioUrl.value);
  }
  stopWebSocket(); // Cleanup WebSocket
});
</script>

<style scoped>
.verify-wrapper {
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

.verify-card {
  width: 520px;
  border: 1px solid rgba(64, 158, 255, 0.15);
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(6px);
}

.verify-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.verify-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.verify-title {
  font-size: 20px;
  font-weight: 600;
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

.file-input {
  display: none;
}

.file-hint {
  font-size: 12px;
  color: #909399;
  margin-left: 8px;
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

.playback {
  margin-top: 10px;
}
</style>
