<!--
  Ticketdetail als seitliche Lade. Zeigt Stammdaten, erlaubt das Bearbeiten
  der freigegebenen Felder, die Umverteilung (nur Leitung) und die
  Zeiterfassung.

  Welche Schaltflächen erscheinen, sagt der Server über can_write und
  can_reassign — die Oberfläche rät das nicht selbst.
-->
<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-30 flex">
      <div class="flex-1 bg-slate-900/30" @click="$emit('close')" />

      <aside class="w-full max-w-2xl bg-white h-full overflow-y-auto shadow-2xl">
        <AppSpinner v-if="loading" />

        <div v-else-if="ticket" class="pb-10">
          <div class="sticky top-0 z-10 bg-white border-b border-slate-200">
            <div class="px-6 pt-4 flex items-start gap-4">
              <div class="min-w-0 flex-1">
                <div class="font-mono text-xs text-slate-400">{{ ticket.name }}</div>
                <h2 class="text-lg font-semibold text-slate-900 truncate">{{ ticket.subject }}</h2>
              </div>
              <button class="btn-secondary btn-sm" @click="$emit('close')">
                {{ t('actions.close') }}
              </button>
            </div>

            <!-- Zwei Reiter statt einer langen Seite: Ein Ticket mit vielen
                 E-Mails schob Zeiterfassung und Bearbeitung so weit nach
                 unten, dass man dafür scrollen musste. In der klebenden
                 Kopfzeile bleibt der Wechsel immer erreichbar. -->
            <div class="px-6 flex gap-5 -mb-px">
              <button
                v-for="entry in tabs"
                :key="entry.id"
                class="py-2.5 text-sm border-b-2 transition-colors"
                :class="
                  tab === entry.id
                    ? 'border-blue-600 text-blue-700 font-medium'
                    : 'border-transparent text-slate-500 hover:text-slate-800'
                "
                @click="tab = entry.id"
              >
                {{ entry.label }}
                <span v-if="entry.count" class="ml-1 text-xs text-slate-400">{{ entry.count }}</span>
              </button>
            </div>
          </div>

          <div class="px-6 py-5">
            <div v-show="tab === 'vorgang'" class="space-y-6">
            <!-- Stammdaten -->
            <dl class="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
              <div>
                <dt class="text-slate-500">{{ t('ticket.status') }}</dt>
                <dd class="mt-0.5"><StatusBadge :status="ticket.status" /></dd>
              </div>
              <div>
                <dt class="text-slate-500">{{ t('ticket.origin') }}</dt>
                <dd class="mt-0.5 text-slate-800">{{ t(`origin.${ticket.tb_origin}`) }}</dd>
              </div>
              <div>
                <dt class="text-slate-500">{{ t('ticket.department') }}</dt>
                <dd class="mt-0.5 text-slate-800">{{ ticket.tb_department }}</dd>
              </div>
              <div>
                <dt class="text-slate-500">{{ t('ticket.assignee') }}</dt>
                <dd class="mt-0.5 text-slate-800">
                  {{ ticket.assignee_name || t('ticket.unassigned') }}
                </dd>
              </div>
              <div v-if="ticket.customer">
                <dt class="text-slate-500">{{ t('ticket.customer') }}</dt>
                <dd class="mt-0.5 text-slate-800">{{ ticket.customer }}</dd>
              </div>
              <div v-if="ticket.raised_by">
                <dt class="text-slate-500">{{ t('ticket.raised_by') }}</dt>
                <dd class="mt-0.5 text-slate-800 truncate">{{ ticket.raised_by }}</dd>
              </div>
              <div>
                <dt class="text-slate-500">{{ t('ticket.created') }}</dt>
                <dd class="mt-0.5 text-slate-800">{{ formatDateTime(ticket.creation, locale) }}</dd>
              </div>
              <div>
                <dt class="text-slate-500">{{ t('ticket.updated') }}</dt>
                <dd class="mt-0.5 text-slate-800">{{ formatDateTime(ticket.modified, locale) }}</dd>
              </div>
            </dl>

            <TimeTracker
              v-if="ticket.can_write"
              :issue="ticket.name"
              :can-track="ticket.can_write"
              @changed="$emit('changed')"
            />

            <div v-if="ticket.description">
              <div class="label">{{ t('ticket.description') }}</div>
              <!-- Als Text, nicht als HTML: siehe stripHtml() in utils/format.js -->
              <div class="text-sm text-slate-700 whitespace-pre-wrap break-words">
                {{ stripHtml(ticket.description) }}
              </div>
            </div>

            <!-- Bearbeiten -->
            <div v-if="ticket.can_write" class="card">
              <div class="card-body space-y-3">
                <div>
                  <label class="label">{{ t('ticket.status') }}</label>
                  <select v-model="form.status" class="input">
                    <option v-for="s in options.statuses || []" :key="s" :value="s">
                      {{ t(`status.${s}`) }}
                    </option>
                  </select>
                </div>
                <div>
                  <label class="label">{{ t('ticket.subject') }}</label>
                  <input v-model="form.subject" type="text" class="input" />
                </div>
                <button class="btn-primary" :disabled="saving" @click="save()">
                  {{ t('actions.save') }}
                </button>
              </div>
            </div>

            <!-- Umverteilen: nur Leitung -->
            <div v-if="ticket.can_reassign" class="card">
              <div class="card-body">
                <div class="label">{{ t('reassign.title') }}</div>
                <p class="text-xs text-slate-400 mb-2">{{ t('reassign.hint') }}</p>
                <div class="flex flex-wrap gap-2">
                  <select v-model="targetEmployee" class="input flex-1 min-w-[12rem]">
                    <option value="">—</option>
                    <option v-for="m in members" :key="m.employee" :value="m.employee">
                      {{ m.employee_name }} ({{ m.open_tickets }})
                    </option>
                  </select>
                  <button
                    class="btn-secondary"
                    :disabled="saving || !targetEmployee || targetEmployee === ticket.tb_assigned_employee"
                    @click="reassign()"
                  >
                    {{ t('actions.reassign') }}
                  </button>
                </div>
              </div>
            </div>


            </div>

            <div v-show="tab === 'verlauf'" class="space-y-6">
            <!-- E-Mail-Verlauf. Bei per Mail erzeugten Tickets steht der Text
                 NICHT im Ticket, sondern in verknüpften Communication-Sätzen —
                 ohne diesen Block sähe man nur den Betreff. -->
            <div v-if="(ticket.conversation || []).length">
              <div class="label">{{ t('ticket.conversation') }}</div>
              <ul class="space-y-3">
                <li
                  v-for="msg in ticket.conversation"
                  :key="msg.name"
                  class="rounded-lg border px-4 py-3"
                  :class="
                    msg.sent_or_received === 'Received'
                      ? 'bg-slate-50 border-slate-200'
                      : 'bg-blue-50/60 border-blue-100'
                  "
                >
                  <div class="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-xs">
                    <IconMailDown
                      v-if="msg.sent_or_received === 'Received'"
                      :size="14"
                      :stroke-width="1.8"
                      class="text-slate-400 shrink-0"
                    />
                    <IconMailUp v-else :size="14" :stroke-width="1.8" class="text-blue-400 shrink-0" />
                    <span class="font-medium text-slate-700">
                      {{ msg.sender_full_name || msg.sender }}
                    </span>
                    <span class="text-slate-400">{{ msg.sender }}</span>
                    <span class="ml-auto text-slate-400">
                      {{ formatDateTime(msg.creation, locale) }}
                    </span>
                  </div>

                  <div class="mt-2 text-sm text-slate-700 whitespace-pre-wrap break-words">
                    {{ stripHtml(msg.content) }}
                  </div>

                  <div v-if="(msg.attachments || []).length" class="mt-2 flex flex-wrap gap-2">
                    <a
                      v-for="file in msg.attachments"
                      :key="file.file_url"
                      :href="file.file_url"
                      target="_blank"
                      rel="noopener"
                      class="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800 underline"
                    >
                      <IconPaperclip :size="13" :stroke-width="1.8" />
                      {{ file.file_name }}
                    </a>
                  </div>
                </li>
              </ul>
            </div>

            <!-- Antworten. Nur wenn ein Empfänger bekannt ist -- bei einem
                 rein internen Ticket ohne Absenderadresse gäbe es niemanden,
                 an den die Mail gehen könnte. -->
            <div v-if="ticket.can_write && canReply" class="card">
              <div class="card-body space-y-3">
                <div class="label">{{ t('reply.title') }}</div>

                <div>
                  <label class="label text-xs font-normal text-slate-500" for="rcpt">
                    {{ t('reply.recipients') }}
                  </label>
                  <input id="rcpt" v-model="replyTo" type="text" class="input" />
                </div>

                <textarea
                  v-model="replyText"
                  rows="5"
                  class="input"
                  :placeholder="t('reply.placeholder')"
                />

                <div class="flex flex-wrap items-center gap-2">
                  <button
                    class="btn-primary"
                    :disabled="sending || !replyText.trim()"
                    @click="sendReply()"
                  >
                    <IconSend :size="15" :stroke-width="1.8" />
                    {{ sending ? t('reply.sending') : t('reply.send') }}
                  </button>
                  <span class="text-xs text-slate-400">{{ t('reply.hint') }}</span>
                </div>
              </div>
            </div>
            </div>
          </div>
        </div>
      </aside>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { IconMailDown, IconMailUp, IconPaperclip, IconSend } from '@tabler/icons-vue'
