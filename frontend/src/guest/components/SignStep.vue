<script setup lang="ts">
import { computed, nextTick, reactive, ref } from 'vue'
import PdfViewer from '@/shared/components/PdfViewer.vue'
import { __ } from '@/shared/translate'
import { canFinish, editable, isCapture, nextRequired, progress } from '../flow'
import { readAsDataUrl } from '../signature'
import type { GuestField } from '../types'
import type { GuestFlow } from '../useGuestFlow'
import BrandIcon from './BrandIcon.vue'
import FieldBox from './FieldBox.vue'
import GuestHeader from './GuestHeader.vue'
import MoreSheet from './MoreSheet.vue'
import ReviewSheet from './ReviewSheet.vue'
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
const menu = ref(false)
const previews = reactive<Record<string, string>>({})
const attachmentInput = ref<HTMLInputElement | null>(null)
const pendingAttachment = ref<GuestField | null>(null)

const count = computed(() => progress(fields.value))
const upcoming = computed(() => nextRequired(fields.value, active.value ?? undefined))
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

function choose(mode: 'decline' | 'delegate') {
  menu.value = false
  more.value = mode
}

async function next() {
  const field = upcoming.value
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
    <div class="sticky top-0 z-10">
      <GuestHeader :title="summary.envelope.title" :company="summary.envelope.company">
        <div class="relative">
          <button
            type="button"
            class="flex size-9 items-center justify-center rounded-lg text-ink-gray-7 hover:bg-surface-gray-2"
            :aria-label="__('More')"
            aria-haspopup="menu"
            :aria-expanded="menu"
            data-testid="more"
            @click="menu = !menu"
          >
            <BrandIcon name="more" />
          </button>
          <template v-if="menu">
            <div class="fixed inset-0 z-10" @click="menu = false" />
            <div
              role="menu"
              class="absolute end-0 top-10 z-20 w-56 rounded-lg border border-outline-gray-2 bg-surface-base p-1 shadow-lg"
            >
              <button
                v-if="summary.recipient.can_delegate"
                type="button"
                role="menuitem"
                class="flex w-full rounded px-3 py-2 text-start text-base text-ink-gray-8 hover:bg-surface-gray-2"
                data-testid="open-delegate"
                @click="choose('delegate')"
              >
                {{ __('Pass to someone else') }}
              </button>
              <button
                type="button"
                role="menuitem"
                class="flex w-full rounded px-3 py-2 text-start text-base text-ink-red-4 hover:bg-surface-gray-2"
                data-testid="open-decline"
                @click="choose('decline')"
              >
                {{ __('Decline to sign') }}
              </button>
            </div>
          </template>
        </div>
      </GuestHeader>
      <div
        v-if="count.total"
        class="h-1 bg-surface-gray-3"
        role="progressbar"
        :aria-valuemin="0"
        :aria-valuemax="count.total"
        :aria-valuenow="count.done"
        :aria-label="__('Signing progress')"
      >
        <div
          class="h-full transition-all"
          :style="{ width: `${(count.done / count.total) * 100}%`, background: 'var(--sign-brand)' }"
        />
      </div>
    </div>

    <p class="px-4 pt-3 text-sm text-ink-gray-6" data-testid="progress">
      <template v-if="isApprover || !count.total">{{ __('Read the document, then approve it.') }}</template>
      <template v-else>
        {{ __('{0} of {1} done', [count.done, count.total]) }}
      </template>
    </p>

    <main class="flex-1 px-2 py-3 pb-32">
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

    <div class="pointer-events-none fixed inset-x-0 bottom-0 z-20 flex flex-col items-center gap-2 px-4 pb-5">
      <p
        v-if="state.error && !signatureField && !valueField && !more"
        class="pointer-events-auto rounded-lg bg-surface-base px-3 py-2 text-sm text-ink-red-4 shadow"
        role="alert"
      >
        {{ state.error }}
      </p>
      <button
        v-if="!ready"
        type="button"
        class="pointer-events-auto flex h-12 items-center gap-2 rounded-full px-6 text-base font-medium text-white shadow-lg"
        :style="{ background: 'var(--sign-brand)' }"
        data-testid="next"
        @click="next"
      >
        {{ upcoming ? __('Next: {0}', [__(upcoming.type)]) : __('Next') }}
        <BrandIcon name="arrow-down" class="size-4" />
      </button>
      <button
        v-else
        type="button"
        class="pointer-events-auto flex h-12 items-center gap-2 rounded-full px-8 text-base font-medium text-white shadow-lg"
        :style="{ background: 'var(--sign-brand)' }"
        data-testid="finish"
        @click="confirming = true"
      >
        {{ isApprover ? __('Approve') : __('Review and finish') }}
      </button>
    </div>

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
    <ReviewSheet
      :open="confirming"
      :fields="fields"
      :approver="isApprover"
      :busy="state.busy"
      :error="state.error"
      @close="confirming = false"
      @confirm="flow.finish()"
    />
  </div>
</template>
