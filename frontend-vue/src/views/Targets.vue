<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useApiStore, type Target, type PaginatedResponse } from '@/stores/api'
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
          <th>Name</th>
          <th>Sessions</th>
          <th>Belichtung</th>
          <th>Typ</th>
          <th>Sternbild</th>
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
