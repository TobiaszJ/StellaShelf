<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useApiStore, type Frame } from '@/stores/api'

const route = useRoute()
const apiStore = useApiStore()
const session = ref<any>(null)
const frames = ref<Frame[]>([])

const sessionId = computed(() => parseInt(route.params.id as string))

onMounted(async () => {
  try {
    session.value = await apiStore.fetch(`/sessions/${sessionId.value}`)
    frames.value = await apiStore.fetch<Frame[]>('/frames', { session_id: sessionId.value, page_size: 100 })
  } catch {
    // error
  }
})

function frameTypeBadge(type_: string) {
  return `badge badge-${type_.toLowerCase()}`
}
</script>

<template>
  <div>
    <div class="page-header">
      <h2>{{ session?.target_name || 'Loading...' }}</h2>
      <p v-if="session">
        {{ session.camera_name }} {{ session.date_obs ? ' &middot; ' + new Date(session.date_obs).toLocaleDateString('de-CH') : '' }}
        &middot; {{ session.total_exposure_h }}h &middot; {{ session.frame_count }} Frames
      </p>
    </div>

    <div class="card">
      <h3>Frames</h3>
      <table class="data-table">
        <thead>
          <tr>
            <th>Datei</th>
            <th>Typ</th>
            <th>Filter</th>
            <th>Belichtung</th>
            <th>Gain</th>
            <th>Temp</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="f in frames" :key="f.id">
            <td>{{ f.filename }}</td>
            <td><span :class="frameTypeBadge(f.frame_type)">{{ f.frame_type }}</span></td>
            <td>{{ f.filter_name || '-' }}</td>
            <td>{{ f.exposure }}s</td>
            <td>{{ f.gain ?? '-' }}</td>
            <td>{{ f.ccd_temp ? f.ccd_temp.toFixed(1) + '°C' : '-' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
