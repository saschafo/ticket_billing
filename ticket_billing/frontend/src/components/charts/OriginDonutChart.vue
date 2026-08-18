<!--
  Herkunft der Tickets als Ring, mit Prozentwerten.

  Die Zahlen stehen in der Mitte und in der Legende, nicht am Ring: Bei zwei
  Segmenten spart das die Beschriftungslinien, und der größere Anteil ist
  ohnehin sofort zu sehen.
-->
<template>
  <div class="space-y-3">
    <ChartLegend :items="legend" />

    <div class="relative">
      <BaseChart
        type="doughnut"
        :data="chartData"
        :options="options"
        :height="height"
        :empty="!total"
      />

      <div
        v-if="total"
        class="absolute inset-0 flex flex-col items-center justify-center pointer-events-none"
      >
        <span class="text-2xl font-bold text-slate-900 tabular-nums">{{ total }}</span>
        <span class="text-xs text-slate-400">{{ centerLabel }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import BaseChart from './BaseChart.vue'
import ChartLegend from './ChartLegend.vue'
import { ORIGIN_COLORS } from './palette'

const props = defineProps({
  internal: { type: Number, default: 0 },
  external: { type: Number, default: 0 },
  internalLabel: { type: String, default: 'Intern' },
  externalLabel: { type: String, default: 'Extern' },
  centerLabel: { type: String, default: '' },
  height: { type: Number, default: 260 },
})

const total = computed(() => (props.internal || 0) + (props.external || 0))

const share = (value) => (total.value ? Math.round((value / total.value) * 100) : 0)

const legend = computed(() => [
  {
    label: props.externalLabel,
    color: ORIGIN_COLORS.External,
    value: `${props.external} · ${share(props.external)} %`,
  },
  {
    label: props.internalLabel,
    color: ORIGIN_COLORS.Internal,
    value: `${props.internal} · ${share(props.internal)} %`,
  },
])

const chartData = computed(() => ({
  labels: [props.externalLabel, props.internalLabel],
  datasets: [
    {
      data: [props.external, props.internal],
      backgroundColor: [ORIGIN_COLORS.External, ORIGIN_COLORS.Internal],
      borderWidth: 0,
      // Ring statt Torte: Die Mitte trägt die Gesamtzahl.
      cutout: '68%',
    },
  ],
}))

const options = computed(() => ({
  plugins: {
    tooltip: {
      backgroundColor: '#1e293b',
      padding: 10,
      cornerRadius: 6,
      callbacks: {
        label: (ctx) => `${ctx.label}: ${ctx.parsed} · ${share(ctx.parsed)} %`,
      },
    },
  },
}))
</script>
