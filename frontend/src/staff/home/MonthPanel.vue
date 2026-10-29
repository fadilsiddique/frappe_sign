<script setup lang="ts">
// The side panel once setup is done: this month in figures, what expires soon, and the seal.
import { Button, toast } from 'frappe-ui'
import { computed, ref } from 'vue'
import { __ } from '@/shared/translate'
import { errorMessage, staff } from '../api'
import { monthName, shortDate } from '../format'
import { notSignedYet } from './lines'
import type { Dashboard, SetupStatus, WaitingRow } from './types'

const props = defineProps<{ dashboard: Dashboard; setup: SetupStatus | null }>()
const emit = defineEmits<{ changed: [] }>()

const expiring = computed(() => props.dashboard.waiting.filter((row) => row.expiring_soon))
const seal = computed(() => props.setup?.steps.find((step) => step.key === 'seal')?.facts ?? null)
const reminding = ref<string | null>(null)

async function remind(row: WaitingRow) {
  reminding.value = row.name
  try {
    await staff('remind', { envelope: row.name })
    toast.success(__('Reminder sent'))
    emit('changed')
  } catch (error) {
    toast.error(errorMessage(error))
  } finally {
    reminding.value = null
  }
}
</script>

<template>
  <section
    aria-labelledby="month-title"
    class="flex flex-col gap-3 rounded-lg border border-outline-gray-1 bg-surface-base p-4"
    data-testid="month"
  >
    <h2 id="month-title" class="text-lg font-semibold text-ink-gray-9">{{ monthName() }}</h2>
    <dl class="grid grid-cols-3 gap-2">
      <div>
        <dt class="text-sm text-ink-gray-6">{{ __('Completed') }}</dt>
        <dd class="text-3xl font-semibold text-ink-gray-9">{{ dashboard.month.completed }}</dd>
      </div>
      <div>
        <dt class="text-sm text-ink-gray-6">{{ __('Waiting') }}</dt>
        <dd class="text-3xl font-semibold text-ink-gray-9">{{ dashboard.month.waiting }}</dd>
      </div>
      <div>
        <dt class="text-sm text-ink-gray-6">{{ __('Declined') }}</dt>
        <dd class="text-3xl font-semibold text-ink-gray-9">{{ dashboard.month.declined }}</dd>
      </div>
    </dl>
  </section>

  <section
    v-if="expiring.length"
    aria-labelledby="expiring-title"
    class="flex flex-col gap-3 rounded-lg border border-outline-gray-1 bg-surface-base p-4"
    data-testid="expiring"
  >
    <h2 id="expiring-title" class="text-lg font-semibold text-ink-gray-9">{{ __('Expiring soon') }}</h2>
    <div v-for="row in expiring" :key="row.name" class="flex items-start gap-2.5">
      <span
        class="grid size-6 shrink-0 place-items-center rounded-full bg-surface-amber-2 text-ink-amber-6"
        aria-hidden="true"
      >
        <span class="lucide-clock size-3.5" />
      </span>
      <span class="flex min-w-0 flex-1 flex-col gap-0.5">
        <RouterLink
          :to="`/requests/${row.name}`"
          class="truncate text-base font-medium text-ink-gray-9 hover:underline"
        >
          {{ row.title }}
        </RouterLink>
        <span class="text-sm text-ink-gray-6">
          {{ __('Expires {0}.', [shortDate(row.expires_on ?? '')]) }} {{ notSignedYet(row) }}
        </span>
        <Button
          class="mt-1.5 self-start"
          variant="outline"
          icon-left="lucide-bell"
          :label="__('Remind')"
          :loading="reminding === row.name"
          @click="remind(row)"
        />
      </span>
    </div>
  </section>

  <p
    v-if="seal?.valid_to && !seal.expired"
    class="flex items-center gap-2 px-1 text-sm text-ink-gray-6"
    data-testid="seal-status"
  >
    <span class="lucide-shield-check size-4 text-ink-green-6" aria-hidden="true" />
    {{ __('Company seal valid until {0}', [shortDate(String(seal.valid_to))]) }}
  </p>
</template>
