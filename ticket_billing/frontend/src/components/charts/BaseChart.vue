<!--
  Gemeinsame Hülle um Chart.js.

  Chart.js zeichnet auf ein Canvas und lebt außerhalb von Vues Reaktivität.
  Diese Komponente hält beides zusammen: Sie erzeugt das Diagramm einmal,
  schiebt bei Datenänderungen nur die neuen Werte hinein (statt es
  wegzuwerfen und neu zu bauen -- das flackert) und räumt es beim Verlassen
  der Ansicht wieder ab. Ohne das letzte Aufräumen bleiben Canvas-Kontexte
  und Resize-Beobachter liegen.

  Registriert werden nur die tatsächlich benutzten Chart.js-Bausteine; der
  Sammelimport zöge das ganze Paket ins Bundle.
-->
<template>
  <div class="relative" :style="{ height: height + 'px' }">
    <canvas ref="canvas" />
    <div
      v-if="empty"
      class="absolute inset-0 flex items-center justify-center text-sm text-slate-400"
    >
      {{ t('stats.no_data') }}
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  ArcElement,
  BarController,
  BarElement,
  CategoryScale,
  Chart,
  DoughnutController,
  Filler,
  LineController,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
} from 'chart.js'
import { FONT_FAMILY } from './palette'

Chart.register(
  ArcElement,
  BarController,
  BarElement,
  CategoryScale,
  DoughnutController,
  Filler,
  LineController,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
)

Chart.defaults.font.family = FONT_FAMILY
Chart.defaults.font.size = 11

// Das Legend-Plugin ist oben bewusst NICHT registriert -- die Legenden über
// den Diagrammen sind eigene Vue-Komponenten, weil die eingebaute weder in
// der Anordnung noch im Stil passt.
//
// Es darf hier deshalb auch nichts an Chart.defaults.plugins.legend gesetzt
// werden: Ohne Registrierung gibt es den Zweig nicht, und der Zugriff wirft
// schon beim Laden dieses Moduls. Die Komponente rendert dann gar nichts,
// und zwar wortlos -- an der Stelle des Diagramms steht nur ein leeres
// Vue-Kommentar.

const props = defineProps({
  type: { type: String, required: true },
  data: { type: Object, required: true },
  options: { type: Object, default: () => ({}) },
  height: { type: Number, default: 240 },
  empty: { type: Boolean, default: false },
})

const { t } = useI18n()
const canvas = ref(null)
let chart = null

function create() {
  if (!canvas.value) return
  chart = new Chart(canvas.value, {
    type: props.type,
    data: props.data,
    options: {
      responsive: true,
      maintainAspectRatio: false,
      // Ohne Animation: Es ist ein Zahlen-Dashboard, kein Effekt -- und ein
      // sofort fertiges Bild laesst sich auch zuverlaessig abfotografieren.
      animation: false,
      ...props.options,
    },
  })
}

watch(
  () => [props.data, props.options],
  () => {
    if (!chart) return
    chart.data = props.data
    chart.options = { ...chart.options, ...props.options }
    chart.update()
  },
  { deep: true },
)

onMounted(create)
onBeforeUnmount(() => {
  chart?.destroy()
  chart = null
})
</script>
