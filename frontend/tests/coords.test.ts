import { describe, expect, it } from 'vitest'
import {
  clampRect,
  displaySize,
  displayToUser,
  normalizedToPdf,
  normalizedToPixels,
  pdfToNormalized,
  pixelsToNormalized,
  userToDisplay,
  type Box,
  type PageMetric,
  type Rect,
} from '@/shared/coords'
import { readFixtureJson } from './fixtures'

interface FixturePage {
  page: number
  cropbox: Box
  rotation: number
  display_width: number
  display_height: number
}

interface FixtureCase {
  name: string
  page: number
  rect: Rect
  pdf_rect: Box
}

interface Fixture {
  pages: FixturePage[]
  cases: FixtureCase[]
}

// The same file drives frappe_sign/tests/unit/test_coords.py (CLAUDE.md, testing rules).
const fixtures = readFixtureJson<{ fixtures: Record<string, Fixture> }>('coords.json').fixtures
const DIGITS = 3

function metricOf(page: FixturePage): PageMetric {
  const [x0, y0, x1, y1] = page.cropbox
  return { page: page.page, width: x1 - x0, height: y1 - y0, rotation: page.rotation, left: x0, bottom: y0 }
}

const cases = Object.entries(fixtures).flatMap(([file, fixture]) =>
  fixture.cases.map((item) => {
    const page = fixture.pages.find((p) => p.page === item.page)!
    return { file, page, metric: metricOf(page), item }
  }),
)

function expectClose(actual: number[], expected: number[]): void {
  actual.forEach((value, index) => expect(value).toBeCloseTo(expected[index], DIGITS))
}

describe('coords.json', () => {
  it('has cases for every geometric fixture', () => {
    expect(Object.keys(fixtures)).toHaveLength(5)
    expect(cases.length).toBeGreaterThanOrEqual(15)
  })

  it.each(cases)('$file $item.name: display size', ({ page, metric }) => {
    const size = displaySize(metric)
    expect(size.width).toBeCloseTo(page.display_width, DIGITS)
    expect(size.height).toBeCloseTo(page.display_height, DIGITS)
  })

  it.each(cases)('$file $item.name: normalized to PDF user space', ({ metric, item }) => {
    expectClose(normalizedToPdf(metric, item.rect), item.pdf_rect)
  })

  it.each(cases)('$file $item.name: PDF user space back to normalized', ({ metric, item }) => {
    const rect = pdfToNormalized(metric, item.pdf_rect)
    expectClose([rect.x, rect.y, rect.w, rect.h], [item.rect.x, item.rect.y, item.rect.w, item.rect.h])
  })

  it.each(cases)('$file: display points round trip', ({ metric }) => {
    const { width, height } = displaySize(metric)
    for (const [x, y] of [
      [0, 0],
      [12.5, 30],
      [width, height],
    ]) {
      const [ux, uy] = displayToUser(metric, x, y)
      expectClose(userToDisplay(metric, ux, uy), [x, y])
    }
  })
})

describe('pixels', () => {
  it('scales normalized rects to a viewport and back', () => {
    const rect = { x: 0.1, y: 0.2, w: 0.3, h: 0.05 }
    const pixels = normalizedToPixels(rect, 800, 1000)
    expect(pixels).toEqual({ x: 80, y: 200, w: 240, h: 50 })
    const back = pixelsToNormalized(pixels, 800, 1000)
    expectClose([back.x, back.y, back.w, back.h], [0.1, 0.2, 0.3, 0.05])
  })

  it('clamps rects inside the page', () => {
    expect(clampRect({ x: 0.9, y: -0.1, w: 0.2, h: 0.1 })).toEqual({ x: 0.8, y: 0, w: 0.2, h: 0.1 })
  })

  it('rejects rotations that are not a multiple of 90', () => {
    expect(() => displaySize({ page: 1, width: 1, height: 1, rotation: 45, left: 0, bottom: 0 })).toThrow()
  })
})
