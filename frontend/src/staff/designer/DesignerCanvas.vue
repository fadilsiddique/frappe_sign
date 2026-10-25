<script setup lang="ts">
// The pages with their fields: click a palette type, then click the page to place it; drag a
// field to move it, drag a corner or edge to resize; arrow keys nudge, Delete removes,
// Ctrl+Z / Ctrl+Shift+Z undo and redo (DESIGN 7.4).
import { onBeforeUnmount, onMounted, ref } from 'vue'
import PdfViewer from '@/shared/components/PdfViewer.vue'
import type { Rect } from '@/shared/coords'
import type { Handle } from '@/shared/composables/useDragResize'
import { __ } from '@/shared/translate'
import { useDesigner, type FieldType } from './store'

const props = defineProps<{ source: ArrayBuffer | null; placing: FieldType | null }>()
const emit = defineEmits<{ placed: [] }>()
const store = useDesigner()

const HANDLES: Handle[] = ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w']
let drag: {
  key: string
  handle: Handle
  start: Rect
  x: number
  y: number
  viewport: { width: number; height: number }
} | null = null

function place(event: MouseEvent, page: number, width: number, height: number) {
  if (!props.placing) {
    store.clearSelection()
    return
  }
  const box = (event.currentTarget as HTMLElement).getBoundingClientRect()
  store.placeField(props.placing, page, event.clientX - box.left, event.clientY - box.top, { width, height })
  emit('placed')
}

function begin(event: PointerEvent, key: string, handle: Handle, width: number, height: number) {
  if (event.button !== 0) return
  event.preventDefault()
  event.stopPropagation()
  store.select(key, event.shiftKey)
  const field = store.fields.find((f) => f.field_key === key)
  if (!field) return
  store.record()
  drag = {
    key,
    handle,
    start: { x: field.x, y: field.y, w: field.w, h: field.h },
    x: event.clientX,
    y: event.clientY,
    viewport: { width, height },
  }
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', end)
}

function move(event: PointerEvent) {
  if (drag)
    store.dragField(
      drag.key,
      drag.start,
      drag.handle,
      event.clientX - drag.x,
      event.clientY - drag.y,
      drag.viewport,
    )
}

function end() {
  drag = null
  window.removeEventListener('pointermove', move)
  window.removeEventListener('pointerup', end)
}

function onKey(event: KeyboardEvent) {
  const target = event.target as HTMLElement
  if (['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) || target.isContentEditable) return
  const mod = event.ctrlKey || event.metaKey
  if (mod && event.key.toLowerCase() === 'z') {
    event.preventDefault()
    if (event.shiftKey) store.redo()
    else store.undo()
  } else if ((event.key === 'Delete' || event.key === 'Backspace') && store.selected.length) {
    event.preventDefault()
    store.removeSelected()
  } else if (event.key.startsWith('Arrow') && store.selected.length) {
    event.preventDefault()
    store.nudgeSelected(event.key, event.shiftKey)
  }
}

const handleStyle: Record<Handle, string> = {
  nw: 'left-0 top-0 -translate-x-1/2 -translate-y-1/2 cursor-nwse-resize',
  n: 'left-1/2 top-0 -translate-x-1/2 -translate-y-1/2 cursor-ns-resize',
  ne: 'right-0 top-0 translate-x-1/2 -translate-y-1/2 cursor-nesw-resize',
  e: 'right-0 top-1/2 translate-x-1/2 -translate-y-1/2 cursor-ew-resize',
  se: 'right-0 bottom-0 translate-x-1/2 translate-y-1/2 cursor-nwse-resize',
  s: 'left-1/2 bottom-0 -translate-x-1/2 translate-y-1/2 cursor-ns-resize',
  sw: 'left-0 bottom-0 -translate-x-1/2 translate-y-1/2 cursor-nesw-resize',
  w: 'left-0 top-1/2 -translate-x-1/2 -translate-y-1/2 cursor-ew-resize',
  move: '',
}

const viewer = ref<InstanceType<typeof PdfViewer> | null>(null)
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  end()
})
</script>

<template>
  <PdfViewer ref="viewer" :source="source" :pages="store.pages" :max-width="820">
    <template #page="{ page, width, height }">
      <div
        class="absolute inset-0"
        :class="placing ? 'cursor-crosshair' : ''"
        :data-testid="`page-${page}`"
        @click.self="place($event, page, width, height)"
      >
        <div
          v-for="field in store.fieldsOn(page)"
          :key="field.field_key"
          class="absolute select-none rounded-sm border-2 text-[10px] leading-tight"
          :class="store.selected.includes(field.field_key) ? 'z-10 shadow' : ''"
          :style="{
            left: `${field.x * 100}%`,
            top: `${field.y * 100}%`,
            width: `${field.w * 100}%`,
            height: `${field.h * 100}%`,
            borderColor: store.roleColor(field.role_label),
            background: `${store.roleColor(field.role_label)}22`,
          }"
          :data-field="field.field_key"
          role="button"
          :aria-label="`${__(field.field_type)} ${field.role_label}`"
          @pointerdown="begin($event, field.field_key, 'move', width, height)"
        >
          <span class="pointer-events-none block truncate px-1 py-0.5 text-ink-gray-8">
            {{ __(field.field_type) }}<span v-if="field.required" class="text-ink-red-4">*</span>
            <span v-if="field.anchor_tag" :title="__('Placed by an anchor')"> ⚓</span>
          </span>
          <template v-if="store.selected.length === 1 && store.selected[0] === field.field_key">
            <span
              v-for="handle in HANDLES"
              :key="handle"
              class="absolute size-2.5 rounded-sm border border-white"
              :class="handleStyle[handle]"
              :style="{ background: store.roleColor(field.role_label) }"
              :data-handle="handle"
              @pointerdown="begin($event, field.field_key, handle, width, height)"
            />
          </template>
        </div>
      </div>
    </template>
  </PdfViewer>
</template>
