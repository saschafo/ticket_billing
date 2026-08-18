<!--
  Bereich C: Abteilungsübergreifende Kennzahlen.

  Reine Auswertung — die Rolle Geschäftsführung hat serverseitig kein
  Schreibrecht auf Issue. Anordnung wie in der Abteilungssicht, damit man
  sich nicht umgewöhnen muss; die Linien zeigen hier Abteilungen statt
  Mitarbeiter.
-->
<template>
  <div class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1>{{ t('views.management_title') }}</h1>
        <p class="text-slate-500 mt-1">{{ t('views.management_subtitle') }}</p>
      </div>

      <div class="flex items-end gap-3">
        <label class="text-sm text-slate-600">
          {{ t('stats.period') }}
          <select v-model.number="days" class="input w-auto py-1.5 text-sm ml-2">
            <option v-for="p in periods" :key="p.days" :value="p.days">
              {{ t(p.key, p.args) }}
            </option>
          </select>
        </label>
        <button class="btn-secondary btn-sm" :disabled="loading" @click="exportXlsx()">
          {{ t('stats.export_excel') }}
        </button>
      </div>
    </div>

    <AppSpinner v-if="loading" />

    <template v-else>
      <KpiDashboard
        :trend="data.trend || []"
        :trend-title="t('stats.volume_by_department')"
        :employees="data.employees || []"
        :totals="data.totals || {}"
      />

      <!-- Die Tabelle bleibt: Sie trägt die Werte, die im Diagramm nicht
           unterzubringen sind (Stunden getrennt nach abrechenbar, intern und
           gebucht) und ist die Vorlage für den Excel-Export. -->
      <section class="card">
        <div class="card-header">
          <h2 class="text-base font-semibold">{{ t('stats.by_department') }}</h2>
        </div>
        <div class="card-body">
          <div class="table-wrapper">
            <table class="table">
              <thead>
                <tr>
                  <th>{{ t('ticket.department') }}</th>
                  <th class="w-20 text-right">{{ t('ticket.many') }}</th>
                  <th class="w-20 text-right">{{ t('stats.open') }}</th>
                  <th class="w-28 text-right">{{ t('stats.external_share') }}</th>
                  <th class="w-28 text-right">{{ t('stats.avg_response') }}</th>
                  <th class="w-28 text-right">{{ t('stats.avg_resolution') }}</th>
                  <th class="w-28 text-right">{{ t('stats.billable') }}</th>
                  <th class="w-28 text-right">{{ t('stats.internal_hours') }}</th>
                  <th class="w-28 text-right">{{ t('stats.submitted') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="d in departments" :key="d.department">
                  <td class="font-medium text-slate-800">{{ d.label }}</td>
                  <td class="text-right tabular-nums">{{ d.total }}</td>
                  <td class="text-right tabular-nums">{{ d.open }}</td>
                  <td class="text-right tabular-nums text-slate-500">{{ d.external_share }} %</td>
                  <td class="text-right tabular-nums text-slate-500">
                    {{ hoursLabel(d.avg_response_hours) }}
                  </td>
                  <td class="text-right tabular-nums text-slate-500">
                    {{ hoursLabel(d.avg_resolution_hours) }}
                  </td>
                  <td class="text-right tabular-nums font-medium">
                    {{ formatHours(d.hours_billable) }}
                  </td>
                  <td class="text-right tabular-nums text-slate-500">
                    {{ formatHours(d.hours_internal) }}
                  </td>
                  <td class="text-right tabular-nums text-slate-500">
                    {{ formatHours(d.hours_submitted) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-if="!departments.length" class="text-sm text-slate-400 py-4">
            {{ t('stats.no_data') }}
          </p>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppSpinner from '@/components/ui/AppSpinner.vue'
import KpiDashboard from '@/components/kpi/KpiDashboard.vue'
import { api } from '@/utils/api'
import { formatHours } from '@/utils/format'
import { useToastStore } from '@/stores/toast'

const { t } = useI18n()
const toast = useToastStore()

const periods = [
  { days: 7, key: 'stats.last_days', args: { days: 7 } },
  { days: 30, key: 'stats.last_days', args: { days: 30 } },
  { days: 84, key: 'stats.last_weeks', args: { weeks: 12 } },
  { days: 365, key: 'stats.last_days', args: { days: 365 } },
]

const days = ref(30)
const data = ref({})
const loading = ref(true)

const departments = computed(() => data.value.departments || [])

function hoursLabel(value) {
  if (value === null || value === undefined) return '—'
  return `${formatHours(value)} ${t('time.hours_short')}`
}

async function reload() {
  loading.value = true
  try {
    data.value = await api.getManagementKpis(days.value)
  } catch (e) {
    toast.error(e.message)
  } finally {
    loading.value = false
  }
}

function exportXlsx() {
  // Als normaler Seitenaufruf, nicht per fetch: Der Browser bekommt damit
  // Dateiname und Content-Type vom Server und legt die Datei selbst ab.
  window.location.href = `/api/method/ticket_billing.api.kpi.export_management_kpis?days=${days.value}`
}

watch(days, reload)
onMounted(reload)
</script>
