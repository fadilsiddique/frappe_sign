<script setup lang="ts">
// The requests grouped by who to chase. One row is selected; the arrow keys move the selection.
// Lanes: the progress and expiry columns have fixed widths so they line up from row to row.
import { computed } from 'vue'
import { __ } from '@/shared/translate'
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
    class="flex flex-col bg-surface-base"
    data-testid="request-list"
    @keydown.down="move($event, 1)"
    @keydown.up="move($event, -1)"
  >
    <div v-for="group in groups" :key="group.key" class="flex flex-col" :data-group="group.key">
      <h3
        class="flex gap-2 border-b border-outline-gray-1 bg-surface-gray-1 px-4 py-2 text-sm font-medium text-ink-gray-8 sm:px-5"
      >
        {{ __(group.label) }}<span class="font-normal text-ink-gray-6">{{ group.rows.length }}</span>
      </h3>
      <button
        v-for="row in group.rows"
        :key="row.name"
        type="button"
        role="option"
        class="relative flex items-center gap-3 border-b border-outline-gray-1 px-4 py-3 text-start hover:bg-surface-gray-1 focus-visible:focus-ring sm:px-5"
        :class="selected === row.name ? 'bg-surface-gray-2' : ''"
        :aria-selected="selected === row.name"
        :data-row="row.name"
        data-testid="request-row"
        @click="emit('select', row)"
      >
        <span
          v-if="selected === row.name"
          class="absolute inset-y-0 start-0 w-[3px] bg-surface-gray-9"
          aria-hidden="true"
        />
        <span class="flex min-w-0 flex-1 flex-col gap-0.5">
          <span class="truncate text-base font-medium text-ink-gray-9">{{ row.title }}</span>
          <span class="truncate text-sm text-ink-gray-6">{{ requestLine(row) }}</span>
        </span>
        <span class="flex w-[76px] shrink-0 flex-col items-end gap-0.5" data-testid="lane-progress">
          <span v-if="row.group === 'draft'" class="text-sm text-ink-gray-6">{{ __('Draft') }}</span>
          <StatusBadge
            v-else-if="row.group === 'closed'"
            :status="row.status"
            :sealing="row.sealing_state ?? undefined"
          />
          <span v-else class="text-sm text-ink-gray-8">{{ __('{0} of {1}', [row.signed, row.total]) }}</span>
          <span
            class="text-xs"
            :class="row.expiring_soon ? 'font-medium text-ink-amber-6' : 'text-ink-gray-6'"
            >{{ expiry(row) }}</span
          >
        </span>
      </button>
    </div>
  </div>
</template>
