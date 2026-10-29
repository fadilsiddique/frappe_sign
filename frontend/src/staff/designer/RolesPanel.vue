<script setup lang="ts">
// The people of the template, one compact row each: colour dot, name, what they do. A row opens
// to show the details. Clicking a signer also makes them the person new fields are added for.
import { Button, FormControl } from 'frappe-ui'
import { ref } from 'vue'
import { __ } from '@/shared/translate'
import { roleKindLabel, signerSourceLabel } from '../labels'
import { useDesigner } from './store'

const store = useDesigner()
const KINDS = ['Signer', 'Approver', 'CC']
const SOURCES = ['Ask at Send', 'Fixed User', 'Doc Field', 'Party Contact', 'Employee']
const open = ref<string | null>(null)

function toggle(label: string, kind: string) {
  open.value = open.value === label ? null : label
  if (kind === 'Signer') store.activeRole = label
}

function rename(label: string, event: Event) {
  const name = (event.target as HTMLInputElement).value.trim() || label
  store.updateRole(label, { role_label: name })
  if (open.value === label) open.value = name
}
</script>

<template>
  <div class="flex flex-col gap-2" data-testid="roles">
    <div class="flex items-center justify-between">
      <h3 class="text-base font-semibold text-ink-gray-9">{{ __('People') }}</h3>
      <Button
        size="sm"
        variant="ghost"
        icon-left="lucide-plus"
        :label="__('Add person')"
        @click="store.addRole('Signer')"
      />
    </div>
    <div
      v-for="role in store.roles"
      :key="role.role_label"
      class="rounded-md border"
      :class="store.activeRole === role.role_label ? 'border-outline-gray-4' : 'border-outline-gray-1'"
    >
      <button
        type="button"
        class="flex h-10 w-full items-center gap-2 px-2 text-start focus-visible:outline-2 focus-visible:outline-outline-gray-4"
        :aria-expanded="open === role.role_label"
        @click="toggle(role.role_label, role.kind)"
      >
        <span
          class="size-3 shrink-0 rounded-full"
          :style="{ backgroundColor: role.color }"
          aria-hidden="true"
        />
        <span class="min-w-0 flex-1 truncate text-base text-ink-gray-9">{{ role.role_label }}</span>
        <span class="shrink-0 text-sm text-ink-gray-6">{{ roleKindLabel(role.kind) }}</span>
        <span
          :class="open === role.role_label ? 'lucide-chevron-up' : 'lucide-chevron-down'"
          class="size-4 shrink-0 text-ink-gray-5"
          aria-hidden="true"
        />
      </button>
      <div v-if="open === role.role_label" class="flex flex-col gap-3 border-t border-outline-gray-1 p-3">
        <div class="flex items-end gap-2">
          <FormControl
            class="flex-1"
            :label="__('Name')"
            :model-value="role.role_label"
            @change="rename(role.role_label, $event)"
          />
          <input
            type="color"
            class="h-8 w-8 shrink-0 rounded"
            :value="role.color"
            :aria-label="__('Colour')"
            @change="store.updateRole(role.role_label, { color: ($event.target as HTMLInputElement).value })"
          />
        </div>
        <div class="grid grid-cols-2 gap-2">
          <FormControl
            type="select"
            :label="__('What they do')"
            :model-value="role.kind"
            :options="KINDS.map((k) => ({ label: roleKindLabel(k), value: k }))"
            @update:model-value="store.updateRole(role.role_label, { kind: $event })"
          />
          <FormControl
            type="number"
            :label="__('Signs as number')"
            :model-value="role.routing_order"
            @change="
              store.updateRole(role.role_label, {
                routing_order: Number(($event.target as HTMLInputElement).value) || 1,
              })
            "
          />
        </div>
        <FormControl
          type="select"
          :label="__('Who is it?')"
          :model-value="role.signer_source"
          :options="SOURCES.map((s) => ({ label: signerSourceLabel(s), value: s }))"
          @update:model-value="store.updateRole(role.role_label, { signer_source: $event })"
        />
        <FormControl
          v-if="role.signer_source === 'Fixed User'"
          :label="__('User')"
          :model-value="role.fixed_user ?? ''"
          @change="
            store.updateRole(role.role_label, {
              fixed_user: ($event.target as HTMLInputElement).value || null,
            })
          "
        />
        <FormControl
          v-if="role.signer_source === 'Doc Field'"
          :label="__('Email field')"
          :model-value="role.source_field ?? ''"
          @change="
            store.updateRole(role.role_label, {
              source_field: ($event.target as HTMLInputElement).value || null,
            })
          "
        />
        <FormControl
          type="checkbox"
          :label="__('Can pass on to someone else')"
          :model-value="Boolean(role.can_delegate)"
          @update:model-value="store.updateRole(role.role_label, { can_delegate: $event ? 1 : 0 })"
        />
        <div>
          <Button
            size="sm"
            variant="ghost"
            theme="red"
            icon-left="lucide-trash-2"
            :label="__('Remove person')"
            @click="store.removeRole(role.role_label)"
          />
        </div>
      </div>
    </div>
  </div>
</template>
