<!-- Bereich A: Was mir zugewiesen ist, plus Zeiterfassung im Detail. -->
<template>
  <div class="space-y-6">
    <div>
      <h1>{{ t('views.my_tickets_title') }}</h1>
      <p class="text-slate-500 mt-1">{{ t('views.my_tickets_subtitle') }}</p>
    </div>

    <div v-if="!session.employee" class="card">
      <div class="card-body text-sm text-amber-800 bg-amber-50 rounded-xl">
        {{ t('session.no_employee') }}
      </div>
    </div>

    <div class="grid grid-cols-2 lg:grid-cols-3 gap-4">
      <StatCard :label="t('stats.open')" :value="stats.open" tone="warn" />
      <StatCard :label="t('stats.closed')" :value="stats.closed" tone="good" />
      <StatCard
        :label="t('stats.hours_7d')"
        :value="formatHours(stats.hours_7d) + ' ' + t('time.hours_short')"
      />
    </div>

    <div class="card">
      <div class="card-header flex flex-wrap items-center gap-3">
        <label class="inline-flex items-center gap-2 text-sm text-slate-600">
          <input v-model="onlyOpen" type="checkbox" class="rounded border-slate-300" />
          {{ t('filter.only_open') }}
        </label>

        <select v-model="status" class="input w-auto py-1.5 text-sm">
          <option value="">{{ t('filter.all') }}</option>
          <option v-for="s in options.statuses || []" :key="s" :value="s">
            {{ t(`status.${s}`) }}
          </option>
        </select>

        <input
          v-model="search"
          type="search"
          class="input w-auto flex-1 min-w-[12rem] py-1.5 text-sm"
          :placeholder="t('filter.search_placeholder')"
        />

        <button class="btn-secondary btn-sm ml-auto"
          :disabled="fetching"
          :title="t('mail.fetch_hint')"
          @click="fetchMail()"
        >
          <IconMailDown :size="14" :stroke-width="1.8" />
          {{ fetching ? t('mail.fetching') : t('mail.fetch') }}
        </button>
        <button class="btn-secondary btn-sm" @click="reload()">
          {{ t('actions.refresh') }}
        </button>
      </div>

      <AppSpinner v-if="loading" />
      <TicketTable
        v-else
        :rows="rows"
        show-timer
        :empty-text="t('ticket.none_assigned')"
        @open="openTicket"
        @start-timer="startTimer"
        @stop-timer="scrollToTimerBar"
      />
    </div>

    <TicketDetail
      :name="selected"
      :open="!!selected"
      :options="options"
      @close="selected = ''"
      @changed="reload()"
    />
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppSpinner from '@/components/ui/AppSpinner.vue'
import StatCard from '@/components/ui/StatCard.vue'
import TicketTable from '@/components/tickets/TicketTable.vue'
import TicketDetail from '@/components/tickets/TicketDetail.vue'
import { api } from '@/utils/api'
import { formatHours } from '@/utils/format'
import { useSessionStore } from '@/stores/session'
import { useTimerStore } from '@/stores/timer'
import { useToastStore } from '@/stores/toast'
import { useTicketEvents } from '@/composables/useTicketEvents'

const { t } = useI18n()
const session = useSessionStore()
const toast = useToastStore()
const timer = useTimerStore()

const rows = ref([])
const stats = ref({ open: 0, closed: 0, hours_7d: 0 })
const options = ref({})
const loading = ref(true)
const selected = ref('')

const onlyOpen = ref(true)
const status = ref('')
const search = ref('')

let searchTimer = null

const fetching = ref(false)

// Der Zeitplan holt alle zehn Minuten. Wer auf eine Antwort wartet, will
// nicht so lange warten -- der Server bremst dabei ueber eine gemeinsame
// Sperre, damit gleichzeitige Klicks den Mailserver nicht vervielfachen.
async function fetchMail() {
  fetching.value = true
  try {
    const res = await api.fetchMail()
    if (res.throttled) toast.info(t('mail.just_fetched'))
    else if (res.new_messages) toast.success(t('mail.fetched', { count: res.new_messages }))
    else toast.info(t('mail.nothing_new'))
    if (res.failed?.length) toast.error(t('mail.failed', { accounts: res.failed.join(', ') }))
    await reload()
  } catch (e) {
    toast.error(e.message)
  } finally {
    fetching.value = false
  }
}

async function reload() {
  loading.value = true
  try {
    const [list, s] = await Promise.all([
      api.listTickets({
        only_open: onlyOpen.value ? 1 : 0,
        status: status.value || null,
        search: search.value || null,
        limit_page_length: 100,
      }),
      api.getMyStats(),
    ])
    rows.value = list.rows
    stats.value = s
  } catch (e) {
    toast.error(e.message)
  } finally {
    loading.value = false
  }
}

function openTicket(name) {
  selected.value = name
}

async function startTimer(issue) {
  try {
    await timer.start(issue)
  } catch (e) {
    toast.error(e.message)
  }
}

// Gestoppt wird immer über die Leiste in der Kopfzeile, damit der
// Bestätigungsdialog nur an einer Stelle existiert. Sie steht oben und ist
// bei langen Listen ausserhalb des Blickfelds.
function scrollToTimerBar() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

// Tippen nicht bei jedem Anschlag abfragen.
watch(search, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(reload, 350)
})
watch([onlyOpen, status], reload)

// Zuweisungen und Statuswechsel anderer landen ohne Zutun in der Liste.
useTicketEvents(reload)

onMounted(async () => {
  options.value = await api.getFormOptions().catch(() => ({}))
  await reload()
})
</script>
