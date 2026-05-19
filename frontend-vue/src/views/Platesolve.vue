<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { usePlatesolveStore } from '@/stores/platesolve'
import BackgroundTaskRunner from '@/components/BackgroundTaskRunner.vue'

const store = usePlatesolveStore()
const { state } = storeToRefs(store)

function start() {
  store.startPlatesolve().catch((e: any) => {
    console.error('API error:', e.response?.data?.detail || e.message)
    alert('Ein Fehler ist aufgetreten. Bitte versuche es erneut.')
  })
}

function cancel() {
  store.cancelPlatesolve().catch(() => {})
}
</script>

<template>
  <BackgroundTaskRunner
    :key="'platesolve-'+state.phase"
    title="Platesolving"
    description="Koordinaten für Frames ohne RA/Dec bestimmen"
    actionLabel="Platesolving starten"
    runningLabel="Platesolving läuft..."
    :running="state.running"
    :phase="state.phase"
    :total="state.total"
    :doneCount="state.solved"
    :failed="state.failed"
    :log="state.log"
    :onStart="start"
    :onCancel="cancel"
  />
</template>
