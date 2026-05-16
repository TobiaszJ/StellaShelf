<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter, RouterView, RouterLink } from 'vue-router'
import { Telescope, Target, Camera, ScanLine, Search, Settings as SettingsIcon, HelpCircle, Globe, Sun, Moon, Activity, LayoutDashboard, List, Crosshair, Menu, X } from 'lucide-vue-next'
import { useScanStore } from '@/stores/scan'
import { usePlatesolveStore } from '@/stores/platesolve'
import { useAnalyseStore } from '@/stores/analyse'
import { useIdentifyStore } from '@/stores/identify'
import { useThemeStore } from '@/stores/theme'
import { useApiStore } from '@/stores/api'

const scanStore = useScanStore()
const platesolveStore = usePlatesolveStore()
const analyseStore = useAnalyseStore()
const identifyStore = useIdentifyStore()
const themeStore = useThemeStore()
const apiStore = useApiStore()

const router = useRouter()
const sidebarOpen = ref(false)
const buildInfo = ref('')

async function loadBuildInfo() {
  try {
    const health = await apiStore.fetch<{ version: string; build: string }>('/health')
    buildInfo.value = health.build
  } catch {
    buildInfo.value = 'dev'
  }
}

function closeSidebar() {
  sidebarOpen.value = false
}

watch(() => router.currentRoute.value.path, () => {
  closeSidebar()
})

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

analyseStore.fetchStatus()
if (analyseStore.state.running) {
  analyseStore.startPolling()
}

identifyStore.fetchStatus()
if (identifyStore.state.running) {
  identifyStore.startPolling()
}

function toggleTheme() {
  if (themeStore.theme === 'dark') themeStore.setTheme('light')
  else if (themeStore.theme === 'light') themeStore.setTheme('dark')
  else themeStore.setTheme('dark')
}
</script>

<template>
  <div class="app-layout">
    <!-- Mobile overlay -->
    <div class="sidebar-overlay" :class="{ visible: sidebarOpen }" @click="closeSidebar"></div>

    <aside class="sidebar" :class="{ open: sidebarOpen }">
      <div class="sidebar-header">
        <div class="sidebar-header-row">
          <h1>
            <Telescope :size="20" />
            StellaShelf
          </h1>
          <button class="sidebar-close" @click="closeSidebar" aria-label="Menü schließen">
            <X :size="18" />
          </button>
        </div>
        <div class="version">v0.4.0</div>
        <div class="build" v-if="buildInfo">{{ buildInfo }}</div>
      </div>
      <nav class="sidebar-nav">
        <RouterLink to="/" class="nav-item" @click="closeSidebar">
          <LayoutDashboard :size="18" />
          <span class="nav-label">Dashboard</span>
        </RouterLink>
        <RouterLink to="/targets" class="nav-item" @click="closeSidebar">
          <Target :size="18" />
          <span class="nav-label">Objekte</span>
        </RouterLink>
        <RouterLink to="/sessions" class="nav-item" @click="closeSidebar">
          <List :size="18" />
          <span class="nav-label">Sessions</span>
        </RouterLink>
        <RouterLink to="/equipment" class="nav-item" @click="closeSidebar">
          <Camera :size="18" />
          <span class="nav-label">Ausrüstung</span>
        </RouterLink>
        <RouterLink to="/search" class="nav-item" @click="closeSidebar">
          <Search :size="18" />
          <span class="nav-label">Suche</span>
        </RouterLink>
        <RouterLink to="/scan" class="nav-item" @click="closeSidebar">
          <ScanLine :size="18" />
          <span class="nav-label">Scan</span>
        </RouterLink>
        <RouterLink to="/settings" class="nav-item" @click="closeSidebar">
          <SettingsIcon :size="18" />
          <span class="nav-label">Einstellungen</span>
        </RouterLink>
        <RouterLink to="/platesolve" class="nav-item" @click="closeSidebar">
          <Globe :size="18" />
          <span class="nav-label">Platesolving</span>
        </RouterLink>
        <RouterLink to="/analyse" class="nav-item" @click="closeSidebar">
          <Activity :size="18" />
          <span class="nav-label">Analyse</span>
        </RouterLink>
        <RouterLink to="/identify" class="nav-item" @click="closeSidebar">
          <Crosshair :size="18" />
          <span class="nav-label">Identifizieren</span>
        </RouterLink>
        <RouterLink to="/help" class="nav-item" @click="closeSidebar">
          <HelpCircle :size="18" />
          <span class="nav-label">Hilfe</span>
        </RouterLink>
      </nav>
      <div class="sidebar-footer">
        <button class="nav-item" @click="toggleTheme">
          <Sun v-if="!themeStore.isDark" :size="18" />
          <Moon v-else :size="18" />
          <span class="nav-label">{{ themeStore.isDark ? 'Dark Mode' : 'Light Mode' }}</span>
        </button>
      </div>
    </aside>

    <div class="main-content">
      <!-- Top bar for mobile -->
      <div class="top-bar">
        <button class="hamburger" @click="sidebarOpen = !sidebarOpen" aria-label="Menü öffnen">
          <Menu :size="22" />
        </button>
        <span class="top-bar-title">StellaShelf</span>
      </div>

      <!-- Scan Banner -->
      <div v-if="scanStore.state.running" class="scan-banner">
        <ScanLine :size="16" style="color: var(--accent); flex-shrink: 0;" />
        <span class="scan-text">{{ scanStore.phaseLabel }}</span>
        <div class="progress-bar-bg">
          <div class="progress-bar-fill" :style="{ width: scanStore.progress + '%' }"></div>
        </div>
        <span class="scan-pct">{{ scanStore.progress }}%</span>
      </div>

      <!-- Platesolve Banner -->
      <div v-if="platesolveStore.state.running" class="scan-banner">
        <Globe :size="16" style="color: var(--accent2); flex-shrink: 0;" />
        <span class="scan-text">{{ platesolveStore.phaseLabel }}</span>
        <div class="progress-bar-bg">
          <div class="progress-bar-fill" :style="{ width: platesolveStore.progress + '%', background: 'linear-gradient(90deg, var(--accent2), var(--accent))' }"></div>
        </div>
        <span class="scan-pct">{{ platesolveStore.progress }}%</span>
      </div>

      <!-- Analyse Banner -->
      <div v-if="analyseStore.state.running" class="scan-banner">
        <Activity :size="16" style="color: var(--accent2); flex-shrink: 0;" />
        <span class="scan-text">{{ analyseStore.phaseLabel }}</span>
        <div class="progress-bar-bg">
          <div class="progress-bar-fill" :style="{ width: analyseStore.progress + '%', background: 'linear-gradient(90deg, var(--accent), var(--accent2))' }"></div>
        </div>
        <span class="scan-pct">{{ analyseStore.progress }}%</span>
      </div>

      <!-- Identify Banner -->
      <div v-if="identifyStore.state.running" class="scan-banner">
        <Target :size="16" style="color: var(--accent); flex-shrink: 0;" />
        <span class="scan-text">{{ identifyStore.phaseLabel }}</span>
        <div class="progress-bar-bg">
          <div class="progress-bar-fill" :style="{ width: identifyStore.progress + '%', background: 'linear-gradient(90deg, var(--accent2), var(--accent))' }"></div>
        </div>
        <span class="scan-pct">{{ identifyStore.progress }}%</span>
      </div>

      <main class="content-area">
        <RouterView />
      </main>
    </div>
  </div>
</template>
