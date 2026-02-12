import { getAuth } from './auth'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000/api'

async function request(path, options = {}) {
  const auth = getAuth()
  const headers = options.headers ? { ...options.headers } : {}
  if (auth?.token) {
    headers.Authorization = `Token ${auth.token}`
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })
  const contentType = res.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    const data = await res.json()
    if (!res.ok) {
      throw new Error(data.error || '请求失败')
    }
    return data
  }
  if (!res.ok) {
    throw new Error('请求失败')
  }
  return res
}

export function login(payload) {
  return request('/login/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
}

export function register(payload) {
  return request('/register/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
}

export function getMe() {
  return request('/me/', { method: 'GET' })
}

export function enrollVoice(formData) {
  return request('/enroll/', { method: 'POST', body: formData })
}

export function verifyVoice(formData) {
  return request('/verify/', { method: 'POST', body: formData })
}

export function fetchMyLogs() {
  return request('/my-logs/', { method: 'GET' })
}

export function fetchLogs(params = {}) {
  const query = new URLSearchParams(params).toString()
  return request(`/logs/${query ? `?${query}` : ''}`, { method: 'GET' })
}

export function fetchEnrollLogs() {
  return request('/enroll-logs/', { method: 'GET' })
}

export function fetchUsers() {
  return request('/users/', { method: 'GET' })
}

export function deleteUser(id) {
  return request(`/users/${id}/`, { method: 'DELETE' })
}

export function fetchVoiceTemplates() {
  return request('/voice-templates/', { method: 'GET' })
}

export function deleteVoiceTemplate(id) {
  return request(`/voice-templates/${id}/`, { method: 'DELETE' })
}

export function fetchStats() {
  return request('/stats/', { method: 'GET' })
}

export async function fetchRocImage() {
  const res = await request('/roc/', { method: 'GET' })
  const blob = await res.blob()
  return URL.createObjectURL(blob)
}
