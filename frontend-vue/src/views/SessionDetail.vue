<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApiStore, type Frame } from '@/stores/api'
import Pagination from '@/components/Pagination.vue'

const route = useRoute()
const router = useRouter()
const apiStore = useApiStore()
const session = ref<any>(null)
const frames = ref<Frame[]>([])
const stats = ref<any>(null)
const page = ref(1)
const totalPages = ref(1)
const totalItems = ref(0)
const frameTypeFilter = ref('')

const sessionId = computed(() => parseInt(route.params.id as string))

async function loadSession() {
  try {
    session.value = await apiStore.fetch(`/sessions/${sessionId.value}`)
    stats.value = await apiStore.fetch(`/sessions/${sessionId.value}/stats`)
  } catch {
    // error
  }
}

async function loadFrames() {
  try {
    const params: Record<string, any> = {
      session_id: sessionId.value,
      page: page.value,
      page_size: 50,
    }
    if (frameTypeFilter.value) {
      params.frame_type = frameTypeFilter.value
    }
    const res = await apiStore.fetch<any>(`/frames`, params)
    frames.value = res.items || res
    totalItems.value = res.total ?? frames.value.length
    totalPages.value = res.pages ?? 1
  } catch {
    // error
  }
}

watch([page, frameTypeFilter], loadFrames)

onMounted(() => {
  loadSession()
  loadFrames()
})

function frameTypeBadge(type_: string) {
  return `badge badge-${type_.toLowerCase()}`
}

const frameTypes = computed(() => {
  if (!stats.value?.frame_type_counts) return []
  return Object.keys(stats.value.frame_type_counts)
})
</script>

<template>
  <div>
    <div class="breadcrumb">
      <a @click="router.push('/sessions')">Sessions</a>
      <span> / </span>
      <span class="active">{{ session?.target_name || '...' }}</span>
    </div>

    <div class="page-header">
      <h2>{{ session?.target_name || 'Loading...' }}</h2>
      <p v-if="session">
        {{ session.camera_name || '-' }}
        <span v-if="session.date_obs"> &middot; {{ new Date(session.date_obs).toLocaleDateString('de-CH') }}</span>
        &middot; {{ session.total_exposure_h }}h &middot; {{ session.frame_count }} Frames
        <span :class="['badge', `badge-${session.status}`]">{{ session.status }}</span>
      </p>
    </div>

    <!-- Aggregate cards -->
    <div class="stats-grid" v-if="stats">
      <div class="stat-card" v-for="(count, type) in stats.frame_type_counts" :key="type">
        <div class="value">{{ count }}</div>
        <div class="label">{{ type }}</div>
      </div>
      <div class="stat-card" v-for="item in stats.exposure_per_filter" :key="item.filter">
        <div class="value">{{ (item.total_s / 3600).toFixed(2) }}h</div>
        <div class="label">{{ item.filter }} ({{ item.frames }} Frames)</div>
      </div>
    </div>

    <div class="card">
      <h3>Frames</h3>

      <!-- Frame type filter -->
      <div class="filters" v-if="frameTypes.length">
        <div class="filter-group">
          <label>Typ</label>
          <div class="btn-group">
            <button
              :class="['btn', 'btn-sm', { active: frameTypeFilter === '' }]"
              @click="frameTypeFilter = ''; page = 1"
            >
              Alle
            </button>
            <button
              v-for="ft in frameTypes"
              :key="ft"
              :class="['btn', 'btn-sm', { active: frameTypeFilter === ft }]"
              @click="frameTypeFilter = ft; page = 1"
            >
              {{ ft }}
            </button>
          </div>
        </div>
      </div>

      <table class="data-table">
        <thead>
          <tr>
            <th>Datei</th>
            <th>Typ</th>
            <th>Filter</th>
            <th>Belichtung</th>
            <th>Gain</th>
            <th>Temp</th>
            <th>Binning</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="f in frames" :key="f.id">
            <td class="cell-filename" :title="f.filepath">{{ f.filename }}</td>
            <td><span :class="frameTypeBadge(f.frame_type)">{{ f.frame_type }}</span></td>
            <td>{{ f.filter_name || '-' }}</td>
            <td>{{ f.exposure ? f.exposure + 's' : '-' }}</td>
            <td>{{ f.gain ?? '-' }}</td>
            <td>{{ f.ccd_temp != null ? f.ccd_temp.toFixed(1) + '°C' : '-' }}</td>
            <td>{{ f.binning }}x{{ f.binning }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <Pagination :total="totalItems" :page="page" :pages="totalPages" @update:page="page = $event" />
  </div>
</template>

<style scoped>
.breadcrumb {
  font-size: 13px;
  margin-bottom: 8px;
  color: var(--text-muted);
}
.breadcrumb a { cursor: pointer; color: var(--accent); }
.breadcrumb .active { color: var(--text); }
.btn-group {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.btn-group .btn.active {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}
.cell-filename {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: monospace;
  font-size: 12px;
}
</style>
