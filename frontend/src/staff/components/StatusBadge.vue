<script setup lang="ts">
import { Badge } from 'frappe-ui'
import { computed } from 'vue'
import { __ } from '@/shared/translate'

const props = defineProps<{ status: string; sealing?: string; sending?: string }>()
const theme = computed(() => {
  if (props.status === 'Completed') return 'green'
  if (['Declined', 'Voided', 'Expired'].includes(props.status)) return 'red'
  if (props.sealing === 'Failed' || props.sending === 'Failed') return 'red'
  if (props.sending === 'Queued') return 'blue'
  if (['Sent', 'In Progress'].includes(props.status)) return 'blue'
  return 'gray'
})
const label = computed(() =>
  props.status === 'Draft' && props.sending === 'Queued'
    ? __('Sending')
    : props.status === 'Draft' && props.sending === 'Failed'
      ? __('Send failed')
      : props.status === 'In Progress' && props.sealing && !['Not Started', 'Sealed'].includes(props.sealing)
        ? __('Sealing: {0}', [__(props.sealing)])
        : __(props.status),
)
</script>

<template>
  <Badge :theme="theme" :label="label" />
</template>
