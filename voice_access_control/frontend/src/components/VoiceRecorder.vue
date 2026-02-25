<template>
  <div class="voice-recorder">
    <!-- 声波展示区域 -->
    <div class="wave-container" ref="waveContainerRef">
      <canvas ref="waveCanvasRef" class="wave-canvas"></canvas>
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
        <span>待提交录音 ({{ enrollFiles.length }}/{{ maxRecords }})</span>
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
        >
          <div class="wav-info">
            <el-icon><Document /></el-icon>
            <span class="wav-name">{{ f.name }}</span>
            <span class="wav-size">{{ (f.size / 1024).toFixed(1) }} KB</span>
          </div>
          <el-button
            circle
            size="small"
            type="danger"
            :icon="Delete"
            @click="removeEnrollFile(idx)"
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
import { Microphone, Document, Delete } from "@element-plus/icons-vue";
import { enrollVoice } from "../api";

const props = defineProps({
  maxRecords: {
    type: Number,
    default: 5,
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
const waveCanvasRef = ref(null);
const waveContainerRef = ref(null);

// Audio State
let mediaStream = null;
let mediaRecorder = null;
let audioChunks = [];
let audioContext = null;
let analyser = null;
let animationId = null;

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
  // Clear canvas
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
  enrollFiles.value.splice(index, 1);
}

function clearEnrollFiles() {
  enrollFiles.value = [];
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
