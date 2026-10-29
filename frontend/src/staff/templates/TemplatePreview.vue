<script setup lang="ts">
// Draws the Print Format with a real document and shows where each signature field lands.
import { Button } from 'frappe-ui'
import { computed, ref, shallowRef } from 'vue'
import { __ } from '@/shared/translate'
import { errorMessage, fetchPdf, STAFF_API, staff } from '../api'
import AnchorPreview from '../components/AnchorPreview.vue'
import DocumentPicker from '../send/DocumentPicker.vue'
import { checkWarnings } from '../send/warnings'
import type { Preview, Recipient } from '../send/types'
import type { PersonRow } from './types'

const props = defineProps<{ doctype: string; printFormat: string; people: PersonRow[] }>()
const name = ref('')
const loading = ref(false)
const error = ref('')
const preview = shallowRef<Preview | null>(null)
const pdf = shallowRef<ArrayBuffer | null>(null)

const roles = computed(() => props.people.map((person) => person.role_label))
const warnings = computed(() => {
  const asRecipients = props.people.map((person) => ({ ...person }) as unknown as Recipient)
  return preview.value ? checkWarnings(preview.value.anchors, asRecipients) : []
})

async function draw() {
  error.value = ''
  loading.value = true
  try {
    const rendered = await staff<Preview>('preview_source', {
      doctype: props.doctype,
      name: name.value,
      print_format: props.printFormat,
    })
    pdf.value = await fetchPdf(`/api/method/${STAFF_API}preview_pdf?key=${encodeURIComponent(rendered.key)}`)
    preview.value = rendered
  } catch (failure) {
    error.value = errorMessage(failure)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="flex flex-col gap-4" data-testid="template-preview">
    <div class="flex flex-wrap items-end gap-3">
      <div class="min-w-64 flex-1">
        <DocumentPicker
          v-model:name="name"
          :doctype="doctype"
          :doctypes="[{ doctype, templates: 1 }]"
          hide-doctype
        />
      </div>
      <Button
        variant="subtle"
        icon-left="lucide-eye"
        :label="__('Preview')"
        :loading="loading"
        :disabled="!name || !printFormat"
        data-testid="draw-preview"
        @click="draw"
      />
    </div>
    <p v-if="error" class="text-sm text-ink-red-4" role="alert">{{ error }}</p>
    <ul
      v-if="warnings.length"
      class="flex flex-col gap-1 text-sm text-ink-amber-3"
      data-testid="preview-warnings"
    >
      <li v-for="warning in warnings" :key="warning">{{ warning }}</li>
    </ul>
    <div v-if="preview" class="rounded-lg bg-surface-gray-2 p-3" data-testid="anchor-preview">
      <AnchorPreview :source="pdf" :pages="preview.metrics" :anchors="preview.anchors" :roles="roles" />
    </div>
    <p v-else class="text-sm text-ink-gray-6">
      {{ __('Pick a document to see the printed page with the signature boxes on it.') }}
    </p>
  </div>
</template>
