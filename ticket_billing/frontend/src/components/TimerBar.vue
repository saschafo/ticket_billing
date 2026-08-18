<!--
  Leiste unter der Navigation, solange ein Timer läuft.

  Sie steht in der Shell und nicht in einer einzelnen Ansicht: Ein laufender
  Timer ist überall relevant, und gerade beim Wechsel in eine andere Ansicht
  vergisst man ihn sonst.
-->
<template>
  <!-- Doppelt abgesichert: Die Shell fragt für solche Rollen gar nicht erst
       ab, und selbst mit einem Zustand im Store bliebe die Leiste hier weg. -->
  <div
    v-if="timer.running && session.canTrackTime"
    class="border-b transition-colors"
    :class="timer.isWarning ? 'bg-amber-50 border-amber-300' : 'bg-slate-50 border-slate-200'"
  >
    <div class="mx-auto px-4 py-2 flex flex-wrap items-center gap-x-4 gap-y-2" :class="ui.containerClass">
      <span
        class="inline-flex items-center gap-2 text-sm font-medium"
        :class="timer.isWarning ? 'text-amber-900' : 'text-slate-700'"
      >
        <span
          class="w-2 h-2 rounded-full"
          :class="timer.isWarning ? 'bg-amber-500' : 'bg-emerald-500 animate-pulse'"
        />
        {{ t('time.running') }}
      </span>

      <span class="text-sm text-slate-600 truncate min-w-0 flex-1">
        {{ timer.running.subject || timer.running.issue }}
      </span>

      <span
        class="tabular-nums text-lg font-bold"
        :class="timer.isWarning ? 'text-amber-700' : 'text-slate-900'"
      >
        {{ formatHours(timer.elapsedHours) }}
      </span>

      <span v-if="timer.isWarning" class="text-xs text-amber-800">
        {{ t('time.warning_long', { hours: timer.warningHours }) }}
      </span>

      <button class="btn-primary btn-sm" :disabled="timer.busy" @click="dialog = true">
        <IconPlayerStopFilled :size="14" />
        {{ t('time.stop') }}
      </button>
    </div>

    <StopTimerDialog
      :open="dialog"
      :issue="timer.running.issue"
      :subject="timer.running.subject"
      :measured="timer.elapsedHours"
      :note="timer.running.note"
      :busy="timer.busy"
      @cancel="dialog = false"
      @confirm="confirm"
      @discard="discard"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { IconPlayerStopFilled } from '@tabler/icons-vue'
import StopTimerDialog from '@/components/tickets/StopTimerDialog.vue'
import { formatHours } from '@/utils/format'
import { useSessionStore } from '@/stores/session'
import { useUiStore } from '@/stores/ui'
import { useTimerStore } from '@/stores/timer'
import { useToastStore } from '@/stores/toast'

const { t } = useI18n()
const session = useSessionStore()
const ui = useUiStore()
const timer = useTimerStore()
const toast = useToastStore()
const emit = defineEmits(['booked'])

const dialog = ref(false)

async function confirm({ hours, description }) {
  try {
    await timer.stop({ hours, description })
    dialog.value = false
    toast.success(t('time.booked'))
    emit('booked')
  } catch (e) {
    toast.error(e.message)
  }
}

async function discard() {
  try {
    await timer.stop({ discard: true })
    dialog.value = false
    toast.info(t('time.discarded'))
    emit('booked')
  } catch (e) {
    toast.error(e.message)
  }
}
</script>
