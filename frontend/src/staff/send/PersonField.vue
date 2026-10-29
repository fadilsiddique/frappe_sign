<script setup lang="ts">
// A name with suggestions from Contacts and Users. Picking one fills the email too; a name that
// nobody has stays as typed (a Combobox would clear it again on blur). ARIA combobox pattern.
import { TextInput } from 'frappe-ui'
import { computed, ref, useId, watch } from 'vue'
import { staff } from '../api'
import type { Person } from './types'

const name = defineModel<string>('name', { required: true })
const email = defineModel<string>('email', { required: true })
defineProps<{ placeholder: string }>()

const id = useId()
const people = ref<Person[]>([])
const focused = ref(false)
const active = ref(-1)
let request = 0
let timer: number | undefined
let picked = ''

const shown = computed(() => focused.value && people.value.length > 0)

watch(name, (text) => {
  window.clearTimeout(timer)
  if (!focused.value || text === picked) return
  timer = window.setTimeout(async () => {
    const current = ++request
    try {
      const found = await staff<Person[]>('search_people', { query: text })
      if (current === request) {
        people.value = found
        active.value = -1
      }
    } catch {
      people.value = []
    }
  }, 250)
})

function pick(person: Person) {
  picked = person.full_name
  name.value = person.full_name
  email.value = person.email
  people.value = []
  active.value = -1
}

function move(step: number) {
  if (!shown.value) return
  active.value = (active.value + step + people.value.length) % people.value.length
}

function enter(event: KeyboardEvent) {
  if (shown.value && active.value >= 0) {
    event.preventDefault()
    pick(people.value[active.value])
  }
}

function blur() {
  // Let a click on a suggestion land before the list goes away.
  window.setTimeout(() => (focused.value = false), 150)
}
</script>

<template>
  <div class="relative">
    <TextInput
      v-model="name"
      role="combobox"
      autocomplete="off"
      :placeholder="placeholder"
      :aria-expanded="shown"
      :aria-controls="`${id}-list`"
      :aria-activedescendant="active >= 0 ? `${id}-${active}` : undefined"
      aria-autocomplete="list"
      @focus="focused = true"
      @blur="blur"
      @keydown.down.prevent="move(1)"
      @keydown.up.prevent="move(-1)"
      @keydown.enter="enter"
      @keydown.esc="people = []"
    />
    <ul
      v-show="shown"
      :id="`${id}-list`"
      role="listbox"
      class="absolute inset-x-0 top-full z-20 mt-1 max-h-64 overflow-auto rounded-lg border border-outline-gray-2 bg-surface-modal p-1 shadow-lg"
    >
      <li
        v-for="(person, index) in people"
        :id="`${id}-${index}`"
        :key="person.email"
        role="option"
        :aria-selected="index === active"
        class="flex cursor-pointer flex-col rounded px-2 py-1.5"
        :class="index === active ? 'bg-surface-gray-3' : 'hover:bg-surface-gray-2'"
        @mousedown.prevent="pick(person)"
      >
        <span class="truncate text-base text-ink-gray-9">{{ person.full_name }}</span>
        <span class="truncate text-sm text-ink-gray-6">{{ person.email }}</span>
      </li>
    </ul>
  </div>
</template>
