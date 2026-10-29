<script setup lang="ts">
// The selected request: status, title, the main action for its state, the people as a step list
// and what happened, in plain words. The full page (U.5) adds the PDF.
import { Button, createResource, Dropdown } from 'frappe-ui'
import { computed, watch } from 'vue'
import { __ } from '@/shared/translate'
import ErrorState from '../components/ErrorState.vue'
import ListSkeleton from '../components/ListSkeleton.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { errorMessage } from '../api'
import { shortDate } from '../format'
import type { ActivityEvent } from './activity'
import ActivityTimeline from './ActivityTimeline.vue'
import PeopleSteps from './PeopleSteps.vue'
import type { Person } from './people'
import type { RequestRow } from './types'
import { useRequestActions } from './useRequestActions'
import { useRequestView } from './useRequestView'

interface Detail {
  envelope: Record<string, string | null>
  recipients: Person[]
  events: ActivityEvent[]
  chain_ok: boolean
  can_write: boolean
}

const props = defineProps<{ row: RequestRow }>()
const emit = defineEmits<{ changed: [] }>()

const detail = createResource({
  url: 'frappe_sign.api.staff.get_envelope',
  makeParams: () => ({ envelope: props.row.name }),
})
watch(
  () => props.row.name,
  () => void detail.fetch(),
  { immediate: true },
)
const data = computed(() =>
  (detail.data as Detail | null)?.envelope?.name === props.row.name ? (detail.data as Detail) : null,
)

const actions = useRequestActions(async () => {
  await detail.reload()
  emit('changed')
})

const canWrite = computed(() => Boolean(data.value?.can_write))
const view = useRequestView(
  computed(() =>
    data.value
      ? { ...data.value.envelope, name: props.row.name, status: props.row.status, can_write: canWrite.value }
      : null,
  ),
  actions,
)
const { primary, menu } = view

const sentLine = computed(() => {
  const sentOn = data.value?.envelope.sent_on
  const date = sentOn ? shortDate(sentOn.slice(0, 10)) : null
  if (!date) return __('Created by {0}', [props.row.sender_name])
  return __('Sent {0} by {1}', [date, props.row.sender_name])
})
</script>

<template>
  <section class="flex flex-col gap-5 p-5" :aria-label="__('Request preview')" data-testid="request-preview">
    <ErrorState v-if="detail.error" :message="errorMessage(detail.error)" @retry="detail.reload()" />
    <ListSkeleton v-else-if="!data" :rows="3" />
    <template v-else>
      <div class="flex flex-wrap items-start gap-3">
        <div class="flex min-w-48 flex-1 flex-col gap-1.5">
          <span class="flex items-center gap-2">
            <StatusBadge
              :status="row.status"
              :sealing="row.sealing_state ?? undefined"
              :sending="row.send_state ?? undefined"
            />
            <span class="text-sm text-ink-gray-6">{{ sentLine }}</span>
          </span>
          <h2 class="text-3xl font-semibold text-ink-gray-9">
            <RouterLink :to="`/requests/${row.name}`" class="hover:underline" data-testid="preview-title">{{
              row.title
            }}</RouterLink>
          </h2>
          <a
            v-if="row.reference_name"
            :href="`/app/${String(row.reference_doctype).toLowerCase().replace(/ /g, '-')}/${encodeURIComponent(row.reference_name)}`"
            class="text-sm text-ink-gray-7 underline decoration-outline-gray-3 underline-offset-2 hover:text-ink-gray-9"
            >{{ __(String(row.reference_doctype)) }} {{ row.reference_name }}</a
          >
        </div>
        <div class="flex items-center gap-2">
          <Button
            v-if="primary"
            variant="solid"
            :label="primary.label"
            :icon-left="primary.icon"
            :href="primary.href"
            :route="primary.route"
            data-testid="primary-action"
            @click="primary.run?.()"
          />
          <Dropdown v-if="menu.length" :options="menu" placement="right">
            <Button
              variant="outline"
              icon="lucide-ellipsis"
              :aria-label="__('More actions')"
              data-testid="more-actions"
            />
          </Dropdown>
        </div>
      </div>

      <PeopleSteps
        :people="data.recipients"
        :order="data.envelope.signing_order"
        :status="row.status"
        :can-act="canWrite"
        @remind="(person) => actions.remind(row.name, person.name)"
        @new-link="(person) => actions.newLink(row.name, person.name, person.email)"
      />

      <div class="border-t border-outline-gray-1 pt-4">
        <ActivityTimeline
          :key="row.name"
          :events="data.events"
          :people="data.recipients"
          :chain-ok="data.chain_ok"
        />
      </div>
    </template>
  </section>
</template>
