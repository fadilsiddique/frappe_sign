<script setup lang="ts">
import { computed } from 'vue'
import { __ } from '@/shared/translate'
import type { Terminal } from '../flow'

const props = defineProps<{ screen: Terminal; waitingFor?: string[]; completed?: boolean; error?: string }>()

const content = computed(() => {
  switch (props.screen) {
    case 'signed':
      return {
        title: __('Thank you for signing'),
        body: props.completed
          ? __('Everyone has signed. The sealed document will be emailed to you shortly.')
          : __('We will email you the completed document when everyone has signed.'),
        tone: 'green',
      }
    case 'already':
      return {
        title: __('Already signed'),
        body: __('You have already responded to this document.'),
        tone: 'green',
      }
    case 'waiting':
      return {
        title: __('Not your turn yet'),
        body: __('Waiting for {0} to sign first. We will email you when it is your turn.', [
          (props.waitingFor ?? []).join(', ') || __('another signer'),
        ]),
        tone: 'gray',
      }
    case 'declined':
      return {
        title: __('Declined'),
        body: __('This document was declined. The sender has been told.'),
        tone: 'red',
      }
    case 'delegated':
      return {
        title: __('Passed on'),
        body: __('Someone else will sign in your place. You can close this page.'),
        tone: 'gray',
      }
    case 'voided':
      return {
        title: __('Cancelled'),
        body: __('The sender cancelled this document. You do not need to sign it.'),
        tone: 'gray',
      }
    case 'completed':
      return { title: __('Completed'), body: __('Everyone has signed this document.'), tone: 'green' }
    case 'expired':
      return {
        title: __('Link not valid'),
        body: __('This link has expired or was replaced by a newer one. Ask the sender for a new link.'),
        tone: 'gray',
      }
    default:
      return {
        title: __('Something went wrong'),
        body: props.error || __('Reload the page to try again.'),
        tone: 'red',
      }
  }
})
</script>

<template>
  <section
    class="mx-auto mt-16 max-w-sm rounded-lg bg-surface-base p-6 text-center shadow"
    data-testid="terminal"
    :data-screen="screen"
  >
    <div
      class="mx-auto mb-4 flex size-12 items-center justify-center rounded-full text-xl"
      :class="{
        'bg-surface-green-2 text-ink-green-3': content.tone === 'green',
        'bg-surface-red-2 text-ink-red-4': content.tone === 'red',
        'bg-surface-gray-2 text-ink-gray-6': content.tone === 'gray',
      }"
      aria-hidden="true"
    >
      {{ content.tone === 'green' ? '✓' : content.tone === 'red' ? '!' : 'i' }}
    </div>
    <h1 class="text-lg font-semibold text-ink-gray-9">{{ content.title }}</h1>
    <p class="mt-2 text-base text-ink-gray-6">{{ content.body }}</p>
  </section>
</template>
