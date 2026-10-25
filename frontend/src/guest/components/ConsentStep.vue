<script setup lang="ts">
import { Button } from 'frappe-ui'
import { ref } from 'vue'
import type { Summary } from '../types'

defineProps<{ summary: Summary; busy: boolean; error: string }>()
const emit = defineEmits<{ accept: [] }>()
const agreed = ref(false)
</script>

<template>
  <section class="mx-auto mt-6 max-w-lg rounded-lg bg-surface-base p-5 shadow" data-testid="consent">
    <p class="text-sm text-ink-gray-5">
      {{ __('{0} sent you a document to sign', [summary.envelope.sender_name]) }}
    </p>
    <h1 class="mt-1 text-xl font-semibold text-ink-gray-9">{{ summary.envelope.title }}</h1>
    <p
      v-if="summary.envelope.message"
      class="mt-3 whitespace-pre-line rounded bg-surface-gray-1 p-3 text-base text-ink-gray-7"
    >
      {{ summary.envelope.message }}
    </p>
    <h2 class="mt-5 text-base font-medium text-ink-gray-8">{{ __('Electronic records and signatures') }}</h2>
    <!-- consent_text is set by a Sign Manager in Sign Settings; Frappe sanitizes Text Editor HTML on save. -->
    <!-- eslint-disable-next-line vue/no-v-html -->
    <div class="prose prose-sm mt-2 max-h-48 overflow-y-auto text-ink-gray-7" v-html="summary.consent.text" />
    <label class="mt-4 flex items-start gap-3 text-base text-ink-gray-8">
      <input v-model="agreed" type="checkbox" class="form-checkbox mt-1 !rounded-sm" data-testid="agree" />
      <span>{{ __('I agree to sign electronically.') }}</span>
    </label>
    <Button
      class="mt-5 w-full"
      variant="solid"
      size="md"
      :disabled="!agreed"
      :loading="busy"
      :label="__('Review and sign')"
      data-testid="start"
      @click="emit('accept')"
    />
    <p v-if="error" class="mt-3 text-sm text-ink-red-4" role="alert">{{ error }}</p>
  </section>
</template>
