<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApiStore, type Frame } from '@/stores/api'
import { useI18n } from 'vue-i18n'
import Pagination from '@/components/Pagination.vue'
import FramePreviewModal from '@/components/FramePreviewModal.vue'
import { usePlatesolveStore } from '@/stores/platesolve'
import { useAnalyseStore } from '@/stores/analyse'
import { useIdentifyStore } from '@/stores/identify'

const { t } = useI18n()
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
const thumbnails = ref<any[]>([])
const sortBy = ref('date_obs')
const sortOrder = ref('desc')

// Preview modal state
const previewFrameId = ref<number | null>(null)

const sessionId = computed(() => parseInt(route.params.id as string))

const statusUpdating = ref(false)

async function updateStatus(newStatus: string) {
  statusUpdating.value = true
  try {
    await apiStore.patch(`/sessions/${sessionId.value}`, { status: newStatus })
    if (session.value) session.value.status = newStatus
  } catch (e: any) {
      console.error('API error:', e.response?.data?.detail || e.message)
      alert(t('error.generic'))
  } finally {
    statusUpdating.value = false
  }
}

function toggleSort(col: string) {
  if (sortBy.value === col) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortBy.value = col
    sortOrder.value = 'asc'
  }
  page.value = 1
}

function sortIcon(col: string): string {
  if (sortBy.value !== col) return '↕'
  return sortOrder.value === 'asc' ? '↑' : '↓'
}

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
      sort_by: sortBy.value,
      sort_order: sortOrder.value,
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

async function loadThumbnails() {
  try {
    const res = await apiStore.fetch<any>(`/frames`, {
      session_id: sessionId.value,
      frame_type: 'LIGHT',
      page: 1,
      page_size: 6,
      sort_by: 'date_obs',
      sort_order: 'desc',
    })
    const items = res.items || res
    thumbnails.value = items.map((f: any) => ({
      id: f.id, filename: f.filename, filter_name: f.filter_name, exposure: f.exposure, thumbnail: null
    }))
  } catch {
    thumbnails.value = []
  }
}

function openPreview(f: any) {
  previewFrameId.value = f.id
}

function closePreview() {
  previewFrameId.value = null
}

const taskBusy = ref(false)
const taskStarted = ref<string | null>(null)

const platesolveStore = usePlatesolveStore()
const analyseStore = useAnalyseStore()
const identifyStore = useIdentifyStore()

async function runTask(task: string) {
  taskBusy.value = true
  taskStarted.value = null
  try {
    await apiStore.post(`/${task}`, {}, { session_id: sessionId.value })
    const store = { platesolve: platesolveStore, analyse: analyseStore, identify: identifyStore }[task]
    if (store) store.startPolling()
    taskStarted.value = task
    setTimeout(() => { taskStarted.value = null }, 3000)
  } catch (e: any) {
      console.error('API error:', e.response?.data?.detail || e.message)
      alert(t('error.generic'))
  } finally {
    taskBusy.value = false
  }
}

watch([page, frameTypeFilter, sortBy, sortOrder], loadFrames)

onMounted(() => {
  loadSession()
  loadFrames()
  loadThumbnails()
})

function frameTypeBadge(type_: string | null) {
  return `badge badge-${(type_ ?? 'unknown').toLowerCase()}`
}

const frameTypes = computed(() => {
  if (!stats.value?.frame_type_counts) return []
  return Object.keys(stats.value.frame_type_counts)
})


</script>

