<script setup lang="ts">
// The page title and its actions. frappe-ui moves the header into the shell's header slot.
// #primary is the page's one main action (HeaderAction): it stays in the header on phones too.
// #actions are the others: in the header on desktop, in a wrapping row under it on phones, where
// the centred title leaves no room for them.
import { PageHeader, PageHeaderMobile } from 'frappe-ui'
import { useIsMobile } from '../shell/useIsMobile'

defineProps<{ title: string }>()
const isMobile = useIsMobile()
</script>

<template>
  <template v-if="isMobile">
    <PageHeaderMobile :title="title">
      <template v-if="$slots.primary" #suffix>
        <slot name="primary" />
      </template>
    </PageHeaderMobile>
    <div v-if="$slots.actions" class="flex flex-wrap gap-2 px-4 pt-3" data-testid="page-actions">
      <slot name="actions" />
    </div>
  </template>
  <PageHeader v-else>
    <h1 class="truncate text-3xl font-semibold text-ink-gray-9">{{ title }}</h1>
    <div v-if="$slots.actions || $slots.primary" class="flex items-center gap-2">
      <slot name="actions" />
      <slot name="primary" />
    </div>
  </PageHeader>
</template>
