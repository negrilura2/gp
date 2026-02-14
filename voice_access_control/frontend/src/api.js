import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  timeout: 15000
});

export function setAuthToken(token) {
  if (token) {
    api.defaults.headers.common.Authorization = `Token ${token}`;
  } else {
    delete api.defaults.headers.common.Authorization;
  }
}

export function login(username, password) {
  return api.post("/login/", { username, password });
}

export function fetchDashboard() {
  return api.get("/dashboard/");
}

export function fetchStatsEcharts() {
  return api.get("/stats/", {
    params: { mode: "echarts" }
  });
}

export function fetchLogs(params) {
  return api.get("/logs/", { params });
}

export function deleteLogs(ids) {
  return api.delete("/logs/bulk-delete/", {
    data: { ids }
  });
}

export function verifyVoice(formData) {
  return api.post("/verify/", formData, {
    headers: { "Content-Type": "multipart/form-data" }
  });
}

export function fetchCurrentUser() {
  return api.get("/me/");
}

export function enrollVoice(formData) {
  return api.post("/enroll/", formData, {
    headers: { "Content-Type": "multipart/form-data" }
  });
}

export function fetchMyLogs() {
  return api.get("/my-logs/");
}

export function fetchThreshold() {
  return api.get("/threshold/");
}

export function updateThreshold(threshold) {
  return api.post("/threshold/", { threshold });
}

export function fetchUsers(params) {
  return api.get("/users/", { params });
}

export function createUser(payload) {
  return api.post("/users/", payload);
}

export function updateUser(userId, payload) {
  return api.patch(`/users/${userId}/`, payload);
}

export function deleteUser(userId) {
  return api.delete(`/users/${userId}/`);
}

export function resetUserPassword(userId, password) {
  return api.post(`/users/${userId}/reset-password/`, { password });
}

export function resetUserVoiceprint(userId) {
  return api.delete(`/users/${userId}/voiceprint/`);
}

export function fetchAdminSecretStatus() {
  return api.get("/admin-secret/status/");
}

export function setAdminSecret(payload) {
  return api.post("/admin-secret/", payload);
}

export function fetchAdminList(secret_password) {
  return api.post("/admin-list/", { secret_password });
}

export function fetchAdminAccessLogs(params) {
  return api.get("/admin-access-logs/", { params });
}

export function fetchAdminUsers(params) {
  return api.get("/admins/", { params });
}

export function createAdminUser(payload) {
  return api.post("/admins/", payload);
}

export function updateAdminUser(userId, payload) {
  return api.patch(`/admins/${userId}/`, payload);
}

export function bulkUpdateAdminStatus(ids, is_active) {
  return api.post("/admins/bulk-status/", { ids, is_active });
}

export function bulkResetAdminPassword(ids, password) {
  return api.post("/admins/bulk-reset-password/", { ids, password });
}

export function fetchRocMetrics() {
  return api.get("/roc/");
}

export function evaluateRocMetrics(name) {
  return api.post("/roc/evaluate/", name ? { name } : {});
}

export function fetchModels() {
  return api.get("/models/");
}

export function switchModel(name) {
  return api.post("/models/switch/", { name });
}
