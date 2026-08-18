import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '@/utils/api'
import { useTimerStore } from '@/stores/timer'

// Wer ist angemeldet, mit welcher Rolle und in welcher Abteilung.
//
// Wichtig: Was hier steht, steuert ausschließlich die Darstellung — welche
// Menüpunkte es gibt und welcher Bereich zuerst kommt. Ob jemand Daten sehen
// darf, entscheidet der Server bei jedem Aufruf neu. Wer diese Werte im
// Browser manipuliert, sieht deshalb höchstens leere Ansichten.
export const useSessionStore = defineStore('session', () => {
  const user = ref(window.frappe_session_user || 'Guest')
  const info = ref(null)
  const loading = ref(false)
  const loaded = ref(false)

  const isLoggedIn = computed(() => !!user.value && user.value !== 'Guest')
  const isEmployee = computed(() => !!info.value?.is_employee)
  const isLead = computed(() => !!info.value?.is_lead)
  const isManagement = computed(() => !!info.value?.is_management)
  const department = computed(() => info.value?.department || null)
  const employee = computed(() => info.value?.employee || null)
  const fullName = computed(() => info.value?.full_name || user.value)

  // access_level 'all' heißt: darf abteilungsübergreifend lesen. Das trifft
  // neben der Geschäftsführung auch auf Administrator und System Manager zu.
  const seesEverything = computed(() => info.value?.access_level === 'all')

  /**
   * Erfasst dieser Benutzer überhaupt Zeit?
   *
   * Nur wer Tickets bearbeitet und einen Mitarbeiterdatensatz hat. Für die
   * Geschäftsführung ist ein Timer gegenstandslos — auch die Aussage "läuft
   * gerade keiner" ist dort keine Information, sondern nur Fläche, die
   * Fragen aufwirft.
   */
  const canTrackTime = computed(() => isEmployee.value && !!employee.value)

  /**
   * Bereiche, die dieser Nutzer zu sehen bekommt.
   *
   * Neben der Rolle zählt, ob die Voraussetzung überhaupt da ist: "Meine
   * Tickets" ohne Mitarbeiterdatensatz und "Abteilung" ohne Abteilung sind
   * leere Hüllen. Das trifft besonders den Administrator — Frappe gibt ihm
   * implizit jede Rolle, ohne dass er deshalb Mitarbeiter wäre.
   */
  const areas = computed(() => {
    const list = []
    if (isEmployee.value && employee.value) list.push('my-tickets')
    if (isLead.value && department.value) list.push('department')
    // Ohne den zweiten Teil liefe ein Administrator in "kein Zugriff",
    // obwohl der Server ihm die Auswertung sehr wohl liefert.
    if (isManagement.value || seesEverything.value) list.push('management')
    return list
  })

  /** Wohin nach der Anmeldung — der engste sinnvolle Bereich zuerst. */
  const homeRoute = computed(() => {
    const available = areas.value
    for (const name of ['my-tickets', 'department', 'management']) {
      if (available.includes(name)) return { name }
    }
    return { name: 'no-access' }
  })

  async function load(force = false) {
    if (loaded.value && !force) return info.value

    loading.value = true
    try {
      const data = await api.getSessionInfo()
      info.value = data
      user.value = data?.user || 'Guest'
      loaded.value = true
      return data
    } catch {
      info.value = null
      user.value = 'Guest'
      loaded.value = true
      return null
    } finally {
      loading.value = false
    }
  }

  async function login(usr, pwd) {
    await api.login(usr, pwd)
    // force: Die beim Seitenaufbau gesetzten Werte sind nach dem Login
    // veraltet — ohne das behielte man die Rollen des vorigen Nutzers.
    await load(true)
  }

  async function logout() {
    try {
      await api.logout()
    } finally {
      // Timerzustand mit abräumen. Der Neuaufbau der Seite unten erledigt das
      // ohnehin -- aber wer sich das darauf verlässt, baut eine Falle für den
      // Tag, an dem jemand ohne Neuladen den Benutzer wechselt.
      useTimerStore().setRunning(null)
      info.value = null
      user.value = 'Guest'
      loaded.value = false
      window.location.href = '/ticketbilling'
    }
  }

  return {
    user, info, loading, loaded,
    isLoggedIn, isEmployee, isLead, isManagement, canTrackTime,
    department, employee, fullName, areas, homeRoute,
    load, login, logout,
  }
})
