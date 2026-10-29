<script setup lang="ts">
// Template designer (DESIGN 7.4): palette, pages, properties; save and publish a version.
import { Button, FormControl, toast } from 'frappe-ui'
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import { __ } from '@/shared/translate'
import type { PageMetric } from '@/shared/coords'
import { errorMessage, fetchPdf, fileToBase64, staff } from '../api'
import DesignerCanvas from '../designer/DesignerCanvas.vue'
import FieldProperties from '../designer/FieldProperties.vue'
import Palette from '../designer/Palette.vue'
import PdfDropZone from '../designer/PdfDropZone.vue'
import RolesPanel from '../designer/RolesPanel.vue'
import { useDesigner, type FieldType } from '../designer/store'
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
const saveState = computed(() => (saving.value ? __('Saving') : store.dirty ? __('Unsaved') : __('Saved')))

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

async function upload(file: File) {
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

function replace(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (file) void upload(file)
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
    <header
      class="flex flex-wrap items-center gap-2 border-b border-outline-gray-1 bg-surface-base px-4 py-2"
    >
      <Button
        variant="ghost"
        icon="lucide-arrow-left"
        :aria-label="__('Templates')"
        @click="router.push('/templates')"
      />
      <FormControl
        v-model="store.title"
        class="w-64 sm:w-72"
        :aria-label="__('Title')"
        @change="store.dirty = true"
      />
      <span class="text-sm text-ink-gray-6" data-testid="save-state" role="status">
        {{ saveState }} ·
        {{ publishedVersion ? __('Published: {0}', [publishedVersion]) : __('Not published') }}
      </span>
      <div class="ms-auto flex items-center gap-2">
        <Button
          variant="ghost"
          icon="lucide-undo-2"
          :aria-label="__('Undo')"
          :disabled="!store.canUndo"
          data-testid="undo"
          @click="store.undo()"
        />
        <Button
          variant="ghost"
          icon="lucide-redo-2"
          :aria-label="__('Redo')"
          :disabled="!store.canRedo"
          data-testid="redo"
          @click="store.redo()"
        />
        <label
          v-if="pdf"
          class="cursor-pointer rounded bg-surface-gray-2 px-3 py-1.5 text-base text-ink-gray-8 hover:bg-surface-gray-3"
        >
          {{ __('Replace PDF') }}
          <input
            type="file"
            accept="application/pdf"
            class="hidden"
            data-testid="replace-pdf"
            @change="replace"
          />
        </label>
        <Button variant="subtle" :loading="saving" :label="__('Save')" @click="save()" />
        <Button variant="solid" :label="__('Publish')" :disabled="!pdf" @click="publish" />
      </div>
    </header>
    <p v-if="loadError" class="p-4 text-ink-red-4">{{ loadError }}</p>
    <div v-else class="flex min-h-0 flex-1">
      <aside class="w-52 shrink-0 overflow-y-auto border-e border-outline-gray-1 bg-surface-base p-3">
        <Palette
          :placing="placing"
          :role="store.activeRole || ''"
          @pick="placing = placing === $event ? null : $event"
        />
      </aside>
      <main class="min-w-0 flex-1 overflow-y-auto bg-surface-gray-2 p-4">
        <DesignerCanvas v-if="pdf" :source="pdf" :placing="placing" @placed="placing = null" />
        <PdfDropZone v-else @file="upload" />
      </main>
      <aside
        class="flex w-80 shrink-0 flex-col gap-6 overflow-y-auto border-s border-outline-gray-1 bg-surface-base p-3"
      >
        <RolesPanel />
        <FieldProperties />
        <div class="flex flex-col gap-3">
          <h3 class="text-base font-semibold text-ink-gray-9">{{ __('Signing') }}</h3>
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
      </aside>
    </div>
  </div>
</template>
