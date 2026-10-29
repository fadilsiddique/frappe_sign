<script setup lang="ts">
// Draw (signature_pad), Type (bundled script fonts) or Upload an image (DESIGN 7.3).
import { BottomSheet } from 'frappe-ui'
import type SignaturePad from 'signature_pad'
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { __ } from '@/shared/translate'
import { fontsFor, INK, readAsDataUrl, trimmed, typedSignature } from '../signature'
import type { GuestField } from '../types'
import '../fonts.css'

const props = defineProps<{ field: GuestField | null; name: string; busy: boolean; error: string }>()
const emit = defineEmits<{ close: []; save: [method: string, image: string] }>()

type Tab = 'Draw' | 'Type' | 'Upload'
const tab = ref<Tab>('Draw')
// A press that starts while the sheet slides in lands on the backdrop; do not let it close the sheet.
const SLIDE_MS = 500
let openedAt = 0
const open = computed({
  get: () => Boolean(props.field),
  set: (value) => {
    if (!value && Date.now() - openedAt > SLIDE_MS) emit('close')
  },
})
const canvas = ref<HTMLCanvasElement | null>(null)
const typed = ref('')
const font = ref(0)
const upload = ref('')
const empty = ref(true)
const localError = ref('')
let pad: SignaturePad | null = null

const fonts = computed(() => fontsFor(typed.value || props.name))
const title = computed(() => (props.field ? __(props.field.type) : ''))

async function setupPad() {
  await nextTick()
  if (!canvas.value) return
  const { default: Pad } = await import('signature_pad')
  const ratio = Math.max(window.devicePixelRatio || 1, 1)
  canvas.value.width = canvas.value.offsetWidth * ratio
  canvas.value.height = canvas.value.offsetHeight * ratio
  canvas.value.getContext('2d')?.scale(ratio, ratio)
  pad?.off()
  pad = new Pad(canvas.value, { penColor: INK, minWidth: 1, maxWidth: 2.6 })
  pad.addEventListener('endStroke', () => (empty.value = pad?.isEmpty() ?? true))
  empty.value = true
}

watch(
  () => [props.field, tab.value] as const,
  ([field, current], [before]) => {
    if (field && !before) openedAt = Date.now()
    localError.value = ''
    if (field && current === 'Draw') void setupPad()
  },
)

watch(
  () => props.field,
  (field) => {
    if (field) typed.value = props.name
  },
)

onBeforeUnmount(() => pad?.off())

function clear() {
  pad?.clear()
  empty.value = true
}

async function chooseFile(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  if (!['image/png', 'image/jpeg'].includes(file.type)) {
    localError.value = __('Use a PNG or JPEG image.')
    return
  }
  upload.value = await readAsDataUrl(file)
}

async function save() {
  localError.value = ''
  try {
    if (tab.value === 'Draw') {
      if (!pad || pad.isEmpty() || !canvas.value) throw new Error(__('Draw your signature first.'))
      emit('save', 'Draw', trimmed(canvas.value).toDataURL('image/png'))
    } else if (tab.value === 'Type') {
      emit('save', 'Type', await typedSignature(typed.value, fonts.value[font.value] ?? fonts.value[0]))
    } else {
      if (!upload.value) throw new Error(__('Choose an image first.'))
      emit('save', 'Upload', upload.value)
    }
  } catch (error) {
    localError.value = error instanceof Error ? error.message : String(error)
  }
}
</script>

<template>
  <BottomSheet v-model:open="open" :title="title">
    <div class="space-y-4 px-4 pb-4" data-testid="signature-sheet">
      <div class="flex gap-1 rounded bg-surface-gray-2 p-1" role="tablist">
        <button
          v-for="option in ['Draw', 'Type', 'Upload'] as Tab[]"
          :key="option"
          type="button"
          role="tab"
          :aria-selected="tab === option"
          class="flex-1 rounded px-3 py-1.5 text-sm"
          :class="
            tab === option ? 'bg-surface-base font-medium text-ink-gray-9 shadow-sm' : 'text-ink-gray-6'
          "
          :data-testid="`tab-${option}`"
          @click="tab = option"
        >
          {{ __(option) }}
        </button>
      </div>

      <div v-if="tab === 'Draw'">
        <div class="relative">
          <canvas
            ref="canvas"
            class="h-44 w-full touch-none rounded-lg border border-outline-gray-2 bg-surface-base"
            :aria-label="__('Draw your signature here')"
            data-testid="pad"
          />
          <div class="pointer-events-none absolute inset-x-4 bottom-10 border-b border-outline-gray-3" />
        </div>
        <div class="mt-1 flex justify-between text-sm text-ink-gray-5">
          <span>{{ __('Sign with your finger or mouse') }}</span>
          <button type="button" class="text-ink-gray-7 underline" :disabled="empty" @click="clear">
            {{ __('Clear') }}
          </button>
        </div>
      </div>

      <div v-else-if="tab === 'Type'" class="space-y-3">
        <input v-model="typed" class="form-input w-full" :aria-label="__('Your name')" data-testid="typed" />
        <div class="grid gap-2">
          <button
            v-for="(item, index) in fonts"
            :key="item.family"
            type="button"
            class="rounded border px-3 py-2 text-start text-3xl leading-tight"
            :class="
              font === index ? 'border-[color:var(--sign-brand)] bg-surface-gray-1' : 'border-outline-gray-2'
            "
            :style="{ fontFamily: `'${item.family}', cursive`, color: INK }"
            :dir="item.arabic ? 'rtl' : 'ltr'"
            @click="font = index"
          >
            {{ typed || name }}
          </button>
        </div>
      </div>

      <div v-else class="space-y-2">
        <input
          type="file"
          accept="image/png,image/jpeg"
          class="block w-full text-sm"
          data-testid="upload"
          @change="chooseFile"
        />
        <img
          v-if="upload"
          :src="upload"
          alt=""
          class="max-h-32 rounded border border-outline-gray-2 object-contain"
        />
      </div>

      <p v-if="localError || error" class="text-sm text-ink-red-4" role="alert">{{ localError || error }}</p>
      <p class="text-xs text-ink-gray-5">
        {{ __('By saving, you agree that this is your electronic signature.') }}
      </p>
      <button
        type="button"
        class="h-12 w-full rounded-lg text-base font-medium text-white disabled:opacity-50"
        :style="{ background: 'var(--sign-brand)' }"
        :disabled="busy"
        data-testid="save-signature"
        @click="save"
      >
        {{ __('Save signature') }}
      </button>
    </div>
  </BottomSheet>
</template>
