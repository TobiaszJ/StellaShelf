<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useApiStore, type Session, type PaginatedResponse } from '@/stores/api'
import Pagination from '@/components/Pagination.vue'

const apiStore = useApiStore()
const router = useRouter()
const route = useRoute()
const sessions = ref<Session[]>([])
const page = ref(1)
const totalPages = ref(1)
const totalItems = ref(0)
const statusFilter = ref('')
const filterName = ref('')
const sortBy = ref('date_obs')
const sortOrder = ref('desc')

function shortPath(path: string | null | undefined): string {
  if (!path) return '-'
  const parts = path.split('/')
  return parts.length > 3 ? '.../' + parts.slice(-3).join('/') : path
}

function toggleSort(col: string) {
  if (sortBy.value === col) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortBy.value = col
    sortOrder.value = 'desc'
  }
  page.value = 1
}

function sortIcon(col: string): string {
  if (sortBy.value !== col) return '↕'
  return sortOrder.value === 'asc' ? '↑' : '↓'
}

// Read filter query param from Equipment view navigation
if (route.query.filter_name) {
  filterName.value = route.query.filter_name as string
}
if (route.query.filter) {
  statusFilter.value = route.query.filter as string
}

async function load() {
  const params: Record<string, any> = {
    page: page.value,
    page_size: 50,
    sort_by: sortBy.value,
    sort_order: sortOrder.value,
  }
  if (statusFilter.value) params.status = statusFilter.value
  if (filterName.value) params.filter_name = filterName.value
  const res = await apiStore.fetch<PaginatedResponse<Session>>('/sessions', params)
  sessions.value = res.items
  totalPages.value = res.pages
  totalItems.value = res.total
}

watch([page, statusFilter, filterName, sortBy, sortOrder], load, { immediate: true })

</script>

<template>
  <div>
    <div class="page-header">
      <h2>Sessions</h2>
      <p>{{ totalItems }} Beobachtungs-Sessions</p>
      <span v-if="filterName" class="filter-badge">Filter: {{ filterName }}</span>
    </div>

    <div class="filters">
      <div class="filter-group">
        <label>Status</label>
        <select v-model="statusFilter">
          <option value="">Alle</option>
          <option value="raw">Raw</option>
          <option value="calibrated">Kalibriert</option>
          <option value="stacked">Gestackt</option>
        </select>
      </div>
      <div class="filter-group">
        <label>Sortierung</label>
        <select v-model="sortBy">
          <option value="date_obs">Datum</option>
          <option value="total_exposure_h">Belichtung</option>
          <option value="frame_count">Frames</option>
        </select>
      </div>
    </div>

    <table class="data-table">
      <thead>
        <tr>
          <th>Ziel</th>
          <th class="sortable" @click="toggleSort('date_obs')">Datum {{ sortIcon('date_obs') }}</th>
          <th>Kamera</th>
          <th>Teleskop</th>
          <th class="sortable" @click="toggleSort('total_exposure_h')">Belichtung {{ sortIcon('total_exposure_h') }}</th>
          <th>Ordner</th>
          <th class="sortable" @click="toggleSort('frame_count')">Frames {{ sortIcon('frame_count') }}</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="s in sessions"
          :key="s.id"
          class="clickable"
          @click="router.push({ name: 'session-detail', params: { id: s.id } })"
        >
          <td><strong>{{ s.target_name }}</strong></td>
          <td>{{ s.date_obs ? new Date(s.date_obs).toLocaleDateString('de-CH') : '-' }}</td>
          <td>{{ s.camera_name || '-' }}</td>
          <td>{{ s.telescope_name || '-' }}</td>
          <td>{{ s.total_exposure_h }}h</td>
          <td class="folder-cell">{{ shortPath(s.folder_path) }}</td>
          <td>{{ s.frame_count }}</td>
          <td><span class="badge badge-light">{{ s.status }}</span></td>
        </tr>
      </tbody>
    </table>

    <Pagination :total="totalItems" :page="page" :pages="totalPages" @update:page="page = $event" />
  </div>
</template>
