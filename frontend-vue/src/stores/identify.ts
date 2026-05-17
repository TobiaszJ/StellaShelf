import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { useApiStore } from './api'
import { i18n } from '@/i18n'

export interface IdentifyState {
  running: boolean
  total: number
  identified: number
  failed: number
  phase: string
  error: string | null
  cancelled: boolean
  log: Array<{ frame: string; status: string; detail: string }>
}

export const useIdentifyStore = defineStore('identify', () => {
  const apiStore = useApiStore()

  const state = ref<IdentifyState>({
    running: false,
    total: 0,
    identified: 0,
    failed: 0,
    phase: 'idle',
    error: null,
    cancelled: false,
    log: [],
  })
  const pollInterval = ref<number | null>(null)

  const progress = computed(() => {
    const done = state.value.identified + state.value.failed
    return state.value.total > 0 ? Math.round((done / state.value.total) * 100) : 0
  })

  const phaseLabel = computed(() => {
    switch (state.value.phase) {
      case 'identifying': return i18n.global.t('phase.identifying')
      case 'done': return i18n.global.t('phase.identify_done')
      case 'cancelled': return i18n.global.t('phase.identify_cancelled')
      case 'error': return i18n.global.t('phase.identify_error')
      default: return ''
    }
  })

  async function fetchStatus() {
    try {
      const data = await apiStore.fetch<IdentifyState>('/identify/status')
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

  async function startIdentify() {
    const res = await apiStore.post<{ status: string }>('/identify', {})
    state.value = {
      running: true,
      total: 0,
      identified: 0,
      failed: 0,
      phase: 'identifying',
      error: null,
      cancelled: false,
      log: [],
    }
    startPolling()
    return res
  }

  async function cancelIdentify() {
    await apiStore.post('/identify/cancel', {})
  }

  watch(() => state.value.phase, (newPhase) => {
    if (['done', 'cancelled', 'error'].includes(newPhase)) {
      stopPolling()
    }
  })

  return { state, progress, phaseLabel, startIdentify, cancelIdentify, fetchStatus, startPolling, stopPolling }
})
