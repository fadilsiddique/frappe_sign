import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'

const rendered: number[] = []

vi.mock('@/shared/pdf', () => ({
  openPdf: vi.fn(async () => ({
    numPages: 3,
    getPage: async (page: number) => ({ page }),
    loadingTask: { destroy: vi.fn() },
  })),
  renderPage: vi.fn(async (page: { page: number }) => {
    rendered.push(page.page)
  }),
}))

let intersect: (targets: Element[]) => void = () => {}

beforeEach(() => {
  rendered.length = 0
  vi.stubGlobal(
    'IntersectionObserver',
    class {
      constructor(callback: (entries: Array<{ isIntersecting: boolean; target: Element }>) => void) {
        intersect = (targets) => callback(targets.map((target) => ({ isIntersecting: true, target })))
      }
      observe() {}
      disconnect() {}
    },
  )
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      disconnect() {}
    },
  )
  Object.defineProperty(HTMLElement.prototype, 'clientWidth', { configurable: true, get: () => 400 })
})

afterEach(() => vi.unstubAllGlobals())

const pages = [
  { page: 1, width: 595.2756, height: 841.8898, rotation: 0, left: 0, bottom: 0 },
  { page: 2, width: 595.2756, height: 841.8898, rotation: 90, left: 0, bottom: 0 },
  { page: 3, width: 540, height: 696, rotation: 270, left: 36, bottom: 48 },
]

describe('PdfViewer', () => {
  it('sizes every page from its metrics before drawing and draws only visible pages', async () => {
    const { default: PdfViewer } = await import('@/shared/components/PdfViewer.vue')
    const wrapper = mount(PdfViewer, {
      props: { source: new ArrayBuffer(8), pages },
      slots: { page: ({ page }: { page: number }) => h('span', { class: 'overlay' }, String(page)) },
    })
    await flushPromises()
    const boxes = wrapper.findAll('[data-page]')
    expect(boxes.map((box) => box.attributes('style'))).toEqual([
      expect.stringContaining(`height: ${(400 * 841.8898) / 595.2756}px`),
      expect.stringContaining(`height: ${(400 * 595.2756) / 841.8898}px`),
      expect.stringContaining(`height: ${(400 * 540) / 696}px`),
    ])
    expect(wrapper.findAll('.overlay').map((el) => el.text())).toEqual(['1', '2', '3'])
    expect(rendered).toEqual([])
    intersect([boxes[1].element])
    await flushPromises()
    expect(rendered).toEqual([2])
    intersect([boxes[1].element])
    await flushPromises()
    // A drawn page is not drawn again at the same width.
    expect(rendered).toEqual([2])
    wrapper.unmount()
  })
})
