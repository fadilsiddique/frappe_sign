<script setup lang="ts">
// Step 2: one row per role. The role and what it does, then a name and an email with suggestions.
import { FormControl } from 'frappe-ui'
import { computed } from 'vue'
import { __ } from '@/shared/translate'
import { roleKindLabel, signingOrderLabel } from '../labels'
import PersonField from './PersonField.vue'
import type { Recipient } from './types'

const props = defineProps<{ recipients: Recipient[]; order: string | null; fromDocument: boolean }>()

const signers = computed(() => props.recipients.filter((row) => row.kind !== 'CC').length)
</script>

<template>
  <div class="flex max-w-3xl flex-col gap-4">
    <p v-if="order && signers > 1" class="text-sm text-ink-gray-6" data-testid="order-line">
      {{ signingOrderLabel(order) }}
    </p>
    <ul
      class="flex flex-col divide-y divide-outline-gray-1 rounded-lg border border-outline-gray-1 bg-surface-base"
    >
      <li
        v-for="(row, index) in recipients"
        :key="row.role_label"
        class="grid gap-3 p-4 sm:grid-cols-[10rem_1fr_1fr] sm:items-start"
        data-testid="person-row"
      >
        <span class="flex items-center gap-2 sm:pt-1.5">
          <span
            v-if="order === 'Sequential' && row.kind !== 'CC'"
            class="grid size-5 shrink-0 place-items-center rounded-full bg-surface-gray-3 text-xs font-semibold text-ink-gray-7"
            aria-hidden="true"
            >{{ row.routing_order || index + 1 }}</span
          >
          <span class="flex min-w-0 flex-col">
            <span class="truncate text-base font-medium text-ink-gray-9">{{ row.role_label }}</span>
            <span class="text-sm text-ink-gray-6">{{ roleKindLabel(row.kind) }}</span>
          </span>
        </span>
        <PersonField v-model:name="row.full_name" v-model:email="row.email" :placeholder="__('Full name')" />
        <span class="flex flex-col gap-1">
          <FormControl v-model="row.email" type="email" :placeholder="__('Email')" />
          <span
            v-if="fromDocument && row.resolved"
            class="flex items-center gap-1 text-sm text-ink-green-4"
            data-testid="found"
          >
            <span class="lucide-check size-3.5" aria-hidden="true" />{{ __('Found on the document') }}
          </span>
          <span v-else-if="fromDocument && row.resolved === false" class="text-sm text-ink-gray-6">
            {{ __('Not found on the document. Enter it here.') }}
          </span>
        </span>
      </li>
    </ul>
  </div>
</template>
