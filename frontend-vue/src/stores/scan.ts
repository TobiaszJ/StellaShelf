import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

export interface ScanState {
  running: boolean
  total: number
  processed: number
  imported: number
  skipped: number
  current_file: string
  phase: string
  error: string | null
}

export const useScanStore = defineStore('scan', () => {
  const state = ref<ScanState>({
    running: false,
    total: 0,
    processed: 0,
    imported: 0,
    skipped: 0,
    current_file: '',
    phase: 'idle',
    error: null,
  })
  const pollInterval = ref<number | null>(null)

  const progress = computed(() =>
    state.value.total > 0 ? Math.round((state.value.processed / state.value.total) * 100) : 0
  )

  const phaseLabel = computed(() => {
    switch (state.value.phase) {
      case 'scanning': return 'Scanne FITS-Header...'
      case 'importing': return 'Importiere in Datenbank...'
      case 'done': return 'Scan abgeschlossen'
      case 'error': return 'Fehler beim Scan'
      default: return ''
    }
  })

  async function fetchStatus() {
    try {
      const res = await axios.get('/api/v1/scan/status')
      state.value = res.data
    } catch {
      // ignore polling errors
    }
  }

  function startPolling() {
    if (pollInterval.value) clearInterval(pollInterval.value)
    fetchStatus()
    pollInterval.value = window.setInterval(fetchStatus, 500)
  }

  function stopPolling() {
    if (pollInterval.value) {
      clearInterval(pollInterval.value)
      pollInterval.value = null
    }
  }

  async function startScan(path: string) {
    const res = await axios.post('/api/v1/scan', { path, recursive: true })
    state.value = {
      running: true,
      total: 0,
      processed: 0,
      imported: 0,
      skipped: 0,
      current_file: 'Initialisiere...',
      phase: 'scanning',
      error: null,
    }
    startPolling()
    return res.data
  }

  // Watch for completion/error to stop polling
  let lastPhase = state.value.phase
  setInterval(() => {
    if (state.value.phase !== lastPhase) {
      lastPhase = state.value.phase
      if (state.value.phase === 'done' || state.value.phase === 'error') {
        stopPolling()
      }
    }
  }, 600)

  return { state, progress, phaseLabel, startScan, startPolling, stopPolling, fetchStatus }
})
