<!--
  Zeiterfassung zu einem Ticket: Timer oder Dauer von Hand.

  Der Timerzustand liegt im gemeinsamen Store, nicht in dieser Komponente —
  dieselbe Uhr treibt die Leiste in der Kopfzeile. Auf dem Server existiert sie
  als Datensatz, überlebt also Neuladen und Gerätewechsel; pro Mitarbeiter
  kann nur eine laufen (eindeutiger Index).
-->
<template>
  <div class="card">
    <div class="card-header flex items-center justify-between">
      <h3 class="text-base font-semibold">{{ t('time.tracking') }}</h3>
      <span class="text-sm text-slate-500">
        {{ t('time.total') }}:
        <strong class="tabular-nums">{{ formatHours(entries.total_hours) }}</strong>
        {{ t('time.hours_short') }}
      </span>
    </div>

    <div class="card-body space-y-4">
      <!-- Timer läuft auf einem ANDEREN Ticket: Erst dort beenden, sonst wäre
           nicht mehr zuzuordnen, worauf die Zeit gebucht wird. -->
      <div
        v-if="timerOnOtherTicket"
        class="rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 text-sm text-amber-900"
      >
        {{ t('time.running_on', { ticket: timer.running.subject || timer.running.issue }) }}
      </div>

      <div v-else-if="timerHere" class="flex flex-wrap items-center gap-3">
        <div class="flex-1 min-w-[10rem]">
          <div class="text-xs" :class="timer.isWarning ? 'text-amber-700' : 'text-slate-500'">
            {{ t('time.elapsed') }}
          </div>
          <div
            class="text-2xl font-bold tabular-nums"
            :class="timer.isWarning ? 'text-amber-700' : 'text-slate-900'"
          >
            {{ formatHours(timer.elapsedHours) }}
          </div>
          <p v-if="timer.isWarning" class="text-xs text-amber-800 mt-0.5">
            {{ t('time.warning_long', { hours: timer.warningHours }) }}
          </p>
        </div>
        <button class="btn-primary" :disabled="timer.busy" @click="dialog = true">
          <IconPlayerStopFilled :size="15" />
          {{ t('time.stop') }}
        </button>
      </div>

      <div v-else>
        <button class="btn-primary" :disabled="timer.busy || !canTrack" @click="start()">
          <IconPlayerPlayFilled :size="15" />
          {{ t('time.start') }}
        </button>
      </div>

      <!-- Manuelle Erfassung -->
      <div class="pt-2 border-t border-slate-100">
        <div class="label">{{ t('time.manual') }}</div>
        <div class="flex flex-wrap items-end gap-2">
          <div class="w-28">
            <input
              v-model="manualHours"
              type="text"
              inputmode="decimal"
              class="input tabular-nums"
              placeholder="1:30"
              :disabled="busy || !canTrack"
            />
          </div>
          <div class="flex-1 min-w-[12rem]">
            <input
              v-model="manualNote"
              type="text"
              class="input"
              :placeholder="t('time.description')"
              :disabled="busy || !canTrack"
            />
          </div>
          <button class="btn-secondary" :disabled="busy || !canTrack || !manualValid" @click="book()">
            {{ t('time.book') }}
          </button>
        </div>
      </div>

      <!-- Gebuchte Einträge -->
      <div class="pt-2 border-t border-slate-100">
        <div class="label">{{ t('time.entries') }}</div>
        <p v-if="!entries.rows?.length" class="text-sm text-slate-400">
          {{ t('time.no_entries') }}
        </p>
        <ul v-else class="divide-y divide-slate-100">
          <li
            v-for="row in entries.rows"
            :key="row.name"
            class="py-2 flex items-baseline gap-3 text-sm"
          >
            <span class="tabular-nums font-medium w-16 shrink-0">
              {{ formatHours(row.hours) }} {{ t('time.hours_short') }}
            </span>
            <span class="text-slate-500 w-32 shrink-0">{{ row.employee_name }}</span>
            <span class="text-slate-600 truncate">{{ row.description }}</span>
            <span class="ml-auto text-xs text-slate-400 shrink-0">
              {{ formatDate(row.from_time, locale) }}
            </span>
          </li>
        </ul>
      </div>
    </div>

    <StopTimerDialog
      v-if="timerHere"
      :open="dialog"
      :issue="issue"
      :subject="timer.running?.subject"
      :measured="timer.elapsedHours"
      :note="timer.running?.note"
      :busy="timer.busy"
      @cancel="dialog = false"
      @confirm="confirmStop"
      @discard="discardTimer"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { IconPlayerPlayFilled, IconPlayerStopFilled } from '@tabler/icons-vue'
import StopTimerDialog from '@/components/tickets/StopTimerDialog.vue'
import { api } from '@/utils/api'
import { formatDate, formatHours, parseHours } from '@/utils/format'
import { useTimerStore } from '@/stores/timer'
import { useToastStore } from '@/stores/toast'

const props = defineProps({
  issue: { type: String, required: true },
  canTrack: { type: Boolean, default: true },
})
const emit = defineEmits(['changed'])

const { t, locale } = useI18n()
const toast = useToastStore()
const timer = useTimerStore()

const entries = ref({ rows: [], total_hours: 0 })
const busy = ref(false)
const dialog = ref(false)

const timerHere = computed(() => timer.isRunningOn(props.issue))
const timerOnOtherTicket = computed(
  () => !!timer.running && timer.running.issue !== props.issue,
)

async function loadEntries() {
  entries.value = await api
    .getTimeEntries(props.issue)
    .catch(() => ({ rows: [], total_hours: 0 }))
}

async function start() {
  try {
    await timer.start(props.issue)
  } catch (e) {
    toast.error(e.message)
  }
}

async function confirmStop({ hours, description }) {
  try {
    await timer.stop({ hours, description })
    dialog.value = false
    toast.success(t('time.booked'))
    await loadEntries()
    emit('changed')
  } catch (e) {
    toast.error(e.message)
  }
}

async function discardTimer() {
  try {
    await timer.stop({ discard: true })
    dialog.value = false
    toast.info(t('time.discarded'))
  } catch (e) {
    toast.error(e.message)
  }
}

const manualHours = ref('')
const manualNote = ref('')
const manualValid = computed(() => {
  const h = parseHours(manualHours.value)
  return Number.isFinite(h) && h > 0 && h <= 24
})

async function book() {
  busy.value = true
  try {
    await api.logTime({
      issue: props.issue,
      hours: parseHours(manualHours.value),
      description: manualNote.value || null,
    })
    manualHours.value = ''
    manualNote.value = ''
    toast.success(t('time.booked'))
    await loadEntries()
    emit('changed')
  } catch (e) {
    toast.error(e.message)
  } finally {
    busy.value = false
  }
}

watch(() => props.issue, loadEntries)
onMounted(loadEntries)
</script>
