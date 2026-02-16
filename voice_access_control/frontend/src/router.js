import { createRouter, createWebHistory } from "vue-router";
import { fetchCurrentUser, setAuthToken } from "./api";
import AdminDashboard from "./views/AdminDashboard.vue";
import VoiceVerify from "./views/VoiceVerify.vue";
import AdminLogin from "./views/AdminLogin.vue";
import UserProfile from "./views/UserProfile.vue";

const routes = [
  { path: "/", component: VoiceVerify },
  { path: "/login", component: AdminLogin },
  { path: "/admin", component: AdminDashboard, meta: { requiresAuth: true, adminOnly: true } },
  { path: "/me", component: UserProfile, meta: { requiresAuth: true } }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

let currentUserCache = null;
let currentTokenCache = null;

async function resolveCurrentUser(token) {
  if (!token) return null;
  if (currentUserCache && currentTokenCache === token) return currentUserCache;
  currentUserCache = null;
  currentTokenCache = token;
  setAuthToken(token);
  try {
    const res = await fetchCurrentUser();
    currentUserCache = res.data;
    return currentUserCache;
  } catch (e) {
    currentUserCache = null;
    return null;
  }
}

router.beforeEach(async (to, from, next) => {
  const token = localStorage.getItem("token");
  if (token) {
    setAuthToken(token);
  }
  if (to.meta?.requiresAuth && !token) {
    next("/");
    return;
  }
  if (to.path === "/login" && token) {
    const user = await resolveCurrentUser(token);
    if (user?.is_staff) {
      next("/admin");
    } else if (user) {
      next("/me");
    } else {
      localStorage.removeItem("token");
      setAuthToken(null);
      next();
    }
    return;
  }
  if (to.meta?.adminOnly) {
    const user = await resolveCurrentUser(token);
    if (!user) {
      localStorage.removeItem("token");
      setAuthToken(null);
      next("/");
      return;
    }
    if (!user.is_staff) {
      next("/me");
      return;
    }
  }
  next();
});

export default router;
