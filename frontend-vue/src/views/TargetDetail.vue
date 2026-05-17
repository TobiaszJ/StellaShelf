<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApiStore, type Session, type PaginatedResponse, type Target } from '@/stores/api'
import { useI18n } from 'vue-i18n'
import Pagination from '@/components/Pagination.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const apiStore = useApiStore()
const target = ref<any>(null)
const sessions = ref<Session[]>([])
const thumbnails = ref<any[]>([])
const page = ref(1)
const totalPages = ref(1)
const totalItems = ref(0)
const sortBy = ref('date_obs')
const sortOrder = ref('desc')

const mergeDestination = ref<Target | null>(null)
const mergeConfirming = ref(false)
const mergeBusy = ref(false)
const showMergeDialog = ref(false)
const mergeSearch = ref('')
const mergeResults = ref<Target[]>([])
const mergeLoading = ref(false)

const targetId = computed(() => parseInt(route.params.id as string))

const taskBusy = ref(false)
const taskStarted = ref<string | null>(null)

async function runTask(task: string) {
  taskBusy.value = true
  taskStarted.value = null
  try {
    await apiStore.post(`/${task}`, {}, { target_id: targetId.value })
    taskStarted.value = task
    setTimeout(() => { taskStarted.value = null }, 3000)
  } catch (e: any) {
    alert(t('error.generic', { message: e.response?.data?.detail || e.message }))
  } finally {
    taskBusy.value = false
  }
}

async function loadTarget() {
  try {
    target.value = await apiStore.fetch(`/targets/${targetId.value}`)
  } catch {
    router.push('/targets')
  }
}

async function loadSessions() {
  const res = await apiStore.fetch<PaginatedResponse<Session>>(`/targets/${targetId.value}/sessions`, {
    page: page.value,
    page_size: 50,
    sort_by: sortBy.value,
    sort_order: sortOrder.value,
  })
  sessions.value = res.items
  totalPages.value = res.pages
  totalItems.value = res.total
}

function toggleSort(col: string) {
  if (sortBy.value === col) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortBy.value = col
    sortOrder.value = 'desc'
  }
  page.value = 1
  loadSessions()
}

function sortIcon(col: string): string {
  if (sortBy.value !== col) return '↕'
  return sortOrder.value === 'asc' ? '↑' : '↓'
}

function onPageChange(p: number) {
  page.value = p
}

async function loadThumbnails() {
  try {
    thumbnails.value = await apiStore.fetch(`/targets/${targetId.value}/thumbnails`, { limit: 6 })
  } catch {
    thumbnails.value = []
  }
}

function formatCoord(value: number | null, prefix: string): string {
  if (value === null || value === undefined) return '-'
  if (prefix === 'RA') {
    const hours = value / 15
    const h = Math.floor(hours)
    const m = Math.floor((hours - h) * 60)
    const s = ((hours - h) * 60 - m) * 60
    return `${h}h ${m}m ${s.toFixed(1)}s`
  }
  const deg = Math.floor(Math.abs(value))
  const m = Math.floor((Math.abs(value) - deg) * 60)
  const s = ((Math.abs(value) - deg) * 60 - m) * 60
  const sign = value >= 0 ? '+' : '−'
  return `${sign}${deg}° ${m}' ${s.toFixed(0)}"`
}

const typeBadgeClass = (type: string | null): string => {
  const map: Record<string, string> = {
    'Galaxy': 'badge-galaxy', 'Nebula': 'badge-nebula',
    'Star': 'badge-star', 'Cluster': 'badge-cluster',
    'Supernova Remnant': 'badge-snr', 'Planetary Nebula': 'badge-planetary',
  }
  return map[type || ''] || 'badge-default'
}

async function searchMergeTargets() {
  if (!mergeSearch.value.trim()) {
    mergeResults.value = []
    return
  }
  mergeLoading.value = true
  try {
    const res = await apiStore.fetch<PaginatedResponse<Target>>('/targets', {
      search: mergeSearch.value,
      page: 1,
      page_size: 10,
    })
    mergeResults.value = res.items.filter(t => t.id !== targetId.value)
  } catch {
    mergeResults.value = []
  } finally {
    mergeLoading.value = false
  }
}

function selectMergeDestination(t: Target) {
  mergeDestination.value = t
  mergeSearch.value = t.name
  mergeResults.value = []
}

function cancelMerge() {
  showMergeDialog.value = false
  mergeSearch.value = ''
  mergeResults.value = []
  mergeDestination.value = null
  mergeConfirming.value = false
}

