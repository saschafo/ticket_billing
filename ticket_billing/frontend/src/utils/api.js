import axios from 'axios'

// Dünne Hülle um Frappes /api/method-Endpunkt. Zwei Dinge nimmt sie ab: den
// CSRF-Token an jedem Request und das Auspacken von Frappes Fehlerformaten,
// damit im UI eine lesbare — und vom Server bereits übersetzte — Meldung
// ankommt.
const csrf = () =>
  window.csrf_token || (document.cookie.match(/csrf_token=([^;]+)/) || [])[1] || ''

const client = axios.create({ baseURL: '/api/method/' })

client.interceptors.request.use((cfg) => {
  cfg.headers['X-Frappe-CSRF-Token'] = csrf()
  return cfg
})

function extractMessage(data, fallback) {
  // frappe.throw(_("...")) landet hier — der Text ist serverseitig übersetzt.
  if (data?._server_messages) {
    try {
      const msgs = JSON.parse(data._server_messages)
      const first = JSON.parse(msgs[0])
      return String(first.message || first).replace(/<[^>]*>/g, '')
    } catch {
      /* weiter unten */
    }
  }

  if (data?.exc) {
    try {
      const lines = JSON.parse(data.exc)
      const last = Array.isArray(lines) ? lines[lines.length - 1] : lines
      return String(last).split(':').pop().trim()
    } catch {
      /* weiter unten */
    }
  }

  if (data?.message && typeof data.message === 'string') return data.message

  return fallback
}

/**
 * Rückgabewert aus Frappes Antwortkörper holen.
 *
 * Frappe legt den Rückgabewert unter "message" ab. Gibt eine Methode aber
 * None zurück, fehlt der Schlüssel ganz und der Körper ist `{}`.
 *
 * Genau daran hing ein Fehler: Wer "kein Wert" auf den Körper zurückfallen
 * lässt, bekommt ein leeres Objekt — und das ist truthy. Aus "es läuft kein
 * Timer" wurde so "Timer läuft" mit 0:00, und zwar für jeden Benutzer.
 * Fehlt "message", ist die richtige Antwort null.
 */
function unwrap(body) {
  if (body === null || typeof body !== 'object') return body
  return 'message' in body ? body.message : null
}

client.interceptors.response.use(
  (r) => unwrap(r.data),
  (err) => {
    const status = err.response?.status
    const error = new Error(extractMessage(err.response?.data, err.message))
    error.status = status
    // 403 wird von der Oberfläche gesondert behandelt: Es ist kein Fehler des
    // Nutzers, sondern heißt, dass dieser Bereich für ihn nicht gilt.
    error.isPermissionError = status === 403
    return Promise.reject(error)
  },
)

export const api = {
  call: (method, params = {}) => client.post(method, params),

  // Frappe-Standard
  login: (usr, pwd) => client.post('login', { usr, pwd }),
  logout: () => client.post('logout'),

  // Sitzung und Sprache
  getSessionInfo: () => client.post('ticket_billing.api.session.get_session_info'),
  setUserLanguage: (lang) =>
    client.post('ticket_billing.api.session.set_user_language', { lang }),

  // Tickets
  listTickets: (params) => client.post('ticket_billing.api.tickets.list_tickets', params),
  getTicket: (name) => client.post('ticket_billing.api.tickets.get_ticket', { name }),
  createTicket: (params) => client.post('ticket_billing.api.tickets.create_ticket', params),
  updateTicket: (params) => client.post('ticket_billing.api.tickets.update_ticket', params),
  reassignTicket: (name, employee) =>
    client.post('ticket_billing.api.tickets.reassign_ticket', { name, employee }),
  getDepartmentMembers: (department) =>
    client.post('ticket_billing.api.tickets.get_department_members', { department }),
  getFormOptions: () => client.post('ticket_billing.api.tickets.get_form_options'),
  replyToTicket: (params) => client.post('ticket_billing.api.tickets.reply_to_ticket', params),
  fetchMail: () => client.post('ticket_billing.api.mail.fetch_mail'),

  // Zeiterfassung
  getRunningTimer: () => client.post('ticket_billing.api.timesheet.get_running_timer'),
  startTimer: (issue, note) =>
    client.post('ticket_billing.api.timesheet.start_timer', { issue, note }),
  stopTimer: (description, discard = 0) =>
    client.post('ticket_billing.api.timesheet.stop_timer', { description, discard }),
  logTime: (params) => client.post('ticket_billing.api.timesheet.log_time', params),
  getTimeEntries: (issue) =>
    client.post('ticket_billing.api.timesheet.get_entries_for_issue', { issue }),

  // Demo
  getDemoStatus: () => client.post('ticket_billing.demo.get_demo_status'),
  demoLogin: (user) => client.post('ticket_billing.demo.demo_login', { user }),

  // Zeiterfassung: Entwürfe und Freigabe
  listMyTimeEntries: (params) =>
    client.post('ticket_billing.api.approvals.list_my_entries', params),
  updateTimeEntry: (params) =>
    client.post('ticket_billing.api.approvals.update_time_entry', params),
  deleteTimeEntry: (name) =>
    client.post('ticket_billing.api.approvals.delete_time_entry', { name }),
  listPendingEntries: (params) =>
    client.post('ticket_billing.api.approvals.list_pending', params),
  submitTimeEntries: (names) =>
    client.post('ticket_billing.api.approvals.submit_time_entries', {
      names: JSON.stringify(names),
    }),

  // Auswertungen
  getMyStats: () => client.post('ticket_billing.api.dashboard.get_my_stats'),
  getTeamStats: (department, days) =>
    client.post('ticket_billing.api.dashboard.get_team_stats', { department, days }),
  getCompanyStats: (days) =>
    client.post('ticket_billing.api.dashboard.get_company_stats', { days }),
  getManagementKpis: (days) =>
    client.post('ticket_billing.api.kpi.get_management_kpis', { days }),
  getDepartmentKpis: (department, days) =>
    client.post('ticket_billing.api.kpi.get_department_kpis', { department, days }),
}

export function useApi() {
  return api
}
