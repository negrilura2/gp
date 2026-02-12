import { createRouter, createWebHistory } from 'vue-router'
import { getAuth } from '../services/auth'
import LoginRegister from '../views/LoginRegister.vue'
import EnrollPage from '../views/EnrollPage.vue'
import VerifyPage from '../views/VerifyPage.vue'
import ProfilePage from '../views/ProfilePage.vue'
import AdminPage from '../views/AdminPage.vue'

const routes = [
  { path: '/', redirect: '/verify' },
  { path: '/login', component: LoginRegister },
  { path: '/enroll', component: EnrollPage, meta: { requiresAuth: true } },
  { path: '/verify', component: VerifyPage },
  { path: '/profile', component: ProfilePage, meta: { requiresAuth: true } },
  { path: '/admin', component: AdminPage, meta: { requiresAuth: true, requiresAdmin: true } }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const auth = getAuth()
  if (to.meta?.requiresAuth && !auth?.token) {
    return '/login'
  }
  if (to.meta?.requiresAdmin && !auth?.is_staff) {
    return '/verify'
  }
  return true
})

export default router
