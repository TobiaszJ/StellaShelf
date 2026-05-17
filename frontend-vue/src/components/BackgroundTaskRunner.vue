<script setup lang="ts">
import { computed, useSlots } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps<{
  title: string
  description: string
  extraDescription?: string
  actionLabel: string
  runningLabel: string
  running: boolean
  phase: string
  total: number
  doneCount: number
  failed: number
  log: Array<{ frame: string; status: string; detail: string }>
  onStart: () => void
  onCancel: () => void
}>()

const progress = computed(() => {
  const done = props.doneCount + props.failed
  return props.total > 0 ? Math.round((done / props.total) * 100) : 0
})

const phaseTitle = computed(() => {
  switch (props.phase) {
    case 'solving':
    case 'analysing':
    case 'identifying':
    case 'scanning':
      return t('task.in_progress')
    case 'done':
      return t('task.done')
    case 'cancelled':
      return t('task.cancelled')
    case 'error':
      return t('task.error')
    default:
      return ''
  }
})

const showProgress = computed(() => props.running || props.phase !== 'idle')
</script>

<template>
  <div>
    <div class="page-header">
      <h2>{{ title }}</h2>
      <p>{{ description }}</p>
    </div>

    <div class="card">
      <p style="margin-bottom: 16px; color: var(--text-muted);">
        {{ t('task.description') }}
      </p>
      <p v-if="extraDescription" style="margin-bottom: 16px; color: var(--text-muted);">
        {{ extraDescription }}
      </p>

      <div class="task-actions">
        <button class="btn" :disabled="running" @click="onStart">
          {{ running ? runningLabel : actionLabel }}
        </button>
        <button v-if="running" class="btn btn-danger" @click="onCancel">
          {{ t('task.cancel') }}
        </button>
      </div>
    </div>

    <div v-if="showProgress" class="card">
      <h3>{{ phaseTitle }}</h3>
      <div class="bar-bg" style="margin: 12px 0;">
        <div class="bar-fill" :style="{ width: progress + '%' }"></div>
      </div>
      <div class="stats-grid" style="margin-top: 12px;">
        <div class="stat-card">
          <div class="value">{{ total }}</div>
          <div class="label">{{ t('task.total') }}</div>
        </div>
        <div class="stat-card">
          <div class="value" style="color: var(--accent2);">{{ doneCount }}</div>
          <div class="label">{{ t('task.successful') }}</div>
        </div>
        <div class="stat-card">
          <div class="value" style="color: var(--danger);">{{ failed }}</div>
          <div class="label">{{ t('task.failed') }}</div>
        </div>
      </div>
      <p v-if="phase === 'done' || phase === 'cancelled'" style="margin-top: 12px; font-weight: 600;">
        {{ phase === 'cancelled' ? t('task.cancelled') : `${doneCount} ${t('task.successful').toLowerCase()}, ${failed} ${t('task.failed').toLowerCase()}` }}
      </p>
    </div>

    <div v-if="log && log.length" class="card">
      <h3>{{ t('task.log_entries', { count: log.length }) }}</h3>
      <div class="log-container">
        <div v-for="(entry, i) in log" :key="i" class="log-entry" :class="'log-' + entry.status">
          <span class="log-status">{{ entry.status === 'solved' || entry.status === 'analysed' || entry.status === 'identified' ? '✓' : entry.status === 'failed' ? '✗' : entry.status === 'cancelled' ? '⬛' : '⚠' }}</span>
          <span class="log-frame">{{ entry.frame || '-' }}</span>
          <span class="log-detail">{{ entry.detail }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.task-actions {
  display: flex;
  gap: 8px;
}
.bar-bg {
  width: 100%;
  height: 24px;
  background: var(--surface2);
  border-radius: 12px;
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent), var(--accent2));
  border-radius: 12px;
  transition: width 0.3s ease;
}
.log-container {
  max-height: 300px;
  overflow-y: auto;
  font-family: monospace;
  font-size: 12px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 4px 0;
}
.log-entry {
  display: flex;
  gap: 8px;
  padding: 4px 12px;
  border-bottom: 1px solid var(--border);
}
.log-entry:last-child { border-bottom: none; }
.log-solved, .log-analysed, .log-identified { color: var(--accent2); }
.log-failed { color: var(--danger); }
.log-cancelled { color: var(--text-muted); }
.log-error { color: var(--danger); }
.log-status { width: 16px; text-align: center; flex-shrink: 0; }
.log-frame { color: var(--text); min-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.log-detail { color: var(--text-muted); }
</style>
