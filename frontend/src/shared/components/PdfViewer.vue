<script setup lang="ts">
// Lazy PDF viewer: page boxes are sized from the page metrics at once, and each page is drawn by
// pdf.js only when it comes near the screen. The `page` slot is laid over each page; its rect is
// the visible page, so normalized field rects map to CSS percentages directly (D7).
import type { PDFDocumentProxy } from 'pdfjs-dist'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { displaySize, type PageMetric } from '@/shared/coords'
import { openPdf, renderPage } from '@/shared/pdf'

const props = withDefaults(
  defineProps<{
    source: ArrayBuffer | null
    pages: PageMetric[]
    maxWidth?: number
    gap?: number
  }>(),
  { maxWidth: 900, gap: 12 },
)

const emit = defineEmits<{ loaded: [count: number]; error: [error: unknown] }>()

const root = ref<HTMLElement | null>(null)
const width = ref(0)
const document = shallowRef<PDFDocumentProxy | null>(null)
const canvases = new Map<number, HTMLCanvasElement>()
const drawn = new Map<number, number>()
let observer: IntersectionObserver | null = null
let resizer: ResizeObserver | null = null

const boxes = computed(() =>
  props.pages.map((metric) => {
    const size = displaySize(metric)
    return { page: metric.page, width: width.value, height: (width.value * size.height) / size.width }
  }),
)

function measure() {
  if (root.value) width.value = Math.min(root.value.clientWidth, props.maxWidth)
}

async function draw(page: number) {
  const canvas = canvases.get(page)
  if (!document.value || !canvas || !width.value || drawn.get(page) === width.value) return
  drawn.set(page, width.value)
  try {
    await renderPage(await document.value.getPage(page), canvas, width.value)
  } catch (error) {
    drawn.delete(page)
    emit('error', error)
  }
}

function observe() {
  observer?.disconnect()
  observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) void draw(Number((entry.target as HTMLElement).dataset.page))
      }
    },
    { rootMargin: '800px 0px' },
  )
  root.value?.querySelectorAll<HTMLElement>('[data-page]').forEach((el) => observer?.observe(el))
}

function setCanvas(page: number, el: unknown) {
  if (el instanceof HTMLCanvasElement) canvases.set(page, el)
}

watch(
  () => props.source,
  async (source) => {
    drawn.clear()
    document.value = null
    if (!source) return
    try {
      document.value = await openPdf(source)
      emit('loaded', document.value.numPages)
      await nextTick()
      observe()
    } catch (error) {
      emit('error', error)
    }
  },
  { immediate: true },
)

watch(width, () => {
  drawn.clear()
  void nextTick(observe)
})

onMounted(() => {
  measure()
  resizer = new ResizeObserver(measure)
  if (root.value) resizer.observe(root.value)
})

onBeforeUnmount(() => {
  observer?.disconnect()
  resizer?.disconnect()
  void document.value?.loadingTask.destroy()
})

defineExpose({
  scrollToPage(page: number) {
    root.value?.querySelector(`[data-page="${page}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  },
})
</script>

<template>
  <div ref="root" class="w-full">
    <div
      v-for="box in boxes"
      :key="box.page"
      :data-page="box.page"
      class="relative mx-auto bg-white shadow-sm ring-1 ring-outline-gray-1"
      :style="{ width: `${box.width}px`, height: `${box.height}px`, marginBottom: `${gap}px` }"
    >
      <canvas :ref="(el) => setCanvas(box.page, el)" class="absolute inset-0" aria-hidden="true" />
      <div class="absolute inset-0">
        <slot name="page" :page="box.page" :width="box.width" :height="box.height" />
      </div>
    </div>
  </div>
</template>
