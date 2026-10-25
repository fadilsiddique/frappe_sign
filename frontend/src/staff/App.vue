<script setup lang="ts">
// The app shell (D18): a frappe-ui sidebar on desktop, a tab bar on phones. The designer needs the
// full width, so it has neither.
import { DesktopShell, FrappeUIProvider, MobileShell } from 'frappe-ui'
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppMobileNav from './shell/AppMobileNav.vue'
import AppSidebar from './shell/AppSidebar.vue'
import { useIsMobile } from './shell/useIsMobile'

const route = useRoute()
const isMobile = useIsMobile()
// The designer has no nav, and its panes scroll on their own.
const fullWidth = computed(() => route.name === 'Designer')
</script>

<template>
  <FrappeUIProvider>
    <MobileShell v-if="isMobile">
      <RouterView />
      <template v-if="!fullWidth" #nav>
        <AppMobileNav />
      </template>
    </MobileShell>
    <DesktopShell v-else :scroll="!fullWidth" class="bg-surface-gray-1">
      <template v-if="!fullWidth" #sidebar>
        <AppSidebar />
      </template>
      <RouterView />
    </DesktopShell>
  </FrappeUIProvider>
</template>
