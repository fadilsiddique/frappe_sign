<script setup lang="ts">
import { Button } from 'frappe-ui'
import { __ } from '@/shared/translate'

defineProps<{ message: string }>()
defineEmits<{ retry: [] }>()
</script>

<template>
  <div role="alert" class="flex flex-col items-center gap-3 px-4 py-10 text-center" data-testid="error-state">
    <span
      class="grid size-10 place-items-center rounded-full bg-surface-red-1 text-ink-red-4"
      aria-hidden="true"
    >
      <span class="lucide-circle-alert size-5" />
    </span>
    <p class="max-w-md text-base text-ink-gray-8">{{ message }}</p>
    <Button :label="__('Try again')" icon-left="lucide-rotate-cw" @click="$emit('retry')" />
  </div>
</template>
