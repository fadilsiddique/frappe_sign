<script setup lang="ts">
// One segment per person, colored by their state, with the count beside it. The bar is decorative:
// the count and the title attribute say the same in words.
import { computed } from 'vue'
import { __ } from '@/shared/translate'

const props = defineProps<{
  people: Array<{ full_name?: string; name?: string; status: string }>
  signed: number
  total: number
  failed?: boolean
}>()

const TONE: Record<string, string> = {
  Signed: 'bg-[var(--sign-signed)]',
  Viewed: 'bg-[var(--sign-viewed)]',
  Declined: 'bg-[var(--sign-declined)]',
  Sent: 'bg-[var(--sign-waiting)]',
  Delegated: 'bg-[var(--sign-closed)]',
}
const WORD: Record<string, string> = {
  Signed: 'signed',
  Viewed: 'opened',
  Declined: 'declined',
  Sent: 'not opened yet',
  Pending: 'waiting for their turn',
  Delegated: 'passed on',
}

const segments = computed(() =>
  props.people.length
    ? props.people.map((person) => ({
        tone: TONE[person.status] ?? 'bg-[var(--sign-card-border)]',
        title: `${person.full_name ?? person.name}: ${__(WORD[person.status] ?? person.status)}`,
      }))
    : [{ tone: 'bg-[var(--sign-card-border)]', title: '' }],
)
</script>

<template>
  <span class="flex flex-col gap-1" data-testid="progress-bar">
    <span class="flex gap-0.5" aria-hidden="true">
      <span
        v-for="(segment, index) in segments"
        :key="index"
        class="h-1.5 min-w-2 flex-1 rounded-full"
        :class="segment.tone"
        :title="segment.title"
      />
    </span>
    <span class="sign-tabular text-xs text-ink-gray-7">{{ __('{0} of {1} signed', [signed, total]) }}</span>
  </span>
</template>
