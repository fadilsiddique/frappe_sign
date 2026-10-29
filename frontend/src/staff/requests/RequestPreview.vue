<script setup lang="ts">
// The selected request: status, title, the main action for its state, the people as a step list
// and what happened, in plain words. The full page (U.5) adds the PDF.
import { Button, createResource, Dropdown, type DropdownItem } from 'frappe-ui'
import { computed, ref, watch } from 'vue'
import { __ } from '@/shared/translate'
import ErrorState from '../components/ErrorState.vue'
import ListSkeleton from '../components/ListSkeleton.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { errorMessage } from '../api'
import { shortDate } from '../format'
import { activityLines, type ActivityEvent } from './activity'
import type { RequestRow } from './types'
import { downloadUrl, useRequestActions } from './useRequestActions'

interface Person {
  name: string
  role_label: string
  kind: string
  full_name: string
  email: string
  status: string
  signed_on: string | null
  viewed_on: string | null
  decline_reason: string | null
}
interface Detail {
  envelope: Record<string, string | null>
  recipients: Person[]
  events: ActivityEvent[]
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

const open = computed(() => ['Sent', 'In Progress'].includes(props.row.status))
const canWrite = computed(() => Boolean(data.value?.can_write))
const nextNames = computed(
  () => new Set(props.row.people.filter((person) => person.next).map((person) => person.name)),
)
const showAudit = ref(false)
watch(
  () => props.row.name,
  () => (showAudit.value = false),
)

const sentLine = computed(() => {
  const sentOn = data.value?.envelope.sent_on
  const date = sentOn ? shortDate(sentOn.slice(0, 10)) : null
  if (!date) return __('Created by {0}', [props.row.sender_name])
  return __('Sent {0} by {1}', [date, props.row.sender_name])
})

const primary = computed(() => {
  if (!data.value || (!canWrite.value && props.row.status !== 'Completed')) return null
  if (props.row.status === 'Draft')
    return { label: __('Send'), icon: 'lucide-send', run: () => actions.send(props.row.name) }
  if (open.value)
    return { label: __('Remind'), icon: 'lucide-bell', run: () => actions.remind(props.row.name) }
  if (props.row.status === 'Completed')
    return {
      label: __('Download signed PDF'),
      icon: 'lucide-download',
      href: downloadUrl(props.row.name, 'signed'),
    }
  return { label: __('Send again'), icon: 'lucide-send', route: '/new' }
})

const menu = computed<DropdownItem[]>(() => {
  const envelope = data.value?.envelope
  if (!envelope) return []
  const items: DropdownItem[] = []
  const go = (url: string) => () => (window.location.href = url)
  if (envelope.original_sha256)
    items.push({
      label: __('Original PDF'),
      icon: 'lucide-file',
      onClick: go(downloadUrl(props.row.name, 'original')),
    })
  if (envelope.signed_sha256) {
    items.push({
      label: __('Certificate'),
      icon: 'lucide-award',
      onClick: go(downloadUrl(props.row.name, 'certificate')),
    })
    if (props.row.status !== 'Completed')
      items.push({
        label: __('Signed PDF'),
        icon: 'lucide-download',
        onClick: go(downloadUrl(props.row.name, 'signed')),
      })
  }
  if (envelope.sealing_state === 'Failed' && canWrite.value)
    items.push({
      label: __('Retry seal'),
      icon: 'lucide-rotate-cw',
      onClick: () => actions.retrySeal(props.row.name),
    })
  if (open.value && canWrite.value)
    items.push({
      label: __('Void request'),
      icon: 'lucide-ban',
      theme: 'red',
      onClick: () => actions.voidRequest(props.row.name),
    })
  return items
})

function state(person: Person): string {
  if (person.status === 'Signed')
    return person.signed_on ? __('Signed {0}', [shortDate(person.signed_on.slice(0, 10))]) : __('Signed')
  if (person.status === 'Declined')
    return person.decline_reason ? __('Declined: {0}', [person.decline_reason]) : __('Declined')
  if (person.status === 'Delegated') return __('Passed to someone else')
  if (person.status === 'Viewed') return __('Opened, not signed yet')
  if (person.status === 'Sent') return __('Not opened yet')
  return props.row.status === 'Draft' ? __('Not sent yet') : __('Waits for the people before')
}

function tone(person: Person): string {
  if (person.status === 'Signed') return 'bg-green-500 text-white ring-green-500'
  if (person.status === 'Declined') return 'bg-surface-red-2 text-ink-red-4 ring-red-500'
  if (nextNames.value.has(person.name)) return 'bg-surface-base text-ink-blue-6 ring-blue-500'
  return 'bg-surface-base text-ink-gray-6 ring-gray-300'
}

const lines = computed(() => (data.value ? activityLines(data.value.events, data.value.recipients) : []))
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

