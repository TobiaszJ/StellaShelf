<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useApiStore, type SearchResult } from '@/stores/api'

const apiStore = useApiStore()
const router = useRouter()
const query = ref('')
const results = ref<any>(null)
const activeTab = ref('all')

async function search() {
  if (!query.value.trim()) {
    results.value = null
    return
  }
  try {
    results.value = await apiStore.fetch('/search', { q: query.value.trim(), limit: 20 })
  } catch {
    results.value = null
  }
}

watch(query, (val) => {
  if (!val) results.value = null
})
</script>

<template>
  <div>
    <div class="page-header">
      <h2>Suche</h2>
      <p>Durchsuche alle Metadaten deiner Astro-Sammlung</p>
    </div>

    <div class="search-bar">
      <input
        v-model="query"
        placeholder="Suchbegriff eingeben (z.B. M42, NGC7000, Ha)..."
        type="text"
        class="search-input"
        @keyup.enter="search"
      />
      <button class="btn" @click="search" :disabled="!query.trim()">
        Suchen
      </button>
    </div>

    <div v-if="results" class="search-results">
      <div class="tabs">
        <button :class="['tab', { active: activeTab === 'all' }]" @click="activeTab = 'all'">
          Alle ({{ results.targets.length + results.sessions.length + results.frames.length }})
        </button>
        <button :class="['tab', { active: activeTab === 'targets' }]" @click="activeTab = 'targets'">
          Targets ({{ results.targets.length }})
        </button>
        <button :class="['tab', { active: activeTab === 'sessions' }]" @click="activeTab = 'sessions'">
          Sessions ({{ results.sessions.length }})
        </button>
        <button :class="['tab', { active: activeTab === 'frames' }]" @click="activeTab = 'frames'">
          Frames ({{ results.frames.length }})
        </button>
      </div>

      <!-- Targets -->
      <div class="card" v-if="activeTab === 'all' || activeTab === 'targets'">
        <h3>Targets</h3>
        <table class="data-table" v-if="results.targets.length">
          <thead><tr><th>Name</th><th>Typ</th></tr></thead>
          <tbody>
            <tr v-for="t in results.targets" :key="t.id" class="clickable" @click="router.push({ name: 'target-detail', params: { id: t.id } })">
              <td><strong>{{ t.name }}</strong></td>
              <td>{{ t.type || '-' }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="empty">Keine Targets gefunden.</p>
      </div>

      <!-- Sessions -->
      <div class="card" v-if="activeTab === 'all' || activeTab === 'sessions'">
        <h3>Sessions</h3>
        <table class="data-table" v-if="results.sessions.length">
          <thead><tr><th>Session</th><th>Datum</th><th>Frames</th></tr></thead>
          <tbody>
            <tr v-for="s in results.sessions" :key="s.id" class="clickable" @click="router.push({ name: 'session-detail', params: { id: s.id } })">
              <td><strong>{{ s.group_key }}</strong></td>
              <td>{{ s.date_obs ? new Date(s.date_obs).toLocaleDateString('de-CH') : '-' }}</td>
              <td>{{ s.frame_count }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="empty">Keine Sessions gefunden.</p>
      </div>

      <!-- Frames -->
      <div class="card" v-if="activeTab === 'all' || activeTab === 'frames'">
        <h3>Frames</h3>
        <table class="data-table" v-if="results.frames.length">
          <thead><tr><th>Datei</th><th>Target</th><th>Typ</th></tr></thead>
          <tbody>
            <tr v-for="f in results.frames" :key="f.id">
              <td style="font-family: monospace; font-size: 12px;">{{ f.filename }}</td>
              <td>{{ f.object_name }}</td>
              <td><span :class="'badge badge-' + f.frame_type.toLowerCase()">{{ f.frame_type }}</span></td>
            </tr>
          </tbody>
        </table>
        <p v-else class="empty">Keine Frames gefunden.</p>
      </div>
    </div>

    <p v-else-if="query && !results" class="loading">Suche läuft...</p>
    <p v-else class="empty">Gib einen Suchbegriff ein, um zu beginnen.</p>
  </div>
</template>

<style scoped>
.search-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
}
.search-input {
  flex: 1;
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 10px 14px;
  border-radius: 6px;
  font-size: 15px;
}
.search-input:focus {
  outline: none;
  border-color: var(--accent);
}
.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 12px;
}
.tab {
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text-muted);
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
}
.tab.active {
  background: rgba(88,166,255,0.1);
  color: var(--accent);
  border-color: var(--accent);
}
</style>
