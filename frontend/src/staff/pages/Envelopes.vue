<script setup lang="ts">
import { createListResource } from 'frappe-ui'
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { __ } from '@/shared/translate'
import AppPageHeader from '../components/AppPageHeader.vue'
import EmptyState from '../components/EmptyState.vue'
import HeaderAction from '../components/HeaderAction.vue'
import ResourceState from '../components/ResourceState.vue'
import StatusBadge from '../components/StatusBadge.vue'

const route = useRoute()
const FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'open', label: 'Waiting' },
  { value: 'Draft', label: 'Drafts' },
  { value: 'Completed', label: 'Completed' },
  { value: 'closed', label: 'Closed' },
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
  <AppPageHeader :title="__('Sent')">
    <template #primary>
      <HeaderAction icon="lucide-plus" :label="__('New request')" route="/new" />
    </template>
  </AppPageHeader>
  <div class="max-w-5xl p-4 sm:p-5" data-testid="envelopes">
    <div class="mb-3 flex flex-wrap gap-1" role="group" :aria-label="__('Show')">
      <button
        v-for="filter in FILTERS"
        :key="filter.value"
        type="button"
        class="rounded px-3 py-1 text-base"
        :aria-pressed="status === filter.value"
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
    <div class="rounded-lg border border-outline-gray-1 bg-surface-base">
      <ResourceState :resource="envelopes">
        <template #empty>
          <EmptyState
            v-if="status === 'all'"
            icon="lucide-send"
            :title="__('No requests yet')"
            :text="__('Send one from a Quotation in Desk, or upload a PDF here.')"
          />
          <EmptyState
            v-else
            icon="lucide-inbox"
            :title="__('Nothing here')"
            :text="__('Look in All for every request.')"
          />
        </template>
        <div class="divide-y divide-outline-gray-1">
          <RouterLink
            v-for="row in envelopes.data ?? []"
            :key="row.name"
            :to="`/envelopes/${row.name}`"
            class="grid grid-cols-[1fr_auto] items-center gap-2 px-4 py-3 hover:bg-surface-gray-1"
          >
            <span class="min-w-0">
              <span class="block truncate text-base text-ink-gray-9">{{ row.title }}</span>
              <span class="block text-sm text-ink-gray-6">
                <template v-if="row.reference_name"
                  >{{ row.reference_doctype }} {{ row.reference_name }}</template
                >
                <template v-else>{{ row.name }}</template>
              </span>
            </span>
            <StatusBadge :status="row.status" :sealing="row.sealing_state" :sending="row.send_state" />
          </RouterLink>
        </div>
      </ResourceState>
    </div>
  </div>
</template>
