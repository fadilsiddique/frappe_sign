// The staff app's sections, shared by the sidebar and the mobile tab bar (UX_PLAN "Shell", D18).
import type { RouteDestination } from 'frappe-ui'

export interface NavItem {
  key: 'home' | 'to-sign' | 'sent' | 'templates' | 'settings'
  label: string
  icon: string
  route?: RouteDestination
  href?: string
  // Route names that light this item up.
  activeFor: string[]
}

export const NAV_ITEMS: NavItem[] = [
  { key: 'home', label: 'Home', icon: 'lucide-house', route: '/', activeFor: ['Home'] },
  // Home's "For you to sign" panel until a page of its own exists (U.3).
  {
    key: 'to-sign',
    label: 'To sign',
    icon: 'lucide-pen-line',
    route: { path: '/', hash: '#to-sign' },
    activeFor: [],
  },
  {
    key: 'sent',
    label: 'Sent',
    icon: 'lucide-send',
    route: '/requests',
    activeFor: ['Requests', 'Request', 'SendWizard'],
  },
  {
    key: 'templates',
    label: 'Templates',
    icon: 'lucide-file-text',
    route: '/templates',
    activeFor: ['Templates', 'Designer'],
  },
  // Desk's Sign Settings form until /sign/settings exists (U.9).
  { key: 'settings', label: 'Settings', icon: 'lucide-settings', href: '/app/sign-settings', activeFor: [] },
]

export const DESK_URL = '/app'

export function isActive(item: NavItem, routeName: unknown): boolean {
  return item.activeFor.includes(String(routeName))
}
