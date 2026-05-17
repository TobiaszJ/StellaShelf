import { createI18n } from 'vue-i18n'
import de from '@/locales/de.json'
import en from '@/locales/en.json'

const savedLocale = localStorage.getItem('stellashelf-locale')
const systemLocale = navigator.language?.startsWith('de') ? 'de' : 'en'

export const i18n = createI18n({
  legacy: false,
  locale: savedLocale || systemLocale,
  fallbackLocale: 'en',
  messages: { de, en },
})

export function setLocale(locale: 'de' | 'en') {
  i18n.global.locale.value = locale
  localStorage.setItem('stellashelf-locale', locale)
}
