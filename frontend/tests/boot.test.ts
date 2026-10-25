import { describe, expect, it } from 'vitest'
import { applyBoot, readBoot } from '@/shared/boot'
import { __, setMessages } from '@/shared/translate'

describe('boot', () => {
  it('falls back to defaults without a boot block', () => {
    expect(readBoot(undefined)).toMatchObject({
      lang: 'en',
      dir: 'ltr',
      user: null,
      full_name: null,
      user_image: null,
    })
  })

  it('keeps branding defaults for missing keys', () => {
    const boot = readBoot({
      dir: 'rtl',
      branding: { company: 'Upscape', logo: null, brand_color: '#0f766e' },
    })
    expect(boot.dir).toBe('rtl')
    expect(boot.branding.company).toBe('Upscape')
  })

  it('puts language, direction and brand colour on the root element', () => {
    const root = document.createElement('html')
    applyBoot(
      readBoot({ lang: 'ar', dir: 'rtl', branding: { company: null, logo: null, brand_color: '#123456' } }),
      root,
    )
    expect(root.lang).toBe('ar')
    expect(root.dir).toBe('rtl')
    expect(root.style.getPropertyValue('--sign-brand')).toBe('#123456')
  })
})

describe('__', () => {
  it('translates and fills positional placeholders', () => {
    setMessages({ 'Signed by {0}': 'وقعه {0}' })
    expect(__('Signed by {0}', ['Ahmed'])).toBe('وقعه Ahmed')
    expect(__('Untranslated {0} {1}', [1])).toBe('Untranslated 1 {1}')
    setMessages({})
  })
})
