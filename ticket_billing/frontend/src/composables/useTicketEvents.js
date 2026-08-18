import { onBeforeUnmount, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRealtimeStore } from '@/stores/realtime'
import { useSessionStore } from '@/stores/session'
import { useToastStore } from '@/stores/toast'

/**
 * Auf Ticketänderungen reagieren, die andere ausgelöst haben.
 *
 * Das Ereignis ist nur der Auslöser — nachgeladen wird über die normalen,
 * rechtegeprüften Endpunkte. Was im Ereignis steht, landet nie ungeprüft in
 * der Liste.
 *
 * Gesammelt statt sofort: Eine Umverteilung erzeugt Ereignisse für mehrere
 * Beteiligte, und ein Stapelvorgang mehrere hintereinander. Ohne die kurze
 * Sammelfrist liefe für jedes einzelne eine eigene Abfrage.
 *
 * @param {Function} reload  wird nach dem Sammeln aufgerufen
 */
export function useTicketEvents(reload) {
  const realtime = useRealtimeStore()
  const session = useSessionStore()
  const toast = useToastStore()
  const { t } = useI18n()

  let off = null
  let pending = null

  onMounted(() => {
    off = realtime.on('ticket', (data) => {
      // Eine Zuweisung an mich ist eine Nachricht, kein stilles Nachladen --
      // sonst taucht das Ticket kommentarlos in der Liste auf.
      const mine = data?.assignee && data.assignee === session.employee
      // Eine Kundenantwort ist der Fall, den man sonst uebersieht: Sie
      // aendert die Liste nur unauffaellig.
      if (data?.kind === 'reply' && mine) {
        toast.info(t('ticket.new_reply_on', { subject: data.subject || data.name }))
      }

      if (data?.kind === 'assigned' && mine && data.by !== session.user) {
        toast.info(t('time.assigned_to_you', { subject: data.subject || data.name }))
      }

      clearTimeout(pending)
      pending = setTimeout(reload, 400)
    })
  })

  onBeforeUnmount(() => {
    off?.()
    clearTimeout(pending)
  })
}
