<script setup lang="ts">
// A card for each company's Sign Profile, and a way to add the next one.
import { Button, FormControl, toast } from 'frappe-ui'
import { ref } from 'vue'
import { __ } from '@/shared/translate'
import EmptyState from '../components/EmptyState.vue'
import { errorMessage, staff } from '../api'
import ProfileCard from './ProfileCard.vue'
import type { SettingsData } from './types'

defineProps<{ data: SettingsData }>()
const emit = defineEmits<{ changed: [] }>()

const adding = ref(false)
const company = ref('')
const busy = ref(false)

async function add(name: string) {
  if (!name.trim()) return
  busy.value = true
  try {
    await staff('save_profile', { company: name.trim(), values: {} })
    adding.value = false
    company.value = ''
    emit('changed')
  } catch (error) {
    toast.error(errorMessage(error))
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="flex flex-col gap-4" data-testid="tab-company">
    <EmptyState
      v-if="!data.profiles.length"
      icon="lucide-building-2"
      :title="__('No company yet')"
      :text="__('A company profile holds the seal, the logo and the sender email for its documents.')"
    />
    <ProfileCard
      v-for="profile in data.profiles"
      :key="profile.company"
      :profile="profile"
      :data="data"
      @changed="emit('changed')"
    />
    <div v-if="data.can_edit" class="flex flex-wrap items-end gap-2">
      <Button
        v-if="!adding"
        variant="outline"
        icon-left="lucide-plus"
        :label="__('Add a company')"
        data-testid="add-company"
        @click="adding = true"
      />
      <template v-else>
        <FormControl
          v-if="data.has_erpnext"
          v-model="company"
          type="select"
          :label="__('Company')"
          :options="[
            { label: __('Choose a company'), value: '' },
            ...data.companies.map((c) => ({ label: c, value: c })),
          ]"
          data-testid="new-company"
        />
        <FormControl v-else v-model="company" :label="__('Company name')" data-testid="new-company" />
        <Button
          variant="solid"
          :label="__('Add')"
          :loading="busy"
          data-testid="confirm-add-company"
          @click="add(company)"
        />
        <Button variant="ghost" :label="__('Cancel')" @click="adding = false" />
      </template>
    </div>
  </div>
</template>
