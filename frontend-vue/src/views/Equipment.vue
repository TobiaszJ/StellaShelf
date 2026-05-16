<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useApiStore, type Camera, type Telescope, type FilterStat } from '@/stores/api'
import Pagination from '@/components/Pagination.vue'

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

  items.sort((a, b) => {
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
</script>

<template>
  <div>
    <div class="page-header">
      <h2>Equipment</h2>
      <p>{{ totalItems }} Einträge in deiner Sammlung</p>
    </div>

    <div class="tabs">
      <button :class="['tab', { active: activeTab === 'cameras' }]" @click="activeTab = 'cameras'; page = 1">
        Kameras ({{ cameras.length }})
      </button>
      <button :class="['tab', { active: activeTab === 'telescopes' }]" @click="activeTab = 'telescopes'; page = 1">
        Teleskope ({{ telescopes.length }})
      </button>
      <button :class="['tab', { active: activeTab === 'filters' }]" @click="activeTab = 'filters'; page = 1">
        Filter ({{ filters.length }})
      </button>
    </div>

    <!-- Cameras -->
    <div class="card" v-if="activeTab === 'cameras'">
      <h3>Kameras</h3>
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th class="sortable" @click="toggleSort('name')">Name{{ sortIndicator('name') }}</th>
              <th class="sortable" @click="toggleSort('pixel_size_um')">Pixel{{ sortIndicator('pixel_size_um') }}</th>
              <th class="sortable" @click="toggleSort('frame_count')">Frames{{ sortIndicator('frame_count') }}</th>
              <th class="sortable" @click="toggleSort('total_exposure_h')">Belichtung{{ sortIndicator('total_exposure_h') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in paginatedItems" :key="c.id">
              <td><strong>{{ c.name }}</strong> <span v-if="c.short_name" class="text-faint">({{ c.short_name }})</span></td>
              <td>{{ c.pixel_size_um ? c.pixel_size_um + 'µm' : '-' }}</td>
              <td>{{ c.frame_count }}</td>
              <td>{{ c.total_exposure_h }}h</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Telescopes -->
    <div class="card" v-if="activeTab === 'telescopes'">
      <h3>Teleskope</h3>
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th class="sortable" @click="toggleSort('name')">Name{{ sortIndicator('name') }}</th>
              <th class="sortable" @click="toggleSort('focal_length_mm')">Brennweite{{ sortIndicator('focal_length_mm') }}</th>
              <th class="sortable" @click="toggleSort('frame_count')">Frames{{ sortIndicator('frame_count') }}</th>
              <th class="sortable" @click="toggleSort('total_exposure_h')">Belichtung{{ sortIndicator('total_exposure_h') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in paginatedItems" :key="t.id">
              <td><strong>{{ t.name }}</strong></td>
              <td>{{ t.focal_length_mm ? t.focal_length_mm + ' mm' : '-' }}</td>
              <td>{{ t.frame_count }}</td>
              <td>{{ t.total_exposure_h }}h</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Filters -->
    <div class="card" v-if="activeTab === 'filters'">
      <h3>Filter</h3>
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th class="sortable" @click="toggleSort('name')">Name{{ sortIndicator('name') }}</th>
              <th class="sortable" @click="toggleSort('frame_count')">Frames{{ sortIndicator('frame_count') }}</th>
              <th class="sortable" @click="toggleSort('total_exposure_h')">Belichtung{{ sortIndicator('total_exposure_h') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="f in paginatedItems" :key="f.name" class="clickable" @click="viewFrames(f.name)">
              <td><strong>{{ f.name }}</strong></td>
              <td>{{ f.frame_count }}</td>
              <td>{{ f.total_exposure_h }}h</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <Pagination :total="totalItems" :page="page" :pages="totalPages" @update:page="page = $event" />
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
</style>
