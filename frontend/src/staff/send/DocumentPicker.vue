<script setup lang="ts">
// Pick a DocType from the enabled ones, then a document from a searchable list that shows the
// number, the party, the date and the total, so nobody types a number from memory.
import { Combobox, FormControl } from 'frappe-ui'
import { computed, ref, watch } from 'vue'
import { __ } from '@/shared/translate'
import { staff } from '../api'
import { shortDate } from '../format'
import type { DocumentChoice } from './types'

const props = defineProps<{
  doctypes: Array<{ doctype: string; templates: number }>
  // The DocType is already known (the template editor): show only the document search.
  hideDoctype?: boolean
}>()
const doctype = defineModel<string>('doctype', { required: true })
const name = defineModel<string>('name', { required: true })

const query = ref('')
const rows = ref<DocumentChoice[]>([])
const loading = ref(false)
const picked = ref<DocumentChoice | null>(null)
let request = 0
let timer: number | undefined

const noTemplates = computed(
  () => props.doctypes.find((row) => row.doctype === doctype.value)?.templates === 0,
)

async function search() {
  if (!doctype.value) return
  const id = ++request
  loading.value = true
  try {
    const found = await staff<DocumentChoice[]>('document_choices', {
      doctype: doctype.value,
      query: query.value,
    })
    if (id === request) rows.value = found
  } finally {
    if (id === request) loading.value = false
  }
}

watch(doctype, () => {
  name.value = ''
  picked.value = null
  query.value = ''
  void search()
})
watch(query, () => {
  window.clearTimeout(timer)
  timer = window.setTimeout(() => void search(), 250)
})
watch(
  () => props.doctypes,
  (list) => {
    if (!doctype.value && list.length) doctype.value = list[0].doctype
    else void search()
  },
  { immediate: true },
)

function amount(row: DocumentChoice): string {
  if (row.total === null) return ''
  const value = new Intl.NumberFormat(document.documentElement.lang || 'en', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(row.total)
  return row.currency ? `${row.currency} ${value}` : value
}

function line(row: DocumentChoice): string {
  return [row.party, row.date ? shortDate(row.date) : '', amount(row)].filter(Boolean).join(' · ')
}

// The picked document stays in the options so the field keeps its label when the results change.
const options = computed(() => {
  const list = rows.value.map((row) => ({ label: row.name, value: row.name, description: line(row) }))
  if (picked.value && !list.some((option) => option.value === picked.value?.name))
    list.unshift({ label: picked.value.name, value: picked.value.name, description: line(picked.value) })
  return list
})

function choose(value: string | number | null | undefined) {
  name.value = value ? String(value) : ''
  picked.value = rows.value.find((row) => row.name === name.value) ?? picked.value
}
</script>

<template>
  <div class="flex max-w-xl flex-col gap-4" data-testid="document-source">
    <FormControl
      v-if="!hideDoctype"
      v-model="doctype"
      type="select"
      :label="__('Type of document')"
      :options="doctypes.map((row) => ({ label: __(row.doctype), value: row.doctype }))"
      data-testid="doctype-select"
    />
    <Combobox
      v-model:query="query"
      :model-value="name || null"
      :options="options"
      :filterable="false"
      :loading="loading"
      :label="__('Document')"
      :placeholder="__('Search by number or name')"
      :empty-text="__('No documents found')"
      data-testid="document-combobox"
      @update:model-value="choose"
    >
    </Combobox>
    <p v-if="noTemplates && !hideDoctype" class="text-sm text-ink-amber-3">
      {{ __('There is no published template for {0} yet. Make one in Templates first.', [__(doctype)]) }}
    </p>
  </div>
</template>
