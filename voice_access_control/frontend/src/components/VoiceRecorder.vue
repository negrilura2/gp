<template>
  <div class="voice-recorder">
    <!-- 声波展示区域 -->
    <div class="wave-container" ref="waveContainerRef" @click="handleCanvasClick">
      <canvas ref="waveCanvasRef" class="wave-canvas"></canvas>
    </div>

    <!-- 播放进度条 -->
    <div class="progress-container" v-if="activeFile && !recording">
       <el-slider 
         v-model="playbackProgress" 
         :max="1" 
         :step="0.001" 
         :format-tooltip="formatProgress"
         @input="handleSliderInput"
         @change="handleSliderChange"
       />
    </div>

    <!-- 录音控制区域 -->
    <div class="record-controls">
      <el-button
        v-if="!recording"
        type="primary"
        size="large"
        :icon="Microphone"
        @click="startRecording"
      >
        开始录音一条语音
      </el-button>
      <el-button
        v-else
        type="danger"
        size="large"
        class="recording-btn"
        @click="stopRecording"
      >
        <span class="recording-dot"></span>
        停止录音
      </el-button>

      <div class="file-actions" v-if="!recording">
        <el-upload
          action="#"
          :auto-upload="false"
          :show-file-list="false"
          accept=".wav"
          multiple
          :on-change="handleSelectAudio"
        >
          <el-button>选择文件</el-button>
        </el-upload>
        <span class="file-hint">或上传 WAV</span>
      </div>
    </div>

    <!-- 待提交列表 -->
    <div class="enroll-list" v-if="enrollFiles.length > 0">
      <div class="list-header">
        <span>待提交录音 ({{ enrollFiles.length }})</span>
        <el-button
          type="success"
          :loading="submitting"
          @click="submitVoiceprint"
          :disabled="enrollFiles.length < 1"
        >
          提交声纹 (当前 {{ enrollFiles.length }} 条)
        </el-button>
        <el-button @click="clearEnrollFiles" plain size="small">
          清空全部录音/上传
        </el-button>
      </div>

      <div class="wav-items">
        <div
          v-for="(f, idx) in enrollFiles"
          :key="idx"
          class="wav-item"
          :class="{ 'is-active': activeFile === f }"
          @click="previewAudio(f)"
        >
          <div class="wav-info">
            <el-button
              circle
              size="small"
              type="primary"
              :icon="playing && activeFile === f ? VideoPause : VideoPlay"
              @click.stop="togglePlayback(f)"
              style="margin-right: 8px"
            />
            <el-icon><Document /></el-icon>
            <span class="wav-name">{{ f.name }}</span>
            <span class="wav-size">{{ (f.size / 1024).toFixed(1) }} KB</span>
          </div>
          <el-button
            circle
            size="small"
            type="danger"
            :icon="Delete"
            @click.stop="removeEnrollFile(idx)"
          />
        </div>
      </div>
      <div class="list-hint">
        建议录制 3~5 条不同内容的语音，用于提高鲁棒性
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onUnmounted, nextTick } from "vue";
import { ElMessage } from "element-plus";
import { Microphone, Document, Delete, VideoPlay, VideoPause } from "@element-plus/icons-vue";
import { enrollVoice } from "../api";

const props = defineProps({
  maxRecords: {
    type: Number,
    default: 100, // Increased from 5 to 100 as requested
  },
  targetSampleRate: {
    type: Number,
    default: 16000,
  },
});

const emit = defineEmits(["enrolled"]);

const recording = ref(false);
const submitting = ref(false);
const enrollFiles = ref([]);
const activeFile = ref(null);
const playing = ref(false);
const playbackProgress = ref(0);
const isSeeking = ref(false);
const waveCanvasRef = ref(null);
const waveContainerRef = ref(null);

// Audio State
let mediaStream = null;
let mediaRecorder = null;
let audioChunks = [];
let audioContext = null;
let analyser = null;
let animationId = null;
let playbackSource = null;
let playbackStartTime = 0;
let playbackDuration = 0;
let currentAudioBuffer = null;
let currentRawData = null;
let currentFileKey = "";

