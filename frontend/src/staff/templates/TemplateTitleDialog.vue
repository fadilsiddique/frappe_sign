<script setup lang="ts">
// Asks for the name of a new template from your own PDF, then lets the page create it.
import { Button, Dialog, FormControl } from 'frappe-ui'
import { ref, watch } from 'vue'
import { __ } from '@/shared/translate'

const open = defineModel<boolean>({ required: true })
defineProps<{ loading?: boolean }>()
const emit = defineEmits<{ create: [title: string] }>()

const title = ref('')
watch(open, (value) => {
  if (value) title.value = ''
})

function submit() {
  const value = title.value.trim()
  if (value) emit('create', value)
}
</script>

<template>
  <Dialog v-model="open" :title="__('Name your template')" size="md">
    <form class="flex flex-col gap-5" data-testid="template-title-form" @submit.prevent="submit">
      <div class="flex items-start gap-3">
        <span
          class="grid size-10 shrink-0 place-items-center rounded-[12px] bg-[var(--sign-accent-50)] text-[var(--sign-accent-600)]"
          aria-hidden="true"
        >
          <span class="lucide-file-up size-5" />
        </span>
        <p class="text-p-base text-ink-gray-7">
          {{ __('Pick a name your team will recognise, such as "Lease agreement". You can rename it later.') }}
        </p>
      </div>
      <FormControl
        v-model="title"
        :label="__('Template title')"
        :placeholder="__('Lease agreement')"
        autofocus
        data-testid="template-title"
      />
      <div class="flex justify-end gap-2">
        <Button :label="__('Cancel')" variant="subtle" type="button" @click="open = false" />
        <Button
          :label="__('Continue')"
          variant="solid"
          type="submit"
          :disabled="!title.trim()"
          :loading="loading"
          data-testid="template-title-submit"
        />
      </div>
    </form>
  </Dialog>
</template>
