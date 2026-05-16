<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useApiStore, type Target, type PaginatedResponse, type DuplicateGroup } from '@/stores/api'
import Pagination from '@/components/Pagination.vue'

const apiStore = useApiStore()
const router = useRouter()
const targets = ref<Target[]>([])
const page = ref(1)
const totalPages = ref(1)
const totalItems = ref(0)
const search = ref('')
const sortBy = ref('name')
const sortOrder = ref('desc')

// Filter state
const objectTypes = ref<string[]>([])
const constellations = ref<string[]>([])
const selectedType = ref('')
const selectedConstellation = ref('')

// Duplicate detection
const duplicates = ref<DuplicateGroup[]>([])
const showDuplicates = ref(false)
const merging = ref<Set<string>>(new Set())

async function loadFilters() {
  const res = await apiStore.fetch<{ object_types: string[]; constellations: string[] }>('/targets/types')
  objectTypes.value = res.object_types
  constellations.value = res.constellations
}

async function load() {
  const res = await apiStore.fetch<PaginatedResponse<Target>>('/targets', {
    page: page.value,
    page_size: 50,
    search: search.value || undefined,
    sort_by: sortBy.value,
    sort_order: sortOrder.value,
    object_type: selectedType.value || undefined,
    constellation: selectedConstellation.value || undefined,
  })
  targets.value = res.items
  totalPages.value = res.pages
  totalItems.value = res.total
}

async function checkDuplicates() {
  try {
    duplicates.value = await apiStore.fetch<DuplicateGroup[]>('/targets/duplicates')
    if (duplicates.value.length > 0) showDuplicates.value = true
  } catch {
    // ignore
  }
}

async function mergeGroup(canonicalName: string) {
  merging.value.add(canonicalName)
  try {
    await apiStore.post('/targets/merge-group', { canonical_name: canonicalName })
    // Refresh duplicates and targets list
    duplicates.value = await apiStore.fetch<DuplicateGroup[]>('/targets/duplicates')
    if (duplicates.value.length === 0) showDuplicates.value = false
    load()
  } catch (e: any) {
    alert('Fehler beim Zusammenführen: ' + (e.response?.data?.detail || e.message))
  } finally {
    merging.value.delete(canonicalName)
  }
}

const typeBadgeClass = (type: string | null): string => {
  const map: Record<string, string> = {
    'Galaxy': 'badge-galaxy',
    'Nebula': 'badge-nebula',
    'Star': 'badge-star',
    'Cluster': 'badge-cluster',
    'Supernova Remnant': 'badge-snr',
    'Planetary Nebula': 'badge-planetary',
  }
  return map[type || ''] || 'badge-default'
}

watch([page, search, sortBy, sortOrder, selectedType, selectedConstellation], load, { immediate: true })
loadFilters()
checkDuplicates()

function viewTarget(id: number) {
  router.push({ name: 'target-detail', params: { id } })
}

function toggleSortOrder() {
  sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
}
</script>

