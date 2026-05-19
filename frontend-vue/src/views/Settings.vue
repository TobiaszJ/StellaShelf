<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useApiStore, type Camera, type Telescope } from '@/stores/api'
import { useThemeStore } from '@/stores/theme'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const apiStore = useApiStore()
const themeStore = useThemeStore()
const settings = ref<Record<string, string>>({})
const loading = ref(true)
const saving = ref(false)
const saved = ref(false)
const activeTab = ref('general')
const confirmingReset = ref(false)
const resetBusy = ref(false)

const cameras = ref<Camera[]>([])
const telescopes = ref<Telescope[]>([])

const settingsDefs = computed(() => [
  { key: 'scan_paths', label: t('settings.setting_scan_paths'), description: t('settings.setting_scan_paths_desc'), type: 'text', placeholder: 'z.B. /mnt/data/Astro/astro,/home/user/astro' },
  { key: 'astap_binary', label: t('settings.setting_astap_binary'), description: t('settings.setting_astap_binary_desc'), type: 'text', placeholder: 'z.B. /usr/bin/astap' },
])

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
  } finally {
    loading.value = false
  }
}

function buildPayload() {
  const payload: { key: string; value: string; description: string }[] = []
  for (const def of settingsDefs.value) {
    payload.push({ key: def.key, value: settings.value[def.key] || '', description: def.description })
  }
  for (const c of cameras.value) {
    const overrideVal = settings.value[`camera_${c.id}_shortname`]
    if (overrideVal && overrideVal !== (c.short_name || '')) {
      payload.push({ key: `camera_${c.id}_shortname`, value: overrideVal, description: t('settings.override_cameras_title') + ': ' + c.name })
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
      console.error('API error:', e.message || t('error.generic', { message: 'Unbekannter Fehler' }))
      alert(t('error.generic'))
  } finally {
    saving.value = false
  }
}

async function resetDb() {
  resetBusy.value = true
  try {
    await apiStore.post('/db/reset', { confirm: true })
    confirmingReset.value = false
    alert(t('settings.danger_reset_title') + ' — ' + t('settings.danger_reset_desc'))
    window.location.reload()
  } catch (e: any) {
      console.error('API error:', e.response?.data?.detail || e.message)
      alert(t('error.generic'))
  } finally {
    resetBusy.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="page-header">
      <h2>{{ $t('settings.title') }}</h2>
      <p>{{ $t('settings.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ $t('settings.loading') }}</div>

    <template v-else>
      <div class="tabs">
        <button :class="['tab', { active: activeTab === 'general' }]" @click="activeTab = 'general'">{{ $t('settings.tab_general') }}</button>
        <button :class="['tab', { active: activeTab === 'equipment' }]" @click="activeTab = 'equipment'">{{ $t('settings.tab_equipment') }}</button>
        <button :class="['tab', 'tab-danger', { active: activeTab === 'danger' }]" @click="activeTab = 'danger'">{{ $t('settings.tab_danger') }}</button>
      </div>

      <div v-if="activeTab === 'general'" class="card">
        <div class="settings-list">
          <div v-for="def in settingsDefs" :key="def.key" class="setting-item">
            <label :for="def.key">{{ def.label }}</label>
            <p class="setting-desc">{{ def.description }}</p>
            <input :id="def.key" v-model="settings[def.key]" type="text" class="setting-input" :placeholder="def.placeholder || ''" />
          </div>
          <div class="setting-item">
            <label>{{ $t('settings.setting_theme') }}</label>
            <p class="setting-desc">{{ $t('settings.setting_theme_desc') }}</p>
            <select class="setting-input" :value="themeStore.theme" @change="themeStore.setTheme(($event.target as HTMLSelectElement).value as any)">
              <option value="dark">{{ $t('nav.theme_dark') }}</option>
              <option value="light">{{ $t('nav.theme_light') }}</option>
              <option value="system">System</option>
            </select>
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'equipment'" class="card">
        <h3>{{ $t('settings.override_cameras_title') }}</h3>
        <p style="color: var(--text-muted); font-size: 13px; margin-bottom: 16px;">
          {{ $t('settings.override_cameras_desc') }}
        </p>
        <div class="table-responsive" v-if="cameras.length">
          <table class="data-table">
            <thead><tr><th>{{ $t('settings.col_original') }}</th><th>{{ $t('settings.col_display') }}</th></tr></thead>
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
        </div>
        <p v-else class="empty">{{ $t('settings.override_cameras_none') }}</p>

        <h3 style="margin-top: 24px;">{{ $t('settings.override_telescopes_title') }}</h3>
        <div class="table-responsive" v-if="telescopes.length">
          <table class="data-table">
            <thead><tr><th>{{ $t('settings.col_original') }}</th><th>{{ $t('settings.col_display') }}</th></tr></thead>
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
        </div>
        <p v-else class="empty">{{ $t('settings.override_telescopes_none') }}</p>
      </div>

      <div v-if="activeTab === 'danger'" class="card danger-zone">
        <h3 style="color: var(--danger);">{{ $t('settings.danger_reset_title') }}</h3>
        <p style="color: var(--text-muted); font-size: 13px; margin-bottom: 16px;">
          {{ $t('settings.danger_reset_desc') }}
        </p>
        <div v-if="!confirmingReset">
          <button class="btn btn-danger" @click="confirmingReset = true">
            {{ $t('settings.danger_reset_button') }}
          </button>
        </div>
        <div v-else class="reset-confirm">
          <p style="margin-bottom: 12px;"><strong>{{ $t('settings.danger_reset_confirm') }}</strong></p>
          <div class="reset-actions">
            <button class="btn btn-danger" @click="resetDb" :disabled="resetBusy">
              {{ resetBusy ? $t('settings.danger_reset_busy') : $t('settings.danger_reset_yes') }}
            </button>
            <button class="btn btn-ghost" @click="confirmingReset = false" :disabled="resetBusy">
              {{ $t('settings.danger_reset_cancel') }}
            </button>
          </div>
        </div>
      </div>

      <div class="setting-actions">
        <button class="btn" @click="save" :disabled="saving">
          {{ saving ? $t('settings.save_busy') : $t('settings.save') }}
        </button>
        <span v-if="saved" class="save-success">{{ $t('settings.save_success') }}</span>
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
.tab-danger {
  color: var(--danger) !important;
}
.tab-danger.active {
  border-bottom-color: var(--danger) !important;
}
.danger-zone {
  border-color: rgba(248, 81, 73, 0.3);
}
.reset-confirm {
  padding: 12px;
  background: rgba(248, 81, 73, 0.05);
  border-radius: 8px;
}
.reset-actions {
  display: flex;
  gap: 8px;
}
</style>
