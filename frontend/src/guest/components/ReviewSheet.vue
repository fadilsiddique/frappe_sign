<script setup lang="ts">
// Last look before finishing: what the signer filled in, in reading order.
import { BottomSheet } from 'frappe-ui'
import { computed } from 'vue'
import { __ } from '@/shared/translate'
import { reviewItems } from '../flow'
import type { GuestField } from '../types'
import BrandIcon from './BrandIcon.vue'

const props = defineProps<{
  open: boolean
  fields: GuestField[]
  approver: boolean
  busy: boolean
  error: string
}>()
const emit = defineEmits<{ close: []; confirm: [] }>()

const items = computed(() => reviewItems(props.fields))
const sheet = computed({
  get: () => props.open,
  set: (value) => value || emit('close'),
})
</script>

<template>
  <BottomSheet
    v-model:open="sheet"
    :title="approver ? __('Approve this document?') : __('Check before you sign')"
  >
    <div class="px-4 pb-4" data-testid="confirm">
      <ul v-if="items.length" class="divide-y divide-outline-gray-1" data-testid="review-list">
        <li v-for="item in items" :key="item.key" class="flex items-center gap-3 py-2.5">
          <span class="w-24 shrink-0 text-sm text-ink-gray-6">{{ __(item.type) }}</span>
          <span class="min-w-0 flex-1 truncate text-base text-ink-gray-9">
            <template v-if="item.text">{{ item.text }}</template>
            <template v-else-if="item.done">{{ __('Done') }}</template>
          </span>
          <BrandIcon name="check" class="text-ink-green-3" />
        </li>
      </ul>
      <p class="mt-3 text-sm text-ink-gray-6">
        {{ __('Your signature and the date are added to the document. You cannot change them afterwards.') }}
      </p>
      <p v-if="error" class="mt-2 text-sm text-ink-red-4" role="alert">{{ error }}</p>
      <div class="mt-4 flex gap-2">
        <button
          type="button"
          class="h-11 flex-1 rounded-lg border border-outline-gray-2 text-base text-ink-gray-8"
          @click="emit('close')"
        >
          {{ __('Back') }}
        </button>
        <button
          type="button"
          class="h-11 flex-[2] rounded-lg text-base font-medium text-white disabled:opacity-50"
          :style="{ background: 'var(--sign-brand)' }"
          :disabled="busy"
          data-testid="confirm-finish"
          @click="emit('confirm')"
        >
          {{ approver ? __('Approve') : __('Finish and sign') }}
        </button>
      </div>
    </div>
  </BottomSheet>
</template>
