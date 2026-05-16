import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { useApiStore } from './api'
import type { ScanState } from './api'

export const useScanStore = defineStore('scan', () => {
  const apiStore = useApiStore()

  const state = ref<ScanState>({
    running: false,
    total: 0,
    processed: 0,
    imported: 0,
    skipped: 0,
    calibration_files: 0,
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
      case 'scanning': return 'Scanne und importiere...'
      case 'done': return 'Scan abgeschlossen'
      case 'cancelled': return 'Scan abgebrochen'
      case 'error': return 'Fehler beim Scan'
      default: return ''
    }
  })

  async function fetchStatus() {
    try {
      const data = await apiStore.fetch<ScanState>('/scan/status')
      state.value = data
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
    const res = await apiStore.post<{ status: string; path: string }>('/scan', { path, recursive: true })
    state.value = {
      running: true,
      total: 0,
      processed: 0,
      imported: 0,
      skipped: 0,
      calibration_files: 0,
      current_file: 'Initialisiere...',
      phase: 'scanning',
      error: null,
    }
    startPolling()
    return res
  }

  async function cancelScan() {
    await apiStore.post('/scan/cancel', {})
  }

  // Watch for completion/error to stop polling
  watch(() => state.value.phase, (newPhase) => {
    if (newPhase === 'done' || newPhase === 'error' || newPhase === 'cancelled') {
      stopPolling()
    }
  })

  return { state, progress, phaseLabel, startScan, cancelScan, startPolling, stopPolling, fetchStatus }
})