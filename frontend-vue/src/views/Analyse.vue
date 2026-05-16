<script setup lang="ts">
import { useAnalyseStore } from '@/stores/analyse'
import BackgroundTaskRunner from '@/components/BackgroundTaskRunner.vue'

const store = useAnalyseStore()
const st = store.state

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
    title="Frame Qualitätsanalyse"
    description="HFD und Sternanzahl für Light-Frames mit ASTAP ermitteln"
    extraDescription="ASTAP analysiert alle Light-Frames ohne bisherige HFD-Messung."
    actionLabel="Analyse starten"
    runningLabel="Analyse läuft..."
    :running="st.running"
    :phase="st.phase"
    :total="st.total"
    :doneCount="st.analysed"
    :failed="st.failed"
    :log="st.log"
    :onStart="start"
    :onCancel="cancel"
  />
</template>
