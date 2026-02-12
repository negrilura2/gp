const AUTH_KEY = 'voice_auth'

export function getAuth() {
  const raw = localStorage.getItem(AUTH_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export function setAuth(auth) {
  localStorage.setItem(AUTH_KEY, JSON.stringify(auth))
  window.dispatchEvent(new Event('auth-changed'))
}

export function clearAuth() {
  localStorage.removeItem(AUTH_KEY)
  window.dispatchEvent(new Event('auth-changed'))
}
