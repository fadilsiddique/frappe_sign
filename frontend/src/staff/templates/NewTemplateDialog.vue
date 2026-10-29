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
        class="flex flex-col items-start gap-3 rounded-lg border border-outline-gray-2 p-4 text-start transition-colors hover:bg-surface-gray-1 focus-visible:outline-2 focus-visible:outline-outline-gray-4"
        :data-testid="`kind-${kind.key}`"
        @click="emit('pick', kind.key)"
      >
        <span class="grid size-9 place-items-center rounded-md bg-surface-gray-2 text-ink-gray-7">
          <span :class="kind.icon" class="size-5" aria-hidden="true" />
        </span>
        <span class="text-base font-medium text-ink-gray-9">{{ __(kind.title) }}</span>
        <span class="text-sm text-ink-gray-6">{{ __(kind.text) }}</span>
      </button>
    </div>
  </Dialog>
</template>
