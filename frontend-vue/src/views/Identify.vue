<script setup lang="ts">
import { useIdentifyStore } from '@/stores/identify'
import BackgroundTaskRunner from '@/components/BackgroundTaskRunner.vue'

const store = useIdentifyStore()
const st = store.state

function start() {
  store.startIdentify().catch((e: any) => {
    alert('Fehler: ' + (e.response?.data?.detail || e.message))
  })
}

function cancel() {
  store.cancelIdentify().catch(() => {})
}
</script>

<template>
  <BackgroundTaskRunner
    title="Objekt Identifikation"
    description="Deep-Sky-Objekte aus RA/Dec-Koordinaten bestimmen"
    extraDescription="Es wird das grösste Objekt aus dem OpenNGC-Katalog (NGC/IC/Messier/common name) im Bildfeld ausgewählt. Frames werden automatisch dem passenden Target zugeordnet."
    actionLabel="Identifikation starten"
    runningLabel="Identifikation läuft..."
    :running="st.running"
    :phase="st.phase"
    :total="st.total"
    :doneCount="st.identified"
    :failed="st.failed"
    :log="st.log"
    :onStart="start"
    :onCancel="cancel"
  />
</template>
