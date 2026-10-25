<script setup lang="ts">
import { Badge } from 'frappe-ui'
import { computed } from 'vue'
import { requestStatus } from '../labels'

const props = defineProps<{ status: string; sealing?: string; sending?: string }>()
const view = computed(() => requestStatus(props.status, props.sealing, props.sending))
</script>

<template>
  <Badge :theme="view.theme" :label="view.label" />
</template>
