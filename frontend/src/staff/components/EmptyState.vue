<script setup lang="ts">
// An empty list or page says what to do next (UX_PLAN "States").
defineProps<{ title: string; text?: string; icon?: string }>()
</script>

<template>
  <div class="flex flex-col items-center gap-2 px-4 py-10 text-center" data-testid="empty-state">
    <span
      v-if="icon"
      class="mb-1 grid size-10 place-items-center rounded-full bg-surface-gray-2 text-ink-gray-6"
      aria-hidden="true"
    >
      <span :class="icon" class="size-5" />
    </span>
    <p class="text-base font-medium text-ink-gray-9">{{ title }}</p>
    <p v-if="text" class="max-w-md text-p-sm text-ink-gray-6">{{ text }}</p>
    <div v-if="$slots.action" class="mt-2 flex gap-2">
      <slot name="action" />
    </div>
  </div>
</template>
