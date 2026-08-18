<template>
  <div class="card p-5">
    <div class="flex items-center gap-2 text-sm text-slate-500">
      <component :is="icon" v-if="icon" :size="16" :stroke-width="1.8" class="text-slate-400 shrink-0" />
      <span>{{ label }}</span>
    </div>
    <div class="mt-1 text-3xl font-bold tabular-nums" :class="toneClass">{{ value }}</div>
    <div v-if="hint" class="mt-1 text-xs text-slate-400">{{ hint }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], default: 0 },
  hint: { type: String, default: '' },
  tone: { type: String, default: 'default' },
  // Optional. Icons stehen nur dort, wo sie die Kachel schneller erkennbar
  // machen -- eine Kachel ohne passendes Symbol bekommt keins.
  icon: { type: [Object, Function], default: null },
})

const toneClass = computed(
  () =>
    ({
      default: 'text-slate-900',
      warn: 'text-amber-600',
      danger: 'text-red-600',
      good: 'text-emerald-600',
    })[props.tone] || 'text-slate-900',
)
</script>
