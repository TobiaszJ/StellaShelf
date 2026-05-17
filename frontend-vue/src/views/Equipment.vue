<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useApiStore, type Camera, type Telescope, type FilterStat, type PaginatedResponse } from '@/stores/api'
import { useI18n } from 'vue-i18n'
import Pagination from '@/components/Pagination.vue'

const { t } = useI18n()
const apiStore = useApiStore()
const router = useRouter()
const activeTab = ref('cameras')

// Data
const cameras = ref<Camera[]>([])
const telescopes = ref<Telescope[]>([])
const filters = ref<FilterStat[]>([])

// Pagination
const page = ref(1)
const pageSize = 20

// Sorting
const sortKey = ref('frame_count')
const sortOrder = ref('desc')

// Merge state
const mergeSourceId = ref<number | null>(null)
const mergeSourceName = ref('')
const mergeSearch = ref('')
const mergeResults = ref<any[]>([])
const mergeLoading = ref(false)
const mergeBusy = ref(false)
const mergeConfirming = ref(false)
const mergeDestination = ref<any>(null)

onMounted(async () => {
  cameras.value = await apiStore.fetch<Camera[]>('/cameras')
  telescopes.value = await apiStore.fetch<Telescope[]>('/telescopes')
  filters.value = await apiStore.fetch<FilterStat[]>('/filters')
})

function toggleSort(key: string) {
  if (sortKey.value === key) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortOrder.value = 'desc'
  }
}

const sortedItems = computed(() => {
  let items: any[]
  switch (activeTab.value) {
    case 'cameras': items = [...cameras.value]; break
    case 'telescopes': items = [...telescopes.value]; break
    case 'filters': items = [...filters.value]; break
    default: items = []
  }
  items.sort((a: any, b: any) => {
    const aVal = a[sortKey.value] ?? ''
    const bVal = b[sortKey.value] ?? ''
    const cmp = typeof aVal === 'string' ? aVal.localeCompare(bVal) : (aVal - bVal)
    return sortOrder.value === 'asc' ? cmp : -cmp
  })
  return items
})

const paginatedItems = computed(() => {
  const start = (page.value - 1) * pageSize
  return sortedItems.value.slice(start, start + pageSize)
})

const totalItems = computed(() => sortedItems.value.length)
const totalPages = computed(() => Math.max(1, Math.ceil(totalItems.value / pageSize)))

const sortIndicator = (key: string) => {
  if (sortKey.value !== key) return ''
  return sortOrder.value === 'asc' ? ' ↑' : ' ↓'
}

function viewFrames(filterName: string) {
  router.push({ name: 'sessions', query: { filter_name: filterName } })
}

function viewCamera(cameraId: number) {
  router.push({ name: 'sessions', query: { camera_id: String(cameraId) } })
}

function viewTelescope(telescopeId: number) {
  router.push({ name: 'sessions', query: { telescope_id: String(telescopeId) } })
}

// Merge logic
function openMerge(item: any) {
  mergeSourceId.value = item.id || null
  mergeSourceName.value = item.name || item
  mergeSearch.value = ''
  mergeResults.value = []
  mergeDestination.value = null
  mergeConfirming.value = false
}

function cancelMerge() {
  mergeSourceId.value = null
  mergeSourceName.value = ''
  mergeSearch.value = ''
  mergeResults.value = []
  mergeDestination.value = null
  mergeConfirming.value = false
}

async function searchMergeTargets() {
  if (!mergeSearch.value.trim()) {
    mergeResults.value = []
    return
  }
  mergeLoading.value = true
  try {
    if (activeTab.value === 'cameras') {
      mergeResults.value = cameras.value.filter(
        c => c.id !== mergeSourceId.value && c.name.toLowerCase().includes(mergeSearch.value.toLowerCase())
      )
    } else if (activeTab.value === 'telescopes') {
      const all = telescopes.value.filter(t => t.id !== mergeSourceId.value && t.name.toLowerCase().includes(mergeSearch.value.toLowerCase()))
      mergeResults.value = all
    } else if (activeTab.value === 'filters') {
      const all = filters.value.filter(f => f.name.toLowerCase() !== mergeSourceName.value.toLowerCase() && f.name.toLowerCase().includes(mergeSearch.value.toLowerCase()))
      mergeResults.value = all
    }
  } catch {
    mergeResults.value = []
  } finally {
    mergeLoading.value = false
  }
}

function selectMergeDestination(item: any) {
  mergeDestination.value = item
  mergeSearch.value = item.name || item
  mergeResults.value = []
}

