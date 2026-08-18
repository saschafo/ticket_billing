<template>
  <span class="badge gap-1" :class="cls">
    <component :is="icon" :size="13" :stroke-width="2.2" class="shrink-0" />
    {{ t(`status.${status}`) }}
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  IconCircleCheck,
  IconCircleDot,
  IconLock,
  IconMessage,
  IconPlayerPause,
} from '@tabler/icons-vue'

const props = defineProps({ status: { type: String, default: 'Open' } })
const { t } = useI18n()

const icon = computed(
  () =>
    ({
      Open: IconCircleDot,
      Replied: IconMessage,
      'On Hold': IconPlayerPause,
      Resolved: IconCircleCheck,
      Closed: IconLock,
    })[props.status] || IconCircleDot,
)

const cls = computed(
  () =>
    ({
      Open: 'badge-blue',
      Replied: 'badge-purple',
      'On Hold': 'badge-yellow',
      Resolved: 'badge-green',
      Closed: 'badge-gray',
    })[props.status] || 'badge-gray',
)
</script>
