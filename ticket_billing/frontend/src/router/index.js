import { createRouter, createWebHistory } from 'vue-router'
import AppShell from '@/components/AppShell.vue'
import { useSessionStore } from '@/stores/session'

// Basis "/ticketbilling" — passend zur website_route_rules-Regel in hooks.py.
// Wird eine der beiden Stellen geändert, muss die andere mitwandern, sonst
// landet jeder Reload einer Unterroute im Frappe-404.
const router = createRouter({
  history: createWebHistory('/ticketbilling'),
  routes: [
    {
      path: '/',
      component: AppShell,
      children: [
        {
          path: '',
          name: 'home',
          redirect: () => ({ name: 'my-tickets' }),
        },
        {
          path: 'tickets',
          name: 'my-tickets',
          component: () => import('@/views/MyTicketsView.vue'),
          meta: { area: 'my-tickets' },
        },
        {
          path: 'zeiten',
          name: 'my-times',
          component: () => import('@/views/MyTimesheetsView.vue'),
          meta: { area: 'my-tickets' },
        },
        {
          path: 'abteilung',
          name: 'department',
          component: () => import('@/views/DepartmentView.vue'),
          meta: { area: 'department' },
        },
        {
          path: 'abteilung/kennzahlen',
          name: 'department-kpi',
          component: () => import('@/views/DepartmentKpiView.vue'),
          meta: { area: 'department' },
        },
        {
          path: 'zeiten-buchen',
          name: 'approvals',
          component: () => import('@/views/ApprovalsView.vue'),
          meta: { area: 'department' },
        },
        {
          path: 'auswertung',
          name: 'management',
          component: () => import('@/views/ManagementView.vue'),
          meta: { area: 'management' },
        },
        {
          path: 'kein-zugriff',
          name: 'no-access',
          component: () => import('@/views/NoAccessView.vue'),
        },
      ],
    },
    {
      path: '/anmelden',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
    },
    // Pfad statt Routenname: Der Auffangpfad sammelt den Rest der URL in
    // pathMatch, und ein Ziel per Name uebernimmt diesen Parameter, den
    // es dort nicht gibt -- vue-router verwirft ihn und warnt bei jeder
    // unbekannten Adresse. Mit dem Pfad entsteht die Frage gar nicht.
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

// Der Wächter blendet nur aus, was ohnehin keine Daten liefern würde — die
// eigentliche Absicherung sitzt im Backend. Ohne ihn liefe der Nutzer in
// leere Ansichten und Fehlermeldungen statt in den Bereich, der ihm gehört.
router.beforeEach(async (to) => {
  const session = useSessionStore()
  await session.load()

  if (!session.isLoggedIn) {
    return to.name === 'login' ? true : { name: 'login', query: { weiter: to.fullPath } }
  }

  if (to.name === 'login') return session.homeRoute

  const area = to.meta?.area
  if (area && !session.areas.includes(area)) {
    return session.homeRoute
  }

  return true
})

export default router
