<template>
  <span class="badge gap-1" :class="cls">
    <component :is="icon" :size="13" :stroke-width="2.2" class="shrink-0" />
    {{ t(`entry_status.${status}`) }}
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { IconBan, IconCircleCheck, IconPencil } from '@tabler/icons-vue'

const props = defineProps({ status: { type: String, default: 'draft' } })
const { t } = useI18n()

const icon = computed(
  () =>
    ({ draft: IconPencil, submitted: IconCircleCheck, cancelled: IconBan })[props.status] ||
    IconPencil,
)

// Entwurf ist der Zustand, in dem noch etwas zu tun ist -- deshalb auffällig.
// Gebucht ist erledigt und darf ruhig zurücktreten.
const cls = computed(
  () =>
    ({
      draft: 'badge-yellow',
      submitted: 'badge-green',
      cancelled: 'badge-gray',
    })[props.status] || 'badge-gray',
)
</script>
