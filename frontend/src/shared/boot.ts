// Boot data that www/sign.py and www/s.py put on window.frappe_sign. In the Vite dev server there is
// no boot block, so every field has a default.
export interface Branding {
  company: string | null
  logo: string | null
  brand_color: string | null
}

export interface Boot {
  user: string | null
  // Staff app only: the sidebar's user menu.
  full_name: string | null
  user_image: string | null
  lang: string
  dir: 'ltr' | 'rtl'
  branding: Branding
  messages: Record<string, string>
}

declare global {
  interface Window {
    frappe_sign?: Partial<Boot>
    csrf_token?: string
  }
}

const DEFAULT_BOOT: Boot = {
  user: null,
  full_name: null,
  user_image: null,
  lang: 'en',
  dir: 'ltr',
  branding: { company: null, logo: null, brand_color: null },
  messages: {},
}

export function readBoot(source: Partial<Boot> | undefined = window.frappe_sign): Boot {
  return {
    ...DEFAULT_BOOT,
    ...source,
    branding: { ...DEFAULT_BOOT.branding, ...source?.branding },
  }
}

// Language and direction go on <html> so Tailwind logical properties (ms-, pe-) follow RTL.
export function applyBoot(boot: Boot, root: HTMLElement = document.documentElement): void {
  root.lang = boot.lang
  root.dir = boot.dir
  if (boot.branding.brand_color) root.style.setProperty('--sign-brand', boot.branding.brand_color)
}
