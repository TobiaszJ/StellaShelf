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
const cameraId = ref<number | null>(null)
const telescopeId = ref<number | null>(null)
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

// Read filter query params from Equipment view navigation
if (route.query.filter_name) {
  filterName.value = route.query.filter_name as string
}
if (route.query.filter) {
  statusFilter.value = route.query.filter as string
}
if (route.query.camera_id) {
  cameraId.value = parseInt(route.query.camera_id as string)
}
if (route.query.telescope_id) {
  telescopeId.value = parseInt(route.query.telescope_id as string)
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
  if (cameraId.value) params.camera_id = cameraId.value
  if (telescopeId.value) params.telescope_id = telescopeId.value
  const res = await apiStore.fetch<PaginatedResponse<Session>>('/sessions', params)
  sessions.value = res.items
  totalPages.value = res.pages
  totalItems.value = res.total
}

watch([page, statusFilter, filterName, cameraId, telescopeId, sortBy, sortOrder], load, { immediate: true })

</script>

<template>
  <div>
    <div class="page-header">
      <h2>{{ $t('sessions.title') }}</h2>
      <p>{{ $t('sessions.description', { count: totalItems }) }}</p>
      <span v-if="filterName" class="filter-badge">{{ $t('sessions.filter_badge', { name: filterName }) }}</span>
      <span v-if="cameraId" class="filter-badge">Kamera: {{ cameraId }}</span>
      <span v-if="telescopeId" class="filter-badge">Teleskop: {{ telescopeId }}</span>
    </div>

    <div class="filters">
      <div class="filter-group">
        <label>{{ $t('sessions.filter_status') }}</label>
        <select v-model="statusFilter">
          <option value="">{{ $t('sessions.filter_all') }}</option>
          <option value="raw">{{ $t('sessions.status_raw') }}</option>
          <option value="calibrated">{{ $t('sessions.status_calibrated') }}</option>
          <option value="stacked">{{ $t('sessions.status_stacked') }}</option>
        </select>
      </div>
      <div class="filter-group">
        <label>{{ $t('sessions.filter_sort') }}</label>
        <select v-model="sortBy">
          <option value="date_obs">{{ $t('sessions.col_date') }}</option>
          <option value="total_exposure_h">{{ $t('sessions.col_exposure') }}</option>
          <option value="frame_count">{{ $t('sessions.col_frames') }}</option>
        </select>
      </div>
    </div>

    <div class="table-responsive">
      <table class="data-table">
        <thead>
          <tr>
            <th>{{ $t('sessions.col_target') }}</th>
            <th class="sortable" @click="toggleSort('date_obs')">{{ $t('sessions.col_date') }} {{ sortIcon('date_obs') }}</th>
            <th>{{ $t('sessions.col_camera') }}</th>
            <th>{{ $t('sessions.col_telescope') }}</th>
            <th class="sortable" @click="toggleSort('total_exposure_h')">{{ $t('sessions.col_exposure') }} {{ sortIcon('total_exposure_h') }}</th>
            <th>{{ $t('sessions.col_folder') }}</th>
            <th class="sortable" @click="toggleSort('frame_count')">{{ $t('sessions.col_frames') }} {{ sortIcon('frame_count') }}</th>
            <th>{{ $t('sessions.col_status') }}</th>
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
    </div>

    <Pagination :total="totalItems" :page="page" :pages="totalPages" @update:page="page = $event" />
  </div>
</template>
