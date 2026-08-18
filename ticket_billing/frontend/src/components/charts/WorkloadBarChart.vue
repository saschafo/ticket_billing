<!-- Auslastung je Mitarbeiter: offene Tickets als waagerechte Balken. -->
<template>
  <BaseChart
    type="bar"
    :data="chartData"
    :options="options"
    :height="height"
    :empty="!rows.length"
  />
</template>

<script setup>
import { computed } from 'vue'
import BaseChart from './BaseChart.vue'
import { GRID_COLOR, TICK_COLOR, seriesColor } from './palette'

const props = defineProps({
  /** [{ label, value, hint }] */
  rows: { type: Array, default: () => [] },
  height: { type: Number, default: 260 },
  valueLabel: { type: String, default: '' },
})

const chartData = computed(() => ({
  labels: props.rows.map((r) => r.label),
  datasets: [
    {
      label: props.valueLabel,
      data: props.rows.map((r) => r.value),
      // Eine Farbe je Person, damit die Balken zu den Linien im Diagramm
      // darüber passen -- dort steht dieselbe Reihenfolge.
      backgroundColor: props.rows.map((_, i) => seriesColor(i)),
      borderWidth: 0,
      borderRadius: 3,
      barThickness: 18,
    },
  ],
}))

const options = computed(() => ({
  // Waagerecht: Mitarbeiternamen sind lang, senkrecht müsste man sie kippen.
  indexAxis: 'y',
  plugins: {
    tooltip: {
      backgroundColor: '#1e293b',
      padding: 10,
      cornerRadius: 6,
      callbacks: {
        label: (ctx) => {
          const row = props.rows[ctx.dataIndex]
          return row?.hint ? `${ctx.parsed.x} · ${row.hint}` : String(ctx.parsed.x)
        },
      },
    },
  },
  scales: {
    x: {
      beginAtZero: true,
      grid: { color: GRID_COLOR, drawTicks: false },
      border: { display: false },
      ticks: { color: TICK_COLOR, precision: 0, padding: 6 },
    },
    y: {
      grid: { display: false },
      border: { color: GRID_COLOR },
      ticks: { color: '#475569' },
    },
  },
}))
</script>
