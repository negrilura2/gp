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
