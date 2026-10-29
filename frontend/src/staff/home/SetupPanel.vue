<script setup lang="ts">
// "Set up signing": numbered steps joined by a line. The first step to do is open, with its one
// sentence and its button, the page's primary action. Any step opens on click.
import { Button } from 'frappe-ui'
import { computed, ref, watch } from 'vue'
import { __ } from '@/shared/translate'
import { firstOpenStep, stepsLeft, stepViews, type StepView } from './setupSteps'
import type { SetupKey, SetupStatus } from './types'

const props = defineProps<{ status: SetupStatus }>()

const views = computed(() => stepViews(props.status))
const current = computed(() => firstOpenStep(props.status))
const required = computed(() => props.status.steps.filter((step) => step.required).length)
const done = computed(() => required.value - stepsLeft(props.status))

const open = ref<SetupKey | null>(current.value)
// When a step gets done (the data reloads), open the next one.
watch(current, (next) => (open.value = next))

function toggle(step: StepView) {
  open.value = open.value === step.key ? null : step.key
}

function dot(step: StepView): string {
  if (step.done) return 'bg-green-500 text-ink-white ring-green-500'
  if (step.key === current.value) return 'bg-surface-gray-9 text-ink-white ring-gray-900'
  return 'bg-surface-base text-ink-gray-6 ring-gray-300'
}
</script>

<template>
  <section
    aria-labelledby="setup-title"
    class="flex flex-col gap-1 rounded-lg border border-outline-gray-1 bg-surface-base p-4"
    data-testid="setup-panel"
  >
    <div class="flex items-baseline gap-2 pb-2">
      <h2 id="setup-title" class="flex-1 text-lg font-semibold text-ink-gray-9">
        {{ __('Set up signing') }}
      </h2>
      <span class="text-sm text-ink-gray-6">{{ __('{0} of {1}', [done, required]) }}</span>
    </div>
    <ol class="flex flex-col">
      <li v-for="(step, index) in views" :key="step.key" class="relative flex flex-col" :data-step="step.key">
        <span
          v-if="index < views.length - 1"
          aria-hidden="true"
          class="absolute start-[11px] top-8 -bottom-2 w-0.5"
          :class="step.done ? 'bg-green-500' : 'bg-surface-gray-3'"
        />
        <button
          type="button"
          class="flex w-full items-start gap-3 rounded py-2 text-start focus-visible:focus-ring"
          :aria-expanded="open === step.key"
          :data-done="step.done ? '1' : '0'"
          @click="toggle(step)"
        >
          <span
            class="relative z-[1] grid size-6 shrink-0 place-items-center rounded-full text-xs font-semibold ring-[1.5px] ring-inset"
            :class="dot(step)"
          >
            <span v-if="step.done" class="lucide-check size-3.5" aria-hidden="true" />
            <template v-else>{{ step.number }}</template>
            <span class="sr-only">{{ step.done ? __('Done') : __('To do') }}</span>
          </span>
          <span class="flex min-w-0 flex-1 flex-col gap-0.5 pt-0.5">
            <span
              class="text-base"
              :class="[
                step.key === current || open === step.key ? 'font-semibold' : 'font-medium',
                step.done ? 'text-ink-gray-7' : 'text-ink-gray-9',
              ]"
            >
              {{ step.title }}
              <span v-if="step.optional" class="font-normal text-ink-gray-6">{{ __('(optional)') }}</span>
            </span>
            <span
              v-if="step.summary && open !== step.key"
              class="truncate text-sm"
              :class="step.done ? 'text-ink-gray-6' : 'text-ink-red-4'"
              >{{ step.summary }}</span
            >
          </span>
        </button>
        <div
          v-if="open === step.key"
          class="flex flex-col items-start gap-3 pb-3 ps-9"
          data-testid="step-detail"
        >
          <p v-if="step.summary" class="text-sm" :class="step.done ? 'text-ink-gray-6' : 'text-ink-red-4'">
            {{ step.summary }}
          </p>
          <p class="text-p-sm text-ink-gray-7">{{ step.text }}</p>
          <template v-if="step.canFix">
            <Button
              v-if="step.route"
              :variant="step.key === current ? 'solid' : 'outline'"
              :label="step.action"
              :route="step.route"
            />
            <Button
              v-else
              :variant="step.key === current ? 'solid' : 'outline'"
              :label="step.action"
              icon-right="lucide-arrow-up-right"
              :href="step.href"
              :title="__('Opens in Desk')"
            />
          </template>
          <p v-else class="text-sm text-ink-gray-6">
            {{ __('Ask a Sign Manager or System Manager to do this.') }}
          </p>
        </div>
      </li>
    </ol>
  </section>
</template>
