<script setup lang="ts">
// Filter pills with counts, search (after a short pause in typing) and the Filter row.
import { Button, FormControl, TextInput } from 'frappe-ui'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { __ } from '@/shared/translate'
import { emptyFilters, hasFilters } from './useRequests'
import type { FilterOptions, RequestCounts, RequestFilters, Tab } from './types'

const props = defineProps<{ counts: RequestCounts | null; options: FilterOptions }>()
const tab = defineModel<Tab>('tab', { required: true })
const filters = defineModel<RequestFilters>('filters', { required: true })

const PILLS: Array<{ tab: Tab; label: string }> = [
  { tab: 'open', label: 'Open' },
  { tab: 'completed', label: 'Completed' },
  { tab: 'closed', label: 'Closed' },
  { tab: 'all', label: 'All' },
]

const text = ref(filters.value.search)
let timer: number | undefined
watch(text, (value) => {
  window.clearTimeout(timer)
  timer = window.setTimeout(() => (filters.value = { ...filters.value, search: value.trim() }), 300)
})
// "Clear search" in the empty state resets the filters from outside.
watch(
  () => filters.value.search,
  (value) => {
    if (value !== text.value.trim()) text.value = value
  },
)
onBeforeUnmount(() => window.clearTimeout(timer))

const withoutSearch = (value: RequestFilters) => ({ ...value, search: '' })
const filtersSet = computed(() => hasFilters(withoutSearch(filters.value)))
const showFilters = ref(filtersSet.value)
const doctypeOptions = computed(() => [
  { label: __('Any document'), value: '' },
  ...props.options.doctypes.map((value) => ({ label: __(value), value })),
])
const senderOptions = computed(() => [
  { label: __('Anyone'), value: '' },
  ...props.options.senders.map((sender) => ({ label: sender.full_name, value: sender.name })),
])

function set(key: keyof RequestFilters, value: string | null | undefined) {
  filters.value = { ...filters.value, [key]: value ?? '' }
}
function clear() {
  filters.value = emptyFilters()
  text.value = ''
}
</script>

<template>
  <div class="flex flex-col gap-2 border-b border-outline-gray-1 bg-surface-base px-4 py-3 sm:px-5">
    <div class="flex flex-wrap items-center gap-2">
      <div class="flex flex-1 flex-wrap gap-1.5" role="group" :aria-label="__('Show')">
        <button
          v-for="pill in PILLS"
          :key="pill.tab"
          type="button"
          class="inline-flex h-7 items-center gap-1.5 rounded-full px-3 text-sm focus-visible:focus-ring"
          :class="
            tab === pill.tab
              ? 'bg-surface-gray-9 text-white'
              : 'text-ink-gray-7 ring-1 ring-inset ring-outline-gray-2 hover:bg-surface-gray-2'
          "
          :aria-pressed="tab === pill.tab"
          :data-testid="`pill-${pill.tab}`"
          @click="tab = pill.tab"
        >
          {{ __(pill.label) }}
          <span v-if="counts" class="opacity-80" :data-testid="`count-${pill.tab}`">{{
            counts[pill.tab]
          }}</span>
        </button>
      </div>
      <TextInput
        v-model="text"
        type="search"
        class="w-full sm:w-60"
        :placeholder="__('Search')"
        :aria-label="__('Search requests')"
        data-testid="search"
      >
        <template #prefix><span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" /></template>
      </TextInput>
      <Button
        icon-left="lucide-list-filter"
        :label="__('Filter')"
        :variant="filtersSet ? 'solid' : 'outline'"
        :aria-expanded="showFilters"
        data-testid="filter-toggle"
        @click="showFilters = !showFilters"
      />
    </div>
    <div v-if="showFilters" class="flex flex-wrap items-end gap-3" data-testid="filters">
      <FormControl
        v-if="options.doctypes.length"
        class="w-44"
        type="select"
        :label="__('Document type')"
        :model-value="filters.reference_doctype"
        :options="doctypeOptions"
        @update:model-value="set('reference_doctype', $event)"
      />
      <FormControl
        v-if="options.senders.length > 1"
        class="w-44"
        type="select"
        :label="__('Sent by')"
        :model-value="filters.sender"
        :options="senderOptions"
        @update:model-value="set('sender', $event)"
      />
      <FormControl
        class="w-40"
        type="date"
        :label="__('From')"
        :model-value="filters.date_from"
        @update:model-value="set('date_from', $event)"
      />
      <FormControl
        class="w-40"
        type="date"
        :label="__('To')"
        :model-value="filters.date_to"
        @update:model-value="set('date_to', $event)"
      />
      <Button v-if="filtersSet" variant="ghost" :label="__('Clear filters')" @click="clear" />
    </div>
  </div>
</template>
