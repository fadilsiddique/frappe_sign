// Typed and drawn signatures become PNG images in the browser; the server only stores images.
import { __ } from '@/shared/translate'

export interface ScriptFont {
  family: string
  label: string
  arabic: boolean
}

// Bundled OFL fonts (src/guest/fonts/), loaded only when the Type tab is used.
export const SCRIPT_FONTS: ScriptFont[] = [
  { family: 'Frappe Sign Great Vibes', label: 'Great Vibes', arabic: false },
  { family: 'Frappe Sign Dancing Script', label: 'Dancing Script', arabic: false },
  { family: 'Frappe Sign Aref Ruqaa', label: 'Aref Ruqaa', arabic: true },
]

const ARABIC = /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFC]/

export function hasArabic(text: string): boolean {
  return ARABIC.test(text)
}

export function fontsFor(text: string): ScriptFont[] {
  return hasArabic(text) ? SCRIPT_FONTS.filter((f) => f.arabic) : SCRIPT_FONTS.filter((f) => !f.arabic)
}

export const INK = '#1e3a8a'

// Draw `text` in a script font on a transparent canvas and return a trimmed PNG data URL.
export async function typedSignature(text: string, font: ScriptFont, height = 120): Promise<string> {
  const value = text.trim()
  if (!value) throw new Error(__('Type your name first.'))
  const size = Math.round(height * 0.6)
  await document.fonts.load(`${size}px "${font.family}"`, value)
  const canvas = document.createElement('canvas')
  const context = canvas.getContext('2d')!
  context.font = `${size}px "${font.family}"`
  canvas.width = Math.ceil(context.measureText(value).width + size)
  canvas.height = height
  context.font = `${size}px "${font.family}"`
  context.fillStyle = INK
  context.textBaseline = 'middle'
  context.direction = hasArabic(value) ? 'rtl' : 'ltr'
  context.textAlign = 'center'
  context.fillText(value, canvas.width / 2, height / 2)
  return trimmed(canvas).toDataURL('image/png')
}

// Crop transparent margins so the signature fills its field.
export function trimmed(canvas: HTMLCanvasElement, padding = 4): HTMLCanvasElement {
  const context = canvas.getContext('2d')
  if (!context || !canvas.width || !canvas.height) return canvas
  const { data, width, height } = context.getImageData(0, 0, canvas.width, canvas.height)
  let top = height
  let left = width
  let right = -1
  let bottom = -1
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (data[(y * width + x) * 4 + 3] > 8) {
        if (x < left) left = x
        if (x > right) right = x
        if (y < top) top = y
        if (y > bottom) bottom = y
      }
    }
  }
  if (right < 0) return canvas
  const out = document.createElement('canvas')
  out.width = right - left + 1 + padding * 2
  out.height = bottom - top + 1 + padding * 2
  out
    .getContext('2d')!
    .drawImage(canvas, left - padding, top - padding, out.width, out.height, 0, 0, out.width, out.height)
  return out
}

export function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}
