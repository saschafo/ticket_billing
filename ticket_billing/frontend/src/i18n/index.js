import { createI18n } from 'vue-i18n'
import { api } from '@/utils/api'
import de from './locales/de.json'
import en from './locales/en.json'

// Eine neue Sprache ergänzen: Datei unter locales/ anlegen, hier importieren
// und in messages sowie AVAILABLE_LOCALES eintragen. Der Sprachumschalter
// speist sich aus dieser Liste, es ist also keine weitere Stelle zu ändern.
export const AVAILABLE_LOCALES = [
  { code: 'de', label: 'Deutsch' },
  { code: 'en', label: 'English' },
]

export const DEFAULT_LOCALE = 'de'

const STORAGE_KEY = 'ticket_billing.locale'
const known = AVAILABLE_LOCALES.map((l) => l.code)

/**
 * Startsprache, in dieser Reihenfolge:
 *   1. zuletzt im Browser gewählte Sprache
 *   2. die von Frappe aufgelöste Sitzungssprache (window.frappe_boot_lang aus
 *      www/ticketbilling.html) — so stimmen Server- und Oberflächensprache
 *      überein, und serverseitige Fehlermeldungen passen zur Anzeige
 *   3. Standardsprache
 * Frappe liefert teils Regionalkürzel wie "de-CH"; davon zählt der Teil vor
 * dem Bindestrich, sofern er bekannt ist.
 */
function resolveStartLocale() {
  const stored = (() => {
    try {
      return localStorage.getItem(STORAGE_KEY)
    } catch {
      return null
    }
  })()
  if (stored && known.includes(stored)) return stored

  const boot = (window.frappe_boot_lang || '').split('-')[0]
  if (boot && known.includes(boot)) return boot

  return DEFAULT_LOCALE
}

const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: resolveStartLocale(),
  fallbackLocale: DEFAULT_LOCALE,
  messages: { de, en },
})

/**
 * Sprache umschalten.
 *
 * Drei Ebenen, damit die Wahl überall gilt: vue-i18n für die Oberfläche,
 * localStorage für den nächsten Besuch, und der Frappe-Benutzer, damit auch
 * serverseitig erzeugte Texte — Fehlermeldungen, E-Mails, PDFs — folgen.
 * Die Speicherung am Benutzer darf fehlschlagen (Gast, Netz weg), ohne dass
 * die Oberfläche stehen bleibt.
 */
export async function setLocale(code) {
  if (!known.includes(code) || i18n.global.locale.value === code) return

  i18n.global.locale.value = code
  document.documentElement.setAttribute('lang', code)

  try {
    localStorage.setItem(STORAGE_KEY, code)
  } catch {
    // privater Modus o. Ä. — gilt dann nur für diese Sitzung
  }

  try {
    await api.setUserLanguage(code)
  } catch {
    // Nicht angemeldet oder Server nicht erreichbar: Die Oberfläche ist
    // bereits umgeschaltet, mehr ist hier nicht zu retten.
  }
}

export default i18n
