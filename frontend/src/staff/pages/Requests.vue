<script setup lang="ts">
// Sent (UX_PLAN "Sent", Direction B): the requests grouped by who to chase, beside a preview of the
// selected one. Tab, filters and selection live in the address, so Back and shared links work.
// Without room for a preview (phones, narrow windows) a tap opens the request's own page.
import { Button } from 'frappe-ui'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { __ } from '@/shared/translate'
import AppPageHeader from '../components/AppPageHeader.vue'
import EmptyState from '../components/EmptyState.vue'
import HeaderAction from '../components/HeaderAction.vue'
import ResourceState from '../components/ResourceState.vue'
import RequestList from '../requests/RequestList.vue'
import RequestPreview from '../requests/RequestPreview.vue'
import RequestsToolbar from '../requests/RequestsToolbar.vue'
import type { RequestFilters, RequestRow, Tab } from '../requests/types'
import { emptyFilters, hasFilters, useRequests } from '../requests/useRequests'
import { useMatchMedia, WIDE_QUERY } from '../shell/useIsMobile'

const TABS: Tab[] = ['open', 'completed', 'closed', 'all']
const route = useRoute()
const router = useRouter()
const wide = useMatchMedia(WIDE_QUERY)

const one = (value: unknown): string => (typeof value === 'string' ? value : '')
const tab = ref<Tab>(TABS.find((value) => value === route.query.status) ?? 'open')
const filters = ref<RequestFilters>({
  search: one(route.query.q),
  reference_doctype: one(route.query.doctype),
  sender: one(route.query.sender),
  date_from: one(route.query.from),
  date_to: one(route.query.to),
})
const selectedName = ref(one(route.query.open))

const list = useRequests(tab, filters)
const selected = computed<RequestRow | null>(() => {
  const rows = list.data ?? []
  return rows.find((row) => row.name === selectedName.value) ?? (wide.value ? (rows[0] ?? null) : null)
})

// Keep the address in step with the page, without adding history entries.
watch([tab, filters, selectedName], () => {
  const query: Record<string, string> = {}
  if (tab.value !== 'open') query.status = tab.value
  if (filters.value.search) query.q = filters.value.search
  if (filters.value.reference_doctype) query.doctype = filters.value.reference_doctype
  if (filters.value.sender) query.sender = filters.value.sender
  if (filters.value.date_from) query.from = filters.value.date_from
  if (filters.value.date_to) query.to = filters.value.date_to
  if (selectedName.value && wide.value) query.open = selectedName.value
  void router.replace({ query })
})

function select(row: RequestRow) {
  if (wide.value) selectedName.value = row.name
  else void router.push(`/requests/${row.name}`)
}

const filtered = computed(() => hasFilters(filters.value))
function clearAll() {
  filters.value = emptyFilters()
}
</script>

<template>
  <AppPageHeader :title="__('Sent')">
    <template #primary>
      <HeaderAction icon="lucide-plus" :label="__('New request')" route="/new" />
    </template>
  </AppPageHeader>
  <div class="flex flex-col" data-testid="requests">
    <RequestsToolbar
      v-model:tab="tab"
      v-model:filters="filters"
      :counts="list.counts"
      :options="list.options"
    />
    <div class="flex items-start">
      <div
        class="min-w-0 flex-1 border-outline-gray-1 lg:w-[420px] lg:flex-none lg:border-e"
        :class="{ 'lg:max-w-[420px]': true }"
      >
        <ResourceState :resource="list" :rows="6">
          <template #empty>
            <EmptyState
              v-if="filtered"
              icon="lucide-search-x"
              :title="__('No requests match')"
              :text="__('Try other words, or clear the filters.')"
            >
              <template #action>
                <Button :label="__('Clear search')" @click="clearAll" />
              </template>
            </EmptyState>
            <EmptyState
              v-else-if="list.counts && list.counts.all === 0"
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
          <RequestList :rows="list.data ?? []" :selected="selected?.name ?? null" @select="select" />
          <div v-if="list.hasMore" class="flex justify-center border-t border-outline-gray-1 p-3">
            <Button
              :label="__('Load more')"
              :loading="list.loadingMore"
              data-testid="load-more"
              @click="list.more()"
            />
          </div>
        </ResourceState>
      </div>
      <div v-if="wide" class="sticky top-0 min-w-0 flex-1 self-start">
        <RequestPreview v-if="selected" :key="selected.name" :row="selected" @changed="list.reload()" />
      </div>
    </div>
  </div>
</template>
