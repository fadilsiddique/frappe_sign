<script setup lang="ts">
// The steps of the wizard: done steps show a tick and can be clicked to go back.
import { computed } from 'vue'
import { __ } from '@/shared/translate'
import type { Step } from './types'

const props = defineProps<{ steps: Step[]; current: Step }>()
const emit = defineEmits<{ go: [step: Step] }>()

const LABELS: Record<Step, string> = {
  source: 'Document',
  recipients: 'People',
  fields: 'Fields',
  preview: 'Check',
  review: 'Send',
}
const index = computed(() => props.steps.indexOf(props.current))
</script>

<template>
  <ol class="flex items-center gap-2 text-sm" :aria-label="__('Steps')" data-testid="steps">
    <li v-for="(name, position) in steps" :key="name" class="flex items-center gap-2">
      <button
        type="button"
        class="flex items-center gap-2 rounded py-1 pe-2 focus-visible:outline-2 focus-visible:outline-outline-gray-4"
        :disabled="position >= index"
        :aria-current="name === current ? 'step' : undefined"
        @click="emit('go', name)"
      >
        <span
          class="grid size-6 place-items-center rounded-full text-xs font-semibold"
          :class="
            position < index
              ? 'bg-surface-gray-7 text-ink-white'
              : name === current
                ? 'bg-surface-gray-7 text-ink-white'
                : 'bg-surface-gray-3 text-ink-gray-6'
          "
        >
          <span v-if="position < index" class="lucide-check size-3.5" aria-hidden="true" />
          <template v-else>{{ position + 1 }}</template>
        </span>
        <span :class="name === current ? 'font-medium text-ink-gray-9' : 'text-ink-gray-6'">{{
          __(LABELS[name])
        }}</span>
      </button>
      <span
        v-if="position < steps.length - 1"
        class="h-px w-6 bg-outline-gray-2 sm:w-10"
        aria-hidden="true"
      />
    </li>
  </ol>
</template>
