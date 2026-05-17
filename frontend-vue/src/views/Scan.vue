<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useScanStore } from '@/stores/scan'
import { useApiStore } from '@/stores/api'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const scanStore = useScanStore()
const apiStore = useApiStore()
const selectedPath = ref('')
const knownPaths = ref<{ label: string; value: string }[]>([])

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
  }
  knownPaths.value = []
  selectedPath.value = ''
})

const btnDisabled = computed(() => scanStore.state.running)

async function startScan() {
  if (!selectedPath.value.trim()) {
    alert(t('error.generic', { message: 'Bitte einen Pfad eingeben' }))
    return
  }
  try {
    await scanStore.startScan(selectedPath.value)
  } catch (e: any) {
    alert(e.response?.data?.detail || t('phase.scan_error'))
  }
}

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
    params[cleanupField.value] = cleanupPattern.value
    const res = await apiStore.fetch<any>('/frames', params)
    cleanupResults.value = res.items || []
    cleanupTotal.value = res.total || 0
  } catch (e: any) {
    alert(t('error.generic', { message: e.response?.data?.detail || e.message }))
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
    alert(t('scan.cleanup_found', { count: res.deleted }))
    cleanupConfirming.value = false
    cleanupResults.value = cleanupResults.value.filter((f: any) => !cleanupSelected.value.has(f.id))
    cleanupSelected.value = new Set()
    cleanupTotal.value -= res.deleted
  } catch (e: any) {
    alert(t('error.generic', { message: e.response?.data?.detail || e.message }))
  } finally {
    cleanupBusy.value = false
  }
}

