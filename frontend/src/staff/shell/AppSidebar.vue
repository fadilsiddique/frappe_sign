<script setup lang="ts">
import { Avatar, call, createResource, Dropdown, Sidebar, SidebarHeader, SidebarItem, toast } from 'frappe-ui'
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { readBoot } from '@/shared/boot'
import { __ } from '@/shared/translate'
import { errorMessage } from '../api'
import { DESK_URL, isActive, NAV_ITEMS } from './nav'

const route = useRoute()
const boot = readBoot()
const userName = boot.full_name || boot.user || ''

const dashboard = createResource({ url: 'frappe_sign.api.staff.get_dashboard', auto: true })
const toSign = computed(() => {
  const count = (dashboard.data as { needs_my_signature?: unknown[] } | null)?.needs_my_signature?.length
  return count ? String(count) : undefined
})

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
        v-for="item in NAV_ITEMS"
        :key="item.key"
        :label="__(item.label)"
        :icon="item.icon"
        :route="item.route"
        :href="item.href"
        :active="isActive(item, route.name)"
        :suffix="item.key === 'to-sign' ? toSign : undefined"
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
