<template>
  <div>
    <div class="table-wrapper">
      <table class="table">
        <thead>
          <tr>
            <th class="w-36">{{ t('ticket.id') }}</th>
            <th>{{ t('ticket.subject') }}</th>
            <th class="w-28">{{ t('ticket.status') }}</th>
            <th class="w-24">{{ t('ticket.origin') }}</th>
            <th v-if="showAssignee" class="w-40">{{ t('ticket.assignee') }}</th>
            <th class="w-32">{{ t('ticket.updated') }}</th>
            <th v-if="showTimer" class="w-16"><span class="sr-only">{{ t('time.timer') }}</span></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in rows"
            :key="row.name"
            class="cursor-pointer"
            @click="$emit('open', row.name)"
          >
            <td class="font-mono text-xs text-slate-500">{{ row.name }}</td>
            <!-- Der Hinweis steht am Betreff, nicht in einer eigenen
                 Spalte: Er betrifft nur wenige Zeilen, und eine Spalte, die
                 meist leer ist, kostet Breite ohne Gegenwert. Nur bei einer
                 Nachricht nach der Eroeffnung -- sonst traege ihn jedes neue
                 Ticket, und ein Hinweis, den alle tragen, sagt nichts. -->
            <td class="font-medium text-slate-800">
              <span class="inline-flex items-center gap-2">
                <span
                  v-if="row.awaiting_reply && row.is_follow_up"
                  class="badge badge-blue gap-1"
                  :title="t('ticket.new_reply_hint')"
                >
                  <IconMailDown :size="12" :stroke-width="2" />
                  {{ t('ticket.new_reply') }}
                </span>
                {{ row.subject }}
              </span>
            </td>
            <td><StatusBadge :status="row.status" /></td>
            <td class="text-slate-600">{{ t(`origin.${row.tb_origin}`) }}</td>
            <td v-if="showAssignee">
              <span v-if="row.assignee_name" class="text-slate-700">{{ row.assignee_name }}</span>
              <span v-else class="badge badge-yellow">{{ t('ticket.unassigned') }}</span>
            </td>
            <td class="text-slate-500 text-xs">{{ formatDate(row.modified, locale) }}</td>

            <!-- Zeiterfassung direkt aus der Liste: Der häufigste Fall ist
                 "ich fange jetzt damit an", und dafür soll niemand erst das
                 Detail öffnen müssen. @click.stop, damit die Zeile sich
                 nicht gleichzeitig öffnet. -->
            <td v-if="showTimer" class="text-right">
              <button
                v-if="timer.isRunningOn(row.name)"
                class="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-amber-100 text-amber-700 hover:bg-amber-200"
                :title="t('time.running')"
                @click.stop="$emit('stop-timer', row.name)"
              >
                <IconPlayerStopFilled :size="15" />
              </button>
              <button
                v-else
                class="inline-flex items-center justify-center w-8 h-8 rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700 disabled:opacity-40"
                :title="t('time.start')"
                :disabled="timer.busy"
                @click.stop="$emit('start-timer', row.name)"
              >
                <IconPlayerPlayFilled :size="15" />
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-if="!rows.length" class="text-center text-sm text-slate-400 py-8">
      {{ emptyText || t('ticket.none_found') }}
    </p>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { IconMailDown, IconPlayerPlayFilled, IconPlayerStopFilled } from '@tabler/icons-vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { formatDate } from '@/utils/format'
import { useTimerStore } from '@/stores/timer'

defineProps({
  rows: { type: Array, default: () => [] },
  showAssignee: { type: Boolean, default: false },
  showTimer: { type: Boolean, default: false },
  emptyText: { type: String, default: '' },
})
defineEmits(['open', 'start-timer', 'stop-timer'])

const { t, locale } = useI18n()
const timer = useTimerStore()
</script>
