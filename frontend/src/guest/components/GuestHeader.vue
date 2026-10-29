<script setup lang="ts">
// White header with the company logo and name from the Sign Profile, then the document title.
import { computed } from 'vue'
import { readBoot } from '@/shared/boot'

// `company` is the request's company, used when the Sign Profile has no display name.
const props = defineProps<{ title?: string; company?: string | null }>()
const branding = readBoot().branding
const name = computed(() => branding.company || props.company || '')
const initial = computed(() => name.value.trim().charAt(0).toUpperCase())
</script>

<template>
  <header class="border-b border-outline-gray-1 bg-surface-base px-4 py-3" data-testid="guest-header">
    <div class="flex items-center gap-3">
      <img
        v-if="branding.logo"
        :src="branding.logo"
        alt=""
        class="size-8 shrink-0 rounded object-contain"
        data-testid="brand-logo"
      />
      <span
        v-else-if="name"
        class="flex size-8 shrink-0 items-center justify-center rounded text-sm font-semibold text-white"
        :style="{ background: 'var(--sign-brand)' }"
        aria-hidden="true"
      >
        {{ initial }}
      </span>
      <div class="min-w-0 flex-1">
        <p v-if="name" class="truncate text-sm font-medium text-ink-gray-9">
          {{ name }}
        </p>
        <p v-if="title" class="truncate text-sm text-ink-gray-6">{{ title }}</p>
      </div>
      <slot />
    </div>
  </header>
</template>
