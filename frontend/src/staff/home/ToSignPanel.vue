<script setup lang="ts">
// "For you to sign": what colleagues sent the user to sign or approve. Sign opens the signing page.
import { Button, toast } from 'frappe-ui'
import { ref } from 'vue'
import { __ } from '@/shared/translate'
import { errorMessage, staff } from '../api'
import EmptyState from '../components/EmptyState.vue'
import { askedLine } from './lines'
import type { ToSignRow } from './types'

defineProps<{ rows: ToSignRow[] }>()
const opening = ref<string | null>(null)

async function sign(row: ToSignRow) {
  opening.value = row.name
  try {
    const { url } = await staff<{ url: string }>('my_signing_link', { envelope: row.name })
    window.location.href = url
  } catch (error) {
    toast.error(errorMessage(error))
    opening.value = null
  }
}
</script>

<template>
  <section
    id="to-sign"
    aria-labelledby="to-sign-title"
    class="flex flex-col rounded-lg border border-outline-gray-1 bg-surface-base"
    data-testid="to-sign"
  >
    <div class="flex items-center gap-2 px-4 pb-2.5 pt-3.5">
      <h2 id="to-sign-title" class="flex-1 text-lg font-semibold text-ink-gray-9">
        {{ __('For you to sign') }}
      </h2>
      <span v-if="rows.length" class="text-sm text-ink-gray-6">
        {{ rows.length === 1 ? __('1 waiting on you') : __('{0} waiting on you', [rows.length]) }}
      </span>
    </div>
    <EmptyState
      v-if="!rows.length"
      class="border-t border-outline-gray-1"
      :title="__('You are all caught up')"
      :text="__('Documents that colleagues send you to sign or approve show here.')"
    />
    <div
      v-for="row in rows"
      :key="row.name"
      class="flex items-center gap-3.5 border-t border-outline-gray-1 px-4 py-3"
      data-testid="to-sign-row"
    >
      <span
        class="grid h-11 w-9 shrink-0 place-items-center rounded-sm border border-outline-gray-2 bg-surface-base text-ink-gray-5"
        aria-hidden="true"
      >
        <span class="lucide-file-text size-4" />
      </span>
      <span class="flex min-w-0 flex-1 flex-col gap-0.5">
        <span class="truncate text-base font-medium text-ink-gray-9">{{ row.title }}</span>
        <span class="truncate text-sm text-ink-gray-6">{{ askedLine(row) }}</span>
      </span>
      <span class="hidden w-28 shrink-0 text-sm text-ink-gray-6 sm:block">
        {{ row.kind === 'Approver' ? __('You approve') : __('You sign') }}
      </span>
      <span class="flex w-24 shrink-0 justify-end">
        <Button
          variant="solid"
          :label="row.kind === 'Approver' ? __('Approve') : __('Sign')"
          :loading="opening === row.name"
          @click="sign(row)"
        />
      </span>
    </div>
  </section>
</template>