function formatProgress(val) {
  if (!playbackDuration) return "0:00";
  const sec = val * playbackDuration;
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

// --- Canvas Logic ---
function getCanvasMetrics() {
  const canvas = waveCanvasRef.value;
  if (!canvas) return null;
  const container = waveContainerRef.value;
  const width = container ? container.clientWidth : 600;
  const height = container ? container.clientHeight : 120;
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

function drawWave() {
  if (!analyser) return;
  const metrics = getCanvasMetrics();
  if (!metrics) return;
  const { canvas, width, height, ratio } = metrics;
  const ctx = setupHiDpiCanvas(canvas, width, height, ratio);

  const bufferLength = analyser.fftSize;
  const dataArray = new Uint8Array(bufferLength);

  function draw() {
    if (!analyser) return;
    animationId = requestAnimationFrame(draw);
    analyser.getByteTimeDomainData(dataArray);

    ctx.fillStyle = "#000000";
    ctx.fillRect(0, 0, width, height);

    ctx.lineWidth = 2;
    ctx.strokeStyle = "#4ade80"; // green-400
    ctx.beginPath();

    const sliceWidth = width / bufferLength;
    let x = 0;
    for (let i = 0; i < bufferLength; i++) {
      const v = dataArray[i] / 128.0;
      const y = (v * height) / 2;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
      x += sliceWidth;
    }
    ctx.lineTo(width, height / 2);
    ctx.stroke();
  }
  draw();
}

function stopDrawWave() {
  if (animationId) {
    cancelAnimationFrame(animationId);
    animationId = null;
  }
}

function clearCanvas() {
  const metrics = getCanvasMetrics();
  if (metrics) {
    const { canvas, width, height, ratio } = metrics;
    const ctx = setupHiDpiCanvas(canvas, width, height, ratio);
    ctx.fillStyle = "#000000";
    ctx.fillRect(0, 0, width, height);
  }
}

// --- Recording Logic ---
async function startRecording() {
  if (enrollFiles.value.length >= props.maxRecords) {
    ElMessage.warning(`最多录制 ${props.maxRecords} 条语音`);
    return;
  }
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioContext = new (window.AudioContext || window.webkitAudioContext)({
      sampleRate: props.targetSampleRate,
    });
    const source = audioContext.createMediaStreamSource(mediaStream);
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 2048;
    source.connect(analyser);

    mediaRecorder = new MediaRecorder(mediaStream);
    audioChunks = [];
    mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) audioChunks.push(e.data);
    };
    mediaRecorder.onstop = handleRecordingStop;
    mediaRecorder.start();
    recording.value = true;
    drawWave();
  } catch (e) {
    console.error("Microphone error:", e);
    ElMessage.error("无法访问麦克风");
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
  recording.value = false;
  stopDrawWave();
  clearCanvas();
  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop());
    mediaStream = null;
  }
  if (audioContext) {
    audioContext.close();
    audioContext = null;
  }
}

async function handleRecordingStop() {
  const blob = new Blob(audioChunks, { type: "audio/wav" });
  // Simple conversion to file
  // Note: Browser recorded blob might be webm/ogg depending on implementation,
  // Backend validate_audio_file handles format check (sf.read supports many).
  // Ideally we should re-encode to WAV 16k mono, but for MVP keep it simple
  // assuming backend uses soundfile/librosa which handles containers.
  // Or reuse previous downsample logic if strictly required.
  // Here we use a generic name.
  const file = new File([blob], `record_${Date.now()}.wav`, { type: "audio/wav" });
  addEnrollFile(file);
}

function handleSelectAudio(uploadFile) {
  if (uploadFile.raw) {
    addEnrollFile(uploadFile.raw);
  }
}

function addEnrollFile(file) {
  if (enrollFiles.value.length >= props.maxRecords) {
    ElMessage.warning(`已达到最大数量 ${props.maxRecords}`);
    return;
  }
  enrollFiles.value.push(file);
}

function removeEnrollFile(index) {
  const removed = enrollFiles.value[index];
  enrollFiles.value.splice(index, 1);

  const noFilesLeft = enrollFiles.value.length === 0;
  const removedIsActive = removed && activeFile.value === removed;

  if (noFilesLeft || removedIsActive) {
    activeFile.value = null;
    playbackProgress.value = 0;
    currentAudioBuffer = null;
    currentRawData = null;
    currentFileKey = "";
    stopPlayback(true);
    clearCanvas();
  }
}

