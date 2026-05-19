<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useIdentifyStore } from '@/stores/identify'
import BackgroundTaskRunner from '@/components/BackgroundTaskRunner.vue'

const store = useIdentifyStore()
const { state } = storeToRefs(store)

function start() {
  store.startIdentify().catch((e: any) => {
    console.error('API error:', e.response?.data?.detail || e.message)
    alert('Ein Fehler ist aufgetreten. Bitte versuche es erneut.')
  })
}

function cancel() {
  store.cancelIdentify().catch(() => {})
}
</script>

<template>
  <BackgroundTaskRunner
    :key="'identify-'+state.phase"
    title="Objekt Identifikation"
    description="Deep-Sky-Objekte aus RA/Dec-Koordinaten bestimmen"
    extraDescription="Es wird das grösste Objekt aus dem OpenNGC-Katalog (NGC/IC/Messier/common name) im Bildfeld ausgewählt. Frames werden automatisch dem passenden Target zugeordnet."
    actionLabel="Identifikation starten"
    runningLabel="Identifikation läuft..."
    :running="state.running"
    :phase="state.phase"
    :total="state.total"
    :doneCount="state.identified"
    :failed="state.failed"
    :log="state.log"
    :onStart="start"
    :onCancel="cancel"
  />
</template>
