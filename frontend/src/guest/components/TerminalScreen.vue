<script setup lang="ts">
import { computed } from 'vue'
import { __ } from '@/shared/translate'
import type { Terminal } from '../flow'
import BrandIcon from './BrandIcon.vue'
import GuestHeader from './GuestHeader.vue'

const props = defineProps<{
  screen: Terminal
  title?: string
  company?: string | null
  waitingFor?: string[]
  completed?: boolean
  error?: string
}>()

const content = computed(() => {
  switch (props.screen) {
    case 'signed':
      return {
        title: props.title ? __('You signed {0}', [props.title]) : __('Thank you for signing'),
        body: props.completed
          ? __('Everyone has signed. Everyone will get the signed PDF by email shortly.')
          : __('Everyone will get the signed PDF by email once all signers are done.'),
        tone: 'green',
        icon: 'check',
      }
    case 'already':
      return {
        title: __('Already signed'),
        body: __('You have already responded to this document.'),
        tone: 'green',
        icon: 'check',
      }
    case 'waiting':
      return {
        title: __('Not your turn yet'),
        body: __('Waiting for {0} to sign first. We will email you when it is your turn.', [
          (props.waitingFor ?? []).join(', ') || __('another signer'),
        ]),
        tone: 'gray',
        icon: 'clock',
      }
    case 'declined':
      return {
        title: __('Declined'),
        body: __('This document was declined. The sender has been told.'),
        tone: 'red',
        icon: 'x',
      }
    case 'delegated':
      return {
        title: __('Passed on'),
        body: __('Someone else will sign in your place. You can close this page.'),
        tone: 'gray',
        icon: 'check',
      }
    case 'voided':
      return {
        title: __('Cancelled'),
        body: __('The sender cancelled this document. You do not need to sign it.'),
        tone: 'gray',
        icon: 'ban',
      }
    case 'completed':
      return {
        title: __('Completed'),
        body: __('Everyone has signed this document.'),
        tone: 'green',
        icon: 'check',
      }
    case 'expired':
      return {
        title: __('Link not valid'),
        body: __('This link has expired or was replaced by a newer one. Ask the sender for a new link.'),
        tone: 'gray',
        icon: 'clock',
      }
    default:
      return {
        title: __('Something went wrong'),
        body: props.error || __('Reload the page to try again.'),
        tone: 'red',
        icon: 'alert',
      }
  }
})
</script>

<template>
  <div class="-mx-3 flex min-h-screen flex-col bg-surface-base" data-testid="terminal" :data-screen="screen">
    <GuestHeader :company="company" />
    <section class="mx-auto flex w-full max-w-sm flex-1 flex-col items-center px-6 pt-20 text-center">
      <div
        class="mb-5 flex size-14 items-center justify-center rounded-full"
        :class="{
          'bg-surface-green-2 text-ink-green-3': content.tone === 'green',
          'bg-surface-red-2 text-ink-red-4': content.tone === 'red',
          'bg-surface-gray-2 text-ink-gray-6': content.tone === 'gray',
        }"
      >
        <BrandIcon :name="content.icon as any" class="size-7" />
      </div>
      <h1 class="text-xl font-semibold text-ink-gray-9">{{ content.title }}</h1>
      <p class="mt-2 text-base text-ink-gray-6">{{ content.body }}</p>
    </section>
  </div>
</template>
