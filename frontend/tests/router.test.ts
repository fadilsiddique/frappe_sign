import { describe, expect, it } from 'vitest'
import { createMemoryHistory, createWebHistory } from 'vue-router'
import { createGuestRouter, GUEST_BASE } from '@/guest/router'
import { createStaffRouter, STAFF_BASE } from '@/staff/router'

describe('routers', () => {
  it('serves the staff app under /sign', () => {
    const router = createStaffRouter(createWebHistory(STAFF_BASE))
    expect(router.resolve('/').href).toBe('/sign/')
    expect(router.resolve('/').name).toBe('Home')
  })

  it('serves the guest app under /s with the token as a route param', () => {
    const router = createGuestRouter(createWebHistory(GUEST_BASE))
    const route = router.resolve('/abc123')
    expect(route.href).toBe('/s/abc123')
    expect(route.name).toBe('Sign')
    expect(route.params.token).toBe('abc123')
  })

  it('catches unknown paths', () => {
    expect(createStaffRouter(createMemoryHistory()).resolve('/nope/deeper').name).toBe('NotFound')
  })
})
