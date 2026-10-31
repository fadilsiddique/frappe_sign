<script setup lang="ts">
// "New template" asks the kind first (UX_PLAN "Templates").
import { Dialog } from 'frappe-ui'
import { __ } from '@/shared/translate'

const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ pick: [kind: 'print-format' | 'pdf'] }>()

const KINDS = [
  {
    key: 'print-format' as const,
    icon: 'lucide-file-check',
    title: 'For an ERPNext document (Print Format)',
    text: 'A Quotation or an order, printed with its Print Format. The signature boxes come from the format.',
  },
  {
    key: 'pdf' as const,
    icon: 'lucide-file-up',
    title: 'Your own PDF',
    text: 'Upload a PDF and place the signature boxes on its pages.',
  },
]
</script>

<template>
  <Dialog v-model="open" :title="__('New template')" size="xl">
    <div class="grid gap-3 sm:grid-cols-2" data-testid="template-kinds">
      <button
        v-for="kind in KINDS"
        :key="kind.key"
        type="button"
        class="flex flex-col items-start gap-3 rounded-[12px] border border-outline-gray-2 p-5 text-start transition hover:-translate-y-0.5 hover:border-[var(--sign-accent-500)] hover:bg-[var(--sign-accent-50)]/50 hover:shadow-md focus-visible:focus-ring"
        :data-testid="`kind-${kind.key}`"
        @click="emit('pick', kind.key)"
      >
        <span class="grid size-10 place-items-center rounded-[12px] bg-[var(--sign-accent-50)] text-[var(--sign-accent-600)]">
          <span :class="kind.icon" class="size-5" aria-hidden="true" />
        </span>
        <span class="text-base font-medium text-ink-gray-9">{{ __(kind.title) }}</span>
        <span class="text-sm text-ink-gray-6">{{ __(kind.text) }}</span>
      </button>
    </div>
  </Dialog>
</template>
