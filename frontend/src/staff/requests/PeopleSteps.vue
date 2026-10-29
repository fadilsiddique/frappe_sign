<script setup lang="ts">
// The people of a request as a vertical step list, in signing order. Remind and New link show on
// the people whose turn it is. Used by the Sent preview and the request page.
import { Button } from 'frappe-ui'
import { computed } from 'vue'
import { __ } from '@/shared/translate'
import { nextPeople, personState, type Person } from './people'

const props = defineProps<{
  people: Person[]
  order: string | null
  status: string
  canAct: boolean
}>()
const emit = defineEmits<{ remind: [person: Person]; newLink: [person: Person] }>()

const next = computed(() => nextPeople(props.people, props.order))
const open = computed(() => ['Sent', 'In Progress'].includes(props.status))
const heading = computed(() =>
  props.people.length > 1 && props.order === 'Parallel'
    ? __('People, all at once')
    : __('People, in signing order'),
)

function tone(person: Person): string {
  if (person.status === 'Signed') return 'bg-green-500 text-white ring-green-500'
  if (person.status === 'Declined') return 'bg-surface-red-2 text-ink-red-4 ring-red-500'
  if (next.value.has(person.name)) return 'bg-surface-base text-ink-blue-6 ring-blue-500'
  return 'bg-surface-base text-ink-gray-6 ring-gray-300'
}
</script>

<template>
  <div class="flex flex-col gap-3">
    <h3 class="text-base font-semibold text-ink-gray-9">{{ heading }}</h3>
    <ol class="flex flex-col">
      <li
        v-for="(person, index) in people"
        :key="person.name"
        class="relative flex gap-3 pb-4"
        data-testid="person"
      >
        <span
          v-if="index < people.length - 1"
          class="absolute start-[13px] top-8 bottom-0 w-0.5"
          :class="person.status === 'Signed' ? 'bg-green-500' : 'bg-surface-gray-3'"
          aria-hidden="true"
        />
        <span
          class="relative grid size-7 shrink-0 place-items-center rounded-full text-xs font-semibold ring-[1.5px] ring-inset"
          :class="tone(person)"
          aria-hidden="true"
        >
          <span v-if="person.status === 'Signed'" class="lucide-check size-3.5" />
          <template v-else>{{ index + 1 }}</template>
        </span>
        <span class="flex min-w-0 flex-1 flex-col gap-0.5 pt-0.5">
          <span class="flex flex-wrap items-baseline gap-x-2">
            <span class="text-base font-medium text-ink-gray-9">{{ person.full_name }}</span>
            <span class="text-sm text-ink-gray-6">{{ person.role_label }}</span>
          </span>
          <span
            class="text-sm"
            :class="person.status === 'Declined' ? 'text-ink-red-4' : 'text-ink-gray-6'"
            >{{ personState(person, status) }}</span
          >
          <span v-if="open && canAct && next.has(person.name)" class="flex gap-1.5 pt-1.5">
            <Button size="sm" variant="outline" :label="__('Remind')" @click="emit('remind', person)" />
            <Button size="sm" variant="ghost" :label="__('New link')" @click="emit('newLink', person)" />
          </span>
        </span>
      </li>
    </ol>
  </div>
</template>
