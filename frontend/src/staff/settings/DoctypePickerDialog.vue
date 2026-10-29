<script setup lang="ts">
// Search the DocTypes that can be turned on for signing and pick one.
import { Dialog, FormControl } from 'frappe-ui'
import { ref, watch } from 'vue'
import { __ } from '@/shared/translate'
import { errorMessage, staff } from '../api'

const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ pick: [doctype: string] }>()

const query = ref('')
const choices = ref<string[]>([])
const error = ref('')
let timer: ReturnType<typeof setTimeout> | undefined
let latest = 0

async function search() {
  const mine = ++latest
  try {
    const found = await staff<string[]>('doctype_choices', { query: query.value })
    if (mine === latest) {
      choices.value = found
      error.value = ''
    }
  } catch (e) {
    if (mine === latest) error.value = errorMessage(e)
  }
}

watch(open, (value) => {
  if (!value) return
  query.value = ''
  void search()
})
watch(query, () => {
  clearTimeout(timer)
  timer = setTimeout(search, 200)
})
</script>

<template>
  <Dialog v-model="open" :title="__('Add a document type')" size="lg">
    <div class="flex flex-col gap-3" data-testid="doctype-picker">
      <FormControl
        v-model="query"
        type="search"
        :placeholder="__('Search, for example Quotation')"
        data-testid="doctype-search"
      />
      <p v-if="error" class="text-sm text-ink-red-4" role="alert">{{ error }}</p>
      <ul class="flex max-h-72 flex-col overflow-y-auto" role="listbox">
        <li v-for="name in choices" :key="name" role="option" :aria-selected="false">
          <button
            type="button"
            class="w-full rounded px-2 py-2 text-start text-base text-ink-gray-8 hover:bg-surface-gray-2 focus-visible:focus-ring"
            :data-testid="`pick-${name}`"
            @click="emit('pick', name)"
          >
            {{ __(name) }}
          </button>
        </li>
      </ul>
      <p v-if="!choices.length && !error" class="text-sm text-ink-gray-6">
        {{ __('No document type matches.') }}
      </p>
    </div>
  </Dialog>
</template>
