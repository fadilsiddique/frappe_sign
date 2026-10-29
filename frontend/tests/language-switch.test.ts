import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import LanguageSwitch from '@/shared/components/LanguageSwitch.vue'

function boot(lang: string) {
  window.frappe_sign = { lang, dir: lang === 'ar' ? 'rtl' : 'ltr' }
}

afterEach(() => {
  delete window.frappe_sign
  vi.restoreAllMocks()
})

describe('LanguageSwitch', () => {
  it('offers Arabic on an English page and English on an Arabic one, each in its own language', () => {
    boot('en')
    expect(mount(LanguageSwitch).text()).toBe('العربية')
    boot('ar')
    expect(mount(LanguageSwitch).text()).toBe('English')
  })

  it('stores the preferred language and reloads', async () => {
    boot('en')
    const reload = vi.fn()
    vi.stubGlobal('location', { ...window.location, reload })
    await mount(LanguageSwitch).trigger('click')
    expect(document.cookie).toContain('preferred_language=ar')
    expect(reload).toHaveBeenCalled()
    vi.unstubAllGlobals()
  })
})
