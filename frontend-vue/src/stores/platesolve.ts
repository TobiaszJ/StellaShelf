import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { useApiStore } from './api'

export interface PlatesolveState {
  running: boolean
  total: number
  solved: number
  failed: number
  phase: string
  error: string | null
  cancelled: boolean
  log: Array<{ frame: string; status: string; detail: string }>
}

export const usePlatesolveStore = defineStore('platesolve', () => {
  const apiStore = useApiStore()

  const state = ref<PlatesolveState>({
    running: false,
    total: 0,
    solved: 0,
    failed: 0,
    phase: 'idle',
    error: null,
    cancelled: false,
    log: [],
  })
  const pollInterval = ref<number | null>(null)

  const progress = computed(() => {
    const done = state.value.solved + state.value.failed
    return state.value.total > 0 ? Math.round((done / state.value.total) * 100) : 0
  })

  const phaseLabel = computed(() => {
    switch (state.value.phase) {
      case 'solving': return 'Platesolving...'
      case 'done': return 'Platesolving abgeschlossen'
      case 'cancelled': return 'Platesolving abgebrochen'
      case 'error': return 'Fehler beim Platesolving'
      default: return ''
    }
  })

  async function fetchStatus() {
    try {
      const data = await apiStore.fetch<PlatesolveState>('/platesolve/status')
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

  async function startPlatesolve() {
    const res = await apiStore.post<{ status: string }>('/platesolve', {})
    state.value = {
      running: true,
      total: 0,
      solved: 0,
      failed: 0,
      phase: 'solving',
      error: null,
      cancelled: false,
      log: [],
    }
    startPolling()
    return res
  }

  async function cancelPlatesolve() {
    await apiStore.post('/platesolve/cancel', {})
  }

  watch(() => state.value.phase, (newPhase) => {
    if (['done', 'cancelled', 'error'].includes(newPhase)) {
      stopPolling()
    }
  })

  return { state, progress, phaseLabel, startPlatesolve, cancelPlatesolve, fetchStatus, startPolling, stopPolling }
})
