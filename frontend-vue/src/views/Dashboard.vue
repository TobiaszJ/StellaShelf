<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useApiStore, type DashboardData } from '@/stores/api'
import StatCard from '@/components/StatCard.vue'

const apiStore = useApiStore()
const router = useRouter()
const dashboard = ref<DashboardData | null>(null)
const topTargets = ref<any[]>([])
const recentSessions = ref<any[]>([])

async function load() {
  dashboard.value = await apiStore.fetch<DashboardData>('/dashboard')
  topTargets.value = dashboard.value?.top_targets || []
  recentSessions.value = dashboard.value?.recent_sessions || []
}

onMounted(load)
</script>

<template>
  <div>
    <div class="page-header">
      <h2>Dashboard</h2>
      <p>Uebersicht deiner Astrofoto-Sammlung</p>
    </div>

    <div class="stats-grid">
      <StatCard v-if="dashboard" :value="dashboard.total_targets" label="Targets" />
      <StatCard v-if="dashboard" :value="dashboard.total_sessions" label="Sessions" />
      <StatCard v-if="dashboard" :value="dashboard.total_frames?.toLocaleString()" label="Frames" />
      <StatCard v-if="dashboard" :value="dashboard.total_exposure_h + 'h'" label="Belichtung" />
    </div>

    <div class="card">
      <h3>Top Targets (nach Belichtungszeit)</h3>
      <div class="target-grid">
        <div
          v-for="t in topTargets"
          :key="t.id"
          class="target-card"
          @click="router.push({ name: 'target-detail', params: { id: t.id } })"
        >
          <div class="name">{{ t.name }}</div>
          <div class="meta">{{ t.total_exposure_h }}h &middot; {{ t.session_count }} Sessions</div>
        </div>
      </div>
    </div>

    <div class="card">
      <h3>Letzte Sessions</h3>
      <table class="data-table">
        <thead>
          <tr>
            <th>Ziel</th>
            <th>Datum</th>
            <th>Belichtung</th>
            <th>Frames</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="s in recentSessions"
            :key="s.id"
            class="clickable"
            @click="router.push({ name: 'session-detail', params: { id: s.id } })"
          >
            <td>{{ s.target_id }}</td>
            <td>{{ s.date_obs ? new Date(s.date_obs).toLocaleDateString('de-CH') : '-' }}</td>
            <td>{{ s.total_exposure_h }}h</td>
            <td>{{ s.frame_count }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
