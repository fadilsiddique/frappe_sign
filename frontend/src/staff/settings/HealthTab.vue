<script setup lang="ts">
// What to know before a customer finds out: seal end dates, timestamp servers, the sealing
// queue, failed automatic sends and the sender's mail records (services/health.py).
import { Button, createResource } from 'frappe-ui'
import { computed } from 'vue'
import { __ } from '@/shared/translate'
import { STAFF_API } from '../api'
import ResourceState from '../components/ResourceState.vue'
import { HEALTH_ICON, type HealthReport } from './types'

const health = createResource({ url: `${STAFF_API}get_health`, auto: true })
const report = computed(() => health.data as HealthReport | null)

function check() {
  health.update({ params: { refresh: 1 } })
  health.reload()
}
</script>

<template>
  <div class="flex max-w-2xl flex-col gap-4" data-testid="tab-health">
    <ResourceState :resource="health" :is-empty="() => false">
      <template v-if="report">
        <div class="flex items-center justify-between gap-3">
          <p class="text-base text-ink-gray-8" data-testid="health-summary">
            {{
              report.status === 'ok' || report.status === 'info'
                ? __('Everything looks fine.')
                : report.status === 'warn'
                  ? __('Something needs a look.')
                  : __('Something needs fixing now.')
            }}
          </p>
          <Button
            :label="__('Check again')"
            :loading="health.loading"
            data-testid="health-refresh"
            @click="check"
          />
        </div>
        <ul class="flex flex-col divide-y divide-outline-gray-1 rounded-lg bg-surface-base">
          <li
            v-for="item in report.checks"
            :key="item.key"
            class="flex gap-3 p-4"
            :data-testid="`health-${item.key}`"
            :data-status="item.status"
          >
            <span
              :class="[HEALTH_ICON[item.status].icon, HEALTH_ICON[item.status].color]"
              class="mt-0.5 size-5 shrink-0"
              role="img"
              :aria-label="__(HEALTH_ICON[item.status].label)"
            />
            <div class="min-w-0 flex-1">
              <p class="text-base font-medium text-ink-gray-9">{{ item.title }}</p>
              <p class="text-sm text-ink-gray-7">{{ item.detail }}</p>
              <p v-if="item.hint" class="mt-1 text-sm text-ink-gray-7">{{ item.hint }}</p>
            </div>
          </li>
        </ul>
      </template>
    </ResourceState>
  </div>
</template>
