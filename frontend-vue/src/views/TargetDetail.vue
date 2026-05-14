<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApiStore, type Session, type PaginatedResponse } from '@/stores/api'
import Pagination from '@/components/Pagination.vue'

const route = useRoute()
const router = useRouter()
const apiStore = useApiStore()
const target = ref<any>(null)
const sessions = ref<Session[]>([])
const page = ref(1)
const totalPages = ref(1)
const totalItems = ref(0)

const targetId = computed(() => parseInt(route.params.id as string))

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
  })
  sessions.value = res.items
  totalPages.value = res.pages
  totalItems.value = res.total
}

onMounted(() => {
  loadTarget()
  loadSessions()
})

watch(page, loadSessions)
</script>

<template>
  <div>
    <div class="page-header">
      <h2>{{ target?.name || 'Loading...' }}</h2>
      <p v-if="target">
        {{ target.session_count }} Sessions &middot; {{ target.total_exposure_h }}h Belichtung
        <span v-if="target.object_type">&middot; {{ target.object_type }}</span>
      </p>
    </div>

    <div class="card">
      <h3>Sessions</h3>
      <table class="data-table">
        <thead>
          <tr>
            <th>Datum</th>
            <th>Kamera</th>
            <th>Teleskop</th>
            <th>Belichtung</th>
            <th>Frames</th>
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

    <Pagination :total="totalItems" :page="page" :pages="totalPages" @update:page="page = $event" />
  </div>
</template>
