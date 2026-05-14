<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useApiStore, type Camera, type Telescope } from '@/stores/api'

const apiStore = useApiStore()
const settings = ref<Record<string, string>>({})
const loading = ref(true)
const saving = ref(false)
const saved = ref(false)
const activeTab = ref('general')

const cameras = ref<Camera[]>([])
const telescopes = ref<Telescope[]>([])

const SETTINGS_DEFINITIONS = [
  { key: 'scan_paths', label: 'Scan-Verzeichnisse', description: 'Komma-getrennte Liste von Pfaden', type: 'text' },
  { key: 'astap_binary', label: 'ASTAP Binary Pfad', description: 'Pfad zur ASTAP ausführbaren Datei', type: 'text' },
  { key: 'theme', label: 'Theme', description: 'light / dark / system', type: 'select', options: ['light', 'dark', 'system'] },
]

async function load() {
  loading.value = true
  try {
    const res = await apiStore.fetch<any[]>('/settings')
    for (const s of res) {
      settings.value[s.key] = s.value || ''
    }
    cameras.value = await apiStore.fetch<Camera[]>('/cameras')
    telescopes.value = await apiStore.fetch<Telescope[]>('/telescopes')
  } catch {
    // Settings table may not exist yet
  } finally {
    loading.value = false
  }
}

function buildPayload() {
  const payload: { key: string; value: string; description: string }[] = []
  for (const def of SETTINGS_DEFINITIONS) {
    payload.push({ key: def.key, value: settings.value[def.key] || '', description: def.description })
  }
  // Camera overrides
  for (const c of cameras.value) {
    const overrideVal = settings.value[`camera_${c.id}_shortname`]
    if (overrideVal && overrideVal !== (c.short_name || '')) {
      payload.push({ key: `camera_${c.id}_shortname`, value: overrideVal, description: `Override für ${c.name}` })
    }
  }
  return payload
}

async function save() {
  saving.value = true
  saved.value = false
  try {
    await apiStore.post('/settings', buildPayload())
    saved.value = true
    setTimeout(() => { saved.value = false }, 2000)
  } catch (e: any) {
    alert('Fehler beim Speichern: ' + (e.message || 'Unbekannter Fehler'))
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="page-header">
      <h2>Einstellungen</h2>
      <p>Konfiguriere Pfade, Equipment und Verhalten</p>
    </div>

    <div v-if="loading" class="loading">Lade Einstellungen...</div>

    <template v-else>
      <div class="tabs">
        <button :class="['tab', { active: activeTab === 'general' }]" @click="activeTab = 'general'">Allgemein</button>
        <button :class="['tab', { active: activeTab === 'equipment' }]" @click="activeTab = 'equipment'">Equipment-Namen</button>
      </div>

      <!-- General Settings -->
      <div v-if="activeTab === 'general'" class="card">
        <div class="settings-list">
          <div v-for="def in SETTINGS_DEFINITIONS" :key="def.key" class="setting-item">
            <label :for="def.key">{{ def.label }}</label>
            <p class="setting-desc">{{ def.description }}</p>
            <select v-if="def.type === 'select'" :id="def.key" v-model="settings[def.key]" class="setting-input">
              <option v-for="opt in def.options" :key="opt" :value="opt">{{ opt }}</option>
            </select>
            <input v-else :id="def.key" v-model="settings[def.key]" type="text" class="setting-input" />
          </div>
        </div>
      </div>

      <!-- Equipment Overrides -->
      <div v-if="activeTab === 'equipment'" class="card">
        <h3>Kamera-Namen überschreiben</h3>
        <p style="color: var(--text-muted); font-size: 13px; margin-bottom: 16px;">
          Ändere die angezeigten Namen deiner Kameras (z.B. "ZWO ASI294MM Pro" → "ASI294MM")
        </p>
        <table class="data-table" v-if="cameras.length">
          <thead><tr><th>Original-Name</th><th>Angezeigter Name</th></tr></thead>
          <tbody>
            <tr v-for="c in cameras" :key="c.id">
              <td style="font-size: 12px; color: var(--text-muted);">{{ c.name }}</td>
              <td>
                <input
                  v-model="settings[`camera_${c.id}_shortname`]"
                  :placeholder="c.short_name || c.name"
                  class="override-input"
                />
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else class="empty">Keine Kameras gefunden.</p>

        <h3 style="margin-top: 24px;">Teleskop-Namen überschreiben</h3>
        <table class="data-table" v-if="telescopes.length">
          <thead><tr><th>Original-Name</th><th>Angezeigter Name</th></tr></thead>
          <tbody>
            <tr v-for="t in telescopes" :key="t.id">
              <td style="font-size: 12px; color: var(--text-muted);">{{ t.name }}</td>
              <td>
                <input
                  v-model="settings[`telescope_${t.id}_shortname`]"
                  :placeholder="t.short_name || t.name"
                  class="override-input"
                />
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else class="empty">Keine Teleskope gefunden.</p>
      </div>

      <div class="setting-actions">
        <button class="btn" @click="save" :disabled="saving">
          {{ saving ? 'Speichern...' : 'Speichern' }}
        </button>
        <span v-if="saved" class="save-success">✓ Gespeichert</span>
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
.settings-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.setting-item label {
  display: block;
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 2px;
}
.setting-desc {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 6px;
}
.setting-input {
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
  width: 100%;
  max-width: 400px;
}
.setting-input:focus {
  outline: none;
  border-color: var(--accent);
}
.override-input {
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 13px;
  width: 100%;
  max-width: 300px;
}
.override-input:focus { outline: none; border-color: var(--accent); }
.setting-actions {
  margin-top: 24px;
  display: flex;
  align-items: center;
  gap: 12px;
}
.save-success {
  color: var(--accent2);
  font-size: 13px;
  font-weight: 600;
}
</style>
