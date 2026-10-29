<script setup lang="ts">
// The document comes first: who sent it and why, then the consent as a sheet pinned to the bottom.
import { ref } from 'vue'
import type { Summary } from '../types'
import GuestHeader from './GuestHeader.vue'

const props = defineProps<{ summary: Summary; busy: boolean; error: string }>()
const emit = defineEmits<{ accept: [] }>()
const agreed = ref(false)
const company = props.summary.envelope.company
</script>

<template>
  <div class="-mx-3 flex min-h-screen flex-col bg-surface-gray-2" data-testid="consent">
    <GuestHeader :title="summary.envelope.title" :company="summary.envelope.company" />

    <main class="flex-1 px-4 pb-96 pt-6">
      <div class="mx-auto max-w-lg">
        <p class="text-sm text-ink-gray-6">
          {{
            company
              ? __('From {0}, sent by {1}', [company, summary.envelope.sender_name])
              : __('Sent by {0}', [summary.envelope.sender_name])
          }}
        </p>
        <h1 class="mt-1 text-xl font-semibold text-ink-gray-9">{{ summary.envelope.title }}</h1>
        <p class="mt-1 text-base text-ink-gray-6">
          {{
            summary.recipient.kind === 'Approver'
              ? __('You are asked to approve this document.')
              : __('You are asked to sign this document.')
          }}
        </p>
        <p
          v-if="summary.envelope.message"
          class="mt-4 whitespace-pre-line border-s-2 border-outline-gray-3 ps-3 text-base text-ink-gray-7"
        >
          {{ summary.envelope.message }}
        </p>
      </div>
    </main>

    <section
      class="fixed inset-x-0 bottom-0 z-20 rounded-t-xl border-t border-outline-gray-1 bg-surface-base px-4 pb-5 pt-4 shadow-2xl"
      :aria-label="__('Electronic records and signatures')"
    >
      <div class="mx-auto max-w-lg">
        <h2 class="text-base font-semibold text-ink-gray-9">{{ __('Electronic records and signatures') }}</h2>
        <!-- eslint-disable vue/no-v-html -->
        <!-- consent_text is set by a Sign Manager in Sign Settings; Frappe sanitizes Text Editor HTML on save. -->
        <div
          class="prose prose-sm mt-2 max-h-32 overflow-y-auto text-ink-gray-7"
          tabindex="0"
          v-html="summary.consent.text"
        />
        <!-- eslint-enable vue/no-v-html -->
        <label
          class="mt-4 flex cursor-pointer items-start gap-3 rounded-lg border border-outline-gray-2 p-3 text-base text-ink-gray-8"
        >
          <input
            v-model="agreed"
            type="checkbox"
            class="mt-0.5 size-5 shrink-0 rounded border-outline-gray-4"
            :style="{ accentColor: 'var(--sign-brand)' }"
            data-testid="agree"
          />
          <span>{{ __('I agree to sign electronically.') }}</span>
        </label>
        <button
          type="button"
          class="mt-3 flex h-11 w-full items-center justify-center rounded-lg text-base font-medium text-white transition disabled:cursor-not-allowed disabled:opacity-40"
          :style="{ background: 'var(--sign-brand)' }"
          :disabled="!agreed || busy"
          data-testid="start"
          @click="emit('accept')"
        >
          {{ busy ? __('Opening...') : __('Review and sign') }}
        </button>
        <p v-if="error" class="mt-3 text-sm text-ink-red-4" role="alert">{{ error }}</p>
      </div>
    </section>
  </div>
</template>
