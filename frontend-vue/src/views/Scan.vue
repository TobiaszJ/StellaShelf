<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useScanStore } from '@/stores/scan'
import { useApiStore } from '@/stores/api'

const scanStore = useScanStore()
const apiStore = useApiStore()
const selectedPath = ref('')
const knownPaths = ref<{ label: string; value: string }[]>([])

// Cleanup state
const cleanupTab = ref<'scan' | 'cleanup'>('scan')
const cleanupPattern = ref('')
const cleanupField = ref<'filename' | 'filepath'>('filename')
const cleanupResults = ref<any[]>([])
const cleanupLoading = ref(false)
const cleanupTotal = ref(0)
const cleanupSelected = ref<Set<number>>(new Set())
const cleanupBusy = ref(false)
const cleanupConfirming = ref(false)
const cleanupOrphansBusy = ref(false)
const cleanupOrphanResult = ref<string | null>(null)

onMounted(async () => {
  try {
    const settings = await apiStore.fetch<{ key: string; value: string }[]>('/settings')
    const scanPathsSetting = settings.find((s: any) => s.key === 'scan_paths')
    if (scanPathsSetting?.value) {
      const paths = scanPathsSetting.value.split(',').map((p: string) => p.trim()).filter(Boolean)
      if (paths.length > 0) {
        knownPaths.value = paths.map((p: string) => ({ label: p, value: p }))
        selectedPath.value = paths[0]
        return
      }
    }
  } catch {
    // Settings table may not exist yet
  }
  knownPaths.value = []
  selectedPath.value = ''
})

const btnDisabled = computed(() => scanStore.state.running)

async function startScan() {
  if (!selectedPath.value.trim()) {
    alert('Bitte einen Pfad eingeben')
    return
  }
  try {
    await scanStore.startScan(selectedPath.value)
  } catch (e: any) {
    alert(e.response?.data?.detail || 'Fehler beim Starten des Scans')
  }
}

// Cleanup functions
async function searchFrames() {
  if (!cleanupPattern.value.trim()) return
  cleanupLoading.value = true
  cleanupResults.value = []
  cleanupSelected.value = new Set()
  cleanupTotal.value = 0
  try {
    const params: Record<string, any> = {
      page: 1,
      page_size: 10000,
      sort_by: 'filename',
      sort_order: 'asc',
    }
    // Send raw user input — backend handles * _ % escaping
    params[cleanupField.value] = cleanupPattern.value
    const res = await apiStore.fetch<any>('/frames', params)
    cleanupResults.value = res.items || []
    cleanupTotal.value = res.total || 0
  } catch (e: any) {
    alert('Fehler bei der Suche: ' + (e.response?.data?.detail || e.message))
  } finally {
    cleanupLoading.value = false
  }
}

function toggleSelectAll() {
  if (cleanupSelected.value.size === cleanupResults.value.length) {
    cleanupSelected.value = new Set()
  } else {
    cleanupSelected.value = new Set(cleanupResults.value.map((f: any) => f.id))
  }
}

function toggleSelect(id: number) {
  const s = new Set(cleanupSelected.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  cleanupSelected.value = s
}

function keydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && cleanupTab.value === 'cleanup') searchFrames()
}

async function deleteSelected() {
  const ids = Array.from(cleanupSelected.value)
  if (!ids.length) return
  cleanupBusy.value = true
  try {
    const res = await apiStore.post<any>('/frames/delete', { frame_ids: ids })
    alert(`${res.deleted} Frames gelöscht.`)
    cleanupConfirming.value = false
    cleanupResults.value = cleanupResults.value.filter((f: any) => !cleanupSelected.value.has(f.id))
    cleanupSelected.value = new Set()
    cleanupTotal.value -= res.deleted
  } catch (e: any) {
    alert('Fehler: ' + (e.response?.data?.detail || e.message))
  } finally {
    cleanupBusy.value = false
  }
}

