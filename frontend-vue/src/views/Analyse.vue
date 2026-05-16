<script setup lang="ts">
import { useAnalyseStore } from '@/stores/analyse'

const analyseStore = useAnalyseStore()
const state = analyseStore.state

async function startAnalyse() {
  try {
    await analyseStore.startAnalyse()
  } catch (e: any) {
    alert('Fehler: ' + (e.response?.data?.detail || e.message))
  }
}

async function cancelAnalyse() {
  try {
    await analyseStore.cancelAnalyse()
  } catch {
    // ignore
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h2>Frame Qualitätsanalyse</h2>
      <p>HFD und Sternanzahl für Light-Frames mit ASTAP ermitteln</p>
    </div>

    <div class="card">
      <p style="margin-bottom: 16px; color: var(--text-muted);">
        ASTAP analysiert alle Light-Frames ohne bisherige HFD-Messung.
        Die Analyse läuft im Hintergrund — du kannst währenddessen weiterarbeiten.
      </p>

      <div class="analyse-actions">
        <button class="btn" @click="startAnalyse" :disabled="state.running">
          {{ state.running ? 'Analyse läuft...' : 'Analyse starten' }}
        </button>
        <button v-if="state.running" class="btn btn-danger" @click="cancelAnalyse">
          Abbrechen
        </button>
      </div>
    </div>

    <div v-if="state.running || state.phase !== 'idle'" class="card">
      <h3>{{ state.phase === 'analysing' ? 'Analysiere Frames...' : state.phase === 'done' ? 'Fertig' : state.phase === 'cancelled' ? 'Abgebrochen' : state.phase === 'error' ? 'Fehler' : '' }}</h3>
      <div class="bar-bg" style="margin: 12px 0;">
        <div class="bar-fill" :style="{ width: analyseStore.progress + '%' }"></div>
      </div>
      <div class="stats-grid" style="margin-top: 12px;">
        <div class="stat-card">
          <div class="value">{{ state.total }}</div>
          <div class="label">Total</div>
        </div>
        <div class="stat-card">
          <div class="value" style="color: var(--accent2);">{{ state.analysed }}</div>
          <div class="label">Analysiert</div>
        </div>
        <div class="stat-card">
          <div class="value" style="color: var(--danger);">{{ state.failed }}</div>
          <div class="label">Fehlgeschlagen</div>
        </div>
      </div>
      <p v-if="state.phase === 'done' || state.phase === 'cancelled'" style="margin-top: 12px; font-weight: 600;">
        {{ state.phase === 'cancelled' ? 'Abgebrochen' : `${state.analysed} analysiert, ${state.failed} fehlgeschlagen` }}
      </p>
    </div>

    <div v-if="state.log && state.log.length" class="card">
      <h3>Log ({{ state.log.length }} Einträge)</h3>
      <div class="log-container">
        <div v-for="(entry, i) in state.log" :key="i" class="log-entry" :class="'log-' + entry.status">
          <span class="log-status">{{ entry.status === 'analysed' ? '✓' : entry.status === 'failed' ? '✗' : entry.status === 'cancelled' ? '⬛' : '⚠' }}</span>
          <span class="log-frame">{{ entry.frame || '-' }}</span>
          <span class="log-detail">{{ entry.detail }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.analyse-actions {
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
  background: linear-gradient(90deg, var(--accent2), var(--accent));
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
.log-analysed { color: var(--accent2); }
.log-failed { color: var(--danger); }
.log-cancelled { color: var(--text-muted); }
.log-error { color: var(--danger); }
.log-status { width: 16px; text-align: center; flex-shrink: 0; }
.log-frame { color: var(--text); min-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.log-detail { color: var(--text-muted); }
</style>
