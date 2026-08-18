<!--
  Kennzahlen der eigenen Abteilung — für die Abteilungsleitung.

  Gleicher Aufbau wie die Sicht der Geschäftsführung, nur ohne
  Abteilungsvergleich: Die Linien zeigen die eigenen Mitarbeiter.
-->
<template>
  <div class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1>{{ t('views.dept_kpi_title', { department: label }) }}</h1>
        <p class="text-slate-500 mt-1">{{ t('views.dept_kpi_subtitle') }}</p>
      </div>

      <label class="text-sm text-slate-600">
        {{ t('stats.period') }}
        <select v-model.number="days" class="input w-auto py-1.5 text-sm ml-2">
          <option v-for="p in periods" :key="p.days" :value="p.days">{{ t(p.key, p.args) }}</option>
        </select>
      </label>
    </div>

    <AppSpinner v-if="loading" />

    <template v-else>
      <!-- Offene Zeiterfassungen: gehört nicht in die Kachelreihe oben, weil
           es kein Kennwert der Abteilung ist, sondern eine offene Aufgabe der
           Leitung. Deshalb ein eigener Block mit Weg zur Bearbeitung. -->
      <div
        v-if="pending.entries"
        class="rounded-xl border border-amber-200 bg-amber-50 px-5 py-4 flex flex-wrap items-center gap-x-6 gap-y-3"
      >
        <IconAlertTriangle :size="22" :stroke-width="1.8" class="text-amber-600 shrink-0" />
        <div>
          <div class="text-sm text-amber-900 font-medium">{{ t('entry.pending_block') }}</div>
          <div class="text-xs text-amber-800 mt-0.5">
            {{ t('entry.pending_hint', { count: pending.entries, hours: formatHours(pending.hours) }) }}
          </div>
        </div>
        <RouterLink :to="{ name: 'approvals' }" class="btn-primary btn-sm ml-auto">
          {{ t('nav.approvals') }}
        </RouterLink>
      </div>

      <KpiDashboard
        :trend="data.trend || []"
        :trend-title="t('stats.volume_by_employee')"
        :employees="data.employees || []"
        :totals="data.totals || {}"
      />
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { IconAlertTriangle } from '@tabler/icons-vue'
import AppSpinner from '@/components/ui/AppSpinner.vue'
import KpiDashboard from '@/components/kpi/KpiDashboard.vue'
import { api } from '@/utils/api'
import { formatHours } from '@/utils/format'
import { useToastStore } from '@/stores/toast'

const { t } = useI18n()
const toast = useToastStore()

// 84 Tage = 12 Wochen und damit die Voreinstellung: Das Liniendiagramm zeigt
// dann genau zwölf Punkte, einen je Woche.
const periods = [
  { days: 30, key: 'stats.last_days', args: { days: 30 } },
  { days: 84, key: 'stats.last_weeks', args: { weeks: 12 } },
  { days: 365, key: 'stats.last_days', args: { days: 365 } },
]

const days = ref(84)
const data = ref({})
const loading = ref(true)

const label = computed(() => data.value.label || '')
const pending = computed(() => data.value.pending_time || { entries: 0, hours: 0 })

async function reload() {
  loading.value = true
  try {
    data.value = await api.getDepartmentKpis(null, days.value)
  } catch (e) {
    toast.error(e.message)
  } finally {
    loading.value = false
  }
}

watch(days, reload)
onMounted(reload)
</script>
