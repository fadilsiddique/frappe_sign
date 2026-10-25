<script setup lang="ts">
import { MobileNav, MobileNavItem } from 'frappe-ui'
import { useRoute } from 'vue-router'
import { __ } from '@/shared/translate'
import { isActive, NAV_ITEMS } from './nav'

const route = useRoute()
</script>

<template>
  <MobileNav data-testid="mobile-nav">
    <MobileNavItem
      v-for="item in NAV_ITEMS"
      :key="item.key"
      :label="__(item.label)"
      :icon="item.icon"
      :route="item.route"
      :href="item.href"
      :active="isActive(item, route.name)"
    />
  </MobileNav>
</template>
