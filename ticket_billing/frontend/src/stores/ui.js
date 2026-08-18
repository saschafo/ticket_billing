import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

// Anzeigeeinstellungen. Rein clientseitig: Ob jemand breit oder zentriert
// arbeitet, geht den Server nichts an und soll auch nach dem Abmelden
// erhalten bleiben -- deshalb localStorage und nicht der Benutzerdatensatz.
const STORAGE_KEY = 'ticket_billing.wide'

function read() {
  try {
    return localStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

export const useUiStore = defineStore('ui', () => {
  // Schmal ist der Standard: Wer nichts umstellt, sieht die Anwendung wie
  // bisher, und lange Betreff- oder Notizspalten bleiben in lesbarer
  // Zeilenbreite.
  const wide = ref(read())

  /** Breitenklasse für alle Container der Shell. */
  const containerClass = computed(() => (wide.value ? 'max-w-none' : 'max-w-7xl'))

  function toggle() {
    wide.value = !wide.value
    try {
      localStorage.setItem(STORAGE_KEY, wide.value ? '1' : '0')
    } catch {
      // privater Modus o. Ä. -- gilt dann nur für diese Sitzung
    }
  }

  return { wide, containerClass, toggle }
})
