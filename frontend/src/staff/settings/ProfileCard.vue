<script setup lang="ts">
// One company: logo and color, sender email, who signs, and the seal. Saved together.
import { Button, FormControl, toast } from 'frappe-ui'
import { computed, ref, watch } from 'vue'
import { __ } from '@/shared/translate'
import { errorMessage, staff, uploadPublicImage } from '../api'
import SealDialog from './SealDialog.vue'
import { sealLine, senderLine, toneClass, toneIcon } from './lines'
import type { ProfileCard, SettingsData } from './types'

const props = defineProps<{ profile: ProfileCard; data: SettingsData }>()
const emit = defineEmits<{ changed: [] }>()

const FIELDS = [
  'logo',
  'brand_color',
  'legal_footer',
  'sender_email_account',
  'authorised_signatory',
] as const
type Draft = Record<(typeof FIELDS)[number], string>

const draft = ref<Draft>(fromProfile(props.profile))
const saving = ref(false)
const sealBusy = ref(false)
const uploading = ref(false)
const sealDialog = ref(false)

function fromProfile(profile: ProfileCard): Draft {
  return Object.fromEntries(FIELDS.map((field) => [field, profile[field] ?? ''])) as Draft
}
watch(
  () => props.profile,
  (next) => (draft.value = fromProfile(next)),
)

const canEdit = computed(() => props.data.can_edit)
const dirty = computed(() => FIELDS.some((field) => draft.value[field] !== (props.profile[field] ?? '')))
const seal = computed(() => sealLine(props.profile.seal))
const sender = computed(() => senderLine(props.profile.sender))
const hasValidSeal = computed(() => Boolean(props.profile.seal.kind) && !props.profile.seal.expired)
const colorValid = computed(
  () => !draft.value.brand_color || /^#[0-9a-fA-F]{6}$/.test(draft.value.brand_color),
)

async function save() {
  if (!colorValid.value) {
    toast.error(__('Enter the color as #RRGGBB, for example #0f766e.'))
    return
  }
  saving.value = true
  try {
    await staff('save_profile', { company: props.profile.company, values: draft.value })
    toast.success(__('Saved'))
    emit('changed')
  } catch (error) {
    toast.error(errorMessage(error))
  } finally {
    saving.value = false
  }
}

async function pickLogo(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  uploading.value = true
  try {
    draft.value.logo = await uploadPublicImage(file)
  } catch (error) {
    toast.error(errorMessage(error))
  } finally {
    uploading.value = false
  }
}

async function createTestSeal() {
  sealBusy.value = true
  try {
    await staff('create_test_certificate', {
      company: props.profile.company,
      common_name: props.profile.company,
      replace: true,
    })
    toast.success(__('Test seal created'))
    emit('changed')
  } catch (error) {
    toast.error(errorMessage(error))
  } finally {
    sealBusy.value = false
  }
}
</script>

