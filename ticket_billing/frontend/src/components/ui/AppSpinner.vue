<template>
  <div class="flex items-center justify-center gap-3 py-10 text-slate-400">
    <span
      class="inline-block w-5 h-5 rounded-full border-2 border-slate-200 border-t-slate-500 animate-spin"
      aria-hidden="true"
    />
    <span class="text-sm">{{ t('common.loading') }}</span>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
</script>
