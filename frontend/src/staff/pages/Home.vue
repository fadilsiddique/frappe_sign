<script setup lang="ts">
import { Button, createResource, toast } from 'frappe-ui'
import { __ } from '@/shared/translate'
import { errorMessage, staff } from '../api'
import AppPageHeader from '../components/AppPageHeader.vue'
import EmptyState from '../components/EmptyState.vue'
import HeaderAction from '../components/HeaderAction.vue'
import ResourceState from '../components/ResourceState.vue'

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
  <!-- U.3 replaces this page with the work queue and the setup panel (UX_PLAN "Home"). -->
  <AppPageHeader :title="__('Home')">
    <template #primary>
      <HeaderAction icon="lucide-plus" :label="__('New request')" route="/new" />
    </template>
  </AppPageHeader>
  <div class="max-w-5xl p-4 sm:p-5" data-testid="home">
    <ResourceState :resource="dashboard" :rows="3">
      <div v-if="dashboard.data" class="space-y-6">
        <dl class="grid gap-4 rounded-lg border border-outline-gray-1 bg-surface-base p-4 sm:grid-cols-4">
          <div>
            <dt class="text-sm text-ink-gray-6">{{ __('Needs your signature') }}</dt>
            <dd class="mt-1 text-3xl font-semibold text-ink-gray-9">
              {{ (dashboard.data as Dashboard).needs_my_signature.length }}
            </dd>
          </div>
          <RouterLink to="/envelopes?status=open" class="rounded hover:bg-surface-gray-1">
            <dt class="text-sm text-ink-gray-6">{{ __('Waiting on others') }}</dt>
            <dd class="mt-1 text-3xl font-semibold text-ink-gray-9">
              {{ (dashboard.data as Dashboard).waiting_for_others }}
            </dd>
          </RouterLink>
          <RouterLink to="/envelopes?status=Completed" class="rounded hover:bg-surface-gray-1">
            <dt class="text-sm text-ink-gray-6">{{ __('Completed this month') }}</dt>
            <dd class="mt-1 text-3xl font-semibold text-ink-gray-9">
              {{ (dashboard.data as Dashboard).completed_this_month }}
            </dd>
          </RouterLink>
          <div>
            <dt class="text-sm text-ink-gray-6">{{ __('Expiring in 3 days') }}</dt>
            <dd class="mt-1 text-3xl font-semibold text-ink-gray-9">
              {{ (dashboard.data as Dashboard).expiring_soon }}
            </dd>
          </div>
        </dl>
        <section id="to-sign" class="rounded-lg border border-outline-gray-1 bg-surface-base">
          <h2 class="border-b border-outline-gray-1 px-4 py-3 text-lg font-semibold text-ink-gray-9">
            {{ __('For you to sign') }}
          </h2>
          <div
            v-for="row in (dashboard.data as Dashboard).needs_my_signature"
            :key="row.name"
            class="flex items-center justify-between gap-3 border-b border-outline-gray-1 px-4 py-3 last:border-b-0"
          >
            <span class="min-w-0 truncate text-base text-ink-gray-9">{{ row.title }}</span>
            <Button variant="solid" :label="__('Sign')" @click="signNow(row.name)" />
          </div>
          <EmptyState
            v-if="!(dashboard.data as Dashboard).needs_my_signature.length"
            icon="lucide-pen-line"
            :title="__('Nothing to sign')"
            :text="__('When a colleague adds you as a signer, the document shows here.')"
          />
        </section>
      </div>
    </ResourceState>
  </div>
</template>
