<script setup lang="ts">
// The loading, error and empty states of a frappe-ui resource, the same on every page. The default
// slot shows once there is data; a reload keeps the old data on screen instead of a skeleton.
import { computed } from 'vue'
import { __ } from '@/shared/translate'
import { errorMessage } from '../api'
import ErrorState from './ErrorState.vue'
import ListSkeleton from './ListSkeleton.vue'

// A createResource result, or a createListResource result (its error sits on `list`).
export interface LoadableResource {
  data: unknown
  error?: unknown
  list?: { error: unknown }
  reload: () => unknown
}

const props = withDefaults(
  defineProps<{ resource: LoadableResource; isEmpty?: (data: unknown) => boolean; rows?: number }>(),
  { isEmpty: (data: unknown) => Array.isArray(data) && data.length === 0, rows: 5 },
)

const error = computed(() => props.resource.error ?? props.resource.list?.error)
const state = computed(() => {
  const data = props.resource.data
  if (error.value) return 'error'
  if (data === null || data === undefined) return 'loading'
  return props.isEmpty(data) ? 'empty' : 'ready'
})
const message = computed(() => errorMessage(error.value) || __('Could not load this.'))
</script>

<template>
  <div :aria-busy="state === 'loading'">
    <slot v-if="state === 'loading'" name="loading">
      <ListSkeleton :rows="rows" />
    </slot>
    <ErrorState v-else-if="state === 'error'" :message="message" @retry="resource.reload()" />
    <slot v-else-if="state === 'empty'" name="empty" />
    <slot v-else />
  </div>
</template>
