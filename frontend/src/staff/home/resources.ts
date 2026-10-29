// Home's server data. The sidebar shares them (To sign count, setup steps left): one request each.
// frappe-ui keeps cached resources in the browser too, so the cache key carries the user.
import { createResource } from 'frappe-ui'
import { readBoot } from '@/shared/boot'

const cacheKey = (name: string) => ['frappe_sign', name, readBoot().user ?? '']

export function useDashboard() {
  return createResource({
    url: 'frappe_sign.api.staff.get_dashboard',
    cache: cacheKey('dashboard'),
    auto: true,
  })
}

export function useSetupStatus() {
  return createResource({
    url: 'frappe_sign.api.staff.get_setup_status',
    cache: cacheKey('setup'),
    auto: true,
  })
}
