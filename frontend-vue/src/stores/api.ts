import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1' })

export interface Target {
  id: number
  name: string
  object_type: string | null
  constellation: string | null
  ra_deg: number | null
  dec_deg: number | null
  alt_names: string | null
  session_count: number
  total_exposure_h: number
}

export interface Session {
  id: number
  target_id: number
  target_name: string
  camera_name: string | null
  telescope_name: string | null
  date_obs: string | null
  group_key: string
  status: string
  total_exposure_s: number
  total_exposure_h: number
  frame_count: number
  folder_path: string | null
}

export interface Frame {
  id: number
  session_id: number | null
  filename: string
  filepath: string
  frame_type: string | null
  object_name: string | null
  filter_name: string | null
  exposure: number | null
  gain: number | null
  ccd_temp: number | null
  binning: number
  date_obs: string | null
  hfd_median: number | null
  stars_detected: number | null
}

export interface Camera {
  id: number
  name: string
  short_name: string | null
  pixel_size_um: number | null
  frame_count: number
  total_exposure_h: number
}

export interface Telescope {
  id: number
  name: string
  short_name: string | null
  focal_length_mm: number | null
  frame_count: number
  total_exposure_h: number
}

export interface FilterStat {
  name: string
  frame_count: number
  total_exposure_h: number
}

export interface SearchResult {
  targets: Array<{ id: number; name: string; type: string | null }>
  sessions: Array<{ id: number; group_key: string; date_obs: string | null; frame_count: number }>
  frames: Array<{ id: number; object_name: string; filename: string; frame_type: string }>
}

export interface DashboardData {
  total_exposure_h: number
  total_frames: number
  total_sessions: number
  total_targets: number
  top_targets: Array<{ id: number; name: string; total_exposure_h: number; session_count: number }>
  recent_sessions: Array<{ id: number; target_id: number; target_name: string; date_obs: string | null; total_exposure_h: number; frame_count: number }>
  cameras: Array<{ id: number; name: string; short_name: string | null; frame_count: number; total_exposure_h: number }>
}

export interface ScanState {
  running: boolean
  total: number
  processed: number
  imported: number
  skipped: number
  calibration_files: number
  current_file: string
  phase: string
  error: string | null
}

export interface DuplicateGroup {
  canonical_name: string
  targets: Array<{ id: number; name: string; session_count: number }>
}

export interface PaginatedResponse<T> {
  total: number
  page: number
  page_size: number
  pages: number
  items: T[]
}

export const useApiStore = defineStore('api', () => {
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetch<T>(url: string, params: Record<string, any> = {}): Promise<T> {
    loading.value = true
    error.value = null
    try {
      const res = await api.get(url, { params })
      return res.data
    } catch (e: any) {
      error.value = e.response?.data?.detail || e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function post<T>(url: string, data: any, params?: Record<string, any>): Promise<T> {
    loading.value = true
    error.value = null
    try {
      const res = await api.post(url, data, params ? { params } : {})
      return res.data
    } catch (e: any) {
      error.value = e.response?.data?.detail || e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function patch<T>(url: string, data: any): Promise<T> {
    loading.value = true
    error.value = null
    try {
      const res = await api.patch(url, data)
      return res.data
    } catch (e: any) {
      error.value = e.response?.data?.detail || e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchBlob(url: string): Promise<Blob> {
    const res = await api.get(url, { responseType: 'blob' })
    return res.data
  }

  return { loading, error, fetch, post, patch, fetchBlob }
})