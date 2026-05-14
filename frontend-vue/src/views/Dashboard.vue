<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useApiStore, type DashboardData } from '@/stores/api'
import StatCard from '@/components/StatCard.vue'
import VChart from 'vue-echarts'
import 'echarts'

const apiStore = useApiStore()
const router = useRouter()
const dashboard = ref<DashboardData | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    dashboard.value = await apiStore.fetch<DashboardData>('/dashboard')
  } catch (e: any) {
    error.value = e.message || 'Fehler beim Laden des Dashboards'
  } finally {
    loading.value = false
  }
}

onMounted(load)

const topTargets = computed(() => dashboard.value?.top_targets || [])
const recentSessions = computed(() => dashboard.value?.recent_sessions || [])
const cameras = computed(() => dashboard.value?.cameras || [])

const chartOption = computed(() => ({
  tooltip: { trigger: 'axis' as const },
  grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
  xAxis: {
    type: 'category' as const,
    data: topTargets.value.slice(0, 5).map((t: any) => t.name),
    axisLabel: { color: '#8b949e', fontSize: 11 },
  },
  yAxis: {
    type: 'value' as const,
    name: 'Stunden',
    nameTextStyle: { color: '#8b949e', fontSize: 11 },
    axisLabel: { color: '#8b949e', fontSize: 11 },
    splitLine: { lineStyle: { color: '#21262d' } },
  },
  series: [{
    type: 'bar' as const,
    data: topTargets.value.slice(0, 5).map((t: any) => t.total_exposure_h),
    itemStyle: { color: '#58a6ff', borderRadius: [4, 4, 0, 0] },
    barMaxWidth: 40,
  }],
}))
</script>

<template>
  <div>
    <div class="page-header">
      <h2>Dashboard</h2>
      <p>Übersicht deiner Astrofoto-Sammlung</p>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="loading">Lade Dashboard...</div>

    <!-- Error state -->
    <div v-else-if="error" class="empty" style="color: var(--danger)">
      {{ error }}
    </div>

    <template v-else-if="dashboard">
      <div class="stats-grid">
        <StatCard :value="dashboard.total_targets" label="Targets" />
        <StatCard :value="dashboard.total_sessions" label="Sessions" />
        <StatCard :value="dashboard.total_frames?.toLocaleString()" label="Frames" />
        <StatCard :value="dashboard.total_exposure_h + 'h'" label="Belichtung" />
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
            <div class="meta">{{ t.total_exposure_h }}h · {{ t.session_count }} Sessions</div>
          </div>
        </div>
      </div>

      <div class="card">
        <h3>Kameras</h3>
        <table class="data-table">
          <thead><tr><th>Name</th><th>Frames</th><th>Belichtung</th></tr></thead>
          <tbody>
            <tr v-for="c in cameras" :key="c.id">
              <td><strong>{{ c.short_name || c.name }}</strong></td>
              <td>{{ c.frame_count }}</td>
              <td>{{ c.total_exposure_h }}h</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card" v-if="topTargets.length">
        <h3>Belichtung pro Target (Top 5)</h3>
        <div class="chart-container">
          <VChart :option="chartOption" autoresize />
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
              <td>{{ s.target_name }}</td>
              <td>{{ s.date_obs ? new Date(s.date_obs).toLocaleDateString('de-CH') : '-' }}</td>
              <td>{{ s.total_exposure_h }}h</td>
              <td>{{ s.frame_count }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>
