<!--
  Bereich B: Alle Vorgänge der eigenen Abteilung, Umverteilung und
  Team-Auswertung.
-->
<template>
  <div class="space-y-6">
    <div>
      <h1>{{ t('views.department_title', { department: departmentLabel }) }}</h1>
      <p class="text-slate-500 mt-1">{{ t('views.department_subtitle') }}</p>
    </div>

    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <StatCard :label="t('stats.open')" :value="team.open || 0" tone="warn" />
      <StatCard
        :label="t('stats.resolved_in_period', { days: team.days || 30 })"
        :value="team.closed || 0"
        tone="good"
      />
      <StatCard
        :label="t('stats.unassigned')"
        :value="team.unassigned || 0"
        :tone="team.unassigned ? 'danger' : 'default'"
      />
      <StatCard
        :label="t('stats.total_hours')"
        :value="formatHours(team.total_hours) + ' ' + t('time.hours_short')"
      />
    </div>

    <div class="grid lg:grid-cols-3 gap-4">
      <div class="card lg:col-span-2">
        <div class="card-header">
          <h2 class="text-base font-semibold">{{ t('stats.workload') }}</h2>
        </div>
        <div class="card-body">
          <div class="table-wrapper">
            <table class="table">
              <thead>
                <!-- Anteilige Breiten statt fester: Bei w-full und festen
                     Zahlenspalten schluckt die Namensspalte den ganzen Rest,
                     und die Zahlen kleben weit rechts am Rand. So verteilen
                     sich die Spalten gleichmäßig und bleiben zusammen lesbar. -->
                <tr>
                  <th class="w-[40%]">{{ t('stats.member') }}</th>
                  <th class="w-[20%] text-right">{{ t('stats.open') }}</th>
                  <th class="w-[20%] text-right">
                    {{ t('stats.resolved_in_period', { days: team.days || 30 }) }}
                  </th>
                  <th class="w-[20%] text-right">{{ t('stats.hours') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="m in team.members || []" :key="m.employee">
                  <td class="font-medium text-slate-800">{{ m.employee_name }}</td>
                  <td class="text-right tabular-nums">{{ m.open_tickets }}</td>
                  <td class="text-right tabular-nums text-slate-500">{{ m.resolved_tickets }}</td>
                  <td class="text-right tabular-nums text-slate-500">
                    {{ formatHours(m.hours) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-if="!(team.members || []).length" class="text-sm text-slate-400 py-4">
            {{ t('common.empty') }}
          </p>
        </div>
      </div>

      <div class="space-y-4">
        <div class="card">
          <div class="card-header"><h2 class="text-base font-semibold">{{ t('stats.by_status') }}</h2></div>
          <div class="card-body"><BarList :rows="statusRows" /></div>
        </div>
        <div class="card">
          <div class="card-header"><h2 class="text-base font-semibold">{{ t('stats.by_origin') }}</h2></div>
          <div class="card-body"><BarList :rows="originRows" /></div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-header flex flex-wrap items-center gap-3">
        <h2 class="text-base font-semibold">{{ t('ticket.many') }}</h2>

        <select v-model="assignee" class="input w-auto py-1.5 text-sm">
          <option value="">{{ t('filter.all') }}</option>
          <option v-for="m in team.members || []" :key="m.employee" :value="m.employee">
            {{ m.employee_name }}
          </option>
        </select>

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
      <TicketTable v-else :rows="rows" show-assignee @open="selected = $event" />
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
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppSpinner from '@/components/ui/AppSpinner.vue'
import BarList from '@/components/ui/BarList.vue'
import StatCard from '@/components/ui/StatCard.vue'
import TicketTable from '@/components/tickets/TicketTable.vue'
import TicketDetail from '@/components/tickets/TicketDetail.vue'
import { api } from '@/utils/api'
import { formatHours } from '@/utils/format'
import { useSessionStore } from '@/stores/session'
import { useToastStore } from '@/stores/toast'
import { useTicketEvents } from '@/composables/useTicketEvents'

const { t } = useI18n()
const session = useSessionStore()
const toast = useToastStore()

const team = ref({})
const rows = ref([])
const options = ref({})
const loading = ref(true)
const selected = ref('')

const status = ref('')
const assignee = ref('')
const search = ref('')
let searchTimer = null

// ERPNext hängt an Abteilungsnamen das Firmenkürzel ("Support - MF").
// In der Überschrift stört das nur.
const departmentLabel = computed(() => (session.department || '').split(' - ')[0])

const statusRows = computed(() =>
  Object.entries(team.value.by_status || {}).map(([k, v]) => ({ label: t(`status.${k}`), value: v })),
)
const originRows = computed(() =>
  Object.entries(team.value.by_origin || {}).map(([k, v]) => ({ label: t(`origin.${k}`), value: v })),
)

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
    const [list, stats] = await Promise.all([
      api.listTickets({
        status: status.value || null,
        assignee: assignee.value || null,
        search: search.value || null,
        limit_page_length: 200,
      }),
      api.getTeamStats(session.department, 30),
    ])
    rows.value = list.rows
    team.value = stats
  } catch (e) {
    toast.error(e.message)
  } finally {
    loading.value = false
  }
}

watch(search, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(reload, 350)
})
watch([status, assignee], reload)

// Auch die Auslastungstabelle zieht dadurch nach: reload() holt beides.
useTicketEvents(reload)

onMounted(async () => {
  options.value = await api.getFormOptions().catch(() => ({}))
  await reload()
})
</script>
