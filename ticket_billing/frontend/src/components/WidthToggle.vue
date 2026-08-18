<!-- Umschalter zwischen zentrierter und voller Breite. -->
<template>
  <button
    class="inline-flex items-center justify-center w-9 h-9 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-800 transition-colors"
    :title="ui.wide ? t('layout.to_narrow') : t('layout.to_wide')"
    :aria-label="ui.wide ? t('layout.to_narrow') : t('layout.to_wide')"
    :aria-pressed="ui.wide"
    @click="ui.toggle()"
  >
    <!-- Zwei Zustände, zwei Bilder: nach außen zeigende Pfeile heißt
         "verbreitern", nach innen zeigende "wieder zusammenziehen". -->
    <IconArrowsHorizontal v-if="!ui.wide" :size="19" :stroke-width="1.8" />
    <IconArrowsDiff v-else :size="19" :stroke-width="1.8" />
  </button>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { IconArrowsDiff, IconArrowsHorizontal } from '@tabler/icons-vue'
import { useUiStore } from '@/stores/ui'

const { t } = useI18n()
const ui = useUiStore()
</script>
