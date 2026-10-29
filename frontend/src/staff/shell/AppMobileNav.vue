<script setup lang="ts">
import { MobileNav, MobileNavItem } from 'frappe-ui'
import { useRoute } from 'vue-router'
import { __ } from '@/shared/translate'
import { isActive, visibleNavItems } from './nav'

import { readBoot } from '@/shared/boot'

const route = useRoute()
const items = visibleNavItems(readBoot().can_manage)
</script>

<template>
  <MobileNav data-testid="mobile-nav">
    <MobileNavItem
      v-for="item in items"
      :key="item.key"
      :label="__(item.label)"
      :icon="item.icon"
      :route="item.route"
      :href="item.href"
      :active="isActive(item, route.name)"
    />
  </MobileNav>
</template>
