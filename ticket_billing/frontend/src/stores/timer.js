import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '@/utils/api'

// Der laufende Timer, einmal für die ganze Anwendung.
//
// Die Anzeige zählt rein im Browser hoch — ein Intervall, das nur eine Zahl
// neu berechnet. Es wird dafür nichts vom Server geholt: Der Startzeitpunkt
// steht fest, alles andere ist Rechnen. Nachgeladen wird nur, wenn sich
// tatsächlich etwas ändert (eigene Aktion oder Realtime-Ereignis von einem
// anderen Gerät).
export const useTimerStore = defineStore('timer', () => {
  const running = ref(null)
  const busy = ref(false)
  const now = ref(Date.now())

  // Laufzeit, die der Server beim letzten Abruf gemeldet hat, und der
  // Browser-Zeitpunkt dieses Abrufs. Weitergezählt wird ab da nur noch mit
  // der Differenz zweier Browser-Zeiten.
  const baseHours = ref(0)
  const baseAt = ref(Date.now())

  let ticking = null

  /**
   * Laufzeit = was der Server sagte, plus was seither vergangen ist.
   *
   * Nicht aus start_time rechnen: Frappe liefert einen Zeitstempel ohne
   * Zonenangabe, und der Browser liest ihn als seine eigene Zeit. Sitzt der
   * Nutzer in einer anderen Zone als die Site -- oder geht seine Uhr falsch --
   * kommt eine Laufzeit heraus, die um genau diese Differenz daneben liegt.
   * So gerechnet spielt beides keine Rolle.
   */
  const elapsedHours = computed(() => {
    if (!running.value) return 0
    return Math.max(0, baseHours.value + (now.value - baseAt.value) / 3_600_000)
  })

  const warningHours = computed(() => Number(running.value?.warning_hours) || 4)

  /** Läuft der Timer ungewöhnlich lange? Meist heißt das: vergessen zu stoppen. */
  const isWarning = computed(() => !!running.value && elapsedHours.value > warningHours.value)

  const isRunningOn = (issue) => running.value?.issue === issue

  function startTicking() {
    if (ticking) return
    ticking = setInterval(() => (now.value = Date.now()), 1000)
  }

  function stopTicking() {
    clearInterval(ticking)
    ticking = null
  }

  function setRunning(value) {
    running.value = value || null
    baseHours.value = Number(value?.elapsed_hours) || 0
    baseAt.value = Date.now()
    now.value = baseAt.value

    if (running.value) startTicking()
    else stopTicking()
  }

  async function refresh() {
    try {
      setRunning(await api.getRunningTimer())
    } catch {
      setRunning(null)
    }
  }

  async function start(issue, note = null) {
    busy.value = true
    try {
      setRunning(await api.startTimer(issue, note))
      return running.value
    } finally {
      busy.value = false
    }
  }

  async function stop({ hours = null, description = null, discard = false } = {}) {
    busy.value = true
    try {
      const result = await api.stopTimer(description, discard ? 1 : 0, hours)
      setRunning(null)
      return result
    } finally {
      busy.value = false
    }
  }

  return {
    running, busy, elapsedHours, warningHours, isWarning, isRunningOn,
    setRunning, refresh, start, stop, stopTicking,
  }
})
