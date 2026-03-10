<template>
  <div class="voice-verify-container">
    <!-- Grok Navigation -->
    <nav class="verify-nav">
      <div class="nav-logo">
        <span class="logo-symbol">///</span>
        <span class="logo-text">VOICE ACCESS</span>
      </div>
      <div class="nav-actions">
        <button v-if="!hasToken" @click="handleEntry" class="grok-btn-ghost">LOGIN</button>
        <template v-else>
          <button @click="handleEntry" class="grok-btn-ghost">PROFILE</button>
          <button @click="handleLogout" class="grok-btn-ghost">LOGOUT</button>
        </template>
      </div>
    </nav>

    <!-- Hero Content -->
    <main class="verify-hero">
      <div class="hero-content">
        <h1 class="hero-title">Voice Access</h1>
        
        <!-- Status / Prompt -->
        <div class="hero-status">
          <span v-if="isStreaming" class="status-live">
            <span class="pulse-dot"></span> Listening...
          </span>
          <span v-else>{{ statusMessage || 'Identity Verification System' }}</span>
        </div>

        <!-- Result Display -->
        <div class="result-card" :class="[resultStatusClass, { 'is-idle': !hasResult }]">
          <div class="result-header">
            <span class="result-label">VERIFICATION RESULT</span>
            <span class="result-score" v-if="currentScore">{{ (currentScore * 100).toFixed(1) }}% MATCH</span>
          </div>
          <div class="result-body" v-if="hasResult">
            <div class="result-user">{{ currentUserIdentity || 'Unknown' }}</div>
            <div class="result-status">{{ currentStatus }}</div>
          </div>
          <div class="result-body is-placeholder" v-else>
            <div class="result-user placeholder-line"></div>
            <div class="result-status placeholder-line short"></div>
          </div>
          <div class="result-message" v-if="agentResult?.agent?.response">
            "{{ agentResult.agent.response }}"
          </div>
          <div class="result-message stream-hint" v-else>
            <span v-if="isStreaming" class="streaming-dots">Streaming response</span>
            <span v-else>Awaiting voice input</span>
          </div>
        </div>

        <!-- Input Area (Grok Style) -->
        <div class="input-container">
          <div class="input-actions solo">
            <button class="action-btn upload-btn" @click="triggerFileSelect" title="Upload Audio">
              <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
            </button>
            <button
              class="mic-btn"
              :class="{ active: isStreaming }"
              @click="toggleStreaming"
            >
              <div class="mic-icon">
                <svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                  <path d="M12 19v4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                  <path d="M8 23h8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </div>
            </button>
          </div>
          <!-- Hidden File Input -->
          <input
            ref="fileInputRef"
            class="hidden-input"
            type="file"
            accept=".wav"
            @change="onFileChange"
          />
        </div>
        
        <div class="file-info" v-if="file">
           Selected: {{ file.name }}
           <button class="text-btn" @click="handleVerify">Start Analysis</button>
        </div>

      </div>

      <!-- Waveform Background -->
      <div class="wave-bg">
        <canvas ref="waveCanvasRef"></canvas>
      </div>
    </main>

    <!-- Login Dialog -->
    <el-dialog v-model="loginVisible" title="LOGIN" width="360px" center append-to-body class="grok-dialog">
      <el-form @submit.prevent>
        <el-form-item label="USERNAME">
          <el-input v-model="loginUsername" autocomplete="username" />
        </el-form-item>
        <el-form-item label="PASSWORD">
          <el-input
            v-model="loginPassword"
            type="password"
            show-password
            autocomplete="current-password"
          />
        </el-form-item>
        <el-form-item>
          <el-button class="grok-btn-action" :loading="loginLoading" @click="handleLogin" style="width: 100%">
            ENTER
          </el-button>
        </el-form-item>
      </el-form>
    </el-dialog>
  </div>
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

const currentUserIdentity = computed(() => {
  if (agentResult.value?.identity) return agentResult.value.identity.user;
  if (result.value?.predicted_user) return result.value.predicted_user;
  return null;
});

const currentScore = computed(() => {
  if (agentResult.value?.identity) return agentResult.value.identity.score;
  if (result.value?.score) return result.value.score;
  return null;
});

const currentStatus = computed(() => {
  if (agentResult.value?.identity) return agentResult.value.identity.status;
  if (result.value?.result) return result.value.result;
  return null;
});

