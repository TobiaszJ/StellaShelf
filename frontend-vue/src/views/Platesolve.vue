<script setup lang="ts">
import { usePlatesolveStore } from '@/stores/platesolve'
import BackgroundTaskRunner from '@/components/BackgroundTaskRunner.vue'

const store = usePlatesolveStore()
const st = store.state

function start() {
  store.startPlatesolve().catch((e: any) => {
    alert('Fehler: ' + (e.response?.data?.detail || e.message))
  })
}

function cancel() {
  store.cancelPlatesolve().catch(() => {})
}
</script>

<template>
  <BackgroundTaskRunner
    title="Platesolving"
    description="Koordinaten für Frames ohne RA/Dec bestimmen"
    actionLabel="Platesolving starten"
    runningLabel="Platesolving läuft..."
    :running="st.running"
    :phase="st.phase"
    :total="st.total"
    :doneCount="st.solved"
    :failed="st.failed"
    :log="st.log"
    :onStart="start"
    :onCancel="cancel"
  />
</template>