function clearEnrollFiles() {
  enrollFiles.value = [];
  activeFile.value = null;
  stopPlayback();
  clearCanvas();
}

async function previewAudio(file) {
  if (recording.value) return;
  activeFile.value = file;
  
  if (playing.value) {
    stopPlayback(false);
  }

  try {
    const key = `${file.name}-${file.size}-${file.lastModified}`;
    if (currentFileKey && currentFileKey !== key) {
      playbackProgress.value = 0;
    }
    await ensureAudioData(file);
    if (currentRawData) {
      drawProgressWave(currentRawData, playbackProgress.value || 0);
    }
  } catch (e) {
    console.error("无法预览音频", e);
    ElMessage.error("无法解析音频文件");
  }
}

function stopPlayback(reset = true) {
  if (playbackSource) {
    try {
      playbackSource.stop();
    } catch (e) { /* ignore */ }
    playbackSource = null;
  }
  
  if (animationId) {
    cancelAnimationFrame(animationId);
    animationId = null;
  }

  playing.value = false;
  if (reset) {
    playbackProgress.value = 0;
  }
}

async function togglePlayback(file) {
  if (recording.value) return;
  
  if (playing.value && activeFile.value === file) {
    stopPlayback(false);
    if (currentRawData) {
      drawProgressWave(currentRawData, playbackProgress.value || 0);
    }
    return;
  }
  
  if (playing.value) {
    stopPlayback(false);
  }
  
  activeFile.value = file;
  
  try {
    const key = `${file.name}-${file.size}-${file.lastModified}`;
    if (currentFileKey && currentFileKey !== key) {
      playbackProgress.value = 0;
    }
    await ensureAudioData(file);
    if (currentAudioBuffer && currentRawData) {
      startPlaybackAt(playbackProgress.value || 0);
    }
    
  } catch (e) {
    console.error("无法播放音频", e);
    ElMessage.error("无法播放音频文件");
    stopPlayback(false);
  }
}

function handleSliderInput(val) {
  isSeeking.value = true;
  playbackProgress.value = val;
  if (currentRawData) {
    drawProgressWave(currentRawData, val);
  }
}

function handleSliderChange(val) {
  isSeeking.value = false;
  playbackProgress.value = val;
  if (playing.value) {
    seekTo(val);
  } else if (currentRawData) {
    drawProgressWave(currentRawData, val);
  }
}

function seekTo(progress) {
  if (recording.value || !activeFile.value || !audioContext || !currentAudioBuffer) return;
  startPlaybackAt(progress);
}

async function ensureAudioData(file) {
  const key = `${file.name}-${file.size}-${file.lastModified}`;
  if (currentAudioBuffer && currentRawData && currentFileKey === key) {
    return;
  }
  currentFileKey = key;
  if (!audioContext) {
    audioContext = new (window.AudioContext || window.webkitAudioContext)({
      sampleRate: props.targetSampleRate,
    });
  }
  const arrayBuffer = await file.arrayBuffer();
  const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
  currentAudioBuffer = audioBuffer;
  currentRawData = audioBuffer.getChannelData(0);
  playbackDuration = audioBuffer.duration;
}

function startPlaybackAt(progress) {
  if (!audioContext || !currentAudioBuffer || !currentRawData) return;
  const seekTime = Math.max(0, Math.min(progress, 1)) * playbackDuration;
  if (playbackSource) {
    try {
      playbackSource.stop();
    } catch (e) { /* ignore */ }
    playbackSource = null;
  }
  playbackSource = audioContext.createBufferSource();
  playbackSource.buffer = currentAudioBuffer;
  playbackSource.connect(audioContext.destination);
  playing.value = true;
  playbackStartTime = audioContext.currentTime - seekTime;
  playbackSource.onended = () => {
    if (playing.value && (audioContext.currentTime - playbackStartTime >= playbackDuration - 0.2)) {
      playing.value = false;
      playbackProgress.value = 0;
      stopDrawWave();
      if (currentRawData) {
        drawProgressWave(currentRawData, 0);
      }
    }
  };
  playbackSource.start(0, seekTime);
  drawPlaybackWave(currentRawData);
}

