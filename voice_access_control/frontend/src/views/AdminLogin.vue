<template>
  <div class="login-wrapper">
    <el-card class="login-card">
      <div class="login-title">声纹门禁系统登录</div>
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
          <el-button
            type="primary"
            :loading="loggingIn"
            @click="handleLogin"
          >
            登录
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { login as apiLogin, setAuthToken } from "../api";

const router = useRouter();
const loginUsername = ref("");
const loginPassword = ref("");
const loggingIn = ref(false);

async function handleLogin() {
  if (!loginUsername.value || !loginPassword.value) {
    ElMessage.error("请输入用户名和密码");
    return;
  }
  loggingIn.value = true;
  try {
    const res = await apiLogin(loginUsername.value, loginPassword.value);
    const token = res.data.token;
    const isStaff = res.data.is_staff;
    localStorage.setItem("token", token);
    setAuthToken(token);
    ElMessage.success("登录成功");
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
    loggingIn.value = false;
  }
}

onMounted(() => {
  const token = localStorage.getItem("token");
  if (token) {
    setAuthToken(token);
  }
});
</script>

<style scoped>
.login-wrapper {
  height: 100vh;
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

.login-card {
  width: 360px;
  border: 1px solid rgba(64, 158, 255, 0.15);
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(6px);
}

.login-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 16px;
  text-align: center;
}
</style>
