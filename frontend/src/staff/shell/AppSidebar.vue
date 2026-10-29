<script setup lang="ts">
import { Avatar, call, Dropdown, Sidebar, SidebarHeader, SidebarItem, toast } from 'frappe-ui'
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { readBoot } from '@/shared/boot'
import { __ } from '@/shared/translate'
import { errorMessage } from '../api'
import { useDashboard, useSetupStatus } from '../home/resources'
import { stepsLeft } from '../home/setupSteps'
import type { Dashboard, SetupStatus } from '../home/types'
import { DESK_URL, isActive, visibleNavItems } from './nav'

const route = useRoute()
const boot = readBoot()
const items = visibleNavItems(boot.can_manage)
const userName = boot.full_name || boot.user || ''

// Shared with Home (one request each).
const dashboard = useDashboard()
const setup = useSetupStatus()
const toSign = computed(() => {
  const count = (dashboard.data as Dashboard | null)?.to_sign.length
  return count ? String(count) : undefined
})
const setupLeft = computed(() => {
  const status = setup.data as SetupStatus | null
  const left = status ? stepsLeft(status) : 0
  return left ? __('{0} left', [left]) : undefined
})
const suffixes: Record<string, () => string | undefined> = {
  'to-sign': () => toSign.value,
  settings: () => setupLeft.value,
}

async function logOut() {
  try {
    await call('logout')
    window.location.href = '/login'
  } catch (error) {
    toast.error(errorMessage(error))
  }
}
const userMenu = [{ label: __('Log out'), icon: 'lucide-log-out', onClick: logOut }]
</script>

<template>
  <!-- Direction B (UX_PLAN "Chosen direction"): a white sidebar beside a gray page, the active row in gray. -->
  <Sidebar :collapsible="false" class="border-e border-outline-gray-1 !bg-surface-base" data-testid="sidebar">
    <div class="px-2">
      <SidebarHeader
        :title="__('Frappe Sign')"
        :subtitle="boot.branding.company ?? undefined"
        :logo="boot.branding.logo ?? undefined"
      />
    </div>
    <div class="flex flex-1 flex-col gap-0.5 overflow-y-auto px-2 pt-1">
      <SidebarItem
        v-for="item in items"
        :key="item.key"
        :label="__(item.label)"
        :icon="item.icon"
        :route="item.route"
        :href="item.href"
        :active="isActive(item, route.name)"
        :suffix="suffixes[item.key]?.()"
        class="data-[state=active]:!bg-surface-gray-3 data-[state=active]:!shadow-none"
        :data-testid="`nav-${item.key}`"
      />
    </div>
    <div class="flex flex-col gap-0.5 border-t border-outline-gray-1 p-2">
      <SidebarItem :label="__('Back to Desk')" icon="lucide-arrow-left" :href="DESK_URL" />
      <Dropdown :options="userMenu">
        <button
          type="button"
          class="flex h-9 w-full items-center gap-2 rounded px-2 text-start text-base text-ink-gray-8 hover:bg-surface-gray-2 focus-visible:focus-ring"
        >
          <Avatar size="sm" :label="userName" :image="boot.user_image ?? undefined" />
          <span class="min-w-0 flex-1 truncate">{{ userName }}</span>
          <span class="lucide-chevron-down size-4 text-ink-gray-6" aria-hidden="true" />
        </button>
      </Dropdown>
    </div>
  </Sidebar>
</template>
