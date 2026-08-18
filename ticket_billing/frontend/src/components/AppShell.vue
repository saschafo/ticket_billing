<!--
  Rahmen der Anwendung. Die Navigation zeigt nur Bereiche, für die der Nutzer
  eine Rolle hat — was er tatsächlich abrufen darf, entscheidet der Server.
-->
<template>
  <div class="min-h-screen flex flex-col">
    <header class="bg-white border-b border-slate-200 sticky top-0 z-20">
      <div class="mx-auto px-4" :class="ui.containerClass">
        <!-- Die Navigation nimmt den freien Platz und darf notfalls waagerecht
             scrollen. Vorher konnte sie nicht schrumpfen und schob sich bei
             fünf Menüpunkten über den rechten Block. -->
        <div class="h-14 flex items-center gap-3">
          <span class="font-semibold text-slate-900 shrink-0">{{ t('app.name') }}</span>

          <nav class="hidden sm:flex items-center gap-1 flex-1 min-w-0 overflow-x-auto no-scrollbar">
            <RouterLink
              v-for="item in navItems"
              :key="item.name"
              :to="{ name: item.name }"
              class="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-sm font-medium text-slate-600 whitespace-nowrap hover:bg-slate-100 hover:text-slate-900 transition-colors"
              active-class="!bg-slate-100 !text-slate-900"
            >
              <component :is="item.icon" :size="17" :stroke-width="1.8" class="shrink-0" />
              {{ t(item.label) }}
            </RouterLink>
          </nav>

          <div class="flex items-center gap-2 shrink-0 ml-auto">
            <!-- Nur der Name statt "Angemeldet als ...": Wer eingeloggt ist,
                 sagt das Symbol; der Satz davor kostete nur Platz, den die
                 Navigation braucht. -->
            <span
              class="hidden xl:inline-flex items-center gap-1.5 text-sm text-slate-500 max-w-[11rem]"
              :title="t('session.logged_in_as', { user: session.fullName })"
            >
              <IconUserCircle :size="17" :stroke-width="1.8" class="shrink-0 text-slate-400" />
              <span class="truncate">{{ session.fullName }}</span>
            </span>
            <WidthToggle />
            <LanguageSwitcher />
            <button class="btn-secondary btn-sm" @click="session.logout()">
              <IconLogout :size="15" :stroke-width="1.8" />
              <!-- Bei knappem Platz nur das Symbol: Die Beschriftung ist neben
                   einem eindeutigen Icon entbehrlich, der Menuepunkt daneben
                   nicht. -->
              <span class="hidden xl:inline">{{ t('nav.logout') }}</span>
            </button>
          </div>
        </div>

        <!-- Auf schmalen Geräten wandert die Navigation in eine zweite Zeile,
             damit sie nicht mit Name und Sprachwahl um den Platz kämpft. -->
        <nav v-if="navItems.length > 1" class="sm:hidden flex items-center gap-1 pb-2 -mt-1">
          <RouterLink
            v-for="item in navItems"
            :key="item.name"
            :to="{ name: item.name }"
            class="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-sm font-medium text-slate-600 whitespace-nowrap hover:bg-slate-100"
            active-class="!bg-slate-100 !text-slate-900"
          >
            <component :is="item.icon" :size="16" :stroke-width="1.8" class="shrink-0" />
            {{ t(item.label) }}
          </RouterLink>
        </nav>
      </div>

      <TimerBar />
    </header>

    <main class="flex-1">
      <div class="mx-auto px-4 py-6" :class="ui.containerClass">
        <RouterView />
      </div>
    </main>

    <footer class="border-t border-slate-200 py-4">
      <div class="mx-auto px-4 text-xs text-slate-400" :class="ui.containerClass">
        {{ t('app.tagline') }}
      </div>
    </footer>

    <!-- Rückmeldungen -->
    <Teleport to="body">
      <div class="fixed bottom-4 right-4 z-50 flex flex-col gap-2 items-end pointer-events-none">
        <TransitionGroup name="toast">
          <div
            v-for="item in toast.items"
            :key="item.id"
            class="pointer-events-auto px-4 py-2.5 rounded-lg shadow-lg text-sm text-white max-w-sm"
            :class="{
              'bg-emerald-600': item.type === 'success',
              'bg-red-600': item.type === 'error',
              'bg-slate-700': item.type === 'info',
            }"
            @click="toast.remove(item.id)"
          >
            {{ item.text }}
          </div>
        </TransitionGroup>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  IconChartPie,
  IconChecklist,
  IconClock,
  IconLogout,
  IconReportAnalytics,
  IconTicket,
  IconUserCircle,
  IconUsersGroup,
} from '@tabler/icons-vue'
import LanguageSwitcher from '@/components/LanguageSwitcher.vue'
import WidthToggle from '@/components/WidthToggle.vue'
import TimerBar from '@/components/TimerBar.vue'
import { useSessionStore } from '@/stores/session'
import { useToastStore } from '@/stores/toast'
import { useRealtimeStore } from '@/stores/realtime'
import { useTimerStore } from '@/stores/timer'
import { useUiStore } from '@/stores/ui'

const { t } = useI18n()
const session = useSessionStore()
const toast = useToastStore()
const realtime = useRealtimeStore()
const timer = useTimerStore()
const ui = useUiStore()

let offTimer = null

onMounted(() => {
  // Der Site-Name kommt aus der Sitzung, nicht aus der URL -- Frappe sendet
  // in den Namespace "/<sitename>", und der muss nicht der Domain
  // entsprechen, unter der die Anwendung erreichbar ist.
  realtime.connect(session.info?.sitename)

  // Wer keine Zeit erfasst, braucht weder Abfrage noch Abonnement.
  if (!session.canTrackTime) return

  timer.refresh()

  // Timerzustand von einem anderen Gerät übernehmen. Ohne das liefe hier
  // weiter eine Uhr, die längst gestoppt wurde.
  offTimer = realtime.on('timer', (data) => timer.setRunning(data?.timer))
})

onBeforeUnmount(() => {
  offTimer?.()
  timer.stopTicking()
})

const ALL_ITEMS = [
  { name: 'my-tickets', label: 'nav.my_tickets', area: 'my-tickets', icon: IconTicket },
  { name: 'my-times', label: 'nav.my_times', area: 'my-tickets', icon: IconClock },
  { name: 'department', label: 'nav.department', area: 'department', icon: IconUsersGroup },
  { name: 'department-kpi', label: 'nav.dept_kpi', area: 'department', icon: IconReportAnalytics },
  { name: 'approvals', label: 'nav.approvals', area: 'department', icon: IconChecklist },
  { name: 'management', label: 'nav.management', area: 'management', icon: IconChartPie },
]

const navItems = computed(() => ALL_ITEMS.filter((i) => session.areas.includes(i.area)))
</script>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.25s ease;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(0.5rem);
}
</style>
