<script setup>
import { ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { enrollVoice } from '../services/api'

const form = reactive({
  user_id: ''
})

const items = ref([])
const isRecording = ref(false)
const mediaRecorder = ref(null)
const mediaStream = ref(null)
const audioContext = ref(null)
const audioProcessor = ref(null)
const audioChunks = ref([])
const audioSampleRate = ref(16000)
const mimeType = ref('')
const loading = ref(false)
const fileInputRef = ref(null)
const waveformRef = ref(null)
const analyserNode = ref(null)
const waveformSource = ref(null)
const visualizerContext = ref(null)
const drawId = ref(null)

function addFile(file) {
  const url = URL.createObjectURL(file)
  items.value.push({ file, url })
}

function removeItem(index) {
  const item = items.value[index]
  if (item) {
    URL.revokeObjectURL(item.url)
    items.value.splice(index, 1)
  }
}

function handleFileChange(event) {
  const files = Array.from(event.target.files || [])
  files.forEach(addFile)
  event.target.value = ''
}

function openFileDialog() {
  fileInputRef.value?.click()
}

function resolveMimeType() {
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/ogg']
  const supported = candidates.find((t) => MediaRecorder.isTypeSupported(t))
  return supported || ''
}

function mergeBuffers(buffers, length) {
  const result = new Float32Array(length)
  let offset = 0
  buffers.forEach((buffer) => {
    result.set(buffer, offset)
    offset += buffer.length
  })
  return result
}

function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buffer)
  const writeString = (offset, string) => {
    for (let i = 0; i < string.length; i += 1) {
      view.setUint8(offset + i, string.charCodeAt(i))
    }
  }
  let offset = 0
  writeString(offset, 'RIFF')
  offset += 4
  view.setUint32(offset, 36 + samples.length * 2, true)
  offset += 4
  writeString(offset, 'WAVE')
  offset += 4
  writeString(offset, 'fmt ')
  offset += 4
  view.setUint32(offset, 16, true)
  offset += 4
  view.setUint16(offset, 1, true)
  offset += 2
  view.setUint16(offset, 1, true)
  offset += 2
  view.setUint32(offset, sampleRate, true)
  offset += 4
  view.setUint32(offset, sampleRate * 2, true)
  offset += 4
  view.setUint16(offset, 2, true)
  offset += 2
  view.setUint16(offset, 16, true)
  offset += 2
  writeString(offset, 'data')
  offset += 4
  view.setUint32(offset, samples.length * 2, true)
  offset += 4
  for (let i = 0; i < samples.length; i += 1) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true)
    offset += 2
  }
  return buffer
}

function drawWaveform() {
  if (!waveformRef.value || !analyserNode.value) return
  const canvas = waveformRef.value
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const width = canvas.clientWidth || 600
  const height = canvas.clientHeight || 120
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width
    canvas.height = height
  }
  const bufferLength = analyserNode.value.fftSize
  const data = new Uint8Array(bufferLength)
  analyserNode.value.getByteTimeDomainData(data)
  ctx.fillStyle = '#f5f7fb'
  ctx.fillRect(0, 0, width, height)
  ctx.lineWidth = 2
  ctx.strokeStyle = '#409eff'
  ctx.beginPath()
  const sliceWidth = width / bufferLength
  let x = 0
  for (let i = 0; i < bufferLength; i += 1) {
    const v = data[i] / 128.0
    const y = (v * height) / 2
    if (i === 0) {
      ctx.moveTo(x, y)
    } else {
      ctx.lineTo(x, y)
    }
    x += sliceWidth
  }
  ctx.lineTo(width, height / 2)
  ctx.stroke()
  drawId.value = requestAnimationFrame(drawWaveform)
}

function setupVisualizer(ctx, source) {
  const analyser = ctx.createAnalyser()
  analyser.fftSize = 2048
  source.connect(analyser)
  analyserNode.value = analyser
  waveformSource.value = source
  visualizerContext.value = ctx
  drawWaveform()
}

function stopVisualizer() {
  if (drawId.value) {
    cancelAnimationFrame(drawId.value)
    drawId.value = null
  }
  if (waveformSource.value) {
    waveformSource.value.disconnect()
    waveformSource.value = null
  }
  analyserNode.value = null
  const canvas = waveformRef.value
  if (canvas) {
    const ctx = canvas.getContext('2d')
    if (ctx) {
      ctx.clearRect(0, 0, canvas.width, canvas.height)
    }
  }
}

async function startWavRecord() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
  const ctx = new AudioContext()
  const source = ctx.createMediaStreamSource(stream)
  const processor = ctx.createScriptProcessor(4096, 1, 1)
  audioChunks.value = []
  audioSampleRate.value = ctx.sampleRate
  processor.onaudioprocess = (e) => {
    const channel = e.inputBuffer.getChannelData(0)
    audioChunks.value.push(new Float32Array(channel))
  }
  source.connect(processor)
  processor.connect(ctx.destination)
  mediaStream.value = stream
  audioContext.value = ctx
  audioProcessor.value = processor
  setupVisualizer(ctx, source)
}