async function doMerge() {
  if (!mergeDestination.value) return
  mergeBusy.value = true
  try {
    await apiStore.post('/targets/merge', {
      source_id: targetId.value,
      destination_id: mergeDestination.value.id,
    })
    router.push({ name: 'target-detail', params: { id: mergeDestination.value.id } })
  } catch (e: any) {
    alert(t('error.generic', { message: e.response?.data?.detail || e.message }))
  } finally {
    mergeBusy.value = false
  }
}

onMounted(() => {
  loadTarget()
  loadSessions()
  loadThumbnails()
})

watch(page, loadSessions)
watch(mergeSearch, searchMergeTargets)
</script>

<template>
  <div>
    <div class="breadcrumb">
      <a @click="router.push('/targets')">{{ $t('target_detail.title') }}</a>
      <span> / </span>
      <span class="active">{{ target?.name || '...' }}</span>
    </div>

    <div class="page-header">
      <div class="page-header-row">
        <div>
          <h2>{{ target?.name || $t('target_detail.loading') }}</h2>
          <p v-if="target">
            <span v-if="target.object_type" :class="['badge', typeBadgeClass(target.object_type)]">
              {{ target.object_type }}
            </span>
            <span v-if="target.constellation" style="margin-left: 8px">
              {{ $t('target_detail.constellation', { name: target.constellation }) }}
            </span>
            <span v-if="target.alt_names" style="margin-left: 8px; font-size: 12px; color: var(--text-muted);">
              {{ $t('target_detail.also_known_as', { names: target.alt_names }) }}
            </span>
          </p>
        </div>
        <button class="btn btn-sm btn-outline" @click="showMergeDialog = true" :disabled="!target">
          {{ $t('target_detail.merge_button') }}
        </button>
      </div>
      <div class="task-toolbar" v-if="target">
        <button v-if="taskStarted !== 'platesolve'" class="btn btn-sm btn-outline" :disabled="taskBusy" @click="runTask('platesolve')">🔍 Platesolve</button>
        <span v-else class="task-started">✅ Platesolve gestartet</span>

        <button v-if="taskStarted !== 'analyse'" class="btn btn-sm btn-outline" :disabled="taskBusy" @click="runTask('analyse')">📊 Analyse</button>
        <span v-else class="task-started">✅ Analyse gestartet</span>

        <button v-if="taskStarted !== 'identify'" class="btn btn-sm btn-outline" :disabled="taskBusy" @click="runTask('identify')">🎯 Identify</button>
        <span v-else class="task-started">✅ Identify gestartet</span>
      </div>
    </div>

    <!-- Merge Dialog -->
    <div v-if="showMergeDialog" class="modal-overlay" @click.self="cancelMerge">
      <div class="modal">
        <h3>{{ $t('target_detail.merge_title') }}</h3>
        <p style="margin-bottom: 12px; color: var(--text-muted); font-size: 13px;" v-html="$t('target_detail.merge_description', { name: target?.name })"></p>

        <div v-if="!mergeDestination">
          <label>{{ $t('target_detail.merge_search_label') }}</label>
          <input
            v-model="mergeSearch"
            type="text"
            :placeholder="$t('target_detail.merge_search_placeholder')"
            class="merge-search-input"
          />
          <div v-if="mergeLoading" class="loading" style="padding: 12px;">{{ $t('target_detail.merge_searching') }}</div>
          <div v-else-if="mergeResults.length" class="merge-results">
            <div
              v-for="t in mergeResults"
              :key="t.id"
              class="merge-result-item"
              @click="selectMergeDestination(t)"
            >
              <strong>{{ t.name }}</strong>
              <span style="color: var(--text-muted); font-size: 12px;">
                {{ t.session_count }} {{ $t('target_detail.sessions') }} · {{ t.total_exposure_h }}h
              </span>
            </div>
          </div>
          <p v-else-if="mergeSearch && !mergeLoading" class="empty" style="padding: 12px;">
            {{ $t('target_detail.merge_not_found') }}
          </p>
        </div>

        <div v-else>
          <div class="merge-confirm">
            <div class="merge-arrow">
              <span class="merge-from">{{ target?.name }}</span>
              <span class="merge-arrow-sym">→</span>
              <span class="merge-to">{{ mergeDestination.name }}</span>
            </div>
            <p style="margin-top: 12px;" v-html="$t('target_detail.merge_confirm_text', { source: target?.name, dest: mergeDestination.name })"></p>
            <div class="merge-actions">
              <button class="btn" @click="mergeConfirming = true; doMerge()" :disabled="mergeBusy">
                {{ mergeBusy ? $t('target_detail.merge_busy') : $t('target_detail.merge_confirm') }}
              </button>
              <button class="btn btn-ghost" @click="cancelMerge" :disabled="mergeBusy">
                {{ $t('target_detail.merge_cancel') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="stats-grid" v-if="target">
      <div class="stat-card">
        <div class="value">{{ target.session_count }}</div>
        <div class="label">{{ $t('target_detail.sessions') }}</div>
      </div>
      <div class="stat-card">
        <div class="value">{{ target.total_exposure_h }}h</div>
        <div class="label">{{ $t('target_detail.exposure') }}</div>
      </div>
      <div class="stat-card">
        <div class="value">{{ target.ra_deg != null ? formatCoord(target.ra_deg, 'RA') : '-' }}</div>
        <div class="label">{{ $t('target_detail.right_ascension') }}</div>
      </div>
      <div class="stat-card">
        <div class="value">{{ target.dec_deg != null ? formatCoord(target.dec_deg, 'DEC') : '-' }}</div>
        <div class="label">{{ $t('target_detail.declination') }}</div>
      </div>
    </div>

    <div class="card">
      <h3>{{ $t('target_detail.recent_images') }}</h3>
      <div class="thumbnail-grid" v-if="thumbnails.length">
        <div v-for="t in thumbnails" :key="t.id" class="thumbnail-item">
          <img v-if="t.thumbnail" :src="t.thumbnail" :alt="t.filename" class="thumb-img" />
          <div v-else class="thumb-placeholder">
            <span>{{ t.filter_name || '?' }}</span>
          </div>
          <div class="thumb-meta">{{ t.filter_name || '-' }} · {{ t.exposure ? t.exposure + 's' : '-' }}</div>
        </div>
      </div>
      <p v-else class="empty">{{ $t('target_detail.no_thumbnails') }}</p>
    </div>

    <div class="card">
      <h3>{{ $t('target_detail.sessions_list', { count: totalItems }) }}</h3>
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th class="sortable" @click="toggleSort('date_obs')">{{ $t('target_detail.col_date') }} {{ sortIcon('date_obs') }}</th>
              <th>{{ $t('target_detail.col_camera') }}</th>
              <th>{{ $t('target_detail.col_telescope') }}</th>
              <th class="sortable" @click="toggleSort('total_exposure_h')">{{ $t('target_detail.col_exposure') }} {{ sortIcon('total_exposure_h') }}</th>
              <th class="sortable" @click="toggleSort('frame_count')">{{ $t('target_detail.col_frames') }} {{ sortIcon('frame_count') }}</th>
              <th>{{ $t('target_detail.col_status') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="s in sessions"
              :key="s.id"
              class="clickable"
              @click="router.push({ name: 'session-detail', params: { id: s.id } })"
            >
              <td>{{ s.date_obs ? new Date(s.date_obs).toLocaleDateString('de-CH') : '-' }}</td>
              <td>{{ s.camera_name || '-' }}</td>
              <td>{{ s.telescope_name || '-' }}</td>
              <td>{{ s.total_exposure_h }}h</td>
              <td>{{ s.frame_count }}</td>
              <td><span class="badge badge-light">{{ s.status }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <Pagination :total="totalItems" :page="page" :pages="totalPages" @update:page="onPageChange" />
  </div>
</template>

<style scoped>
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
.page-header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}
.breadcrumb {
  font-size: 13px;
  margin-bottom: 8px;
  color: var(--text-muted);
}
.breadcrumb a {
  cursor: pointer;
  color: var(--accent);
}
.breadcrumb .active {
  color: var(--text);
}
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.modal {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 24px;
  max-width: 480px;
  width: 90%;
}
.merge-search-input {
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 14px;
  width: 100%;
  margin-top: 4px;
}
.merge-search-input:focus {
  outline: none;
  border-color: var(--accent);
}
.merge-results {
  margin-top: 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  max-height: 200px;
  overflow-y: auto;
}
.merge-result-item {
  padding: 10px 12px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.merge-result-item:hover {
  background: rgba(255, 255, 255, 0.03);
}
.merge-result-item + .merge-result-item {
  border-top: 1px solid var(--border);
}
.merge-confirm {
  margin-top: 12px;
}
.merge-arrow {
  display: flex;
  align-items: center;
  gap: 12px;
  justify-content: center;
  padding: 16px;
  background: var(--bg);
  border-radius: 8px;
}
.merge-arrow-sym {
  font-size: 20px;
  color: var(--accent);
}
.merge-from {
  font-weight: 600;
  color: var(--danger);
}
.merge-to {
  font-weight: 700;
  color: var(--accent2);
}
.merge-actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
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
}
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
</style>
