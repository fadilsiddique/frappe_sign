<script setup lang="ts">
// The first page of a template's PDF as a small picture; an icon when there is no PDF (a Print
// Format template is drawn from a document) or it cannot be read.
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { openPdf, renderPage } from '@/shared/pdf'
import { fetchPdf } from '../api'

const props = defineProps<{ pdfUrl: string | null }>()
const canvas = ref<HTMLCanvasElement | null>(null)
const failed = ref(!props.pdfUrl)
let destroy: (() => unknown) | null = null

onMounted(async () => {
  if (!props.pdfUrl || !canvas.value) return
  try {
    const document = await openPdf(await fetchPdf(props.pdfUrl))
    destroy = () => document.loadingTask.destroy()
    await renderPage(await document.getPage(1), canvas.value, 200)
    canvas.value.style.width = '100%'
    canvas.value.style.height = '100%'
  } catch {
    failed.value = true
  }
})
onBeforeUnmount(() => void destroy?.())
</script>

<template>
  <div class="grid aspect-[3/4] w-full place-items-center overflow-hidden rounded bg-surface-gray-2">
    <span v-if="failed" class="lucide-file-text size-8 text-ink-gray-4" aria-hidden="true" />
    <canvas v-show="!failed" ref="canvas" class="h-full w-full object-cover object-top" aria-hidden="true" />
  </div>
</template>
