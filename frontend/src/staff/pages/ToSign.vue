<script setup lang="ts">
// To sign: everything colleagues sent the user to sign or approve (the same list Home shows).
import { computed } from 'vue'
import { __ } from '@/shared/translate'
import AppPageHeader from '../components/AppPageHeader.vue'
import ResourceState from '../components/ResourceState.vue'
import { useDashboard } from '../home/resources'
import ToSignPanel from '../home/ToSignPanel.vue'
import type { Dashboard } from '../home/types'

const dashboard = useDashboard()
const data = computed(() => dashboard.data as Dashboard | null)
</script>

<template>
  <AppPageHeader :title="__('To sign')" />
  <div class="p-4 sm:p-5" data-testid="to-sign-page">
    <ResourceState :resource="dashboard" :rows="4">
      <ToSignPanel v-if="data" :rows="data.to_sign" />
    </ResourceState>
  </div>
</template>
