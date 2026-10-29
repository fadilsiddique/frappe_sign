<script setup lang="ts">
// Timestamp servers and upload limits. Most sites never change these.
import { Button, FormControl, toast } from 'frappe-ui'
import { computed, ref, watch } from 'vue'
import { __ } from '@/shared/translate'
import { errorMessage, staff } from '../api'
import type { SettingsData } from './types'

const props = defineProps<{ data: SettingsData }>()
const emit = defineEmits<{ changed: [] }>()

function fromData() {
  const a = props.data.advanced
  return { tsa: a.tsa_urls ?? '', mb: String(a.max_upload_mb), pages: String(a.max_pages) }
}
const draft = ref(fromData())
const saving = ref(false)
watch(
  () => props.data.advanced,
  () => (draft.value = fromData()),
)
const dirty = computed(() => JSON.stringify(draft.value) !== JSON.stringify(fromData()))

async function save() {
  saving.value = true
  try {
    await staff('save_settings', {
      section: 'advanced',
      values: { tsa_urls: draft.value.tsa, max_upload_mb: draft.value.mb, max_pages: draft.value.pages },
    })
    toast.success(__('Saved'))
    emit('changed')
  } catch (error) {
    toast.error(errorMessage(error))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <form
    class="flex max-w-2xl flex-col gap-5 rounded-lg bg-surface-base p-4"
    data-testid="tab-advanced"
    @submit.prevent="save"
  >
    <FormControl
      v-model="draft.tsa"
      type="textarea"
      :rows="3"
      :label="__('Timestamp servers')"
      :description="
        __(
          'One web address per line. A timestamp proves when a document was sealed. Leave empty to use the built-in servers.',
        )
      "
      :disabled="!data.can_edit"
      data-testid="tsa-urls"
    />
    <div class="grid gap-4 sm:grid-cols-2">
      <FormControl
        v-model="draft.mb"
        type="number"
        min="1"
        :label="__('Largest upload (MB)')"
        :disabled="!data.can_edit"
      />
      <FormControl
        v-model="draft.pages"
        type="number"
        min="1"
        :label="__('Most pages in a document')"
        :disabled="!data.can_edit"
      />
    </div>
    <div v-if="data.can_edit" class="flex justify-end">
      <Button
        variant="solid"
        type="submit"
        :label="__('Save')"
        :disabled="!dirty"
        :loading="saving"
        data-testid="save-advanced"
      />
    </div>
  </form>
</template>
