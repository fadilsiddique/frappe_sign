<script setup lang="ts">
// Template designer (DESIGN 7.4): palette, pages, properties; save and publish a version.
import { Button, FormControl, toast } from 'frappe-ui'
import { onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import { __ } from '@/shared/translate'
import type { PageMetric } from '@/shared/coords'
import { errorMessage, fetchPdf, fileToBase64, staff } from '../api'
import DesignerCanvas from '../designer/DesignerCanvas.vue'
import FieldProperties from '../designer/FieldProperties.vue'
import RolesPanel from '../designer/RolesPanel.vue'
import { FIELD_TYPES, useDesigner, type FieldType } from '../designer/store'
import { otpModeLabel, signingOrderLabel } from '../labels'
import { call } from 'frappe-ui'

const props = defineProps<{ id: string }>()
const router = useRouter()
const store = useDesigner()
const pdf = shallowRef<ArrayBuffer | null>(null)
const placing = ref<FieldType | null>(null)
const saving = ref(false)
const loadError = ref('')
const publishedVersion = ref<string | null>(null)

interface TemplateDoc {
  name: string
  title: string
  signing_order: string
  otp_mode: string
  pdf_file: string | null
  page_metrics: string | null
  published_version: string | null
  roles: never[]
  fields: never[]
}

async function load() {
  try {
    const doc = await call<TemplateDoc>('frappe.client.get', { doctype: 'Sign Template', name: props.id })
    store.load(doc)
    publishedVersion.value = doc.published_version
    if (!store.roles.length) store.addRole('Signer')
    store.dirty = false
    store.past = []
    pdf.value = doc.pdf_file ? await fetchPdf(doc.pdf_file) : null
  } catch (error) {
    loadError.value = errorMessage(error)
  }
}

async function upload(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  try {
    await save(false)
    const result = await staff<{ metrics: PageMetric[] }>('upload_pdf', {
      template: props.id,
      file_name: file.name,
      content: await fileToBase64(file),
    })
    store.setPages(result.metrics)
    pdf.value = await file.arrayBuffer()
    toast.success(__('PDF uploaded'))
  } catch (error) {
    toast.error(errorMessage(error))
  }
}

async function save(notify = true) {
  saving.value = true
  try {
    await staff('save_template', { template: props.id, data: store.payload() })
    store.dirty = false
    if (notify) toast.success(__('Saved'))
  } catch (error) {
    toast.error(errorMessage(error))
    throw error
  } finally {
    saving.value = false
  }
}

async function publish() {
  try {
    await save(false)
    const version = await staff<{ name: string; version_no: number }>('publish_template', {
      template: props.id,
    })
    publishedVersion.value = version.name
    toast.success(__('Published version {0}', [version.version_no]))
  } catch (error) {
    toast.error(errorMessage(error))
  }
}

function beforeUnload(event: BeforeUnloadEvent) {
  if (store.dirty) event.preventDefault()
}

onBeforeRouteLeave(() => !store.dirty || window.confirm(__('Leave without saving?')))
onMounted(() => {
  void load()
  window.addEventListener('beforeunload', beforeUnload)
})
onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))
</script>

<template>
  <div class="flex h-full flex-col" data-testid="designer">
    <header class="flex items-center gap-3 border-b border-outline-gray-1 px-4 py-2">
      <Button variant="ghost" :label="__('Templates')" @click="router.push('/templates')" />
      <FormControl
        v-model="store.title"
        class="w-72"
        :aria-label="__('Title')"
        @change="store.dirty = true"
      />
      <span class="text-sm text-ink-gray-5">{{
        publishedVersion ? __('Published: {0}', [publishedVersion]) : __('Not published')
      }}</span>
      <div class="ms-auto flex items-center gap-2">
        <Button :disabled="!store.canUndo" :label="__('Undo')" @click="store.undo()" />
        <Button :disabled="!store.canRedo" :label="__('Redo')" @click="store.redo()" />
        <label
          class="cursor-pointer rounded bg-surface-gray-2 px-3 py-1.5 text-sm text-ink-gray-8 hover:bg-surface-gray-3"
        >
          {{ pdf ? __('Replace PDF') : __('Upload PDF') }}
          <input
            type="file"
            accept="application/pdf"
            class="hidden"
            data-testid="upload-pdf"
            @change="upload"
          />
        </label>
        <Button :loading="saving" :label="__('Save')" @click="save()" />
        <Button variant="solid" :label="__('Publish')" :disabled="!pdf" @click="publish" />
      </div>
    </header>
    <p v-if="loadError" class="p-4 text-ink-red-4">{{ loadError }}</p>
    <div v-else class="flex min-h-0 flex-1">
      <aside
        class="w-48 shrink-0 space-y-1 overflow-y-auto border-e border-outline-gray-1 p-3"
        data-testid="palette"
      >
        <h3 class="mb-2 text-sm font-semibold text-ink-gray-8">{{ __('Add field') }}</h3>
        <p class="mb-2 text-xs text-ink-gray-5">
          {{ __('For {0}. Pick a type, then click the page.', [store.activeRole || '-']) }}
        </p>
        <button
          v-for="type in FIELD_TYPES"
          :key="type"
          type="button"
          class="block w-full rounded px-2 py-1.5 text-start text-sm"
          :class="placing === type ? 'bg-surface-gray-4 font-medium' : 'hover:bg-surface-gray-2'"
          :data-testid="`palette-${type}`"
          @click="placing = placing === type ? null : type"
        >
          {{ __(type) }}
        </button>
      </aside>
      <main class="min-w-0 flex-1 overflow-y-auto bg-surface-gray-2 p-4">
        <DesignerCanvas v-if="pdf" :source="pdf" :placing="placing" @placed="placing = null" />
        <div v-else class="mx-auto mt-20 max-w-sm text-center text-ink-gray-6">
          {{ __('Upload the PDF to place fields on it.') }}
        </div>
      </main>
      <aside class="w-80 shrink-0 space-y-6 overflow-y-auto border-s border-outline-gray-1 p-3">
        <div class="space-y-2">
          <h3 class="text-sm font-semibold text-ink-gray-8">{{ __('Template') }}</h3>
          <FormControl
            v-model="store.signingOrder"
            type="select"
            :label="__('Signing order')"
            :options="['Sequential', 'Parallel'].map((value) => ({ label: signingOrderLabel(value), value }))"
          />
          <FormControl
            v-model="store.otpMode"
            type="select"
            :label="__('Verify with an emailed code')"
            :options="['Off', 'Email'].map((value) => ({ label: otpModeLabel(value), value }))"
          />
        </div>
        <FieldProperties />
        <RolesPanel />
      </aside>
    </div>
  </div>
</template>
