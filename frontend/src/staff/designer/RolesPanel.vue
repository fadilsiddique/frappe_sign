<script setup lang="ts">
import { Button, FormControl } from 'frappe-ui'
import { __ } from '@/shared/translate'
import { useDesigner } from './store'

const store = useDesigner()
const KINDS = ['Signer', 'Approver', 'CC']
const SOURCES = ['Ask at Send', 'Fixed User', 'Doc Field', 'Party Contact', 'Employee']
</script>

<template>
  <div class="space-y-3" data-testid="roles">
    <div class="flex items-center justify-between">
      <h3 class="text-sm font-semibold text-ink-gray-8">{{ __('Roles') }}</h3>
      <Button size="sm" :label="__('Add role')" @click="store.addRole('Signer')" />
    </div>
    <div
      v-for="role in store.roles"
      :key="role.role_label"
      class="space-y-2 rounded border p-2"
      :class="store.activeRole === role.role_label ? 'border-outline-gray-4' : 'border-outline-gray-1'"
      @click="role.kind === 'Signer' && (store.activeRole = role.role_label)"
    >
      <div class="flex items-center gap-2">
        <input
          type="color"
          class="size-6 shrink-0 rounded"
          :value="role.color"
          :aria-label="__('Colour')"
          @change="store.updateRole(role.role_label, { color: ($event.target as HTMLInputElement).value })"
        />
        <FormControl
          class="flex-1"
          :model-value="role.role_label"
          @change="
            store.updateRole(role.role_label, {
              role_label: ($event.target as HTMLInputElement).value.trim() || role.role_label,
            })
          "
        />
        <Button
          size="sm"
          variant="ghost"
          :label="'×'"
          :aria-label="__('Remove role')"
          @click.stop="store.removeRole(role.role_label)"
        />
      </div>
      <div class="grid grid-cols-2 gap-2">
        <FormControl
          type="select"
          :label="__('Kind')"
          :model-value="role.kind"
          :options="KINDS.map((k) => ({ label: __(k), value: k }))"
          @update:model-value="store.updateRole(role.role_label, { kind: $event })"
        />
        <FormControl
          type="number"
          :label="__('Order')"
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
        :label="__('Who signs')"
        :model-value="role.signer_source"
        :options="SOURCES.map((s) => ({ label: __(s), value: s }))"
        @update:model-value="store.updateRole(role.role_label, { signer_source: $event })"
      />
      <FormControl
        v-if="role.signer_source === 'Fixed User'"
        :label="__('User')"
        :model-value="role.fixed_user ?? ''"
        @change="
          store.updateRole(role.role_label, { fixed_user: ($event.target as HTMLInputElement).value || null })
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
    </div>
  </div>
</template>
