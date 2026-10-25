// Mirror of frappe_sign/pdf/types.py (D7). Both are tested against tests/fixtures/coords.json;
// change them together.
//
// Normalized: x, y, w, h in 0..1, top-left origin, visible page (CropBox after /Rotate).
// Display: points from the top-left of the visible page. pdf.js viewports use this space, scaled.
// User space: PDF points in the page's own coordinate system, before /Rotate.

export interface Rect {
  x: number
  y: number
  w: number
  h: number
}

// [llx, lly, urx, ury] in PDF user space.
export type Box = [number, number, number, number]

export interface PageMetric {
  page: number
  width: number
  height: number
  rotation: number
  left: number
  bottom: number
}

export function normalizeRotation(rotation: number): 0 | 90 | 180 | 270 {
  const value = ((rotation % 360) + 360) % 360
  if (value !== 0 && value !== 90 && value !== 180 && value !== 270) {
    throw new Error(`/Rotate ${rotation} is not a multiple of 90`)
  }
  return value
}

export function displaySize(metric: PageMetric): { width: number; height: number } {
  const turned = normalizeRotation(metric.rotation) % 180 !== 0
  return turned
    ? { width: metric.height, height: metric.width }
    : { width: metric.width, height: metric.height }
}

export function displayToUser(metric: PageMetric, x: number, y: number): [number, number] {
  const { left, bottom } = metric
  const right = left + metric.width
  const top = bottom + metric.height
  switch (normalizeRotation(metric.rotation)) {
    case 90:
      return [left + y, bottom + x]
    case 180:
      return [right - x, bottom + y]
    case 270:
      return [right - y, top - x]
    default:
      return [left + x, top - y]
  }
}

export function userToDisplay(metric: PageMetric, ux: number, uy: number): [number, number] {
  const { left, bottom } = metric
  const right = left + metric.width
  const top = bottom + metric.height
  switch (normalizeRotation(metric.rotation)) {
    case 90:
      return [uy - bottom, ux - left]
    case 180:
      return [right - ux, uy - bottom]
    case 270:
      return [top - uy, right - ux]
    default:
      return [ux - left, top - uy]
  }
}

export function normalizedToPdf(metric: PageMetric, rect: Rect): Box {
  const { width, height } = displaySize(metric)
  const corners = [rect.x, rect.x + rect.w].flatMap((cx) =>
    [rect.y, rect.y + rect.h].map((cy) => displayToUser(metric, cx * width, cy * height)),
  )
  const xs = corners.map((c) => c[0])
  const ys = corners.map((c) => c[1])
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)]
}

export function pdfToNormalized(metric: PageMetric, box: Box): Rect {
  const [llx, lly, urx, ury] = box
  const corners = [llx, urx].flatMap((ux) => [lly, ury].map((uy) => userToDisplay(metric, ux, uy)))
  const xs = corners.map((c) => c[0])
  const ys = corners.map((c) => c[1])
  const { width, height } = displaySize(metric)
  return {
    x: Math.min(...xs) / width,
    y: Math.min(...ys) / height,
    w: (Math.max(...xs) - Math.min(...xs)) / width,
    h: (Math.max(...ys) - Math.min(...ys)) / height,
  }
}

// A pdf.js viewport has the display size times its scale, so normalized <-> pixels is a plain
// scale: pdf.js already applies CropBox and /Rotate.
export function normalizedToPixels(rect: Rect, viewportWidth: number, viewportHeight: number): Rect {
  return {
    x: rect.x * viewportWidth,
    y: rect.y * viewportHeight,
    w: rect.w * viewportWidth,
    h: rect.h * viewportHeight,
  }
}

export function pixelsToNormalized(rect: Rect, viewportWidth: number, viewportHeight: number): Rect {
  return {
    x: rect.x / viewportWidth,
    y: rect.y / viewportHeight,
    w: rect.w / viewportWidth,
    h: rect.h / viewportHeight,
  }
}

// Keep a rect inside the page (0..1) without changing its size when it fits.
export function clampRect(rect: Rect, minSize = 0.005): Rect {
  const w = Math.min(Math.max(rect.w, minSize), 1)
  const h = Math.min(Math.max(rect.h, minSize), 1)
  return {
    x: Math.min(Math.max(rect.x, 0), 1 - w),
    y: Math.min(Math.max(rect.y, 0), 1 - h),
    w,
    h,
  }
}