<template>
  <section
    class="flex flex-col gap-5 rounded-lg bg-surface-base p-4"
    :aria-label="profile.company"
    :data-testid="`profile-${profile.company}`"
  >
    <header class="flex items-center gap-3">
      <span
        class="grid size-10 shrink-0 place-items-center overflow-hidden rounded-md bg-surface-gray-2 text-ink-gray-6"
      >
        <img
          v-if="draft.logo"
          :src="draft.logo"
          :alt="__('Logo of {0}', [profile.company])"
          class="size-full object-contain"
        />
        <span v-else class="lucide-building-2 size-5" aria-hidden="true" />
      </span>
      <h2 class="min-w-0 flex-1 truncate text-lg font-semibold text-ink-gray-9">{{ profile.company }}</h2>
    </header>

    <div class="grid gap-4 md:grid-cols-2">
      <div class="flex flex-col gap-1.5">
        <span class="text-sm text-ink-gray-7">{{ __('Logo') }}</span>
        <div class="flex items-center gap-2">
          <label
            class="inline-flex h-7 cursor-pointer items-center gap-1.5 rounded bg-surface-gray-2 px-2 text-base text-ink-gray-8 focus-within:focus-ring hover:bg-surface-gray-3"
            :class="{ 'pointer-events-none opacity-50': !canEdit || uploading }"
          >
            <span class="lucide-image-up size-4" aria-hidden="true" />
            {{ draft.logo ? __('Change logo') : __('Upload logo') }}
            <input
              type="file"
              accept="image/*"
              class="sr-only"
              data-testid="logo-file"
              :disabled="!canEdit"
              @change="pickLogo"
            />
          </label>
          <Button
            v-if="draft.logo && canEdit"
            variant="ghost"
            :label="__('Remove')"
            @click="draft.logo = ''"
          />
        </div>
        <span class="text-sm text-ink-gray-6">{{
          __('Shown at the top of the signing page and emails.')
        }}</span>
      </div>

      <div class="flex flex-col gap-1.5">
        <label class="text-sm text-ink-gray-7" :for="`color-${profile.company}`">{{
          __('Brand color')
        }}</label>
        <div class="flex items-center gap-2">
          <input
            type="color"
            class="size-7 shrink-0 cursor-pointer rounded border border-outline-gray-2 bg-transparent p-0.5"
            :value="colorValid && draft.brand_color ? draft.brand_color : '#000000'"
            :aria-label="__('Pick the brand color')"
            :disabled="!canEdit"
            @input="draft.brand_color = ($event.target as HTMLInputElement).value"
          />
          <FormControl
            :id="`color-${profile.company}`"
            v-model="draft.brand_color"
            placeholder="#0f766e"
            :disabled="!canEdit"
            class="w-32"
            data-testid="brand-color"
          />
        </div>
        <span class="text-sm text-ink-gray-6">{{ __('Buttons and fields on the signing page.') }}</span>
      </div>

      <div class="flex flex-col gap-1.5">
        <FormControl
          v-model="draft.sender_email_account"
          type="select"
          :label="__('Send emails from')"
          :disabled="!canEdit"
          :options="[
            { label: __('The site default'), value: '' },
            ...data.email_accounts.map((a) => ({ label: a.email_id, value: a.name })),
          ]"
          data-testid="sender-account"
        />
        <p class="flex items-start gap-1.5 text-sm text-ink-gray-8" data-testid="sender-status">
          <span
            :class="[toneIcon[sender.tone], toneClass[sender.tone]]"
            class="mt-0.5 size-4 shrink-0"
            aria-hidden="true"
          />{{ sender.text }}
        </p>
      </div>

      <FormControl
        v-model="draft.authorised_signatory"
        type="select"
        :label="__('Signs for the company')"
        :disabled="!canEdit"
        :options="[
          { label: __('Chosen when sending'), value: '' },
          ...data.signatories.map((u) => ({ label: u.full_name || u.name, value: u.name })),
        ]"
        data-testid="signatory"
      />

      <div class="md:col-span-2">
        <FormControl
          v-model="draft.legal_footer"
          type="textarea"
          :rows="2"
          :label="__('Line at the bottom of the certificate page')"
          :disabled="!canEdit"
        />
      </div>
    </div>

    <div class="flex flex-col gap-3 border-t border-outline-gray-1 pt-4" data-testid="seal">
      <div class="flex flex-col gap-1">
        <h3 class="text-base font-medium text-ink-gray-9">{{ __('Company seal') }}</h3>
        <p class="flex items-start gap-1.5 text-sm text-ink-gray-8" data-testid="seal-status">
          <span
            :class="[toneIcon[seal.tone], toneClass[seal.tone]]"
            class="mt-0.5 size-4 shrink-0"
            aria-hidden="true"
          />{{ seal.text }}
        </p>
      </div>
      <div v-if="canEdit" class="flex flex-wrap gap-2">
        <Button
          v-if="!hasValidSeal"
          variant="outline"
          icon-left="lucide-stamp"
          :label="__('Create test seal')"
          :loading="sealBusy"
          data-testid="create-test-seal"
          @click="createTestSeal"
        />
        <Button
          variant="outline"
          icon-left="lucide-file-up"
          :label="hasValidSeal ? __('Replace certificate') : __('Upload certificate')"
          data-testid="open-seal-dialog"
          @click="sealDialog = true"
        />
      </div>
    </div>

    <footer v-if="canEdit" class="flex justify-end">
      <Button
        variant="solid"
        :label="__('Save')"
        :disabled="!dirty"
        :loading="saving"
        data-testid="save-profile"
        @click="save"
      />
    </footer>
    <SealDialog v-model="sealDialog" :company="profile.company" @done="emit('changed')" />
  </section>
</template>
