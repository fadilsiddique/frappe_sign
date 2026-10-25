import { onScopeDispose, ref, type Ref } from 'vue'

// Below Tailwind's `sm` breakpoint the app uses MobileShell and the mobile page header.
export const MOBILE_QUERY = '(max-width: 639px)'

export function useIsMobile(): Ref<boolean> {
  if (typeof window.matchMedia !== 'function') return ref(false)
  const query = window.matchMedia(MOBILE_QUERY)
  const isMobile = ref(query.matches)
  const update = (event: MediaQueryListEvent) => (isMobile.value = event.matches)
  query.addEventListener('change', update)
  onScopeDispose(() => query.removeEventListener('change', update))
  return isMobile
}
