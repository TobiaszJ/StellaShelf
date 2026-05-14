<script setup lang="ts">
import { ref } from 'vue'
import { useApiStore } from '@/stores/api'

const apiStore = useApiStore()
const scanning = ref(false)
const results = ref<any>(null)

async function startPlatesolve() {
  scanning.value = true
  results.value = null
  try {
    results.value = await apiStore.post('/platesolve', {})
  } catch (e: any) {
    alert('Fehler: ' + (e.message || 'Unbekannter Fehler'))
  } finally {
    scanning.value = false
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h2>ASTAP Platesolving</h2>
      <p>Koordinaten für Frames ohne RA/Dec bestimmen</p>
    </div>

    <div class="card">
      <p style="margin-bottom: 16px; color: var(--text-muted);">
        ASTAP (Astrometric Stacking and Plate-solving Tool) kann fehlende Koordinaten in FITS-Headern
        automatisch bestimmen. Voraussetzung: ASTAP ist installiert und der Pfad in den Einstellungen konfiguriert.
      </p>

      <button class="btn" @click="startPlatesolve" :disabled="scanning">
        {{ scanning ? 'Platesolving läuft...' : 'Platesolving starten' }}
      </button>

      <div v-if="results" class="platesolve-results" style="margin-top: 16px;">
        <pre>{{ JSON.stringify(results, null, 2) }}</pre>
      </div>
    </div>
  </div>
</template>
