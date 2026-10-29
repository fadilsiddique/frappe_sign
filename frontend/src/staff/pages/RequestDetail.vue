<script setup lang="ts">
// A request's own page (UX_PLAN "Request detail"): the PDF, with the signed values once there are
// any, beside the people as a step list, the main action for its state and what happened.
import { Button, createResource, Dropdown } from 'frappe-ui'
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import PdfViewer from '@/shared/components/PdfViewer.vue'
import type { PageMetric } from '@/shared/coords'
import { __ } from '@/shared/translate'
import { errorMessage, fetchPdf } from '../api'
import AppPageHeader from '../components/AppPageHeader.vue'
import ResourceState from '../components/ResourceState.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { shortDate } from '../format'
import type { ActivityEvent } from '../requests/activity'
import ActivityTimeline from '../requests/ActivityTimeline.vue'
import PeopleSteps from '../requests/PeopleSteps.vue'
import type { Person } from '../requests/people'
import { downloadUrl, useRequestActions } from '../requests/useRequestActions'
import { useRequestView } from '../requests/useRequestView'

const props = defineProps<{ id: string }>()

interface Detail {
  envelope: Record<string, string | null>
  recipients: Person[]
  events: ActivityEvent[]
  chain_ok: boolean
  can_write: boolean
}

const detail = createResource({
  url: 'frappe_sign.api.staff.get_envelope',
  params: { envelope: props.id },
  auto: true,
})
const data = computed(() => detail.data as Detail | null)
const envelope = computed(() => data.value?.envelope ?? {})
const actions = useRequestActions(() => detail.reload())
const { open, primary, menu } = useRequestView(
  computed(() =>
    data.value
      ? {
          ...data.value.envelope,
          name: props.id,
          status: String(data.value.envelope.status),
          can_write: data.value.can_write,
        }
      : null,
  ),
  actions,
)

const sentLine = computed(() => {
  const sentOn = envelope.value.sent_on
  const sender = envelope.value.sender
  if (!sentOn) return __('Not sent yet')
  return sender
    ? __('Sent {0} by {1}', [shortDate(sentOn.slice(0, 10)), sender])
    : __('Sent {0}', [shortDate(sentOn.slice(0, 10))])
})

// The PDF: the sealed one once there is one, else the original. It is read again when the seal lands.
const kind = computed(() =>
  envelope.value.signed_sha256 ? 'signed' : envelope.value.original_sha256 ? 'original' : null,
)
const pages = computed<PageMetric[]>(() => {
  try {
    return JSON.parse(String(envelope.value.page_metrics ?? '[]')) as PageMetric[]
  } catch {
    return []
  }
})
const pdf = shallowRef<ArrayBuffer | null>(null)
const pdfError = ref('')
watch(
  kind,
  async (value) => {
    pdf.value = null
    pdfError.value = ''
    if (!value) return
    try {
      pdf.value = await fetchPdf(downloadUrl(props.id, value))
    } catch (error) {
      pdfError.value = errorMessage(error)
    }
  },
  { immediate: true },
)

// The request changes as people sign and the seal job runs; refresh while it is open.
const timer = window.setInterval(() => {
  const busy =
    ['Queued', 'Sealing'].includes(String(envelope.value.sealing_state)) ||
    envelope.value.send_state === 'Queued'
  if (open.value || busy) void detail.reload()
}, 10_000)
onBeforeUnmount(() => window.clearInterval(timer))
</script>

<template>
  <AppPageHeader :title="String(envelope.title ?? __('Request'))" />
  <ResourceState :resource="detail" :rows="4">
    <div
      v-if="data"
      class="flex flex-col gap-4 p-4 lg:grid lg:grid-cols-[minmax(0,1fr)_400px] lg:items-start lg:p-5"
      data-testid="envelope-detail"
    >
      <aside
        class="flex flex-col gap-5 rounded-lg border border-outline-gray-1 bg-surface-base p-5 lg:sticky lg:top-5 lg:order-2"
        :aria-label="__('Request details')"
      >
        <div class="flex flex-col gap-1.5">
          <span class="flex flex-wrap items-center gap-2">
            <StatusBadge
              :status="String(envelope.status)"
              :sealing="String(envelope.sealing_state)"
              :sending="String(envelope.send_state)"
            />
            <span class="text-sm text-ink-gray-6">{{ sentLine }}</span>
          </span>
          <h2 class="text-xl font-semibold text-ink-gray-9 lg:sr-only" data-testid="detail-title">
            {{ envelope.title }}
          </h2>
          <a
            v-if="envelope.reference_name"
            :href="`/app/${String(envelope.reference_doctype).toLowerCase().replace(/ /g, '-')}/${encodeURIComponent(String(envelope.reference_name))}`"
            class="text-sm text-ink-gray-7 underline decoration-outline-gray-3 underline-offset-2 hover:text-ink-gray-9"
            >{{ __(String(envelope.reference_doctype)) }} {{ envelope.reference_name }}</a
          >
          <p v-if="envelope.send_error" class="text-sm text-ink-red-4">{{ envelope.send_error }}</p>
          <p v-if="envelope.void_reason" class="text-sm text-ink-gray-7">
            {{ __('Reason: {0}', [String(envelope.void_reason)]) }}
          </p>
        </div>

        <div v-if="primary || menu.length" class="flex items-center gap-2">
          <Button
            v-if="primary"
            class="flex-1"
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

        <PeopleSteps
          :people="data.recipients"
          :order="envelope.signing_order"
          :status="String(envelope.status)"
          :can-act="data.can_write"
          @remind="(person) => actions.remind(id, person.name)"
          @new-link="(person) => actions.newLink(id, person.name, person.email)"
        />

        <div class="border-t border-outline-gray-1 pt-4">
          <ActivityTimeline
            :events="data.events"
            :people="data.recipients"
            :chain-ok="data.chain_ok"
            :audit-head="envelope.audit_head"
          />
        </div>
      </aside>

      <section
        class="min-w-0 rounded-lg bg-surface-gray-2 p-3 lg:order-1 lg:p-5"
        :aria-label="__('Document')"
        data-testid="detail-pdf"
      >
        <p v-if="pdfError" class="py-10 text-center text-sm text-ink-red-4">{{ pdfError }}</p>
        <p v-else-if="!kind" class="py-10 text-center text-sm text-ink-gray-6">
          {{ __('The document is not ready yet.') }}
        </p>
        <PdfViewer v-else-if="pdf" :source="pdf" :pages="pages" @error="pdfError = errorMessage($event)" />
        <p v-else class="py-10 text-center text-sm text-ink-gray-6">{{ __('Loading the document') }}</p>
      </section>
    </div>
  </ResourceState>
</template>