<template>
  <div>
    <div class="page-header">
      <h2>Targets</h2>
      <p>{{ totalItems }} astronomische Objekte</p>
    </div>

    <div v-if="showDuplicates && duplicates.length" class="duplicate-banner">
      <span>{{ duplicates.length }} mögliche Duplikat-Gruppe(n) gefunden.</span>
      <button class="btn btn-sm" @click="showDuplicates = false">Ausblenden</button>
    </div>

    <div v-if="showDuplicates" class="duplicate-list">
      <div v-for="group in duplicates" :key="group.canonical_name" class="duplicate-group">
        <div class="duplicate-group-header">
          <strong>{{ group.canonical_name }}</strong>
          <button
            class="btn btn-sm btn-merge"
            @click="mergeGroup(group.canonical_name)"
            :disabled="merging.has(group.canonical_name)"
          >
            {{ merging.has(group.canonical_name) ? 'Führe zusammen...' : 'Alle zusammenführen' }}
          </button>
        </div>
        <div v-for="t in group.targets" :key="t.id" class="duplicate-target">
          <span>{{ t.name }} ({{ t.session_count }} Sessions)</span>
          <button class="btn btn-sm" @click="viewTarget(t.id)">Öffnen</button>
        </div>
      </div>
    </div>

    <div class="filters">
      <div class="filter-group">
        <label>Suche</label>
        <input v-model="search" placeholder="Name..." type="text" />
      </div>
      <div class="filter-group">
        <label>Typ</label>
        <select v-model="selectedType">
          <option value="">Alle</option>
          <option v-for="t in objectTypes" :key="t" :value="t">{{ t }}</option>
        </select>
      </div>
      <div class="filter-group">
        <label>Sternbild</label>
        <select v-model="selectedConstellation">
          <option value="">Alle</option>
          <option v-for="c in constellations" :key="c" :value="c">{{ c }}</option>
        </select>
      </div>
      <div class="filter-group">
        <label>Sortierung</label>
        <select v-model="sortBy">
          <option value="name">Name</option>
          <option value="total_h">Belichtungszeit</option>
          <option value="session_count">Sessions</option>
          <option value="object_type">Typ</option>
        </select>
      </div>
      <div class="filter-group">
        <label>Richtung</label>
        <button class="btn btn-sm" @click="toggleSortOrder">
          {{ sortOrder === 'asc' ? '↑ Aufsteigend' : '↓ Absteigend' }}
        </button>
      </div>
    </div>

    <table class="data-table">
      <thead>
        <tr>
          <th class="sortable" @click="sortBy = 'name'; sortOrder = sortOrder === 'asc' && sortBy === 'name' ? 'desc' : 'asc'">Name {{ sortBy === 'name' ? (sortOrder === 'asc' ? '↑' : '↓') : '↕' }}</th>
          <th class="sortable" @click="sortBy = 'session_count'; sortOrder = sortOrder === 'asc' && sortBy === 'session_count' ? 'desc' : 'asc'">Sessions {{ sortBy === 'session_count' ? (sortOrder === 'asc' ? '↑' : '↓') : '↕' }}</th>
          <th class="sortable" @click="sortBy = 'total_h'; sortOrder = sortOrder === 'asc' && sortBy === 'total_h' ? 'desc' : 'asc'">Belichtung {{ sortBy === 'total_h' ? (sortOrder === 'asc' ? '↑' : '↓') : '↕' }}</th>
          <th class="sortable" @click="sortBy = 'object_type'; sortOrder = sortOrder === 'asc' && sortBy === 'object_type' ? 'desc' : 'asc'">Typ {{ sortBy === 'object_type' ? (sortOrder === 'asc' ? '↑' : '↓') : '↕' }}</th>
          <th class="sortable" @click="sortBy = 'constellation'; sortOrder = sortOrder === 'asc' && sortBy === 'constellation' ? 'desc' : 'asc'">Sternbild {{ sortBy === 'constellation' ? (sortOrder === 'asc' ? '↑' : '↓') : '↕' }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="t in targets" :key="t.id" class="clickable" @click="viewTarget(t.id)">
          <td><strong>{{ t.name }}</strong></td>
          <td>{{ t.session_count }}</td>
          <td>{{ t.total_exposure_h }}h</td>
          <td>
            <span v-if="t.object_type" :class="['badge', typeBadgeClass(t.object_type)]">
              {{ t.object_type }}
            </span>
            <span v-else class="text-faint">-</span>
          </td>
          <td>{{ t.constellation || '-' }}</td>
        </tr>
      </tbody>
    </table>

    <Pagination :total="totalItems" :page="page" :pages="totalPages" @update:page="page = $event" />
  </div>
</template>

<style scoped>
.duplicate-banner {
  background: rgba(240, 136, 62, 0.1);
  border: 1px solid var(--accent3);
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}
.duplicate-list {
  margin-bottom: 16px;
}
.duplicate-group {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 8px;
}
.duplicate-group-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}
.duplicate-target {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0 0 12px;
  font-size: 13px;
}
.sortable { cursor: pointer; user-select: none; }
.sortable:hover { color: var(--accent); }
</style>
