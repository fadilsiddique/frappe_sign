<script setup lang="ts">
import { computed } from 'vue'
import { __ } from '@/shared/translate'
import { editable, isCapture, isDone } from '../flow'
import type { GuestField } from '../types'

const props = defineProps<{ field: GuestField; active: boolean; preview?: string; signer?: string }>()
defineEmits<{ open: [field: GuestField] }>()

const label = computed(() => {
  const field = props.field
  if (field.type === 'Checkbox') return field.value === '1' ? '✓' : ''
  if (isCapture(field)) return isDone(field) ? '' : __(field.type)
  if (field.type === 'Date Signed') return __('Date')
  if (field.type === 'Full Name') return field.value || props.signer || __(field.type)
  return field.value || __(field.type)
})
</script>

<template>
  <button
    type="button"
    class="absolute flex items-center overflow-hidden rounded-sm border text-start text-xs leading-none transition"
    :class="[
      isDone(field) ? 'border-transparent bg-transparent' : 'border-dashed bg-[color:var(--sign-brand-soft)]',
      field.required && !isDone(field) ? 'border-[color:var(--sign-brand)]' : 'border-outline-gray-3',
      active ? 'ring-2 ring-[color:var(--sign-brand)] ring-offset-1' : '',
      editable(field) ? 'cursor-pointer' : 'cursor-default opacity-80',
    ]"
    :style="{
      left: `${field.rect.x * 100}%`,
      top: `${field.rect.y * 100}%`,
      width: `${field.rect.w * 100}%`,
      height: `${field.rect.h * 100}%`,
    }"
    :disabled="!editable(field)"
    :aria-label="`${__(field.type)}${field.required ? ' (' + __('required') + ')' : ''}`"
    :data-field="field.key"
    :data-done="isDone(field) ? '1' : '0'"
    @click="$emit('open', field)"
  >
    <img v-if="preview" :src="preview" alt="" class="size-full object-contain" />
    <span v-else class="truncate px-1 text-ink-gray-8">{{ label }}</span>
  </button>
</template>
