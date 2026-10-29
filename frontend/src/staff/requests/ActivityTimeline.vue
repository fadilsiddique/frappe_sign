<script setup lang="ts">
// What happened, in plain words; the full audit trail (with the hash chain check) sits behind a toggle.
import { Button, Tooltip } from 'frappe-ui'
import { computed, ref } from 'vue'
import { __ } from '@/shared/translate'
import { activityLines, type ActivityEvent } from './activity'

// `chainOk` stays undefined when the caller does not know; Vue would cast a missing Boolean to false.
const props = withDefaults(
  defineProps<{
    events: ActivityEvent[]
    people: Array<{ name: string; full_name: string }>
    chainOk?: boolean
    auditHead?: string | null
  }>(),
  { chainOk: undefined, auditHead: null },
)

const showAudit = ref(false)
const lines = computed(() => activityLines(props.events, props.people))
</script>

<template>
  <div class="flex flex-col gap-2">
    <div class="flex items-center gap-2">
      <h3 class="flex-1 text-base font-semibold text-ink-gray-9">{{ __('Activity') }}</h3>
      <Tooltip
        v-if="chainOk !== undefined"
        :text="chainOk ? __('The audit trail is intact') : __('The audit trail was changed')"
      >
        <span
          class="grid size-7 place-items-center"
          :class="chainOk ? 'text-ink-green-4' : 'text-ink-red-4'"
          role="img"
          :aria-label="chainOk ? __('Verified') : __('Audit trail broken')"
          data-testid="chain"
        >
          <span :class="chainOk ? 'lucide-shield-check' : 'lucide-shield-alert'" class="size-4" />
        </span>
      </Tooltip>
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
    <template v-else>
      <ol class="flex flex-col divide-y divide-outline-gray-1 text-sm" data-testid="audit">
        <li v-for="event in events" :key="event.seq" class="flex gap-2 py-1.5" data-testid="event">
          <span class="w-8 shrink-0 text-ink-gray-5">#{{ event.seq }}</span>
          <span class="min-w-0 flex-1 text-ink-gray-8">
            <span class="font-medium">{{ __(event.event) }}</span>
            · {{ event.at }}<template v-if="event.actor"> · {{ event.actor }}</template
            ><template v-if="event.ip"> · {{ event.ip }}</template>
          </span>
        </li>
      </ol>
      <p v-if="auditHead" class="break-all text-xs text-ink-gray-6">
        {{ __('Audit head on the certificate: {0}', [auditHead]) }}
      </p>
    </template>
  </div>
</template>
