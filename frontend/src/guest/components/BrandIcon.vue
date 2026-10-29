<script setup lang="ts">
// The few icons the guest page needs, drawn inline so the guest bundle does not load an icon set.
defineProps<{ name: 'check' | 'x' | 'clock' | 'ban' | 'alert' | 'more' | 'arrow-down' | 'shield' }>()
const paths: Record<string, string> = {
  check: 'M20 6 9 17l-5-5',
  x: 'M18 6 6 18M6 6l12 12',
  clock: 'M12 6v6l4 2M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z',
  ban: 'M4.9 4.9l14.2 14.2M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z',
  alert: 'M12 8v4M12 16h.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z',
  more: 'M12 5h.01M12 12h.01M12 19h.01',
  'arrow-down': 'M12 5v14M19 12l-7 7-7-7',
  shield:
    'M20 13c0 5-3.5 7.5-7.7 9a1 1 0 0 1-.6 0C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.2-2.7a1.2 1.2 0 0 1 1.6 0C14.5 3.8 17 5 19 5a1 1 0 0 1 1 1Z',
}
</script>

<template>
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    class="size-5 shrink-0"
  >
    <path :d="paths[name]" />
  </svg>
</template>
