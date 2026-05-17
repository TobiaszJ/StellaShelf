<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { usePlatesolveStore } from '@/stores/platesolve'
import BackgroundTaskRunner from '@/components/BackgroundTaskRunner.vue'

const { t } = useI18n()
const store = usePlatesolveStore()
const st = store.state

function start() {
  store.startPlatesolve().catch((e: any) => {
    alert(t('error.generic', { message: e.response?.data?.detail || e.message }))
  })
}

function cancel() {
  store.cancelPlatesolve().catch(() => {})
}
</script>

<template>
  <BackgroundTaskRunner
    :title="t('task.platesolve_title')"
    :description="t('task.platesolve_desc')"
    :actionLabel="t('task.start_platesolve')"
    :runningLabel="t('task.running_platesolve')"
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
