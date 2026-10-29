<script setup lang="ts">
// The empty canvas: drop a PDF here, or click to choose one.
import { ref } from 'vue'
import { __ } from '@/shared/translate'

const emit = defineEmits<{ file: [file: File] }>()
const over = ref(false)

function chosen(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (file) emit('file', file)
}

function dropped(event: DragEvent) {
  over.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file) emit('file', file)
}
</script>

<template>
  <label
    class="mx-auto mt-10 flex max-w-xl cursor-pointer flex-col items-center gap-3 rounded-lg border-2 border-dashed bg-surface-base px-6 py-16 text-center transition-colors focus-within:outline-2 focus-within:outline-outline-gray-4"
    :class="
      over ? 'border-outline-gray-5 bg-surface-gray-1' : 'border-outline-gray-3 hover:bg-surface-gray-1'
    "
    data-testid="pdf-drop"
    @dragover.prevent="over = true"
    @dragleave="over = false"
    @drop.prevent="dropped"
  >
    <span class="grid size-11 place-items-center rounded-full bg-surface-gray-2 text-ink-gray-7">
      <span class="lucide-file-up size-6" aria-hidden="true" />
    </span>
    <span class="text-lg font-medium text-ink-gray-9">{{ __('Drop your PDF here') }}</span>
    <span class="text-base text-ink-gray-6">{{
      __('or click to choose a file. Then place the signature boxes on its pages.')
    }}</span>
    <input type="file" accept="application/pdf" class="sr-only" data-testid="upload-pdf" @change="chosen" />
  </label>
</template>