import AppSpinner from '@/components/ui/AppSpinner.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import TimeTracker from '@/components/tickets/TimeTracker.vue'
import { api } from '@/utils/api'
import { formatDateTime, stripHtml } from '@/utils/format'
import { useToastStore } from '@/stores/toast'

const props = defineProps({
  name: { type: String, default: '' },
  open: { type: Boolean, default: false },
  options: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['close', 'changed'])

const { t, locale } = useI18n()
const toast = useToastStore()

const ticket = ref(null)
const loading = ref(false)
const saving = ref(false)
const members = ref([])
const targetEmployee = ref('')
const form = reactive({ status: '', subject: '' })

const tab = ref('vorgang')
const tabs = computed(() => [
  { id: 'vorgang', label: t('ticket.tab_case') },
  {
    id: 'verlauf',
    label: t('ticket.tab_conversation'),
    count: (ticket.value?.conversation || []).length,
  },
])

async function load() {
  if (!props.name) return
  loading.value = true
  ticket.value = null
  try {
    const data = await api.getTicket(props.name)
    ticket.value = data
    form.status = data.status
    form.subject = data.subject
    targetEmployee.value = data.tb_assigned_employee || ''
    prefillReply(data)
    // Hat zuletzt der Aussteller geschrieben, ist der Verlauf das, was der
    // Bearbeiter zuerst sehen will -- sonst die Stammdaten.
    const letzte = (data.conversation || []).at(-1)
    tab.value = letzte?.sent_or_received === 'Received' ? 'verlauf' : 'vorgang' 

    members.value = data.can_reassign
      ? await api.getDepartmentMembers(data.tb_department).catch(() => [])
      : []
  } catch (e) {
    toast.error(e.message)
    emit('close')
  } finally {
    loading.value = false
  }
}

// Antworten geht nur, wenn eine Adresse bekannt ist: der Absender der letzten
// eingegangenen Nachricht, sonst der ursprüngliche Absender des Tickets.
const canReply = computed(() => {
  const received = (ticket.value?.conversation || []).filter((m) => m.sent_or_received === 'Received')
  return !!(received.length || ticket.value?.raised_by)
})

const replyText = ref('')
const replyTo = ref('')
const sending = ref(false)

function prefillReply(data) {
  const received = (data?.conversation || []).filter((m) => m.sent_or_received === 'Received')
  replyTo.value = received.length ? received[received.length - 1].sender : data?.raised_by || ''
  replyText.value = ''
}

async function sendReply() {
  sending.value = true
  try {
    const res = await api.replyToTicket({
      name: ticket.value.name,
      message: replyText.value,
      recipients: replyTo.value,
    })
    replyText.value = ''
    ticket.value = { ...ticket.value, conversation: res.conversation, status: res.status }
    form.status = res.status
    toast.success(t('reply.sent', { to: res.recipients.join(', ') }))
    emit('changed')
  } catch (e) {
    toast.error(e.message)
  } finally {
    sending.value = false
  }
}

async function save() {
  saving.value = true
  try {
    ticket.value = await api.updateTicket({
      name: ticket.value.name,
      status: form.status,
      subject: form.subject,
    })
    toast.success(t('common.saved'))
    emit('changed')
  } catch (e) {
    toast.error(e.message)
  } finally {
    saving.value = false
  }
}

async function reassign() {
  saving.value = true
  try {
    ticket.value = await api.reassignTicket(ticket.value.name, targetEmployee.value)
    members.value = await api.getDepartmentMembers(ticket.value.tb_department).catch(() => [])
    toast.success(t('reassign.done', { name: ticket.value.assignee_name }))
    emit('changed')
  } catch (e) {
    toast.error(e.message)
  } finally {
    saving.value = false
  }
}

watch(() => [props.name, props.open], () => props.open && load(), { immediate: true })
</script>
