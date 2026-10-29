<script setup lang="ts">
// Defaults for every request: how long it lasts, reminders, the emailed code and the consent text.
import { Button, FormControl, toast } from 'frappe-ui'
import { computed, ref, watch } from 'vue'
import { __ } from '@/shared/translate'
import { errorMessage, staff } from '../api'
import { consentToHtml, consentToText } from './lines'
import type { SettingsData } from './types'

const props = defineProps<{ data: SettingsData }>()
const emit = defineEmits<{ changed: [] }>()

function fromData() {
  const s = props.data.signing
  return {
    expiry: String(s.default_expiry_days),
    reminder: String(s.default_reminder_days),
    otp: String(s.otp_validity_minutes),
    consent: consentToText(s.consent_text),
  }
}
const draft = ref(fromData())
const saving = ref(false)
watch(
  () => props.data.signing,
  () => (draft.value = fromData()),
)

const dirty = computed(() => JSON.stringify(draft.value) !== JSON.stringify(fromData()))

async function save() {
  saving.value = true
  try {
    await staff('save_settings', {
      section: 'signing',
      values: {
        default_expiry_days: draft.value.expiry,
        default_reminder_days: draft.value.reminder,
        otp_validity_minutes: draft.value.otp,
        consent_text: consentToHtml(draft.value.consent),
      },
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
    data-testid="tab-signing"
    @submit.prevent="save"
  >
    <div class="grid gap-4 sm:grid-cols-3">
      <FormControl
        v-model="draft.expiry"
        type="number"
        min="1"
        :label="__('Request lasts (days)')"
        :disabled="!data.can_edit"
        data-testid="expiry-days"
      />
      <FormControl
        v-model="draft.reminder"
        type="number"
        min="0"
        :label="__('Remind every (days)')"
        :description="__('0 turns reminders off.')"
        :disabled="!data.can_edit"
      />
      <FormControl
        v-model="draft.otp"
        type="number"
        min="1"
        :label="__('Emailed code lasts (minutes)')"
        :disabled="!data.can_edit"
      />
    </div>
    <FormControl
      v-model="draft.consent"
      type="textarea"
      :rows="6"
      :label="__('Words signers agree to')"
      :description="__('Leave empty to use the standard text. A blank line starts a new paragraph.')"
      :disabled="!data.can_edit"
      data-testid="consent-text"
    />
    <div v-if="data.can_edit" class="flex justify-end">
      <Button
        variant="solid"
        type="submit"
        :label="__('Save')"
        :disabled="!dirty"
        :loading="saving"
        data-testid="save-signing"
      />
    </div>
  </form>
</template>
