<script setup lang="ts">
// An empty list or page says what to do next (UX_PLAN "States").
defineProps<{ title: string; text?: string; icon?: string }>()
</script>

<template>
  <div class="flex flex-col items-center gap-2 px-4 py-14 text-center" data-testid="empty-state">
    <span
      v-if="icon"
      class="mb-1 grid size-12 place-items-center rounded-[16px] bg-[var(--sign-accent-50)] text-[var(--sign-accent-600)] ring-8 ring-[var(--sign-accent-50)]/60"
      aria-hidden="true"
    >
      <span :class="icon" class="size-6" />
    </span>
    <p class="text-lg font-semibold text-ink-gray-9">{{ title }}</p>
    <p v-if="text" class="max-w-md text-p-sm text-ink-gray-6">{{ text }}</p>
    <div v-if="$slots.action" class="mt-2 flex gap-2">
      <slot name="action" />
    </div>
  </div>
</template>
