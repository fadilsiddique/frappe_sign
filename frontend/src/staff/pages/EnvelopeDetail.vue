<script setup lang="ts">
// Request detail: people and their progress, audit timeline, actions (DESIGN 7.2). U.5 redesigns it.
import { Button, createResource, toast } from 'frappe-ui'
import { computed, onBeforeUnmount } from 'vue'
import { __ } from '@/shared/translate'
import { errorMessage, STAFF_API, staff } from '../api'
import AppPageHeader from '../components/AppPageHeader.vue'
import ResourceState from '../components/ResourceState.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { roleKindLabel } from '../labels'

const props = defineProps<{ id: string }>()

interface Detail {
  envelope: Record<string, string | null>
  recipients: Array<Record<string, string | number | null>>
  events: Array<{ seq: number; event: string; at: string; actor: string | null; ip: string | null }>
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
const open = computed(() => ['Sent', 'In Progress'].includes(String(envelope.value.status)))

async function act(method: string, args: Record<string, unknown>, done: string) {
  try {
    await staff(method, { envelope: props.id, ...args })
    toast.success(done)
    await detail.reload()
  } catch (error) {
    toast.error(errorMessage(error))
  }
}

function voidEnvelope() {
  const reason = window.prompt(__('Why are you voiding this request?'))
  if (reason) void act('void_envelope', { reason }, __('Voided'))
}

function resend(recipient: string, email: string) {
  const next = window.prompt(__('Send a new link to'), email)
  if (next) void act('resend', { recipient, email: next }, __('New link sent'))
}

function downloadUrl(kind: string) {
  return `/api/method/${STAFF_API}download?envelope=${encodeURIComponent(props.id)}&kind=${kind}`
}

// The envelope changes as signers act and the seal job runs; refresh while it is open.
const timer = window.setInterval(() => {
  const busy =
    ['Queued', 'Sealing'].includes(String(envelope.value.sealing_state)) ||
    envelope.value.send_state === 'Queued'
  if (open.value || busy) void detail.reload()
}, 10_000)
onBeforeUnmount(() => window.clearInterval(timer))
</script>

<template>
  <AppPageHeader :title="String(envelope.title ?? __('Request'))">
    <template v-if="data" #actions>
      <Button
        v-if="envelope.status === 'Draft' && envelope.send_state !== 'Queued' && data.can_write"
        variant="solid"
        :label="__('Send')"
        @click="act('send_envelope', {}, __('Sending'))"
      />
      <Button
        v-if="open && data.can_write"
        :label="__('Remind')"
        @click="act('remind', {}, __('Reminder sent'))"
      />
      <Button v-if="open && data.can_write" theme="red" :label="__('Void')" @click="voidEnvelope" />
      <Button
        v-if="envelope.sealing_state === 'Failed'"
        :label="__('Retry seal')"
        @click="act('retry_seal', {}, __('Sealing queued'))"
      />
      <a
        v-if="envelope.original_sha256"
        :href="downloadUrl('original')"
        class="rounded bg-surface-gray-2 px-3 py-1.5 text-sm text-ink-gray-8"
        >{{ __('Original PDF') }}</a
      >
      <a
        v-if="envelope.signed_sha256"
        :href="downloadUrl('signed')"
        class="rounded bg-surface-gray-2 px-3 py-1.5 text-sm text-ink-gray-8"
        >{{ __('Signed PDF') }}</a
      >
      <a
        v-if="envelope.signed_sha256"
        :href="downloadUrl('certificate')"
        class="rounded bg-surface-gray-2 px-3 py-1.5 text-sm text-ink-gray-8"
        >{{ __('Certificate') }}</a
      >
    </template>
  </AppPageHeader>
  <ResourceState :resource="detail" :rows="4">
    <div v-if="data" class="max-w-5xl space-y-6 p-4 sm:p-5" data-testid="envelope-detail">
      <div>
        <p class="text-sm text-ink-gray-6">{{ envelope.name }}</p>
        <div class="mt-2">
          <StatusBadge
            :status="String(envelope.status)"
            :sealing="String(envelope.sealing_state)"
            :sending="String(envelope.send_state)"
          />
        </div>
        <p v-if="envelope.send_error" class="mt-2 text-sm text-ink-red-4">{{ envelope.send_error }}</p>
      </div>
      <section class="rounded-lg border border-outline-gray-1 bg-surface-base">
        <h2 class="border-b border-outline-gray-1 px-4 py-3 text-base font-semibold text-ink-gray-8">
          {{ __('People') }}
        </h2>
        <div
          v-for="row in data.recipients"
          :key="String(row.name)"
          class="flex flex-wrap items-center justify-between gap-2 px-4 py-3"
          data-testid="recipient"
        >
          <div>
            <p class="text-base text-ink-gray-9">
              {{ row.full_name }}
              <span class="text-sm text-ink-gray-5"
                >· {{ row.role_label }} ({{ roleKindLabel(String(row.kind)) }})</span
              >
            </p>
            <p class="text-sm text-ink-gray-5">{{ row.email }}</p>
            <p v-if="row.decline_reason" class="text-sm text-ink-red-4">{{ row.decline_reason }}</p>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-sm text-ink-gray-7"
              >{{ __(String(row.status))
              }}<template v-if="row.signed_on"> · {{ row.signed_on }}</template></span
            >
            <Button
              v-if="open && data.can_write && ['Sent', 'Viewed'].includes(String(row.status))"
              size="sm"
              :label="__('New link')"
              @click="resend(String(row.name), String(row.email))"
            />
          </div>
        </div>
      </section>

      <section class="rounded-lg border border-outline-gray-1 bg-surface-base">
        <div class="flex items-center justify-between border-b border-outline-gray-1 px-4 py-3">
          <h2 class="text-base font-semibold text-ink-gray-8">{{ __('Audit trail') }}</h2>
          <span
            class="text-sm"
            :class="data.chain_ok ? 'font-medium text-ink-green-4' : 'font-medium text-ink-red-4'"
            data-testid="chain"
          >
            {{ data.chain_ok ? __('Hash chain verified') : __('Hash chain broken') }}
          </span>
        </div>
        <ol class="divide-y divide-outline-gray-1">
          <li
            v-for="event in data.events"
            :key="event.seq"
            class="grid grid-cols-[3rem_1fr] gap-2 px-4 py-2 text-sm"
            data-testid="event"
          >
            <span class="text-ink-gray-5">#{{ event.seq }}</span>
            <span>
              <span class="font-medium text-ink-gray-9">{{ __(event.event) }}</span>
              <span class="text-ink-gray-6">
                · {{ event.at }}<template v-if="event.actor"> · {{ event.actor }}</template
                ><template v-if="event.ip"> · {{ event.ip }}</template></span
              >
            </span>
          </li>
        </ol>
        <p
          v-if="envelope.audit_head"
          class="break-all border-t border-outline-gray-1 px-4 py-2 text-xs text-ink-gray-5"
        >
          {{ __('Audit head on the certificate: {0}', [String(envelope.audit_head)]) }}
        </p>
      </section>
    </div>
  </ResourceState>
</template>
