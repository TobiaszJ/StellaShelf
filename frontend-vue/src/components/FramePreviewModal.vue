<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import { useApiStore } from '@/stores/api'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const apiStore = useApiStore()

const props = defineProps<{
  frameId: number | null
}>()

const emit = defineEmits<{
  close: []
}>()

const frame = ref<any>(null)
const thumbUrl = ref<string | null>(null)
const loading = ref(false)
const blobUrls = ref<string[]>([])

function trackBlobUrl(url: string | null) {
  if (url) blobUrls.value.push(url)
}

function revokeAll() {
  for (const url of blobUrls.value) URL.revokeObjectURL(url)
  blobUrls.value = []
}

onUnmounted(() => revokeAll())

const metadataEntries = computed(() => {
  if (!frame.value) return []
  const entries: { label: string; value: string }[] = []
  const fields: Record<string, string> = {
    filename: 'Dateiname', filepath: 'Pfad', file_size: 'Größe (Bytes)',
    frame_type: 'Typ', object_name: 'Objekt', instrume: 'Kamera', telescop: 'Teleskop',
    filter_name: 'Filter', exposure: 'Belichtung (s)', gain: 'Gain', ccd_temp: 'Temperatur (°C)',
    binning: 'Binning', date_obs: 'Datum (UTC)', date_local: 'Datum (Lokal)',
    width: 'Breite (px)', height: 'Höhe (px)', pixel_size_um: 'Pixelgröße (µm)',
    ra_deg: 'RA (°)', dec_deg: 'DEC (°)', focal_length_mm: 'Brennweite (mm)',
    site_name: 'Standort', observer: 'Beobachter', creator: 'Software',
    fwhm: 'FWHM', eccentricity: 'Exzentrizität', snr: 'SNR',
    hfd_median: 'HFD', stars_detected: 'Sterne',
  }
  for (const [key, label] of Object.entries(fields)) {
    const val = (frame.value as any)[key]
    if (val !== null && val !== undefined && val !== '') {
      let display = String(val)
      if (key === 'exposure') display = Number(val).toFixed(1) + 's'
      if (key === 'ccd_temp' && typeof val === 'number') display = val.toFixed(1) + '°C'
      if (key === 'ra_deg' && typeof val === 'number') display = val.toFixed(4) + '°'
      if (key === 'dec_deg' && typeof val === 'number') display = val.toFixed(4) + '°'
      if (key === 'date_obs' || key === 'date_local') display = new Date(val).toLocaleString('de-CH')
      if (key === 'binning') display = val + 'x' + val
      entries.push({ label, value: display })
    }
  }
  return entries
})

async function load(id: number) {
  loading.value = true
  frame.value = null
  thumbUrl.value = null
  try {
    frame.value = await apiStore.fetch(`/frames/${id}`)
    try {
      const blob = await apiStore.fetchBlob(`/frames/${id}/thumbnail?preview=true`)
      thumbUrl.value = URL.createObjectURL(blob)
      trackBlobUrl(thumbUrl.value)
    } catch {
      thumbUrl.value = null
    }
  } catch {
    frame.value = null
  } finally {
    loading.value = false
  }
}

function close() {
  revokeAll()
  emit('close')
}

watch(() => props.frameId, (id) => {
  if (id !== null) load(id)
})
</script>

<template>
  <div v-if="frameId !== null" class="modal-overlay" @click.self="close">
    <div class="preview-modal">
      <div class="preview-header">
        <h3>{{ frame?.filename || t('session_detail.preview_title') }}</h3>
        <button class="btn-close" @click="close">&times;</button>
      </div>
      <div class="preview-body">
        <div class="preview-image">
          <div v-if="loading" class="loading">{{ t('session_detail.loading') }}</div>
          <img v-else-if="thumbUrl" :src="thumbUrl" :alt="frame?.filename || ''" class="preview-img" />
          <div v-else class="preview-noimg">{{ t('session_detail.preview_noimg') }}</div>
        </div>
        <div class="preview-metadata">
          <div class="table-responsive">
            <table class="metadata-table">
              <tbody>
                <tr v-for="entry in metadataEntries" :key="entry.label">
                  <td class="meta-label">{{ entry.label }}</td>
                  <td class="meta-value">{{ entry.value }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.preview-modal {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  width: 90%;
  max-width: 900px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}
.preview-header h3 {
  font-size: 15px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.btn-close {
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 24px;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
}
.btn-close:hover { color: var(--text); }
.preview-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}
.preview-image {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #000;
  min-height: 300px;
  overflow: hidden;
}
.preview-img {
  max-width: 100%;
  max-height: 65vh;
  object-fit: contain;
}
.preview-noimg {
  color: var(--text-muted);
  font-size: 14px;
}
.preview-metadata {
  width: 300px;
  overflow-y: auto;
  border-left: 1px solid var(--border);
  padding: 12px;
}
.metadata-table {
  width: 100%;
  font-size: 12px;
  border-collapse: collapse;
}
.metadata-table tr {
  border-bottom: 1px solid var(--border);
}
.metadata-table td {
  padding: 6px 4px;
  vertical-align: top;
}
.meta-label {
  color: var(--text-muted);
  white-space: nowrap;
  width: 40%;
  font-weight: 500;
}
.meta-value {
  color: var(--text);
  word-break: break-all;
  font-family: monospace;
}
</style>
