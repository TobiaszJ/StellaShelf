<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useApiStore } from '@/stores/api'

const apiStore = useApiStore()

interface NamedObject {
  name: string
  messier: string | null
  common_names: string | null
  object_type: string | null
  constellation: string | null
  ra_deg: number | null
  dec_deg: number | null
  preferred_name: string | null
}

const objects = ref<NamedObject[]>([])
const loading = ref(true)
const saving = ref(false)
const filterText = ref('')
const saveCount = ref(0)

const edits = ref<Record<string, string>>({})

onMounted(async () => {
  try {
    objects.value = await apiStore.fetch<NamedObject[]>('/catalog/named-objects')
    // Initialize edits from saved preferences
    for (const obj of objects.value) {
      if (obj.preferred_name) {
        edits.value[obj.name] = obj.preferred_name
      }
    }
  } catch {
    objects.value = []
  } finally {
    loading.value = false
  }
})

const filtered = computed(() => {
  if (!filterText.value) return objects.value
  const q = filterText.value.toLowerCase()
  return objects.value.filter(
    (o) =>
      o.name.toLowerCase().includes(q) ||
      (o.messier || '').toLowerCase().includes(q) ||
      (o.common_names || '').toLowerCase().includes(q)
  )
})

function getOptions(obj: NamedObject): string[] {
  const opts: string[] = []
  if (obj.messier) opts.push(`M${obj.messier.replace(/^0+/, '')}`)
  opts.push(obj.name)
  if (obj.common_names) {
    for (const n of obj.common_names.split(',')) {
      const s = n.trim()
      if (s) opts.push(s)
    }
  }
  return [...new Set(opts)]
}

/** The name identify would use when no preference is set (first full name / common name). */
function effectiveName(obj: NamedObject): string {
  const names = getOptions(obj)
  // Prefer first common name, fall back to first option
  if (obj.common_names) {
    const first = obj.common_names.split(',')[0].trim()
    if (first) return first
  }
  return names[0] || obj.name
}

function selectPreference(obj: NamedObject, value: string) {
  if (value === '__custom__') {
    edits.value[obj.name] = ''
  } else if (value === effectiveName(obj)) {
    delete edits.value[obj.name]
  } else {
    edits.value[obj.name] = value
  }
}

async function saveAll() {
  saving.value = true
  saveCount.value = 0
  try {
    for (const [ngcName, preferred] of Object.entries(edits.value)) {
      if (!preferred) continue
      await apiStore.post('/catalog/name-preference', { ngc_name: ngcName, preferred_name: preferred })
      saveCount.value++
    }
  } catch (e: any) {
    console.error('API error:', e.response?.data?.detail || e.message)
    alert('Ein Fehler ist aufgetreten. Bitte versuche es erneut.')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h2>Objektnamen verwalten</h2>
      <p>Wähle die bevorzugte Bezeichnung für Deep-Sky-Objekte mit mehreren Namen</p>
    </div>

    <div v-if="loading" class="loading">Lade Katalog-Objekte...</div>

    <template v-else>
      <div class="filters">
        <div class="filter-group" style="flex: 1;">
          <label>Suchen</label>
          <input v-model="filterText" type="text" placeholder="M33, NGC598, Triangulum..." />
        </div>
        <div class="filter-group" style="align-self: flex-end;">
          <button class="btn" :disabled="saving" @click="saveAll">
            {{ saving ? 'Speichere...' : `${Object.keys(edits).length} Namenswahlen speichern` }}
          </button>
        </div>
      </div>

      <div v-if="saveCount > 0" style="background: rgba(63,185,80,0.1); border: 1px solid var(--accent2); border-radius: 8px; padding: 12px 16px; margin-bottom: 16px; font-size: 13px; color: var(--accent2);">
        {{ saveCount }} Namenswahlen gespeichert.
      </div>

      <div class="card">
        <p style="color: var(--text-muted); font-size: 13px; margin-bottom: 12px;">
          {{ filtered.length }} Objekte mit alternativen Namen
        </p>

        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>Katalog</th>
                <th>Messier</th>
                <th>NGC/IC</th>
                <th>Typ</th>
                <th>Sternbild</th>
                <th style="min-width: 220px;">Bevorzugter Name</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="obj in filtered" :key="obj.name">
                <td>{{ obj.name.startsWith('IC') ? 'IC' : 'NGC' }}</td>
                <td>{{ obj.messier ? 'M' + obj.messier.replace(/^0+/, '') : '-' }}</td>
                <td>{{ obj.name }}</td>
                <td><span class="badge badge-light">{{ obj.object_type }}</span></td>
                <td>{{ obj.constellation || '-' }}</td>
                <td>
                  <div class="name-picker">
                    <select
                      :value="edits[obj.name] || effectiveName(obj)"
                      @change="(e) => selectPreference(obj, (e.target as HTMLSelectElement).value)"
                      class="name-select"
                    >
                      <option :value="effectiveName(obj)" style="font-weight: 600">{{ effectiveName(obj) }} ⬅</option>
                      <option
                        v-for="opt in getOptions(obj).filter(o => o !== effectiveName(obj))"
                        :key="opt"
                        :value="opt"
                      >{{ opt }}</option>
                      <option value="__custom__">— Eigener Name —</option>
                    </select>
                    <input
                      v-if="edits[obj.name] && !getOptions(obj).includes(edits[obj.name])"
                      v-model="edits[obj.name]"
                      type="text"
                      class="name-custom"
                      placeholder="Eigenen Namen eingeben..."
                    />
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.name-picker {
  display: flex;
  gap: 6px;
  align-items: center;
}
.name-select {
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  min-width: 180px;
  cursor: pointer;
}
.name-select:focus {
  outline: none;
  border-color: var(--accent);
}
.name-custom {
  background: var(--bg);
  border: 1px solid var(--accent);
  color: var(--text);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  width: 160px;
}
.name-custom:focus {
  outline: none;
}
</style>
