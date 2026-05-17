<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter, RouterView, RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Telescope, Target, Camera, ScanLine, Search, Settings as SettingsIcon, HelpCircle, Globe, Sun, Moon, Activity, LayoutDashboard, List, Crosshair, Menu, X, Languages, Bookmark } from 'lucide-vue-next'
import { useScanStore } from '@/stores/scan'
import { usePlatesolveStore } from '@/stores/platesolve'
import { useAnalyseStore } from '@/stores/analyse'
import { useIdentifyStore } from '@/stores/identify'
import { useThemeStore } from '@/stores/theme'
import { useApiStore } from '@/stores/api'
import { i18n, setLocale } from '@/i18n'
import { frontendVersion } from '@/version'

const scanStore = useScanStore()
const platesolveStore = usePlatesolveStore()
const analyseStore = useAnalyseStore()
const identifyStore = useIdentifyStore()
const themeStore = useThemeStore()
const apiStore = useApiStore()

const { t } = useI18n()
const router = useRouter()
const sidebarOpen = ref(false)
const currentLocale = ref(i18n.global.locale.value)
const buildInfo = ref('')
const versionMismatch = ref(false)
const backendVersion = ref('')

function switchLocale() {
  const next = currentLocale.value === 'de' ? 'en' : 'de'
  setLocale(next)
  currentLocale.value = next
}

async function loadBuildInfo() {
  try {
    const health = await apiStore.fetch<{ version: string; build: string }>('/health')
    buildInfo.value = health.build
    backendVersion.value = health.version
    if (health.version !== frontendVersion) {
      versionMismatch.value = true
    }
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
  <!-- Version mismatch overlay -->
  <div v-if="versionMismatch" class="version-mismatch">
    <div class="version-mismatch-card">
      <h2>⚠ Version mismatch</h2>
      <p>Frontend v{{ frontendVersion }} kann nicht mit Backend v{{ backendVersion }} kommunizieren.</p>
      <p style="margin-top: 8px; font-size: 13px; color: var(--text-muted);">
        Bitte Seite neu laden oder Server aktualisieren.
      </p>
    </div>
  </div>

  <div v-else class="app-layout">
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
        <div class="version">{{ t('nav.version') }}</div>
        <div class="build" v-if="buildInfo">{{ buildInfo }}</div>
      </div>
      <nav class="sidebar-nav">
        <RouterLink to="/" class="nav-item" @click="closeSidebar">
          <LayoutDashboard :size="18" />
          <span class="nav-label">{{ t('nav.dashboard') }}</span>
        </RouterLink>
        <RouterLink to="/search" class="nav-item" @click="closeSidebar">
          <Search :size="18" />
          <span class="nav-label">{{ t('nav.search') }}</span>
        </RouterLink>
        <RouterLink to="/targets" class="nav-item" @click="closeSidebar">
          <Target :size="18" />
          <span class="nav-label">{{ t('nav.targets') }}</span>
        </RouterLink>
        <RouterLink to="/sessions" class="nav-item" @click="closeSidebar">
          <List :size="18" />
          <span class="nav-label">{{ t('nav.sessions') }}</span>
        </RouterLink>
        <RouterLink to="/equipment" class="nav-item" @click="closeSidebar">
          <Camera :size="18" />
          <span class="nav-label">{{ t('nav.equipment') }}</span>
        </RouterLink>

        <div class="nav-separator"></div>

        <RouterLink to="/scan" class="nav-item" @click="closeSidebar">
          <ScanLine :size="18" />
          <span class="nav-label">{{ t('nav.scan') }}</span>
        </RouterLink>
        <RouterLink to="/platesolve" class="nav-item" @click="closeSidebar">
          <Globe :size="18" />
          <span class="nav-label">{{ t('nav.platesolve') }}</span>
        </RouterLink>
        <RouterLink to="/identify" class="nav-item" @click="closeSidebar">
          <Crosshair :size="18" />
          <span class="nav-label">{{ t('nav.identify') }}</span>
        </RouterLink>
        <RouterLink to="/analyse" class="nav-item" @click="closeSidebar">
          <Activity :size="18" />
          <span class="nav-label">{{ t('nav.analyse') }}</span>
        </RouterLink>

        <div class="nav-separator"></div>

        <RouterLink to="/settings" class="nav-item" @click="closeSidebar">
          <SettingsIcon :size="18" />
          <span class="nav-label">{{ t('nav.settings') }}</span>
        </RouterLink>
        <RouterLink to="/name-preferences" class="nav-item" @click="closeSidebar">
          <Bookmark :size="18" />
          <span class="nav-label">Objektnamen</span>
        </RouterLink>
        <RouterLink to="/help" class="nav-item" @click="closeSidebar">
          <HelpCircle :size="18" />
          <span class="nav-label">{{ t('nav.help') }}</span>
        </RouterLink>
      </nav>
      <div class="sidebar-footer">
        <button class="nav-item" @click="toggleTheme">
          <Sun v-if="!themeStore.isDark" :size="18" />
          <Moon v-else :size="18" />
          <span class="nav-label">{{ themeStore.isDark ? t('nav.theme_dark') : t('nav.theme_light') }}</span>
        </button>
        <button class="nav-item" @click="switchLocale" style="width:100%;border:none;background:none;">
          <Languages :size="18" />
          <span class="nav-label">{{ currentLocale === 'de' ? 'English' : 'Deutsch' }}</span>
        </button>
      </div>
    </aside>

    <div class="main-content">
      <!-- Top bar for mobile -->
      <div class="top-bar">
        <button class="hamburger" @click="sidebarOpen = !sidebarOpen" aria-label="Menü öffnen">
          <Menu :size="22" />
        </button>
        <span class="top-bar-title">{{ t('topbar.title') }}</span>
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
