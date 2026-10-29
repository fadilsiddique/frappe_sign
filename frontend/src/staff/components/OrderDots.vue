<script setup lang="ts">
// People in signing order as numbered dots: green with a tick once signed, blue for who is next.
// Decorative: the row says the same in words ("Next: ...", "1 of 2").
defineProps<{ people: Array<{ status: string; next: boolean }> }>()

function tone(person: { status: string; next: boolean }): string {
  if (person.status === 'Signed') return 'bg-green-500 text-ink-white ring-green-500'
  if (person.next) return 'bg-surface-base text-ink-blue-6 ring-blue-500'
  return 'bg-surface-base text-ink-gray-6 ring-gray-300'
}
</script>

<template>
  <span class="flex items-center gap-1" aria-hidden="true" data-testid="order-dots">
    <span
      v-for="(person, index) in people"
      :key="index"
      class="grid size-5 shrink-0 place-items-center rounded-full text-2xs font-semibold ring-[1.5px] ring-inset"
      :class="tone(person)"
      :data-state="person.status === 'Signed' ? 'signed' : person.next ? 'next' : 'later'"
    >
      <span v-if="person.status === 'Signed'" class="lucide-check size-3" />
      <template v-else>{{ index + 1 }}</template>
    </span>
  </span>
</template>
