<script setup lang="ts">
import { Badge } from 'frappe-ui'
import { readBoot } from '@/shared/boot'

const boot = readBoot()
</script>

<template>
  <main class="flex h-full items-center justify-center bg-surface-gray-1 p-6">
    <section class="w-full max-w-md rounded-lg bg-surface-white p-6 text-center shadow">
      <h1 class="text-xl font-semibold text-ink-gray-9">{{ __('Frappe Sign') }}</h1>
      <p class="mt-2 text-base text-ink-gray-6">{{ __('The staff app is on its way.') }}</p>
      <Badge v-if="boot.user" class="mt-4" :label="boot.user" theme="gray" />
    </section>
  </main>
</template>
