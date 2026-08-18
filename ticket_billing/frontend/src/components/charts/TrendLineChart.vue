<!--
  Ticketaufkommen im Zeitverlauf, eine Linie je Kategorie.

  Dünne Linien ohne Punktmarker, dezentes Raster nur waagerecht: Bei zwölf
  Wochen und mehreren Serien machen Marker die Grafik unruhig, ohne etwas
  hinzuzufügen -- der Wert steht im Tooltip.
-->
<template>
  <div class="space-y-3">
    <ChartLegend :items="legend" />
    <BaseChart type="line" :data="chartData" :options="options" :height="height" :empty="!series.length" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import BaseChart from './BaseChart.vue'
import ChartLegend from './ChartLegend.vue'
import { GRID_COLOR, TICK_COLOR, seriesColor } from './palette'

const props = defineProps({
  /** Beschriftungen der x-Achse, z. B. Kalenderwochen. */
  labels: { type: Array, default: () => [] },
  /** [{ label, values: number[] }] -- eine Reihe je Kategorie. */
  series: { type: Array, default: () => [] },
  height: { type: Number, default: 260 },
})

const legend = computed(() =>
  props.series.map((s, i) => ({ label: s.label, color: seriesColor(i) })),
)

const chartData = computed(() => ({
  labels: props.labels,
  datasets: props.series.map((s, i) => ({
    label: s.label,
    data: s.values,
    borderColor: seriesColor(i),
    backgroundColor: seriesColor(i),
    borderWidth: 1.6,
    pointRadius: 0,
    // Beim Überfahren doch ein Punkt, damit sichtbar ist, welcher Wert
    // gerade gemeint ist.
    pointHoverRadius: 3,
    // Gerade Verbindungen, keine Glättung: Es sind Stückzahlen. Eine Kurve
    // schießt zwischen 0 und 1 über beide Werte hinaus und behauptet damit
    // Zwischenstände, die es nicht gibt.
    tension: 0,
    fill: false,
  })),
}))

const options = computed(() => ({
  interaction: { mode: 'index', intersect: false },
  plugins: {
    tooltip: {
      backgroundColor: '#1e293b',
      padding: 10,
      cornerRadius: 6,
      displayColors: true,
      boxWidth: 8,
      boxHeight: 8,
    },
  },
  scales: {
    x: {
      grid: { display: false },
      border: { color: GRID_COLOR },
      ticks: {
        color: TICK_COLOR,
        maxRotation: 0,
        autoSkipPadding: 12,
      },
    },
    y: {
      beginAtZero: true,
      grid: { color: GRID_COLOR, drawTicks: false },
      border: { display: false },
      ticks: {
        color: TICK_COLOR,
        padding: 8,
        // Ganze Tickets, keine Zwischenschritte wie 2,5.
        precision: 0,
      },
    },
  },
}))
</script>
