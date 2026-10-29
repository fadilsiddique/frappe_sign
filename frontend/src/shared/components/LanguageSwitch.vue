<script setup lang="ts">
// English / Arabic switch for the signer. Frappe reads the preferred_language cookie on the next
// request, so setting it and reloading is enough; the sender's choice stays the default.
import { computed } from 'vue'
import { readBoot } from '@/shared/boot'

const boot = readBoot()
const arabic = computed(() => boot.lang.startsWith('ar'))
// Each language is named in itself (never through __()), so it reads right in either language.
const target = computed(() =>
  arabic.value ? { code: 'en', name: 'English' } : { code: 'ar', name: 'العربية' },
)

function switchLanguage() {
  document.cookie = `preferred_language=${target.value.code}; path=/; max-age=31536000; SameSite=Lax`
  window.location.reload()
}
</script>

<template>
  <button
    type="button"
    class="shrink-0 rounded px-2 py-1 text-sm text-ink-gray-7 hover:bg-surface-gray-2 focus-visible:outline focus-visible:outline-2"
    :lang="target.code"
    data-testid="language-switch"
    @click="switchLanguage"
  >
    {{ target.name }}
  </button>
</template>
