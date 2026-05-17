<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useAnalyseStore } from '@/stores/analyse'
import BackgroundTaskRunner from '@/components/BackgroundTaskRunner.vue'

const store = useAnalyseStore()
const { state, progress, phaseLabel } = storeToRefs(store)

function start() {
  store.startAnalyse().catch((e: any) => {
    alert('Fehler: ' + (e.response?.data?.detail || e.message))
  })
}

function cancel() {
  store.cancelAnalyse().catch(() => {})
}
</script>

<template>
  <BackgroundTaskRunner
    :key="'analyse-'+state.phase"
    title="Frame Qualitätsanalyse"
    description="HFD und Sternanzahl für Light-Frames mit ASTAP ermitteln"
    extraDescription="ASTAP analysiert alle Light-Frames ohne bisherige HFD-Messung."
    actionLabel="Analyse starten"
    runningLabel="Analyse läuft..."
    :running="state.running"
    :phase="state.phase"
    :total="state.total"
    :doneCount="state.analysed"
    :failed="state.failed"
    :log="state.log"
    :onStart="start"
    :onCancel="cancel"
  />
</template>
