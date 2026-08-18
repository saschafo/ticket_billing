<!--
  Meine Zeiterfassungen.

  Entwürfe sind änderbar und löschbar, gebuchte Einträge nur noch lesbar. Was
  geht, sagt der Server über "editable" — die Oberfläche leitet das nicht aus
  dem Status ab, weil dort auch mehrzeilige Altbestände hereinkommen können.
-->
<template>
  <div class="space-y-6">
    <div>
      <h1>{{ t('views.my_times_title') }}</h1>
      <p class="text-slate-500 mt-1">{{ t('views.my_times_subtitle') }}</p>
    </div>

    <div class="grid grid-cols-2 lg:grid-cols-3 gap-4">
      <StatCard :label="t('entry.drafts')" :value="data.draft_count || 0" :tone="data.draft_count ? 'warn' : 'default'" />
      <StatCard
        :label="t('entry.draft_hours')"
        :value="formatHours(data.draft_hours) + ' ' + t('time.hours_short')"
      />
      <StatCard :label="t('entry.total_entries')" :value="(data.rows || []).length" />
    </div>

    <div class="card">
      <div class="card-header flex flex-wrap items-center gap-3">
        <label class="inline-flex items-center gap-2 text-sm text-slate-600">
          <input v-model="onlyDraft" type="checkbox" class="rounded border-slate-300" />
          {{ t('entry.only_drafts') }}
        </label>
        <span class="text-xs text-slate-400">{{ t('entry.hint_submit') }}</span>
        <button class="btn-secondary btn-sm ml-auto" @click="reload()">
          {{ t('actions.refresh') }}
        </button>
      </div>

      <AppSpinner v-if="loading" />

      <template v-else>
        <div class="table-wrapper">
          <table class="table">
            <thead>
              <tr>
                <th class="w-28">{{ t('entry.status') }}</th>
                <th class="w-28">{{ t('entry.date') }}</th>
                <th>{{ t('ticket.one') }}</th>
                <th>{{ t('time.description') }}</th>
                <th class="w-24 text-right">{{ t('stats.hours') }}</th>
                <th class="w-28"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in data.rows || []" :key="row.name">
                <td><EntryStatusBadge :status="row.status" /></td>
                <td class="text-slate-500 text-xs">{{ formatDate(row.start_date, locale) }}</td>
                <td class="text-slate-800 truncate max-w-[16rem]">
                  {{ row.issue_subject || row.issue || '—' }}
                </td>
                <td class="text-slate-600 truncate max-w-[18rem]">{{ row.description }}</td>
                <td class="text-right tabular-nums font-medium">{{ formatHours(row.hours) }}</td>
                <td class="text-right">
                  <div v-if="row.editable" class="flex justify-end gap-1">
                    <button class="btn-secondary btn-sm" @click="edit(row)">
                      {{ t('actions.edit') }}
                    </button>
                    <button class="btn-secondary btn-sm !text-red-600" @click="remove(row)">
                      {{ t('actions.delete') }}
                    </button>
                  </div>
                  <span v-else class="text-xs text-slate-400">{{ t('entry.locked') }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <p v-if="!(data.rows || []).length" class="text-center text-sm text-slate-400 py-8">
          {{ t('entry.none') }}
        </p>
      </template>
    </div>

    <EntryEditDialog
      :open="!!editing"
      :entry="editing"
      :busy="busy"
      @cancel="editing = null"
      @save="save"
    />
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppSpinner from '@/components/ui/AppSpinner.vue'
import StatCard from '@/components/ui/StatCard.vue'
import EntryStatusBadge from '@/components/ui/EntryStatusBadge.vue'
import EntryEditDialog from '@/components/time/EntryEditDialog.vue'
import { api } from '@/utils/api'
import { formatDate, formatHours } from '@/utils/format'
import { useToastStore } from '@/stores/toast'

const { t, locale } = useI18n()
const toast = useToastStore()

const data = ref({ rows: [], draft_count: 0, draft_hours: 0 })
const loading = ref(true)
const busy = ref(false)
const onlyDraft = ref(false)
const editing = ref(null)

async function reload() {
  loading.value = true
  try {
    data.value = await api.listMyTimeEntries({ only_draft: onlyDraft.value ? 1 : 0 })
  } catch (e) {
    toast.error(e.message)
  } finally {
    loading.value = false
  }
}

function edit(row) {
  editing.value = row
}

async function save({ hours, description }) {
  busy.value = true
  try {
    await api.updateTimeEntry({ name: editing.value.name, hours, description })
    editing.value = null
    toast.success(t('common.saved'))
    await reload()
  } catch (e) {
    toast.error(e.message)
  } finally {
    busy.value = false
  }
}

async function remove(row) {
  if (!window.confirm(t('entry.confirm_delete'))) return
  try {
    await api.deleteTimeEntry(row.name)
    toast.success(t('entry.deleted'))
    await reload()
  } catch (e) {
    toast.error(e.message)
  }
}

watch(onlyDraft, reload)
onMounted(reload)
</script>
