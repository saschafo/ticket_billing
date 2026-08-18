// Formatierung nach der aktuellen Oberflächensprache. Die Sprache wird
// hereingereicht statt hier aus i18n gezogen, damit die Funktionen ohne
// Vue-Kontext (Tests, Hilfsskripte) benutzbar bleiben.

export function formatDate(value, locale = 'de') {
  if (!value) return '—'
  const d = new Date(String(value).replace(' ', 'T'))
  if (Number.isNaN(d.getTime())) return String(value)
  return d.toLocaleDateString(locale, { day: '2-digit', month: '2-digit', year: 'numeric' })
}

export function formatDateTime(value, locale = 'de') {
  if (!value) return '—'
  const d = new Date(String(value).replace(' ', 'T'))
  if (Number.isNaN(d.getTime())) return String(value)
  return d.toLocaleString(locale, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * HTML in reinen Text verwandeln.
 *
 * Ticketbeschreibungen können aus eingehenden E-Mails stammen, also aus einer
 * Quelle, die niemand kontrolliert. Solcher Inhalt wird hier bewusst NICHT
 * per v-html gerendert — ein präpariertes Mail-HTML liefe sonst im Browser
 * des Bearbeiters. Formatierung geht dabei verloren; das ist der Preis.
 *
 * Soll die Formatierung erhalten bleiben, gehört serverseitiges Bereinigen
 * gegen eine Positivliste davor (etwa bleach), nicht ein Filter im Browser.
 */
export function stripHtml(value) {
  if (!value) return ''
  return String(value)
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/(p|div|li|tr|h[1-6])>/gi, '\n')
    .replace(/<[^>]*>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

/** Dezimalstunden als "1:45 h" — im Arbeitsalltag leichter zu lesen als 1,75. */
export function formatHours(value) {
  const hours = Number(value || 0)
  if (!hours) return '0:00'
  const total = Math.round(hours * 60)
  const h = Math.floor(total / 60)
  const m = total % 60
  return `${h}:${String(m).padStart(2, '0')}`
}

/**
 * Gegenstück zu formatHours: liest "1:45", "1,75" und "1.75" als Stunden.
 *
 * Beide Schreibweisen zuzulassen ist kein Luxus — im Bestätigungsdialog steht
 * die gemessene Dauer als "1:45", und wer sie korrigiert, tippt mal so und mal
 * so. Bei Unsinn kommt NaN zurück; das Feld gilt dann als ungültig, statt
 * stillschweigend als null durchzurutschen.
 */
export function parseHours(value) {
  if (value === null || value === undefined) return NaN
  const text = String(value).trim().replace(',', '.')
  if (!text) return NaN

  if (text.includes(':')) {
    const [h, m] = text.split(':')
    const hours = Number(h || 0)
    const minutes = Number(m || 0)
    if (!Number.isFinite(hours) || !Number.isFinite(minutes) || minutes >= 60) return NaN
    return hours + minutes / 60
  }

  const num = Number(text)
  return Number.isFinite(num) ? num : NaN
}
