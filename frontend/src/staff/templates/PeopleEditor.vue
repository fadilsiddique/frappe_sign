<script setup lang="ts">
// Who signs, one row per person, in signing order. The words are the user's (UX_PLAN "Words").
import { Button, FormControl } from 'frappe-ui'
import { __ } from '@/shared/translate'
import { roleKindLabel, signerSourceLabel } from '../labels'
import type { PersonRow } from './types'

const people = defineModel<PersonRow[]>({ required: true })
const KINDS = ['Signer', 'Approver', 'CC']
const SOURCES = ['Party Contact', 'Doc Field', 'Fixed User', 'Ask at Send']

function add() {
  const next = people.value.length + 1
  people.value = [
    ...people.value,
    {
      role_label: __('Signer {0}', [next]),
      kind: 'Signer',
      signer_source: 'Ask at Send',
      source_field: '',
      fixed_user: '',
    },
  ]
}

function update(index: number, change: Partial<PersonRow>) {
  people.value = people.value.map((row, i) => (i === index ? { ...row, ...change } : row))
}

function remove(index: number) {
  people.value = people.value.filter((_, i) => i !== index)
}
</script>

<template>
  <div class="flex flex-col gap-3" data-testid="people-editor">
    <ol class="flex flex-col gap-3">
      <li
        v-for="(person, index) in people"
        :key="index"
        class="flex gap-3 rounded-lg border border-outline-gray-2 p-3"
        data-testid="person-row"
      >
        <span
          class="mt-1 grid size-6 shrink-0 place-items-center rounded-full bg-surface-gray-3 text-xs font-medium text-ink-gray-8"
          aria-hidden="true"
          >{{ index + 1 }}</span
        >
        <div class="flex min-w-0 flex-1 flex-col gap-3">
          <div class="grid gap-3 sm:grid-cols-2">
            <FormControl
              :model-value="person.role_label"
              :label="__('Name of the role')"
              data-testid="person-role"
              @change="update(index, { role_label: ($event.target as HTMLInputElement).value.trim() })"
            />
            <FormControl
              type="select"
              :model-value="person.kind"
              :label="__('What they do')"
              :options="KINDS.map((kind) => ({ label: roleKindLabel(kind), value: kind }))"
              @update:model-value="update(index, { kind: String($event) })"
            />
          </div>
          <FormControl
            type="select"
            :model-value="person.signer_source"
            :label="__('Who is it?')"
            :options="SOURCES.map((source) => ({ label: signerSourceLabel(source), value: source }))"
            data-testid="person-source"
            @update:model-value="update(index, { signer_source: String($event) })"
          />
          <FormControl
            v-if="person.signer_source === 'Doc Field'"
            :model-value="person.source_field"
            :label="__('Field of the document')"
            :placeholder="__('For example contact_email')"
            @change="update(index, { source_field: ($event.target as HTMLInputElement).value.trim() })"
          />
          <FormControl
            v-if="person.signer_source === 'Fixed User'"
            :model-value="person.fixed_user"
            :label="__('Their user (email)')"
            @change="update(index, { fixed_user: ($event.target as HTMLInputElement).value.trim() })"
          />
        </div>
        <Button
          variant="ghost"
          icon="lucide-trash-2"
          :aria-label="__('Remove {0}', [person.role_label])"
          :disabled="people.length < 2"
          @click="remove(index)"
        />
      </li>
    </ol>
    <div>
      <Button variant="subtle" icon-left="lucide-plus" :label="__('Add a person')" @click="add" />
    </div>
    <p class="text-sm text-ink-gray-6">
      {{
        __(
          'The name of the role must match the name used in sign_field() in the Print Format. Spaces count as underscores.',
        )
      }}
    </p>
  </div>
</template>
