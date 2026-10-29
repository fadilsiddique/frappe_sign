<script setup lang="ts">
// Field types by group, each with an icon. Pick a type, then click the page to place it.
import { __ } from '@/shared/translate'
import type { FieldType } from './store'

defineProps<{ placing: FieldType | null; role: string }>()
const emit = defineEmits<{ pick: [type: FieldType] }>()

// Full class names, so Tailwind finds each icon.
const GROUPS: Array<{ title: string; types: Array<{ type: FieldType; icon: string }> }> = [
  {
    title: 'Signature',
    types: [
      { type: 'Signature', icon: 'lucide-signature' },
      { type: 'Initials', icon: 'lucide-pen-line' },
      { type: 'Company Stamp', icon: 'lucide-stamp' },
    ],
  },
  {
    title: 'Details',
    types: [
      { type: 'Full Name', icon: 'lucide-user' },
      { type: 'Email', icon: 'lucide-mail' },
      { type: 'Date Signed', icon: 'lucide-calendar' },
      { type: 'Text', icon: 'lucide-type' },
      { type: 'Number', icon: 'lucide-hash' },
      { type: 'Checkbox', icon: 'lucide-square-check' },
      { type: 'Dropdown', icon: 'lucide-list' },
      { type: 'Attachment', icon: 'lucide-paperclip' },
    ],
  },
]
</script>

<template>
  <nav class="flex flex-col gap-4" :aria-label="__('Add field')" data-testid="palette">
    <p class="text-sm text-ink-gray-6">
      {{ __('Adding for {0}. Pick a type, then click the page.', [role || '-']) }}
    </p>
    <section v-for="group in GROUPS" :key="group.title" class="flex flex-col gap-1">
      <h3 class="px-2 text-sm font-medium text-ink-gray-6">{{ __(group.title) }}</h3>
      <button
        v-for="item in group.types"
        :key="item.type"
        type="button"
        class="flex h-8 items-center gap-2 rounded px-2 text-start text-base focus-visible:outline-2 focus-visible:outline-outline-gray-4"
        :class="
          placing === item.type
            ? 'bg-surface-gray-4 font-medium text-ink-gray-9'
            : 'text-ink-gray-8 hover:bg-surface-gray-2'
        "
        :aria-pressed="placing === item.type"
        :data-testid="`palette-${item.type}`"
        @click="emit('pick', item.type)"
      >
        <span :class="item.icon" class="size-4 shrink-0 text-ink-gray-6" aria-hidden="true" />
        {{ __(item.type) }}
      </button>
    </section>
  </nav>
</template>
