<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterView, RouterLink } from 'vue-router'
import { Telescope, Target, Camera, FolderOpen, ScanLine, Search, Settings as SettingsIcon, HelpCircle, Globe, Sun, Moon } from 'lucide-vue-next'
import { useScanStore } from '@/stores/scan'
import { usePlatesolveStore } from '@/stores/platesolve'
import { useThemeStore } from '@/stores/theme'
import { useApiStore } from '@/stores/api'

const scanStore = useScanStore()
const platesolveStore = usePlatesolveStore()
const themeStore = useThemeStore()
const apiStore = useApiStore()

const buildInfo = ref('')

async function loadBuildInfo() {
  try {
    const health = await apiStore.fetch<{ version: string; build: string }>('/health')
    buildInfo.value = health.build
  } catch {
    buildInfo.value = 'dev'
  }
}

onMounted(() => {
  loadBuildInfo()
})

// Initialize theme on mount
themeStore.init()

// Start polling on mount
scanStore.fetchStatus()
if (scanStore.state.running) {
  scanStore.startPolling()
}

platesolveStore.fetchStatus()
if (platesolveStore.state.running) {
  platesolveStore.startPolling()
}

function toggleTheme() {
  if (themeStore.theme === 'dark') themeStore.setTheme('light')
  else if (themeStore.theme === 'light') themeStore.setTheme('dark')
  else themeStore.setTheme('dark')
}
</script>

<template>
  <div class="app-layout">
    <aside class="sidebar">
      <div class="sidebar-header">
        <h1>
          <Telescope :size="20" />
          StellaShelf
        </h1>
        <div class="version">v0.3.0</div>
        <div class="build" v-if="buildInfo">{{ buildInfo }}</div>
      </div>
      <nav class="sidebar-nav">
        <RouterLink to="/" class="nav-item">
          <Target :size="18" />
          Dashboard
        </RouterLink>
        <RouterLink to="/targets" class="nav-item">
          <FolderOpen :size="18" />
          Targets
        </RouterLink>
        <RouterLink to="/sessions" class="nav-item">
          <Target :size="18" />
          Sessions
        </RouterLink>
        <RouterLink to="/equipment" class="nav-item">
          <Camera :size="18" />
          Equipment
        </RouterLink>
        <RouterLink to="/search" class="nav-item">
          <Search :size="18" />
          Suche
        </RouterLink>
        <RouterLink to="/scan" class="nav-item">
          <ScanLine :size="18" />
          Scan
        </RouterLink>
        <RouterLink to="/settings" class="nav-item">
          <SettingsIcon :size="18" />
          Einstellungen
        </RouterLink>
        <RouterLink to="/platesolve" class="nav-item">
          <Globe :size="18" />
          Platesolving
        </RouterLink>
        <RouterLink to="/help" class="nav-item">
          <HelpCircle :size="18" />
          Hilfe
        </RouterLink>
      </nav>
      <div style="padding: 8px; border-top: 1px solid var(--border);">
        <button class="nav-item" @click="toggleTheme" style="width: 100%; border: none; background: none; cursor: pointer;">
          <Sun v-if="!themeStore.isDark" :size="18" />
          <Moon v-else :size="18" />
          {{ themeStore.isDark ? 'Dark Mode' : 'Light Mode' }}
        </button>
      </div>
    </aside>

    <div class="main-content">
      <!-- Scan Banner -->
      <div v-if="scanStore.state.running" class="scan-banner">
        <ScanLine :size="16" style="color: var(--accent)" />
        <span class="scan-text">{{ scanStore.phaseLabel }}</span>
        <div class="progress-bar-bg">
          <div class="progress-bar-fill" :style="{ width: scanStore.progress + '%' }"></div>
        </div>
        <span class="scan-pct">{{ scanStore.progress }}%</span>
      </div>

      <!-- Platesolve Banner -->
      <div v-if="platesolveStore.state.running" class="scan-banner">
        <Globe :size="16" style="color: var(--accent2)" />
        <span class="scan-text">{{ platesolveStore.phaseLabel }}</span>
        <div class="progress-bar-bg">
          <div class="progress-bar-fill" :style="{ width: platesolveStore.progress + '%', background: 'linear-gradient(90deg, var(--accent2), var(--accent))' }"></div>
        </div>
        <span class="scan-pct">{{ platesolveStore.progress }}%</span>
      </div>

      <main class="content-area">
        <RouterView />
      </main>
    </div>
  </div>
</template>
