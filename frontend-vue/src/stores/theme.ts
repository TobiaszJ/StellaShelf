import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useThemeStore = defineStore('theme', () => {
  const theme = ref<'light' | 'dark' | 'system'>('system')

  function init() {
    const stored = localStorage.getItem('stellashelf-theme') as 'light' | 'dark' | 'system' | null
    if (stored) {
      theme.value = stored
    }
    applyTheme()
  }

  function applyTheme() {
    let resolved: 'light' | 'dark'
    if (theme.value === 'system') {
      resolved = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
    } else {
      resolved = theme.value
    }
    document.documentElement.setAttribute('data-theme', resolved)
  }

  function setTheme(newTheme: 'light' | 'dark' | 'system') {
    theme.value = newTheme
    localStorage.setItem('stellashelf-theme', newTheme)
    applyTheme()
  }

  // Listen for system theme changes when in 'system' mode
  if (typeof window !== 'undefined') {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      if (theme.value === 'system') applyTheme()
    })
  }

  const isDark = ref(true)

  watch(theme, (t) => {
    isDark.value = t === 'dark' || (t === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)
  }, { immediate: true })

  return { theme, isDark, init, setTheme }
})
