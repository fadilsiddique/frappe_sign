<script setup lang="ts">
// Placeholder rows shaped like a list row: title, a line under it, and a badge at the end.
import { Skeleton } from 'frappe-ui'

withDefaults(defineProps<{ rows?: number }>(), { rows: 5 })
</script>

<template>
  <div class="divide-y divide-outline-gray-1" data-testid="list-skeleton">
    <div v-for="row in rows" :key="row" class="flex items-center gap-4 px-4 py-3">
      <div class="flex flex-1 flex-col gap-2">
        <Skeleton class="h-4 w-2/5 rounded" />
        <Skeleton class="h-3 w-1/4 rounded" />
      </div>
      <Skeleton class="h-5 w-16 rounded-full" />
    </div>
  </div>
</template>
