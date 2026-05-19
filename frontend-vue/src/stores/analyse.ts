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
  const pollFailCount = ref(0)
  const BASE_INTERVAL = 500
  const MAX_INTERVAL = 16000

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
      pollFailCount.value = 0
    } catch {
      pollFailCount.value++
    }
  }

  function startPolling() {
    if (pollInterval.value) clearTimeout(pollInterval.value)
    fetchStatus()
    scheduleNext()
  }

  function scheduleNext() {
    const delay = Math.min(BASE_INTERVAL * Math.pow(2, pollFailCount.value), MAX_INTERVAL)
    pollInterval.value = window.setTimeout(() => {
      fetchStatus()
      scheduleNext()
    }, delay)
  }

  function stopPolling() {
    if (pollInterval.value) {
      clearTimeout(pollInterval.value)
      pollInterval.value = null
    }
    pollFailCount.value = 0
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