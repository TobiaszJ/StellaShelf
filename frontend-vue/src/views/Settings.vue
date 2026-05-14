<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useApiStore } from '@/stores/api'

const apiStore = useApiStore()
const settings = ref<Record<string, string>>({})
const loading = ref(true)
const saving = ref(false)
const saved = ref(false)

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
  } catch {
    // Settings table may not exist yet
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  saved.value = false
  try {
    const payload = SETTINGS_DEFINITIONS.map(def => ({
      key: def.key,
      value: settings.value[def.key] || '',
      description: def.description,
    }))
    await apiStore.post('/settings', payload)
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

    <div v-else class="card">
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

      <div class="setting-actions">
        <button class="btn" @click="save" :disabled="saving">
          {{ saving ? 'Speichern...' : 'Speichern' }}
        </button>
        <span v-if="saved" class="save-success">✓ Gespeichert</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
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
