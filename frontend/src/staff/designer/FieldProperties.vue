<script setup lang="ts">
import { Button, FormControl } from 'frappe-ui'
import { computed } from 'vue'
import { __ } from '@/shared/translate'
import { FIELD_TYPES, useDesigner, type DesignerField } from './store'

const store = useDesigner()
const field = computed(() => (store.selection.length === 1 ? store.selection[0] : null))

function set<K extends keyof DesignerField>(key: K, value: DesignerField[K]) {
  if (field.value) store.updateField(field.value.field_key, { [key]: value } as Partial<DesignerField>)
}
</script>

<template>
  <div v-if="field" class="space-y-3" data-testid="field-properties">
    <h3 class="text-sm font-semibold text-ink-gray-8">{{ __('Field') }}</h3>
    <FormControl
      type="select"
      :label="__('Type')"
      :model-value="field.field_type"
      :options="FIELD_TYPES.map((t) => ({ label: __(t), value: t }))"
      @update:model-value="set('field_type', $event)"
    />
    <FormControl
      type="select"
      :label="__('Role')"
      :model-value="field.role_label"
      :options="store.signerRoles.map((r) => ({ label: r.role_label, value: r.role_label }))"
      @update:model-value="set('role_label', $event)"
    />
    <FormControl :label="__('Key')" :model-value="field.field_key" disabled />
    <FormControl
      type="checkbox"
      :label="__('Required')"
      :model-value="Boolean(field.required)"
      @update:model-value="set('required', $event ? 1 : 0)"
    />
    <FormControl
      type="checkbox"
      :label="__('Read only (prefilled)')"
      :model-value="Boolean(field.read_only)"
      @update:model-value="set('read_only', $event ? 1 : 0)"
    />
    <FormControl
      :label="__('Prefill from field')"
      :model-value="field.prefill_path ?? ''"
      :placeholder="__('customer_name or {{ doc.grand_total }}')"
      @change="set('prefill_path', ($event.target as HTMLInputElement).value || null)"
    />
    <FormControl
      v-if="field.field_type === 'Dropdown'"
      type="textarea"
      :label="__('Options, one per line')"
      :model-value="field.options ?? ''"
      @change="set('options', ($event.target as HTMLTextAreaElement).value)"
    />
    <FormControl
      v-if="['Text', 'Number'].includes(field.field_type)"
      :label="__('Pattern (regex)')"
      :model-value="field.validation_regex ?? ''"
      @change="set('validation_regex', ($event.target as HTMLInputElement).value || null)"
    />
    <FormControl
      type="number"
      :label="__('Font size')"
      :model-value="field.font_size"
      @change="set('font_size', Number(($event.target as HTMLInputElement).value) || 11)"
    />
    <p class="text-xs text-ink-gray-5">
      {{
        __('Page {0}: x {1}, y {2}, w {3}, h {4}', [
          field.page,
          field.x.toFixed(3),
          field.y.toFixed(3),
          field.w.toFixed(3),
          field.h.toFixed(3),
        ])
      }}
    </p>
    <div class="flex gap-2">
      <Button
        size="sm"
        :label="__('Copy to all pages')"
        @click="store.duplicateToAllPages(field.field_key)"
      />
      <Button size="sm" theme="red" :label="__('Delete')" @click="store.removeSelected()" />
    </div>
  </div>
  <p v-else-if="store.selection.length > 1" class="text-sm text-ink-gray-6">
    {{
      __('{0} fields selected. Use the arrow keys to move them, Delete to remove them.', [
        store.selection.length,
      ])
    }}
  </p>
  <p v-else class="text-sm text-ink-gray-5">{{ __('Select a field to edit it.') }}</p>
</template>
