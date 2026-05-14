<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApiStore, type Session, type PaginatedResponse } from '@/stores/api'
import Pagination from '@/components/Pagination.vue'

const route = useRoute()
const router = useRouter()
const apiStore = useApiStore()
const target = ref<any>(null)
const sessions = ref<Session[]>([])
const thumbnails = ref<any[]>([])
const page = ref(1)
const totalPages = ref(1)
const totalItems = ref(0)

const targetId = computed(() => parseInt(route.params.id as string))

async function loadTarget() {
  try {
    target.value = await apiStore.fetch(`/targets/${targetId.value}`)
  } catch {
    router.push('/targets')
  }
}

async function loadSessions() {
  const res = await apiStore.fetch<PaginatedResponse<Session>>(`/targets/${targetId.value}/sessions`, {
    page: page.value,
    page_size: 50,
  })
  sessions.value = res.items
  totalPages.value = res.pages
  totalItems.value = res.total
}

async function loadThumbnails() {
  try {
    thumbnails.value = await apiStore.fetch(`/targets/${targetId.value}/thumbnails`, { limit: 6 })
  } catch {
    thumbnails.value = []
  }
}

function formatCoord(value: number | null, prefix: string): string {
  if (value === null || value === undefined) return '-'
  if (prefix === 'RA') {
    const hours = value / 15
    const h = Math.floor(hours)
    const m = Math.floor((hours - h) * 60)
    const s = ((hours - h) * 60 - m) * 60
    return `${h}h ${m}m ${s.toFixed(1)}s`
  }
  const deg = Math.floor(Math.abs(value))
  const m = Math.floor((Math.abs(value) - deg) * 60)
  const s = ((Math.abs(value) - deg) * 60 - m) * 60
  const sign = value >= 0 ? '+' : '−'
  return `${sign}${deg}° ${m}' ${s.toFixed(0)}"`
}

const typeBadgeClass = (type: string | null): string => {
  const map: Record<string, string> = {
    'Galaxy': 'badge-galaxy', 'Nebula': 'badge-nebula',
    'Star': 'badge-star', 'Cluster': 'badge-cluster',
    'Supernova Remnant': 'badge-snr', 'Planetary Nebula': 'badge-planetary',
  }
  return map[type || ''] || 'badge-default'
}

onMounted(() => {
  loadTarget()
  loadSessions()
  loadThumbnails()
})

watch(page, loadSessions)
</script>

<template>
  <div>
    <div class="breadcrumb">
      <a @click="router.push('/targets')">Targets</a>
      <span> / </span>
      <span class="active">{{ target?.name || '...' }}</span>
    </div>

    <div class="page-header">
      <h2>{{ target?.name || 'Loading...' }}</h2>
      <p v-if="target">
        <span v-if="target.object_type" :class="['badge', typeBadgeClass(target.object_type)]">
          {{ target.object_type }}
        </span>
        <span v-if="target.constellation" style="margin-left: 8px">
          Sternbild {{ target.constellation }}
        </span>
      </p>
    </div>

    <div class="stats-grid" v-if="target">
      <div class="stat-card">
        <div class="value">{{ target.session_count }}</div>
        <div class="label">Sessions</div>
      </div>
      <div class="stat-card">
        <div class="value">{{ target.total_exposure_h }}h</div>
        <div class="label">Belichtung</div>
      </div>
      <div class="stat-card">
        <div class="value">{{ target.ra_deg ? formatCoord(target.ra_deg, 'RA') : '-' }}</div>
        <div class="label">Rektaszension</div>
      </div>
      <div class="stat-card">
        <div class="value">{{ target.dec_deg ? formatCoord(target.dec_deg, 'DEC') : '-' }}</div>
        <div class="label">Deklination</div>
      </div>
    </div>

    <div class="card">
      <h3>Letzte Aufnahmen</h3>
      <div class="thumbnail-grid" v-if="thumbnails.length">
        <div v-for="t in thumbnails" :key="t.id" class="thumbnail-item">
          <img v-if="t.thumbnail" :src="t.thumbnail" :alt="t.filename" class="thumb-img" />
          <div v-else class="thumb-placeholder">
            <span>{{ t.filter_name || '?' }}</span>
          </div>
          <div class="thumb-meta">{{ t.filter_name || '-' }} · {{ t.exposure ? t.exposure + 's' : '-' }}</div>
        </div>
      </div>
      <p v-else class="empty">Keine Vorschaubilder verfügbar.</p>
    </div>

    <div class="card">
      <h3>Sessions ({{ totalItems }})</h3>
      <table class="data-table">
        <thead>
          <tr>
            <th>Datum</th>
            <th>Kamera</th>
            <th>Teleskop</th>
            <th>Belichtung</th>
            <th>Frames</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="s in sessions"
            :key="s.id"
            class="clickable"
            @click="router.push({ name: 'session-detail', params: { id: s.id } })"
          >
            <td>{{ s.date_obs ? new Date(s.date_obs).toLocaleDateString('de-CH') : '-' }}</td>
            <td>{{ s.camera_name || '-' }}</td>
            <td>{{ s.telescope_name || '-' }}</td>
            <td>{{ s.total_exposure_h }}h</td>
            <td>{{ s.frame_count }}</td>
            <td><span class="badge badge-light">{{ s.status }}</span></td>
          </tr>
        </tbody>
      </table>
    </div>

    <Pagination :total="totalItems" :page="page" :pages="totalPages" @update:page="page = $event" />
  </div>
</template>

<style scoped>
.breadcrumb {
  font-size: 13px;
  margin-bottom: 8px;
  color: var(--text-muted);
}
.breadcrumb a {
  cursor: pointer;
  color: var(--accent);
}
.breadcrumb .active {
  color: var(--text);
}
.thumbnail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 12px;
}
.thumbnail-item {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
}
.thumb-img {
  width: 100%;
  height: 120px;
  object-fit: cover;
  display: block;
}
.thumb-placeholder {
  width: 100%;
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface2);
  color: var(--text-faint);
  font-size: 24px;
  font-weight: 700;
}
.thumb-meta {
  padding: 6px 8px;
  font-size: 11px;
  color: var(--text-muted);
}
</style>
