<template>
  <label class="inline-flex items-center gap-1.5">
    <span class="sr-only">{{ t('language.switch') }}</span>
    <IconLanguage :size="18" :stroke-width="1.8" class="text-slate-400 shrink-0" aria-hidden="true" />
    <select
      class="input w-auto py-1.5 pr-8 text-sm"
      :value="locale"
      :aria-label="t('language.switch')"
      :disabled="busy"
      @change="change($event.target.value)"
    >
      <option v-for="l in AVAILABLE_LOCALES" :key="l.code" :value="l.code">
        {{ l.label }}
      </option>
    </select>
  </label>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { IconLanguage } from '@tabler/icons-vue'
import { AVAILABLE_LOCALES, setLocale } from '@/i18n'
import { useToastStore } from '@/stores/toast'

const { t, locale } = useI18n()
const toast = useToastStore()
const busy = ref(false)

async function change(code) {
  busy.value = true
  try {
    await setLocale(code)
    // Nach dem Umschalten ist t() bereits in der neuen Sprache — die
    // Bestätigung erscheint also in der Sprache, die man gerade gewählt hat.
    toast.success(t('language.saved'))
  } finally {
    busy.value = false
  }
}
</script>
