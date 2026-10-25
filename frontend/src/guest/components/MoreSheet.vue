<script setup lang="ts">
// Decline (reason required) or pass the document on to someone else (when the role allows it).
import { BottomSheet, Button } from 'frappe-ui'
import { computed, ref } from 'vue'

const props = defineProps<{ mode: 'decline' | 'delegate' | null; busy: boolean; error: string }>()
const emit = defineEmits<{ close: []; decline: [reason: string]; delegate: [name: string, email: string] }>()

const reason = ref('')
const name = ref('')
const email = ref('')
const open = computed({
  get: () => Boolean(props.mode),
  set: (next) => next || emit('close'),
})
</script>

<template>
  <BottomSheet
    v-model:open="open"
    :title="mode === 'decline' ? __('Decline to sign') : __('Ask someone else to sign')"
  >
    <form v-if="mode === 'decline'" class="space-y-3 px-4 pb-4" @submit.prevent="emit('decline', reason)">
      <textarea
        v-model="reason"
        class="form-textarea w-full"
        rows="3"
        :placeholder="__('Tell the sender why')"
        maxlength="1000"
        data-testid="decline-reason"
      />
      <p v-if="error" class="text-sm text-ink-red-4" role="alert">{{ error }}</p>
      <Button
        class="w-full"
        theme="red"
        variant="solid"
        size="md"
        type="submit"
        :disabled="!reason.trim()"
        :loading="busy"
        :label="__('Decline')"
      />
    </form>
    <form
      v-else-if="mode === 'delegate'"
      class="space-y-3 px-4 pb-4"
      @submit.prevent="emit('delegate', name, email)"
    >
      <input v-model="name" class="form-input w-full" :placeholder="__('Full name')" maxlength="140" />
      <input v-model="email" class="form-input w-full" type="email" :placeholder="__('Email address')" />
      <p v-if="error" class="text-sm text-ink-red-4" role="alert">{{ error }}</p>
      <Button
        class="w-full"
        variant="solid"
        size="md"
        type="submit"
        :disabled="!name.trim() || !email.trim()"
        :loading="busy"
        :label="__('Send to them')"
      />
    </form>
  </BottomSheet>
</template>
