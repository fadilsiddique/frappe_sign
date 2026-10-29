<script setup lang="ts">
// Upload a company seal: a PKCS#12 (.p12) file and its password.
import { Button, Dialog, FormControl, toast } from 'frappe-ui'
import { ref, watch } from 'vue'
import { __ } from '@/shared/translate'
import { errorMessage, fileToBase64, staff } from '../api'

const props = defineProps<{ company: string }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ done: [] }>()

const file = ref<File | null>(null)
const password = ref('')
const kind = ref('CA-issued')
const busy = ref(false)

watch(open, (value) => {
  if (!value) return
  file.value = null
  password.value = ''
  kind.value = 'CA-issued'
})

async function upload() {
  if (!file.value || !password.value) {
    toast.error(__('Choose the file and enter its password.'))
    return
  }
  busy.value = true
  try {
    await staff('upload_certificate', {
      company: props.company,
      file_name: file.value.name,
      content: await fileToBase64(file.value),
      password: password.value,
      kind: kind.value,
    })
    toast.success(__('Company seal updated'))
    open.value = false
    emit('done')
  } catch (error) {
    toast.error(errorMessage(error))
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <Dialog v-model="open" :title="__('Upload a certificate')" size="lg">
    <form class="flex flex-col gap-4" data-testid="seal-dialog" @submit.prevent="upload">
      <p class="text-p-sm text-ink-gray-7">
        {{
          __('Use the .p12 file from your certificate provider. It replaces the current seal of {0}.', [
            company,
          ])
        }}
      </p>
      <label class="flex flex-col gap-1.5 text-sm text-ink-gray-7">
        {{ __('Certificate file (.p12 or .pfx)') }}
        <input
          type="file"
          accept=".p12,.pfx"
          class="text-base text-ink-gray-9 file:me-3 file:rounded file:border-0 file:bg-surface-gray-2 file:px-3 file:py-1.5 file:text-sm file:text-ink-gray-8"
          data-testid="seal-file"
          @change="file = ($event.target as HTMLInputElement).files?.[0] ?? null"
        />
      </label>
      <FormControl
        v-model="password"
        type="password"
        :label="__('Password of the file')"
        autocomplete="off"
        data-testid="seal-password"
      />
      <FormControl
        v-model="kind"
        type="select"
        :label="__('Issued by')"
        :options="[
          { label: __('A certificate authority'), value: 'CA-issued' },
          { label: __('An Adobe approved provider (AATL)'), value: 'AATL' },
        ]"
      />
      <div class="flex justify-end gap-2">
        <Button variant="ghost" :label="__('Cancel')" @click="open = false" />
        <Button
          variant="solid"
          type="submit"
          :label="__('Upload')"
          :loading="busy"
          data-testid="seal-upload"
        />
      </div>
    </form>
  </Dialog>
</template>
