import { createRouter, createWebHistory } from "vue-router";
import AdminDashboard from "./views/AdminDashboard.vue";
import VoiceVerify from "./views/VoiceVerify.vue";
import AdminLogin from "./views/AdminLogin.vue";
import UserProfile from "./views/UserProfile.vue";

const routes = [
  { path: "/", component: VoiceVerify },
  { path: "/login", component: AdminLogin },
  { path: "/admin", component: AdminDashboard },
  { path: "/me", component: UserProfile }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

export default router;
