<script setup lang="ts">
// What happens to the document once everyone has signed. The choices build the stored JSON.
import { FormControl } from 'frappe-ui'
import { computed } from 'vue'
import { __ } from '@/shared/translate'
import { afterOptions, afterProblem, type AfterChoice, type AfterState } from './afterSigning'
import type { SettableField } from './types'

const props = defineProps<{ doctype: string; fields: SettableField[] }>()
const after = defineModel<AfterState>({ required: true })

const options = computed(() => afterOptions(props.doctype, after.value.choice))
const problem = computed(() => afterProblem(after.value))
const HINTS: Partial<Record<AfterChoice, string>> = {
  sales_order:
    'The Sales Order is saved as a draft, made from the Quotation, as the person who sent the request.',
  submit: 'The document is submitted as the person who sent the request.',
}

function change(patch: Partial<AfterState>) {
  after.value = { ...after.value, ...patch }
}
</script>

<template>
  <div class="flex flex-col gap-3" data-testid="after-signing">
    <FormControl
      type="select"
      :model-value="after.choice"
      :label="__('After everyone signs')"
      :options="options"
      data-testid="after-choice"
      @update:model-value="change({ choice: $event as AfterChoice })"
    />
    <p v-if="HINTS[after.choice]" class="text-sm text-ink-gray-6">{{ __(HINTS[after.choice] as string) }}</p>
    <template v-if="after.choice === 'set_field'">
      <FormControl
        type="select"
        :model-value="after.fieldname"
        :label="__('Field')"
        :options="fields.map((field) => ({ label: __(field.label), value: field.fieldname }))"
        @update:model-value="change({ fieldname: String($event ?? '') })"
      />
      <FormControl
        :model-value="after.value"
        :label="__('Value')"
        :description="__('Use today, or today+7 for a day in the future.')"
        @change="change({ value: ($event.target as HTMLInputElement).value })"
      />
    </template>
    <FormControl
      v-if="after.choice === 'workflow'"
      :model-value="after.workflowAction"
      :label="__('Workflow action')"
      :placeholder="__('For example Approve')"
      @change="change({ workflowAction: ($event.target as HTMLInputElement).value })"
    />
    <p v-if="problem" class="text-sm text-ink-amber-3" role="alert">{{ problem }}</p>
  </div>
</template>
