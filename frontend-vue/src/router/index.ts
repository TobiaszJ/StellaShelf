import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '@/views/Dashboard.vue'
import Targets from '@/views/Targets.vue'
import Sessions from '@/views/Sessions.vue'
import Equipment from '@/views/Equipment.vue'
import Scan from '@/views/Scan.vue'
import TargetDetail from '@/views/TargetDetail.vue'
import SessionDetail from '@/views/SessionDetail.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'dashboard', component: Dashboard },
    { path: '/targets', name: 'targets', component: Targets },
    { path: '/targets/:id', name: 'target-detail', component: TargetDetail, props: true },
    { path: '/sessions', name: 'sessions', component: Sessions },
    { path: '/sessions/:id', name: 'session-detail', component: SessionDetail, props: true },
    { path: '/equipment', name: 'equipment', component: Equipment },
    { path: '/scan', name: 'scan', component: Scan },
  ],
})

export default router
