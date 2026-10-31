<script setup lang="ts">
// The requests grouped by who to chase. One row is selected; the arrow keys move the selection.
// Lanes: the progress and expiry columns have fixed widths so they line up from row to row.
import { computed } from 'vue'
import { __ } from '@/shared/translate'
import ProgressBar from '../components/ProgressBar.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { shortDate } from '../format'
import { GROUPS, requestLine } from './lines'
import type { RequestRow } from './types'

const props = defineProps<{ rows: RequestRow[]; selected: string | null }>()
const emit = defineEmits<{ select: [row: RequestRow] }>()

const groups = computed(() =>
  GROUPS.map((group) => ({ ...group, rows: props.rows.filter((row) => row.group === group.key) })).filter(
    (group) => group.rows.length,
  ),
)

function expiry(row: RequestRow): string {
  if (!row.expires_on || row.group === 'done' || row.group === 'closed' || row.group === 'draft') return ''
  return row.expiring_soon ? __('Ends {0}', [shortDate(row.expires_on)]) : shortDate(row.expires_on)
}

// Keyboard order is the order on screen: group by group.
function move(event: KeyboardEvent, step: number) {
  const ordered = groups.value.flatMap((group) => group.rows)
  const index = ordered.findIndex((row) => row.name === props.selected)
  const next = ordered[Math.min(ordered.length - 1, Math.max(0, index + step))]
  if (!next) return
  event.preventDefault()
  emit('select', next)
  const list = event.currentTarget as HTMLElement
  list.querySelector<HTMLElement>(`[data-row="${CSS.escape(next.name)}"]`)?.focus()
}
</script>

<template>
  <div
    role="listbox"
    :aria-label="__('Requests')"
    class="flex flex-col gap-4 p-3 sm:p-4"
    data-testid="request-list"
    @keydown.down="move($event, 1)"
    @keydown.up="move($event, -1)"
  >
    <div
      v-for="group in groups"
      :key="group.key"
      class="sign-card flex flex-col overflow-hidden"
      role="group"
      :aria-label="__(group.label)"
      :data-group="group.key"
    >
      <h3
        aria-hidden="true"
        class="flex items-center gap-2 border-b border-outline-gray-1 bg-surface-gray-1 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-ink-gray-7 sm:px-5"
      >
        {{ __(group.label) }}<span class="sign-tabular rounded-full bg-surface-base px-1.5 font-medium text-ink-gray-7 ring-1 ring-inset ring-outline-gray-2">{{ group.rows.length }}</span>
      </h3>
      <button
        v-for="row in group.rows"
        :key="row.name"
        type="button"
        role="option"
        class="relative flex items-center gap-3 border-b border-outline-gray-1 px-4 py-3.5 text-start transition-colors last:border-b-0 hover:bg-[var(--sign-accent-50)]/60 focus-visible:focus-ring sm:px-5"
        :class="selected === row.name ? 'bg-[var(--sign-accent-50)]' : ''"
        :aria-selected="selected === row.name"
        :data-row="row.name"
        data-testid="request-row"
        @click="emit('select', row)"
      >
        <span
          v-if="selected === row.name"
          class="absolute inset-y-0 start-0 w-[3px] bg-[var(--sign-accent-600)]"
          aria-hidden="true"
        />
        <span class="flex min-w-0 flex-1 flex-col gap-0.5">
          <span class="truncate text-base font-medium text-ink-gray-9">{{ row.title }}</span>
          <span class="truncate text-sm text-ink-gray-6">{{ requestLine(row) }}</span>
        </span>
        <span class="flex w-[112px] shrink-0 flex-col items-stretch gap-1" data-testid="lane-progress">
          <span v-if="row.group === 'draft'" class="text-sm text-ink-gray-6">{{ __('Draft') }}</span>
          <StatusBadge
            v-else-if="row.group === 'closed'"
            class="self-start"
            :status="row.status"
            :sealing="row.sealing_state ?? undefined"
          />
          <ProgressBar v-else :people="row.people" :signed="row.signed" :total="row.total" />
          <span
            class="text-xs"
            :class="row.expiring_soon ? 'font-medium text-[var(--sign-waiting)]' : 'text-ink-gray-6'"
            >{{ expiry(row) }}</span
          >
        </span>
      </button>
    </div>
  </div>
</template>