async function doMerge() {
  if (!mergeDestination.value || mergeSourceId.value === null) return
  mergeBusy.value = true
  try {
    if (activeTab.value === 'cameras') {
      await apiStore.post('/cameras/merge', {
        source_id: mergeSourceId.value,
        destination_id: mergeDestination.value.id,
      })
      cameras.value = await apiStore.fetch<Camera[]>('/cameras')
    } else if (activeTab.value === 'telescopes') {
      await apiStore.post('/telescopes/merge', {
        source_id: mergeSourceId.value,
        destination_id: mergeDestination.value.id,
      })
      telescopes.value = await apiStore.fetch<Telescope[]>('/telescopes')
    } else if (activeTab.value === 'filters') {
      await apiStore.post('/filters/merge', {
        source_name: mergeSourceName.value,
        destination_name: mergeDestination.value.name,
      })
      filters.value = await apiStore.fetch<FilterStat[]>('/filters')
    }
    cancelMerge()
  } catch (e: any) {
    alert('Fehler: ' + (e.response?.data?.detail || e.message))
  } finally {
    mergeBusy.value = false
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h2>{{ $t('equipment.title') }}</h2>
      <p>{{ $t('equipment.description', { count: totalItems }) }}</p>
    </div>

    <div class="tabs">
      <button :class="['tab', { active: activeTab === 'cameras' }]" @click="activeTab = 'cameras'; page = 1">
        {{ $t('equipment.tab_cameras', { count: cameras.length }) }}
      </button>
      <button :class="['tab', { active: activeTab === 'telescopes' }]" @click="activeTab = 'telescopes'; page = 1">
        {{ $t('equipment.tab_telescopes', { count: telescopes.length }) }}
      </button>
      <button :class="['tab', { active: activeTab === 'filters' }]" @click="activeTab = 'filters'; page = 1">
        {{ $t('equipment.tab_filters', { count: filters.length }) }}
      </button>
    </div>

    <!-- Cameras -->
    <div class="card" v-if="activeTab === 'cameras'">
      <h3>{{ $t('equipment.tab_cameras', { count: cameras.length }) }}</h3>
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th class="sortable" @click="toggleSort('name')">{{ $t('equipment.col_name') }}{{ sortIndicator('name') }}</th>
              <th class="sortable" @click="toggleSort('pixel_size_um')">{{ $t('equipment.col_pixel') }}{{ sortIndicator('pixel_size_um') }}</th>
              <th class="sortable" @click="toggleSort('frame_count')">{{ $t('equipment.col_frames') }}{{ sortIndicator('frame_count') }}</th>
              <th class="sortable" @click="toggleSort('total_exposure_h')">{{ $t('equipment.col_exposure') }}{{ sortIndicator('total_exposure_h') }}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in paginatedItems" :key="c.id" class="clickable" @click="viewCamera(c.id)">
              <td><strong>{{ c.name }}</strong> <span v-if="c.short_name" class="text-faint">({{ c.short_name }})</span></td>
              <td>{{ c.pixel_size_um ? c.pixel_size_um + 'µm' : '-' }}</td>
              <td>{{ c.frame_count }}</td>
              <td>{{ c.total_exposure_h }}h</td>
              <td><button class="btn btn-sm btn-outline" @click.stop="openMerge(c)">Merge</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Telescopes -->
    <div class="card" v-if="activeTab === 'telescopes'">
      <h3>{{ $t('equipment.tab_telescopes', { count: telescopes.length }) }}</h3>
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th class="sortable" @click="toggleSort('name')">{{ $t('equipment.col_name') }}{{ sortIndicator('name') }}</th>
              <th class="sortable" @click="toggleSort('focal_length_mm')">{{ $t('equipment.col_focal') }}{{ sortIndicator('focal_length_mm') }}</th>
              <th class="sortable" @click="toggleSort('frame_count')">{{ $t('equipment.col_frames') }}{{ sortIndicator('frame_count') }}</th>
              <th class="sortable" @click="toggleSort('total_exposure_h')">{{ $t('equipment.col_exposure') }}{{ sortIndicator('total_exposure_h') }}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in paginatedItems" :key="t.id" class="clickable" @click="viewTelescope(t.id)">
              <td><strong>{{ t.name }}</strong></td>
              <td>{{ t.focal_length_mm ? t.focal_length_mm + ' mm' : '-' }}</td>
              <td>{{ t.frame_count }}</td>
              <td>{{ t.total_exposure_h }}h</td>
              <td><button class="btn btn-sm btn-outline" @click.stop="openMerge(t)">Merge</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Filters -->
    <div class="card" v-if="activeTab === 'filters'">
      <h3>{{ $t('equipment.tab_filters', { count: filters.length }) }}</h3>
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th class="sortable" @click="toggleSort('name')">{{ $t('equipment.col_name') }}{{ sortIndicator('name') }}</th>
              <th class="sortable" @click="toggleSort('frame_count')">{{ $t('equipment.col_frames') }}{{ sortIndicator('frame_count') }}</th>
              <th class="sortable" @click="toggleSort('total_exposure_h')">{{ $t('equipment.col_exposure') }}{{ sortIndicator('total_exposure_h') }}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="f in paginatedItems" :key="f.name" class="clickable" @click="viewFrames(f.name)">
              <td><strong>{{ f.name }}</strong></td>
              <td>{{ f.frame_count }}</td>
              <td>{{ f.total_exposure_h }}h</td>
              <td><button class="btn btn-sm btn-outline" @click.stop="openMerge(f)">Merge</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <Pagination :total="totalItems" :page="page" :pages="totalPages" @update:page="page = $event" />

    <!-- Merge Modal -->
    <div v-if="mergeSourceId !== null || activeTab === 'filters' && mergeSourceName" class="modal-overlay" @click.self="cancelMerge">
      <div class="modal">
        <h3>{{ activeTab === 'cameras' ? 'Kamera zusammenführen' : activeTab === 'telescopes' ? 'Teleskop zusammenführen' : 'Filter zusammenführen' }}</h3>
        <p style="margin-bottom: 12px; color: var(--text-muted); font-size: 13px;">
          <strong>{{ mergeSourceName }}</strong> mit einem anderen {{ activeTab === 'cameras' ? 'Kamera' : activeTab === 'telescopes' ? 'Teleskop' : 'Filter' }} zusammenführen.
          Alle Sessions und Frames werden auf das Ziel übertragen.
        </p>

        <div v-if="!mergeDestination">
          <label>Ziel {{ activeTab === 'cameras' ? 'Kamera' : activeTab === 'telescopes' ? 'Teleskop' : 'Filter' }} suchen</label>
          <input v-model="mergeSearch" type="text" placeholder="Name eingeben..." class="merge-search-input" @input="searchMergeTargets" />
          <div v-if="mergeLoading" class="loading" style="padding: 12px;">Suche...</div>
          <div v-else-if="mergeResults.length" class="merge-results">
            <div v-for="item in mergeResults" :key="item.id || item.name" class="merge-result-item" @click="selectMergeDestination(item)">
              <strong>{{ item.name || item }}</strong>
              <span style="color: var(--text-muted); font-size: 12px;">
                {{ item.frame_count || 0 }} Frames
              </span>
            </div>
          </div>
          <p v-else-if="mergeSearch && !mergeLoading" class="empty" style="padding: 12px;">Keine Einträge gefunden.</p>
        </div>

        <div v-else>
          <div class="merge-confirm">
            <div class="merge-arrow">
              <span class="merge-from">{{ mergeSourceName }}</span>
              <span class="merge-arrow-sym">→</span>
              <span class="merge-to">{{ mergeDestination.name || mergeDestination }}</span>
            </div>
            <div class="merge-actions" style="margin-top: 16px;">
              <button class="btn btn-danger" @click="doMerge" :disabled="mergeBusy">
                {{ mergeBusy ? 'Führe zusammen...' : 'Bestätigen & Zusammenführen' }}
              </button>
              <button class="btn btn-ghost" @click="cancelMerge" :disabled="mergeBusy">Abbrechen</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 16px;
}
.tab {
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text-muted);
  padding: 8px 16px;
  border-radius: 6px 6px 0 0;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
}
.tab.active {
  background: var(--surface);
  color: var(--text);
  border-bottom-color: var(--accent);
}
th.sortable { cursor: pointer; user-select: none; }
th.sortable:hover { color: var(--text); }
.text-faint { color: var(--text-faint); font-size: 12px; }

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
  background: rgba(255,255,255,0.03);
}
.merge-result-item + .merge-result-item {
  border-top: 1px solid var(--border);
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
.merge-arrow-sym { font-size: 20px; color: var(--accent); }
.merge-from { font-weight: 600; color: var(--danger); }
.merge-to { font-weight: 700; color: var(--accent2); }
.merge-actions { display: flex; gap: 8px; }
</style>
