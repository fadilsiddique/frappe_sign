<script setup lang="ts">
import { createListResource } from 'frappe-ui'
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { __ } from '@/shared/translate'
import StatusBadge from '../components/StatusBadge.vue'

const route = useRoute()
const FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'open', label: 'Waiting' },
  { value: 'Draft', label: 'Draft' },
  { value: 'Completed', label: 'Completed' },
  { value: 'closed', label: 'Declined, voided or expired' },
]
const status = ref(String(route.query.status ?? 'all'))
const filters = computed(() => {
  if (status.value === 'open') return { status: ['in', ['Sent', 'In Progress']] }
  if (status.value === 'closed') return { status: ['in', ['Declined', 'Voided', 'Expired']] }
  if (status.value === 'all') return {}
  return { status: status.value }
})
const envelopes = createListResource({
  doctype: 'Sign Envelope',
  fields: [
    'name',
    'title',
    'status',
    'sealing_state',
    'send_state',
    'sent_on',
    'modified',
    'reference_doctype',
    'reference_name',
  ],
  orderBy: 'modified desc',
  pageLength: 50,
  filters: filters.value,
  auto: true,
})
watch(filters, (next) => {
  envelopes.update({ filters: next })
  void envelopes.reload()
})
</script>

<template>
  <div class="mx-auto max-w-5xl p-6" data-testid="envelopes">
    <h1 class="mb-4 text-xl font-semibold text-ink-gray-9">{{ __('Envelopes') }}</h1>
    <div class="mb-3 flex flex-wrap gap-1">
      <button
        v-for="filter in FILTERS"
        :key="filter.value"
        type="button"
        class="rounded px-3 py-1 text-sm"
        :class="
          status === filter.value
            ? 'bg-surface-gray-4 text-ink-gray-9'
            : 'text-ink-gray-6 hover:bg-surface-gray-2'
        "
        @click="status = filter.value"
      >
        {{ __(filter.label) }}
      </button>
    </div>
    <div class="divide-y divide-outline-gray-1 rounded-lg border border-outline-gray-1 bg-surface-base">
      <RouterLink
        v-for="row in envelopes.data ?? []"
        :key="row.name"
        :to="`/envelopes/${row.name}`"
        class="grid grid-cols-[1fr_auto] items-center gap-2 px-4 py-3 hover:bg-surface-gray-1"
      >
        <span class="min-w-0">
          <span class="block truncate text-base text-ink-gray-9">{{ row.title }}</span>
          <span class="block text-sm text-ink-gray-5">
            {{ row.name
            }}<template v-if="row.reference_name">
              · {{ row.reference_doctype }} {{ row.reference_name }}</template
            >
          </span>
        </span>
        <StatusBadge :status="row.status" :sealing="row.sealing_state" :sending="row.send_state" />
      </RouterLink>
      <p v-if="envelopes.data && !envelopes.data.length" class="p-6 text-center text-ink-gray-5">
        {{ __('Nothing here.') }}
      </p>
    </div>
  </div>
</template>