const resultStatusClass = computed(() => {
  const status = currentStatus.value;
  if (status === 'ACCEPT') return 'status-success';
  if (status === 'REJECT') return 'status-warning';
  return 'status-neutral';
});
const hasResult = computed(() => Boolean(agentResult.value || result.value));

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
    // ctx.fillStyle = "#000000"; // Removed to keep transparent
    // ctx.fillRect(0, 0, width, height);
    
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#06b6d4"; // Cyan
    ctx.shadowBlur = 15;
    ctx.shadowColor = "rgba(6, 182, 212, 0.8)";
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
// Audio Playback Logic (TTS)
// -----------------------------------------------------------------------------
let mediaSource = null;
let sourceBuffer = null;
let audioPlayer = new Audio(); // Global player instance
let audioQueue = [];           // Binary queue
let isAudioUpdating = false;   // Renamed from isUpdating to avoid conflicts

const initAudioStream = () => {
    audioPlayer.pause();
    audioQueue = [];
    isAudioUpdating = false;

    mediaSource = new MediaSource();
    audioPlayer.src = URL.createObjectURL(mediaSource);

    mediaSource.addEventListener('sourceopen', () => {
        try {
            // Edge TTS returns MP3 (audio/mpeg)
            sourceBuffer = mediaSource.addSourceBuffer('audio/mpeg');
            sourceBuffer.addEventListener('updateend', () => {
                isAudioUpdating = false;
                processQueue();
            });
        } catch (e) {
            console.error("MSE AddSourceBuffer Error:", e);
        }
    });

    audioPlayer.play().catch(e => console.error("等待用户交互以播放音频"));
};

const processQueue = () => {
    if (isAudioUpdating || audioQueue.length === 0 || !sourceBuffer || sourceBuffer.updating) {
        return;
    }

    isAudioUpdating = true;
    const chunk = audioQueue.shift();
    try {
        sourceBuffer.appendBuffer(chunk);
    } catch (e) {
        console.error("SourceBuffer Append Error:", e);
        isAudioUpdating = false;
    }
};

const stopAudio = () => {
    audioPlayer.pause();
    audioQueue = [];
    isAudioUpdating = false;

    if (mediaSource) {
        if (mediaSource.readyState === 'open') {
            try {
                mediaSource.endOfStream();
            } catch (e) {
            }
        }
        mediaSource = null;
    }

    if (audioPlayer.src) {
        URL.revokeObjectURL(audioPlayer.src);
        audioPlayer.src = '';
    }
};

const handleAudioChunk = (base64Data) => {
    try {
        const binaryString = atob(base64Data);
        const len = binaryString.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }

        audioQueue.push(bytes);
        processQueue();
    } catch (e) {
        console.error("Base64 Decode Error:", e);
    }
};

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
      initAudioStream(); // Initialize audio playback
      await startAudioCapture();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'result') {
          agentResult.value = data;
          // Handle TTS Audio if present
          if (data.audio) {
              handleAudioChunk(data.audio);
          }
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
  stopAudio(); // Stop audio playback
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
/* Grok Theme for Voice Verify */
.voice-verify-container {
  min-height: 100vh;
  width: 100vw;
  background-color: var(--bg-primary);
  color: var(--text-primary);
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
  font-family: var(--font-body);
}

/* Nav */
.verify-nav {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 48px;
  z-index: 50;
}

.nav-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 20px;
  letter-spacing: 0.05em;
  color: var(--text-primary);
}

.logo-symbol {
  font-size: 24px;
}

.nav-actions {
  display: flex;
  gap: 16px;
}

.grok-btn-ghost {
  background: transparent;
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 500;
  padding: 10px 24px;
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.2s;
  letter-spacing: 0.05em;
}

.grok-btn-ghost:hover {
  border-color: var(--text-primary);
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.05);
}

/* Hero */
.verify-hero {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 10;
  padding-bottom: 100px;
}

.hero-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  max-width: 800px;
  padding: 0 24px;
  text-align: center;
  position: relative;
  z-index: 2;
}

