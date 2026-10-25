<script setup lang="ts">
import { BottomSheet, Button } from 'frappe-ui'
import { computed, ref, watch } from 'vue'
import { __ } from '@/shared/translate'
import type { GuestField } from '../types'

const props = defineProps<{ field: GuestField | null; busy: boolean; error: string }>()
const emit = defineEmits<{ close: []; save: [value: string] }>()

const value = ref('')
const open = computed({
  get: () => Boolean(props.field),
  set: (next) => next || emit('close'),
})
const inputType = computed(() => {
  if (props.field?.type === 'Email') return 'email'
  if (props.field?.type === 'Number') return 'text'
  return 'text'
})

watch(
  () => props.field,
  (field) => {
    value.value = field?.value ?? ''
  },
)
</script>

<template>
  <BottomSheet v-model:open="open" :title="field ? __(field.type) : ''">
    <form
      v-if="field"
      class="space-y-4 px-4 pb-4"
      data-testid="value-sheet"
      @submit.prevent="emit('save', value)"
    >
      <select
        v-if="field.type === 'Dropdown'"
        v-model="value"
        class="form-select w-full"
        :aria-label="__(field.type)"
      >
        <option value="" disabled>{{ __('Choose') }}</option>
        <option v-for="option in field.options" :key="option" :value="option">{{ option }}</option>
      </select>
      <input
        v-else
        v-model="value"
        class="form-input w-full"
        :type="inputType"
        :inputmode="field.type === 'Number' ? 'decimal' : undefined"
        :aria-label="__(field.type)"
        maxlength="500"
        data-testid="value-input"
        autofocus
      />
      <p v-if="error" class="text-sm text-ink-red-4" role="alert">{{ error }}</p>
      <Button class="w-full" variant="solid" size="md" type="submit" :loading="busy" :label="__('Save')" />
    </form>
  </BottomSheet>
</template>
