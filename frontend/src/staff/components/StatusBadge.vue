<script setup lang="ts">
// A soft pill with a dot. The colors are the request state tokens (style.css), so a status looks
// the same here, in the progress bar and in the timeline.
import { computed } from 'vue'
import { requestStatus } from '../labels'

const props = defineProps<{ status: string; sealing?: string; sending?: string }>()
const view = computed(() => requestStatus(props.status, props.sealing, props.sending))

const TONE: Record<string, string> = {
  gray: 'bg-[var(--sign-closed-soft)] text-[var(--sign-closed)]',
  blue: 'bg-[var(--sign-viewed-soft)] text-[var(--sign-viewed)]',
  green: 'bg-[var(--sign-signed-soft)] text-[var(--sign-signed)]',
  amber: 'bg-[var(--sign-waiting-soft)] text-[var(--sign-waiting)]',
  red: 'bg-[var(--sign-declined-soft)] text-[var(--sign-declined)]',
}
</script>

<template>
  <span
    class="inline-flex h-6 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 text-sm font-medium"
    :class="TONE[view.theme]"
    :data-theme="view.theme"
    >{{ view.label }}</span
  >
</template>
