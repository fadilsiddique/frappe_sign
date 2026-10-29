<script setup lang="ts">
// "Waiting on others": the user's open requests, grouped by who to chase, a customer or supplier
// outside the company or a colleague. Each row opens the request.
import { computed } from 'vue'
import { __ } from '@/shared/translate'
import EmptyState from '../components/EmptyState.vue'
import OrderDots from '../components/OrderDots.vue'
import { shortDate } from '../format'
import { nextLine } from './lines'
import type { WaitingRow } from './types'

const props = defineProps<{ rows: WaitingRow[]; setupDone: boolean }>()

const groups = computed(() =>
  [
    { key: 'outside', label: __('Waiting on customers and suppliers') },
    { key: 'team', label: __('Waiting on your team') },
  ]
    .map((group) => ({ ...group, rows: props.rows.filter((row) => row.group === group.key) }))
    .filter((group) => group.rows.length),
)

function expiry(row: WaitingRow): string {
  if (!row.expires_on) return ''
  return row.expiring_soon ? __('Ends {0}', [shortDate(row.expires_on)]) : shortDate(row.expires_on)
}
</script>

<template>
  <section
    aria-labelledby="waiting-title"
    class="flex flex-col rounded-lg border border-outline-gray-1 bg-surface-base"
    data-testid="waiting"
  >
    <div class="flex items-center gap-2 px-4 pb-2.5 pt-3.5">
      <h2 id="waiting-title" class="flex-1 text-lg font-semibold text-ink-gray-9">
        {{ __('Waiting on others') }}
      </h2>
      <RouterLink
        v-if="rows.length"
        to="/envelopes"
        class="rounded text-sm text-ink-gray-7 hover:text-ink-gray-9 hover:underline focus-visible:focus-ring"
        >{{ __('See all sent') }}</RouterLink
      >
    </div>
    <EmptyState
      v-if="!rows.length"
      class="border-t border-outline-gray-1"
      :title="__('Nothing waiting')"
      :text="
        setupDone
          ? __('Requests you send show here until everyone has signed.')
          : __('Finish setting up, then send your first request.')
      "
    />
    <div v-for="group in groups" :key="group.key" class="flex flex-col" :data-group="group.key">
      <h3
        class="flex gap-2 border-t border-outline-gray-1 bg-surface-gray-1 px-4 py-2 text-sm font-medium text-ink-gray-8"
      >
        {{ group.label }}<span class="font-normal text-ink-gray-6">{{ group.rows.length }}</span>
      </h3>
      <RouterLink
        v-for="row in group.rows"
        :key="row.name"
        :to="`/envelopes/${row.name}`"
        class="flex items-center gap-3.5 border-t border-outline-gray-1 px-4 py-3 hover:bg-surface-gray-1 focus-visible:focus-ring"
        data-testid="waiting-row"
      >
        <span class="flex min-w-0 flex-1 flex-col gap-0.5">
          <span class="truncate text-base font-medium text-ink-gray-9">{{ row.title }}</span>
          <span class="truncate text-sm text-ink-gray-6">{{ nextLine(row) }}</span>
        </span>
        <span class="hidden w-36 shrink-0 items-center gap-2 sm:flex">
          <OrderDots :people="row.people" />
          <span class="text-sm text-ink-gray-7">{{ __('{0} of {1}', [row.signed, row.total]) }}</span>
        </span>
        <span
          class="w-24 shrink-0 text-end text-sm"
          :class="row.expiring_soon ? 'font-medium text-ink-amber-6' : 'text-ink-gray-6'"
          >{{ expiry(row) }}</span
        >
        <span
          class="lucide-chevron-right size-4 shrink-0 text-ink-gray-5 rtl:rotate-180"
          aria-hidden="true"
        />
      </RouterLink>
    </div>
  </section>
</template>