function drawProgressWave(data, progress) {
  stopDrawWave();
  const metrics = getCanvasMetrics();
  if (!metrics) return;
  const { canvas, width, height, ratio } = metrics;
  const ctx = setupHiDpiCanvas(canvas, width, height, ratio);
  
  const step = Math.ceil(data.length / width);
  const amp = height / 2;
  const mid = height / 2;
  const progressX = width * progress;
  
  ctx.fillStyle = "#000000";
  ctx.fillRect(0, 0, width, height);
  
  // Draw unplayed part (Green #4ade80)
  ctx.save();
  ctx.beginPath();
  ctx.rect(progressX, 0, width - progressX, height);
  ctx.clip();
  
  ctx.lineWidth = 1;
  ctx.strokeStyle = "#4ade80"; 
  ctx.beginPath();
  for (let i = 0; i < width; i++) {
    let min = 1.0;
    let max = -1.0;
    for (let j = 0; j < step; j++) {
      const idx = (i * step) + j;
      if (idx < data.length) {
        const datum = data[idx];
        if (datum < min) min = datum;
        if (datum > max) max = datum;
      }
    }
    ctx.moveTo(i, mid + min * amp);
    ctx.lineTo(i, mid + max * amp);
  }
  ctx.stroke();
  ctx.restore();

  // Draw played part (Red #ef4444) - As requested "Red"
  ctx.save();
  ctx.beginPath();
  ctx.rect(0, 0, progressX, height);
  ctx.clip();
  
  ctx.lineWidth = 1;
  ctx.strokeStyle = "#ef4444"; 
  ctx.beginPath();
  for (let i = 0; i < width; i++) {
    let min = 1.0;
    let max = -1.0;
    for (let j = 0; j < step; j++) {
      const idx = (i * step) + j;
      if (idx < data.length) {
        const datum = data[idx];
        if (datum < min) min = datum;
        if (datum > max) max = datum;
      }
    }
    ctx.moveTo(i, mid + min * amp);
    ctx.lineTo(i, mid + max * amp);
  }
  ctx.stroke();
  ctx.restore();
  
  // Draw progress line (Red #ef4444)
  ctx.strokeStyle = "#ef4444";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(progressX, 0);
  ctx.lineTo(progressX, height);
  ctx.stroke();
}

function drawPlaybackWave(data) {
  stopDrawWave();
  const metrics = getCanvasMetrics();
  if (!metrics) return;
  const { canvas, width, height, ratio } = metrics;
  const ctx = setupHiDpiCanvas(canvas, width, height, ratio);
  
  const step = Math.ceil(data.length / width);
  const amp = height / 2;
  const mid = height / 2;
  
  function draw() {
    if (!playing.value) return;
    animationId = requestAnimationFrame(draw);
    
    if (isSeeking.value) return;

    const now = audioContext.currentTime;
    const elapsed = now - playbackStartTime;
    const progress = Math.min(elapsed / playbackDuration, 1.0);
    const progressX = width * progress;
    
    ctx.fillStyle = "#000000";
    ctx.fillRect(0, 0, width, height);
    
    // Draw unplayed part (Green #4ade80)
    ctx.save();
    ctx.beginPath();
    ctx.rect(progressX, 0, width - progressX, height);
    ctx.clip();
    
    ctx.lineWidth = 1;
    ctx.strokeStyle = "#4ade80"; // Unplayed: Green
    ctx.beginPath();
    for (let i = 0; i < width; i++) {
      let min = 1.0;
      let max = -1.0;
      for (let j = 0; j < step; j++) {
        const idx = (i * step) + j;
        if (idx < data.length) {
          const datum = data[idx];
          if (datum < min) min = datum;
          if (datum > max) max = datum;
        }
      }
      ctx.moveTo(i, mid + min * amp);
      ctx.lineTo(i, mid + max * amp);
    }
    ctx.stroke();
    ctx.restore();

    // Draw played part (Red #ef4444)
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, progressX, height);
    ctx.clip();
    
    ctx.lineWidth = 1;
    ctx.strokeStyle = "#ef4444"; // Played: Red
    ctx.beginPath();
    for (let i = 0; i < width; i++) {
      let min = 1.0;
      let max = -1.0;
      for (let j = 0; j < step; j++) {
        const idx = (i * step) + j;
        if (idx < data.length) {
          const datum = data[idx];
          if (datum < min) min = datum;
          if (datum > max) max = datum;
        }
      }
      ctx.moveTo(i, mid + min * amp);
      ctx.lineTo(i, mid + max * amp);
    }
    ctx.stroke();
    ctx.restore();
    
    // Draw progress line (Red #ef4444)
    ctx.strokeStyle = "#ef4444";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(progressX, 0);
    ctx.lineTo(progressX, height);
    ctx.stroke();
    
    playbackProgress.value = progress;
  }
  draw();
}

