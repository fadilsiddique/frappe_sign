<script setup lang="ts">
// Step 1: where the document comes from. Three large choices; the picked one opens below.
import { createListResource } from 'frappe-ui'
import { computed, onMounted, ref } from 'vue'
import { __ } from '@/shared/translate'
import { staff } from '../api'
import EmptyState from '../components/EmptyState.vue'
import DocumentPicker from './DocumentPicker.vue'
import TemplateThumb from './TemplateThumb.vue'
import type { Choice, SourcePick, TemplateRow } from './types'

defineProps<{ busy: boolean }>()
const pick = defineModel<SourcePick>({ required: true })
const emit = defineEmits<{ upload: [file: File] }>()

const doctypes = ref<Array<{ doctype: string; templates: number }>>([])
onMounted(async () => {
  doctypes.value = await staff('sendable_doctypes')
  // Without an enabled DocType there is no document to pick: start from the templates.
  if (!doctypes.value.length && pick.value.choice === 'document') select('template')
})

const templates = createListResource({
  doctype: 'Sign Template',
  fields: ['name', 'title', 'published_version', 'source_type', 'reference_doctype', 'pdf_file'],
  filters: { published_version: ['is', 'set'], is_active: 1 },
  orderBy: 'title asc',
  pageLength: 200,
  auto: true,
})

const CHOICES: Array<{ key: Choice; icon: string; title: string; text: string }> = [
  {
    key: 'document',
    icon: 'lucide-file-check',
    title: 'From an ERPNext document',
    text: 'A Quotation, an order or a contract, printed with its Print Format.',
  },
  {
    key: 'template',
    icon: 'lucide-layout-template',
    title: 'From a template',
    text: 'A template you made, ready to send.',
  },
  {
    key: 'upload',
    icon: 'lucide-upload',
    title: 'Upload a PDF',
    text: 'Add the fields yourself on the pages.',
  },
]
const visible = computed(() => CHOICES.filter((choice) => choice.key !== 'document' || doctypes.value.length))

function select(key: Choice) {
  pick.value = { ...pick.value, choice: key }
}

// A template made for a document needs that document: carry on in the document picker.
function chooseTemplate(row: TemplateRow) {
  if (row.source_type === 'Print Format' && row.reference_doctype)
    pick.value = { choice: 'document', doctype: row.reference_doctype, name: '', template: row.name }
  else pick.value = { ...pick.value, choice: 'template', template: row.name }
}

function typeLabel(row: TemplateRow): string {
  return row.source_type === 'Print Format' ? __('Print Format') : __('Own PDF')
}

function chosen(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (file) emit('upload', file)
}

function dropped(event: DragEvent) {
  const file = event.dataTransfer?.files?.[0]
  if (file) emit('upload', file)
}
</script>

<template>
  <div class="flex flex-col gap-6">
    <div class="grid gap-3 md:grid-cols-3" role="radiogroup" :aria-label="__('Where is the document?')">
      <button
        v-for="choice in visible"
        :key="choice.key"
        type="button"
        role="radio"
        :aria-checked="pick.choice === choice.key"
        class="flex items-start gap-3 rounded-lg border p-4 text-start transition-colors focus-visible:outline-2 focus-visible:outline-outline-gray-4"
        :class="
          pick.choice === choice.key
            ? 'border-outline-gray-5 bg-surface-base ring-1 ring-outline-gray-5'
            : 'border-outline-gray-2 bg-surface-base hover:bg-surface-gray-1'
        "
        :data-testid="`choice-${choice.key}`"
        @click="select(choice.key)"
      >
        <span class="grid size-9 shrink-0 place-items-center rounded-md bg-surface-gray-2 text-ink-gray-7">
          <span :class="choice.icon" class="size-5" aria-hidden="true" />
        </span>
        <span class="flex flex-col gap-0.5">
          <span class="text-base font-medium text-ink-gray-9">{{ __(choice.title) }}</span>
          <span class="text-sm text-ink-gray-6">{{ __(choice.text) }}</span>
        </span>
      </button>
    </div>

    <DocumentPicker
      v-if="pick.choice === 'document' && doctypes.length"
      v-model:doctype="pick.doctype"
      v-model:name="pick.name"
      :doctypes="doctypes"
    />

    <div v-else-if="pick.choice === 'template'" data-testid="template-cards">
      <EmptyState
        v-if="templates.data && !templates.data.length"
        icon="lucide-layout-template"
        :title="__('No published templates')"
        :text="__('Make a template first, or upload a PDF.')"
      />
      <ul class="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <li v-for="row in (templates.data ?? []) as TemplateRow[]" :key="row.name">
          <button
            type="button"
            class="flex w-full flex-col gap-2 rounded-lg border p-2 text-start transition-colors focus-visible:outline-2 focus-visible:outline-outline-gray-4"
            :class="
              pick.template === row.name
                ? 'border-outline-gray-5 bg-surface-base ring-1 ring-outline-gray-5'
                : 'border-outline-gray-2 bg-surface-base hover:bg-surface-gray-1'
            "
            :disabled="busy"
            @click="chooseTemplate(row)"
          >
            <TemplateThumb :pdf-url="row.source_type === 'Print Format' ? null : row.pdf_file" />
            <span class="flex flex-col gap-0.5 px-1 pb-1">
              <span class="truncate text-base font-medium text-ink-gray-9">{{ row.title }}</span>
              <span class="truncate text-sm text-ink-gray-6">{{
                row.reference_doctype ? `${__(row.reference_doctype)} · ${typeLabel(row)}` : typeLabel(row)
              }}</span>
            </span>
          </button>
        </li>
      </ul>
    </div>

    <label
      v-else-if="pick.choice === 'upload'"
      class="flex max-w-xl cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed border-outline-gray-3 bg-surface-base p-10 text-center hover:bg-surface-gray-1 focus-within:outline-2 focus-within:outline-outline-gray-4"
      @dragover.prevent
      @drop.prevent="dropped"
    >
      <span class="lucide-file-up size-8 text-ink-gray-5" aria-hidden="true" />
      <span class="text-base font-medium text-ink-gray-9">{{ __('Drop a PDF here, or choose one') }}</span>
      <span class="text-sm text-ink-gray-6">{{ __('You place the fields on the next steps.') }}</span>
      <input
        type="file"
        accept="application/pdf"
        class="sr-only"
        data-testid="source-upload"
        @change="chosen"
      />
    </label>
  </div>
</template>
