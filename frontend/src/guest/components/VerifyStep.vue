<script setup lang="ts">
import { Button } from 'frappe-ui'
import { ref } from 'vue'
import GuestHeader from './GuestHeader.vue'

defineProps<{ title: string; sentTo: string; busy: boolean; error: string }>()
const emit = defineEmits<{ request: []; verify: [code: string] }>()
const code = ref('')
</script>

<template>
  <div class="-mx-3 min-h-screen bg-surface-base" data-testid="verify">
    <GuestHeader />
    <section class="mx-auto mt-10 max-w-sm px-6">
      <h1 class="text-lg font-semibold text-ink-gray-9">{{ __('Verify your email') }}</h1>
      <p class="mt-1 text-base text-ink-gray-6">
        {{ __('To open {0}, enter the code we email you.', [title]) }}
      </p>
      <Button
        v-if="!sentTo"
        class="mt-5 w-full"
        variant="solid"
        size="md"
        :loading="busy"
        :label="__('Email me a code')"
        @click="emit('request')"
      />
      <form v-else class="mt-5 space-y-3" @submit.prevent="emit('verify', code)">
        <p class="text-sm text-ink-gray-6">{{ __('We sent a 6-digit code to {0}.', [sentTo]) }}</p>
        <input
          v-model="code"
          class="form-input w-full text-center text-lg tracking-[0.5em]"
          inputmode="numeric"
          autocomplete="one-time-code"
          maxlength="6"
          :aria-label="__('Verification code')"
          data-testid="otp"
        />
        <Button
          class="w-full"
          variant="solid"
          size="md"
          type="submit"
          :loading="busy"
          :disabled="code.length !== 6"
          :label="__('Verify')"
        />
        <Button class="w-full" variant="ghost" :label="__('Send a new code')" @click="emit('request')" />
      </form>
      <p v-if="error" class="mt-3 text-sm text-ink-red-4" role="alert">{{ error }}</p>
    </section>
  </div>
</template>