      <div class="flex flex-col gap-3">
        <h3 class="text-base font-semibold text-ink-gray-9">
          {{
            row.people.length > 1 && data.envelope.signing_order === 'Parallel'
              ? __('People, all at once')
              : __('People, in signing order')
          }}
        </h3>
        <ol class="flex flex-col">
          <li
            v-for="(person, index) in data.recipients"
            :key="person.name"
            class="relative flex gap-3 pb-4"
            data-testid="person"
          >
            <span
              v-if="index < data.recipients.length - 1"
              class="absolute start-[13px] top-8 bottom-0 w-0.5"
              :class="person.status === 'Signed' ? 'bg-green-500' : 'bg-surface-gray-3'"
              aria-hidden="true"
            />
            <span
              class="relative grid size-7 shrink-0 place-items-center rounded-full text-xs font-semibold ring-[1.5px] ring-inset"
              :class="tone(person)"
              aria-hidden="true"
            >
              <span v-if="person.status === 'Signed'" class="lucide-check size-3.5" />
              <template v-else>{{ index + 1 }}</template>
            </span>
            <span class="flex min-w-0 flex-1 flex-col gap-0.5 pt-0.5">
              <span class="flex flex-wrap items-baseline gap-x-2">
                <span class="text-base font-medium text-ink-gray-9">{{ person.full_name }}</span>
                <span class="text-sm text-ink-gray-6">{{ person.role_label }}</span>
              </span>
              <span
                class="text-sm"
                :class="person.status === 'Declined' ? 'text-ink-red-4' : 'text-ink-gray-6'"
                >{{ state(person) }}</span
              >
              <span v-if="open && canWrite && nextNames.has(person.name)" class="flex gap-1.5 pt-1.5">
                <Button
                  size="sm"
                  variant="outline"
                  :label="__('Remind')"
                  @click="actions.remind(row.name, person.name)"
                />
                <Button
                  size="sm"
                  variant="ghost"
                  :label="__('New link')"
                  @click="actions.newLink(row.name, person.name, person.email)"
                />
              </span>
            </span>
          </li>
        </ol>
      </div>

      <div class="flex flex-col gap-2 border-t border-outline-gray-1 pt-4">
        <div class="flex items-center gap-2">
          <h3 class="flex-1 text-base font-semibold text-ink-gray-9">{{ __('Activity') }}</h3>
          <Button
            variant="ghost"
            size="sm"
            :label="showAudit ? __('Hide audit details') : __('Show audit details')"
            @click="showAudit = !showAudit"
          />
        </div>
        <ul v-if="!showAudit" class="flex flex-col gap-1.5" data-testid="activity">
          <li v-for="line in lines" :key="line.seq" class="flex gap-3 text-sm">
            <span class="flex-1 text-ink-gray-9">{{ line.text }}</span>
            <span class="w-28 shrink-0 text-end text-ink-gray-6">{{ line.ago }}</span>
          </li>
        </ul>
        <ol v-else class="flex flex-col divide-y divide-outline-gray-1 text-sm" data-testid="audit">
          <li v-for="event in data.events" :key="event.seq" class="flex gap-2 py-1.5">
            <span class="w-8 shrink-0 text-ink-gray-5">#{{ event.seq }}</span>
            <span class="min-w-0 flex-1 text-ink-gray-8">
              <span class="font-medium">{{ __(event.event) }}</span>
              · {{ event.at }}<template v-if="event.actor"> · {{ event.actor }}</template
              ><template v-if="event.ip"> · {{ event.ip }}</template>
            </span>
          </li>
        </ol>
      </div>
    </template>
  </section>
</template>
