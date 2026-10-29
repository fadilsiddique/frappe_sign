<script setup lang="ts">
// Recipients as overlapping avatars. The ring shows each person's state; a tick marks who signed.
import { Avatar } from 'frappe-ui'
import { computed } from 'vue'
import { __ } from '@/shared/translate'

export type PersonState = 'signed' | 'opened' | 'waiting' | 'declined'

export interface StackPerson {
  name: string
  state: PersonState
  image?: string | null
}

const props = withDefaults(defineProps<{ people: StackPerson[]; max?: number }>(), { max: 4 })

const RING: Record<PersonState, string> = {
  signed: 'ring-green-500',
  opened: 'ring-blue-500',
  waiting: 'ring-gray-300',
  declined: 'ring-red-500',
}

function describe(person: StackPerson): string {
  if (person.state === 'signed') return __('{0}: signed', [person.name])
  if (person.state === 'opened') return __('{0}: opened, not signed', [person.name])
  if (person.state === 'declined') return __('{0}: declined', [person.name])
  return __('{0}: not opened yet', [person.name])
}

// When the people do not fit, the last slot shows "+n" instead of a face.
const shown = computed(() =>
  props.people.length > props.max ? props.people.slice(0, props.max - 1) : props.people,
)
const hidden = computed(() => props.people.slice(shown.value.length))
</script>

<template>
  <ul class="flex items-center ps-1.5" data-testid="avatar-stack">
    <li
      v-for="person in shown"
      :key="person.name"
      class="relative -ms-1.5 rounded-full ring-[1.5px] ring-offset-1"
      :class="RING[person.state]"
      :title="describe(person)"
      :aria-label="describe(person)"
      :data-state="person.state"
    >
      <Avatar size="sm" :label="person.name" :image="person.image ?? undefined" />
      <span
        v-if="person.state === 'signed'"
        class="absolute -bottom-1 -end-1 grid size-3.5 place-items-center rounded-full border-[1.5px] border-white bg-green-500 text-white"
        aria-hidden="true"
      >
        <span class="lucide-check size-2" />
      </span>
    </li>
    <li
      v-if="hidden.length"
      class="relative -ms-1.5 grid size-6 place-items-center rounded-full bg-surface-gray-3 text-2xs font-semibold text-ink-gray-7 ring-2 ring-white"
      :title="hidden.map(describe).join(', ')"
      :aria-label="hidden.map(describe).join(', ')"
    >
      +{{ hidden.length }}
    </li>
  </ul>
</template>
