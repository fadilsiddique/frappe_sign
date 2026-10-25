<script setup lang="ts">
import { onMounted } from 'vue'
import ConsentStep from '../components/ConsentStep.vue'
import SignStep from '../components/SignStep.vue'
import TerminalScreen from '../components/TerminalScreen.vue'
import VerifyStep from '../components/VerifyStep.vue'
import { useGuestFlow } from '../useGuestFlow'

const props = defineProps<{ token: string }>()
const flow = useGuestFlow(props.token)
const state = flow.state

onMounted(() => {
  // The token is in the address bar; keep it out of history entries made later.
  void flow.start()
})
</script>

<template>
  <div class="flow-root min-h-full bg-surface-gray-2 px-3 pb-6">
    <div
      v-if="state.screen === 'loading'"
      class="flex h-screen items-center justify-center text-ink-gray-5"
      data-testid="loading"
    >
      {{ __('Opening document...') }}
    </div>
    <VerifyStep
      v-else-if="state.screen === 'verify'"
      :title="state.summary?.envelope.title ?? ''"
      :sent-to="state.otpSentTo"
      :busy="state.busy"
      :error="state.error"
      @request="flow.requestOtp()"
      @verify="(code) => flow.verifyOtp(code)"
    />
    <ConsentStep
      v-else-if="state.screen === 'consent' && state.summary"
      :summary="state.summary"
      :busy="state.busy"
      :error="state.error"
      @accept="flow.acceptConsent()"
    />
    <div v-else-if="state.screen === 'sign' && state.summary" class="-mx-3">
      <SignStep :flow="flow" />
    </div>
    <TerminalScreen
      v-else
      :screen="state.screen as any"
      :waiting-for="state.waitingFor"
      :completed="state.completed"
      :error="state.error"
    />
  </div>
</template>
