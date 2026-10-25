<script setup lang="ts">
import { Button, createResource, toast } from 'frappe-ui'
import { __ } from '@/shared/translate'
import { errorMessage, staff } from '../api'

interface Dashboard {
  needs_my_signature: Array<{ name: string; title: string; sender: string; expires_on: string | null }>
  waiting_for_others: number
  completed_this_month: number
  expiring_soon: number
}

const dashboard = createResource({ url: 'frappe_sign.api.staff.get_dashboard', auto: true })

async function signNow(envelope: string) {
  try {
    const { url } = await staff<{ url: string }>('my_signing_link', { envelope })
    window.location.href = url
  } catch (error) {
    toast.error(errorMessage(error))
  }
}
</script>

<template>
  <div class="mx-auto max-w-5xl space-y-6 p-6" data-testid="home">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-semibold text-ink-gray-9">{{ __('Signatures') }}</h1>
      <Button variant="solid" :label="__('Send a document')" :route="'/new'" />
    </div>
    <div v-if="dashboard.data" class="grid gap-4 sm:grid-cols-4">
      <div class="rounded-lg border border-outline-gray-1 bg-surface-base p-4">
        <p class="text-sm text-ink-gray-5">{{ __('Needs my signature') }}</p>
        <p class="mt-1 text-2xl font-semibold text-ink-gray-9">
          {{ (dashboard.data as Dashboard).needs_my_signature.length }}
        </p>
      </div>
      <RouterLink
        to="/envelopes?status=open"
        class="rounded-lg border border-outline-gray-1 bg-surface-base p-4 hover:bg-surface-gray-1"
      >
        <p class="text-sm text-ink-gray-5">{{ __('Waiting for others') }}</p>
        <p class="mt-1 text-2xl font-semibold text-ink-gray-9">
          {{ (dashboard.data as Dashboard).waiting_for_others }}
        </p>
      </RouterLink>
      <RouterLink
        to="/envelopes?status=Completed"
        class="rounded-lg border border-outline-gray-1 bg-surface-base p-4 hover:bg-surface-gray-1"
      >
        <p class="text-sm text-ink-gray-5">{{ __('Completed this month') }}</p>
        <p class="mt-1 text-2xl font-semibold text-ink-gray-9">
          {{ (dashboard.data as Dashboard).completed_this_month }}
        </p>
      </RouterLink>
      <div class="rounded-lg border border-outline-gray-1 bg-surface-base p-4">
        <p class="text-sm text-ink-gray-5">{{ __('Expiring in 3 days') }}</p>
        <p class="mt-1 text-2xl font-semibold text-ink-gray-9">
          {{ (dashboard.data as Dashboard).expiring_soon }}
        </p>
      </div>
    </div>
    <section
      v-if="dashboard.data && (dashboard.data as Dashboard).needs_my_signature.length"
      class="rounded-lg border border-outline-gray-1 bg-surface-base"
    >
      <h2 class="border-b border-outline-gray-1 px-4 py-3 text-base font-semibold text-ink-gray-8">
        {{ __('Needs my signature') }}
      </h2>
      <div
        v-for="row in (dashboard.data as Dashboard).needs_my_signature"
        :key="row.name"
        class="flex items-center justify-between px-4 py-3"
      >
        <span class="text-base text-ink-gray-9">{{ row.title }}</span>
        <Button variant="solid" :label="__('Sign now')" @click="signNow(row.name)" />
      </div>
    </section>
  </div>
</template>
