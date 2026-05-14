<script setup lang="ts">
import { RouterView, RouterLink } from 'vue-router'
import { Telescope, Target, Camera, FolderOpen, ScanLine } from 'lucide-vue-next'
import { useScanStore } from '@/stores/scan'

const scanStore = useScanStore()

// Start polling on mount
scanStore.fetchStatus()
if (scanStore.state.running) {
  scanStore.startPolling()
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
        <div class="version">v0.2.0</div>
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
        <RouterLink to="/scan" class="nav-item">
          <ScanLine :size="18" />
          Scan
        </RouterLink>
      </nav>
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

      <main class="content-area">
        <RouterView />
      </main>
    </div>
  </div>
</template>
