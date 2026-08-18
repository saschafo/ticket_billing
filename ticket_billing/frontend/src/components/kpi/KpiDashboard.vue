<!--
  Gemeinsamer Aufbau beider Kennzahlen-Ansichten.

  Geschäftsführung und Abteilungsleitung sehen dieselbe Anordnung — nur die
  Kategorien unterscheiden sich (Abteilungen gegen Mitarbeiter). Zwei
  getrennte Ansichten mit gleicher Optik würden mit der Zeit auseinander
  driften, deshalb eine Komponente mit Daten von außen.

  Aufbau: vier Kacheln, darunter der Zeitverlauf, darunter Auslastung und
  Herkunft nebeneinander.
-->
<template>
  <div class="space-y-6">
    <!-- a) Kennzahlen -->
    <div class="grid grid-cols-2 xl:grid-cols-4 gap-4">
      <StatCard v-for="tile in tiles" :key="tile.label" v-bind="tile" />
    </div>

    <!-- b) Zeitverlauf -->
    <section class="card">
      <div class="card-header">
        <h2 class="text-base font-semibold">{{ trendTitle }}</h2>
      </div>
      <div class="card-body">
        <TrendLineChart :labels="trendLabels" :series="trendSeries" :height="280" />
      </div>
    </section>

    <!-- c) Auslastung und Herkunft -->
    <div class="grid gap-4" :class="ui.wide ? 'xl:grid-cols-2' : 'lg:grid-cols-2'">
      <section class="card">
        <div class="card-header">
          <h2 class="text-base font-semibold">{{ t('stats.workload') }}</h2>
        </div>
        <div class="card-body">
          <WorkloadBarChart
            :rows="workloadRows"
            :value-label="t('stats.open_tickets')"
            :height="chartHeight"
          />
        </div>
      </section>

      <section class="card">
        <div class="card-header">
          <h2 class="text-base font-semibold">{{ t('stats.origin_title') }}</h2>
        </div>
        <div class="card-body">
          <OriginDonutChart
            :internal="internal"
            :external="external"
            :internal-label="t('origin.Internal')"
            :external-label="t('origin.External')"
            :center-label="t('ticket.many')"
            :height="chartHeight"
          />
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  IconCircleCheck,
  IconClock,
  IconCurrencyEuro,
  IconTicket,
} from '@tabler/icons-vue'
import StatCard from '@/components/ui/StatCard.vue'
import TrendLineChart from '@/components/charts/TrendLineChart.vue'
import WorkloadBarChart from '@/components/charts/WorkloadBarChart.vue'
import OriginDonutChart from '@/components/charts/OriginDonutChart.vue'
import { formatHours } from '@/utils/format'
import { useUiStore } from '@/stores/ui'

const props = defineProps({
  /** [{period, values: {kategorie: zahl}}] vom Server */
  trend: { type: Array, default: () => [] },
  trendTitle: { type: String, default: '' },
  /** [{employee_name, open_tickets, hours}] */
  employees: { type: Array, default: () => [] },
  totals: { type: Object, default: () => ({}) },
})

const { t } = useI18n()
const ui = useUiStore()

// Im breiten Modus stehen die beiden unteren Diagramme nebeneinander und
// bekommen mehr Platz in der Höhe -- sonst wirken sie gequetscht.
const chartHeight = computed(() => (ui.wide ? 280 : 240))

const tiles = computed(() => [
  { label: t('stats.open'), value: props.totals.open ?? 0, tone: 'warn', icon: IconTicket },
  {
    label: t('stats.avg_response'),
    value: hours(props.totals.avg_response_hours),
    icon: IconClock,
  },
  {
    label: t('stats.avg_resolution'),
    value: hours(props.totals.avg_resolution_hours),
    icon: IconCircleCheck,
  },
  {
    label: t('stats.billable'),
    value: hours(props.totals.hours_billable),
    tone: 'good',
    icon: IconCurrencyEuro,
    hint: t('stats.of_total', { total: formatHours(props.totals.hours_total) }),
  },
])

function hours(value) {
  if (value === null || value === undefined) return '—'
  return `${formatHours(value)} ${t('time.hours_short')}`
}

const trendLabels = computed(() => props.trend.map((p) => shorten(p.period)))

// Kategorien aus allen Zeitpunkten sammeln, nicht nur aus dem ersten: Wer
// erst in Woche fünf ein Ticket bekommen hat, fehlte sonst ganz.
const trendSeries = computed(() => {
  const names = new Set()
  for (const point of props.trend) {
    for (const key of Object.keys(point.values || {})) names.add(key)
  }

  return [...names].sort().map((name) => ({
    label: name,
    values: props.trend.map((p) => p.values?.[name] || 0),
  }))
})

function shorten(period) {
  const match = String(period).match(/^(\d{4})-(\d{2})-(\d{2})$/)
  return match ? `${match[3]}.${match[2]}.` : String(period).replace(/^\d{4}-/, '')
}

const workloadRows = computed(() =>
  props.employees.map((e) => ({
    label: e.employee_name,
    value: e.open_tickets,
    hint: `${formatHours(e.hours)} ${t('time.hours_short')}`,
  })),
)

const internal = computed(() => props.totals.internal ?? 0)
const external = computed(() => props.totals.external ?? 0)
</script>
