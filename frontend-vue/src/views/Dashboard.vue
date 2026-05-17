<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useApiStore, type DashboardData } from '@/stores/api'
import { useI18n } from 'vue-i18n'
import StatCard from '@/components/StatCard.vue'
import VChart from 'vue-echarts'
import 'echarts'

const { t } = useI18n()
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
    error.value = e.message || t('error.generic', { message: 'Dashboard laden fehlgeschlagen' })
  } finally {
    loading.value = false
  }
}

onMounted(load)

const topTargets = computed(() => dashboard.value?.top_targets || [])
const recentSessions = computed(() => dashboard.value?.recent_sessions || [])
const cameras = computed(() => dashboard.value?.cameras || [])

const chartOption = computed(() => {
  const isDark = document.documentElement.getAttribute('data-theme') !== 'light'
  const textColor = isDark ? '#8b949e' : '#656d76'
  const splitColor = isDark ? '#21262d' : '#d0d7de'
  const barColor = isDark ? '#58a6ff' : '#0969da'
  return {
    tooltip: { trigger: 'axis' as const },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category' as const,
      data: topTargets.value.slice(0, 5).map((t: any) => t.name),
      axisLabel: { color: textColor, fontSize: 11 },
    },
    yAxis: {
      type: 'value' as const,
      name: t('dashboard.hours'),
      nameTextStyle: { color: textColor, fontSize: 11 },
      axisLabel: { color: textColor, fontSize: 11 },
      splitLine: { lineStyle: { color: splitColor } },
    },
    series: [{
      type: 'bar' as const,
      data: topTargets.value.slice(0, 5).map((t: any) => t.total_exposure_h),
      itemStyle: { color: barColor, borderRadius: [4, 4, 0, 0] },
      barMaxWidth: 40,
    }],
  }
})
</script>

<template>
  <div>
    <div class="page-header">
      <h2>{{ $t('dashboard.title') }}</h2>
      <p>{{ $t('dashboard.description') }}</p>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="loading">{{ $t('dashboard.loading') }}</div>

    <!-- Error state -->
    <div v-else-if="error" class="empty" style="color: var(--danger)">
      {{ error }}
    </div>

    <template v-else-if="dashboard">
      <div class="stats-grid">
        <StatCard :value="dashboard.total_targets" :label="$t('dashboard.targets')" />
        <StatCard :value="dashboard.total_sessions" :label="$t('dashboard.sessions')" />
        <StatCard :value="dashboard.total_frames?.toLocaleString()" :label="$t('dashboard.frames')" />
        <StatCard :value="dashboard.total_exposure_h + 'h'" :label="$t('dashboard.exposure')" />
      </div>

      <div class="card">
        <h3>{{ $t('dashboard.top_targets') }}</h3>
        <div class="target-grid">
          <div
            v-for="t in topTargets"
            :key="t.id"
            class="target-card"
            @click="router.push({ name: 'target-detail', params: { id: t.id } })"
          >
            <div class="name">{{ t.name }}</div>
            <div class="meta">{{ t.total_exposure_h }}h · {{ t.session_count }} {{ $t('dashboard.sessions') }}</div>
          </div>
        </div>
      </div>

      <div class="card">
        <h3>{{ $t('dashboard.cameras') }}</h3>
        <div class="table-responsive">
          <table class="data-table">
            <thead><tr><th>{{ $t('dashboard.col_name') }}</th><th>{{ $t('dashboard.col_frames') }}</th><th>{{ $t('dashboard.col_exposure') }}</th></tr></thead>
            <tbody>
              <tr v-for="c in cameras" :key="c.id">
                <td><strong>{{ c.short_name || c.name }}</strong></td>
                <td>{{ c.frame_count }}</td>
                <td>{{ c.total_exposure_h }}h</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="card" v-if="topTargets.length">
        <h3>{{ $t('dashboard.exposure_per_target') }}</h3>
        <div class="chart-container">
          <VChart :option="chartOption" autoresize />
        </div>
      </div>

      <div class="card">
        <h3>{{ $t('dashboard.recent_sessions') }}</h3>
        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>{{ $t('dashboard.col_target') }}</th>
                <th>{{ $t('dashboard.col_date') }}</th>
                <th>{{ $t('dashboard.col_exposure') }}</th>
                <th>{{ $t('dashboard.col_frames') }}</th>
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
      </div>
    </template>
  </div>
</template>
