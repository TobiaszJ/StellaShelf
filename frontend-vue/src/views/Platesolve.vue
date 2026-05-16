<script setup lang="ts">
import { usePlatesolveStore } from '@/stores/platesolve'

const platesolveStore = usePlatesolveStore()
const state = platesolveStore.state

async function startPlatesolve() {
  try {
    await platesolveStore.startPlatesolve()
  } catch (e: any) {
    alert('Fehler: ' + (e.response?.data?.detail || e.message))
  }
}

async function cancelPlatesolve() {
  try {
    await platesolveStore.cancelPlatesolve()
  } catch {
    // ignore
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h2>ASTAP Platesolving</h2>
      <p>Koordinaten für Frames ohne RA/Dec bestimmen</p>
    </div>

    <div class="card">
      <p style="margin-bottom: 16px; color: var(--text-muted);">
        ASTAP kann fehlende Koordinaten in FITS-Headern automatisch bestimmen.
        Die Berechnung läuft im Hintergrund — du kannst währenddessen weiterarbeiten.
      </p>

      <div class="platesolve-actions">
        <button class="btn" @click="startPlatesolve" :disabled="state.running">
          {{ state.running ? 'Platesolving läuft...' : 'Platesolving starten' }}
        </button>
        <button v-if="state.running" class="btn btn-danger" @click="cancelPlatesolve">
          Abbrechen
        </button>
      </div>
    </div>

    <div v-if="state.running || state.phase !== 'idle'" class="card">
      <h3>{{ state.phase === 'solving' ? 'Löse Frames...' : state.phase === 'done' ? 'Fertig' : state.phase === 'cancelled' ? 'Abgebrochen' : state.phase === 'error' ? 'Fehler' : '' }}</h3>
      <div class="bar-bg" style="margin: 12px 0;">
        <div class="bar-fill" :style="{ width: platesolveStore.progress + '%' }"></div>
      </div>
      <div class="stats-grid" style="margin-top: 12px;">
        <div class="stat-card">
          <div class="value">{{ state.total }}</div>
          <div class="label">Total</div>
        </div>
        <div class="stat-card">
          <div class="value" style="color: var(--accent2);">{{ state.solved }}</div>
          <div class="label">Gelöst</div>
        </div>
        <div class="stat-card">
          <div class="value" style="color: var(--danger);">{{ state.failed }}</div>
          <div class="label">Fehlgeschlagen</div>
        </div>
      </div>
      <p v-if="state.phase === 'done' || state.phase === 'cancelled'" style="margin-top: 12px; font-weight: 600;">
        {{ state.phase === 'cancelled' ? 'Abgebrochen' : `${state.solved} gelöst, ${state.failed} fehlgeschlagen` }}
      </p>
    </div>

    <div v-if="state.log && state.log.length" class="card">
      <h3>Log ({{ state.log.length }} Einträge)</h3>
      <div class="log-container">
        <div v-for="(entry, i) in state.log" :key="i" class="log-entry" :class="'log-' + entry.status">
          <span class="log-status">{{ entry.status === 'solved' ? '✓' : entry.status === 'failed' ? '✗' : entry.status === 'cancelled' ? '⬛' : '⚠' }}</span>
          <span class="log-frame">{{ entry.frame || '-' }}</span>
          <span class="log-detail">{{ entry.detail }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.platesolve-actions {
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
.log-solved { color: var(--accent2); }
.log-failed { color: var(--danger); }
.log-cancelled { color: var(--text-muted); }
.log-error { color: var(--danger); }
.log-status { width: 16px; text-align: center; flex-shrink: 0; }
.log-frame { color: var(--text); min-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.log-detail { color: var(--text-muted); }
</style>
