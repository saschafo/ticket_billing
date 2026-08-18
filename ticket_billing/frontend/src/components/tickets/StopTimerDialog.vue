<!--
  Bestätigung vor dem Buchen.

  Der Timer wird nicht beim Öffnen gestoppt: Solange der Dialog offen ist,
  läuft er weiter. Wer "Abbrechen" wählt, arbeitet einfach weiter — das ist
  der Grund, warum die Dauer erst beim Öffnen eingefroren wird und die Buchung
  genau diesen Wert nimmt.
-->
<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-40 flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-slate-900/40" @click="$emit('cancel')" />

      <div class="relative card w-full max-w-md">
        <div class="card-header">
          <h3 class="text-base font-semibold">{{ t('time.stop_title') }}</h3>
          <p class="text-sm text-slate-500 mt-0.5 truncate">{{ subject || issue }}</p>
        </div>

        <div class="card-body space-y-4">
          <div class="rounded-lg bg-slate-50 px-4 py-3 text-sm text-slate-600">
            {{ t('time.measured') }}:
            <strong class="tabular-nums text-slate-900">{{ formatHours(measured) }}</strong>
            {{ t('time.hours_short') }}
          </div>

          <div>
            <label class="label" for="dur">{{ t('time.booked_duration') }}</label>
            <input
              id="dur"
              ref="durationInput"
              v-model="duration"
              type="text"
              inputmode="decimal"
              class="input tabular-nums"
              :class="{ 'border-red-400': invalid }"
              placeholder="1:30"
            />
            <p class="mt-1 text-xs" :class="invalid ? 'text-red-600' : 'text-slate-400'">
              {{ invalid ? t('time.invalid_duration') : t('time.duration_hint') }}
            </p>
          </div>

          <div>
            <label class="label" for="note">{{ t('time.description') }}</label>
            <input id="note" v-model="noteDraft" type="text" class="input" />
          </div>
        </div>

        <div class="card-header border-t border-b-0 flex flex-wrap gap-2">
          <button class="btn-primary" :disabled="invalid || busy" @click="$emit('confirm', { hours: parsed, description: noteDraft })">
            {{ t('time.book') }}
          </button>
          <button class="btn-secondary" :disabled="busy" @click="$emit('cancel')">
            {{ t('actions.cancel') }}
          </button>
          <button class="btn-danger ml-auto" :disabled="busy" @click="$emit('discard')">
            {{ t('time.discard') }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { formatHours, parseHours } from '@/utils/format'

const props = defineProps({
  open: { type: Boolean, default: false },
  issue: { type: String, default: '' },
  subject: { type: String, default: '' },
  measured: { type: Number, default: 0 },
  note: { type: String, default: '' },
  busy: { type: Boolean, default: false },
})
defineEmits(['confirm', 'cancel', 'discard'])

const { t } = useI18n()

const duration = ref('')
// noteDraft, nicht note: Die gleichnamige Prop liefert nur den
// Anfangswert. Hiesse beides gleich, verdeckt die lokale Variable die
// Prop in der Vorlage -- es faellt niemandem auf, bis es das tut.
const noteDraft = ref('')
const durationInput = ref(null)

const parsed = computed(() => parseHours(duration.value))
const invalid = computed(
  () => !Number.isFinite(parsed.value) || parsed.value <= 0 || parsed.value > 24,
)

watch(
  () => props.open,
  async (isOpen) => {
    if (!isOpen) return
    // Beim Öffnen einfrieren: Der Timer läuft weiter, aber gebucht wird der
    // Wert, den der Nutzer hier sieht und bestätigt.
    duration.value = formatHours(props.measured)
    noteDraft.value = props.note || ''
    await nextTick()
    durationInput.value?.select()
  },
  { immediate: true },
)
</script>
