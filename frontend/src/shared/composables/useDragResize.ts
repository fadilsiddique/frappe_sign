// Move and resize a normalized field rect with pointer events (DESIGN 7.4). The geometry is in
// `dragRect`, a pure function: snap to a grid in PDF points, keep a minimum size, stay on the page.
import { onBeforeUnmount, ref, type Ref } from 'vue'
import { clampRect, displaySize, type PageMetric, type Rect } from '@/shared/coords'

export type Handle = 'move' | 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw'

export const GRID_POINTS = 4
export const MIN_POINTS = 8

export interface Viewport {
  width: number
  height: number
}

// Grid and minimum size of a page as normalized steps (x relative to width, y to height).
export function pageSteps(metric: PageMetric, gridPoints = GRID_POINTS, minPoints = MIN_POINTS) {
  const { width, height } = displaySize(metric)
  return {
    grid: { x: gridPoints / width, y: gridPoints / height },
    min: { w: minPoints / width, h: minPoints / height },
  }
}

function snap(value: number, step: number): number {
  return step > 0 ? Math.round(value / step) * step : value
}

// The rect after dragging `handle` by (dx, dy) screen pixels on a page drawn at `viewport` size.
export function dragRect(
  start: Rect,
  handle: Handle,
  dx: number,
  dy: number,
  viewport: Viewport,
  steps: ReturnType<typeof pageSteps>,
): Rect {
  const nx = dx / viewport.width
  const ny = dy / viewport.height
  let left = start.x
  let top = start.y
  let right = start.x + start.w
  let bottom = start.y + start.h
  if (handle === 'move') {
    const x = snap(start.x + nx, steps.grid.x)
    const y = snap(start.y + ny, steps.grid.y)
    return clampRect({ x, y, w: start.w, h: start.h }, 0)
  }
  if (handle.includes('w')) left = Math.min(snap(left + nx, steps.grid.x), right - steps.min.w)
  if (handle.includes('e')) right = Math.max(snap(right + nx, steps.grid.x), left + steps.min.w)
  if (handle.includes('n')) top = Math.min(snap(top + ny, steps.grid.y), bottom - steps.min.h)
  if (handle.includes('s')) bottom = Math.max(snap(bottom + ny, steps.grid.y), top + steps.min.h)
  left = Math.max(0, left)
  top = Math.max(0, top)
  right = Math.min(1, right)
  bottom = Math.min(1, bottom)
  return { x: left, y: top, w: right - left, h: bottom - top }
}

// Arrow keys move by one grid step; with Shift by ten.
export function nudge(rect: Rect, key: string, steps: ReturnType<typeof pageSteps>, big = false): Rect {
  const factor = big ? 10 : 1
  const moves: Record<string, [number, number]> = {
    ArrowLeft: [-1, 0],
    ArrowRight: [1, 0],
    ArrowUp: [0, -1],
    ArrowDown: [0, 1],
  }
  const move = moves[key]
  if (!move) return rect
  return clampRect(
    { ...rect, x: rect.x + move[0] * steps.grid.x * factor, y: rect.y + move[1] * steps.grid.y * factor },
    0,
  )
}

export interface DragResizeOptions {
  viewport: () => Viewport
  steps: () => ReturnType<typeof pageSteps>
  onChange: (rect: Rect) => void
  onEnd?: (rect: Rect) => void
}

export function useDragResize(rect: Ref<Rect>, options: DragResizeOptions) {
  const dragging = ref<Handle | null>(null)
  let origin = { x: 0, y: 0 }
  let start: Rect = rect.value
  let last: Rect = rect.value

  function move(event: PointerEvent) {
    if (!dragging.value) return
    last = dragRect(
      start,
      dragging.value,
      event.clientX - origin.x,
      event.clientY - origin.y,
      options.viewport(),
      options.steps(),
    )
    options.onChange(last)
  }

  function stop() {
    if (!dragging.value) return
    dragging.value = null
    window.removeEventListener('pointermove', move)
    window.removeEventListener('pointerup', stop)
    window.removeEventListener('pointercancel', stop)
    options.onEnd?.(last)
  }

  function begin(event: PointerEvent, handle: Handle = 'move') {
    if (event.button !== undefined && event.button !== 0) return
    event.preventDefault()
    event.stopPropagation()
    origin = { x: event.clientX, y: event.clientY }
    start = { ...rect.value }
    last = start
    dragging.value = handle
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', stop)
    window.addEventListener('pointercancel', stop)
  }

  onBeforeUnmount(stop)
  return { dragging, begin, stop }
}
