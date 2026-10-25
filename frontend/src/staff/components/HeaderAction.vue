<script setup lang="ts">
// A page header's primary action: a labelled button on desktop, an icon button on phones, where the
// header centres the title and has no room for a label.
import { Button, type RouteDestination } from 'frappe-ui'
import { useIsMobile } from '../shell/useIsMobile'

defineProps<{ label: string; icon: string; route?: RouteDestination }>()
const isMobile = useIsMobile()
</script>

<template>
  <Button v-if="isMobile" variant="solid" :icon="icon" :label="label" :aria-label="label" :route="route" />
  <Button v-else variant="solid" :icon-left="icon" :label="label" :route="route" />
</template>
