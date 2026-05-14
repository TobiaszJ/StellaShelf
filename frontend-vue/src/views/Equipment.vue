<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useApiStore, type Camera, type Telescope } from '@/stores/api'

const apiStore = useApiStore()
const cameras = ref<Camera[]>([])
const telescopes = ref<Telescope[]>([])

onMounted(async () => {
  cameras.value = await apiStore.fetch<Camera[]>('/cameras')
  telescopes.value = await apiStore.fetch<Telescope[]>('/telescopes')
})
</script>

<template>
  <div>
    <div class="page-header">
      <h2>Equipment</h2>
      <p>Kameras und Teleskope in deiner Sammlung</p>
    </div>

    <div class="card">
      <h3>Kameras</h3>
      <table class="data-table">
        <thead>
          <tr><th>Name</th><th>Pixel (um)</th><th>Frames</th><th>Belichtung</th></tr>
        </thead>
        <tbody>
          <tr v-for="c in cameras" :key="c.id">
            <td>{{ c.name }}</td>
            <td>{{ c.pixel_size_um || '-' }}</td>
            <td>{{ c.frame_count }}</td>
            <td>{{ c.total_exposure_h }}h</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="card">
      <h3>Teleskope</h3>
      <table class="data-table">
        <thead>
          <tr><th>Name</th><th>Brennweite (mm)</th><th>Frames</th><th>Belichtung</th></tr>
        </thead>
        <tbody>
          <tr v-for="t in telescopes" :key="t.id">
            <td>{{ t.name }}</td>
            <td>{{ t.focal_length_mm || '-' }}</td>
            <td>{{ t.frame_count }}</td>
            <td>{{ t.total_exposure_h }}h</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
