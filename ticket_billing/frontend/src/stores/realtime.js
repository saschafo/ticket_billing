import { defineStore } from 'pinia'
import { ref } from 'vue'
import { io } from 'socket.io-client'

// Anbindung an Frappes Socket.IO-Dienst.
//
// Zwei Fallstricke, die hier gelöst sind:
//
// 1. Frappe sendet in den Namespace "/<sitename>". Der interne Site-Name muss
//    nicht der Domain entsprechen, unter der die Anwendung läuft — er kommt
//    deshalb aus get_session_info() und nicht aus der URL.
// 2. Die Authentifizierung vergleicht serverseitig den Hostnamen aus "Host"
//    mit dem aus "Origin". Damit das aufgeht, muss nginx das echte Origin
//    durchreichen (siehe resources/core/nginx/nginx-template.conf im
//    Docker-Repo). Sonst verbindet sich hier nichts, ohne dass die Oberfläche
//    es merkt.
//
// Die Ereignisse selbst sind reine Auslöser: Die Oberfläche lädt daraufhin
// über die normalen, rechtegeprüften Endpunkte nach. Was im Ereignis steht,
// wird nie ungeprüft angezeigt.
export const useRealtimeStore = defineStore('realtime', () => {
  const connected = ref(false)
  const enabled = ref(true)

  let socket = null
  const handlers = new Map()

  function emitLocal(event, payload) {
    for (const fn of handlers.get(event) || []) {
      try {
        fn(payload)
      } catch {
        // Ein fehlerhafter Abonnent darf die übrigen nicht mitreißen.
      }
    }
  }

  function connect(sitename) {
    if (socket || !sitename) return

    socket = io(`${window.location.origin}/${sitename}`, {
      path: '/socket.io/',
      withCredentials: true,
      // Ohne Begrenzung versucht socket.io endlos weiter. Bei dauerhaft
      // fehlender Verbindung bleibt die Anwendung bedienbar, nur eben mit
      // manuellem Aktualisieren.
      reconnectionAttempts: 10,
      reconnectionDelayMax: 10000,
    })

    socket.on('connect', () => (connected.value = true))
    socket.on('disconnect', () => (connected.value = false))
    socket.on('connect_error', () => (connected.value = false))

    socket.on('ticket_billing:ticket', (data) => emitLocal('ticket', data))
    socket.on('ticket_billing:timer', (data) => emitLocal('timer', data))
  }

  function disconnect() {
    socket?.disconnect()
    socket = null
    connected.value = false
  }

  /** Ereignis abonnieren. Gibt die Abmeldefunktion zurück. */
  function on(event, fn) {
    if (!handlers.has(event)) handlers.set(event, new Set())
    handlers.get(event).add(fn)
    return () => handlers.get(event)?.delete(fn)
  }

  return { connected, enabled, connect, disconnect, on }
})