<template>
  <div>
    <div class="breadcrumb">
      <a @click="router.push('/sessions')">{{ $t('sessions.title') }}</a>
      <span> / </span>
      <span class="active">{{ session?.target_name || '...' }}</span>
    </div>

    <div class="page-header">
      <h2>{{ session?.target_name || $t('session_detail.loading') }}</h2>
      <p v-if="session">
        {{ session.camera_name || '-' }}
        <span v-if="session.date_obs"> &middot; {{ new Date(session.date_obs).toLocaleDateString('de-CH') }}</span>
        &middot; {{ session.total_exposure_h }}h &middot; {{ session.frame_count }} {{ $t('sessions.col_frames') }}
        <select class="status-select" :value="session.status" @change="updateStatus(($event.target as HTMLSelectElement).value)" :disabled="statusUpdating">
          <option value="raw">{{ $t('session_detail.status_raw') }}</option>
          <option value="calibrated">{{ $t('session_detail.status_calibrated') }}</option>
          <option value="stacked">{{ $t('session_detail.status_stacked') }}</option>
        </select>
      </p>
      <div class="task-toolbar" v-if="session">
        <button v-if="taskStarted !== 'platesolve'" class="btn btn-sm btn-outline" :disabled="taskBusy" @click="runTask('platesolve')">🔍 Platesolve</button>
        <span v-else class="task-started">✅ Platesolve gestartet</span>

        <button v-if="taskStarted !== 'analyse'" class="btn btn-sm btn-outline" :disabled="taskBusy" @click="runTask('analyse')">📊 Analyse</button>
        <span v-else class="task-started">✅ Analyse gestartet</span>

        <button v-if="taskStarted !== 'identify'" class="btn btn-sm btn-outline" :disabled="taskBusy" @click="runTask('identify')">🎯 Identify</button>
        <span v-else class="task-started">✅ Identify gestartet</span>
      </div>
    </div>

    <!-- Aggregate cards -->
    <div class="stats-grid" v-if="stats">
      <div class="stat-card" v-for="(count, type) in stats.frame_type_counts" :key="type">
        <div class="value">{{ count }}</div>
        <div class="label">{{ type }}</div>
      </div>
      <div class="stat-card" v-for="item in stats.exposure_per_filter" :key="item.filter">
        <div class="value">{{ (item.total_s / 3600).toFixed(2) }}h</div>
        <div class="label">{{ item.filter }} ({{ item.frames }} {{ $t('sessions.col_frames') }})</div>
      </div>
    </div>

    <div class="card" v-if="thumbnails.length">
      <h3>{{ $t('session_detail.recent_images') }}</h3>
      <div class="thumbnail-grid">
        <div v-for="t in thumbnails" :key="t.id" class="thumbnail-item" @click="openPreview(t)">
          <img v-if="t.thumbnail" :src="t.thumbnail" :alt="t.filename" class="thumb-img" />
          <div v-else class="thumb-placeholder">
            <span>{{ t.filter_name || '?' }}</span>
          </div>
          <div class="thumb-meta">{{ t.filter_name || '-' }} · {{ t.exposure ? t.exposure + 's' : '-' }}</div>
        </div>
      </div>
    </div>

    <div class="card">
      <h3>{{ $t('session_detail.frames_title', { count: totalItems }) }}</h3>

      <!-- Frame type filter -->
      <div class="filters" v-if="frameTypes.length">
        <div class="filter-group">
          <label>{{ $t('session_detail.filter_type') }}</label>
          <div class="btn-group">
            <button
              :class="['btn', 'btn-sm', { active: frameTypeFilter === '' }]"
              @click="frameTypeFilter = ''; page = 1"
            >
              {{ $t('session_detail.filter_all') }}
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

      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th class="sortable" @click="toggleSort('date_obs')">{{ $t('session_detail.col_date') }} {{ sortIcon('date_obs') }}</th>
              <th class="sortable" @click="toggleSort('frame_type')">{{ $t('session_detail.col_type') }} {{ sortIcon('frame_type') }}</th>
              <th class="sortable" @click="toggleSort('filter_name')">{{ $t('session_detail.col_filter') }} {{ sortIcon('filter_name') }}</th>
              <th class="sortable" @click="toggleSort('exposure')">{{ $t('session_detail.col_exposure') }} {{ sortIcon('exposure') }}</th>
              <th class="sortable" @click="toggleSort('gain')">{{ $t('session_detail.col_gain') }} {{ sortIcon('gain') }}</th>
              <th class="sortable" @click="toggleSort('ccd_temp')">{{ $t('session_detail.col_temp') }} {{ sortIcon('ccd_temp') }}</th>
              <th class="sortable" @click="toggleSort('binning')">{{ $t('session_detail.col_binning') }} {{ sortIcon('binning') }}</th>
              <th class="sortable" @click="toggleSort('hfd_median')">{{ $t('session_detail.col_hfd') }} {{ sortIcon('hfd_median') }}</th>
              <th class="sortable" @click="toggleSort('stars_detected')">{{ $t('session_detail.col_stars') }} {{ sortIcon('stars_detected') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="f in frames" :key="f.id" class="clickable" @click="openPreview(f)">
              <td class="cell-filename" :title="f.filepath">{{ f.filename }}</td>
              <td><span :class="frameTypeBadge(f.frame_type)">{{ f.frame_type }}</span></td>
              <td>{{ f.filter_name || '-' }}</td>
              <td>{{ f.exposure ? f.exposure + 's' : '-' }}</td>
              <td>{{ f.gain ?? '-' }}</td>
              <td>{{ f.ccd_temp != null ? f.ccd_temp.toFixed(1) + '°C' : '-' }}</td>
              <td>{{ f.binning }}x{{ f.binning }}</td>
              <td>{{ f.hfd_median != null ? f.hfd_median.toFixed(1) : '-' }}</td>
              <td>{{ f.stars_detected ?? '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <Pagination :total="totalItems" :page="page" :pages="totalPages" @update:page="page = $event" />

    <FramePreviewModal :frameId="previewFrameId" @close="closePreview" />
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
.sortable { cursor: pointer; user-select: none; }
.sortable:hover { color: var(--accent); }
.cell-filename {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: monospace;
  font-size: 12px;
}
.thumbnail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 12px;
}
.thumbnail-item {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
  cursor: pointer;
  transition: border-color 0.15s;
}
.thumbnail-item:hover { border-color: var(--accent); }
.thumb-img {
  width: 100%;
  height: 120px;
  object-fit: cover;
  display: block;
}
.thumb-placeholder {
  width: 100%;
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface2);
  color: var(--text-faint);
  font-size: 24px;
  font-weight: 700;
}
.thumb-meta {
  padding: 6px 8px;
  font-size: 11px;
  color: var(--text-muted);
}

.task-started {
  font-size: 12px;
  font-weight: 600;
  color: var(--accent2);
  padding: 4px 8px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.task-toolbar {
  display: flex;
  gap: 6px;
  margin-top: 8px;
  flex-wrap: wrap;
}
.status-select {
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  margin-left: 6px;
  cursor: pointer;
}
.status-select:focus {
  outline: none;
  border-color: var(--accent);
}
</style>
