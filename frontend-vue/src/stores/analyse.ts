import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { useApiStore } from './api'
import { i18n } from '@/i18n'

export interface AnalyseState {
  running: boolean
  total: number
  analysed: number
  failed: number
  phase: string
  error: string | null
  cancelled: boolean
  log: Array<{ frame: string; status: string; detail: string }>
}

export const useAnalyseStore = defineStore('analyse', () => {
  const apiStore = useApiStore()

  const state = ref<AnalyseState>({
    running: false,
    total: 0,
    analysed: 0,
    failed: 0,
    phase: 'idle',
    error: null,
    cancelled: false,
    log: [],
  })
  const pollInterval = ref<number | null>(null)

  const progress = computed(() => {
    const done = state.value.analysed + state.value.failed
    return state.value.total > 0 ? Math.round((done / state.value.total) * 100) : 0
  })

  const phaseLabel = computed(() => {
    switch (state.value.phase) {
      case 'analysing': return i18n.global.t('phase.analysing')
      case 'done': return i18n.global.t('phase.analyse_done')
      case 'cancelled': return i18n.global.t('phase.analyse_cancelled')
      case 'error': return i18n.global.t('phase.analyse_error')
      default: return ''
    }
  })

  async function fetchStatus() {
    try {
      const data = await apiStore.fetch<AnalyseState>('/analyse/status')
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

  async function startAnalyse(force: boolean = false) {
    const params: Record<string, any> = {}
    if (force) params.force = 'true'
    const res = await apiStore.fetch<{ status: string }>('/analyse', params)
    state.value = {
      running: true,
      total: 0,
      analysed: 0,
      failed: 0,
      phase: 'analysing',
      error: null,
      cancelled: false,
      log: [],
    }
    startPolling()
    return res
  }

  async function cancelAnalyse() {
    await apiStore.post('/analyse/cancel', {})
  }

  watch(() => state.value.phase, (newPhase) => {
    if (['done', 'cancelled', 'error'].includes(newPhase)) {
      stopPolling()
    }
  })

  return { state, progress, phaseLabel, startAnalyse, cancelAnalyse, fetchStatus, startPolling, stopPolling }
})
