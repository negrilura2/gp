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
  padding: 24px;
  background-color: var(--bg-primary);
  background-image: radial-gradient(1000px circle at 10% -20%, rgba(56, 189, 248, 0.2), transparent 50%),
    radial-gradient(900px circle at 90% 0%, rgba(167, 139, 250, 0.2), transparent 55%),
    linear-gradient(180deg, rgba(5, 6, 10, 0.6), rgba(5, 6, 10, 0.98));
}

.login-card {
  width: 360px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  box-shadow: 0 24px 50px rgba(5, 10, 24, 0.5);
  backdrop-filter: blur(16px);
  background: linear-gradient(160deg, rgba(14, 22, 38, 0.95), rgba(7, 10, 20, 0.9));
}

.login-title {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 16px;
  text-align: center;
  letter-spacing: 0.4px;
}
</style>