async function cleanupOrphans() {
  cleanupOrphansBusy.value = true
  cleanupOrphanResult.value = null
  try {
    const res = await apiStore.post<any>('/db/cleanup-orphans', {})
    cleanupOrphanResult.value = `${res.sessions} Sessions, ${res.targets} Targets, ${res.cameras} Kameras, ${res.telescopes} Teleskope entfernt`
  } catch (e: any) {
    alert('Fehler: ' + (e.response?.data?.detail || e.message))
  } finally {
    cleanupOrphansBusy.value = false
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h2>Datenverwaltung</h2>
      <p>FITS-Daten scannen und bereinigen</p>
    </div>

    <div class="tabs">
      <button :class="['tab', { active: cleanupTab === 'scan' }]" @click="cleanupTab = 'scan'">Scan</button>
      <button :class="['tab', { active: cleanupTab === 'cleanup' }]" @click="cleanupTab = 'cleanup'">Bereinigung</button>
    </div>

    <!-- Scan Tab -->
    <template v-if="cleanupTab === 'scan'">
      <div class="card">
        <h3>Scan-Pfad auswählen</h3>
        <div class="scan-path-selector">
          <div class="filter-group">
            <label>Verzeichnis</label>
            <select v-model="selectedPath">
              <option v-for="p in knownPaths" :key="p.value" :value="p.value">{{ p.label }}</option>
            </select>
          </div>
          <div class="filter-group">
            <label>Oder benutzerdefiniert</label>
            <input type="text" v-model="selectedPath" placeholder="/pfad/zu/fits/..." />
          </div>
          <div class="scan-actions">
            <button class="btn btn-success" :disabled="btnDisabled" @click="startScan">
              Scan starten
            </button>
            <button v-if="scanStore.state.running" class="btn btn-danger" @click="scanStore.cancelScan()">
              Abbrechen
            </button>
          </div>
        </div>
      </div>

      <div v-if="scanStore.state.phase !== 'idle'" class="card scan-progress-large">
        <h3>{{ scanStore.phaseLabel }}</h3>
        <div class="bar-bg">
          <div class="bar-fill" :style="{ width: scanStore.progress + '%' }"></div>
        </div>
        <div class="scan-stats-row">
          <div class="scan-stat">
            <div class="num">{{ scanStore.state.total.toLocaleString() }}</div>
            <div class="lbl">Total</div>
          </div>
          <div class="scan-stat">
            <div class="num">{{ scanStore.state.processed.toLocaleString() }}</div>
            <div class="lbl">Gescannt</div>
          </div>
          <div class="scan-stat">
            <div class="num">{{ scanStore.state.imported.toLocaleString() }}</div>
            <div class="lbl">Importiert</div>
          </div>
          <div class="scan-stat">
            <div class="num">{{ scanStore.state.skipped.toLocaleString() }}</div>
            <div class="lbl">Übersprungen</div>
          </div>
        </div>
        <div class="current-file">{{ scanStore.state.current_file }}</div>
      </div>

      <div class="card">
        <h3>Info</h3>
        <p>Der Scan liest FITS-Header aus und importiert Metadaten in die Datenbank.
           Bestehende Dateien werden übersprungen. Der Scan läuft im Hintergrund —
           du kannst währenddessen weiterarbeiten.</p>
      </div>
    </template>

    <!-- Cleanup Tab -->
    <template v-if="cleanupTab === 'cleanup'">
      <div class="card">
        <h3>Frames suchen und löschen</h3>
        <p style="color: var(--text-muted); font-size: 13px; margin-bottom: 12px;">
          Suche nach Frames anhand von Dateiname oder Pfad. Verwende * als Platzhalter.
        </p>
        <div class="cleanup-filters">
          <div class="filter-group">
            <label>Suchfeld</label>
            <select v-model="cleanupField">
              <option value="filename">Dateiname</option>
              <option value="filepath">Pfad</option>
            </select>
          </div>
          <div class="filter-group" style="flex: 1;">
            <label>Suchmuster</label>
            <input
              type="text"
              v-model="cleanupPattern"
              placeholder="z.B. *bad* oder *c_*"
              @keydown="keydown"
            />
          </div>
          <div class="filter-group" style="align-self: flex-end;">
            <button class="btn" @click="searchFrames" :disabled="!cleanupPattern.trim() || cleanupLoading">
              {{ cleanupLoading ? 'Suche...' : 'Suchen' }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="cleanupResults.length" class="card">
        <div class="cleanup-result-header">
          <h3>{{ cleanupTotal }} Frames gefunden</h3>
          <div class="cleanup-actions">
            <span style="font-size: 13px; color: var(--text-muted);">
              {{ cleanupSelected.size }} ausgewählt
            </span>
            <button
              v-if="!cleanupConfirming"
              class="btn btn-danger btn-sm"
              :disabled="!cleanupSelected.size"
              @click="cleanupConfirming = true"
            >
              Ausgewählte löschen
            </button>
            <template v-else>
              <span style="font-size: 13px; color: var(--danger);">
                <strong>{{ cleanupSelected.size }} Frames wirklich löschen?</strong>
              </span>
              <button class="btn btn-danger btn-sm" @click="deleteSelected" :disabled="cleanupBusy">
                {{ cleanupBusy ? 'Lösche...' : 'Ja, löschen' }}
              </button>
              <button class="btn btn-sm btn-ghost" @click="cleanupConfirming = false" :disabled="cleanupBusy">
                Abbrechen
              </button>
            </template>
          </div>
        </div>
        <div class="cleanup-table-wrapper">
          <div class="table-responsive">
            <table class="data-table compact">
              <thead>
                <tr>
                  <th style="width: 32px;">
                    <input
                      type="checkbox"
                      :checked="cleanupSelected.size === cleanupResults.length"
                      :indeterminate="cleanupSelected.size > 0 && cleanupSelected.size < cleanupResults.length"
                      @change="toggleSelectAll"
                    />
                  </th>
                  <th>Dateiname</th>
                  <th>Typ</th>
                  <th>Filter</th>
                  <th>Belichtung</th>
                  <th>Pfad</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="f in cleanupResults" :key="f.id">
                  <td>
                    <input
                      type="checkbox"
                      :checked="cleanupSelected.has(f.id)"
                      @change="toggleSelect(f.id)"
                    />
                  </td>
                  <td class="cell-monospace">{{ f.filename }}</td>
                  <td><span class="badge badge-light">{{ f.frame_type }}</span></td>
                  <td>{{ f.filter_name || '-' }}</td>
                  <td>{{ f.exposure ? f.exposure + 's' : '-' }}</td>
                  <td class="cell-monospace cell-path">{{ f.filepath }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div v-else-if="cleanupLoading" class="loading">Suche nach Frames...</div>
      <div v-else-if="cleanupPattern && !cleanupLoading" class="card">
        <p class="empty">Keine Frames gefunden.</p>
      </div>

      <div class="card">
        <h3>Verwaiste Einträge bereinigen</h3>
        <p style="color: var(--text-muted); font-size: 13px; margin-bottom: 12px;">
          Entfernt Sessions ohne Frames, Targets ohne Sessions sowie nicht verwendete Kameras und Teleskope.
          Wird automatisch nach jedem Löschvorgang ausgeführt.
        </p>
        <div class="orphan-actions">
          <button class="btn btn-sm" @click="cleanupOrphans" :disabled="cleanupOrphansBusy">
            {{ cleanupOrphansBusy ? 'Bereinige...' : 'Verwaiste Einträge entfernen' }}
          </button>
          <span v-if="cleanupOrphanResult" class="orphan-success">{{ cleanupOrphanResult }}</span>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 16px;
}
.tab {
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text-muted);
  padding: 8px 16px;
  border-radius: 6px 6px 0 0;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
}
.tab.active {
  color: var(--text);
  border-bottom-color: var(--accent);
}
.scan-actions {
  display: flex;
  gap: 8px;
  align-self: flex-end;
}
.cleanup-filters {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}
.cleanup-result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 8px;
}
.cleanup-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.cleanup-table-wrapper {
  max-height: 500px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: 6px;
}
.cleanup-table-wrapper .data-table th {
  position: sticky;
  top: 0;
  background: var(--surface);
  z-index: 1;
}
.cell-monospace {
  font-family: monospace;
  font-size: 12px;
  max-width: 250px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cell-path {
  color: var(--text-muted);
}
.orphan-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.orphan-success {
  font-size: 13px;
  color: var(--accent2);
  font-weight: 600;
}
</style>
