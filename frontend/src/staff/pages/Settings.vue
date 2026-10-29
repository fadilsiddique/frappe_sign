<script setup lang="ts">
// Settings (UX_PLAN "Settings"): company, documents, signing and advanced. A Sign Manager sees it,
// a System Manager changes it.
import { createResource } from 'frappe-ui'
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { __ } from '@/shared/translate'
import { STAFF_API } from '../api'
import AppPageHeader from '../components/AppPageHeader.vue'
import ResourceState from '../components/ResourceState.vue'
import AdvancedTab from '../settings/AdvancedTab.vue'
import CompanyTab from '../settings/CompanyTab.vue'
import DocumentsTab from '../settings/DocumentsTab.vue'
import HealthTab from '../settings/HealthTab.vue'
import SigningTab from '../settings/SigningTab.vue'
import { SETTINGS_TABS, type SettingsData, type SettingsTab } from '../settings/types'
import { useSetupStatus } from '../home/resources'

const route = useRoute()
const router = useRouter()
const settings = createResource({ url: `${STAFF_API}get_settings`, auto: true })
const setup = useSetupStatus()

const tab = computed<SettingsTab>(() => {
  const asked = String(route.query.tab ?? '')
  return SETTINGS_TABS.some((t) => t.key === asked) ? (asked as SettingsTab) : 'company'
})
const data = computed(() => settings.data as SettingsData | null)

function select(key: SettingsTab) {
  void router.replace({ path: '/settings', query: key === 'company' ? {} : { tab: key } })
}

// A change here can finish a setup step, so the sidebar's "3 left" follows.
function changed() {
  settings.reload()
  setup.reload()
}

function move(event: KeyboardEvent, index: number) {
  const step = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
  if (!step) return
  const next = SETTINGS_TABS[(index + step + SETTINGS_TABS.length) % SETTINGS_TABS.length]!
  select(next.key)
  document.getElementById(`tab-${next.key}`)?.focus()
}
</script>

<template>
  <AppPageHeader :title="__('Settings')" />
  <div class="flex flex-col gap-4 p-4 sm:p-5" data-testid="settings">
    <div
      role="tablist"
      :aria-label="__('Settings')"
      class="flex gap-1 overflow-x-auto border-b border-outline-gray-2"
    >
      <button
        v-for="(item, index) in SETTINGS_TABS"
        :id="`tab-${item.key}`"
        :key="item.key"
        type="button"
        role="tab"
        :aria-selected="tab === item.key"
        :aria-controls="`panel-${item.key}`"
        :tabindex="tab === item.key ? 0 : -1"
        class="-mb-px shrink-0 border-b-2 px-3 py-2 text-base focus-visible:focus-ring"
        :class="
          tab === item.key
            ? 'border-outline-gray-8 font-medium text-ink-gray-9'
            : 'border-transparent text-ink-gray-6 hover:text-ink-gray-8'
        "
        :data-testid="`settings-tab-${item.key}`"
        @click="select(item.key)"
        @keydown="move($event, index)"
      >
        {{ __(item.label) }}
      </button>
    </div>
    <ResourceState :resource="settings" :is-empty="() => false">
      <div
        v-if="data"
        :id="`panel-${tab}`"
        role="tabpanel"
        :aria-labelledby="`tab-${tab}`"
        class="flex flex-col gap-4"
      >
        <p
          v-if="!data.can_edit"
          class="flex items-center gap-2 text-sm text-ink-gray-6"
          data-testid="read-only"
        >
          <span class="lucide-lock size-4" aria-hidden="true" />{{
            __('Only a System Manager can change these settings.')
          }}
        </p>
        <CompanyTab v-if="tab === 'company'" :data="data" @changed="changed" />
        <DocumentsTab v-else-if="tab === 'documents'" :data="data" @changed="changed" />
        <SigningTab v-else-if="tab === 'signing'" :data="data" @changed="changed" />
        <AdvancedTab v-else-if="tab === 'advanced'" :data="data" @changed="changed" />
        <HealthTab v-else />
      </div>
    </ResourceState>
  </div>
</template>
