<!-- Legende oberhalb des Diagramms: farbiges Quadrat plus Name. -->
<template>
  <div v-if="items.length" class="flex flex-wrap gap-x-4 gap-y-1.5">
    <span
      v-for="item in items"
      :key="item.label"
      class="inline-flex items-center gap-1.5 text-xs text-slate-500"
    >
      <span class="w-3 h-3 rounded-sm shrink-0" :style="{ backgroundColor: item.color }" />
      <span class="truncate max-w-[12rem]">{{ item.label }}</span>
      <span v-if="item.value !== undefined" class="tabular-nums text-slate-400">
        {{ item.value }}
      </span>
    </span>
  </div>
</template>

<script setup>
defineProps({
  items: { type: Array, default: () => [] },
})
</script>
