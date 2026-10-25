<script setup lang="ts">
import { FrappeUIProvider } from 'frappe-ui'
import { useRoute } from 'vue-router'
import { __ } from '@/shared/translate'

const route = useRoute()
const links = [
  { to: '/', label: 'Home' },
  { to: '/envelopes', label: 'Envelopes' },
  { to: '/new', label: 'Send' },
  { to: '/templates', label: 'Templates' },
]
</script>

<template>
  <FrappeUIProvider>
    <div class="flex h-full flex-col bg-surface-gray-1">
      <nav
        v-if="route.name !== 'Designer'"
        class="flex items-center gap-1 border-b border-outline-gray-1 bg-surface-base px-4 py-2"
      >
        <span class="me-4 font-semibold text-ink-gray-9">{{ __('Frappe Sign') }}</span>
        <RouterLink
          v-for="link in links"
          :key="link.to"
          :to="link.to"
          class="rounded px-3 py-1.5 text-sm text-ink-gray-7 hover:bg-surface-gray-2"
          active-class="bg-surface-gray-2 text-ink-gray-9"
          :exact-active-class="link.to === '/' ? 'bg-surface-gray-2 text-ink-gray-9' : undefined"
        >
          {{ __(link.label) }}
        </RouterLink>
        <a href="/app/sign-envelope" class="ms-auto text-sm text-ink-gray-5 hover:text-ink-gray-8">{{
          __('Desk')
        }}</a>
      </nav>
      <div class="min-h-0 flex-1 overflow-auto">
        <RouterView />
      </div>
    </div>
  </FrappeUIProvider>
</template>
