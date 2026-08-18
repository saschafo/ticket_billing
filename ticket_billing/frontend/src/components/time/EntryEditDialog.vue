<!-- Dauer und Notiz eines Entwurfs ändern. Auch die Leitung nutzt ihn, um vor
     dem Buchen zu korrigieren. -->
<template>
  <Teleport to="body">
    <div v-if="open && entry" class="fixed inset-0 z-40 flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-slate-900/40" @click="$emit('cancel')" />

      <div class="relative card w-full max-w-md">
        <div class="card-header">
          <h3 class="text-base font-semibold">{{ t('entry.edit_title') }}</h3>
          <p class="text-sm text-slate-500 mt-0.5 truncate">
            {{ entry.issue_subject || entry.issue }}
          </p>
        </div>

        <div class="card-body space-y-4">
          <dl v-if="entry.employee_name" class="text-sm">
            <dt class="text-slate-500">{{ t('stats.member') }}</dt>
            <dd class="text-slate-800">{{ entry.employee_name }}</dd>
          </dl>

          <div>
            <label class="label" for="eh">{{ t('time.hours') }}</label>
            <input
              id="eh"
              ref="hoursInput"
              v-model="hours"
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
            <label class="label" for="ed">{{ t('time.description') }}</label>
            <input id="ed" v-model="description" type="text" class="input" />
          </div>
        </div>

        <div class="card-header border-t border-b-0 flex gap-2">
          <button
            class="btn-primary"
            :disabled="invalid || busy"
            @click="$emit('save', { hours: parsed, description })"
          >
            {{ t('actions.save') }}
          </button>
          <button class="btn-secondary" :disabled="busy" @click="$emit('cancel')">
            {{ t('actions.cancel') }}
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
  entry: { type: Object, default: null },
  busy: { type: Boolean, default: false },
})
defineEmits(['save', 'cancel'])

const { t } = useI18n()

const hours = ref('')
const description = ref('')
const hoursInput = ref(null)

const parsed = computed(() => parseHours(hours.value))
const invalid = computed(
  () => !Number.isFinite(parsed.value) || parsed.value <= 0 || parsed.value > 24,
)

watch(
  () => [props.open, props.entry?.name],
  async () => {
    if (!props.open || !props.entry) return
    hours.value = formatHours(props.entry.hours)
    description.value = props.entry.description || ''
    await nextTick()
    hoursInput.value?.select()
  },
  { immediate: true },
)
</script>
