<script setup lang="ts">
// Home (UX_PLAN "Home", Direction B): the work queue beside a side panel. Until setup is done the
// side panel walks through it; then it shows the month, what expires soon and the seal.
import { computed } from 'vue'
import { __ } from '@/shared/translate'
import HeaderAction from '../components/HeaderAction.vue'
import AppPageHeader from '../components/AppPageHeader.vue'
import ResourceState from '../components/ResourceState.vue'
import MonthPanel from '../home/MonthPanel.vue'
import { useDashboard, useSetupStatus } from '../home/resources'
import SetupPanel from '../home/SetupPanel.vue'
import ToSignPanel from '../home/ToSignPanel.vue'
import type { Dashboard, SetupStatus } from '../home/types'
import WaitingPanel from '../home/WaitingPanel.vue'

const dashboard = useDashboard()
const setup = useSetupStatus()

const data = computed(() => dashboard.data as Dashboard | null)
const status = computed(() => setup.data as SetupStatus | null)
// Until the status loads, assume setup is done: an established site should not flash the steps.
const setupDone = computed(() => status.value?.complete ?? true)
</script>

<template>
  <AppPageHeader :title="__('Home')">
    <template #primary>
      <HeaderAction
        icon="lucide-plus"
        :label="__('New request')"
        route="/new"
        :variant="setupDone ? 'solid' : 'outline'"
      />
    </template>
  </AppPageHeader>
  <div class="flex flex-wrap items-start gap-5 p-4 sm:p-5" data-testid="home">
    <main class="flex min-w-0 flex-[999_1_520px] flex-col gap-5">
      <ResourceState :resource="dashboard" :rows="4">
        <div v-if="data" class="flex flex-col gap-5">
          <ToSignPanel :rows="data.to_sign" />
          <WaitingPanel :rows="data.waiting" :setup-done="setupDone" />
        </div>
      </ResourceState>
    </main>
    <aside
      class="flex max-w-full flex-[1_1_320px] flex-col gap-5"
      :class="{ 'max-lg:order-first': !setupDone }"
      :aria-label="__('Setup and figures')"
    >
      <ResourceState :resource="setup" :rows="3" :is-empty="() => false" class="flex flex-col gap-5">
        <SetupPanel v-if="status && !status.complete" :status="status" />
        <MonthPanel
          v-else-if="data && status"
          :dashboard="data"
          :setup="status"
          @changed="dashboard.reload()"
        />
      </ResourceState>
    </aside>
  </div>
</template>
