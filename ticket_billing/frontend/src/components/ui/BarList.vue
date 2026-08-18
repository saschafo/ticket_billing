<!--
  Balken als reines CSS — bewusst ohne Diagrammbibliothek. Für den Vergleich
  weniger Werte reicht das, spart rund 200 kB im Bundle und funktioniert ohne
  externe Ressourcen (die Auslieferung über Frappe erlaubt keine CDN-Zugriffe).
-->
<template>
  <div>
    <div v-if="!rows.length" class="text-sm text-slate-400 py-4">
      {{ t('stats.no_data') }}
    </div>

    <ul v-else class="space-y-2.5">
      <li v-for="row in rows" :key="row.label">
        <div class="flex items-baseline justify-between gap-3 text-sm">
          <span class="text-slate-700 truncate">{{ row.label }}</span>
          <span class="tabular-nums font-medium text-slate-900 shrink-0">
            {{ row.display ?? row.value }}
          </span>
        </div>
        <div class="mt-1 h-2 rounded-full bg-slate-100 overflow-hidden">
          <div
            class="h-full rounded-full transition-all duration-300"
            :style="{ width: width(row.value), backgroundColor: 'var(--color-primary)' }"
          />
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  rows: { type: Array, default: () => [] },
})
const { t } = useI18n()

const max = computed(() => Math.max(1, ...props.rows.map((r) => Number(r.value) || 0)))

function width(value) {
  const pct = ((Number(value) || 0) / max.value) * 100
  // Ein Wert größer null bekommt einen sichtbaren Rest-Balken, sonst sähe
  // "1 von 200" aus wie "nichts".
  return `${value > 0 ? Math.max(pct, 3) : 0}%`
}
</script>
