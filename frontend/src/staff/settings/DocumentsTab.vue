<script setup lang="ts">
// The DocTypes people can send for signature, each with its default template and how often it was sent.
import { Button, FormControl, toast } from 'frappe-ui'
import { ref } from 'vue'
import { __ } from '@/shared/translate'
import EmptyState from '../components/EmptyState.vue'
import { errorMessage, staff } from '../api'
import DoctypePickerDialog from './DoctypePickerDialog.vue'
import { sendsLine } from './lines'
import type { SettingsData } from './types'

defineProps<{ data: SettingsData }>()
const emit = defineEmits<{ changed: [] }>()
const picking = ref(false)

async function run(method: string, args: Record<string, unknown>, done?: string) {
  try {
    await staff(method, args)
    if (done) toast.success(done)
    emit('changed')
  } catch (error) {
    toast.error(errorMessage(error))
  }
}

async function add(doctype: string) {
  picking.value = false
  await run('enable_doctype', { doctype }, __('{0} can now be sent for signature', [__(doctype)]))
}

async function remove(doctype: string) {
  const ok = window.confirm(
    __('Stop sending {0} for signature? Its signature fields and past requests stay.', [__(doctype)]),
  )
  if (ok) await run('disable_doctype', { doctype })
}
</script>

<template>
  <div class="flex flex-col gap-4" data-testid="tab-documents">
    <p class="max-w-2xl text-p-sm text-ink-gray-7">
      {{
        __('People can send these documents for signature from their form. Most teams start with Quotation.')
      }}
    </p>
    <EmptyState
      v-if="!data.documents.length"
      icon="lucide-file-check"
      :title="__('No document type yet')"
      :text="__('Add Quotation or another document to send it for signature.')"
    />
    <ul v-else class="divide-y divide-outline-gray-1 rounded-lg bg-surface-base" data-testid="document-rows">
      <li
        v-for="row in data.documents"
        :key="row.doctype"
        class="flex flex-col gap-2 p-3 sm:flex-row sm:items-center sm:gap-3"
        :data-testid="`document-${row.doctype}`"
      >
        <span class="min-w-0 flex-1 truncate text-base font-medium text-ink-gray-9">{{
          __(row.doctype)
        }}</span>
        <FormControl
          type="select"
          class="sm:w-60 sm:shrink-0"
          :model-value="row.default_template ?? ''"
          :disabled="!data.can_edit"
          :aria-label="__('Default template for {0}', [__(row.doctype)])"
          :options="[
            {
              label: row.templates.length ? __('No default template') : __('No published template'),
              value: '',
            },
            ...row.templates.map((t) => ({ label: t.title, value: t.name })),
          ]"
          data-testid="default-template"
          @update:model-value="
            run('set_default_template', { doctype: row.doctype, template: $event || null })
          "
        />
        <span class="text-sm text-ink-gray-6 sm:w-28 sm:shrink-0 sm:text-end">{{
          sendsLine(row.sends)
        }}</span>
        <span class="flex size-8 shrink-0 items-center justify-center">
          <Button
            v-if="data.can_edit"
            variant="ghost"
            icon="lucide-trash-2"
            :aria-label="__('Stop sending {0}', [__(row.doctype)])"
            data-testid="remove-document"
            @click="remove(row.doctype)"
          />
        </span>
      </li>
    </ul>
    <div v-if="data.can_edit">
      <Button
        variant="outline"
        icon-left="lucide-plus"
        :label="__('Add a document type')"
        data-testid="add-document"
        @click="picking = true"
      />
    </div>
    <DoctypePickerDialog v-model="picking" @pick="add" />
  </div>
</template>
