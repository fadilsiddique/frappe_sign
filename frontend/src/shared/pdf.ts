// pdf.js is loaded on demand, so it stays out of the first load of the guest bundle (DESIGN 7.3).
import type { PDFDocumentProxy, PDFPageProxy } from 'pdfjs-dist'

type Pdfjs = typeof import('pdfjs-dist')

let pdfjs: Promise<Pdfjs> | null = null

export function loadPdfjs(): Promise<Pdfjs> {
  pdfjs ??= Promise.all([import('pdfjs-dist'), import('pdfjs-dist/build/pdf.worker.min.mjs?url')]).then(
    ([lib, worker]) => {
      lib.GlobalWorkerOptions.workerSrc = worker.default
      return lib
    },
  )
  return pdfjs
}

export async function openPdf(data: ArrayBuffer): Promise<PDFDocumentProxy> {
  const lib = await loadPdfjs()
  // pdf.js takes ownership of the buffer; give it a copy so callers can keep theirs.
  return lib.getDocument({ data: new Uint8Array(data.slice(0)) }).promise
}

// Draw a page into a canvas at `cssWidth` CSS pixels wide, sharp on high-density screens.
export async function renderPage(
  page: PDFPageProxy,
  canvas: HTMLCanvasElement,
  cssWidth: number,
): Promise<void> {
  const base = page.getViewport({ scale: 1 })
  const viewport = page.getViewport({ scale: cssWidth / base.width })
  const ratio = Math.min(window.devicePixelRatio || 1, 3)
  canvas.width = Math.floor(viewport.width * ratio)
  canvas.height = Math.floor(viewport.height * ratio)
  canvas.style.width = `${viewport.width}px`
  canvas.style.height = `${viewport.height}px`
  await page.render({ canvas, viewport, transform: ratio === 1 ? undefined : [ratio, 0, 0, ratio, 0, 0] })
    .promise
}
