<template>
  <div class="card max-w-xl">
    <div class="card-body">
      <h1 class="text-xl font-semibold">{{ t('session.no_access') }}</h1>
      <p class="mt-2 text-slate-600">{{ t('session.no_access_hint') }}</p>
      <p class="mt-4 text-sm text-slate-400">
        {{ t('session.logged_in_as', { user: session.fullName }) }}
      </p>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { useSessionStore } from '@/stores/session'

const { t } = useI18n()
const session = useSessionStore()
</script>
