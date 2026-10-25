import { describe, expect, it } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { mount } from '@vue/test-utils'
import { displaySize, normalizedToPdf, type PageMetric } from '@/shared/coords'
import { dragRect, nudge, pageSteps, useDragResize, type Handle } from '@/shared/composables/useDragResize'
import { readFixtureJson } from './fixtures'

interface FixturePage {
  page: number
  cropbox: [number, number, number, number]
  rotation: number
}

const fixtures = readFixtureJson<{ fixtures: Record<string, { pages: FixturePage[] }> }>(
  'coords.json',
).fixtures
const metrics: [string, PageMetric][] = Object.entries(fixtures).map(([file, fixture]) => {
  const [x0, y0, x1, y1] = fixture.pages[0].cropbox
  return [
    file,
    { page: 1, width: x1 - x0, height: y1 - y0, rotation: fixture.pages[0].rotation, left: x0, bottom: y0 },
  ]
})

const start = { x: 0.2, y: 0.3, w: 0.25, h: 0.05 }

describe('dragRect on every coords.json page', () => {
  it.each(metrics)('%s: a move lands on the 4 pt grid of the displayed page', (_file, metric) => {
    const viewport = { width: 390, height: (390 * displaySize(metric).height) / displaySize(metric).width }
    const steps = pageSteps(metric)
    const moved = dragRect(start, 'move', 37, 53, viewport, steps)
    const size = displaySize(metric)
    for (const [value, length] of [
      [moved.x * size.width, 4],
      [moved.y * size.height, 4],
    ]) {
      expect(Math.abs(value / length - Math.round(value / length))).toBeLessThan(1e-6)
    }
    expect(moved.w).toBeCloseTo(start.w, 9)
    expect(moved.h).toBeCloseTo(start.h, 9)
    // The PDF rect the server will use stays inside the visible page box.
    const [llx, lly, urx, ury] = normalizedToPdf(metric, moved)
    expect(llx).toBeGreaterThanOrEqual(metric.left - 1e-6)
    expect(lly).toBeGreaterThanOrEqual(metric.bottom - 1e-6)
    expect(urx).toBeLessThanOrEqual(metric.left + metric.width + 1e-6)
    expect(ury).toBeLessThanOrEqual(metric.bottom + metric.height + 1e-6)
  })

  it.each(metrics)('%s: stays on the page and keeps its minimum size', (_file, metric) => {
    const steps = pageSteps(metric)
    const viewport = { width: 600, height: 800 }
    const flung = dragRect(start, 'move', 5000, -5000, viewport, steps)
    expect(flung.x + flung.w).toBeLessThanOrEqual(1 + 1e-9)
    expect(flung.y).toBe(0)
    const squashed = dragRect(start, 'se', -5000, -5000, viewport, steps)
    expect(squashed.w).toBeCloseTo(steps.min.w, 9)
    expect(squashed.h).toBeCloseTo(steps.min.h, 9)
    expect(squashed.x).toBeCloseTo(start.x, 9)
  })
})

describe('handles', () => {
  const metric: PageMetric = { page: 1, width: 600, height: 800, rotation: 0, left: 0, bottom: 0 }
  const steps = pageSteps(metric)
  const viewport = { width: 600, height: 800 }

  it.each<[Handle, number, number, (r: typeof start) => void]>([
    // The right edge (270 pt) moves to 330 pt and snaps to the 4 pt grid: 332 pt.
    ['e', 60, 0, (r) => expect([r.x, r.w]).toEqual([0.2, expect.closeTo(332 / 600 - 0.2, 9)])],
    ['w', 60, 0, (r) => expect([r.x, r.w]).toEqual([expect.closeTo(0.3, 9), expect.closeTo(0.15, 9)])],
    ['s', 0, 40, (r) => expect([r.y, r.h]).toEqual([0.3, expect.closeTo(0.1, 9)])],
    ['n', 0, -40, (r) => expect([r.y, r.h]).toEqual([expect.closeTo(0.25, 9), expect.closeTo(0.1, 9)])],
  ])('%s handle', (handle, dx, dy, check) => {
    check(dragRect(start, handle, dx, dy, viewport, steps))
  })

  it('nudges by one grid step, ten with shift', () => {
    expect(nudge(start, 'ArrowRight', steps).x).toBeCloseTo(0.2 + 4 / 600, 9)
    expect(nudge(start, 'ArrowUp', steps, true).y).toBeCloseTo(0.3 - 40 / 800, 9)
    expect(nudge(start, 'Enter', steps)).toBe(start)
  })
})

describe('useDragResize', () => {
  it('follows the pointer and reports the end', async () => {
    const rect = ref({ ...start })
    const ended: unknown[] = []
    const Probe = defineComponent({
      setup() {
        const drag = useDragResize(rect, {
          viewport: () => ({ width: 600, height: 800 }),
          steps: () => pageSteps({ page: 1, width: 600, height: 800, rotation: 0, left: 0, bottom: 0 }),
          onChange: (next) => (rect.value = next),
          onEnd: (next) => ended.push(next),
        })
        return () => h('div', { onPointerdown: (e: PointerEvent) => drag.begin(e) })
      },
    })
    const wrapper = mount(Probe, { attachTo: document.body })
    wrapper.element.dispatchEvent(
      new MouseEvent('pointerdown', { clientX: 100, clientY: 100, button: 0, bubbles: true }),
    )
    window.dispatchEvent(new MouseEvent('pointermove', { clientX: 160, clientY: 180 }) as PointerEvent)
    window.dispatchEvent(new MouseEvent('pointerup') as PointerEvent)
    expect(rect.value.x).toBeCloseTo(0.3, 9)
    expect(rect.value.y).toBeCloseTo(0.4, 9)
    expect(ended).toHaveLength(1)
    wrapper.unmount()
  })
})
