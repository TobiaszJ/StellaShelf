<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useApiStore } from '@/stores/api'
import { useI18n } from 'vue-i18n'
import FramePreviewModal from '@/components/FramePreviewModal.vue'

const { t } = useI18n()
const apiStore = useApiStore()
const router = useRouter()
const query = ref('')
const results = ref<any>(null)
const activeTab = ref('all')
const previewFrameId = ref<number | null>(null)

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
      <h2>{{ $t('search.title') }}</h2>
      <p>{{ $t('search.description') }}</p>
    </div>

    <div class="search-bar">
      <input
        v-model="query"
        :placeholder="$t('search.placeholder')"
        type="text"
        class="search-input"
        @keyup.enter="search"
      />
      <button class="btn" @click="search" :disabled="!query.trim()">
        {{ $t('search.button') }}
      </button>
    </div>

    <div v-if="results" class="search-results">
      <div class="tabs">
        <button :class="['tab', { active: activeTab === 'all' }]" @click="activeTab = 'all'">
          {{ $t('search.tab_all') }} ({{ results.targets.length + results.sessions.length + results.frames.length }})
        </button>
        <button :class="['tab', { active: activeTab === 'targets' }]" @click="activeTab = 'targets'">
          {{ $t('search.tab_targets', { count: results.targets.length }) }}
        </button>
        <button :class="['tab', { active: activeTab === 'sessions' }]" @click="activeTab = 'sessions'">
          {{ $t('search.tab_sessions', { count: results.sessions.length }) }}
        </button>
        <button :class="['tab', { active: activeTab === 'frames' }]" @click="activeTab = 'frames'">
          {{ $t('search.tab_frames', { count: results.frames.length }) }}
        </button>
      </div>

      <div class="card" v-if="activeTab === 'all' || activeTab === 'targets'">
        <h3>{{ $t('search.tab_targets', { count: results.targets.length }) }}</h3>
        <div class="table-responsive" v-if="results.targets.length">
          <table class="data-table">
            <thead><tr><th>{{ $t('search.col_name') }}</th><th>{{ $t('search.col_type') }}</th></tr></thead>
            <tbody>
              <tr v-for="t in results.targets" :key="t.id" class="clickable" @click="router.push({ name: 'target-detail', params: { id: t.id } })">
                <td><strong>{{ t.name }}</strong></td>
                <td>{{ t.type || '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="empty">{{ $t('search.empty_targets') }}</p>
      </div>

      <div class="card" v-if="activeTab === 'all' || activeTab === 'sessions'">
        <h3>{{ $t('search.tab_sessions', { count: results.sessions.length }) }}</h3>
        <div class="table-responsive" v-if="results.sessions.length">
          <table class="data-table">
            <thead><tr><th>{{ $t('search.col_session') }}</th><th>{{ $t('search.col_date') }}</th><th>{{ $t('search.col_frames') }}</th></tr></thead>
            <tbody>
              <tr v-for="s in results.sessions" :key="s.id" class="clickable" @click="router.push({ name: 'session-detail', params: { id: s.id } })">
                <td><strong>{{ s.group_key }}</strong></td>
                <td>{{ s.date_obs ? new Date(s.date_obs).toLocaleDateString('de-CH') : '-' }}</td>
                <td>{{ s.frame_count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="empty">{{ $t('search.empty_sessions') }}</p>
      </div>

      <div class="card" v-if="activeTab === 'all' || activeTab === 'frames'">
        <h3>{{ $t('search.tab_frames', { count: results.frames.length }) }}</h3>
        <div class="table-responsive" v-if="results.frames.length">
          <table class="data-table">
            <thead><tr><th>{{ $t('search.col_file') }}</th><th>{{ $t('search.col_target_name') }}</th><th>{{ $t('search.col_type') }}</th></tr></thead>
            <tbody>
            <tr v-for="f in results.frames" :key="f.id" class="clickable" @click="previewFrameId = f.id">
              <td style="font-family: monospace; font-size: 12px;">{{ f.filename }}</td>
              <td>{{ f.object_name }}</td>
              <td><span :class="'badge badge-' + f.frame_type.toLowerCase()">{{ f.frame_type }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    </div>

    <p v-else-if="query && !results" class="loading">{{ t('search.searching') }}</p>
    <p v-else class="empty">{{ t('search.start_hint') }}</p>

    <FramePreviewModal :frameId="previewFrameId" @close="previewFrameId = null" />
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