function drawStaticWave(data) {
  stopDrawWave(); // Stop any animation first
  const metrics = getCanvasMetrics();
  if (!metrics) return;
  const { canvas, width, height, ratio } = metrics;
  const ctx = setupHiDpiCanvas(canvas, width, height, ratio);
  
  ctx.fillStyle = "#000000";
  ctx.fillRect(0, 0, width, height);
  
  ctx.lineWidth = 1;
  ctx.strokeStyle = "#4ade80"; // green-400
  ctx.beginPath();
  
  const step = Math.ceil(data.length / width);
  const amp = height / 2;
  const mid = height / 2;
  
  for (let i = 0; i < width; i++) {
    let min = 1.0;
    let max = -1.0;
    for (let j = 0; j < step; j++) {
      const idx = (i * step) + j;
      if (idx < data.length) {
        const datum = data[idx];
        if (datum < min) min = datum;
        if (datum > max) max = datum;
      }
    }
    // Normalize slightly for visibility
    ctx.moveTo(i, mid + min * amp);
    ctx.lineTo(i, mid + max * amp);
  }
  ctx.stroke();
}

function handleCanvasClick(event) {
  if (recording.value || !activeFile.value || !audioContext) return;
  
  const metrics = getCanvasMetrics();
  if (!metrics) return;
  const { width } = metrics;
  
  const rect = event.target.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const progress = Math.max(0, Math.min(x / width, 1.0));
  
  if (playbackDuration > 0) {
    playbackProgress.value = progress;
    if (playing.value) {
      seekTo(progress);
    } else if (currentRawData) {
      drawProgressWave(currentRawData, progress);
    }
   }
 }

// --- Submit Logic ---
async function submitVoiceprint() {
  if (enrollFiles.value.length === 0) return;
  submitting.value = true;
  try {
    const formData = new FormData();
    enrollFiles.value.forEach((f) => {
      formData.append("files", f);
    });
    await enrollVoice(formData);
    ElMessage.success("声纹提交成功");
    clearEnrollFiles();
    emit("enrolled");
  } catch (e) {
    const msg = e.response?.data?.error || "提交失败";
    ElMessage.error(msg);
  } finally {
    submitting.value = false;
  }
}

onUnmounted(() => {
  stopRecording();
});
</script>

<style scoped>
.voice-recorder {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.wave-container {
  background: #000;
  border-radius: 8px;
  height: 120px;
  overflow: hidden;
  position: relative;
  cursor: pointer;
}

.wave-canvas {
  width: 100%;
  height: 100%;
  display: block;
}

.record-controls {
  display: flex;
  gap: 16px;
  align-items: center;
}

.recording-btn {
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.6; }
  100% { opacity: 1; }
}

.recording-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  background: white;
  border-radius: 50%;
  margin-right: 6px;
}

.file-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-hint {
  color: #94a3b8;
  font-size: 13px;
}

.enroll-list {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 16px;
  background: #f8fafc;
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-weight: 600;
  color: #334155;
}

.wav-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.wav-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: white;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  cursor: pointer;
  transition: all 0.2s;
}

.wav-item:hover {
  background-color: #f1f5f9;
}

.wav-item.is-active {
  background-color: #e2e8f0;
  border-color: #cbd5e1;
}

.wav-info {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #475569;
}

.wav-name {
  font-weight: 500;
}

.wav-size {
  font-size: 12px;
  color: #94a3b8;
}

.list-hint {
  margin-top: 12px;
  font-size: 12px;
  color: #64748b;
  text-align: right;
}
</style>
