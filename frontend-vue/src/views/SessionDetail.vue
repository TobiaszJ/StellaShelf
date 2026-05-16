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
const thumbnails = ref<any[]>([])
const sortBy = ref('date_obs')
const sortOrder = ref('desc')

// Preview modal state
const previewFrame = ref<any>(null)
const previewThumb = ref<string | null>(null)
const previewLoading = ref(false)

const sessionId = computed(() => parseInt(route.params.id as string))

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
    thumbnails.value = await Promise.all(
      items.map(async (f: any) => {
        try {
          const blob = await apiStore.fetchBlob(`/frames/${f.id}/thumbnail`)
          const url = URL.createObjectURL(blob)
          return { id: f.id, filename: f.filename, filter_name: f.filter_name, exposure: f.exposure, thumbnail: url }
        } catch {
          return { id: f.id, filename: f.filename, filter_name: f.filter_name, exposure: f.exposure, thumbnail: null }
        }
      })
    )
  } catch {
    thumbnails.value = []
  }
}

async function openPreview(f: any) {
  previewLoading.value = true
  previewFrame.value = null
  previewThumb.value = null
  try {
    const detail = await apiStore.fetch(`/frames/${f.id}`)
    previewFrame.value = detail
    try {
      const blob = await apiStore.fetchBlob(`/frames/${f.id}/thumbnail?preview=true`)
      previewThumb.value = URL.createObjectURL(blob)
    } catch {
      previewThumb.value = null
    }
  } catch (e: any) {
    alert('Fehler: ' + (e.response?.data?.detail || e.message))
  } finally {
    previewLoading.value = false
  }
}

function closePreview() {
  if (previewThumb.value) URL.revokeObjectURL(previewThumb.value)
  previewFrame.value = null
  previewThumb.value = null
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

const metadataEntries = computed(() => {
  if (!previewFrame.value) return []
  const entries: { label: string; value: string }[] = []
  const fields: Record<string, string> = {
    filename: 'Dateiname', filepath: 'Pfad', file_size: 'Größe (Bytes)',
    frame_type: 'Typ', object_name: 'Objekt', instrume: 'Kamera', telescop: 'Teleskop',
    filter_name: 'Filter', exposure: 'Belichtung (s)', gain: 'Gain', ccd_temp: 'Temperatur (°C)',
    binning: 'Binning', date_obs: 'Datum (UTC)', date_local: 'Datum (Lokal)',
    width: 'Breite (px)', height: 'Höhe (px)', pixel_size_um: 'Pixelgröße (µm)',
    ra_deg: 'RA (°)', dec_deg: 'DEC (°)', focal_length_mm: 'Brennweite (mm)',
    site_name: 'Standort', observer: 'Beobachter', creator: 'Software',
    fwhm: 'FWHM', eccentricity: 'Exzentrizität', snr: 'SNR',
  }
  for (const [key, label] of Object.entries(fields)) {
    const val = (previewFrame.value as any)[key]
    if (val !== null && val !== undefined && val !== '') {
      let display = String(val)
      if (key === 'exposure') display = Number(val).toFixed(1) + 's'
      if (key === 'ccd_temp' && typeof val === 'number') display = val.toFixed(1) + '°C'
      if (key === 'ra_deg' && typeof val === 'number') display = val.toFixed(4) + '°'
      if (key === 'dec_deg' && typeof val === 'number') display = val.toFixed(4) + '°'
      if (key === 'date_obs' || key === 'date_local') display = new Date(val).toLocaleString('de-CH')
      if (key === 'binning') display = val + 'x' + val
      entries.push({ label, value: display })
    }
  }
  return entries
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

    <div class="card" v-if="thumbnails.length">
      <h3>Letzte Aufnahmen</h3>
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
      <h3>Frames ({{ totalItems }})</h3>

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
            <th class="sortable" @click="toggleSort('date_obs')">Datum {{ sortIcon('date_obs') }}</th>
            <th class="sortable" @click="toggleSort('frame_type')">Typ {{ sortIcon('frame_type') }}</th>
            <th class="sortable" @click="toggleSort('filter_name')">Filter {{ sortIcon('filter_name') }}</th>
            <th class="sortable" @click="toggleSort('exposure')">Belichtung {{ sortIcon('exposure') }}</th>
            <th class="sortable" @click="toggleSort('gain')">Gain {{ sortIcon('gain') }}</th>
            <th class="sortable" @click="toggleSort('ccd_temp')">Temp {{ sortIcon('ccd_temp') }}</th>
            <th class="sortable" @click="toggleSort('binning')">Binning {{ sortIcon('binning') }}</th>
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
          </tr>
        </tbody>
      </table>
    </div>

    <Pagination :total="totalItems" :page="page" :pages="totalPages" @update:page="page = $event" />

    <!-- Preview Modal -->
    <div v-if="previewFrame" class="modal-overlay" @click.self="closePreview">
      <div class="preview-modal">
        <div class="preview-header">
          <h3>{{ previewFrame.filename }}</h3>
          <button class="btn-close" @click="closePreview">&times;</button>
        </div>
        <div class="preview-body">
          <div class="preview-image">
            <div v-if="previewLoading" class="loading">Lade Vorschaubild...</div>
            <img v-else-if="previewThumb" :src="previewThumb" :alt="previewFrame.filename" class="preview-img" />
            <div v-else class="preview-noimg">Kein Vorschaubild verfügbar</div>
          </div>
          <div class="preview-metadata">
            <table class="metadata-table">
              <tbody>
                <tr v-for="entry in metadataEntries" :key="entry.label">
                  <td class="meta-label">{{ entry.label }}</td>
                  <td class="meta-value">{{ entry.value }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
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
/* Preview Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.preview-modal {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  width: 90%;
  max-width: 900px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}
.preview-header h3 {
  font-size: 15px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.btn-close {
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 24px;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
}
.btn-close:hover { color: var(--text); }
.preview-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}
.preview-image {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #000;
  min-height: 300px;
  overflow: hidden;
}
.preview-img {
  max-width: 100%;
  max-height: 65vh;
  object-fit: contain;
}
.preview-noimg {
  color: var(--text-muted);
  font-size: 14px;
}
.preview-metadata {
  width: 300px;
  overflow-y: auto;
  border-left: 1px solid var(--border);
  padding: 12px;
}
.metadata-table {
  width: 100%;
  font-size: 12px;
  border-collapse: collapse;
}
.metadata-table tr {
  border-bottom: 1px solid var(--border);
}
.metadata-table td {
  padding: 6px 4px;
  vertical-align: top;
}
.meta-label {
  color: var(--text-muted);
  white-space: nowrap;
  width: 40%;
  font-weight: 500;
}
.meta-value {
  color: var(--text);
  word-break: break-all;
  font-family: monospace;
}
</style>