.hero-title {
  font-family: var(--font-display);
  font-size: 120px;
  font-weight: 700;
  letter-spacing: -0.04em;
  line-height: 1;
  margin-bottom: 24px;
  background: linear-gradient(180deg, #fff 0%, #aaa 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  opacity: 0.9;
  text-shadow: 0 0 80px rgba(255, 255, 255, 0.15);
}

.hero-status {
  font-family: var(--font-mono);
  font-size: 16px;
  color: var(--text-secondary);
  margin-bottom: 48px;
  min-height: 24px;
  letter-spacing: 0.05em;
}

.status-live {
  color: var(--accent-secondary);
  display: flex;
  align-items: center;
  gap: 8px;
}

.pulse-dot {
  width: 8px;
  height: 8px;
  background: currentColor;
  border-radius: 50%;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.5); }
  100% { opacity: 1; transform: scale(1); }
}

/* Input Area */
.input-container {
  width: 100%;
  max-width: 640px;
  position: relative;
  display: flex;
  justify-content: center;
  margin-top: 120px;
}

.input-actions {
  display: flex;
  align-items: center;
  gap: 18px;
}

.input-actions.solo {
  background: transparent;
  padding: 0;
}

.action-btn {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  cursor: pointer;
  padding: 12px;
  border-radius: 999px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.action-btn:hover {
  color: var(--text-primary);
  border-color: var(--text-primary);
  box-shadow: 0 0 18px rgba(255, 255, 255, 0.15);
}

.mic-btn {
  background: var(--text-primary);
  color: var(--bg-primary);
  border: none;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 0 22px rgba(255, 255, 255, 0.25);
}

.mic-btn:hover {
  transform: scale(1.1);
  box-shadow: 0 0 20px rgba(255, 255, 255, 0.4);
}

.mic-btn.active {
  background: var(--accent-danger);
  color: #fff;
  animation: pulse-ring 2s infinite;
}

@keyframes pulse-ring {
  0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
  70% { box-shadow: 0 0 0 15px rgba(239, 68, 68, 0); }
  100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
}

.hidden-input {
  display: none;
}

.file-info {
  margin-top: 12px;
  font-size: 13px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 12px;
}

.text-btn {
  background: transparent;
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  padding: 4px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

/* Result Card */
.result-card {
  margin-bottom: 32px;
  background: rgba(20, 20, 20, 0.9);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 24px;
  width: 100%;
  max-width: 400px;
  text-align: left;
  backdrop-filter: blur(20px);
  transition: all 0.35s ease;
  position: relative;
  z-index: 3;
}

.result-card.status-success {
  border-color: rgba(16, 185, 129, 0.5);
  box-shadow: 0 0 30px rgba(16, 185, 129, 0.15);
}

.result-card.status-warning {
  border-color: rgba(239, 68, 68, 0.5);
  box-shadow: 0 0 30px rgba(239, 68, 68, 0.15);
}

.result-card.is-idle {
  border-color: rgba(255, 255, 255, 0.08);
  box-shadow: none;
  opacity: 0.7;
}

.result-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-secondary);
}

.result-body {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12px;
}

.result-body.is-placeholder {
  gap: 16px;
}

.result-user {
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
}

.result-status {
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 600;
}

.status-success .result-status { color: var(--accent-success); }
.status-warning .result-status { color: var(--accent-danger); }

.result-message {
  font-size: 14px;
  color: var(--text-secondary);
  font-style: italic;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.stream-hint {
  font-style: normal;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-tertiary);
}

.streaming-dots::after {
  content: " ···";
  animation: dots 1.5s infinite;
}

@keyframes dots {
  0% { content: " ·"; }
  33% { content: " ··"; }
  66% { content: " ···"; }
  100% { content: " ·"; }
}

.placeholder-line {
  height: 18px;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.18), rgba(255, 255, 255, 0.08));
  border-radius: 6px;
  width: 160px;
  animation: shimmer 1.8s infinite;
}

.placeholder-line.short {
  width: 80px;
  height: 14px;
}

@keyframes shimmer {
  0% { background-position: -200px 0; }
  100% { background-position: 200px 0; }
}

/* Wave Background */
.wave-bg {
  position: absolute;
  top: 68%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: min(720px, 88vw);
  height: 120px;
  z-index: 0;
  opacity: 0.45;
  pointer-events: none;
}

.wave-bg canvas {
  width: 100%;
  height: 100%;
}

/* Transitions */
.fade-slide-enter-active, .fade-slide-leave-active {
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}
.fade-slide-enter-from, .fade-slide-leave-to {
  opacity: 0;
  transform: translateY(20px);
}
</style>
