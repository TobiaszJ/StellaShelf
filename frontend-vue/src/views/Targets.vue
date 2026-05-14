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

async function load() {
  const res = await apiStore.fetch<PaginatedResponse<Target>>('/targets', {
    page: page.value,
    page_size: 50,
    search: search.value || undefined,
    sort_by: sortBy.value,
    sort_order: sortOrder.value,
  })
  targets.value = res.items
  totalPages.value = res.pages
  totalItems.value = res.total
}

watch([page, search, sortBy, sortOrder], load, { immediate: true })

function viewTarget(id: number) {
  router.push({ name: 'target-detail', params: { id } })
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
        <label>Sortierung</label>
        <select v-model="sortBy">
          <option value="name">Name</option>
          <option value="total_h">Belichtungszeit</option>
          <option value="session_count">Sessions</option>
        </select>
      </div>
      <div class="filter-group">
        <label>Richtung</label>
        <select v-model="sortOrder">
          <option value="asc">Aufsteigend</option>
          <option value="desc">Absteigend</option>
        </select>
      </div>
    </div>

    <table class="data-table">
      <thead>
        <tr>
          <th>Name</th>
          <th>Sessions</th>
          <th>Belichtung</th>
          <th>Typ</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="t in targets" :key="t.id" class="clickable" @click="viewTarget(t.id)">
          <td><strong>{{ t.name }}</strong></td>
          <td>{{ t.session_count }}</td>
          <td>{{ t.total_exposure_h }}h</td>
          <td>{{ t.object_type || '-' }}</td>
        </tr>
      </tbody>
    </table>

    <Pagination :total="totalItems" :page="page" :pages="totalPages" @update:page="page = $event" />
  </div>
</template>
