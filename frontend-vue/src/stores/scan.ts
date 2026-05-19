import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { useApiStore } from './api'
import type { ScanState } from './api'
import { i18n } from '@/i18n'

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
  const pollFailCount = ref(0)
  const BASE_INTERVAL = 500
  const MAX_INTERVAL = 16000

  const progress = computed(() =>
    state.value.total > 0 ? Math.round((state.value.processed / state.value.total) * 100) : 0
  )

  const phaseLabel = computed(() => {
    switch (state.value.phase) {
      case 'scanning': return i18n.global.t('phase.scanning')
      case 'done': return i18n.global.t('phase.scan_done')
      case 'cancelled': return i18n.global.t('phase.scan_cancelled')
      case 'error': return i18n.global.t('phase.scan_error')
      default: return ''
    }
  })

  async function fetchStatus() {
    try {
      const data = await apiStore.fetch<ScanState>('/scan/status')
      state.value = data
      pollFailCount.value = 0
    } catch {
      pollFailCount.value++
    }
  }

  function startPolling() {
    if (pollInterval.value) clearInterval(pollInterval.value)
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

  watch(() => state.value.phase, (newPhase) => {
    if (newPhase === 'done' || newPhase === 'error' || newPhase === 'cancelled') {
      stopPolling()
    }
  })

  return { state, progress, phaseLabel, startScan, cancelScan, startPolling, stopPolling, fetchStatus }
})