function stopWavRecord() {
  if (!audioContext.value || !audioProcessor.value) return
  audioProcessor.value.disconnect()
  audioContext.value.close()
  if (mediaStream.value) {
    mediaStream.value.getTracks().forEach((t) => t.stop())
  }
  const length = audioChunks.value.reduce((sum, cur) => sum + cur.length, 0)
  const samples = mergeBuffers(audioChunks.value, length)
  const wavBuffer = encodeWav(samples, audioSampleRate.value)
  const blob = new Blob([wavBuffer], { type: 'audio/wav' })
  const file = new File([blob], `record-${Date.now()}.wav`, { type: 'audio/wav' })
  addFile(file)
  audioChunks.value = []
  stopVisualizer()
}

async function startRecord() {
  if (isRecording.value) return
  try {
    if (typeof AudioContext !== 'undefined') {
      await startWavRecord()
      isRecording.value = true
      return
    }
    if (mimeType.value && typeof MediaRecorder !== 'undefined') {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const ctx = new AudioContext()
      const source = ctx.createMediaStreamSource(stream)
      setupVisualizer(ctx, source)
      const recorder = new MediaRecorder(stream, { mimeType: mimeType.value })
      const chunks = []
      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunks.push(e.data)
      }
      recorder.onstop = () => {
        const blob = new Blob(chunks, { type: mimeType.value })
        const file = new File([blob], `record-${Date.now()}.webm`, { type: mimeType.value })
        addFile(file)
        stream.getTracks().forEach((t) => t.stop())
        if (visualizerContext.value && visualizerContext.value.state !== 'closed') {
          visualizerContext.value.close()
        }
        visualizerContext.value = null
        stopVisualizer()
        isRecording.value = false
      }
      recorder.start()
      mediaRecorder.value = recorder
      isRecording.value = true
      return
    }
    ElMessage.error('当前浏览器不支持录音，请使用文件上传')
  } catch (e) {
    ElMessage.error('无法访问麦克风')
  }
}

function stopRecord() {
  if (!isRecording.value) return
  stopVisualizer()
  if (mediaRecorder.value) {
    mediaRecorder.value.stop()
    return
  }
  stopWavRecord()
  isRecording.value = false
}

async function submitEnroll() {
  if (items.value.length === 0) {
    ElMessage.error('请先添加音频')
    return
  }
  const formData = new FormData()
  if (form.user_id) {
    formData.append('user_id', form.user_id)
  }
  items.value.forEach((item) => {
    formData.append('files', item.file, item.file.name)
  })
  loading.value = true
  try {
    const res = await enrollVoice(formData)
    ElMessage.success(`注册成功，上传 ${res.wav_count} 条音频`)
  } catch (e) {
    ElMessage.error(e.message || '注册失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  mimeType.value = typeof MediaRecorder !== 'undefined' ? resolveMimeType() : ''
})

onBeforeUnmount(() => {
  items.value.forEach((item) => URL.revokeObjectURL(item.url))
  stopVisualizer()
  if (visualizerContext.value && visualizerContext.value.state !== 'closed') {
    visualizerContext.value.close()
  }
})
</script>

<template>
  <div class="card-panel">
    <div class="section-title">声纹注册</div>
    <el-form :model="form" label-width="90px">
      <el-form-item label="用户ID">
        <el-input v-model="form.user_id" placeholder="留空则使用当前登录用户" />
      </el-form-item>
    </el-form>

    <div class="form-row mt-12">
      <el-button type="primary" @click="startRecord" :disabled="isRecording">开始录音</el-button>
      <el-button type="danger" @click="stopRecord" :disabled="!isRecording">停止录音</el-button>
      <input ref="fileInputRef" type="file" accept=".wav,.mp3,.flac,.ogg,.m4a,audio/*" multiple style="display: none" @change="handleFileChange" />
      <el-button @click="openFileDialog">选择文件</el-button>
      <el-button type="success" :loading="loading" @click="submitEnroll">上传注册</el-button>
    </div>

    <div class="mt-16">
      <div class="section-title">录音波形</div>
      <canvas ref="waveformRef" style="width: 100%; height: 120px; background: #f5f7fb; border-radius: 8px;"></canvas>
    </div>

    <div class="mt-16">
      <div class="section-title">已添加音频（建议 3 条）</div>
      <div class="record-list" v-if="items.length">
        <div class="record-item" v-for="(item, index) in items" :key="item.url">
          <div>音频 {{ index + 1 }}</div>
          <audio :src="item.url" controls style="width: 100%; margin-top: 8px;"></audio>
          <el-button size="small" class="mt-12" @click="removeItem(index)">移除</el-button>
        </div>
      </div>
      <el-empty v-else description="暂无音频"></el-empty>
    </div>
  </div>
</template>
