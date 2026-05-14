<script setup lang="ts">
import { ref, computed } from 'vue'
import { useScanStore } from '@/stores/scan'

const scanStore = useScanStore()
const selectedPath = ref('/mnt/data/Astro/astro')

const knownPaths = [
  { label: 'Alle Daten', value: '/mnt/data/Astro/astro' },
  { label: 'ASI533MCPro', value: '/mnt/data/Astro/astro/ASI533MCPro' },
  { label: 'ASI2600MMPro', value: '/mnt/data/Astro/astro/ASI2600MMPro' },
  { label: 'ASI2600MMPro2', value: '/mnt/data/Astro/astro/ASI2600MMPro2' },
  { label: 'ASI294MMPro', value: '/mnt/data/Astro/astro/ASI294MMPro' },
  { label: 'ASI183MMPro', value: '/mnt/data/Astro/astro/ASI183MMPro' },
  { label: 'nas/', value: '/mnt/data/Astro/astro/nas' },
  { label: 'Sort', value: '/mnt/data/Astro/astro/Sort' },
]

const btnDisabled = computed(() => scanStore.state.running)

async function startScan() {
  try {
    await scanStore.startScan(selectedPath.value)
  } catch (e: any) {
    alert(e.response?.data?.detail || 'Fehler beim Starten des Scans')
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h2>Scan starten</h2>
      <p>FITS-Header auslesen und in die Datenbank importieren</p>
    </div>

    <div class="card">
      <h3>Scan-Pfad auswaehlen</h3>
      <div class="scan-path-selector">
        <div class="filter-group">
          <label>Verzeichnis</label>
          <select v-model="selectedPath">
            <option v-for="p in knownPaths" :key="p.value" :value="p.value">{{ p.label }}</option>
          </select>
        </div>
        <div class="filter-group">
          <label>Oder benutzerdefiniert</label>
          <input type="text" v-model="selectedPath" placeholder="/mnt/data/Astro/..." />
        </div>
        <button class="btn btn-success" :disabled="btnDisabled" @click="startScan">
          Scan starten
        </button>
      </div>
    </div>

    <div v-if="scanStore.state.phase !== 'idle'" class="card scan-progress-large">
      <h3>{{ scanStore.phaseLabel }}</h3>
      <div class="bar-bg">
        <div class="bar-fill" :style="{ width: scanStore.progress + '%' }"></div>
      </div>
      <div class="scan-stats-row">
        <div class="scan-stat">
          <div class="num">{{ scanStore.state.total.toLocaleString() }}</div>
          <div class="lbl">Total</div>
        </div>
        <div class="scan-stat">
          <div class="num">{{ scanStore.state.processed.toLocaleString() }}</div>
          <div class="lbl">Gescannt</div>
        </div>
        <div class="scan-stat">
          <div class="num">{{ scanStore.state.imported.toLocaleString() }}</div>
          <div class="lbl">Importiert</div>
        </div>
        <div class="scan-stat">
          <div class="num">{{ scanStore.state.skipped.toLocaleString() }}</div>
          <div class="lbl">Uebersprungen</div>
        </div>
      </div>
      <div class="current-file">{{ scanStore.state.current_file }}</div>
    </div>

    <div class="card">
      <h3>Info</h3>
      <p>Der Scan liest FITS-Header aus und importiert Metadaten in die Datenbank.
         Bestehende Dateien werden uebersprungen. Der Scan laeuft im Hintergrund —
         du kannst waehrenddessen weiterarbeiten.</p>
    </div>
  </div>
</template>