async function cleanupOrphans() {
  cleanupOrphansBusy.value = true
  cleanupOrphanResult.value = null
  try {
    const res = await apiStore.post<any>('/db/cleanup-orphans', {})
    cleanupOrphanResult.value = t('scan.cleanup_orphan_success', {
      result: `${res.sessions} ${t('nav.sessions')}, ${res.targets} ${t('nav.targets')}, ${res.cameras} ${t('equipment.tab_cameras', { count: 0 }).split(' ')[0]}, ${res.telescopes} ${t('equipment.tab_telescopes', { count: 0 }).split(' ')[0]}`
    })
  } catch (e: any) {
    alert(t('error.generic', { message: e.response?.data?.detail || e.message }))
  } finally {
    cleanupOrphansBusy.value = false
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h2>{{ $t('scan.title') }}</h2>
      <p>{{ $t('scan.description') }}</p>
    </div>

    <div class="tabs">
      <button :class="['tab', { active: cleanupTab === 'scan' }]" @click="cleanupTab = 'scan'">{{ $t('scan.tab_scan') }}</button>
      <button :class="['tab', { active: cleanupTab === 'cleanup' }]" @click="cleanupTab = 'cleanup'">{{ $t('scan.tab_cleanup') }}</button>
    </div>

    <template v-if="cleanupTab === 'scan'">
      <div class="card">
        <h3>{{ $t('scan.scan_path') }}</h3>
        <div class="scan-path-selector">
          <div class="filter-group">
            <label>{{ $t('scan.scan_directory') }}</label>
            <select v-model="selectedPath">
              <option v-for="p in knownPaths" :key="p.value" :value="p.value">{{ p.label }}</option>
            </select>
          </div>
          <div class="filter-group">
            <label>{{ $t('scan.scan_custom') }}</label>
            <input type="text" v-model="selectedPath" :placeholder="$t('scan.scan_placeholder')" />
          </div>
          <div class="scan-actions">
            <button class="btn btn-success" :disabled="btnDisabled" @click="startScan">
              {{ $t('scan.scan_start') }}
            </button>
            <button v-if="scanStore.state.running" class="btn btn-danger" @click="scanStore.cancelScan()">
              {{ $t('scan.scan_cancel') }}
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
            <div class="lbl">{{ $t('scan.scan_total') }}</div>
          </div>
          <div class="scan-stat">
            <div class="num">{{ scanStore.state.processed.toLocaleString() }}</div>
            <div class="lbl">{{ $t('scan.scan_processed') }}</div>
          </div>
          <div class="scan-stat">
            <div class="num">{{ scanStore.state.imported.toLocaleString() }}</div>
            <div class="lbl">{{ $t('scan.scan_imported') }}</div>
          </div>
          <div class="scan-stat">
            <div class="num">{{ scanStore.state.skipped.toLocaleString() }}</div>
            <div class="lbl">{{ $t('scan.scan_skipped') }}</div>
          </div>
        </div>
        <div class="current-file">{{ scanStore.state.current_file }}</div>
      </div>

      <div class="card">
        <h3>{{ $t('scan.scan_info_title') }}</h3>
        <p>{{ $t('scan.scan_info_text') }}</p>
      </div>
    </template>

    <template v-if="cleanupTab === 'cleanup'">
      <div class="card">
        <h3>{{ $t('scan.cleanup_title') }}</h3>
        <p style="color: var(--text-muted); font-size: 13px; margin-bottom: 12px;">
          {{ $t('scan.cleanup_desc') }}
        </p>
        <div class="cleanup-filters">
          <div class="filter-group">
            <label>{{ $t('scan.cleanup_field') }}</label>
            <select v-model="cleanupField">
              <option value="filename">{{ $t('scan.cleanup_filename') }}</option>
              <option value="filepath">{{ $t('scan.cleanup_filepath') }}</option>
            </select>
          </div>
          <div class="filter-group" style="flex: 1;">
            <label>{{ $t('scan.cleanup_pattern') }}</label>
            <input
              type="text"
              v-model="cleanupPattern"
              :placeholder="$t('scan.cleanup_pattern_placeholder')"
              @keydown="keydown"
            />
          </div>
          <div class="filter-group" style="align-self: flex-end;">
            <button class="btn" @click="searchFrames" :disabled="!cleanupPattern.trim() || cleanupLoading">
              {{ cleanupLoading ? $t('scan.cleanup_searching') : $t('scan.cleanup_search') }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="cleanupResults.length" class="card">
        <div class="cleanup-result-header">
          <h3>{{ $t('scan.cleanup_found', { count: cleanupTotal }) }}</h3>
          <div class="cleanup-actions">
            <span style="font-size: 13px; color: var(--text-muted);">
              {{ $t('scan.cleanup_selected', { count: cleanupSelected.size }) }}
            </span>
            <button
              v-if="!cleanupConfirming"
              class="btn btn-danger btn-sm"
              :disabled="!cleanupSelected.size"
              @click="cleanupConfirming = true"
            >
              {{ $t('scan.cleanup_delete') }}
            </button>
            <template v-else>
              <span style="font-size: 13px; color: var(--danger);">
                <strong>{{ $t('scan.cleanup_confirm', { count: cleanupSelected.size }) }}</strong>
              </span>
              <button class="btn btn-danger btn-sm" @click="deleteSelected" :disabled="cleanupBusy">
                {{ cleanupBusy ? $t('scan.cleanup_deleting') : $t('scan.cleanup_confirm_yes') }}
              </button>
              <button class="btn btn-sm btn-ghost" @click="cleanupConfirming = false" :disabled="cleanupBusy">
                {{ $t('scan.cleanup_cancel') }}
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
                  <th>{{ $t('scan.col_filename') }}</th>
                  <th>{{ $t('scan.col_type') }}</th>
                  <th>{{ $t('scan.col_filter') }}</th>
                  <th>{{ $t('scan.col_exposure') }}</th>
                  <th>{{ $t('scan.col_path') }}</th>
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

      <div v-else-if="cleanupLoading" class="loading">{{ $t('scan.cleanup_searching') }}</div>
      <div v-else-if="cleanupPattern && !cleanupLoading" class="card">
        <p class="empty">{{ $t('scan.cleanup_not_found') }}</p>
      </div>

      <div class="card">
        <h3>{{ $t('scan.cleanup_orphan_title') }}</h3>
        <p style="color: var(--text-muted); font-size: 13px; margin-bottom: 12px;">
          {{ $t('scan.cleanup_orphan_desc') }}
        </p>
        <div class="orphan-actions">
          <button class="btn btn-sm" @click="cleanupOrphans" :disabled="cleanupOrphansBusy">
            {{ cleanupOrphansBusy ? $t('scan.cleanup_orphan_busy') : $t('scan.cleanup_orphan_button') }}
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
