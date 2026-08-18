<!--
  Zeiten zur Buchung — Sicht der Abteilungsleitung.

  Zeigt ausschließlich Entwürfe der eigenen Abteilung; die Einschränkung
  kommt vom Server, nicht von dieser Ansicht. Buchen geht einzeln oder für
  eine Mehrfachauswahl, korrigieren vorher ebenfalls.
-->
<template>
  <div class="space-y-6">
    <div>
      <h1>{{ t('views.approvals_title') }}</h1>
      <p class="text-slate-500 mt-1">
        {{ t('views.approvals_subtitle', { department: departmentLabel }) }}
      </p>
    </div>

    <div class="grid grid-cols-2 lg:grid-cols-3 gap-4">
      <StatCard
        :label="t('entry.pending')"
        :value="(data.rows || []).length"
        :tone="(data.rows || []).length ? 'warn' : 'good'"
      />
      <StatCard
        :label="t('stats.total_hours')"
        :value="formatHours(data.total_hours) + ' ' + t('time.hours_short')"
      />
      <StatCard :label="t('entry.selected')" :value="selected.size" />
    </div>

    <div v-if="(data.by_employee || []).length" class="card">
      <div class="card-header"><h2 class="text-base font-semibold">{{ t('stats.member') }}</h2></div>
      <div class="card-body">
        <BarList :rows="employeeRows" />
      </div>
    </div>

    <div class="card">
      <div class="card-header flex flex-wrap items-center gap-3">
        <label class="text-sm text-slate-600">
          {{ t('entry.from') }}
          <input v-model="fromDate" type="date" class="input w-auto py-1.5 text-sm ml-1" />
        </label>
        <label class="text-sm text-slate-600">
          {{ t('entry.to') }}
          <input v-model="toDate" type="date" class="input w-auto py-1.5 text-sm ml-1" />
        </label>

        <button
          class="btn-primary btn-sm ml-auto"
          :disabled="!selected.size || busy"
          @click="submitSelected()"
        >
          {{ t('entry.submit_selected', { count: selected.size }) }}
        </button>
      </div>

      <AppSpinner v-if="loading" />

      <template v-else>
        <div class="table-wrapper">
          <table class="table">
            <thead>
              <tr>
                <th class="w-10">
                  <input
                    type="checkbox"
                    class="rounded border-slate-300"
                    :checked="allSelected"
                    :aria-label="t('entry.select_all')"
                    @change="toggleAll($event.target.checked)"
                  />
                </th>
                <th class="w-28">{{ t('entry.date') }}</th>
                <th class="w-36">{{ t('stats.member') }}</th>
                <th>{{ t('ticket.one') }}</th>
                <th>{{ t('time.description') }}</th>
                <th class="w-24 text-right">{{ t('stats.hours') }}</th>
                <th class="w-40"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in data.rows || []" :key="row.name">
                <td>
                  <input
                    type="checkbox"
                    class="rounded border-slate-300"
                    :checked="selected.has(row.name)"
                    :aria-label="row.name"
                    @change="toggle(row.name, $event.target.checked)"
                  />
                </td>
                <td class="text-slate-500 text-xs">{{ formatDate(row.start_date, locale) }}</td>
                <td class="text-slate-800">{{ row.employee_name }}</td>
                <td class="text-slate-800 truncate max-w-[14rem]">
                  {{ row.issue_subject || row.issue || '—' }}
                </td>
                <td class="text-slate-600 truncate max-w-[16rem]">{{ row.description }}</td>
                <td class="text-right tabular-nums font-medium">{{ formatHours(row.hours) }}</td>
                <td class="text-right">
                  <div class="flex justify-end gap-1">
                    <button
                      v-if="row.editable"
                      class="btn-secondary btn-sm"
                      @click="editing = row"
                    >
                      {{ t('actions.edit') }}
                    </button>
                    <button class="btn-secondary btn-sm" :disabled="busy" @click="submitOne(row)">
                      {{ t('entry.submit') }}
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <p v-if="!(data.rows || []).length" class="text-center text-sm text-slate-400 py-8">
          {{ t('entry.nothing_pending') }}
        </p>
      </template>
    </div>

    <EntryEditDialog
      :open="!!editing"
      :entry="editing"
      :busy="busy"
      @cancel="editing = null"
      @save="saveEdit"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppSpinner from '@/components/ui/AppSpinner.vue'
import BarList from '@/components/ui/BarList.vue'
import StatCard from '@/components/ui/StatCard.vue'
import EntryEditDialog from '@/components/time/EntryEditDialog.vue'
import { api } from '@/utils/api'
import { formatDate, formatHours } from '@/utils/format'
import { useSessionStore } from '@/stores/session'
import { useToastStore } from '@/stores/toast'

const { t, locale } = useI18n()
const session = useSessionStore()
const toast = useToastStore()

const data = ref({ rows: [], total_hours: 0, by_employee: [] })
const loading = ref(true)
const busy = ref(false)
const selected = ref(new Set())
const editing = ref(null)
const fromDate = ref('')
const toDate = ref('')

const departmentLabel = computed(() => (session.department || '').split(' - ')[0])

const employeeRows = computed(() =>
  (data.value.by_employee || []).map((e) => ({
    label: `${e.employee_name} (${e.count})`,
    value: e.hours,
    display: `${formatHours(e.hours)} ${t('time.hours_short')}`,
  })),
)

const allSelected = computed(
  () => !!(data.value.rows || []).length && selected.value.size === data.value.rows.length,
)

function toggle(name, on) {
  const next = new Set(selected.value)
  on ? next.add(name) : next.delete(name)
  selected.value = next
}

function toggleAll(on) {
  selected.value = on ? new Set((data.value.rows || []).map((r) => r.name)) : new Set()
}

async function reload() {
  loading.value = true
  try {
    data.value = await api.listPendingEntries({
      from_date: fromDate.value || null,
      to_date: toDate.value || null,
    })
    // Auswahl bereinigen: Was gebucht wurde, ist nicht mehr da.
    const names = new Set((data.value.rows || []).map((r) => r.name))
    selected.value = new Set([...selected.value].filter((n) => names.has(n)))
  } catch (e) {
    toast.error(e.message)
  } finally {
    loading.value = false
  }
}

async function submit(names) {
  busy.value = true
  try {
    const res = await api.submitTimeEntries(names)
    if (res.submitted.length) {
      toast.success(t('entry.submitted_count', { count: res.submitted.length }))
    }
    // Fehlschläge einzeln melden -- bei einer Mehrfachauswahl ist sonst
    // unklar, was durchging und was nicht.
    for (const f of res.failed || []) {
      toast.error(`${f.name}: ${f.error}`)
    }
    await reload()
  } catch (e) {
    toast.error(e.message)
  } finally {
    busy.value = false
  }
}

const submitOne = (row) => submit([row.name])
const submitSelected = () => submit([...selected.value])

async function saveEdit({ hours, description }) {
  busy.value = true
  try {
    await api.updateTimeEntry({ name: editing.value.name, hours, description })
    editing.value = null
    toast.success(t('common.saved'))
    await reload()
  } catch (e) {
    toast.error(e.message)
  } finally {
    busy.value = false
  }
}

watch([fromDate, toDate], reload)
onMounted(reload)
</script>
