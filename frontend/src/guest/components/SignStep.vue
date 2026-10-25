<script setup lang="ts">
import { Button } from 'frappe-ui'
import { computed, nextTick, reactive, ref } from 'vue'
import PdfViewer from '@/shared/components/PdfViewer.vue'
import { __ } from '@/shared/translate'
import { canFinish, editable, isCapture, nextRequired, remaining } from '../flow'
import { readAsDataUrl } from '../signature'
import type { GuestField } from '../types'
import type { GuestFlow } from '../useGuestFlow'
import FieldBox from './FieldBox.vue'
import MoreSheet from './MoreSheet.vue'
import SignatureSheet from './SignatureSheet.vue'
import ValueSheet from './ValueSheet.vue'

const props = defineProps<{ flow: GuestFlow }>()
const state = props.flow.state
const summary = computed(() => state.summary!)
const fields = computed(() => summary.value.fields)
const isApprover = computed(() => summary.value.recipient.kind === 'Approver')

const viewer = ref<InstanceType<typeof PdfViewer> | null>(null)
const active = ref<string | null>(null)
const signatureField = ref<GuestField | null>(null)
const valueField = ref<GuestField | null>(null)
const more = ref<'decline' | 'delegate' | null>(null)
const confirming = ref(false)
const previews = reactive<Record<string, string>>({})
const attachmentInput = ref<HTMLInputElement | null>(null)
const pendingAttachment = ref<GuestField | null>(null)

const left = computed(() => remaining(fields.value))
const ready = computed(() => canFinish(fields.value))

function fieldsOn(page: number) {
  return fields.value.filter((field) => field.page === page)
}

async function reveal(field: GuestField) {
  active.value = field.key
  viewer.value?.scrollToPage(field.page)
  await nextTick()
  document
    .querySelector(`[data-field="${field.key}"]`)
    ?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

async function openField(field: GuestField) {
  if (!editable(field)) return
  active.value = field.key
  state.error = ''
  if (field.type === 'Checkbox') {
    await props.flow.saveValue(field.key, field.value === '1' ? '0' : '1')
  } else if (field.type === 'Attachment') {
    pendingAttachment.value = field
    attachmentInput.value?.click()
  } else if (isCapture(field)) {
    signatureField.value = field
  } else {
    valueField.value = field
  }
}

async function next() {
  const field = nextRequired(fields.value, active.value ?? undefined)
  if (!field) return
  await reveal(field)
  await openField(field)
}

async function saveSignature(method: string, image: string) {
  const field = signatureField.value
  if (!field) return
  if (await props.flow.saveCapture(field.key, method, image)) {
    previews[field.key] = image
    signatureField.value = null
    await reveal(field)
  }
}

async function saveValue(value: string) {
  const field = valueField.value
  if (field && (await props.flow.saveValue(field.key, value))) valueField.value = null
}

async function attach(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  const field = pendingAttachment.value
  input.value = ''
  if (file && field) await props.flow.saveCapture(field.key, 'Upload', await readAsDataUrl(file), file.name)
}
</script>

<template>
  <div class="flex min-h-full flex-col bg-surface-gray-2" data-testid="sign">
    <header class="sticky top-0 z-10 border-b border-outline-gray-1 bg-surface-base px-4 py-3">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <h1 class="truncate text-base font-semibold text-ink-gray-9">{{ summary.envelope.title }}</h1>
          <p class="truncate text-sm text-ink-gray-5">
            {{ __('From {0}', [summary.envelope.sender_name]) }}
          </p>
        </div>
        <div class="flex shrink-0 gap-1">
          <Button
            v-if="summary.recipient.can_delegate"
            size="sm"
            variant="ghost"
            :label="__('Delegate')"
            @click="more = 'delegate'"
          />
          <Button
            size="sm"
            variant="ghost"
            theme="red"
            :label="__('Decline')"
            data-testid="open-decline"
            @click="more = 'decline'"
          />
        </div>
      </div>
    </header>

    <main class="flex-1 px-2 py-3 pb-28">
      <PdfViewer ref="viewer" :source="state.pdf" :pages="summary.pages">
        <template #page="{ page }">
          <FieldBox
            v-for="field in fieldsOn(page)"
            :key="field.key"
            :field="field"
            :active="active === field.key"
            :preview="previews[field.key]"
            :signer="summary.recipient.full_name"
            @open="openField"
          />
        </template>
      </PdfViewer>
    </main>

    <footer
      class="fixed inset-x-0 bottom-0 z-20 border-t border-outline-gray-1 bg-surface-base px-4 py-3 shadow-lg"
    >
      <p
        v-if="state.error && !signatureField && !valueField && !more"
        class="mb-2 text-sm text-ink-red-4"
        role="alert"
      >
        {{ state.error }}
      </p>
      <div class="mx-auto flex max-w-lg items-center gap-3">
        <p class="min-w-0 flex-1 text-sm text-ink-gray-6" data-testid="progress">
          <template v-if="isApprover">{{ __('Review the document, then approve it.') }}</template>
          <template v-else-if="left">{{ __('{0} required fields left', [left]) }}</template>
          <template v-else>{{ __('All required fields are filled.') }}</template>
        </p>
        <Button
          v-if="!ready"
          variant="solid"
          size="md"
          :label="active ? __('Next field') : __('Start')"
          data-testid="next"
          @click="next"
        />
        <Button
          v-else
          variant="solid"
          size="md"
          :label="isApprover ? __('Approve') : __('Finish')"
          data-testid="finish"
          @click="confirming = true"
        />
      </div>
    </footer>

    <input
      ref="attachmentInput"
      type="file"
      accept="application/pdf,image/png,image/jpeg"
      class="hidden"
      @change="attach"
    />

    <SignatureSheet
      :field="signatureField"
      :name="summary.recipient.full_name"
      :busy="state.busy"
      :error="state.error"
      @close="signatureField = null"
      @save="saveSignature"
    />
    <ValueSheet
      :field="valueField"
      :busy="state.busy"
      :error="state.error"
      @close="valueField = null"
      @save="saveValue"
    />
    <MoreSheet
      :mode="more"
      :busy="state.busy"
      :error="state.error"
      @close="more = null"
      @decline="(reason) => flow.decline(reason)"
      @delegate="(name, email) => flow.delegate(name, email)"
    />

    <div
      v-if="confirming"
      class="fixed inset-0 z-30 flex items-end justify-center bg-black/40 p-4 sm:items-center"
      role="dialog"
      aria-modal="true"
    >
      <div class="w-full max-w-sm rounded-lg bg-surface-base p-5 shadow-xl" data-testid="confirm">
        <h2 class="text-lg font-semibold text-ink-gray-9">
          {{ isApprover ? __('Approve this document?') : __('Finish signing?') }}
        </h2>
        <p class="mt-2 text-base text-ink-gray-6">
          {{
            __('Your signature and the date are added to the document. You cannot change them afterwards.')
          }}
        </p>
        <p v-if="state.error" class="mt-2 text-sm text-ink-red-4" role="alert">{{ state.error }}</p>
        <div class="mt-5 flex gap-2">
          <Button class="flex-1" size="md" :label="__('Back')" @click="confirming = false" />
          <Button
            class="flex-1"
            variant="solid"
            size="md"
            :loading="state.busy"
            :label="isApprover ? __('Approve') : __('Finish')"
            data-testid="confirm-finish"
            @click="flow.finish()"
          />
        </div>
      </div>
    </div>
  </div>
</template>
